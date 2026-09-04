import json
import subprocess

with open("data/dataset_registry.json") as f:
    registry = json.load(f)

datasets = [d for d in registry.keys() if d != "scifact"]

providers = ["local-deterministic", "openai-simulated"]
topologies = ["standard", "complex"]

for dataset in datasets:
    splits = registry[dataset]["available_splits"]
    split = "test" if "test" in splits else splits[0]

    for provider in providers:
        for topology in topologies:
            print("\n========================================================")
            print(f"Running benchmark on {dataset} / {split} [{provider} | {topology}]")
            print("========================================================")

            try:
                # We use max-trials 2 for speed
                subprocess.run(
                    [
                        "python", "-m", "apps.cli.run_benchmark",
                        "--dataset", dataset,
                        "--split", split,
                        "--max-trials", "2",
                        "--provider", provider,
                        "--topology", topology
                    ],
                    check=True
                )
            except subprocess.CalledProcessError as e:
                print(f"Failed to run benchmark for {dataset} ({provider}/{topology}): {e}")
