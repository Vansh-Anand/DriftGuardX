"""Legacy mocked-integration benchmark.

Despite the historical filename, this module does not execute real-data or
production replay. New real-data evidence must use ``controlled_replay.py``.
"""

import asyncio
import math
import os
import random
import statistics
import time
import uuid
from typing import Any

from apps.api.src.pipeline.real_rag import RealRAGPipeline
from packages.evaluation.src.datasets.schema import EvaluationEpisode
from packages.evaluation.src.metrics import DeterministicMetricsEngine
from packages.evaluation.src.ragas_evaluator import RagasEvaluator
from packages.evaluation.src.tracker import Tracker
from packages.rag_benchmark.src.fault_models import FaultType
from packages.rag_benchmark.src.real_fault_injector import RealFaultInjector
from packages.rag_benchmark.src.schedulers import (
    BCRBSchedulerWrapper,
    CheapestFirstScheduler,
    DetectorOnlyScheduler,
    ExhaustiveScheduler,
    GraphOnlyScheduler,
    GreedyPriorScheduler,
    RandomScheduler,
    UCBScheduler,
)
from packages.rag_pipeline.src.interfaces import LLMAdapter, RetrieverAdapter

# Synthetic examples; these are not SciFact records.
MOCK_EPISODES = [
    EvaluationEpisode(
        query="Does DriftGuard-X cryptographically bind traces to recovery capsules?",
        expected_answer="Yes, DriftGuard-X uses a Recovery Eligibility Certificate to cryptographically bind traces to recovery capsules.",
        relevant_chunk_ids=["chunk_1"],
        difficulty="medium",
        corpus_version_id="scifact-v1",
        ground_truth_root_cause=None,
    ),
    EvaluationEpisode(
        query="What is the purpose of the ReplayStateManifest?",
        expected_answer="The ReplayStateManifest ensures reproducible execution by capturing all version hashes, seeds, and container digests.",
        relevant_chunk_ids=["chunk_2"],
        difficulty="hard",
        corpus_version_id="scifact-v1",
        ground_truth_root_cause=None,
    ),
]

# Create fake corpus chunks for the Retriever to "find"
MOCK_CORPUS = {
    "chunk_1": "DriftGuard-X cryptographically binds traces to recovery capsules using the Recovery Eligibility Certificate to prevent state-stale execution.",
    "chunk_2": "The ReplayStateManifest is generated during the real run to freeze all dependency versions, prompt hashes, and random seeds for reproducible sandboxing.",
    "chunk_3": "A fallback model is triggered when the primary API provider returns a 500 error.",
}


class MockRetrievedChunk:
    def __init__(self, chunk_id, document_id, score):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.score = score
        self.text_content = ""
        self.metadata = {}


class MockHybridRetriever(RetrieverAdapter):
    def __init__(self):
        self.name = "mock_db"

    async def retrieve(self, query: str, corpus_version_id: str, top_k: int = 5):
        # Extremely simple mock: just return chunk 1 and 2 if words match
        res = []
        if "bind" in query.lower() or "cryptographically" in query.lower():
            res.append(MockRetrievedChunk(chunk_id="chunk_1", document_id="doc_1", score=0.9))
        if "manifest" in query.lower() or "reproducible" in query.lower():
            res.append(MockRetrievedChunk(chunk_id="chunk_2", document_id="doc_2", score=0.95))
        if not res:
            res.append(MockRetrievedChunk(chunk_id="chunk_3", document_id="doc_3", score=0.4))
        return res


class MockLLMAdapter(LLMAdapter):
    def __init__(self, model_name="mock"):
        self.model_name = model_name

    async def generate(self, prompt: str, context: list) -> dict:
        ans = (
            "I DONT KNOW"
            if "ALWAYS RESPOND" in prompt
            else "Yes, DriftGuard-X uses a Recovery Eligibility Certificate"
        )
        return {
            "text": ans,
            "tokens_input": 10,
            "tokens_output": 10,
            "latency_ms": 100,
            "cost_usd": 0.0,
            "model_metadata": {"model": self.model_name, "provider": "mock"},
        }


class LocalArtifactStore:
    def __init__(self, dir_path: str):
        self.dir_path = dir_path

    async def save_trace(self, run_id: str, trace_data: dict[str, Any]) -> None:
        # Mock artifact store
        pass


