import json
import os

import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = "results/benchmark_runs"
OUTPUT_DIR = "results/plots"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_results(filepath):
    with open(filepath) as f:
        data = json.load(f)
    return data

def plot_benchmark_results(dataset_name, results) -> None:
    faults = list(set([r['fault_type'] for r in results.values()]))
    strategies = list(set([r['strategy'] for r in results.values()]))

    # Plot Accuracy
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(faults))
    width = 0.2

    for i, strategy in enumerate(strategies):
        accs = []
        for fault in faults:
            for r in results.values():
                if r['fault_type'] == fault and r['strategy'] == strategy:
                    accs.append(r['acc_mean'])
                    break
            else:
                accs.append(0)
        ax.bar(x + i*width - width*len(strategies)/2, accs, width, label=strategy)

    ax.set_ylabel('Accuracy (Correct Root Cause)')
    ax.set_title(f'Recovery Accuracy by Strategy ({dataset_name})')
    ax.set_xticks(x)
    ax.set_xticklabels(faults)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{dataset_name}_accuracy.png"))
    plt.close()

    # Plot Cost
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, strategy in enumerate(strategies):
        costs = []
        for fault in faults:
            for r in results.values():
                if r['fault_type'] == fault and r['strategy'] == strategy:
                    costs.append(r['cost_mean'])
                    break
            else:
                costs.append(0)
        ax.bar(x + i*width - width*len(strategies)/2, costs, width, label=strategy)

    ax.set_ylabel('Execution Cost ($)')
    ax.set_title(f'Recovery Cost by Strategy ({dataset_name})')
    ax.set_xticks(x)
    ax.set_xticklabels(faults)
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f"{dataset_name}_cost.png"))
    plt.close()

def main() -> None:
    files = [f for f in os.listdir(RESULTS_DIR) if f.startswith('benchmark_') and f.endswith('.json')]
    for file in files:
        filepath = os.path.join(RESULTS_DIR, file)
        data = parse_results(filepath)
        plot_benchmark_results(data['dataset'] + "_" + data['split'], data['results'])

if __name__ == "__main__":
    main()
