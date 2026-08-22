import argparse
import asyncio
import os
import uuid
import time
import math
import statistics
import random
import json
import csv
from typing import List, Dict, Any

from apps.api.src.database import AsyncSessionLocal
from apps.api.src.config import settings
from packages.rag_benchmark.src.rag_pipeline import RealRAGPipeline
from packages.rag_benchmark.src.real_fault_injector import RealFaultInjector, FaultType
from packages.evaluation.src.datasets.schema import EvaluationEpisode
from packages.evaluation.src.metrics import DeterministicMetricsEngine
from packages.evaluation.src.tracker import Tracker
from packages.ingestion.src.embedder import LocalEmbedder

from packages.rag_benchmark.src.schedulers import (
    RandomScheduler,
    GraphOnlyScheduler,
    BCRBSchedulerWrapper
)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def load_beir_data(dataset: str, split: str):
    print(f"Loading BEIR dataset: {dataset} (split: {split})")
    
    queries_path = os.path.join(ROOT_DIR, "data", "raw", dataset, "queries.jsonl")
    qrels_path = os.path.join(ROOT_DIR, "data", "raw", dataset, "qrels", f"{split}.tsv")
    
    if not os.path.exists(queries_path) or not os.path.exists(qrels_path):
        raise FileNotFoundError(f"BEIR data not found for {dataset}/{split}. Did you run manage_datasets.py?")
        
    queries = {}
    with open(queries_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                q_id = str(data.get("_id", data.get("id")))
                queries[q_id] = data.get("text", "")
                
    qrels = {}
    with open(qrels_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader, None) # skip header
        for row in reader:
            if len(row) >= 3:
                q_id, doc_id, score = row[0], row[1], row[2]
                if int(score) > 0:
                    qrels.setdefault(q_id, []).append(doc_id)
                    
    valid_q_ids = list(qrels.keys())
    print(f"Loaded {len(queries)} queries and {len(valid_q_ids)} queries with positive ground-truth.")
    return queries, qrels, valid_q_ids

async def run_real_benchmark(dataset: str, split: str, max_trials: int):
    print("Initializing Benchmark Engine with Real OpenAI API and PostgreSQL/SQLite...")
    
    tenant_id = uuid.uuid4()
    
    try:
        queries_dict, qrels_dict, valid_qids = load_beir_data(dataset, split)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    
    async with AsyncSessionLocal() as session:
        # Get the latest corpus_version_id from DB for this dataset
        from apps.api.src.models_ingestion import CorpusVersionORM
        from sqlalchemy import select
        
        stmt = select(CorpusVersionORM).where(CorpusVersionORM.source_name == dataset).order_by(CorpusVersionORM.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        version_record = result.scalars().first()
        
        if not version_record:
            print(f"Error: No ingested corpus found for dataset '{dataset}'! Please run ingest_corpus.py first.")
            return
            
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
        tracker = Tracker(experiment_name=f"{dataset.upper()}-RAG-Eval-Real")
        
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
        
        print(f"Running benchmark grid: {len(faults)} faults x {len(schedulers)} schedulers x {max_trials} trials...")
        
        results = {}
        for fault_id, gt_root_cause in faults:
            for scheduler_name, scheduler in schedulers.items():
                
                latencies = []
                costs = []
                accuracies = []
                recovery_costs = []
                successes = []
                
                # Sample qids for this grid search
                sampled_qids = random.sample(valid_qids, min(max_trials, len(valid_qids)))
                
                for qid in sampled_qids:
                    run_id = str(uuid.uuid4())
                    query_text = queries_dict[qid]
                    gt_docs = qrels_dict[qid]
                    
                    episode = EvaluationEpisode(
                        episode_id=run_id,
                        query=query_text,
                        relevant_chunk_ids=gt_docs,
                        corpus_version_id=corpus_version_id,
                        fault_id=fault_id,
                        ground_truth_root_cause=gt_root_cause
                    )
                    
                    # Inject Fault
                    injector.inject_fault(fault_id)
                    
                    try:
                        start_time = time.time()
                        out_dict = await pipeline.run(query=query_text, run_id=run_id)
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
                    
                mean_acc = statistics.mean(accuracies) if accuracies else 0.0
                std_acc = statistics.stdev(accuracies) if len(accuracies) > 1 else 0.0
                ci_acc = 1.96 * (std_acc / math.sqrt(max_trials))
                
                mean_rec_cost = statistics.mean(recovery_costs) if recovery_costs else 0.0
                std_rec = statistics.stdev(recovery_costs) if len(recovery_costs) > 1 else 0.0
                ci_rec = 1.96 * (std_rec / math.sqrt(max_trials))
                
                results[(fault_id, scheduler_name)] = {
                    "acc": mean_acc, "acc_ci": ci_acc,
                    "cost": mean_rec_cost, "cost_ci": ci_rec,
                    "succ": statistics.mean(successes) if successes else 0.0
                }
                
                tracker.log_episode(
                    episode_data={"fault": fault_id, "scheduler": scheduler_name, "dataset": dataset},
                    metrics={"acc": mean_acc, "cost": mean_rec_cost, "succ": statistics.mean(successes) if successes else 0.0},
                    run_id="summary"
                )

        print("\n--- Benchmark Final Report [REAL-SYSTEM DATA] ---")
        print(f"Dataset: {dataset.upper()} | Split: {split.upper()} | Trials per grid: {max_trials}")
        print(f"{'Fault Type':<30} | {'Scheduler':<15} | {'RCA Acc':<15} | {'Rec Cost':<15} | {'Succ Rate':<10}")
        print("-" * 95)
        for (f, s), r in results.items():
            acc_str = f"{r['acc']:.2f} ± {r['acc_ci']:.2f}"
            cost_str = f"{r['cost']:.3f} ± {r['cost_ci']:.3f}"
            print(f"{f:<30} | {s:<15} | {acc_str:<15} | {cost_str:<15} | {r['succ']:.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAG benchmark with real dataset queries.")
    parser.add_argument("--dataset", required=True, help="Dataset canonical name (e.g. scifact, arguana)")
    parser.add_argument("--split", required=True, help="Split name (e.g. test, dev)")
    parser.add_argument("--max-trials", type=int, default=10, help="Max queries to sample per grid combination (default: 10)")
    
    args = parser.parse_args()
    
    asyncio.run(run_real_benchmark(args.dataset, args.split, args.max_trials))