async def run_mocked_integration_benchmark() -> None:
    print("Initializing Benchmark Engine...")

    # 1. Initialize Pipeline
    import tempfile

    retriever = MockHybridRetriever()
    llm = MockLLMAdapter(model_name="gpt-3.5-turbo-mock")
    artifact_store = LocalArtifactStore(os.path.join(tempfile.gettempdir(), "artifacts"))

    pipeline = RealRAGPipeline(
        retriever=retriever,
        llm=llm,
        prompt_template="Question: {query}",
        artifact_store=artifact_store,
        top_k=2,
    )

    # 2. Initialize Evaluators & Trackers
    metrics_engine = DeterministicMetricsEngine()
    RagasEvaluator()
    tracker = Tracker(experiment_name="SciFact-RAG-Eval-v1")

    # 3. Define Schedulers and Faults
    schedulers = {
        "exhaustive": ExhaustiveScheduler(),
        "random": RandomScheduler(),
        "cheapest_first": CheapestFirstScheduler(),
        "greedy_prior": GreedyPriorScheduler(),
        "ucb": UCBScheduler(),
        "bcrb_current": BCRBSchedulerWrapper(total_budget=0.2),
        "detector_only": DetectorOnlyScheduler(),
        "graph_only": GraphOnlyScheduler(),
    }

    faults = [
        (FaultType.STALE_CORPUS, "STALE_CORPUS_FAILURE"),
        (FaultType.DROPPED_CHUNKS, "RETRIEVAL_FAILURE"),
        (FaultType.EMBEDDING_MISMATCH, "EMBEDDING_MISMATCH_FAILURE"),
        (FaultType.RETRIEVER_TOPK_REGRESSION, "TOPK_REGRESSION_FAILURE"),
        (FaultType.PROMPT_REGRESSION, "PROMPT_HALLUCINATION"),
        (FaultType.MODEL_DRIFT, "MODEL_DRIFT_FAILURE"),
        (FaultType.PROVIDER_TIMEOUT, "TIMEOUT_FAILURE"),
        (FaultType.MALFORMED_OUTPUT, "PARSER_FAILURE"),
        (FaultType.TOOL_SCHEMA_MISMATCH, "TOOL_MISMATCH_FAILURE"),
        (FaultType.POLICY_CHANGE, "POLICY_VIOLATION_FAILURE"),
        (FaultType.MEMORY_CONTAMINATION, "MEMORY_CONTAMINATION_FAILURE"),
        (FaultType.DB_FAILURE, "DB_FAILURE"),
    ]

    candidates = [gt for _, gt in faults]
    injector = RealFaultInjector(pipeline)

    num_trials = 30

    print(
        f"Running benchmark grid: {len(faults)} faults x {len(schedulers)} schedulers x {num_trials} trials..."
    )
    print(
        "EVIDENCE: CONTROLLED SYNTHETIC HARNESS — mocked integrations; "
        "not production or real-system replay evidence."
    )

    results = {}

    for fault_id, gt_root_cause in faults:
        for scheduler_name, scheduler in schedulers.items():

            latencies = []
            costs = []
            accuracies = []
            recovery_costs = []
            successes = []

            for _ in range(num_trials):
                run_id = uuid.uuid4()
                tenant_id = uuid.uuid4()

                # Inject Fault
                injector.inject_fault(fault_id)

                # Execute Pipeline
                try:
                    start_time = time.time()
                    out = await pipeline.execute(
                        query=MOCK_EPISODES[0].query,
                        corpus_version_id=MOCK_EPISODES[0].corpus_version_id,
                        run_id=run_id,
                        tenant_id=tenant_id,
                    )
                    latency = (time.time() - start_time) * 1000
                except Exception as e:
                    out = {"answer": str(e), "chunk_ids": [], "cost_usd": 0, "tokens": {"total": 0}}
                    latency = 0

                history = []
                predicted_cause = None
                total_recovery_cost = 0.0
                replay_success = False

                if scheduler_name not in ["detector_only", "graph_only"]:
                    while True:
                        next_cand = scheduler.select_next(candidates, history)
                        if not next_cand:
                            break

                        history.append({"candidate": next_cand})
                        total_recovery_cost += 0.05

                        if next_cand == gt_root_cause:
                            predicted_cause = next_cand
                            replay_success = True
                            if isinstance(scheduler, BCRBSchedulerWrapper):
                                scheduler.update(next_cand, True, 0.05)
                            elif hasattr(scheduler, "update"):
                                scheduler.update(next_cand, True)
                            break
                        else:
                            if isinstance(scheduler, BCRBSchedulerWrapper):
                                scheduler.update(next_cand, False, 0.05)
                            elif hasattr(scheduler, "update"):
                                scheduler.update(next_cand, False)
                else:
                    predicted_cause = random.choice(candidates)  # Mocking imperfect detection

                rca_metrics = metrics_engine.calculate_rca_metrics(
                    [predicted_cause] if predicted_cause else [], [gt_root_cause]
                )

                injector.reset()

                latencies.append(latency)
                costs.append(out.get("cost_usd", 0.0))
                accuracies.append(rca_metrics["accuracy"])
                recovery_costs.append(total_recovery_cost)
                successes.append(1.0 if replay_success else 0.0)

            mean_acc = statistics.mean(accuracies)
            std_acc = statistics.stdev(accuracies) if num_trials > 1 else 0.0
            ci_acc = 1.96 * (std_acc / math.sqrt(num_trials))

            mean_rec_cost = statistics.mean(recovery_costs)
            std_rec = statistics.stdev(recovery_costs) if num_trials > 1 else 0.0
            ci_rec = 1.96 * (std_rec / math.sqrt(num_trials))

            results[(fault_id, scheduler_name)] = {
                "acc": mean_acc,
                "acc_ci": ci_acc,
                "cost": mean_rec_cost,
                "cost_ci": ci_rec,
                "succ": statistics.mean(successes),
            }

            tracker.log_episode(
                episode_data={"fault": fault_id, "scheduler": scheduler_name},
                metrics={
                    "acc": mean_acc,
                    "cost": mean_rec_cost,
                    "succ": statistics.mean(successes),
                },
                run_id="summary",
            )

    print("\n--- Benchmark Final Report [CONTROLLED SYNTHETIC EVIDENCE] ---")
    print(
        f"{'Fault Type':<30} | {'Scheduler':<15} | {'RCA Acc':<15} | {'Rec Cost':<15} | {'Succ Rate':<10}"
    )
    print("-" * 95)
    for (f, s), r in results.items():
        acc_str = f"{r['acc']:.2f} ± {r['acc_ci']:.2f}"
        cost_str = f"{r['cost']:.3f} ± {r['cost_ci']:.3f}"
        print(f"{f:<30} | {s:<15} | {acc_str:<15} | {cost_str:<15} | {r['succ']:.2f}")


if __name__ == "__main__":
    asyncio.run(run_mocked_integration_benchmark())
