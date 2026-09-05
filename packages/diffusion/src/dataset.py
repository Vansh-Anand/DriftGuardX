"""
DriftGuard-X v2 — Synthetic Dataset Generator for Diffusion
Generates controlled injected-fault episodes.
"""

import random

import torch
from torch_geometric.data import Data

from packages.contracts.src.graph import EdgeType, NodeType
from packages.diffusion.src.contracts import DiffusionInput, EdgeFeatures, NodeState

NODE_TYPE_MAP = {t: i for i, t in enumerate(NodeType)}


def generate_synthetic_episode(
    family_id: int, 
    num_nodes: int = 5, 
    fault_type: str = "fault_1",
    workload_type: str = "A"
) -> tuple[DiffusionInput, torch.Tensor, torch.Tensor]:
    """
    Generates a synthetic causal graph episode.
    Returns:
      - DiffusionInput
      - root_labels (Tensor of shape [N, 1])
      - symptom_labels (Tensor of shape [N, 1])
    """
    nodes = []
    edges = []

    if workload_type == "A":
        # Workload A: Standard sequential pipeline
        # prompt -> retriever -> reranker -> generator -> policy
        types = [
            NodeType.PROMPT,
            NodeType.AGENT,
            NodeType.MEMORY,
            NodeType.TOOL,
            NodeType.MODEL,
            NodeType.POLICY,
        ]
        
        # Build sequential edges
        for i in range(num_nodes):
            node_id = f"node_{family_id}_{i}"
            nodes.append(NodeState(
                node_id=node_id,
                local_symptom_score=0.0,
                severity_weight=0.0,
                node_type=types[i % len(types)],
            ))
            if i > 0:
                edge_type = EdgeType.INTER_AGENT_COMMUNICATION if types[(i - 1) % len(types)] == NodeType.AGENT else EdgeType.DATA_DEPENDENCY
                edges.append(EdgeFeatures(
                    source_id=f"node_{family_id}_{i-1}",
                    target_id=node_id,
                    edge_type=edge_type,
                    confidence=1.0,
                    directionality=1.0,
                ))
    else:
        # Workload B: Parallel fanout topology
        # prompt -> router -> [retriever1, retriever2, retriever3] -> generator
        num_nodes = max(6, num_nodes)
        node_ids = [f"node_{family_id}_{i}" for i in range(num_nodes)]
        types = [NodeType.PROMPT, NodeType.AGENT, NodeType.MEMORY, NodeType.MEMORY, NodeType.MEMORY, NodeType.MODEL] + [NodeType.TOOL] * (num_nodes - 6)
        
        for i in range(num_nodes):
            nodes.append(NodeState(
                node_id=node_ids[i],
                local_symptom_score=0.0,
                severity_weight=0.0,
                node_type=types[i],
            ))
            
        edges.append(EdgeFeatures(source_id=node_ids[0], target_id=node_ids[1], edge_type=EdgeType.DATA_DEPENDENCY, confidence=1.0, directionality=1.0))
        edges.append(EdgeFeatures(source_id=node_ids[1], target_id=node_ids[2], edge_type=EdgeType.INTER_AGENT_COMMUNICATION, confidence=1.0, directionality=1.0))
        edges.append(EdgeFeatures(source_id=node_ids[1], target_id=node_ids[3], edge_type=EdgeType.INTER_AGENT_COMMUNICATION, confidence=1.0, directionality=1.0))
        edges.append(EdgeFeatures(source_id=node_ids[1], target_id=node_ids[4], edge_type=EdgeType.INTER_AGENT_COMMUNICATION, confidence=1.0, directionality=1.0))
        edges.append(EdgeFeatures(source_id=node_ids[2], target_id=node_ids[5], edge_type=EdgeType.DATA_DEPENDENCY, confidence=1.0, directionality=1.0))
        edges.append(EdgeFeatures(source_id=node_ids[3], target_id=node_ids[5], edge_type=EdgeType.DATA_DEPENDENCY, confidence=1.0, directionality=1.0))
        edges.append(EdgeFeatures(source_id=node_ids[4], target_id=node_ids[5], edge_type=EdgeType.DATA_DEPENDENCY, confidence=1.0, directionality=1.0))
        for i in range(6, num_nodes):
            edges.append(EdgeFeatures(source_id=node_ids[5], target_id=node_ids[i], edge_type=EdgeType.DATA_DEPENDENCY, confidence=1.0, directionality=1.0))


    # Ground truth labels
    root_labels = torch.zeros(num_nodes, 1, dtype=torch.float)
    symptom_labels = torch.zeros(num_nodes, 1, dtype=torch.float)

    # Fault injection logic
    # We support fault_1 to fault_12. Map them to a node index modulo num_nodes.
    fault_num = int(fault_type.split("_")[1]) if "_" in fault_type else 1
    root_idx = fault_num % num_nodes

    for i in range(num_nodes):
        if i == root_idx:
            local_score = random.uniform(0.7, 1.0)
            root_labels[i] = 1.0
            symptom_labels[i] = 1.0
        elif i > root_idx:
            # Downstream nodes exhibit symptoms due to propagation
            local_score = random.uniform(0.6, 0.9)
            symptom_labels[i] = 1.0
        else:
            # Upstream nodes are clean
            local_score = random.uniform(0.0, 0.3)
            
        nodes[i].local_symptom_score = local_score
        nodes[i].severity_weight = local_score

    diffusion_in = DiffusionInput(nodes=nodes, edges=edges)

    # Convert to features
    features = []
    import numpy as np
    for i, n in enumerate(diffusion_in.nodes):
        dur = random.uniform(10, 100)
        rel_dur = dur / 500.0
        self_time = dur * 0.8 / 500.0
        is_err = 1.0 if n.local_symptom_score > 0.8 else 0.0
        fanout = float(sum(1 for e in diffusion_in.edges if e.source_id == n.node_id))
        op_code = float(hash(str(n.node_type)) % 50)
        features.append([np.log1p(dur), rel_dur, self_time, is_err, fanout, op_code])
        
    x = torch.tensor(features, dtype=torch.float)

    edge_index = []
    edge_attr = []
    for e in diffusion_in.edges:
        src = int(e.source_id.split("_")[-1])
        dst = int(e.target_id.split("_")[-1])
        edge_index.append([src, dst])
        edge_attr.append([1.0, e.confidence])  # Simplified edge type

    if len(edge_index) > 0:
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_attr, dtype=torch.float)
    else:
        edge_index = torch.empty((2, 0), dtype=torch.long)
        edge_attr = torch.empty((0, 2), dtype=torch.float)

    node_types = torch.tensor(
        [NODE_TYPE_MAP[n.node_type] for n in diffusion_in.nodes], dtype=torch.long
    )

    data = Data(
        x=x,
        edge_index=edge_index,
        edge_attr=edge_attr,
        y_root=root_labels,
        y_symptom=symptom_labels,
        node_types=node_types,
    )
    
    return diffusion_in, root_labels, symptom_labels, data


def build_pyg_dataset(
    num_episodes: int = 100,
    workloads: list[str] = ["A"],
    fault_range: tuple[int, int] = (1, 8)
) -> list[Data]:
    dataset = []
    faults = [f"fault_{i}" for i in range(fault_range[0], fault_range[1] + 1)]
    for i in range(num_episodes):
        fault = random.choice(faults)
        wl = workloads[i % len(workloads)]
        _, _, _, data = generate_synthetic_episode(
            family_id=i, fault_type=fault, workload_type=wl
        )
        dataset.append(data)

    return dataset

