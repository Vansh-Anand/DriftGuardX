"""
DriftGuard-X v2 — Diffusion Models (Prompt 06)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATv2Conv


class LocalDetectorBaseline(nn.Module):
    """
    Baseline: No propagation. Root probability is exactly the local symptom score.
    """

    def forward(self, x, edge_index, edge_attr=None):
        # x is [N, 2] where x[:, 0] is local_symptom_score
        root_prob = x[:, 0].unsqueeze(1)
        return root_prob, root_prob


class FixedPageRankDiffusion(nn.Module):
    """
    Fixed non-learned propagation based on PageRank.
    """

    def __init__(self, alpha=0.85, steps=3):
        super().__init__()
        self.alpha = alpha
        self.steps = steps

    def forward(self, x, edge_index, edge_attr=None):
        N = x.size(0)
        adj = torch.zeros((N, N), device=x.device)
        if edge_index.size(1) > 0:
            adj[edge_index[0], edge_index[1]] = 1.0

        # Normalize adjacency
        deg = adj.sum(dim=1, keepdim=True)
        deg[deg == 0] = 1.0
        adj = adj / deg

        # Initial states (Personalization vector)
        p0 = x[:, 0].unsqueeze(1)
        p = p0.clone()

        for _ in range(self.steps):
            p = self.alpha * torch.mm(adj, p) + (1 - self.alpha) * p0

        return p, p0


class LearnedGATDiffusion(nn.Module):
    """
    Learned GAT-style propagation for distinguishing roots from symptoms.
    """

    def __init__(self, in_channels=2, hidden_channels=16, out_channels=1, heads=2, num_layers=2):
        super().__init__()
        self.num_layers = num_layers

        self.convs = nn.ModuleList()
        self.convs.append(
            GATv2Conv(in_channels, hidden_channels, heads=heads, edge_dim=2, concat=False)
        )

        for _ in range(num_layers - 1):
            self.convs.append(
                GATv2Conv(hidden_channels, hidden_channels, heads=heads, edge_dim=2, concat=False)
            )

        self.root_head = nn.Linear(hidden_channels, out_channels)
        self.symptom_head = nn.Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index, edge_attr=None):
        h = x
        for i, conv in enumerate(self.convs):
            h = conv(h, edge_index, edge_attr=edge_attr)
            if i < self.num_layers - 1:
                h = F.elu(h)

        # Outputs
        root_logits = self.root_head(h)
        symptom_logits = self.symptom_head(h)

        return torch.sigmoid(root_logits), torch.sigmoid(symptom_logits)
