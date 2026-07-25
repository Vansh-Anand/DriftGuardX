"""
DriftGuard-X v2 — Synthetic Dataset Generator for Diffusion
Generates controlled injected-fault episodes.
"""
import random
from typing import List, Tuple
import torch
from torch_geometric.data import Data

from packages.diffusion.src.contracts import DiffusionInput, NodeState, EdgeFeatures
from packages.contracts.src.graph import NodeType, EdgeType

NODE_TYPE_MAP = {t: i for i, t in enumerate(NodeType)}

def generate_synthetic_episode(
    family_id: int, 
    num_nodes: int = 5,
    fault_type: str = "retrieval_fault"
) -> Tuple[DiffusionInput, torch.Tensor, torch.Tensor]:
    """
    Generates a synthetic causal graph episode.
    Returns:
      - DiffusionInput
      - root_labels (Tensor of shape [N, 1])
      - symptom_labels (Tensor of shape [N, 1])
    """
    # Create simple sequential pipeline graph:
    # prompt -> retriever -> reranker -> generator -> policy
    nodes = []
    edges = []
    
    types = [NodeType.PROMPT, NodeType.AGENT, NodeType.MEMORY, NodeType.TOOL, NodeType.MODEL, NodeType.POLICY]
    
    # Ground truth labels
    root_labels = torch.zeros(num_nodes, 1, dtype=torch.float)
    symptom_labels = torch.zeros(num_nodes, 1, dtype=torch.float)
    
    # Fault injection logic
    root_idx = 1 if fault_type == "retrieval_fault" else 3 # Retriever or Generator
    
    for i in range(num_nodes):
        node_id = f"node_{family_id}_{i}"
        
        # Local detector scores (noisy)
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
            
        state = NodeState(
            node_id=node_id,
            local_symptom_score=local_score,
            severity_weight=local_score,
            node_type=types[i % len(types)]
        )
        nodes.append(state)
        
        if i > 0:
            # If the source was an AGENT, emit INTER_AGENT_COMMUNICATION to simulate multi-agent cascade
            edge_type = EdgeType.INTER_AGENT_COMMUNICATION if types[(i-1) % len(types)] == NodeType.AGENT else EdgeType.DATA_DEPENDENCY
            
            edge = EdgeFeatures(
                source_id=f"node_{family_id}_{i-1}",
                target_id=node_id,
                edge_type=edge_type,
                confidence=1.0,
                directionality=1.0
            )
            edges.append(edge)
            
    return DiffusionInput(nodes=nodes, edges=edges), root_labels, symptom_labels

def build_pyg_dataset(num_episodes: int = 100) -> List[Data]:
    dataset = []
    # Split by family to avoid leakage
    for i in range(num_episodes):
        fault = "retrieval_fault" if i % 2 == 0 else "generation_fault"
        diffusion_in, root_labels, symptom_labels = generate_synthetic_episode(family_id=i, fault_type=fault)
        
        x = torch.tensor([[n.local_symptom_score, n.severity_weight] for n in diffusion_in.nodes], dtype=torch.float)
        
        edge_index = []
        edge_attr = []
        for e in diffusion_in.edges:
            src = int(e.source_id.split("_")[-1])
            dst = int(e.target_id.split("_")[-1])
            edge_index.append([src, dst])
            edge_attr.append([1.0, e.confidence]) # Simplified edge type
            
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_attr, dtype=torch.float)
        
        node_types = torch.tensor([NODE_TYPE_MAP[n.node_type] for n in diffusion_in.nodes], dtype=torch.long)
        
        data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y_root=root_labels, y_symptom=symptom_labels, node_types=node_types)
        dataset.append(data)
        
    return dataset
