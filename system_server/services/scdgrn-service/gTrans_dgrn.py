import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optm
from torch.nn import CosineSimilarity
import math
from typing import Optional, Union
try:
    import anndata as ad
    ANNDATA_AVAILABLE = True
except ImportError:
    ANNDATA_AVAILABLE = False

class GTransformer(nn.Module):
    def __init__(self, adata=None, time_column='time', 
                 hidden_dim=[128, 64, 32], output_dim=16, num_head=[3, 3],
                 alpha=0.2, attention_type='dot', reduction='concate',
                 embed_dim=16, num_heads=2, units=64,
                 gru_input_size=32, gru_hidden_size=128, gru_num_layers=2,
                 final_out_dim=16, causal_out_dim=3,
                 dropout_rate=0.01, init_weight_value=0.01,
                 min_intermediate_dim=32, weight_scale=100.0,
                 device=None, config=None):
        """
        Initialize GTransformer model.
        
        Args:
            adata: AnnData object containing expression data and time information (required).
            time_column: Column name in adata.obs containing time point information. Default: 'time'.
            hidden_dim: List of hidden dimensions [hidden1_dim, hidden2_dim, hidden3_dim]. Default: [128, 64, 32].
            num_head: List of number of attention heads [num_head1, num_head2]. Default: [3, 3].
            Other parameters:
                output_dim: Output dimension for embeddings. Default: 16.
                alpha: LeakyReLU negative slope. Default: 0.2.
                attention_type: Attention type ('dot', 'cosine', 'MLP'). Default: 'dot'.
                reduction: Reduction method ('mean' or 'concate'). Default: 'concate'.
                embed_dim: Embedding dimension for transformer layers. Default: 16.
                num_heads: Number of heads for self-attention. Default: 2.
                units: Hidden units for fully connected layers. Default: 64.
                gru_input_size: Input size for GRU layer. Default: 32.
                gru_hidden_size: Hidden size for GRU layer. Default: 128.
                gru_num_layers: Number of layers for GRU. Default: 2.
                final_out_dim: Output dimension for final output layer. Default: 16.
                causal_out_dim: Output dimension for causal output layer. Default: 3.
                dropout_rate: Dropout rate. Default: 0.01.
                init_weight_value: Initial weight value for learnable parameters. Default: 0.01.
                weight_scale: Scaling factor for learnable weights in decode. Default: 100.0.
                device: Device to run on. If None, will use CUDA if available else CPU.
                config: Configuration dictionary with model parameters. Will override individual parameters if provided.
        """
        super(GTransformer, self).__init__()
        
        # Merge config if provided
        if config is not None:
            for key, value in config.items():
                if key in locals():
                    locals()[key] = value
        
        # Validate adata is provided
        if adata is None:
            raise ValueError("adata must be provided")
        
        if not ANNDATA_AVAILABLE:
            raise ImportError("anndata package is required. Please install it: pip install anndata")
        
        # Extract parameters from adata
        if time_column not in adata.obs.columns:
            raise ValueError(f"Time column '{time_column}' not found in adata.obs. Available columns: {list(adata.obs.columns)}")
        
        # Get unique time points
        unique_times = sorted([v for v in adata.obs[time_column].unique() if pd.notna(v)])
        num_time_points = len(unique_times)
        
        # Calculate input_dim from adata (max number of cells across all time points)
        max_cells = 0
        for time_val in unique_times:
            time_mask = adata.obs[time_column] == time_val
            time_adata = adata[time_mask]
            max_cells = max(max_cells, time_adata.n_obs)
        
        input_dim = max_cells
        
        # Store time point information
        self.time_point = num_time_points
        self.recons_tp = num_time_points
        self.timesteps = num_time_points
        
        # Store adata and time_column for later use
        self.adata = adata
        self.time_column = time_column
        
        # Extract parameters from hidden_dim and num_head lists
        hidden1_dim, hidden2_dim, hidden3_dim = hidden_dim
        num_head1, num_head2 = num_head
        
        # Set device
        if device is None:
            device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        
        # Store parameters
        self.num_head1 = num_head1
        self.num_head2 = num_head2
        self.device = device
        self.alpha = alpha
        self.type = attention_type
        self.reduction = reduction
        self.flag = False
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.units = units
        self.output_dim = output_dim
        self.dropout_rate = dropout_rate
        self.min_intermediate_dim = min_intermediate_dim
        self.weight_scale = weight_scale
        self.Wadp = None
        
        # Cache for positional encoding to avoid recreating it every forward pass
        self._pos_encoding_cache = {} 


        # Projection layer to map from output_dim to embed_dim for self-attention
        self.output_to_embed = nn.Linear(self.output_dim, self.embed_dim)
        
        # Self-attention layers
        self.self_attention_layer1 = SelfAttention(self.embed_dim, self.num_heads).to(device)
        self.self_attention_layer2 = SelfAttention(self.embed_dim, self.num_heads).to(device)
        self.self_attention_layer3 = SelfAttention(self.embed_dim, self.num_heads).to(device)
        self.layer_norm = nn.LayerNorm(self.embed_dim)

        # Learnable weight parameters
        self.w = nn.Parameter(init_weight_value * torch.ones(2))


        # Calculate hidden dimensions based on reduction method
        if self.reduction == 'mean':
            self.hidden1_dim = hidden1_dim
            self.hidden2_dim = hidden2_dim
        elif self.reduction == 'concate':
            self.hidden1_dim = num_head1 * hidden1_dim
            self.hidden2_dim = num_head2 * hidden2_dim
        else:
            raise ValueError(f"Unsupported reduction method: {self.reduction}")

        # Graph attention layers
        self.ConvLayer1 = [AttentionLayer(input_dim, hidden1_dim, alpha) for _ in range(num_head1)]
        for i, attention in enumerate(self.ConvLayer1):
            self.add_module(f'ConvLayer1_AttentionHead{i}', attention)
        
        self.ConvLayer2 = [AttentionLayer(self.hidden1_dim, hidden2_dim, alpha) for _ in range(num_head2)]
        for i, attention in enumerate(self.ConvLayer2):
            self.add_module(f'ConvLayer2_AttentionHead{i}', attention)

        # MLP layers for TF and target embeddings
        self.tf_linear1 = nn.Linear(hidden2_dim, hidden3_dim)
        self.target_linear1 = nn.Linear(hidden2_dim, hidden3_dim)
        self.tf_linear2 = nn.Linear(hidden3_dim, output_dim)
        self.target_linear2 = nn.Linear(hidden3_dim, output_dim)

        # Store input_dim (number of cells, should be unified by external sampling)
        self.input_dim = input_dim

        # MLP layer for attention type
        if self.type == 'MLP':
            self.linear = nn.Linear(2 * output_dim, 2)

        # GRU layer for temporal modeling
        self.gru = nn.GRU(
            input_size=gru_input_size, 
            hidden_size=gru_hidden_size, 
            num_layers=gru_num_layers, 
            batch_first=True
        )

        # Attention layer
        self.attention = Attention(self.units)

        # Fully connected layers
        self.fc1 = nn.Linear(self.embed_dim, self.units)
        self.fc2 = nn.Linear(self.units, self.units)
        self.final_out = nn.Linear(self.units, final_out_dim)
        self.final_out_causal = nn.Linear(2 * self.units, causal_out_dim)
        self.final_out_causal_two_label = nn.Linear(2 * self.units, 1)


        self.reset_parameters()

    def reset_parameters(self):
        for attention in self.ConvLayer1:
            attention.reset_parameters() ## 

        for attention in self.ConvLayer2:
            attention.reset_parameters()

        nn.init.xavier_uniform_(self.tf_linear1.weight,gain=1.414)
        nn.init.xavier_uniform_(self.target_linear1.weight, gain=1.414)
        nn.init.xavier_uniform_(self.tf_linear2.weight, gain=1.414)
        nn.init.xavier_uniform_(self.target_linear2.weight, gain=1.414)




    def encode(self,x,adj):
        ## 
        if self.reduction =='concate':
            x = torch.cat([att(x, adj) for att in self.ConvLayer1], dim=1) # 
            x = F.elu(x)

        elif self.reduction =='mean':
            x = torch.mean(torch.stack([att(x, adj) for att in self.ConvLayer1]), dim=0) # 
            x = F.elu(x)

        else:
            raise TypeError


        with torch.no_grad():
            out = torch.mean(torch.stack([att(x, adj) for att in self.ConvLayer2]),dim=0) #
        return out


    def decode(self, tf_embed, target_embed):
        """
        Decode TF and target embeddings to predict interactions.
        
        Args:
            tf_embed: List of TF embeddings for each time point
            target_embed: List of target embeddings for each time point
            
        Returns:
            Prediction results and embeddings
        """
        t_p = self.recons_tp
        h_t_tf = []
        h_t_target = []
        
        for i in range(t_p):
            h_t_tf.append(tf_embed[i])
            h_t_target.append(target_embed[i])
        
        h_x_tf = torch.cat(h_t_tf, dim=1).view(-1, t_p, self.output_dim)
        h_x_target = torch.cat(h_t_target, dim=1).view(-1, t_p, self.output_dim)
        
        # Clear lists to free memory
        del h_t_tf, h_t_target

        ## 
        r_h_x_tf = h_x_tf.view(h_x_tf.size(0),-1)
        r_h_x_target = h_x_target.view(h_x_target.size(0), -1)
        self.oput_gat = torch.cat((r_h_x_tf, r_h_x_target), dim=1)


        #prob = self.linear(h)
        ## 
        # x shape (batch, time_step, input_size)
        # r_out shape (batch, time_step, output_size)
        # h_n shape (n_layers, batch, hidden_size)   
        # h_c shape (n_layers, batch, hidden_size)
        #r_out, (h_n, h_c) = self.gru(h_x, None)  # 


        device = self.device

        inputs_tf = h_x_tf
        inputs_target = h_x_target
        
        # Use cached positional encoding if available, otherwise create and cache it
        # Positional encoding should match output_dim (not embed_dim) since inputs are (batch, t_p, output_dim)
        cache_key = (t_p, self.output_dim)
        if cache_key not in self._pos_encoding_cache:
            pos_encoding = torch.zeros((t_p, self.output_dim), device=device)
            pos = torch.arange(0, t_p, dtype=torch.float, device=device).unsqueeze(1)
            div_term = torch.exp(torch.arange(0, self.output_dim, 2, device=device).float() * (-math.log(10000.0) / self.output_dim))
            pos_encoding[:, 0::2] = torch.sin(pos * div_term)
            if self.output_dim > 1:
                pos_encoding[:, 1::2] = torch.cos(pos * div_term)
            pos_encoding = pos_encoding.unsqueeze(0)
            self._pos_encoding_cache[cache_key] = pos_encoding
        else:
            pos_encoding = self._pos_encoding_cache[cache_key]


        x_pos_tf = inputs_tf + pos_encoding  ## 
        x_pos_target = inputs_target + pos_encoding
        
        # Project from output_dim to embed_dim for self-attention
        x_pos_tf_proj = self.output_to_embed(x_pos_tf)
        x_pos_target_proj = self.output_to_embed(x_pos_target)
        
        # Apply self-attention
        x_tf = self.self_attention_layer1(x_pos_tf_proj)
        x_target = self.self_attention_layer1(x_pos_target_proj)
        
        # Compute learnable weights for combining input and attention output
        w_rs = self.weight_scale * self.w
        w1 = torch.exp(w_rs[0]) / torch.sum(torch.exp(w_rs))
        w2 = torch.exp(w_rs[1]) / torch.sum(torch.exp(w_rs))

        # Use projected inputs for combination
        output_tf = w1 * x_pos_tf_proj + w2 * x_tf
        output_target = w1 * x_pos_target_proj + w2 * x_target
        
        # Clear intermediate tensors
        del x_pos_tf, x_pos_target
        
        x_tf = self.layer_norm(output_tf)
        x_target = self.layer_norm(output_target)
        
        # Clear output tensors
        del output_tf, output_target

        # Apply fully connected layers
        x_tf = F.relu(self.fc1(x_tf))
        x_target = F.relu(self.fc1(x_target))

        reshape_x_tf = x_tf.view(x_tf.size(0), -1)
        reshape_x_target = x_target.view(x_target.size(0), -1)

        # Store transformer output for later use
        self.out_transformer = torch.cat((reshape_x_tf, reshape_x_target), dim=1)
        
        # Apply attention mechanism
        attention_output_tf, Wadp_tf = self.attention(x_tf)
        attention_output_target, Wadp_target = self.attention(x_target)

        # Return predictions based on flag
        if self.flag:
            liner_concat = torch.cat((attention_output_tf, attention_output_target), dim=1)
            prob = self.final_out_causal(liner_concat)
            return prob
        else:
            linear_output_tf = self.final_out(attention_output_tf)
            linear_output_target = self.final_out(attention_output_target)

            self.tf_ouput = linear_output_tf
            self.target_output = linear_output_target

            prob = torch.mul(linear_output_tf, linear_output_target)
            prob = torch.sum(prob, dim=1).view(-1, 1)

            return prob, linear_output_tf, linear_output_target



        # torch.Size([64, 28, 128])->torch.Size([64,128])
        #out = self.out(r_out[:,-1, :])  # torch.Size([64, 128])-> torch.Size([64, 10])    ##
        #out = F.relu(out)
        #out = F.dropout(out,p=0.5)
        #out = self.final_out(out)
        #out = F.leaky_relu(out)

        ##
        # l_out = []
        # for i in range(t_p):
        #     out = self.out(r_out[:, i, :])
        #     out = F.relu(out)
        #     l_out.append(out)
        # ll_out = torch.cat(l_out, dim=1)
        # #ll_out = self.out(ll_out)
        # #F.dropout(ll_out,p=0.01)
        # lll_out = self.final_out(ll_out)

        ## 
        # l_out = []
        # for i in range(t_p):
        #     out = self.out(r_out[:, i, :])
        #     #out = F.relu(out)
        #     #out = out.cpu().detach().numpy()
        #     l_out.append(out)
        #
        # feature_vectors = l_out
        # # 
        # features_matrix = torch.stack(feature_vectors,dim=1)
        # pooled_features = torch.mean(features_matrix,dim=1)
        #
        # lll_out = self.final_out(pooled_features)
        #return prob

    def forward(self, x, adj, train_sample, recons_tp):
        """
        Forward pass through the model.
        
        Args:
            x: List of input tensors for each time point, each of shape (num_genes, num_cells)
            adj: Adjacency matrix for graph attention
            train_sample: Training sample indices, shape (batch_size, 2)
            recons_tp: Number of time points to reconstruct
            
        Returns:
            Prediction results
        """
        self.recons_tp = recons_tp
        train_tf_total = []
        train_target_total = []
        
        # Use all available time points from data
        actual_time_points = min(len(x), recons_tp)
        
        for i in range(actual_time_points):
            # x[i] shape: (num_genes, num_cells)
            # Note: External sampling should ensure all time points have the same number of cells (input_dim)
            # Directly use x[i] without any adaptation layer
            e = x[i]  # (num_genes, num_cells) where num_cells == input_dim
            embed = self.encode(e, adj)
            
            # Compute TF and target embeddings
            tf_embed = self.tf_linear1(embed)
            tf_embed = F.leaky_relu(tf_embed)
            tf_embed = F.dropout(tf_embed, p=self.dropout_rate)
            tf_embed = self.tf_linear2(tf_embed)
            tf_embed = F.leaky_relu(tf_embed)

            target_embed = self.target_linear1(embed)
            target_embed = F.leaky_relu(target_embed)
            target_embed = F.dropout(target_embed, p=self.dropout_rate)
            target_embed = self.target_linear2(target_embed)
            target_embed = F.leaky_relu(target_embed)
            
            # Clear embed tensor after use
            del embed

            # Extract training samples
            train_tf = tf_embed[train_sample[:, 0]]
            train_target = target_embed[train_sample[:, 1]]
            train_tf_total.append(train_tf)
            train_target_total.append(train_target)
            
        # Update recons_tp to match the actual number of processed time points
        self.recons_tp = actual_time_points
        pred = self.decode(train_tf_total, train_target_total)

        return pred

    def get_embedding(self):
        return self.tf_ouput, self.target_output



