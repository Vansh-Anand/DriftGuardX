import json
from pathlib import Path

import pytest

from packages.rag_benchmark.src.controlled_replay import (
    BM25Index,
    load_scifact_snapshot,
    run_controlled_replay,
)


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

    assert evidence["evidence_kind"] == "controlled_replay"
    assert evidence["dataset"]["evaluated_query_count"] == 1
    assert len(evidence["manifest_sha256"]) == 64
    assert all(len(trial["evidence_sha256"]) == 64 for trial in evidence["trials"])
    assert evidence["aggregates"]["bcrb_integrity_prior"]["recovery_rate"] == 1.0
    assert evidence["aggregates"]["bcrb_integrity_prior"]["mean_replays"] == 1.0
    comparison = evidence["statistical_comparisons"]["bcrb_integrity_prior_vs_fixed_order"]
    assert comparison["n_pairs"] == 1
    assert comparison["mean_delta"] == -3.0
