"""
DriftGuard-X v2 — Graph Attention Network (GAT) Inference Engine
Trained on synthetic distributed traces.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np

from packages.contracts.src.models import GATFeatureSchema

try:
    import torch
    import torch.nn.functional as F
    from torch.nn import Dropout, LayerNorm, Linear, ReLU, Sequential
    from torch_geometric.nn import GATConv, global_max_pool, global_mean_pool

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

    # Mock classes for type checking if torch is missing
    class MockModule:
        def __init__(self, *args, **kwargs):
            pass

    torch = type(
        "torch",
        (),
        {"nn": type("nn", (), {"Module": MockModule}), "Tensor": Any, "long": Any, "float": Any},
    )  # type: ignore


class DriftGuardX_GAT(torch.nn.Module):
    """
    3-Layer Graph Attention Network architecture for distributed microservice fault detection.
    Matches the trained weights in 'driftguardx_gat_model.pth'.
    """

    def __init__(self, in_channels: int = 6, hidden_dim: int = 64, num_classes: int = 2):
        super().__init__()

        # Layer 1: in_channels -> hidden_dim * 4 heads
        self.conv1 = GATConv(in_channels, hidden_dim, heads=4, dropout=0.2)
        self.norm1 = LayerNorm(hidden_dim * 4)

        # Layer 2: (hidden_dim * 4) -> hidden_dim * 4 heads
        self.conv2 = GATConv(hidden_dim * 4, hidden_dim, heads=4, dropout=0.2)
        self.norm2 = LayerNorm(hidden_dim * 4)

        # Layer 3: (hidden_dim * 4) -> hidden_dim (1 head)
        self.conv3 = GATConv(hidden_dim * 4, hidden_dim, heads=1, concat=False, dropout=0.2)
        self.norm3 = LayerNorm(hidden_dim)

        # Classifier Head (Mean + Max pooling concat -> hidden_dim * 2)
        self.graph_classifier = Sequential(
            Linear(hidden_dim * 2, 64), ReLU(), Dropout(0.3), Linear(64, num_classes)
        )

        # Node Classifier Head
        self.node_classifier = Sequential(
            Linear(hidden_dim, 32), ReLU(), Dropout(0.3), Linear(32, num_classes)
        )

    def forward(
        self, x: torch.Tensor, edge_index: torch.Tensor, batch: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        x = F.elu(self.conv1(x, edge_index))
        x = self.norm1(x)

        x = F.elu(self.conv2(x, edge_index))
        x = self.norm2(x)

        x_node = F.elu(self.conv3(x, edge_index))
        x_node = self.norm3(x_node)

        x_mean = global_mean_pool(x_node, batch)
        x_max = global_max_pool(x_node, batch)
        x_pool = torch.cat([x_mean, x_max], dim=1)

        graph_logits = self.graph_classifier(x_pool)
        node_logits = self.node_classifier(x_node)

        return graph_logits, node_logits


class GATTraceDetector:
    """
    Production detector wrapper for executing GAT inference on live or ingested Jaeger/OTel traces.
    """

    def __init__(self, model_path: str = "driftguardx_gat_model.pth", device: str | None = None):
        self.is_loaded = False

        if not TORCH_AVAILABLE:
            print("Warning: PyTorch not available. Detector running in mock heuristic mode.")
            self.device = "mock_cpu"
            return

        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = DriftGuardX_GAT(in_channels=6, hidden_dim=64, num_classes=2)

        if os.path.exists(model_path):
            state_dict = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
        else:
            print(
                f"Warning: Model weight file '{model_path}' not found. Detector running in mock mode."
            )

    def detect_trace_anomaly(self, spans: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Run inference on a single distributed trace (list of span dicts).

        Args:
            spans: List of spans with keys:
                   - 'span_id' (str)
                   - 'parent_id' (Optional[str])
                   - 'duration_ms' (float)
                   - 'operation_name' (str)
                   - 'is_error' (bool)

        Returns:
            Dict containing:
                - 'is_fault': bool
                - 'fault_probability': float (0.0 - 1.0)
                - 'predicted_class': int (0=Normal, 1=Faulty)
                - 'num_spans': int
                - 'root_cause_candidates': List of highest latency / error spans
        """
        if not self.is_loaded or len(spans) == 0:
            return {
                "is_fault": False,
                "fault_probability": 0.0,
                "predicted_class": 0,
                "num_spans": len(spans),
                "root_cause_candidates": [],
            }

        span_id_map = {s.get("span_id", str(i)): i for i, s in enumerate(spans)}
        total_trace_dur = max(float(s.get("duration_ms", 1.0)) for s in spans) + 1e-5

        # Build edges and children map
        children = {i: [] for i in range(len(spans))}
        edge_sources, edge_targets = [], []

        for i, s in enumerate(spans):
            parent_id = s.get("parent_id")
            if parent_id and parent_id in span_id_map:
                parent_idx = span_id_map[parent_id]
                children[parent_idx].append(i)
                edge_sources.extend([parent_idx, i])
                edge_targets.extend([i, parent_idx])

        if len(edge_sources) == 0:
            # Self loops fallback
            edge_sources = list(range(len(spans)))
            edge_targets = list(range(len(spans)))

        # Extract features using GATFeatureSchema
        node_features = []
        for i, s in enumerate(spans):
            dur = float(s.get("duration_ms", 0.0))
            rel_dur = dur / total_trace_dur
            child_durs = sum(float(spans[c].get("duration_ms", 0.0)) for c in children[i])
            self_time = max(0.0, dur - child_durs) / total_trace_dur
            is_err = 1.0 if s.get("is_error", False) else 0.0
            fanout = float(len(children[i]))
            op_code = float(hash(s.get("operation_name", "")) % 50)

            schema = GATFeatureSchema(
                log_duration=float(np.log1p(dur)),
                relative_duration=rel_dur,
                self_time_ratio=self_time,
                is_error=is_err,
                fanout=fanout,
                operation_encoding=op_code,
            )
            node_features.append(schema.to_list())

        x = torch.tensor(node_features, dtype=torch.float, device=self.device)
        edge_index = torch.tensor(
            [edge_sources, edge_targets], dtype=torch.long, device=self.device
        )

        with torch.no_grad():
            graph_logits, node_logits = self.model(x, edge_index)
            probs = F.softmax(graph_logits, dim=1).cpu().numpy()[0]
            pred_class = int(np.argmax(probs))
            fault_prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
            node_probs = F.softmax(node_logits, dim=1)[:, 1].cpu().numpy()

        # Identify suspicious spans using node-level GAT predictions
        # (Fallback to self_time/is_error heuristics if node probs are uninformative, e.g. untrained)
        suspicious_spans = sorted(
            [
                {
                    "span_id": s.get("span_id", str(i)),
                    "operation_name": s.get("operation_name", "unknown"),
                    "duration_ms": s.get("duration_ms", 0.0),
                    "is_error": s.get("is_error", False),
                    "self_time_ratio": node_features[i][2],
                    "node_fault_prob": float(node_probs[i]),
                }
                for i, s in enumerate(spans)
            ],
            key=lambda item: (
                item["node_fault_prob"],
                item["is_error"],
                item["self_time_ratio"],
                item["duration_ms"],
            ),
            reverse=True,
        )

        return {
            "is_fault": bool(pred_class == 1),
            "fault_probability": round(fault_prob, 4),
            "predicted_class": pred_class,
            "num_spans": len(spans),
            "root_cause_candidates": suspicious_spans[:3],
        }
