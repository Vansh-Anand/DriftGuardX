import argparse
import json
import statistics
from scipy import stats
import numpy as np

def load_results(results_path: str):
    # Mock loader for demonstration
    pass

def bootstrap_ci(data, num_samples=1000, alpha=0.05):
    """Compute bootstrap confidence interval for the mean."""
    n = len(data)
    if n == 0:
        return (0.0, 0.0)
    means = np.zeros(num_samples)
    for i in range(num_samples):
        sample = np.random.choice(data, size=n, replace=True)
        means[i] = np.mean(sample)
    lower = np.percentile(means, 100 * (alpha / 2))
    upper = np.percentile(means, 100 * (1 - alpha / 2))
    return lower, upper


def run_statistical_tests(bcrb_accs, baseline_accs):
    """Run paired t-test and Wilcoxon signed-rank test."""
    if not bcrb_accs or not baseline_accs or len(bcrb_accs) != len(baseline_accs):
        return {}
    
    t_stat, p_val_t = stats.ttest_rel(bcrb_accs, baseline_accs)
    
    try:
        w_stat, p_val_w = stats.wilcoxon(bcrb_accs, baseline_accs)
    except ValueError:
        w_stat, p_val_w = 0.0, 1.0  # zero differences
        
    return {
        "paired_t_pvalue": p_val_t,
        "wilcoxon_pvalue": p_val_w
    }


def evaluate(args):
    # Dummy data for demonstration of the statistical harness
    # In a real run, this would be loaded from experiment artifacts.
    np.random.seed(args.seed)
    n_trials = args.trials
    
    # BCRB performs better on average
    bcrb_accuracies = np.clip(np.random.normal(0.85, 0.1, n_trials), 0, 1)
    random_accuracies = np.clip(np.random.normal(0.50, 0.2, n_trials), 0, 1)
    detector_accuracies = np.clip(np.random.normal(0.70, 0.15, n_trials), 0, 1)
    
    models = {
        "BCRB": bcrb_accuracies,
        "Random": random_accuracies,
        "Detector-Only": detector_accuracies
    }
    
    print(f"--- Statistical Evaluation ({n_trials} trials, Seed={args.seed}) ---")
    
    for name, accs in models.items():
        mean_acc = np.mean(accs)
        lower, upper = bootstrap_ci(accs)
        print(f"[{name}] Mean Accuracy: {mean_acc:.4f} (95% CI: [{lower:.4f}, {upper:.4f}])")
        
    print("\n--- Significance Testing vs BCRB ---")
    for name, accs in models.items():
        if name == "BCRB":
            continue
        res = run_statistical_tests(bcrb_accuracies, accs)
        print(f"BCRB vs {name}: Paired t-test p={res['paired_t_pvalue']:.4e}, Wilcoxon p={res['wilcoxon_pvalue']:.4e}")
        
    # Generate report
    report = {
        "trials": n_trials,
        "seed": args.seed,
        "models": {}
    }
    for name, accs in models.items():
        report["models"][name] = {
            "mean": float(np.mean(accs)),
            "std": float(np.std(accs)),
            "ci_95": [float(v) for v in bootstrap_ci(accs)]
        }
    
    with open("statistical_report.json", "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    evaluate(args)