class SelfAttention(nn.Module):
    def __init__(self, d_model, n_heads):
        super(SelfAttention, self).__init__()
        self.d_model = d_model
        self.n_heads = n_heads

        # 
        self.query_weight = nn.Linear(d_model, d_model * n_heads, bias=False)
        self.key_weight = nn.Linear(d_model, d_model * n_heads, bias=False)
        self.value_weight = nn.Linear(d_model, d_model * n_heads, bias=False)

        # 
        self.output_weight = nn.Linear(d_model * n_heads, d_model)

    def forward(self, x, mask=None):
        # x: [batch_size, seq_len, d_model]

        batch_size, seq_len, d_model = x.size()

        # 
        query = self.query_weight(x).view(batch_size, seq_len, self.n_heads, -1).transpose(1, 2)  # [batch_size, n_heads, seq_len, d_k]
        key = self.key_weight(x).view(batch_size, seq_len, self.n_heads, -1).transpose(1, 2)  # [batch_size, n_heads, seq_len, d_k]
        value = self.value_weight(x).view(batch_size, seq_len, self.n_heads, -1).transpose(1, 2)  # [batch_size, n_heads, seq_len, d_v]

        # 
        attn_scores = torch.matmul(query, key.transpose(-2, -1)) / torch.sqrt(torch.tensor(self.d_model, dtype=torch.float32))  # [batch_size, n_heads, seq_len, seq_len]

        # 
        if mask is not None:
            attn_scores = attn_scores.masked_fill(mask == 0, -1e9)

        #
        attn_weights = F.softmax(attn_scores, dim=-1)

        # 
        attn_output = torch.matmul(attn_weights, value)  # [batch_size, n_heads, seq_len, d_v]

        # 
        attn_output = attn_output.transpose(1, 2).contiguous().view(batch_size, seq_len, -1)  # [batch_size, seq_len, n_heads * d_v]

        # 
        output = self.output_weight(attn_output)  # [batch_size, seq_len, d_model]

        return output


