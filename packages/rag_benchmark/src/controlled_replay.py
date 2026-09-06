"""Offline controlled-replay benchmark over an immutable public dataset snapshot.

This module deliberately contains no mock-data fallback.  It executes a real
BM25 retrieval workload over the locally materialized BEIR SciFact corpus,
injects a controlled index-integrity fault, and evaluates recovery candidates
by re-running retrieval.  The resulting evidence is ``controlled_replay``;
it is never presented as production-canary evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from packages.contracts.src.evidence import EvidenceClassification
from packages.evaluation.src.bandit_baselines import CandidateArm
from packages.replay.src.bandit import ResourceAdmittedBCRBController

_TOKEN = re.compile(r"[a-z0-9]+")
_CANDIDATES = (
    "increase_top_k",
    "normalize_query",
    "recompute_idf",
    "restore_index_snapshot",
)


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True)
class DatasetSnapshot:
    root: Path
    split: str
    documents: dict[str, str]
    queries: dict[str, str]
    qrels: dict[str, set[str]]
    file_digests: dict[str, str]


def load_dataset_snapshot(root: Path, split: str, dataset_name: str) -> DatasetSnapshot:
    """Load and hash a dataset snapshot, failing closed on missing/malformed data."""
    corpus_path = root / "corpus.jsonl"
    queries_path = root / "queries.jsonl"
    qrels_path = root / "qrels" / f"{split}.tsv"
    required = (corpus_path, queries_path, qrels_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"controlled replay requires a materialized {dataset_name} snapshot; missing: "
            + ", ".join(missing)
        )

    documents: dict[str, str] = {}
    with corpus_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            doc_id = str(record.get("_id", ""))
            if not doc_id:
                raise ValueError(f"corpus record {line_number} has no _id")
            documents[doc_id] = f"{record.get('title', '')} {record.get('text', '')}".strip()

    queries: dict[str, str] = {}
    with queries_path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            query_id = str(record.get("_id", ""))
            if not query_id:
                raise ValueError(f"query record {line_number} has no _id")
            queries[query_id] = str(record.get("text", ""))

    qrels: dict[str, set[str]] = defaultdict(set)
    with qrels_path.open(encoding="utf-8") as stream:
        header = stream.readline().strip().split("\t")
        if header[:3] != ["query-id", "corpus-id", "score"]:
            raise ValueError(f"unexpected qrels header in {qrels_path}")
        for line_number, line in enumerate(stream, start=2):
            row = line.rstrip("\n").split("\t")
            if len(row) < 3:
                raise ValueError(f"malformed qrels row {line_number}")
            if int(row[2]) > 0:
                qrels[row[0]].add(row[1])

    valid = {
        query_id: relevant & documents.keys()
        for query_id, relevant in qrels.items()
        if query_id in queries and relevant & documents.keys()
    }
    if not documents or not queries or not valid:
        raise ValueError(f"{dataset_name} snapshot contains no usable documents, queries, or qrels")

    return DatasetSnapshot(
        root=root,
        split=split,
        documents=documents,
        queries=queries,
        qrels={query_id: set(doc_ids) for query_id, doc_ids in valid.items()},
        file_digests={
            str(path.relative_to(root)).replace("\\", "/"): _file_digest(path) for path in required
        },
    )


class BM25Index:
    """Small deterministic BM25 implementation with an inverted index."""

    def __init__(self, documents: dict[str, str], k1: float = 1.5, b: float = 0.75) -> None:
        if not documents:
            raise ValueError("documents must not be empty")
        self._k1 = k1
        self._b = b
        self._document_count = len(documents)
        self._lengths: dict[str, int] = {}
        postings: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for doc_id, text in documents.items():
            counts = Counter(_tokens(text))
            self._lengths[doc_id] = sum(counts.values())
            for token, frequency in counts.items():
                postings[token].append((doc_id, frequency))
        self._postings = dict(postings)
        self._average_length = sum(self._lengths.values()) / self._document_count

    def search(
        self, query: str, top_k: int = 10, excluded_document_ids: set[str] | None = None, idf_override: dict[str, float] | None = None
    ) -> list[str]:
        if top_k <= 0:
            return []
        excluded = excluded_document_ids or set()
        scores: dict[str, float] = defaultdict(float)
        for token in set(_tokens(query)):
            postings = self._postings.get(token, [])
            if not postings:
                continue
            document_frequency = len(postings)
            if idf_override and token in idf_override:
                inverse_document_frequency = idf_override[token]
            else:
                inverse_document_frequency = math.log(
                    1.0 + (self._document_count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
            for doc_id, term_frequency in postings:
                if doc_id in excluded:
                    continue
                normalized_length = self._lengths[doc_id] / max(self._average_length, 1.0)
                denominator = term_frequency + self._k1 * (
                    1.0 - self._b + self._b * normalized_length
                )
                scores[doc_id] += inverse_document_frequency * (
                    term_frequency * (self._k1 + 1.0) / denominator
                )
        return [
            doc_id
            for doc_id, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        ]


def _recall(retrieved: list[str], relevant: set[str]) -> float:
    return len(set(retrieved) & relevant) / len(relevant)


def _git_state(repo_root: Path) -> dict[str, Any]:
    try:
        git = shutil.which("git")
        if git is None:
            return {"commit": None, "dirty": None}
        commit = subprocess.run(  # - resolved executable and fixed arguments
            [git, "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(  # - resolved executable and fixed arguments
                [git, "status", "--porcelain"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        tracked_diff = subprocess.run(  # - resolved executable and fixed arguments
            [git, "diff", "--binary", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
        implementation_paths = (
            "apps/cli/run_controlled_replay_benchmark.py",
            "packages/contracts/src/evidence.py",
            "packages/evaluation/src/bandit_baselines.py",
            "packages/rag_benchmark/src/controlled_replay.py",
            "packages/replay/src/bandit.py",
            "scripts/download_beir.py",
        )
        implementation_hashes = {
            relative_path: _file_digest(repo_root / relative_path)
            for relative_path in implementation_paths
            if (repo_root / relative_path).is_file()
        }
        return {
            "commit": commit,
            "dirty": dirty,
            "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
            "implementation_file_sha256": implementation_hashes,
        }
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _candidate_order(strategy: str, seed: int) -> list[str]:
    if strategy == "fixed_order":
        return list(_CANDIDATES)
    if strategy == "random":
        candidates = list(_CANDIDATES)
        random.Random(seed).shuffle(candidates)  # noqa: S311 - benchmark sampling
        return candidates
    if strategy == "bcrb_integrity_prior":
        controller = ResourceAdmittedBCRBController(
            total_budget=10.0, exploration_constant=0.0, rollback_reserve_ratio=0.0
        )
        remaining = list(_CANDIDATES)
        ordered: list[str] = []
        while remaining:
            arms = [
                CandidateArm(
                    arm_id=candidate,
                    cost=1.0,
                    prior=0.9 if candidate == "restore_index_snapshot" else 0.1,
                )
                for candidate in remaining
            ]
            selected = controller.select_arm(arms)
            if selected is None:
                break
            ordered.append(selected)
            remaining.remove(selected)
            controller.update(selected, reward=0.0, cost=1.0)
        return ordered
    raise ValueError(f"unsupported strategy: {strategy}")


def _paired_statistics(
    treatment: list[float], baseline: list[float], seed: int, samples: int = 10_000
) -> dict[str, float | int]:
    """Deterministic paired bootstrap CI and sign-randomization p-value."""
    if len(treatment) != len(baseline) or not treatment:
        raise ValueError("paired statistics require non-empty, equally sized samples")
    differences = [left - right for left, right in zip(treatment, baseline, strict=True)]
    rng = random.Random(seed)  # noqa: S311 - deterministic statistical resampling
    bootstrapped = []
    sample_count = len(differences)
    for _ in range(samples):
        bootstrapped.append(
            sum(differences[rng.randrange(sample_count)] for _ in range(sample_count))
            / sample_count
        )
    bootstrapped.sort()
    lower = bootstrapped[int(0.025 * (samples - 1))]
    upper = bootstrapped[int(0.975 * (samples - 1))]

    observed = abs(sum(differences) / sample_count)
    extreme = 0
    for _ in range(samples):
        permuted = abs(
            sum(value if rng.random() >= 0.5 else -value for value in differences) / sample_count
        )
        if permuted >= observed:
            extreme += 1

    return {
        "n_pairs": sample_count,
        "mean_delta": sum(differences) / sample_count,
        "paired_bootstrap_ci95_low": lower,
        "paired_bootstrap_ci95_high": upper,
        "paired_randomization_p_value": (extreme + 1) / (samples + 1),
        "treatment_better_rate": sum(value < 0 for value in differences) / sample_count,
        "resamples": samples,
    }


def run_controlled_replay(
    dataset_root: Path,
    repo_root: Path,
    dataset_name: str = "scifact",
    split: str = "test",
    max_queries: int = 50,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute and return hash-bound real-dataset controlled replay evidence."""
    if max_queries <= 0:
        raise ValueError("max_queries must be positive")
    snapshot = load_dataset_snapshot(dataset_root, split, dataset_name)
    index = BM25Index(snapshot.documents)
    query_ids = sorted(snapshot.qrels)
    random.Random(seed).shuffle(query_ids)  # noqa: S311 - benchmark sampling

    strategies = ("bcrb_integrity_prior", "fixed_order", "random")
    trials: list[dict[str, Any]] = []
    evaluated_queries = 0
    
    fault_families = [
        ("relevant_document_tombstone", "index_snapshot_digest_changed", "restore_index_snapshot"),
        ("low_recall_cutoff", "backend_truncation_bug", "increase_top_k"),
        ("malformed_query", "payload_corruption", "normalize_query"),
        ("stale_idf", "corpus_drift", "recompute_idf"),
    ]

    for query_id in query_ids:
        query = snapshot.queries[query_id]
        relevant = snapshot.qrels[query_id]
        clean = index.search(query, top_k=10)
        clean_recall = _recall(clean, relevant)
        if clean_recall <= 0.0:
            continue
            
        generated_trials = 0
        for fault_name, fault_sig, ground_truth in fault_families:
            faulted_query = query
            faulted_top_k = 10
            faulted_excluded = set()
            faulted_idf_override = None

            if fault_name == "relevant_document_tombstone":
                faulted_excluded = relevant
            elif fault_name == "low_recall_cutoff":
                faulted_top_k = 1
            elif fault_name == "malformed_query":
                # Scramble to break tokenization/matching
                faulted_query = query[::-1] 
            elif fault_name == "stale_idf":
                faulted_idf_override = {t: 0.0001 for t in _tokens(query)}

            faulted = index.search(
                faulted_query, 
                top_k=faulted_top_k, 
                excluded_document_ids=faulted_excluded, 
                idf_override=faulted_idf_override
            )
            faulted_recall = _recall(faulted, relevant)
            if faulted_recall >= clean_recall:
                continue  # Fault didn't cause a regression

            query_seed = int(hashlib.sha256(f"{query_id}-{fault_name}".encode("utf-8")).hexdigest()[:16], 16)
            for strategy in strategies:
                attempts: list[dict[str, Any]] = []
                recovered = False
                for candidate in _candidate_order(strategy, seed ^ query_seed):
                    started = time.perf_counter_ns()
                    
                    replay_query = query if candidate == "normalize_query" else faulted_query
                    replay_top_k = 50 if candidate == "increase_top_k" else faulted_top_k
                    replay_excluded = set() if candidate == "restore_index_snapshot" else faulted_excluded
                    replay_idf = None if candidate == "recompute_idf" else faulted_idf_override
                    
                    replayed = index.search(
                        replay_query, 
                        top_k=replay_top_k, 
                        excluded_document_ids=replay_excluded,
                        idf_override=replay_idf
                    )
                    elapsed_ns = time.perf_counter_ns() - started
                    replay_recall = _recall(replayed, relevant)
                    recovered = replay_recall >= clean_recall and replay_recall > faulted_recall
                    attempts.append(
                        {
                            "candidate": candidate,
                            "elapsed_ns": elapsed_ns,
                            "retrieved_ids": replayed,
                            "recall": replay_recall,
                            "mitigation_observed": recovered,
                        }
                    )
                    if recovered:
                        break

                trial = {
                    "query_id": query_id,
                    "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                    "strategy": strategy,
                    "fault": fault_name,
                    "fault_signature": fault_sig,
                    "ground_truth_intervention": ground_truth,
                    "clean_recall_at_10": clean_recall,
                    "faulted_recall_at_10": faulted_recall,
                    "recovered": recovered,
                    "replays_executed": len(attempts),
                    "elapsed_ns": sum(int(attempt["elapsed_ns"]) for attempt in attempts),
                    "attempts": attempts,
                }
                trial["evidence_sha256"] = _canonical_digest(trial)
                trials.append(trial)
                generated_trials += 1

        if generated_trials > 0:
            evaluated_queries += 1
            if evaluated_queries >= max_queries:
                break

    if evaluated_queries == 0:
        raise RuntimeError(f"no {dataset_name} query was recoverable by the clean BM25 baseline and regressed by any fault")

    aggregates: dict[str, dict[str, float | int]] = {}
    for strategy in strategies:
        strategy_trials = [trial for trial in trials if trial["strategy"] == strategy]
        aggregates[strategy] = {
            "n": len(strategy_trials),
            "recovery_rate": sum(bool(trial["recovered"]) for trial in strategy_trials)
            / len(strategy_trials),
            "mean_replays": sum(int(trial["replays_executed"]) for trial in strategy_trials)
            / len(strategy_trials),
            "mean_elapsed_ms": sum(int(trial["elapsed_ns"]) for trial in strategy_trials)
            / len(strategy_trials)
            / 1_000_000,
        }

    trials_by_strategy = {
        strategy: [trial for trial in trials if trial["strategy"] == strategy]
        for strategy in strategies
    }
    comparisons = {}
    for baseline in ("fixed_order", "random"):
        comparisons[f"bcrb_integrity_prior_vs_{baseline}"] = {
            "metric": "replays_executed",
            "direction": "lower_is_better",
            **_paired_statistics(
                [
                    float(trial["replays_executed"])
                    for trial in trials_by_strategy["bcrb_integrity_prior"]
                ],
                [float(trial["replays_executed"]) for trial in trials_by_strategy[baseline]],
                seed=seed ^ int(hashlib.sha256(baseline.encode()).hexdigest()[:16], 16),
            ),
        }

    evidence: dict[str, Any] = {
        "schema_version": "1.0.0",
        "evidence_class": EvidenceClassification.REAL_CONTROLLED_EXPERIMENT.value,
        "evidence_notice": (
            f"Real public {dataset_name} records and real local BM25 executions with a controlled "
            "index fault. This is not production traffic, a production canary, a safety "
            "certification, or proof of patentability."
        ),
        "limitations": [
            "The experiment covers retrieval and index-integrity recovery, not a full LLM or agent stack.",
            f"{dataset_name} qrels define both evaluation relevance and the controlled tombstone fault.",
            "The index-digest fault signature supplies the BCRB intervention prior.",
            "Results do not establish superiority for other fault families or workloads.",
            "Elapsed time is host-specific observational telemetry; replay counts are the primary metric.",
        ],
        "dataset": {
            "name": f"BEIR/{dataset_name}",
            "split": split,
            "source_url": f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset_name}.zip",
            "document_count": len(snapshot.documents),
            "query_count": len(snapshot.queries),
            "evaluated_query_count": evaluated_queries,
            "file_sha256": snapshot.file_digests,
        },
        "experiment": {
            "seed": seed,
            "retriever": "deterministic_bm25",
            "top_k": 10,
            "fault": "relevant_document_tombstone",
            "strategies": list(strategies),
            "statistics": {
                "paired_bootstrap_resamples": 10_000,
                "paired_randomization_resamples": 10_000,
                "confidence_level": 0.95,
            },
        },
        "source": _git_state(repo_root),
        "aggregates": aggregates,
        "statistical_comparisons": comparisons,
        "trials": trials,
    }
    evidence["manifest_sha256"] = _canonical_digest(evidence)
    return evidence


def write_evidence(evidence: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
