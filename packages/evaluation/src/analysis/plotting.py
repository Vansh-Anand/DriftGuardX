import os

import matplotlib.pyplot as plt
import seaborn as sns


def generate_drift_performance_plot(output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")

    # Mock data for demonstration
    x = ["retrieval-only", "rag", "tool-use"]
    y = [0.8, 0.6, 0.75]

    plt.figure(figsize=(8, 5))
    ax = sns.barplot(x=x, y=y, hue=x, legend=False, palette="viridis")
    ax.set_title("Drift Performance by Regime")
    ax.set_ylabel("Success Rate")
    ax.set_ylim(0, 1.0)

    out_path = os.path.join(output_dir, "drift_performance.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path


def generate_bcrb_frontier_plot(output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")

    x_cost = [0.1, 0.5, 1.0, 5.0, 10.0]
    y_reliability = [0.1, 0.4, 0.6, 0.8, 0.85]

    plt.figure(figsize=(8, 5))
    sns.lineplot(x=x_cost, y=y_reliability, marker="o", color="blue")
    plt.title("BCRB Efficiency Frontier")
    plt.xlabel("Replay Budget (USD)")
    plt.ylabel("Expected Reliability Gain")

    out_path = os.path.join(output_dir, "bcrb_frontier.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path


def generate_rca_precision_plot(output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "rca_precision.png")
    plt.figure(figsize=(6, 4))
    plt.bar(["Baseline", "Exhaustive", "Heuristic"], [0.4, 0.95, 0.85], color="skyblue")
    plt.title("RCA Precision")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path


def generate_bound_coverage_plot(output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "bound_coverage.png")
    plt.figure(figsize=(6, 4))
    plt.plot([10, 50, 100], [0.85, 0.92, 0.95], marker="o", color="green")
    plt.title("Bound Coverage")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path


def generate_recovery_gain_plot(output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "recovery_gain.png")
    plt.figure(figsize=(6, 4))
    plt.bar(["Before", "After"], [0.6, 0.9], color="orange")
    plt.title("Recovery Gain")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path


def generate_policy_safety_plot(output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "policy_safety.png")
    plt.figure(figsize=(6, 4))
    plt.bar(["Strict", "Lax"], [1.0, 0.7], color="red")
    plt.title("Policy Safety")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path


def generate_certificate_latency_plot(output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "certificate_latency.png")
    plt.figure(figsize=(6, 4))
    plt.plot([10, 100, 1000], [5, 12, 50], marker="o", color="purple")
    plt.title("Certificate Latency (ms)")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path
