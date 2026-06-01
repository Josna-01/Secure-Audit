# app/hgat_model.py
# RAG-LC-HGAT model implementation (inference-ready).
# NOTE: corrected fused_dim to match actual concat: case_repr(384)+attn(384)+mean(1024)+max(1024)=2816.

from typing import Optional
import torch
import torch.nn as nn
import torch.nn.functional as F

# optional import for torch_geometric (GATConv)
_has_tg = False
try:
    from torch_geometric.nn import GATConv
    _has_tg = True
except Exception:
    GATConv = None

def init_lin(layer: nn.Module):
    if isinstance(layer, nn.Linear):
        nn.init.xavier_uniform_(layer.weight)
        if layer.bias is not None:
            nn.init.zeros_(layer.bias)

class ImprovedSectionHead(nn.Module):
    def __init__(self, in_dim: int, num_sections: int = 57):
        super().__init__()
        self.num_sections = num_sections
        self.experts = nn.ModuleList([nn.Linear(in_dim, 1) for _ in range(num_sections)])
        for lin in self.experts:
            init_lin(lin)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        outs = [lin(x) for lin in self.experts]  # list of [B,1]
        return torch.cat(outs, dim=-1)  # [B, num_sections]

class RAGLCHGATModel(nn.Module):
    """
    Hybrid RAG + HGAT model.

    IMPORTANT:
      - fused input is 2816 (384 + 384 + 1024 + 1024).
      - shared_base projects 2816 -> 1536 (keeps downstream heads same size).
    """
    def __init__(
        self,
        num_sections: int = 57,
        section_node_features: Optional[torch.Tensor] = None,
        edge_index: Optional[torch.Tensor] = None,
        device: Optional[torch.device] = None,
        case_hidden: int = 384,
        fused_dim: int = 2816,           # corrected fused dimension
        shared_base_dim: int = 1536,     # downstream head input dim
        crime_types: int = 13,
    ):
        super().__init__()
        self.num_sections = num_sections
        self.case_hidden = case_hidden
        self.crime_types = crime_types
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Case encoder: maps (768 + num_sections) -> case_hidden
        self.case_encoder = nn.Sequential(
            nn.Linear(768 + num_sections, 768),
            nn.LayerNorm(768),
            nn.ReLU(),
            nn.Dropout(0.25),
            nn.Linear(768, case_hidden),
            nn.LayerNorm(case_hidden),
            nn.ReLU(),
            nn.Dropout(0.25),
        )
        for m in self.case_encoder:
            init_lin(m)

        # Node features and edge index (set at construction)
        self.section_node_features = None
        if section_node_features is not None:
            self.section_node_features = section_node_features.float().to(self.device)
        self.edge_index = edge_index

        # GAT / fallback MLP
        if _has_tg:
            self.gat1 = GATConv(in_channels=384, out_channels=256, heads=4, concat=True, dropout=0.1)
            self.gat2 = GATConv(in_channels=1024, out_channels=256, heads=4, concat=True, dropout=0.1)
        else:
            self.gat1 = nn.Sequential(nn.Linear(384, 1024), nn.ELU())
            self.gat2 = nn.Sequential(nn.Linear(1024, 1024), nn.ELU())
            init_lin(self.gat1[0])
            init_lin(self.gat2[0])

        # cross-attention
        self.cross_attn = nn.MultiheadAttention(embed_dim=case_hidden, num_heads=4, batch_first=True)
        self.node_to_case_proj = nn.Linear(1024, case_hidden)
        init_lin(self.node_to_case_proj)

        # Shared base: project fused (2816) to shared_base_dim (1536) — matches heads
        self.shared_base = nn.Sequential(
            nn.Linear(fused_dim, shared_base_dim),
            nn.LayerNorm(shared_base_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
        )
        init_lin(self.shared_base[0])

        # Heads
        self.section_head = ImprovedSectionHead(in_dim=shared_base_dim, num_sections=num_sections)
        self.crime_head = nn.Sequential(
            nn.Linear(shared_base_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, crime_types)
        )
        init_lin(self.crime_head[0])
        # last linear init
        if isinstance(self.crime_head[-1], nn.Linear):
            init_lin(self.crime_head[-1])

        # move model to device
        self.to(self.device)

    def _ensure_edge_index(self, num_nodes: int) -> torch.Tensor:
        if self.edge_index is not None:
            return self.edge_index.to(self.device)
        rows, cols = [], []
        for i in range(num_nodes):
            for j in range(num_nodes):
                rows.append(i)
                cols.append(j)
        edge_index = torch.tensor([rows, cols], dtype=torch.long, device=self.device)
        return edge_index

    def infer_from_features(self, features: torch.Tensor) -> dict:
        x = features.to(self.device).float()
        batch_size = x.shape[0]

        # case representation
        case_repr = self.case_encoder(x)  # [B, case_hidden]

        # node features
        if self.section_node_features is None:
            node_feat = torch.zeros((self.num_sections, 384), device=self.device, dtype=torch.float32)
        else:
            node_feat = self.section_node_features  # [N, 384]

        edge_index = self._ensure_edge_index(num_nodes=node_feat.shape[0])

        if _has_tg:
            h = F.elu(self.gat1(node_feat, edge_index))  # [N,1024]
            h = F.elu(self.gat2(h, edge_index))         # [N,1024]
        else:
            h = self.gat1(node_feat)                     # [N,1024]
            h = self.gat2(h)                             # [N,1024]

        node_for_attn = self.node_to_case_proj(h)  # [N, case_hidden]
        pooled_mean = h.mean(dim=0, keepdim=True)  # [1, 1024]
        pooled_max = h.max(dim=0, keepdim=True)[0] # [1, 1024]

        # cross-attn
        q = case_repr.unsqueeze(1)  # [B,1,case_hidden]
        kv = node_for_attn.unsqueeze(0).expand(batch_size, -1, -1)  # [B,N,case_hidden]
        attn_out, _ = self.cross_attn(query=q, key=kv, value=kv, need_weights=False)
        attn_out = attn_out.squeeze(1)  # [B, case_hidden]

        # fuse: case_repr(384) + attn_out(384) + pooled_mean(1024) + pooled_max(1024) = 2816
        pooled_mean_b = pooled_mean.expand(batch_size, -1)
        pooled_max_b = pooled_max.expand(batch_size, -1)
        fused = torch.cat([case_repr, attn_out, pooled_mean_b, pooled_max_b], dim=-1)  # [B,2816]

        # shared base: project 2816 -> shared_base_dim (1536)
        shared = self.shared_base(fused)  # [B, shared_base_dim]

        section_logits = self.section_head(shared)  # [B, num_sections]
        crime_logits = self.crime_head(shared)      # [B, crime_types]

        return {"section_logits": section_logits, "crime_logits": crime_logits}

    def predict_proba(self, features: torch.Tensor) -> dict:
        out = self.infer_from_features(features)
        sec_logits = out["section_logits"]
        crime_logits = out["crime_logits"]
        sec_probs = torch.sigmoid(sec_logits)
        crime_probs = torch.softmax(crime_logits, dim=-1)
        return {"section_probs": sec_probs.detach().cpu().numpy(), "crime_probs": crime_probs.detach().cpu().numpy()}
