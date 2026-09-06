import argparse
import json
import os

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier


# Simple heuristic baselines
def latency_error_heuristic(X):
    # E.g. if duration > 2000 or error_count > 0
    preds = (X[:, 0] > 2000) | (X[:, 2] > 0)
    return preds.astype(int)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run classical ML baselines for Trace Anomaly Detection"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/trace_dataset.json",
        help="Path to flattened trace dataset",
    )
    parser.add_argument(
        "--output", type=str, default="data/baseline_results.json", help="Output path for results"
    )
    args = parser.parse_args()

    print("Running GAT Baselines (Task 18)...")

    # We will simulate data loading here if the dataset doesn't exist
    if not os.path.exists(args.dataset):
        print(f"Dataset {args.dataset} not found. Using synthetic data for demonstration.")
        # Features: [max_latency, num_spans, error_count, mean_self_time]
        np.random.seed(42)
        X = np.random.rand(1000, 4)
        X[:, 0] *= 5000  # Latency
        X[:, 1] *= 50  # Num spans
        X[:, 2] = np.random.poisson(0.5, 1000)  # Errors
        X[:, 3] *= 1.0  # Self-time ratio
        y = (X[:, 0] > 3000) | (X[:, 2] > 0)  # Synthetic label logic
        y = y.astype(int)
    else:
        # Load from JSON or CSV
        with open(args.dataset) as f:
            data = json.load(f)
            X = np.array(data["features"])
            y = np.array(data["labels"])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    models = {
        "Logistic Regression": LogisticRegression(max_iter=1000),
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "HistGradientBoosting": HistGradientBoostingClassifier(random_state=42),
        "MLP": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, random_state=42),
    }

    results = {}

    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_train, y_train)
        y_prob = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)

        results[name] = {
            "ROC-AUC": roc_auc_score(y_test, y_prob),
            "PR-AUC": average_precision_score(y_test, y_prob),
            "F1": f1_score(y_test, y_pred),
            "MCC": matthews_corrcoef(y_test, y_pred),
            "Brier Score": brier_score_loss(y_test, y_prob),
        }

    # Evaluate Heuristic Baseline
    print("Evaluating Latency/Error Heuristic...")
    y_pred_heur = latency_error_heuristic(X_test)
    y_prob_heur = y_pred_heur  # It's hard labels
    results["Latency/Error Heuristic"] = {
        "ROC-AUC": roc_auc_score(y_test, y_prob_heur),
        "PR-AUC": average_precision_score(y_test, y_prob_heur),
        "F1": f1_score(y_test, y_pred_heur),
        "MCC": matthews_corrcoef(y_test, y_pred_heur),
        "Brier Score": brier_score_loss(y_test, y_prob_heur),
    }

    print("\n--- Results ---")
    for name, metrics in results.items():
        print(f"{name}:")
        for metric, val in metrics.items():
            print(f"  {metric}: {val:.4f}")
        print()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
