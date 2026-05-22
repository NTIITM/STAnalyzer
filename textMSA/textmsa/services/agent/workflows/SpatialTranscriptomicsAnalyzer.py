import copy
import numpy as np
import pandas as pd
import scanpy as sc
import squidpy as sq
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from torch.nn import Parameter
from torch_geometric.data import Data
from torch_geometric.nn.conv import MessagePassing
from torch_geometric.utils import add_self_loops, remove_self_loops, softmax
from sklearn.cluster import KMeans
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from scipy import stats
from scipy.spatial.distance import pdist, squareform
from typing import List, Dict, Optional, Tuple
import os
import json
from datetime import datetime
import warnings
from openai import OpenAI

warnings.filterwarnings('ignore')

# OpenAI客户端配置
client = OpenAI(
    api_key=os.getenv("SPATIAL_ANALYZER_API_KEY", "replace_me"),
    base_url=os.getenv("SPATIAL_ANALYZER_BASE_URL", "https://api.openai.com/v1"),
)


# ------------------------------ 大模型交互模块 ------------------------------
class Prompter:
    """生成大模型提示的类（包含细胞微环境分析模板）"""

    def __init__(self, template_dir="prompt_templates"):
        self.template_dir = template_dir
        os.makedirs(template_dir, exist_ok=True)
        self._create_default_templates()

    def _create_default_templates(self):
        """创建所有必要的提示模板"""
        templates = {
            # 高可变基因背景信息分析模板
            "hv_genes_background.txt": (
                "基于以下高可变基因列表，按**递进逻辑**完成分析，为后续基因筛选和组织交互探究提供依据：\n"
                "- 高可变基因列表：{hv_genes}\n\n"
                "请严格按以下4个步骤回答（总字数400-500字）：\n"
                "1. **基因功能与通路分析**\n"
                "   归纳这些基因的核心功能及主要参与的信号通路，列举3-5个代表性基因及其功能。\n"
                "\n2. **组织/器官来源推断**\n"
                "   基于上述功能特征，推断该空间转录组数据最可能来自哪种组织/器官，说明判断依据。\n"
                "\n3. **发育/生理状态判断**\n"
                "   结合组织来源，推测该样本处于什么发育阶段或生理状态，哪些基因是关键标志物？\n"
                "\n4. **技术噪声提示**\n"
                "   哪些基因的高变异性可能源于技术限制而非生物学意义？"
            ),
            # 高可变基因筛选模板
            "hv_genes_refilter.txt": (
                "根据以下信息，从当前基因段中标记出**不可用基因**（需排除的基因）：\n"
                "- 基因段：{gene_chunk}\n"
                "- 组织背景：{tissue_context}\n"
                "不可用基因定义：\n"
                "1. 管家基因（参与基础代谢、核糖体功能等普遍表达的基因）\n"
                "2. 与该组织空间区域特异性无关的基因\n"
                "3. 可能因技术限制导致的假阳性高变基因\n"
                "\n请严格按照以下格式返回结果，不得添加额外内容：\n"
                "【不可用基因列表】\n"
                "gene1\n"
                "gene2\n"
                "gene3\n"
                "...\n"
                "【排除理由】\n"
                "（200字内，说明排除这些基因的主要依据，区分生物学排除和技术排除）\n"
            ),
            # 区域基因功能分析模板
            "region_gene_function.txt": (
                "基于以下信息，分析空间区域{region}中差异表达基因的功能作用及空间调控关系：\n"
                "- 组织背景：{tissue_context}\n"
                "- 差异表达基因（按表达强度排序）：{de_genes}\n"
                "- 基因空间表达特征：{spatial_features}\n"
                "- 该区域相邻区域：{adjacent_regions}\n"
                "\n请按以下结构分析（总字数500字左右）：\n"
                "1. 空间表达模式总结：关键基因的梯度分布、斑块分布等特征及其生物学意义。\n"
                "2. 功能调控网络：结合空间分布，分析基因间可能的调控关系（如梯度相关基因的上下游作用）。\n"
                "3. 区域功能：结合空间差异表达基因，分析该区域的特定功能。\n"
            ),
            # 区域交互分析模板
            "region_interaction.txt": (
                "分析区域{regions}之间的相互作用：\n{region_info}\n"
                "要求：评估空间邻近性、基因功能互作及功能协同关系，400字中文。"
            ),
            # 细胞微环境分析模板
            "cell_microenvironment.txt": (
                "分析指定细胞与其空间邻居构成的微环境相互作用：\n"
                "- 组织背景：{tissue_context}\n"
                "- 指定细胞ID：{cell_id}\n"
                "- 微环境组成：该细胞+{n_neighbors}个空间邻居\n"
                "- 细胞特异性高表达基因：{cell_specific_genes}\n"
                "- 邻居共同高表达基因：{neighbor_common_genes}\n"
                "\n请按以下结构分析（总字数500字左右）：\n"
                "1. 微环境功能特征：基于共同高表达基因，该微环境可能参与哪些生物学过程？\n"
                "2. 目标细胞的作用：其特异性高表达基因如何影响邻居细胞（如信号传递、免疫调节）？\n"
                "3. 微环境对目标细胞的影响：邻居的共同基因如何调控目标细胞的状态（如增殖、分化）？\n"
                "4. 潜在调控关系：细胞与邻居之间可能存在哪些基因调控网络（如配体-受体互作）？"
            )
        }

        for filename, content in templates.items():
            filepath = os.path.join(self.template_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

    def get_prompt(self, template_name: str, **kwargs) -> str:
        template_path = os.path.join(self.template_dir, template_name)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"模板不存在: {template_path}")
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read().format(**kwargs)


