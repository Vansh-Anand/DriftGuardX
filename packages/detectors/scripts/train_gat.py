import argparse
import hashlib
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    brier_score_loss,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier
from torch.nn import Dropout, Linear, ReLU, Sequential
from torch_geometric.loader import DataLoader
from torch_geometric.nn import GCNConv, global_max_pool, global_mean_pool

from packages.detectors.src.gat_inference import DriftGuardX_GAT
from packages.diffusion.src.dataset import build_pyg_dataset


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class DriftGuardX_GCN(torch.nn.Module):
    """Alternative GNN Baseline using Graph Convolutional Networks."""

    def __init__(self, in_channels: int = 6, hidden_dim: int = 64, num_classes: int = 2):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden_dim)
        self.conv2 = GCNConv(hidden_dim, hidden_dim)
        self.conv3 = GCNConv(hidden_dim, hidden_dim)

        self.graph_classifier = Sequential(
            Linear(hidden_dim * 2, 64), ReLU(), Dropout(0.3), Linear(64, num_classes)
        )
        self.node_classifier = Sequential(
            Linear(hidden_dim, 32), ReLU(), Dropout(0.3), Linear(32, num_classes)
        )

    def forward(self, x, edge_index, batch=None):
        if batch is None:
            batch = torch.zeros(x.size(0), dtype=torch.long, device=x.device)

        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        x_node = F.relu(self.conv3(x, edge_index))

        x_mean = global_mean_pool(x_node, batch)
        x_max = global_max_pool(x_node, batch)
        x_pool = torch.cat([x_mean, x_max], dim=1)

        graph_logits = self.graph_classifier(x_pool)
        node_logits = self.node_classifier(x_node)
        return graph_logits, node_logits


def compute_metrics(y_true, y_prob, y_pred):
    try:
        roc_auc = roc_auc_score(y_true, y_prob)
    except ValueError:
        roc_auc = 0.0

    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    pr_auc = auc(recall, precision) if len(recall) > 1 else 0.0
    f1 = f1_score(y_true, y_pred, zero_division=0)
    mcc = matthews_corrcoef(y_true, y_pred)
    brier = brier_score_loss(y_true, y_prob)
    return {
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "f1": float(f1),
        "mcc": float(mcc),
        "brier_score": float(brier),
    }


def compute_ranking_metrics(y_true_nodes, y_prob_nodes, batch_idx):
    """Computes Hit@k and MRR per graph (batch)."""
    graphs = defaultdict(list)
    for y_t, y_p, b in zip(y_true_nodes, y_prob_nodes, batch_idx, strict=False):
        graphs[b].append((y_t, y_p))

    hits = {1: [], 3: [], 5: []}
    mrrs = []

    for b, nodes in graphs.items():
        # Sort nodes by predicted probability descending
        nodes.sort(key=lambda x: x[1], reverse=True)
        # Find first rank of a true root cause
        rank = -1
        for i, (y_t, _) in enumerate(nodes):
            if y_t == 1:
                rank = i + 1
                break

        if rank == -1:
            continue  # No true fault in this graph, ranking not applicable

        hits[1].append(1 if rank <= 1 else 0)
        hits[3].append(1 if rank <= 3 else 0)
        hits[5].append(1 if rank <= 5 else 0)
        mrrs.append(1.0 / rank)

    if not mrrs:
        return {"hit@1": 0.0, "hit@3": 0.0, "hit@5": 0.0, "mrr": 0.0}

    return {
        "hit@1": float(np.mean(hits[1])),
        "hit@3": float(np.mean(hits[3])),
        "hit@5": float(np.mean(hits[5])),
        "mrr": float(np.mean(mrrs)),
    }


def prepare_baseline_data_node_level(dataset):
    X = []
    y = []
    batch = []
    graph_idx = 0
    for data in dataset:
        X.append(data.x.numpy())
        y.append(data.y_root.numpy().squeeze(-1))
        batch.append(np.full(data.num_nodes, graph_idx))
        graph_idx += 1
    return np.concatenate(X), np.concatenate(y), np.concatenate(batch)


def compute_centrality_baseline(dataset):
    # Node ranking based on PageRank
    y_true = []
    y_prob = []
    batch = []
    graph_idx = 0

    for data in dataset:
        G = nx.Graph()
        edges = data.edge_index.numpy()
        for i in range(edges.shape[1]):
            G.add_edge(edges[0, i], edges[1, i])

        try:
            pr = nx.pagerank(G, alpha=0.85)
        except:
            pr = {n: 0.0 for n in range(data.num_nodes)}

        probs = [pr.get(i, 0.0) for i in range(data.num_nodes)]

        y_prob.extend(probs)
        y_true.extend(data.y_root.numpy())
        batch.extend([graph_idx] * data.num_nodes)
        graph_idx += 1

    return compute_ranking_metrics(y_true, y_prob, batch)


def run_ml_baselines(train_dataset, test_dataset):
    X_train, y_train, _ = prepare_baseline_data_node_level(train_dataset)
    X_test, y_test, batch_test = prepare_baseline_data_node_level(test_dataset)

    results = {}
    models = {
        "lr": LogisticRegression(max_iter=1000, random_state=42),
        "rf": RandomForestClassifier(n_estimators=100, random_state=42),
        "xgb": HistGradientBoostingClassifier(random_state=42),
        "mlp": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=200, random_state=42),
    }

    if len(np.unique(y_train)) > 1:
        for name, model in models.items():
            model.fit(X_train, y_train)
            y_prob = (
                model.predict_proba(X_test)[:, 1]
                if model.classes_.size > 1
                else np.zeros_like(y_test)
            )
            y_pred = model.predict(X_test)

            cls_metrics = compute_metrics(y_test, y_prob, y_pred)
            rnk_metrics = compute_ranking_metrics(y_test, y_prob, batch_test)
            results[name] = {**cls_metrics, **rnk_metrics}
    else:
        empty = {
            "roc_auc": 0,
            "pr_auc": 0,
            "f1": 0,
            "mcc": 0,
            "brier_score": 0,
            "hit@1": 0,
            "hit@3": 0,
            "hit@5": 0,
            "mrr": 0,
        }
        results = {name: empty for name in models}

    return results


