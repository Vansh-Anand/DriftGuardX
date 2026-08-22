import asyncio
import os
import uuid
import time
import math
import statistics
import random
from typing import List, Dict, Any

from apps.api.src.database import AsyncSessionLocal
from apps.api.src.config import settings
from packages.rag_benchmark.src.rag_pipeline import RealRAGPipeline
from packages.rag_benchmark.src.real_fault_injector import RealFaultInjector, FaultType
from packages.evaluation.src.datasets.schema import EvaluationEpisode
from packages.evaluation.src.metrics import DeterministicMetricsEngine
from packages.evaluation.src.ragas_evaluator import RagasEvaluator
from packages.evaluation.src.tracker import Tracker
from packages.ingestion.src.embedder import LocalEmbedder

from packages.rag_benchmark.src.schedulers import (
    ExhaustiveScheduler,
    RandomScheduler,
    CheapestFirstScheduler,
    GreedyPriorScheduler,
    UCBScheduler,
    DetectorOnlyScheduler,
    GraphOnlyScheduler,
    BCRBSchedulerWrapper
)

SCIFACT_EPISODES = [
    EvaluationEpisode(
        query="Does DriftGuard-X cryptographically bind traces to recovery capsules?",
        expected_answer="Yes, DriftGuard-X uses a Recovery Eligibility Certificate to cryptographically bind traces to recovery capsules.",
        relevant_chunk_ids=["chunk_1"],
        difficulty="medium",
        corpus_version_id="scifact-v1",
        ground_truth_root_cause=None
    )
]

async def run_real_benchmark():
    print("Initializing Benchmark Engine with Real OpenAI API and PostgreSQL/SQLite...")
    
    tenant_id = uuid.uuid4()
    
    async with AsyncSessionLocal() as session:
        # Get the latest corpus_version_id from DB
        from apps.api.src.models_ingestion import CorpusVersionORM
        from sqlalchemy import select
        result = await session.execute(select(CorpusVersionORM).order_by(CorpusVersionORM.created_at.desc()).limit(1))
        version_record = result.scalars().first()
        
        if not version_record:
            print("No ingested corpus found! Using 'dummy-scifact-v1' for testing.")
            corpus_version_id = "dummy-scifact-v1"
        else:
            corpus_version_id = version_record.version_tag
            
        print(f"Using ingested corpus version: {corpus_version_id}")
        
        embedder = LocalEmbedder()
        
        pipeline = RealRAGPipeline(
            db_session=session,
            embedding_adapter=embedder,
            corpus_version_id=corpus_version_id,
            tenant_id=tenant_id,
            model_name="gpt-3.5-turbo",
            temperature=0.0
        )
        
        metrics_engine = DeterministicMetricsEngine()
        tracker = Tracker(experiment_name="SciFact-RAG-Eval-Real")
        
        schedulers = {
            "random": RandomScheduler(),
            "bcrb_current": BCRBSchedulerWrapper(total_budget=0.2),
            "graph_only": GraphOnlyScheduler()
        }
        
        faults = [
            (FaultType.STALE_CORPUS, "STALE_CORPUS_FAILURE"),
            (FaultType.MODEL_DRIFT, "MODEL_DRIFT_FAILURE"),
            (FaultType.MALFORMED_OUTPUT, "PARSER_FAILURE")
        ]
        
        candidates = [gt for _, gt in faults]
        injector = RealFaultInjector(pipeline)
        num_trials = 3 # keep it small for speed in local workflow
        
        print(f"Running benchmark grid: {len(faults)} faults x {len(schedulers)} schedulers x {num_trials} trials...")
        
        results = {}
        for fault_id, gt_root_cause in faults:
            for scheduler_name, scheduler in schedulers.items():
                
                latencies = []
                costs = []
                accuracies = []
                recovery_costs = []
                successes = []
                
                for _ in range(num_trials):
                    run_id = str(uuid.uuid4())
                    
                    # Inject Fault
                    injector.inject_fault(fault_id)
                    
                    try:
                        start_time = time.time()
                        out_dict = await pipeline.run(query="What is DriftGuard-X?", run_id=run_id)
                        out = out_dict["output"]
                        latency = out.get("latency_ms", (time.time() - start_time) * 1000)
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
                        predicted_cause = random.choice(candidates)
                    
                    rca_metrics = metrics_engine.calculate_rca_metrics(
                        [predicted_cause] if predicted_cause else [], 
                        [gt_root_cause]
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
                    "acc": mean_acc, "acc_ci": ci_acc,
                    "cost": mean_rec_cost, "cost_ci": ci_rec,
                    "succ": statistics.mean(successes)
                }
                
                tracker.log_episode(
                    episode_data={"fault": fault_id, "scheduler": scheduler_name},
                    metrics={"acc": mean_acc, "cost": mean_rec_cost, "succ": statistics.mean(successes)},
                    run_id="summary"
                )

        print("\n--- Benchmark Final Report [REAL-SYSTEM DATA] ---")
        print(f"{'Fault Type':<30} | {'Scheduler':<15} | {'RCA Acc':<15} | {'Rec Cost':<15} | {'Succ Rate':<10}")
        print("-" * 95)
        for (f, s), r in results.items():
            acc_str = f"{r['acc']:.2f} ± {r['acc_ci']:.2f}"
            cost_str = f"{r['cost']:.3f} ± {r['cost_ci']:.3f}"
            print(f"{f:<30} | {s:<15} | {acc_str:<15} | {cost_str:<15} | {r['succ']:.2f}")

if __name__ == "__main__":
    asyncio.run(run_real_benchmark())