class LLMIntegrator:
    """大模型交互封装类（包含细胞微环境分析）"""

    def __init__(self, prompter: Prompter, model_name: str = "deepseek-chat", log_dir: str = "llm_interactions"):
        self.prompter = prompter
        self.model_name = model_name
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.interaction_count = 0
        self.tissue_context = ""

    def _log_qa(self, query: str, response: str, interaction_type: str) -> None:
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{interaction_type}_qa_{self.interaction_count}.txt"
        filepath = os.path.join(self.log_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"【问题】\n{query}\n\n【回答】\n{response}\n")
        print(f"已记录交互到: {filepath}")

    def call_model(self, system_prompt: str, user_prompt: str, temperature: float = 0.4,
                   max_tokens: int = 1000, interaction_type: str = "general") -> str:
        try:
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            response_content = response.choices[0].message.content.strip()
            full_query = f"系统提示: {system_prompt}\n用户问题: {user_prompt}"
            self._log_qa(full_query, response_content, interaction_type)
            return response_content
        except Exception as e:
            error_msg = f"大模型调用失败: {str(e)}"
            print(error_msg)
            self._log_qa(user_prompt, error_msg, f"{interaction_type}_error")
            return error_msg

    def analyze_hv_background(self, hv_genes: List[str], n_hvg_genes=30) -> tuple[list[str], str]:
        prompt = self.prompter.get_prompt(
            "hv_genes_background.txt",
            hv_genes=", ".join(hv_genes[:n_hvg_genes]),
        )
        background_analysis = self.call_model(
            system_prompt="你是空间转录组学专家，需按递进逻辑分析基因功能→组织来源→发育状态→技术噪声。",
            user_prompt=prompt,
            temperature=0.5,
            interaction_type="hv_background_analysis"
        )
        self.tissue_context = background_analysis
        return (hv_genes[:n_hvg_genes], background_analysis)

    def refilter_hv_genes(self, initial_hv_genes: List[str], background_analysis: str,
                          chunk_size: Optional[int] = None) -> Tuple[List[str], List[str]]:
        all_unavailable = []
        all_reasons = []
        if chunk_size and chunk_size > 0:
            chunks = [initial_hv_genes[i:i + chunk_size] for i in range(0, len(initial_hv_genes), chunk_size)]
            print(f"将{len(initial_hv_genes)}个基因分为{len(chunks)}段")
            for i, chunk in enumerate(chunks):
                if not chunk:
                    continue
                unavailable, reason = self._refilter_single_chunk(chunk, background_analysis)
                all_unavailable.extend(unavailable)
                all_reasons.append(f"第{i + 1}段筛选理由: {reason}")
        else:
            unavailable, reason = self._refilter_single_chunk(initial_hv_genes, background_analysis)
            all_unavailable = unavailable
            all_reasons = [reason]
        all_unavailable = list(set(all_unavailable))
        available_genes = [gene for gene in initial_hv_genes if gene not in all_unavailable]
        return available_genes, all_reasons

    def _refilter_single_chunk(self, gene_chunk: List[str], background_analysis: str) -> Tuple[List[str], str]:
        prompt = self.prompter.get_prompt(
            "hv_genes_refilter.txt",
            gene_chunk=", ".join(gene_chunk),
            tissue_context=self.tissue_context
        )
        response = self.call_model(
            system_prompt="你需根据组织背景标记不可用基因，包括管家基因和技术噪声导致的假阳性。",
            user_prompt=prompt,
            temperature=0.3,
            interaction_type="hv_gene_filtering"
        )
        try:
            if "【不可用基因列表】" not in response or "【排除理由】" not in response:
                raise ValueError("缺少格式标记")
            unavailable_genes_part = response.split("【不可用基因列表】")[1].split("【排除理由】")[0].strip()
            unavailable_genes = [line.strip() for line in unavailable_genes_part.split("\n") if line.strip()]
            reason_part = response.split("【排除理由】")[1].strip()
            return unavailable_genes, reason_part
        except Exception as e:
            print(f"解析失败: {e}")
            return [], "解析格式异常"

    def analyze_region_genes(self, region: str, de_genes: List[str], adjacent_regions: List[str],
                             spatial_features: Dict) -> str:
        """分析区域基因功能，融入空间表达特征"""
        prompt = self.prompter.get_prompt(
            "region_gene_function.txt",
            region=region,
            tissue_context=self.tissue_context,
            de_genes=", ".join(de_genes[:10]),  # 取前10个关键基因
            spatial_features=json.dumps(spatial_features, ensure_ascii=False),  # 空间特征JSON
            adjacent_regions=", ".join(adjacent_regions)
        )
        return self.call_model(
            system_prompt="你是空间分子生物学专家，需结合基因空间表达模式（梯度、分布等）分析其功能作用。",
            user_prompt=prompt,
            temperature=0.6,
            interaction_type=f"region_{region}_gene_analysis"
        )

    def analyze_cell_microenvironment(self, cell_id: str, n_neighbors: int,
                                      cell_specific_genes: List[str], neighbor_common_genes: List[str]) -> str:
        """分析指定细胞与其邻居的微环境相互作用"""
        prompt = self.prompter.get_prompt(
            "cell_microenvironment.txt",
            tissue_context=self.tissue_context,
            cell_id=cell_id,
            n_neighbors=n_neighbors,
            cell_specific_genes=", ".join(cell_specific_genes[:10]),  # 取前10个
            neighbor_common_genes=", ".join(neighbor_common_genes[:10]),
        )
        return self.call_model(
            system_prompt="你是细胞微环境专家，擅长分析细胞与其空间邻居的基因表达互作及功能关系。",
            user_prompt=prompt,
            temperature=0.6,
            interaction_type=f"cell_{cell_id}_microenvironment"
        )


