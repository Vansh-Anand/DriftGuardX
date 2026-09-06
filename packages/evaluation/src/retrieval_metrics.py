import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from packages.evaluation.src.metrics import DeterministicMetricsEngine
from packages.rag_pipeline.src.interfaces import RetrieverAdapter


@dataclass
class RetrievalEvaluationResult:
    recall_at_k: dict[int, float]
    mrr: float
    ndcg_at_k: dict[int, float]
    precision_at_k: dict[int, float]
    latency_p50_ms: float
    latency_p95_ms: float
    total_queries: int
    query_details: list[dict[str, Any]] = field(default_factory=list)


class RetrievalEvaluator:
    """
    Evaluates RetrieverAdapter instances using Information Retrieval (IR) metrics:
    - Recall@K
    - MRR (Mean Reciprocal Rank)
    - nDCG@K (Normalized Discounted Cumulative Gain)
    - Latency (P50, P95)
    """

    def __init__(self, k_values: list[int] | None = None):
        self.k_values = k_values or [1, 3, 5, 10]

    async def evaluate_retriever(
        self,
        retriever: RetrieverAdapter,
        test_dataset: list[dict[str, Any]],
        corpus_version_id: str = "v1",
    ) -> RetrievalEvaluationResult:
        """
        Runs the test dataset through the retriever and calculates IR metrics.
        Each test item should have:
        - "query": str
        - "relevant_chunk_ids": list[str]
        """
        latencies_ms: list[float] = []
        recalls: dict[int, list[float]] = {k: [] for k in self.k_values}
        precisions: dict[int, list[float]] = {k: [] for k in self.k_values}
        ndcgs: dict[int, list[float]] = {k: [] for k in self.k_values}
        mrrs: list[float] = []
        query_details: list[dict[str, Any]] = []

        max_k = max(self.k_values)

        for item in test_dataset:
            query = item["query"]
            relevant_ids = [str(x) for x in item["relevant_chunk_ids"]]

            start_t = time.perf_counter()
            retrieved_chunks = await retriever.retrieve(
                query=query, corpus_version_id=corpus_version_id, top_k=max_k
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            latencies_ms.append(elapsed_ms)

            retrieved_ids = [str(c.chunk_id) for c in retrieved_chunks]

            # Compute MRR
            mrr_val = DeterministicMetricsEngine.calculate_mrr(retrieved_ids, relevant_ids)
            mrrs.append(mrr_val)

            # Compute per-K metrics
            item_recalls = {}
            item_ndcgs = {}
            for k in self.k_values:
                rec_val = DeterministicMetricsEngine.calculate_recall_at_k(
                    retrieved_ids, relevant_ids, k
                )
                prec_val = DeterministicMetricsEngine.calculate_precision_at_k(
                    retrieved_ids, relevant_ids, k
                )
                ndcg_val = DeterministicMetricsEngine.calculate_ndcg_at_k(
                    retrieved_ids, relevant_ids, k
                )

                recalls[k].append(rec_val)
                precisions[k].append(prec_val)
                ndcgs[k].append(ndcg_val)
                item_recalls[k] = rec_val
                item_ndcgs[k] = ndcg_val

            query_details.append(
                {
                    "query": query,
                    "retrieved_ids": retrieved_ids,
                    "relevant_ids": relevant_ids,
                    "mrr": mrr_val,
                    "recall": item_recalls,
                    "ndcg": item_ndcgs,
                    "latency_ms": elapsed_ms,
                }
            )

        avg_recalls = {k: float(np.mean(recalls[k])) if recalls[k] else 0.0 for k in self.k_values}
        avg_precisions = {
            k: float(np.mean(precisions[k])) if precisions[k] else 0.0 for k in self.k_values
        }
        avg_ndcgs = {k: float(np.mean(ndcgs[k])) if ndcgs[k] else 0.0 for k in self.k_values}
        avg_mrr = float(np.mean(mrrs)) if mrrs else 0.0

        p50 = float(np.percentile(latencies_ms, 50)) if latencies_ms else 0.0
        p95 = float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0

        return RetrievalEvaluationResult(
            recall_at_k=avg_recalls,
            mrr=avg_mrr,
            ndcg_at_k=avg_ndcgs,
            precision_at_k=avg_precisions,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            total_queries=len(test_dataset),
            query_details=query_details,
        )