def train_gnn(model, train_loader, val_loader, test_loader, device, args):
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    best_val_auc = -1
    best_model_state = None

    for _epoch in range(args.epochs):
        model.train()
        total_loss = 0
        for data in train_loader:
            data = data.to(device)
            optimizer.zero_grad()
            graph_logits, node_logits = model(data.x, data.edge_index, data.batch)

            loss_g = F.cross_entropy(graph_logits, data.y)
            loss_n = F.cross_entropy(node_logits, data.y_root.squeeze(-1).long())
            loss = loss_g + loss_n

            loss.backward()
            optimizer.step()
            total_loss += loss.item() * data.num_graphs

        model.eval()
        val_y_true, val_y_prob = [], []
        with torch.no_grad():
            for data in val_loader:
                data = data.to(device)
                graph_logits, _ = model(data.x, data.edge_index, data.batch)
                probs = F.softmax(graph_logits, dim=1)[:, 1].cpu().numpy()
                val_y_true.extend(data.y.cpu().numpy())
                val_y_prob.extend(probs)

        try:
            val_auc = roc_auc_score(val_y_true, val_y_prob)
        except ValueError:
            val_auc = 0.0

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            best_model_state = model.state_dict()

    if best_model_state:
        model.load_state_dict(best_model_state)

    # Final Test Eval
    model.eval()
    test_y_true, test_y_prob, test_y_pred = [], [], []
    node_y_true, node_y_prob, node_batch = [], [], []

    with torch.no_grad():
        for data in test_loader:
            data = data.to(device)
            graph_logits, node_logits = model(data.x, data.edge_index, data.batch)

            # Graph level classification
            probs = F.softmax(graph_logits, dim=1)[:, 1].cpu().numpy()
            preds = graph_logits.argmax(dim=1).cpu().numpy()
            test_y_true.extend(data.y.cpu().numpy())
            test_y_prob.extend(probs)
            test_y_pred.extend(preds)

            # Node level ranking
            n_probs = F.softmax(node_logits, dim=1)[:, 1].cpu().numpy()
            node_y_true.extend(data.y_root.cpu().numpy().squeeze(-1))
            node_y_prob.extend(n_probs)
            node_batch.extend(data.batch.cpu().numpy())

    cls_metrics = compute_metrics(test_y_true, test_y_prob, test_y_pred)
    rnk_metrics = compute_ranking_metrics(node_y_true, node_y_prob, node_batch)
    return {**cls_metrics, **rnk_metrics}


def train_main(args) -> None:
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Building dataset...")
    dataset = build_pyg_dataset(num_episodes=500)

    import pickle

    dataset_bytes = pickle.dumps([(data.x.numpy(), data.edge_index.numpy()) for data in dataset])
    dataset_hash = hashlib.sha256(dataset_bytes).hexdigest()

    for data in dataset:
        data.y = torch.tensor([data.y_root.max().item()], dtype=torch.long)

    random.shuffle(dataset)
    n = len(dataset)
    train_size = int(0.7 * n)
    val_size = int(0.15 * n)

    train_dataset = dataset[:train_size]
    val_dataset = dataset[train_size : train_size + val_size]
    test_dataset = dataset[train_size + val_size :]

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    print(
        f"Dataset split: {len(train_dataset)} train, {len(val_dataset)} val, {len(test_dataset)} test"
    )

    results = {}

    print("Training GAT...")
    gat_model = DriftGuardX_GAT(in_channels=6, hidden_dim=64, num_classes=2).to(device)
    results["gat"] = train_gnn(gat_model, train_loader, val_loader, test_loader, device, args)

    # Save GAT model explicitly to be used by production inference
    out_dir = Path("packages/detectors/weights")
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "driftguardx_gat_model.pth"
    torch.save(gat_model.state_dict(), model_path)

    print("Training GCN (Alternative GNN)...")
    gcn_model = DriftGuardX_GCN(in_channels=6, hidden_dim=64, num_classes=2).to(device)
    results["gcn"] = train_gnn(gcn_model, train_loader, val_loader, test_loader, device, args)

    print("Evaluating ML Baselines...")
    ml_res = run_ml_baselines(train_dataset, test_dataset)
    results.update(ml_res)

    print("Evaluating Graph Centrality Baseline...")
    cent_rnk = compute_centrality_baseline(test_dataset)
    results["centrality"] = {
        "roc_auc": 0,
        "pr_auc": 0,
        "f1": 0,
        "mcc": 0,
        "brier_score": 0,
        **cent_rnk,
    }

    print("\n--- Final Evaluation ---")
    for name, m in results.items():
        print(
            f"[{name.upper()}] "
            f"ROC: {m['roc_auc']:.3f}, PR: {m['pr_auc']:.3f}, F1: {m['f1']:.3f}, "
            f"Hit@1: {m['hit@1']:.3f}, Hit@3: {m['hit@3']:.3f}, MRR: {m['mrr']:.3f}"
        )

    with open(model_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    meta = {
        "feature_schema_version": "1.0.0",
        "dataset_hash": dataset_hash,
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "metrics": results,
        "checkpoint_hash": file_hash,
        "timestamp": time.time(),
    }

    with open(out_dir / "training_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nGAT Model saved to {model_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.005)
    args = parser.parse_args()

    train_main(args)