# ------------------------------ Stagate空间聚类模块 ------------------------------
class GATConv(MessagePassing):
    _alpha = None

    def __init__(self, in_channels, out_channels, heads: int = 1, concat: bool = True, negative_slope: float = 0.2,
                 dropout: float = 0.0, add_self_loops=True, bias=True, **kwargs):
        kwargs.setdefault("aggr", "add")
        super().__init__(node_dim=0, **kwargs)
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.heads = heads
        self.concat = concat
        self.negative_slope = negative_slope
        self.dropout = dropout
        self.add_self_loops = add_self_loops

        self.lin_src = nn.Parameter(torch.zeros(size=(in_channels, out_channels)))
        nn.init.xavier_normal_(self.lin_src.data, gain=1.414)
        self.lin_dst = self.lin_src

        self.att_src = Parameter(torch.Tensor(1, heads, out_channels))
        self.att_dst = Parameter(torch.Tensor(1, heads, out_channels))
        nn.init.xavier_normal_(self.att_src.data, gain=1.414)
        nn.init.xavier_normal_(self.att_dst.data, gain=1.414)

        self._alpha = None
        self.attentions = None

    def forward(self, x, edge_index, size=None, return_attention_weights=None, attention=True, tied_attention=None):
        H, C = self.heads, self.out_channels
        if isinstance(x, Tensor):
            x_src = x_dst = torch.mm(x, self.lin_src).view(-1, H, C)
        else:
            x_src, x_dst = x
            x_src = torch.mm(x_src, self.lin_src).view(-1, H, C)
            if x_dst is not None:
                x_dst = torch.mm(x_dst, self.lin_dst).view(-1, H, C)
        x = (x_src, x_dst)

        if not attention:
            return x[0].mean(dim=1)

        if tied_attention is None:
            alpha_src = (x_src * self.att_src).sum(dim=-1)
            alpha_dst = None if x_dst is None else (x_dst * self.att_dst).sum(-1)
            alpha = (alpha_src, alpha_dst)
            self.attentions = alpha
        else:
            alpha = tied_attention

        if self.add_self_loops:
            num_nodes = x_src.size(0)
            if x_dst is not None:
                num_nodes = min(num_nodes, x_dst.size(0))
            num_nodes = min(size) if size is not None else num_nodes
            edge_index, _ = remove_self_loops(edge_index)
            edge_index, _ = add_self_loops(edge_index, num_nodes=num_nodes)

        out = self.propagate(edge_index, x=x, alpha=alpha, size=size)
        alpha = self._alpha
        self._alpha = None

        if self.concat:
            out = out.view(-1, self.heads * self.out_channels)
        else:
            out = out.mean(dim=1)

        if isinstance(return_attention_weights, bool):
            return out, (edge_index, alpha)
        else:
            return out

    def message(self, x_j, alpha_j, alpha_i, index, ptr, size_i):
        alpha = alpha_j if alpha_i is None else alpha_j + alpha_i
        alpha = torch.sigmoid(alpha)
        alpha = softmax(alpha, index, ptr, size_i)
        self._alpha = alpha
        alpha = F.dropout(alpha, p=self.dropout, training=self.training)
        return x_j * alpha.unsqueeze(-1)


