# 记忆管理系统设计文档

## 一、概述

记忆管理系统（Memory Management System）是一个为项目提供长期记忆能力的核心组件。系统支持记忆的存储、检索、摘要和更新，通过 BM25 + Reranker 的混合检索策略，结合重要性评分机制，实现高效且精准的记忆检索。

### 核心特性

- ✅ **多语言 BM25 检索**：支持中文、英文、日文等多种语言的智能检索
- ✅ **重要性加权**：检索结果结合记忆的重要性评分
- ✅ **Reranker 精排**：使用现有的 RerankerClient 进行二次排序
- ✅ **LLM 摘要生成**：自动从对话历史中提取关键记忆
- ✅ **项目级隔离**：每个项目拥有独立的记忆集合

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryService                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  记忆检索     │  │  记忆摘要     │  │  记忆管理     │     │
│  │ (Retrieval)  │  │ (Summarize)  │  │  (CRUD)      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  MultiLanguageBM25Retriever           │
        │  ┌──────────┐  ┌──────────┐          │
        │  │语言检测   │  │分词器     │          │
        │  │(Detector) │  │(Tokenizer)│          │
        │  └──────────┘  └──────────┘          │
        └───────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │  UserDataManagerMongoDB               │
        │  (记忆数据持久化)                      │
        └───────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │      MongoDB                           │
        │  memories 集合                         │
        └───────────────────────────────────────┘
