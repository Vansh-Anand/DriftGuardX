"""CLI for real-data, controlled retrieval replay evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.rag_benchmark.src.controlled_replay import run_controlled_replay, write_evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="scifact", help="BEIR dataset canonical name")
    parser.add_argument("--dataset-root", type=Path, default=None, help="Override root path for dataset")
    parser.add_argument("--split", default="test")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output JSON path",
    )
    args = parser.parse_args()

    dataset_root = args.dataset_root or Path("data/raw") / args.dataset
    output_path = args.output or Path(f"results/controlled_replay/{args.dataset}_bm25.json")

    repo_root = Path(__file__).resolve().parents[2]
    evidence = run_controlled_replay(
        dataset_root=dataset_root,
        repo_root=repo_root,
        dataset_name=args.dataset,
        split=args.split,
        max_queries=args.max_queries,
        seed=args.seed,
    )
    write_evidence(evidence, output_path)
    print(f"wrote controlled replay evidence to {output_path}")
    print(f"manifest_sha256={evidence['manifest_sha256']}")


if __name__ == "__main__":
    main()
