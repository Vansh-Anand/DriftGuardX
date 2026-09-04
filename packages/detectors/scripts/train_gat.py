import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    roc_auc_score,
    auc
)
from sklearn.neural_network import MLPClassifier
from torch_geometric.loader import DataLoader
from torch_geometric.data import Data

from packages.detectors.src.gat_inference import DriftGuardX_GAT
from packages.diffusion.src.dataset import build_pyg_dataset


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


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


def prepare_baseline_data(dataset):
    X = []
    y = []
    # Graph-level classification for baseline: aggregate node features
    for data in dataset:
        # Sum pool the node features
        x_graph = data.x.sum(dim=0).numpy()
        X.append(x_graph)
        y.append(data.y_root.max().item())  # If any root fault exists
    return np.array(X), np.array(y)


def run_baselines(train_dataset, test_dataset):
    X_train, y_train = prepare_baseline_data(train_dataset)
    X_test, y_test = prepare_baseline_data(test_dataset)

    metrics = {}

    # MLP
    mlp = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=200, random_state=42)
    if len(np.unique(y_train)) > 1:
        mlp.fit(X_train, y_train)
        y_prob_mlp = mlp.predict_proba(X_test)[:, 1] if mlp.classes_.size > 1 else np.zeros_like(y_test)
        y_pred_mlp = mlp.predict(X_test)
        metrics["mlp"] = compute_metrics(y_test, y_prob_mlp, y_pred_mlp)
    else:
        metrics["mlp"] = {"roc_auc": 0, "pr_auc": 0, "f1": 0, "mcc": 0, "brier_score": 0}

    # Random Forest
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    if len(np.unique(y_train)) > 1:
        rf.fit(X_train, y_train)
        y_prob_rf = rf.predict_proba(X_test)[:, 1] if rf.classes_.size > 1 else np.zeros_like(y_test)
        y_pred_rf = rf.predict(X_test)
        metrics["rf"] = compute_metrics(y_test, y_prob_rf, y_pred_rf)
    else:
        metrics["rf"] = {"roc_auc": 0, "pr_auc": 0, "f1": 0, "mcc": 0, "brier_score": 0}

    return metrics


def train_gat(args):
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Building dataset...")
    # Generate 500 episodes
    dataset = build_pyg_dataset(num_episodes=500)
    
    # Create graph-level labels from node-level labels
    for data in dataset:
        data.y = torch.tensor([data.y_root.max().item()], dtype=torch.long)
        
    random.shuffle(dataset)
    
    n = len(dataset)
    train_size = int(0.7 * n)
    val_size = int(0.15 * n)
    
    train_dataset = dataset[:train_size]
    val_dataset = dataset[train_size:train_size + val_size]
    test_dataset = dataset[train_size + val_size:]

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    print(f"Dataset split: {len(train_dataset)} train, {len(val_dataset)} val, {len(test_dataset)} test")

    # model init (2 features in our PyG dataset: local_symptom_score, severity_weight)
    model = DriftGuardX_GAT(in_channels=2, hidden_dim=64, num_classes=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)

    best_val_auc = -1
    best_model_state = None

    print("Training GAT...")
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0
        for data in train_loader:
            data = data.to(device)
            optimizer.zero_grad()
            out = model(data.x, data.edge_index, data.batch)
            loss = F.cross_entropy(out, data.y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * data.num_graphs

        model.eval()
        val_y_true, val_y_prob = [], []
        with torch.no_grad():
            for data in val_loader:
                data = data.to(device)
                out = model(data.x, data.edge_index, data.batch)
                probs = F.softmax(out, dim=1)[:, 1].cpu().numpy()
                val_y_true.extend(data.y.cpu().numpy())
                val_y_prob.extend(probs)
        
        try:
            val_auc = roc_auc_score(val_y_true, val_y_prob)
        except ValueError:
            val_auc = 0.0

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            best_model_state = model.state_dict()

        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1:03d}, Loss: {total_loss/len(train_dataset):.4f}, Val AUC: {val_auc:.4f}")

    if best_model_state:
        model.load_state_dict(best_model_state)
    
    # Evaluation
    model.eval()
    test_y_true, test_y_prob, test_y_pred = [], [], []
    with torch.no_grad():
        for data in test_loader:
            data = data.to(device)
            out = model(data.x, data.edge_index, data.batch)
            probs = F.softmax(out, dim=1)[:, 1].cpu().numpy()
            preds = out.argmax(dim=1).cpu().numpy()
            test_y_true.extend(data.y.cpu().numpy())
            test_y_prob.extend(probs)
            test_y_pred.extend(preds)

    gat_metrics = compute_metrics(test_y_true, test_y_prob, test_y_pred)
    
    print("\nEvaluating Baselines...")
    baseline_metrics = run_baselines(train_dataset, test_dataset)

    results = {
        "gat": gat_metrics,
        "mlp": baseline_metrics["mlp"],
        "rf": baseline_metrics["rf"]
    }

    print("\n--- Final Evaluation ---")
    for name, metrics in results.items():
        print(f"[{name.upper()}] F1: {metrics['f1']:.4f}, ROC-AUC: {metrics['roc_auc']:.4f}, "
              f"PR-AUC: {metrics['pr_auc']:.4f}, MCC: {metrics['mcc']:.4f}, Brier: {metrics['brier_score']:.4f}")

    # Save model
    out_dir = Path("packages/detectors/weights")
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "driftguardx_gat_model.pth"
    torch.save(best_model_state, model_path)
    
    # Compute checkpoint hash
    with open(model_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    meta = {
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "metrics": results,
        "checkpoint_hash": file_hash,
        "timestamp": time.time()
    }

    with open(out_dir / "training_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nModel saved to {model_path}")
    print(f"Checkpoint Hash: {file_hash}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=0.005)
    args = parser.parse_args()
    
    train_gat(args)