```

### 2.2 模块划分

```
textmsa/services/memory/
├── __init__.py                    # 模块导出
├── memory_service.py              # 主服务类（MemoryService）
├── bm25_retriever.py              # BM25检索器（多语言支持）
│   ├── MultiLanguageBM25Retriever # BM25检索器主类
│   ├── LanguageDetector           # 语言检测器
│   └── TokenizerFactory           # 分词器工厂
├── memory_summarizer.py           # 记忆摘要器
│   └── MemorySummarizer           # LLM摘要生成器
└── utils.py                       # 工具函数
```

---

## 三、数据模型设计

### 3.1 MongoDB 集合结构

**集合名**：`memories`

**文档结构**：
```json
{
    "_id": ObjectId("..."),
    "project_id": "project_123",  // 主键，唯一索引
    "memory_list": [
        {
            "memory_id": "uuid-format-string",
            "content": "用户偏好使用Python进行数据分析",
            "importance": 0.85,
            "created_at": ISODate("2024-01-01T00:00:00Z"),
            "updated_at": ISODate("2024-01-01T00:00:00Z")
        }
    ],
    "created_at": ISODate("2024-01-01T00:00:00Z"),
    "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

### 3.2 Pydantic 模型

在 `textmsa/services/data/mongodb_models.py` 中添加：

```python
class Memory(BaseModel):
    """单个记忆模型"""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    
    memory_id: str = Field(..., description="记忆ID（UUID格式）")
    content: str = Field(..., min_length=1, max_length=2000, description="记忆内容")
    importance: float = Field(..., ge=0.0, le=1.0, description="重要性评分 [0.0, 1.0]")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator('content', mode='before')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("记忆内容不能为空")
        return v.strip()


class MemoryCollection(BaseModel):
    """项目记忆集合模型"""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    
    project_id: str = Field(..., description="项目ID（主键）")
    memory_list: List[Memory] = Field(default_factory=list, description="记忆列表")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=False)
```

### 3.3 数据库索引

在 `UserDataManagerMongoDB._create_indexes()` 中添加：

```python
# 记忆集合索引
self.memories_collection.create_index(
    "project_id",
    unique=True,
    name="memory_project_id_unique"
)
self.memories_collection.create_index(
    [("project_id", ASCENDING), ("updated_at", DESCENDING)],
    name="memory_project_updated"
)
```

---

## 四、多语言 BM25 检索设计

### 4.1 支持的语言

| 语言 | 代码 | 分词器 | 停用词库 |
|------|------|--------|----------|
| 中文 | `zh` | jieba | 中文停用词 |
| 英文 | `en` | nltk | NLTK停用词 |
| 日文 | `ja` | mecab-python3 | 日文停用词 |
| 韩文 | `ko` | konlpy | 韩文停用词 |
| 其他 | `auto` | 基于Unicode的通用分词 | 通用停用词 |

### 4.2 语言检测策略

**优先级顺序**：
1. **显式指定**：如果调用时指定了 `language` 参数，直接使用
2. **自动检测**：使用 `langdetect` 库检测文本语言
3. **默认回退**：如果检测失败，默认使用中文（`zh`）

**实现示例**：
```python
from langdetect import detect, LangDetectException

def detect_language(text: str, default: str = "zh") -> str:
    """检测文本语言"""
    try:
        lang_code = detect(text)
        # 映射到支持的语言代码
        lang_map = {
            "zh-cn": "zh", "zh-tw": "zh",
            "en": "en",
            "ja": "ja",
            "ko": "ko"
        }
        return lang_map.get(lang_code, default)
    except LangDetectException:
        return default
```

### 4.3 分词器设计

#### 4.3.1 分词器接口

```python
from abc import ABC, abstractmethod
from typing import List

class BaseTokenizer(ABC):
    """分词器基类"""
    
    @abstractmethod
    def tokenize(self, text: str) -> List[str]:
        """将文本分词为词列表"""
        pass
    
    @abstractmethod
    def get_stopwords(self) -> set:
        """获取停用词集合"""
        pass
```

#### 4.3.2 各语言分词器实现

**中文分词器**：
```python
import jieba
import jieba.analyse

class ChineseTokenizer(BaseTokenizer):
    def __init__(self):
        # 加载自定义词典（可选）
        # jieba.load_userdict("custom_dict.txt")
        self._stopwords = self._load_stopwords()
    
    def tokenize(self, text: str) -> List[str]:
        # 使用精确模式分词
        words = jieba.cut(text, cut_all=False)
        # 过滤停用词和单字符
        return [w for w in words if w not in self._stopwords and len(w.strip()) > 1]
    
    def get_stopwords(self) -> set:
        return self._stopwords
    
    def _load_stopwords(self) -> set:
        # 加载中文停用词
        # 可以从文件或使用预定义的停用词列表
        return set(["的", "了", "在", "是", "我", ...])
```

**英文分词器**：
```python
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

class EnglishTokenizer(BaseTokenizer):
    def __init__(self):
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')
        
        self._stopwords = set(stopwords.words('english'))
    
    def tokenize(self, text: str) -> List[str]:
        tokens = word_tokenize(text.lower())
        return [w for w in tokens if w.isalnum() and w not in self._stopwords]
    
    def get_stopwords(self) -> set:
        return self._stopwords
```

**通用分词器**（用于未支持的语言）：
```python
import re

class UniversalTokenizer(BaseTokenizer):
    """基于Unicode的通用分词器"""
    
    def __init__(self):
        self._stopwords = set()  # 通用停用词较少
    
    def tokenize(self, text: str) -> List[str]:
        # 使用正则表达式提取单词（字母、数字、CJK字符）
        tokens = re.findall(r'\b\w+\b|[\u4e00-\u9fff]+', text)
        return [t.lower() for t in tokens if len(t.strip()) > 1]
    
    def get_stopwords(self) -> set:
        return self._stopwords
```

#### 4.3.3 分词器工厂

```python
class TokenizerFactory:
    """分词器工厂，根据语言代码返回对应的分词器"""
    
    _tokenizers: Dict[str, BaseTokenizer] = {}
    
    @classmethod
    def get_tokenizer(cls, language: str) -> BaseTokenizer:
        """获取分词器（单例模式）"""
        if language not in cls._tokenizers:
            cls._tokenizers[language] = cls._create_tokenizer(language)
        return cls._tokenizers[language]
    
    @classmethod
    def _create_tokenizer(cls, language: str) -> BaseTokenizer:
        """创建分词器实例"""
        if language == "zh":
            return ChineseTokenizer()
        elif language == "en":
            return EnglishTokenizer()
        elif language == "ja":
            return JapaneseTokenizer()  # 需要实现
        elif language == "ko":
            return KoreanTokenizer()  # 需要实现
        else:
            return UniversalTokenizer()
```

### 4.4 BM25 检索实现

#### 4.4.1 BM25 算法参数

- **k1**: 词频饱和度参数，默认 `1.5`
- **b**: 长度归一化参数，默认 `0.75`
- **epsilon**: 平滑参数，默认 `0.25`

#### 4.4.2 检索流程

```
1. 语言检测
   ↓
2. 获取对应分词器
   ↓
3. 对查询和所有记忆进行分词
   ↓
4. 构建 BM25 索引
   ↓
5. 计算 BM25 分数
   ↓
6. 重要性加权：final_score = bm25_score × (1 + importance)
   ↓
7. 按分数排序，返回 top_k=50
   ↓
8. Reranker 精排（top_k=10）
   ↓
9. 返回最终结果
```

#### 4.4.3 核心实现

```python
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any

class MultiLanguageBM25Retriever:
    """多语言 BM25 检索器"""
    
    def __init__(self, language: Optional[str] = None):
        self.language = language
        self.tokenizer_factory = TokenizerFactory()
        self.language_detector = LanguageDetector()
    
    def retrieve(
        self,
        query: str,
        memories: List[Memory],
        top_k: int = 50,
        language: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        检索相关记忆
        
        Args:
            query: 查询文本
            memories: 记忆列表
            top_k: 返回前k个结果
            language: 语言代码（可选，如果不指定则自动检测）
        
        Returns:
            检索结果列表，每个元素包含：
            {
                "memory_id": str,
                "content": str,
                "importance": float,
                "bm25_score": float,
                "final_score": float
            }
        """
        if not memories:
            return []
        
        # 1. 语言检测
        detected_lang = language or self.language_detector.detect(query)
        tokenizer = self.tokenizer_factory.get_tokenizer(detected_lang)
        
        # 2. 分词
        query_tokens = tokenizer.tokenize(query)
        memory_tokens_list = [tokenizer.tokenize(m.content) for m in memories]
        
        # 3. 构建 BM25 索引
        bm25 = BM25Okapi(memory_tokens_list)
        
        # 4. 计算 BM25 分数
        bm25_scores = bm25.get_scores(query_tokens)
        
        # 5. 重要性加权
        results = []
        for i, memory in enumerate(memories):
            bm25_score = float(bm25_scores[i])
            # 重要性加权公式：final_score = bm25_score × (1 + importance)
            final_score = bm25_score * (1.0 + memory.importance)
            
            results.append({
                "memory_id": memory.memory_id,
                "content": memory.content,
                "importance": memory.importance,
                "bm25_score": bm25_score,
                "final_score": final_score,
                "memory": memory,  # 保留原始对象引用
            })
        
        # 6. 按最终分数排序
        results.sort(key=lambda x: x["final_score"], reverse=True)
        
        # 7. 返回 top_k
        return results[:top_k]
```

---

## 五、记忆摘要设计

### 5.1 摘要生成流程

```
Message 集合（对话历史）
    ↓
格式化对话历史
    ↓
构建 LLM Prompt
    ↓
调用 LLM 生成摘要
    ↓
解析 JSON 响应
    ↓
提取记忆列表（包含 importance）
    ↓
返回 Memory 对象列表
```

### 5.2 Prompt 设计

**系统提示词**：
```
你是一个专业的记忆提取助手。你的任务是从对话历史中提取关键信息，并将其转化为结构化的记忆。

提取原则：
1. 关注用户的偏好、习惯、重要决策
2. 关注项目相关的关键信息
3. 关注需要长期记住的事实
4. 忽略临时性的对话内容

重要性评分规则：
- 0.9-1.0：关键决策、核心偏好、重要结论
- 0.7-0.9：重要信息、用户偏好、项目配置
- 0.5-0.7：一般信息、上下文信息
- 0.0-0.5：次要信息、临时信息

请以 JSON 格式返回，结构如下：
{
  "memories": [
    {
      "content": "记忆内容（简洁明了，不超过100字）",
      "importance": 0.85
    }
  ]
}
```

**用户提示词模板**：
```
请从以下对话历史中提取关键记忆：

【对话历史】
{formatted_messages}

请提取3-10条关键记忆，并按重要性评分排序。
```

### 5.3 实现示例

```python
class MemorySummarizer:
    """记忆摘要生成器"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client()
    
    async def summarize(
        self,
        messages: List[Dict[str, str]],
        project_id: str,
        max_memories: int = 10,
    ) -> List[Memory]:
        """
        从对话历史中提取记忆
        
        Args:
            messages: 对话消息列表，格式：[{"role": "user", "content": "..."}, ...]
            project_id: 项目ID
            max_memories: 最大记忆数量
        
        Returns:
            Memory 对象列表
        """
        # 1. 格式化对话历史
        formatted_messages = self._format_messages(messages)
        
        # 2. 构建 Prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_prompt(formatted_messages, max_memories)
        
        # 3. 调用 LLM
        request = LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},  # 如果支持
        )
        
        response = self.llm_client.chat(request)
        
        # 4. 解析响应
        memories = self._parse_response(response.content, project_id)
        
        return memories
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """格式化对话历史为字符串"""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    def _parse_response(self, content: str, project_id: str) -> List[Memory]:
        """解析 LLM 响应为 Memory 对象列表"""
        import json
        import uuid
        
        try:
            data = json.loads(content)
            memories_data = data.get("memories", [])
            
            memories = []
            for mem_data in memories_data:
                memory = Memory(
                    memory_id=str(uuid.uuid4()),
                    content=mem_data.get("content", ""),
                    importance=float(mem_data.get("importance", 0.5)),
                )
                memories.append(memory)
            
            return memories
        except Exception as e:
            logger.error(f"解析记忆摘要失败: {e}")
            return []
```

---

## 六、记忆服务主类设计

### 6.1 MemoryService 接口

```python
class MemoryService:
    """记忆管理服务"""
    
    def __init__(
        self,
        user_data_manager: Optional[UserDataManagerMongoDB] = None,
        bm25_retriever: Optional[MultiLanguageBM25Retriever] = None,
        memory_summarizer: Optional[MemorySummarizer] = None,
        reranker_client: Optional[RerankerClient] = None,
    ):
        self.user_data_manager = user_data_manager or get_user_data_manager()
        self.bm25_retriever = bm25_retriever or MultiLanguageBM25Retriever()
        self.memory_summarizer = memory_summarizer or MemorySummarizer()
        self.reranker_client = reranker_client or get_reranker_client()
    
    async def retrieve_memories(
        self,
        query: str,
        project_id: str,
        top_k: int = 10,
        language: Optional[str] = None,
        use_reranker: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        检索相关记忆
        
        Args:
            query: 查询文本
            project_id: 项目ID
            top_k: 返回前k个结果
            language: 语言代码（可选）
            use_reranker: 是否使用 Reranker 精排
        
        Returns:
            检索结果列表
        """
        # 1. 获取项目记忆集合
        memory_collection = self.user_data_manager.get_memory_collection(project_id)
        if not memory_collection or not memory_collection.memory_list:
            return []
        
        # 2. BM25 检索（top_k=50）
        bm25_results = self.bm25_retriever.retrieve(
            query=query,
            memories=memory_collection.memory_list,
            top_k=50,
            language=language,
        )
        
        if not use_reranker or len(bm25_results) <= top_k:
            return bm25_results[:top_k]
        
        # 3. Reranker 精排（top_k=10）
        reranked_results = await self._rerank_memories(
            query=query,
            bm25_results=bm25_results,
            top_k=top_k,
        )
        
        return reranked_results
    
    async def summarize_memories(
        self,
        messages: List[Dict[str, str]],
        project_id: str,
        max_memories: int = 10,
    ) -> List[Memory]:
        """
        从对话历史中提取记忆
        
        Args:
            messages: 对话消息列表
            project_id: 项目ID
            max_memories: 最大记忆数量
        
        Returns:
            Memory 对象列表
        """
        return await self.memory_summarizer.summarize(
            messages=messages,
            project_id=project_id,
            max_memories=max_memories,
        )
    
    async def add_memories(
        self,
        project_id: str,
        memories: List[Memory],
    ) -> MemoryCollection:
        """
        添加记忆到项目
        
        Args:
            project_id: 项目ID
            memories: 记忆列表
        
        Returns:
            更新后的记忆集合
        """
        return self.user_data_manager.add_memories(project_id, memories)
    
    async def _rerank_memories(
        self,
        query: str,
        bm25_results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """使用 Reranker 对 BM25 结果进行精排"""
        # 提取文档文本
        documents = [r["content"] for r in bm25_results]
        
        # 调用 Reranker
        request = RerankRequest(
            query=query,
            documents=documents,
            top_n=top_k,
        )
        
        def _call():
            return self.reranker_client.rerank(request)
        
        response = await asyncio.to_thread(_call)
        
        # 映射回原始结果
        reranked = []
        for result in response.results:
            idx = result.index
            if 0 <= idx < len(bm25_results):
                original = bm25_results[idx].copy()
                original["reranker_score"] = result.score
                reranked.append(original)
        
        return reranked
```

### 6.2 单例模式

```python
_memory_service: Optional[MemoryService] = None

def get_memory_service() -> MemoryService:
    """获取记忆服务单例"""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
```

---

## 七、数据访问层设计

### 7.1 UserDataManagerMongoDB 扩展方法

在 `UserDataManagerMongoDB` 类中添加以下方法：

```python
def get_memory_collection(self, project_id: str) -> Optional[MemoryCollection]:
    """获取项目的记忆集合"""
    doc = self.memories_collection.find_one({"project_id": project_id})
    if not doc:
        return None
    return memory_collection_from_dict(doc)

def add_memories(self, project_id: str, memories: List[Memory]) -> MemoryCollection:
    """添加记忆到项目"""
    now = datetime.now(timezone.utc)
    
    # 检查是否存在
    existing = self.get_memory_collection(project_id)
    
    if existing:
        # 更新现有集合
        existing.memory_list.extend(memories)
        existing.updated_at = now
        
        self.memories_collection.update_one(
            {"project_id": project_id},
            {
                "$set": {
                    "memory_list": [m.to_dict() for m in existing.memory_list],
                    "updated_at": now,
                }
            }
        )
        return existing
    else:
        # 创建新集合
        new_collection = MemoryCollection(
            project_id=project_id,
            memory_list=memories,
            created_at=now,
            updated_at=now,
        )
        self.memories_collection.insert_one(new_collection.to_dict())
        return new_collection

def delete_memory(self, project_id: str, memory_id: str) -> bool:
    """删除单个记忆"""
    result = self.memories_collection.update_one(
        {"project_id": project_id},
        {"$pull": {"memory_list": {"memory_id": memory_id}}}
    )
    return result.modified_count > 0

def delete_memory_collection(self, project_id: str) -> bool:
    """删除项目的所有记忆"""
    result = self.memories_collection.delete_one({"project_id": project_id})
    return result.deleted_count > 0
```

### 7.2 辅助函数

在 `mongodb_models.py` 中添加：

```python
def memory_collection_from_dict(data: Dict[str, Any]) -> MemoryCollection:
    """从字典创建 MemoryCollection 模型"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 memory_list
    memory_list = []
    for mem_dict in data.get("memory_list", []):
        memory_list.append(Memory(**mem_dict))
    
    data["memory_list"] = memory_list
    
    # 处理 datetime 字段
    if "created_at" in data and isinstance(data["created_at"], str):
        data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    if "updated_at" in data and isinstance(data["updated_at"], str):
        data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
    
    return MemoryCollection(**data)
```

---

## 八、API 接口设计（可选）

如果需要提供 HTTP API，可以在 `textmsa/services/api/routers/` 下创建 `memory.py`：

```python
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional

router = APIRouter(prefix="/api/memory", tags=["memory"])

@router.post("/retrieve")
async def retrieve_memories(
    query: str,
    project_id: str,
    top_k: int = 10,
    language: Optional[str] = None,
):
    """检索相关记忆"""
    service = get_memory_service()
    results = await service.retrieve_memories(
        query=query,
        project_id=project_id,
        top_k=top_k,
        language=language,
    )
    return {"results": results}

@router.post("/summarize")
async def summarize_memories(
    messages: List[Dict[str, str]],
    project_id: str,
    max_memories: int = 10,
):
    """从对话历史中提取记忆"""
    service = get_memory_service()
    memories = await service.summarize_memories(
        messages=messages,
        project_id=project_id,
        max_memories=max_memories,
    )
    return {"memories": [m.model_dump() for m in memories]}

@router.post("/add")
async def add_memories(
    project_id: str,
    memories: List[Dict[str, Any]],
):
    """添加记忆到项目"""
    service = get_memory_service()
    memory_objects = [Memory(**m) for m in memories]
    collection = await service.add_memories(project_id, memory_objects)
    return {"collection": collection.model_dump()}

@router.get("/{project_id}")
async def get_memories(project_id: str):
    """获取项目的所有记忆"""
    service = get_memory_service()
    collection = service.user_data_manager.get_memory_collection(project_id)
    if not collection:
        raise HTTPException(status_code=404, detail="MEMORY_COLLECTION_NOT_FOUND")
    return {"collection": collection.model_dump()}

@router.delete("/{project_id}/{memory_id}")
async def delete_memory(project_id: str, memory_id: str):
    """删除单个记忆"""
    service = get_memory_service()
    success = service.user_data_manager.delete_memory(project_id, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="MEMORY_NOT_FOUND")
    return {"success": True}
```

---

## 九、依赖项

需要在 `server/requirements.txt` 中添加：

```txt
# 记忆管理系统依赖
rank-bm25>=0.2.2          # BM25检索算法
langdetect>=1.0.9         # 语言检测
jieba>=0.42.1            # 中文分词
nltk>=3.8.1              # 英文分词和停用词
# mecab-python3>=1.0.6   # 日文分词（可选）
# konlpy>=0.6.0          # 韩文分词（可选）
```

**注意**：某些分词器可能需要额外的系统依赖，需要在部署文档中说明。

---

## 十、使用示例

### 10.1 基本使用

```python
from textmsa.services.memory import get_memory_service

# 初始化服务
memory_service = get_memory_service()

# 1. 记忆检索
results = await memory_service.retrieve_memories(
    query="用户偏好设置",
    project_id="project_123",
    top_k=10,
    language="zh",  # 可选，不指定则自动检测
)

# 2. 记忆摘要
messages = [
    {"role": "user", "content": "我喜欢用Python进行数据分析"},
    {"role": "assistant", "content": "好的，我会记住您的偏好"},
    {"role": "user", "content": "请帮我分析这个CSV文件"},
]
memories = await memory_service.summarize_memories(
    messages=messages,
    project_id="project_123",
    max_memories=5,
)

# 3. 记忆添加
await memory_service.add_memories(
    project_id="project_123",
    memories=memories,
)
```

### 10.2 在 Agent 中集成

```python
# 在 agent_service.py 或相关节点中
async def node_with_memory(state: GraphState) -> StateUpdate:
    """使用记忆的节点示例"""
    user_query = state.get("user_message", "")
    project_id = state.get("project_id", "")
    
    # 检索相关记忆
    memory_service = get_memory_service()
    relevant_memories = await memory_service.retrieve_memories(
        query=user_query,
        project_id=project_id,
        top_k=5,
    )
    
    # 将记忆作为上下文注入
    memory_context = "\n".join([m["content"] for m in relevant_memories])
    
    # 在 LLM prompt 中使用记忆上下文
    prompt = f"""
    相关记忆：
    {memory_context}
    
    用户问题：
    {user_query}
    """
    
    # ... 后续处理
```

---

## 十一、性能优化

### 11.1 BM25 索引缓存

对于频繁查询的项目，可以缓存 BM25 索引：

```python
class MultiLanguageBM25Retriever:
    _index_cache: Dict[Tuple[str, str], BM25Okapi] = {}  # (project_id, language) -> index
    
    def _get_or_build_index(self, memories: List[Memory], language: str) -> BM25Okapi:
        """获取或构建 BM25 索引（带缓存）"""
        cache_key = (id(memories), language)  # 使用对象ID作为key
        if cache_key not in self._index_cache:
            # 构建索引...
            pass
        return self._index_cache[cache_key]
```

### 11.2 批量操作优化

支持批量添加记忆，减少数据库操作次数。

### 11.3 异步处理

记忆摘要生成可以异步执行，不阻塞主流程。

---

## 十二、错误处理

### 12.1 异常类型

```python
class MemoryServiceError(Exception):
    """记忆服务基础异常"""
    pass

class MemoryNotFoundError(MemoryServiceError):
    """记忆未找到"""
    pass

class InvalidMemoryError(MemoryServiceError):
    """无效的记忆数据"""
    pass

class LanguageNotSupportedError(MemoryServiceError):
    """不支持的语言"""
    pass
```

### 12.2 错误处理策略

- **语言检测失败**：回退到默认语言（中文）
- **分词失败**：使用通用分词器
- **BM25 计算失败**：返回空结果
- **LLM 摘要失败**：记录错误日志，返回空列表
- **数据库操作失败**：抛出异常，由上层处理

---

## 十三、测试建议

### 13.1 单元测试

- 语言检测准确性测试
- 各语言分词器测试
- BM25 检索准确性测试
- 重要性加权计算测试
- 记忆摘要生成测试

### 13.2 集成测试

- 端到端检索流程测试
- 多语言混合检索测试
- 记忆添加和检索一致性测试

### 13.3 性能测试

- 大规模记忆集合（1000+）检索性能
- 并发检索性能
- 内存占用测试

---

## 十四、待确认问题

1. **记忆更新和删除**：是否需要支持记忆内容的更新？是否需要支持批量删除？
2. **记忆去重**：是否需要基于内容相似度的去重机制？
3. **记忆过期**：是否需要自动清理旧记忆的机制（如超过N天未使用）？
4. **记忆数量限制**：每个项目的记忆数量是否有上限？
5. **多语言支持范围**：除了中文、英文，是否需要优先支持其他语言（如日文、韩文）？
6. **停用词库**：是否需要支持自定义停用词库？
7. **BM25 参数调优**：是否需要支持自定义 k1、b 参数？
8. **API 接口**：是否需要提供 HTTP API 接口？

---

## 十五、实施计划

### Phase 1: 基础功能（1-2周）
- [ ] 数据模型定义和数据库操作
- [ ] 基础 BM25 检索（单语言）
- [ ] 记忆添加功能

### Phase 2: 多语言支持（1周）
- [ ] 语言检测实现
- [ ] 多语言分词器实现
- [ ] 多语言 BM25 集成测试

### Phase 3: 高级功能（1周）
- [ ] 记忆摘要生成
- [ ] Reranker 集成
- [ ] 重要性加权优化

### Phase 4: 优化和测试（1周）
- [ ] 性能优化
- [ ] 单元测试和集成测试
- [ ] 文档完善

---

## 十六、参考资源

- [BM25 算法原理](https://en.wikipedia.org/wiki/Okapi_BM25)
- [rank-bm25 库文档](https://github.com/dorianbrown/rank_bm25)
- [langdetect 库文档](https://github.com/Mimino666/langdetect)
- [jieba 中文分词](https://github.com/fxsjy/jieba)
- [NLTK 文档](https://www.nltk.org/)

---

**文档版本**: v1.0  
**最后更新**: 2024-01-XX  
**作者**: AI Assistant

