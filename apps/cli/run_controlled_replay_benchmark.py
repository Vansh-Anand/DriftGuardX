"""CLI for real-data, controlled retrieval replay evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from packages.rag_benchmark.src.controlled_replay import run_controlled_replay, write_evidence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=Path("data/raw/scifact"))
    parser.add_argument("--split", default="test")
    parser.add_argument("--max-queries", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/controlled_replay/scifact_bm25.json"),
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    evidence = run_controlled_replay(
        dataset_root=args.dataset_root,
        repo_root=repo_root,
        split=args.split,
        max_queries=args.max_queries,
        seed=args.seed,
    )
    write_evidence(evidence, args.output)
    print(f"wrote controlled replay evidence to {args.output}")
    print(f"manifest_sha256={evidence['manifest_sha256']}")


if __name__ == "__main__":
    main()