class Stagate(nn.Module):
    def __init__(self, hidden_dims, device: str = "cpu"):
        super().__init__()
        [in_dim, num_hidden, out_dim] = hidden_dims
        self.conv1 = GATConv(in_dim, num_hidden, heads=1, concat=False, dropout=0, add_self_loops=False, bias=False)
        self.conv2 = GATConv(num_hidden, out_dim, heads=1, concat=False, dropout=0, add_self_loops=False, bias=False)
        self.conv3 = GATConv(out_dim, num_hidden, heads=1, concat=False, dropout=0, add_self_loops=False, bias=False)
        self.conv4 = GATConv(num_hidden, in_dim, heads=1, concat=False, dropout=0, add_self_loops=False, bias=False)
        self.device = device
        self.to(self.device)

    def forward(self, features, edge_index):
        h1 = F.elu(self.conv1(features, edge_index))
        h2 = self.conv2(h1, edge_index, attention=False)
        self.conv3.lin_src.data = self.conv2.lin_src.transpose(0, 1)
        self.conv3.lin_dst.data = self.conv2.lin_dst.transpose(0, 1)
        self.conv4.lin_src.data = self.conv1.lin_src.transpose(0, 1)
        self.conv4.lin_dst.data = self.conv1.lin_dst.transpose(0, 1)
        h3 = F.elu(self.conv3(h2, edge_index, attention=True, tied_attention=self.conv1.attentions))
        h4 = self.conv4(h3, edge_index, attention=False)
        return h2, h4


class StagatePipeline:
    def __init__(self, adata, device="cpu"):
        self.adata = adata
        self.device = device
        self.model = None
        self.embeddings = None
        self.X_tensor = None
        self.edge_index = None
        self.data = None
        self.preprocessed = False
        self.trained = False

    def preprocess(self, n_neighbors=15, use_rep='spatial', hv_genes: Optional[List[str]] = None):
        if hv_genes is not None:
            hv_genes = list(dict.fromkeys(hv_genes))
            valid_genes = [gene for gene in hv_genes if gene in self.adata.var.index]
            if len(valid_genes) < len(hv_genes):
                invalid = len(hv_genes) - len(valid_genes)
                print(f"过滤掉{invalid}个不在数据中的基因")
            self.adata = self.adata[:, valid_genes]
        else:
            raise ValueError("请传入高可变基因列表")

        sc.pp.neighbors(self.adata, n_neighbors=n_neighbors, use_rep=use_rep)
        connectivities = self.adata.obsp['connectivities']
        row, col = connectivities.nonzero()
        self.edge_index = torch.tensor([row, col], dtype=torch.long).to(self.device)

        X = self.adata.X
        if hasattr(X, 'toarray'):
            X = X.toarray()
        self.X_tensor = torch.tensor(X, dtype=torch.float).to(self.device)
        self.data = Data(x=self.X_tensor, edge_index=self.edge_index)
        self.preprocessed = True
        print(f"预处理完成，使用{self.adata.shape[1]}个高可变基因")

    def train_model(self, hidden_channels=64, out_channels=32, epochs=500, lr=0.005, weight_decay=1e-4):
        assert self.preprocessed, "请先运行preprocess()"
        in_channels = self.X_tensor.shape[1]
        hidden_dims = [in_channels, hidden_channels, out_channels]
        self.model = Stagate(hidden_dims, device=self.device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=weight_decay)

        best_loss = float('inf')
        best_model_state_dict = None
        for epoch in range(epochs):
            self.model.train()
            optimizer.zero_grad()
            z, x_recon = self.model(self.data.x, self.data.edge_index)
            loss = F.mse_loss(x_recon, self.data.x)
            loss.backward()
            optimizer.step()

            if loss.item() < best_loss:
                best_loss = loss.item()
                best_model_state_dict = copy.deepcopy(self.model.state_dict())

            if epoch % 50 == 0:
                print(f"Epoch {epoch}, Loss: {loss.item():.6f}, Best Loss: {best_loss:.6f}")

        self.model.load_state_dict(best_model_state_dict)
        self.model.eval()
        with torch.no_grad():
            self.embeddings, _ = self.model(self.data.x, self.data.edge_index)
        self.adata.obsm['STAGATE_emb'] = self.embeddings.cpu().numpy()
        self.trained = True
        print(f"训练完成，最佳Loss: {best_loss:.6f}")

    def cluster(self, method="leiden", n_clusters=14, resolution=1.0):
        assert self.trained, "请先训练模型"
        if method == "kmeans":
            kmeans = KMeans(n_clusters=n_clusters, random_state=0).fit(self.adata.obsm['STAGATE_emb'])
            self.adata.obs['cluster'] = kmeans.labels_.astype(str)
        elif method == "leiden":
            sc.pp.neighbors(self.adata, use_rep='STAGATE_emb')
            sc.tl.leiden(self.adata, resolution=resolution, key_added='cluster')
        elif method == "louvain":
            sc.pp.neighbors(self.adata, use_rep='STAGATE_emb')
            sc.tl.louvain(self.adata, resolution=resolution, key_added='cluster')
        print(f"聚类完成，使用{method}方法得到{self.adata.obs['cluster'].nunique()}个区域")

    def get_adata(self) -> sc.AnnData:
        return self.adata


