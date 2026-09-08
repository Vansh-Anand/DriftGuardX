"""Verify internal evidence integrity and summarize declared controlled experiments.

Hashes detect changed records, not false measurements or a malicious author who
recomputes the hashes. This tool does not verify production safety or patentability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def verify_evidence(data: dict[str, Any], require_clean: bool = False) -> dict[str, Any]:
    expected_priors = {
        "bcrb_uniform_prior": "no_ground_truth",
        "bcrb_oracle_prior": "injected_ground_truth",
        "bcrb_wrong_prior": "deliberately_incorrect_ground_truth",
        "fixed_order": "no_ground_truth",
        "random": "no_ground_truth",
    }
    if data["schema_version"] != "2.0.0" or data["evidence_class"] != "REAL_CONTROLLED_EXPERIMENT":
        raise ValueError("Expected schema 2.0.0 controlled evidence")
    payload = {k: v for k, v in data.items() if k != "manifest_sha256"}
    if digest(payload) != data["manifest_sha256"]:
        raise ValueError("Manifest digest mismatch")
    if require_clean and data["source"].get("dirty") is not False:
        raise ValueError("Clean source provenance required")
    if set(data["aggregates"]) != set(expected_priors):
        raise ValueError("Missing required prior ablations")

    reference_pairs = None
    for strategy, prior_source in expected_priors.items():
        trials = [t for t in data["trials"] if t["strategy"] == strategy]
        pairs = {(t["query_id"], t["fault"]) for t in trials}
        if not trials or len(pairs) != len(trials):
            raise ValueError("Missing or duplicate trial pairs")
        if reference_pairs is not None and pairs != reference_pairs:
            raise ValueError("Unpaired strategy comparison")
        reference_pairs = pairs
        for trial in trials:
            body = {k: v for k, v in trial.items() if k != "evidence_sha256"}
            if digest(body) != trial["evidence_sha256"]:
                raise ValueError("Trial digest mismatch")
            if trial["prior_source"] != prior_source:
                raise ValueError("Mislabelled scheduler prior")
            if trial["replays_executed"] != len(trial["attempts"]):
                raise ValueError("Replay count mismatch")
        aggregate = data["aggregates"][strategy]
        mean_replays = sum(t["replays_executed"] for t in trials) / len(trials)
        recovery_rate = sum(bool(t["recovered"]) for t in trials) / len(trials)
        if aggregate["n"] != len(trials) or not math.isclose(
            aggregate["mean_replays"], mean_replays
        ):
            raise ValueError("Aggregate count mismatch")
        if not math.isclose(aggregate["recovery_rate"], recovery_rate):
            raise ValueError("Aggregate recovery mismatch")
    if any(t["strategy"] not in expected_priors for t in data["trials"]):
        raise ValueError("Unknown trial strategy")
    queries = {q for q, _ in reference_pairs or []}
    if len(queries) != data["dataset"]["evaluated_query_count"]:
        raise ValueError("Query count mismatch")
    for comparison in data["statistical_comparisons"].values():
        if (
            comparison["n_pairs"] != len(queries)
            or comparison["sampling_unit"] != "query_mean_across_regressing_faults"
        ):
            raise ValueError("Incorrect statistical sampling unit")
    return {
        "manifest_sha256": data["manifest_sha256"],
        "evidence_class": data["evidence_class"],
        "seed": data["experiment"]["seed"],
        "dataset": data["dataset"],
        "source": data["source"],
        "fault_pair_counts": dict(Counter(f for _, f in reference_pairs or [])),
        "aggregates": data["aggregates"],
        "statistical_comparisons": data["statistical_comparisons"],
        "limitations": data["limitations"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = []
    for path in args.paths:
        raw = path.read_bytes()
        records.append(
            {
                "path": path.as_posix(),
                "file_sha256": hashlib.sha256(raw).hexdigest(),
                **verify_evidence(json.loads(raw), require_clean=args.require_clean),
            }
        )
    result = {
        "verification": "internal_hash_and_protocol_consistency_only",
        "experiments": records,
    }
    rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(f"Verified {len(records)} controlled evidence file(s)")


if __name__ == "__main__":
    main()
