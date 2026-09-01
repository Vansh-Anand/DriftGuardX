"""
DriftGuard-X v2 - Layer-specific Evaluation Report Generator
"""

import json
import os
import random

from packages.detectors.src.calibration import calibrate_detector


def generate_mock_data(
    size: int = 100, rng: random.Random | None = None
) -> tuple[list[int], list[float]]:
    """Generate synthetic predictions and truths for clean controls and injected faults."""
    generator = rng or random.Random(42)  # noqa: S311 - reproducible simulation, not security
    y_true: list[int] = []
    y_score: list[float] = []
    for _ in range(size):
        # Clean control
        if generator.random() > 0.3:
            y_true.append(0)
            y_score.append(generator.uniform(0.0, 0.4))
        # Injected fault
        else:
            y_true.append(1)
            y_score.append(generator.uniform(0.2, 1.0))
    return y_true, y_score


def main() -> None:
    print("Generating Evaluation Reports with Calibration Plots Data...")

    seed = 42
    rng = random.Random(seed)  # noqa: S311 - reproducible simulation, not security
    layers = ["Generation", "Retrieval", "Memory", "Operational", "Policy", "Tool"]
    report = "# DriftGuard-X: Layer-Specific Evaluation Reports\n\n"
    report += "**Evidence kind:** `synthetic_simulation`\n\n"
    report += f"**Deterministic seed:** `{seed}`\n\n"
    report += (
        "This calibration report uses generated clean controls and injected faults. "
        "It is not real-system or production evidence.\n\n"
    )

    layer_artifacts = {}

    for layer in layers:
        y_true, y_score = generate_mock_data(200, rng)
        cal = calibrate_detector(y_true, y_score, target_fpr=0.05)

        report += f"## {layer} Layer\n"
        report += f"- **Optimal Threshold:** `{cal['optimal_threshold']:.3f}`\n"
        report += f"- **F1 Score:** `{cal['f1']:.3f}`\n"
        report += f"- **True Positive Rate (TPR):** `{cal['tpr']:.3f}`\n"
        report += f"- **False Positive Rate (FPR):** `{cal['fpr']:.3f}`\n"
        report += f"- **AUROC:** `{cal['auroc']:.3f}`\n"
        report += f"- **AUPRC:** `{cal['auprc']:.3f}`\n\n"

        layer_artifacts[layer] = cal

    artifacts = {
        "schema_version": "1.0.0",
        "evidence_kind": "synthetic_simulation",
        "seed": seed,
        "sample_count_per_layer": 200,
        "layers": layer_artifacts,
    }

    os.makedirs("reports", exist_ok=True)

    with open("reports/evaluation_report.md", "w") as f:
        f.write(report)

    with open("reports/calibration_artifacts.json", "w") as f:
        json.dump(artifacts, f, indent=2)

    print("Generated reports/evaluation_report.md and reports/calibration_artifacts.json")


if __name__ == "__main__":
    main()
