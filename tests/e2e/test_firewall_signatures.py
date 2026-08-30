import pytest

torch = pytest.importorskip("torch")

from packages.contracts.src.graph import NodeType
from packages.diffusion.src.dataset import NODE_TYPE_MAP
from packages.diffusion.src.trainer import DiffusionLoss


def test_firewall_signature_loss():
    # Setup node types tensor for a graph: [MEMORY, TOOL, MODEL]
    node_types = torch.tensor(
        [
            NODE_TYPE_MAP[NodeType.MEMORY],
            NODE_TYPE_MAP[NodeType.TOOL],
            NODE_TYPE_MAP[NodeType.MODEL],
        ],
        dtype=torch.long,
    )

    # Create edges: 0 -> 1 (MEMORY -> TOOL) and 1 -> 2 (TOOL -> MODEL)
    edge_index = torch.tensor([[0, 1], [1, 2]], dtype=torch.long)

    # Simulate bad predictions where the symptom probability for the TOOL node (node 1) is very low
    root_pred = torch.tensor([[0.1], [0.1], [0.1]])
    symptom_pred = torch.tensor([[0.1], [0.1], [0.1]])  # Node 1 (TOOL) is 0.1

    root_true = torch.tensor([[0.0], [1.0], [0.0]])
    symptom_true = torch.tensor([[0.0], [1.0], [0.0]])

    criterion = DiffusionLoss(
        lambda_symptom=0.0, lambda_sparse=0.0, lambda_contrastive=0.0, lambda_signature=1.0
    )

    loss, metrics = criterion(
        root_pred,
        symptom_pred,
        root_true,
        symptom_true,
        node_types=node_types,
        edge_index=edge_index,
    )

    # We want symptom_pred to be close to 1.0 for the TOOL node
    # Since it is 0.1, the penalty is (1.0 - 0.1)^2 = 0.9^2 = 0.81
    # Note: bce loss is also computed and added.

    assert "signature_loss" in metrics
    assert metrics["signature_loss"] > 0.8
    assert metrics["signature_loss"] < 0.82

    # Simulate good predictions where the symptom probability for the TOOL node is very high
    symptom_pred_good = torch.tensor([[0.1], [0.99], [0.1]])  # Node 1 (TOOL) is 0.99

    loss_good, metrics_good = criterion(
        root_pred,
        symptom_pred_good,
        root_true,
        symptom_true,
        node_types=node_types,
        edge_index=edge_index,
    )

    # Penalty should be very small: (1.0 - 0.99)^2 = 0.0001
    assert metrics_good["signature_loss"] < 0.001
