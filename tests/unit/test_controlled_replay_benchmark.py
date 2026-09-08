import json
from copy import deepcopy
from pathlib import Path

import pytest

from packages.rag_benchmark.src.controlled_replay import (
    BM25Index,
    _candidate_order,
    load_scifact_snapshot,
    run_controlled_replay,
)
from scripts.verify_controlled_evidence import digest, verify_evidence


def _write_snapshot(root: Path) -> None:
    (root / "qrels").mkdir(parents=True)
    (root / "corpus.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"_id": "d1", "title": "Alpha", "text": "alpha treatment works"}),
                json.dumps({"_id": "d2", "title": "Beta", "text": "beta control study"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "queries.jsonl").write_text(
        json.dumps({"_id": "1", "text": "alpha treatment"}) + "\n", encoding="utf-8"
    )
    (root / "qrels" / "test.tsv").write_text(
        "query-id\tcorpus-id\tscore\n1\td1\t1\n", encoding="utf-8"
    )


def test_bm25_returns_relevant_document_deterministically() -> None:
    index = BM25Index({"d1": "alpha treatment works", "d2": "beta control"})

    assert index.search("alpha treatment", top_k=1) == ["d1"]
    assert index.search("alpha treatment", top_k=1, excluded_document_ids={"d1"}) == []


def test_snapshot_loader_has_no_mock_fallback(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="materialized SciFact snapshot"):
        load_scifact_snapshot(tmp_path, "test")


def test_controlled_replay_is_hash_bound_and_provenance_labeled(tmp_path: Path) -> None:
    dataset_root = tmp_path / "scifact"
    _write_snapshot(dataset_root)

    evidence = run_controlled_replay(
        dataset_root=dataset_root,
        repo_root=tmp_path,
        max_queries=1,
        seed=7,
    )

    assert evidence["evidence_class"] == "REAL_CONTROLLED_EXPERIMENT"
    assert evidence["dataset"]["evaluated_query_count"] == 1
    assert len(evidence["manifest_sha256"]) == 64
    assert all(len(trial["evidence_sha256"]) == 64 for trial in evidence["trials"])
    assert evidence["aggregates"]["bcrb_oracle_prior"]["recovery_rate"] == 1.0
    assert evidence["aggregates"]["bcrb_oracle_prior"]["mean_replays"] == 1.0
    comparison = evidence["statistical_comparisons"]["bcrb_oracle_prior_vs_fixed_order"]
    assert comparison["n_pairs"] == 1
    assert comparison["mean_delta"] == -2.0
    assert verify_evidence(evidence)["seed"] == 7
    changed = deepcopy(evidence)
    changed["trials"][0]["replays_executed"] += 1
    with pytest.raises(ValueError, match="Manifest digest mismatch"):
        verify_evidence(changed)
    changed["manifest_sha256"] = digest(
        {k: v for k, v in changed.items() if k != "manifest_sha256"}
    )
    with pytest.raises(ValueError, match="Trial digest mismatch"):
        verify_evidence(changed)
    assert comparison["sampling_unit"] == "query_mean_across_regressing_faults"
    assert len(evidence["experiment"]["fault_families"]) == 4
    assert evidence["schema_version"] == "2.0.0"
    for trial in evidence["trials"]:
        if trial["strategy"] == "bcrb_oracle_prior":
            assert trial["prior_source"] == "injected_ground_truth"
        if trial["strategy"] == "bcrb_uniform_prior":
            assert trial["prior_source"] == "no_ground_truth"


def test_uniform_scheduler_cannot_use_ground_truth_label() -> None:
    expected = _candidate_order("bcrb_uniform_prior", 42)
    for label in expected:
        assert _candidate_order("bcrb_uniform_prior", 42, label) == expected
        assert _candidate_order("bcrb_oracle_prior", 42, label)[0] == label
        assert _candidate_order("bcrb_wrong_prior", 42, label)[0] != label


def test_oracle_scheduler_requires_explicit_label() -> None:
    with pytest.raises(ValueError, match="known intervention"):
        _candidate_order("bcrb_oracle_prior", 42)
