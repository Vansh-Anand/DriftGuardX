import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from torch_geometric.loader import DataLoader

from packages.detectors.src.gat_inference import DriftGuardX_GAT
from packages.diffusion.src.dataset import build_pyg_dataset


def compute_ranking_metrics(y_true_nodes, y_prob_nodes, batch_idx):
    """Computes Hit@1, Hit@3 and MRR per graph (batch)."""
    graphs = defaultdict(list)
    for y_t, y_p, b in zip(y_true_nodes, y_prob_nodes, batch_idx, strict=False):
        graphs[b].append((y_t, y_p))

    hits = {1: [], 3: []}
    mrrs = []

    for b, nodes in graphs.items():
        nodes.sort(key=lambda x: x[1], reverse=True)
        rank = -1
        for i, (y_t, _) in enumerate(nodes):
            if y_t == 1:
                rank = i + 1
                break

        if rank == -1:
            continue

        hits[1].append(1 if rank <= 1 else 0)
        hits[3].append(1 if rank <= 3 else 0)
        mrrs.append(1.0 / rank)

    if not mrrs:
        return {"hit@1": 0.0, "hit@3": 0.0, "mrr": 0.0}

    return {
        "hit@1": float(np.mean(hits[1])),
        "hit@3": float(np.mean(hits[3])),
        "mrr": float(np.mean(mrrs)),
    }


def evaluate_model(model, loader, device):
    model.eval()
    test_y_true, test_y_prob = [], []
    node_y_true, node_y_prob, node_batch = [], [], []

    with torch.no_grad():
        for data in loader:
            data = data.to(device)
            # Dummy target creation for compatibility if y is not set
            if not hasattr(data, "y") or data.y is None:
                data.y = torch.tensor(
                    [y_root.max().item() for y_root in data.y_root], dtype=torch.long, device=device
                )

            graph_logits, node_logits = model(data.x, data.edge_index, data.batch)

            probs = F.softmax(graph_logits, dim=1)[:, 1].cpu().numpy()
            test_y_true.extend(data.y.cpu().numpy())
            test_y_prob.extend(probs)

            n_probs = F.softmax(node_logits, dim=1)[:, 1].cpu().numpy()
            node_y_true.extend(data.y_root.cpu().numpy().squeeze(-1))
            node_y_prob.extend(n_probs)
            node_batch.extend(data.batch.cpu().numpy())

    try:
        roc_auc = roc_auc_score(test_y_true, test_y_prob)
    except ValueError:
        roc_auc = 0.0

    rnk_metrics = compute_ranking_metrics(node_y_true, node_y_prob, node_batch)
    return {"roc_auc": float(roc_auc), **rnk_metrics}


def main() -> None:
    print("--- DriftGuard-X Generalization Experiment ---")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # PHASE 1: Train on Workload A, Faults 1-8
    print("\nPhase 1: Generating Training Dataset (Workload A, Faults 1-8)")
    train_dataset = build_pyg_dataset(num_episodes=500, workloads=["A"], fault_range=(1, 8))
    for data in train_dataset:
        data.y = torch.tensor([data.y_root.max().item()], dtype=torch.long)

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)

    print("Training GAT model...")
    model = DriftGuardX_GAT(in_channels=6, hidden_dim=64, num_classes=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=1e-4)

    for _epoch in range(10):  # fast training for demo
        model.train()
        for data in train_loader:
            data = data.to(device)
            optimizer.zero_grad()
            graph_logits, node_logits = model(data.x, data.edge_index, data.batch)
            loss_g = F.cross_entropy(graph_logits, data.y)
            loss_n = F.cross_entropy(node_logits, data.y_root.squeeze(-1).long())
            loss = loss_g + loss_n
            loss.backward()
            optimizer.step()

    # PHASE 2: Test In-Distribution (Workload A, Faults 1-8)
    print("\nPhase 2: Evaluating In-Distribution (Workload A, Faults 1-8)")
    id_dataset = build_pyg_dataset(num_episodes=200, workloads=["A"], fault_range=(1, 8))
    for data in id_dataset:
        data.y = torch.tensor([data.y_root.max().item()], dtype=torch.long)
    id_loader = DataLoader(id_dataset, batch_size=32, shuffle=False)
    id_metrics = evaluate_model(model, id_loader, device)

    # PHASE 3: Test Out-of-Distribution (Workload B, Faults 9-12)
    print("\nPhase 3: Evaluating Out-of-Distribution (Workload B, Faults 9-12)")
    ood_dataset = build_pyg_dataset(num_episodes=200, workloads=["B"], fault_range=(9, 12))
    for data in ood_dataset:
        data.y = torch.tensor([data.y_root.max().item()], dtype=torch.long)
    ood_loader = DataLoader(ood_dataset, batch_size=32, shuffle=False)
    ood_metrics = evaluate_model(model, ood_loader, device)

    print("\n==============================================")
    print("      GENERALIZATION EXPERIMENT RESULTS       ")
    print("==============================================")
    print("Metric       | In-Distribution | Out-Of-Distribution")
    print("-------------|-----------------|--------------------")
    print(f"ROC AUC      | {id_metrics['roc_auc']:15.3f} | {ood_metrics['roc_auc']:19.3f}")
    print(f"Hit@1        | {id_metrics['hit@1']:15.3f} | {ood_metrics['hit@1']:19.3f}")
    print(f"Hit@3        | {id_metrics['hit@3']:15.3f} | {ood_metrics['hit@3']:19.3f}")
    print(f"MRR          | {id_metrics['mrr']:15.3f} | {ood_metrics['mrr']:19.3f}")

    out_dir = Path("packages/rag_benchmark/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "generalization_results.json"

    with open(out_file, "w") as f:
        json.dump(
            {
                "in_distribution": id_metrics,
                "out_of_distribution": ood_metrics,
                "timestamp": time.time(),
            },
            f,
            indent=2,
        )

    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
