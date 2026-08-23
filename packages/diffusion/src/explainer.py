"""
DriftGuard-X v2 — Diffusion Node-Level Explainer
"""
from typing import Any

import torch


def generate_node_explanations(
    nodes_info: list[dict[str, Any]],
    local_scores: torch.Tensor,
    root_probs: torch.Tensor,
    edge_index: torch.Tensor,
    attention_weights: torch.Tensor = None
) -> dict[str, dict]:
    """
    Generate explanations for each node in the graph based on diffusion results.
    """
    explanations = {}
    N = len(nodes_info)

    for i in range(N):
        node_id = nodes_info[i]["node_id"]
        local_score = local_scores[i].item()
        root_prob = root_probs[i].item()

        # Delta from local detector score
        delta = root_prob - local_score

        top_edges = []
        if attention_weights != None and edge_index.size(1) > 0:
            # Find incoming edges to this node
            incoming_mask = (edge_index[1] == i)
            if incoming_mask.any():
                incoming_srcs = edge_index[0][incoming_mask]
                incoming_atts = attention_weights[incoming_mask]

                # Sort by attention weight
                sorted_idx = torch.argsort(incoming_atts, descending=True)
                for idx in sorted_idx[:3]:
                    src_node = nodes_info[incoming_srcs[idx].item()]["node_id"]
                    weight = incoming_atts[idx].item()
                    top_edges.append(f"{src_node} ({weight:.2f})")

        explanations[node_id] = {
            "root_probability": root_prob,
            "local_symptom_score": local_score,
            "delta_from_local": delta,
            "top_influential_edges": top_edges,
            "propagation_depth": 2 # Assuming 2-layer GAT
        }

    return explanations
