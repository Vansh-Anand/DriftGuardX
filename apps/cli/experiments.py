import argparse

from packages.evaluation.src.analysis.plotting import (
    generate_bcrb_frontier_plot,
    generate_bound_coverage_plot,
    generate_certificate_latency_plot,
    generate_drift_performance_plot,
    generate_policy_safety_plot,
    generate_rca_precision_plot,
    generate_recovery_gain_plot,
)
from packages.evaluation.src.experiments.configs import ExperimentConfig
from packages.evaluation.src.experiments.orchestrator import ExperimentOrchestrator
from packages.evaluation.src.experiments.tracker import MLflowTracker


def run_experiment(args) -> None:
    config = ExperimentConfig(
        experiment_name=args.name, regime=args.regime, deterministic_seed=args.seed
    )
    tracker = MLflowTracker()
    orchestrator = ExperimentOrchestrator(config, tracker)
    orchestrator.run()
    print(f"Experiment {args.name} completed.")


def generate_plots(args) -> None:
    plots = [
        generate_drift_performance_plot(),
        generate_bcrb_frontier_plot(),
        generate_rca_precision_plot(),
        generate_bound_coverage_plot(),
        generate_recovery_gain_plot(),
        generate_policy_safety_plot(),
        generate_certificate_latency_plot(),
    ]
    print(f"Plots generated: {', '.join(plots)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="DriftGuard-X Experiment Registry CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run an experiment config")
    run_parser.add_argument("--name", type=str, required=True, help="Experiment name")
    run_parser.add_argument(
        "--regime", type=str, default="retrieval-only", help="Evaluation regime"
    )
    run_parser.add_argument("--seed", type=int, default=42, help="Random seed for fault overlays")

    # Plot command
    subparsers.add_parser(
        "plot", help="Generate publication-grade plots from reports"
    )

    args = parser.parse_args()

    if args.command == "run":
        run_experiment(args)
    elif args.command == "plot":
        generate_plots(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