# class ResidualBlock(nn.Module):
#     def __init__(self, d_model, n_heads, dropout_rate=0.1):
#         super(ResidualBlock, self).__init__()
#         self.d_model = d_model
#
#         # 
#         self.self_attention_layer1 = SelfAttention(d_model, n_heads)
#
#         # 
#         self.self_attention_layer2 = SelfAttention(d_model, n_heads)
#         self.layer_norm = nn.LayerNorm(d_model)
#
#         # 
#     def forward(self,x):
#         x1 = self.self_attention_layer1(x)
#         x2 = self.self_attention_layer2(x1)
#         output = x2
#         output = x + output
#         output = self.layer_norm(output)
#         return output

# 
class MultiHeadAttentionLayer(nn.Module):
    def __init__(self, embed_dim, num_heads):
        super(MultiHeadAttentionLayer, self).__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads

        self.query_fc = nn.Linear(embed_dim, embed_dim)
        self.key_fc = nn.Linear(embed_dim, embed_dim)
        self.value_fc = nn.Linear(embed_dim, embed_dim)

        self.softmax = nn.Softmax(dim=-1)
        self.dropout = nn.Dropout(0.1)
        self.layer_norm = nn.LayerNorm(embed_dim)

        self.fc = nn.Linear(embed_dim, embed_dim)

    def forward(self, inputs):  ## (512,time_steps,32)
        batch_size = inputs.size(0)
        query = self.query_fc(inputs).view(batch_size, -1, self.num_heads, self.embed_dim // self.num_heads).transpose(1, 2) ## 
        key = self.key_fc(inputs).view(batch_size, -1, self.num_heads, self.embed_dim // self.num_heads).transpose(1, 2)
        value = self.value_fc(inputs).view(batch_size, -1, self.num_heads, self.embed_dim // self.num_heads).transpose(1, 2)

        scores = torch.matmul(query, key.transpose(-2, -1)) / np.sqrt(self.embed_dim // self.num_heads)
        attention_weights = self.softmax(scores)
        attention_weights = self.dropout(attention_weights)

        context_vector = torch.matmul(attention_weights, value)
        context_vector = context_vector.transpose(1, 2).contiguous().view(batch_size, -1, self.embed_dim)
        # output = self.fc(context_vector)
        # output = self.dropout(output)
        output = context_vector
        output = 4*inputs + output
        #output = self.layer_norm(inputs + output)
        output = self.layer_norm(output)
        return output


class Attention(nn.Module):
    def __init__(self, input_dim):
        super(Attention, self).__init__()
        self.input_dim = input_dim # 
        self.linear = nn.Linear(input_dim, input_dim)
        self.softmax = nn.Softmax(dim=1)

    def forward(self, inputs):
        # inputs: batch_size x seq_length x input_dim
        # 
        linear_output = self.linear(inputs)
        # 
        attention_weights = self.softmax(linear_output)
        #self.Wadp = attention_weights
        # 
        attention_output = torch.sum(attention_weights * inputs, dim=1)
        return attention_output,attention_weights


class AttentionLayer(nn.Module):
    def __init__(self,input_dim,output_dim,alpha=0.2,bias=True):
        super(AttentionLayer, self).__init__()

        self.input_dim = input_dim #
        self.output_dim = output_dim #16
        self.alpha = alpha

        ## w = (output_dim*input_dim)
        self.weight = nn.Parameter(torch.FloatTensor(self.input_dim, self.output_dim))
        self.weight_interact = nn.Parameter(torch.FloatTensor(self.input_dim,self.output_dim))
        ## a 1*2F
        self.a = nn.Parameter(torch.zeros(size=(2*self.output_dim,1))) #


        if bias:
            self.bias = nn.Parameter(torch.FloatTensor(self.output_dim))
        else:
            self.register_parameter('bias', None)

        ## 
        self.reset_parameters()


    def reset_parameters(self):
        ## 
        nn.init.xavier_uniform_(self.weight.data, gain=1.414)
        nn.init.xavier_uniform_(self.weight_interact.data, gain=1.414)
        if self.bias is not None:
            self.bias.data.fill_(0)
        nn.init.xavier_uniform_(self.a.data, gain=1.414)

    def _prepare_attentional_mechanism_input(self, x):

        Wh1 = torch.matmul(x, self.a[:self.output_dim, :])
        Wh2 = torch.matmul(x, self.a[self.output_dim:, :])
        e = F.leaky_relu(Wh1 + Wh2.T,negative_slope=self.alpha)
        return e

    ############（data_feature,adj）att()
    def forward(self,x,adj):
        ## matmul()
        h = torch.matmul(x, self.weight) # x:1120*421   weight:16*421
        e = self._prepare_attentional_mechanism_input(h) ## 

        zero_vec = -9e15 * torch.ones_like(e)
        attention = torch.where(adj.to_dense()>0, e, zero_vec)
        attention = F.softmax(attention, dim=1)
        # attention = F.softmax(e, dim=1)

        attention = F.dropout(attention, training=self.training)
        h_pass = torch.matmul(attention, h)

        output_data = h_pass


        output_data = F.leaky_relu(output_data,negative_slope=self.alpha)
        output_data = F.normalize(output_data,p=2,dim=1)


        if self.bias is not None:
            output_data = output_data + self.bias
        ############## 
        return output_data
