# ------------------------------ 后续分析模块 ------------------------------
class SpatialAnalyzer:
    """空间聚类结果分析（包含细胞微环境分析功能）"""

    def __init__(self, adata: sc.AnnData, x_key='x', y_key='y'):
        self.adata = adata
        self.region_markers = {}
        self.adjacent_regions = {}
        self.x_key = x_key
        self.y_key = y_key
        self.prompter = Prompter()
        self.llm = LLMIntegrator(self.prompter)
        self.region_spatial_features = None  # 存储区域空间特征

        # 预处理细胞坐标（用于邻居搜索）
        self.cell_coords = self.adata.obs[[x_key, y_key]].values
        self.knn_model = NearestNeighbors(n_neighbors=20).fit(self.cell_coords)  # 预训练KNN模型

    def identify_marker_genes(self, num_markers=50):
        sc.tl.rank_genes_groups(self.adata, groupby='cluster', method='t-test', key_added='rank_genes')
        for region in self.adata.obs['cluster'].unique():
            marker_df = sc.get.rank_genes_groups_df(self.adata, group=region, key='rank_genes').head(num_markers)
            self.region_markers[region] = {
                'genes': marker_df['names'].tolist(),
                'log2fc': marker_df['logfoldchanges'].mean(),
                'pvalues': marker_df['pvals_adj'].tolist()
            }
        print(f"标记基因识别完成，每个区域{num_markers}个基因")
        # 计算区域空间特征
        self.region_spatial_features = self.summarize_region_spatial_features(self.region_markers)

    def find_adjacent_regions(self, distance_threshold=5.0):
        from scipy.spatial import cKDTree
        coords = self.adata.obs[[self.x_key, self.y_key]].values
        tree = cKDTree(coords)
        regions = self.adata.obs['cluster'].unique()
        region_coords = {r: coords[self.adata.obs['cluster'] == r].mean(axis=0) for r in regions}

        for r in regions:
            neighbors = tree.query_ball_point(region_coords[r], distance_threshold)
            adjacent = set()
            for idx in neighbors:
                adjacent.add(self.adata.obs.iloc[idx]['cluster'])
            adjacent.discard(r)
            self.adjacent_regions[r] = sorted(adjacent)
        print("相邻区域计算完成")

    def analyze_region_gene_functions(self, region, output_dir="region_gene_analysis"):
        """分析每个区域的基因功能，融入空间表达模式"""
        os.makedirs(output_dir, exist_ok=True)
        assert region in self.adata.obs['cluster'].unique()  # 检查区域是否存在
        print(f"分析区域{region}的差异基因功能及空间模式...")
        de_genes = self.region_markers[region]['genes']
        adjacent = self.adjacent_regions.get(region, [])
        # 获取该区域的空间特征
        spatial_features = self.region_spatial_features.get(region, {})

        # 调用大模型分析（融入空间特征）
        analysis = self.llm.analyze_region_genes(
            region=region,
            de_genes=de_genes,
            adjacent_regions=adjacent,
            spatial_features=spatial_features
        )

        # 保存结果
        output_file = os.path.join(output_dir, f"region_{region}_gene_function.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"区域{region}基因功能与空间模式分析:\n\n")
            f.write(f"主要差异基因: {', '.join(de_genes[:10])}...\n\n")
            f.write(f"空间表达特征: {json.dumps(spatial_features, ensure_ascii=False, indent=2)}\n\n")
            f.write(f"分析结果:\n{analysis}")
        print(f"区域{region}分析已保存至{output_file}")

    def generate_region_interaction(self, regions: List[str], output_file="interaction.txt"):
        region_info = []
        for r in regions:
            adjacent = self.adjacent_regions.get(r, [])
            region_info.append(
                f"区域{r}：\n"
                f"- 标记基因：{', '.join(self.region_markers[r]['genes'][:5])}\n"
                f"- 空间模式：{self.region_spatial_features[r]['dominant_pattern']}\n"  # 加入空间模式
                f"- 相邻区域：{', '.join(adjacent)}\n"
            )
        prompt = self.prompter.get_prompt(
            "region_interaction.txt",
            regions="、".join(regions),
            region_info="\n".join(region_info)
        )
        analysis = self.llm.call_model(
            system_prompt="你是组织生物学专家，分析空间转录组区域间的功能交互。",
            user_prompt=prompt,
            interaction_type="region_interaction_analysis"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(analysis)
        print(f"交互分析报告已保存至{output_file}")

    def find_cell_neighbors(self, cell_id: str, n_neighbors: int = 5) -> Tuple[List[str], np.ndarray]:
        """
        寻找指定细胞的空间邻居

        参数:
            cell_id: 细胞的唯一ID（需与adata.obs.index匹配）
            n_neighbors: 邻居数量

        返回:
            邻居细胞ID列表 + 包含目标细胞和邻居的子数据集索引
        """
        if cell_id not in self.adata.obs.index:
            raise ValueError(f"细胞ID {cell_id} 不存在于数据集中")

        # 获取目标细胞坐标
        cell_idx = self.adata.obs.index.get_loc(cell_id)
        cell_coord = self.cell_coords[cell_idx].reshape(1, -1)

        # 搜索邻居
        _, indices = self.knn_model.kneighbors(cell_coord, n_neighbors=n_neighbors + 1)  # +1包含自身
        indices = indices[0][1:]  # 排除自身

        # 邻居细胞ID
        neighbor_ids = self.adata.obs.index[indices].tolist()
        # 目标细胞+邻居的索引（用于后续表达分析）
        combined_indices = np.concatenate([[cell_idx], indices])

        return neighbor_ids, combined_indices

    def analyze_cell_microenvironment(self, cell_id: str, n_neighbors: int = 5, output_dir="microenvironment_analysis"):
        os.makedirs(output_dir, exist_ok=True)
        print(f"分析细胞{cell_id}的微环境（{n_neighbors}个邻居）...")

        # 1. 获取邻居和联合索引
        neighbor_ids, combined_indices = self.find_cell_neighbors(cell_id, n_neighbors)
        micro_env_adata = self.adata[combined_indices, :].copy()  # 微环境子数据集
        micro_env_adata.obs['group'] = ['cell'] + ['neighbors'] * n_neighbors

        if hasattr(micro_env_adata.X, 'toarray'):
            # 若为稀疏矩阵（如CSR格式），转换为稠密矩阵
            X_dense = micro_env_adata.X.toarray()
        else:
            # 若已为稠密矩阵，直接使用
            X_dense = micro_env_adata.X.copy()

        # 2. 计算基因表达特征
        # 2.1 目标细胞特异性高表达基因
        cell_expr = X_dense[0, :]  # 目标细胞表达量（第0行为目标细胞）
        neighbor_expr = X_dense[1:, :]  # 邻居细胞表达量（第1行及以后为邻居）
        neighbor_mean = np.mean(neighbor_expr, axis=0)  # 邻居平均表达量

        # 确保掩码是一维布尔数组且长度与基因数量一致
        cell_specific_mask = (cell_expr / (neighbor_mean + 1e-10)) > 1.5
        cell_specific_mask = cell_specific_mask.flatten()  # 确保是一维数组
        cell_specific_genes = micro_env_adata.var_names[cell_specific_mask].tolist()

        # 2.2 邻居共同高表达基因
        # 确保所有运算在稠密矩阵上进行
        neighbor_common_mask = (neighbor_mean / (cell_expr + 1e-10)) > 1.2  # 邻居均值 > 细胞1.2倍
        neighbor_common_mask &= (np.std(neighbor_expr, axis=0) < 0.3)  # 邻居内表达稳定
        # 确保掩码是一维布尔数组（与基因数量匹配）
        neighbor_common_mask = neighbor_common_mask.flatten()
        # 提取符合条件的基因
        neighbor_common_genes = micro_env_adata.var_names[neighbor_common_mask].tolist()

        # 3. 调用大模型分析微环境作用
        analysis = self.llm.analyze_cell_microenvironment(
            cell_id=cell_id,
            n_neighbors=n_neighbors,
            cell_specific_genes=cell_specific_genes,
            neighbor_common_genes=neighbor_common_genes,
        )

        # 4. 保存结果
        output_file = os.path.join(output_dir, f"cell_{cell_id}_microenvironment.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"细胞{cell_id}的微环境分析（{n_neighbors}个邻居）:\n\n")
            f.write(f"目标细胞特异性高表达基因: {', '.join(cell_specific_genes[:10])}...\n")
            f.write(f"邻居共同高表达基因: {', '.join(neighbor_common_genes[:10])}...\n")
            f.write(f"分析结果:\n{analysis}")
        print(f"微环境分析已保存至{output_file}")

    # ------------------------------ 空间分布分析工具函数 ------------------------------
    def calculate_gene_spatial_features(self, gene_name, region):
        """计算单个基因的空间表达特征"""
        if gene_name not in self.adata.var_names:
            return None

        # 提取坐标和表达量（修正版：确保坐标和表达量匹配）
        region_mask = self.adata.obs['cluster'] == region
        region_data = self.adata[region_mask, gene_name]
        coords = region_data.obs[[self.x_key, self.y_key]].values
        expr = region_data.X
        if hasattr(expr, 'toarray'):
            expr = expr.toarray().flatten()

        # 1. 表达量统计
        expr_stats = {
            "mean": float(np.mean(expr)),
            "std": float(np.std(expr)),
            "nonzero_fraction": float(np.mean(expr > 0)),
            "max_min_ratio": float(np.max(expr) / (np.min(expr) + 1e-10))  # 避免除零
        }

        # 2. 空间梯度分析
        if len(coords) < 2:  # 避免样本量不足
            gradient_stats = {"mean_gradient": 0.0, "gradient_std": 0.0}
        else:
            norm_coords = StandardScaler().fit_transform(coords)
            norm_expr = (expr - np.mean(expr)) / (np.std(expr) + 1e-10)
            nbrs = NearestNeighbors(n_neighbors=5).fit(norm_coords)
            gradients = []
            for i in range(len(norm_coords)):
                _, indices = nbrs.kneighbors([norm_coords[i]])
                neighbor_expr = norm_expr[indices[0]]
                expr_diff = neighbor_expr - norm_expr[i]
                displacement = norm_coords[indices[0]] - norm_coords[i]
                if displacement.shape[0] == len(expr_diff):
                    slope, _, _, _, _ = stats.linregress(displacement[:, 0], expr_diff)
                    gradients.append(slope)
            gradient_stats = {
                "mean_gradient": float(np.mean(gradients)) if gradients else 0,
                "gradient_std": float(np.std(gradients)) if gradients else 0
            }

        # 3. 空间分布模式分类
        if len(coords) < 5:  # 样本量不足时无法聚类
            pattern = "unknown"
        else:
            features = np.column_stack([coords, expr])
            features = StandardScaler().fit_transform(features)
            from sklearn.cluster import DBSCAN
            try:
                db = DBSCAN(eps=0.5, min_samples=5).fit(features)
                labels = db.labels_
                n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
                if n_clusters <= 1:
                    pattern = "gradient" if gradient_stats["mean_gradient"] > 0.1 else "uniform"
                else:
                    pattern = "patchy" if n_clusters > 3 else "localized"
            except:
                pattern = "unknown"

        # 4. 空间自相关（Moran's I）
        if len(coords) < 2:
            morans_i = 0.0
        else:
            dist_matrix = squareform(pdist(coords))
            np.fill_diagonal(dist_matrix, np.inf)
            weights = 1 / (1 + dist_matrix)
            weights[dist_matrix == np.inf] = 0
            mean_expr = np.mean(expr)
            dev = expr - mean_expr
            numerator = np.sum(weights * np.outer(dev, dev))
            denominator = np.sum(dev ** 2) + 1e-10
            morans_i = (len(expr) / np.sum(weights)) * (numerator / denominator) if denominator != 0 else 0

        return {
            "gene": gene_name,
            "expression_stats": expr_stats,
            "gradient": gradient_stats,
            "distribution_pattern": pattern,
            "spatial_autocorrelation": float(morans_i),
            "summary": f"{pattern}分布（梯度强度: {gradient_stats['mean_gradient']:.2f}，自相关: {morans_i:.2f}）"
        }

    def summarize_region_spatial_features(self, region_markers, top_n=10):
        """汇总区域内关键基因的空间特征"""
        region_spatial_summary = {}
        for region, markers in region_markers.items():
            top_genes = markers['genes'][:top_n]  # 取top N标记基因
            gene_features = []
            for gene in top_genes:
                feat = self.calculate_gene_spatial_features(gene, region)
                if feat:
                    gene_features.append(feat)

            # 区域空间特征汇总
            patterns = [f["distribution_pattern"] for f in gene_features]
            dominant_pattern = max(set(patterns), key=patterns.count) if patterns else "unknown"
            region_spatial_summary[region] = {
                "dominant_pattern": dominant_pattern,
                "gene_features": {f["gene"]: f["summary"] for f in gene_features},
                "gradient_strength": np.mean(
                    [f["gradient"]["mean_gradient"] for f in gene_features]) if gene_features else 0
            }
        return region_spatial_summary


# ------------------------------ 完整流程示例 ------------------------------
def main():
    # 1. 读取数据
    data_path = r"C:\Users\Administrator\Desktop\文件\研究生\项目记录\多尺度大模型生物标注\tempName\data\DLPFC_151507"
    adata = sc.read_visium(data_path)
    print(f"原始数据加载完成: {adata.shape}")

    # 处理重复基因
    if not adata.var.index.is_unique:
        duplicate_genes = adata.var.index[adata.var.index.duplicated()].tolist()
        print(f"检测到{len(duplicate_genes)}个重复基因，已移除")
        adata = adata[:, ~adata.var.index.duplicated(keep='first')]

    # 2. 初步筛选高可变基因
    sc.pp.filter_cells(adata, min_genes=100)
    sc.pp.filter_genes(adata, min_cells=3)
    sc.pp.highly_variable_genes(adata, n_top_genes=300, flavor="seurat_v3")
    initial_hv_genes = adata.var[adata.var['highly_variable']].index.tolist()
    print(f"初步筛选高可变基因: {len(initial_hv_genes)}个")

    # 3. 大模型背景分析
    prompter = Prompter()
    llm = LLMIntegrator(prompter)
    analyed_hv_genes, background_analysis = llm.analyze_hv_background(initial_hv_genes, n_hvg_genes=300)
    print("\n高可变基因背景分析结果:")
    print(background_analysis)

    # 4. 分段筛选基因
    filtered_hv_genes, filter_reasons = llm.refilter_hv_genes(
        initial_hv_genes=analyed_hv_genes,
        background_analysis=background_analysis,
        # chunk_size=100
    )
    print(f"\n剩余可用高可变基因: {len(filtered_hv_genes)}个")

    # 5. Stagate聚类
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"\n使用设备: {device}")
    stagate = StagatePipeline(adata, device=device)
    stagate.preprocess(hv_genes=filtered_hv_genes)
    stagate.train_model(epochs=1000)
    stagate.cluster(method="louvain", resolution=0.2)
    clustered_adata = stagate.get_adata()

    # 6. 后续分析（含空间表达模式和细胞微环境）
    analyzer = SpatialAnalyzer(clustered_adata, x_key='array_row', y_key='array_col')
    analyzer.identify_marker_genes()
    analyzer.find_adjacent_regions()
    analyzer.analyze_region_gene_functions('1')
    analyzer.generate_region_interaction(['2', '5'])
    # 选择一个细胞ID进行微环境分析（示例：取第一个细胞的ID）
    example_cell_id = clustered_adata.obs.index[0]
    analyzer.analyze_cell_microenvironment(
        cell_id=example_cell_id,
        n_neighbors=15,  # 分析15个邻居构成的微环境
        output_dir="cell_microenvironment_results"
    )

    # 保存结果
    clustered_adata.write("clustered_result.h5ad")
    print("\n所有流程完成，结果已保存")


if __name__ == "__main__":
    main()
