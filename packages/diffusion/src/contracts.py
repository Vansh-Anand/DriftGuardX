"""
DriftGuard-X v2 — Diffusion Models Software and Mathematical Contract
PRIVATE — All Rights Reserved.
"""
from pydantic import Field

from packages.contracts.src.graph import EdgeType, NodeType
from packages.contracts.src.models import DGXBaseModel


class NodeState(DGXBaseModel):
    """
    Initial state of a node before diffusion.
    - local_symptom_score: The uncalibrated score from a local detector (0.0 to 1.0).
    - severity_weight: Weight corresponding to SymptomLikelihood.
    - node_type_onehot: One-hot encoded node type (e.g. RETRIEVER, GENERATOR).
    """
    node_id: str
    local_symptom_score: float = 0.0
    severity_weight: float = 0.0
    node_type: NodeType

class EdgeFeatures(DGXBaseModel):
    """
    Edge features for the GNN message passing mechanism.
    - edge_type: Enum translated into one-hot or embedding.
    - confidence: Scalar [0, 1] derived from graph construction (e.g., certainty of causal link).
    - directionality: 1.0 for forward (cause->effect), -1.0 for backward.
    """
    source_id: str
    target_id: str
    edge_type: EdgeType
    confidence: float = 1.0
    directionality: float = 1.0

class DiffusionInput(DGXBaseModel):
    """
    Normalized graph features input for the diffusion models.
    """
    nodes: list[NodeState]
    edges: list[EdgeFeatures]

class NodeExplanation(DGXBaseModel):
    """
    Node-level interpretability metadata.
    """
    top_influential_edges: list[str] = Field(default_factory=list)  # IDs of incoming edges with high attention
    top_contributing_neighbors: list[str] = Field(default_factory=list)
    propagation_depth: int = 0
    delta_from_local: float = 0.0

class DiffusionOutput(DGXBaseModel):
    """
    Result of the diffusion process mapping symptoms to likely roots.
    """
    node_id: str
    root_probability: float  # Calibrated probability that this node is the ROOT cause
    symptom_probability: float  # Calibrated probability that this node exhibits the symptom
    uncertainty: float
    explanation: NodeExplanation

class GraphDiffusionResult(DGXBaseModel):
    model_version: str
    node_outputs: dict[str, DiffusionOutput]

    # Mathematical hyperparams used
    num_steps: int
    aggregation_method: str
    normalization_applied: bool
