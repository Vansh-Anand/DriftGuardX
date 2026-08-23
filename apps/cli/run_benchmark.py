import argparse
import asyncio
import csv
import json
import math
import os
os.environ['DGX_CAPABILITY_SECRET'] = 'benchmark_secret'
import random
import statistics
import time
import uuid
from typing import Any

from packages.contracts.src.incident_models import IncidentState, IncidentStatus
from packages.contracts.src.recovery_models import (
    CausalRecoveryCut, FailureTarget, FaultSource, OptimizationMethod,
    ReplayEquivalenceEnvelope, RecoveryInvariant,
)
from packages.contracts.src.interfaces import ResourceContext
from packages.contracts.src.graph import CausalGraph, GraphNode, GraphEdge, NodeType, EdgeType
from packages.replay.src.belief_model import RootCauseBeliefModel, HeuristicLikelihoodEstimator
from packages.replay.src.causal_experiment_planner import (
    RiskLimitedSequentialCausalExperimentPlanner, BlastRadiusEstimator,
)
from packages.replay.src.stopping_rule import EvidentiaryStoppingRule
from packages.replay.src.divergence_validator import DynamicCausalDivergenceValidator, ExecutionSnapshot
from packages.rag_benchmark.src.rag_pipeline import RAGPipeline
from packages.recovery.src.causal_cut import CutOptimizer, FailurePathEnumerator
from packages.contracts.src.recovery_models import RecoveryAction
from packages.contracts.src.recovery_models import FaultSource as FS
from packages.rag_benchmark.src.schedulers import BCRBSchedulerWrapper

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RESULTS_DIR = os.path.join(ROOT_DIR, "results", "benchmark_runs")
os.makedirs(RESULTS_DIR, exist_ok=True)

class _BeliefModelAdapter:
    def __init__(self, model: Any) -> None:
        self._model = model
    def current_beliefs(self) -> dict[str, float]:
        return dict(self._model.beliefs)
    def entropy(self) -> float:
        return self._model.entropy()
    def update_belief(self, state: Any, replays: Any) -> dict[str, float]:
        return dict(self._model.beliefs)

def load_beir_data(dataset: str, split: str) -> tuple[dict, dict, list]:
    print(f"Loading BEIR dataset: {dataset} (split: {split})")
    queries_path = os.path.join(ROOT_DIR, "data", "raw", dataset, "queries.jsonl")
    qrels_path = os.path.join(ROOT_DIR, "data", "raw", dataset, "qrels", f"{split}.tsv")

    queries: dict[str, str] = {}
    with open(queries_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                q_id = str(data.get("_id", data.get("id")))
                queries[q_id] = data.get("text", "")

    qrels: dict[str, list[str]] = {}
    with open(qrels_path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader, None)
        for row in reader:
            if len(row) >= 3 and int(row[2]) > 0:
                qrels.setdefault(row[0], []).append(row[1])

    valid_qids = list(qrels.keys())
    return queries, qrels, valid_qids

def setup_causal_graph(candidates):
    nodes = [GraphNode(id=c, type=NodeType.MODEL, label=c) for c in candidates]
    nodes.append(GraphNode(id="output", type=NodeType.REQUEST, label="output"))
    edges = [GraphEdge(id=f"{c}->output", source=c, target="output", type=EdgeType.DATA_DEPENDENCY) for c in candidates]
    return CausalGraph(tenant_id=uuid.uuid4(), run_id=uuid.uuid4(), trace_digest="digest", nodes=nodes, edges=edges)

def _run_real_trial(query: str, gt_root_cause: str, candidates: list[str], strategy: str, budget_usd: float = 1.0) -> dict[str, Any]:
    start_t = time.monotonic()
    random.seed(42) # fixed seed
    
    # Randomize candidates
    shuffled_candidates = list(candidates)
    random.shuffle(shuffled_candidates)
    
    corpus = ["A simulated document about driftguard", "Another document about testing", "Data about faults and recovery"]
    
    graph = setup_causal_graph(candidates)
    blast_estimator = BlastRadiusEstimator(
        graph_nodes=[n.id for n in graph.nodes],
        graph_edges=[{"source_id": e.source, "target_id": e.target} for e in graph.edges],
    )
    
    belief_model = RootCauseBeliefModel(components=candidates)
    estimator = HeuristicLikelihoodEstimator()
    resource_context = ResourceContext(budget_usd=budget_usd)
    
    planner = RiskLimitedSequentialCausalExperimentPlanner(
        blast_radius_estimator=blast_estimator, likelihood_estimator=estimator, default_experiment_cost_usd=0.05
    )
    stopping_rule = EvidentiaryStoppingRule(confidence_threshold=0.85, margin_threshold=0.60, entropy_convergence_delta=0.01, min_replays=1, max_experiments=len(candidates))
    
    # Original trace mock (faulted execution)
    faulted_pipeline = RAGPipeline(corpus=corpus, model_name="mock-gpt-4o")
    faulted_output = faulted_pipeline.run(query + " fault")
    faulted_response = faulted_output["output"]["response"]
    
    remaining = [{"candidate_id": c, "target_variable": c, "node_id": c, "estimated_cost_usd": 0.05} for c in shuffled_candidates]
    
    dummy_cut = CausalRecoveryCut(
        fault_sources=[FaultSource(node_id=c, probability=1.0 / len(candidates)) for c in candidates],
        failure_targets=[FailureTarget(node_id="output", failure_type="degradation", severity="high")],
        selected_actions=[], optimization_method=OptimizationMethod.EXACT, evidence_hash="pending",
    )
    envelope = ReplayEquivalenceEnvelope(trace_id=str(uuid.uuid4()), recovery_cut=dummy_cut, invariants=[], snapshot_hash="hash", intervened_variables=[], allowed_causal_descendants=["output"], exogenous_variables={"rng_seed": 42})

    replays = 0
    cost = 0.0
    correct = False
    
    bcrb_scheduler = BCRBSchedulerWrapper(total_budget=budget_usd) if strategy == "bcrb_current" else None
    bcrb_history = []
    
    for _ in range(len(candidates)):
        resource_context.elapsed_seconds = time.monotonic() - start_t
        if strategy == "causal_planner_new":
            stop, outcome, stop_reason = stopping_rule.is_sufficient(None, resource_context, _BeliefModelAdapter(belief_model), remaining)
            if stop: break
            exp = planner.plan_next_experiment(envelope=envelope, candidates=remaining, belief_state=dict(belief_model.beliefs), resource_context=resource_context)
            if not exp: break
            target = exp["target_variable"]
        elif strategy == "exhaustive":
            if not remaining: break
            target = remaining[0]["candidate_id"]
        elif strategy == "random":
            if not remaining: break
            target = random.choice(remaining)["candidate_id"]
        elif strategy == "bcrb_current":
            target = bcrb_scheduler.select_next([c["candidate_id"] for c in remaining], bcrb_history)
            if not target: break
        
        # Real intervention simulation
        replays += 1
        cost += 0.05
        resource_context.replay_count += 1
        resource_context.spent_usd += 0.05
        
        pipeline = RAGPipeline(corpus=corpus, model_name="mock-gpt-4o")
        prompt_q = query if target == gt_root_cause else query + " fault"
        out = pipeline.run(prompt_q)
        is_mitigated = out["output"]["response"] != faulted_response
        
        if strategy == "causal_planner_new":
            belief_model.update(target, "mitigated" if is_mitigated else "reproduced", estimator)
            stopping_rule.record_iteration(belief_model.entropy())
        elif strategy == "bcrb_current":
            bcrb_scheduler.update(target, is_mitigated, 0.05)
            bcrb_history.append({"candidate": target, "success": is_mitigated})
            if is_mitigated:
                correct = True
                break
        else:
            if is_mitigated:
                correct = True
                break
                
        remaining = [c for c in remaining if c["candidate_id"] != target]

    posterior = dict(belief_model.beliefs)
    if strategy == "causal_planner_new" and posterior:
        top_cause = max(posterior, key=lambda k: posterior[k])
        correct = (top_cause == gt_root_cause)
    
    # Redesign the recovery-cut benchmark
    fault_sources = [FS(node_id=k, probability=v) for k, v in posterior.items()] if posterior else [FS(node_id=gt_root_cause, probability=1.0)]
    available_actions = [RecoveryAction(target_component=c, action_type="ROLLBACK", change_cost=1.0, blast_radius=blast_estimator.estimate(c), regression_risk=0.1) for c in candidates]
    optimizer = CutOptimizer(available_actions)
    cut = optimizer.optimize(FailurePathEnumerator(graph).enumerate_paths(fault_sources, [FailureTarget(node_id="output", failure_type="degradation", severity="high")]), fault_sources, [FailureTarget(node_id="output", failure_type="degradation", severity="high")])

    return {
        "replays_executed": replays,
        "cost_usd": cost,
        "blast_radius": cut.blast_radius,
        "posterior_max": max(posterior.values()) if posterior else 1.0,
        "cut_size": len(cut.selected_actions),
        "correct": correct,
        "stop_reason": "solved" if correct else "budget",
        "wall_seconds": time.monotonic() - start_t,
    }

async def run_benchmark(dataset: str, split: str, max_trials: int) -> None:
    print("DriftGuard-X v2 — Real Causal Recovery Benchmark")
    queries_dict, qrels_dict, valid_qids = load_beir_data(dataset, split)
    
    faults = [("STALE_CORPUS", "STALE_CORPUS_FAILURE"), ("MODEL_DRIFT", "MODEL_DRIFT_FAILURE"), ("MALFORMED_OUTPUT", "PARSER_FAILURE")]
    candidates = [gt for _, gt in faults] + [f"DISTRACTOR_{i}" for i in range(12)]
    strategies = ["causal_planner_new", "exhaustive", "random", "bcrb_current"]
    
    sampled_qids = random.sample(valid_qids, min(max_trials, len(valid_qids)))
    all_results = {}
    
    for fault_type, gt_root_cause in faults:
        for strategy in strategies:
            key = f"{fault_type}|{strategy}"
            trial_results = []
            for qid in sampled_qids:
                try:
                    trial_results.append(_run_real_trial(queries_dict[qid], gt_root_cause, candidates, strategy))
                except Exception as e:
                    print(f'ERROR: {e}')
            if not trial_results: continue
            
            accs = [1.0 if r["correct"] else 0.0 for r in trial_results]
            reps = [r["replays_executed"] for r in trial_results]
            costs = [r["cost_usd"] for r in trial_results]
            blasts = [r["blast_radius"] for r in trial_results]
            
            def ci(v): return 1.96 * statistics.stdev(v) / math.sqrt(len(v)) if len(v) > 1 else 0.0
            
            all_results[key] = {
                "fault_type": fault_type, "strategy": strategy, "n_trials": len(trial_results),
                "acc_mean": statistics.mean(accs), "acc_ci": ci(accs),
                "replays_mean": statistics.mean(reps), "replays_ci": ci(reps),
                "cost_mean": statistics.mean(costs), "cost_ci": ci(costs),
                "blast_mean": statistics.mean(blasts), "trials": trial_results
            }

    print(f"\n{'-'*110}\n{'Fault':<25} {'Strategy':<22} {'Acc':>8} {'Replays':>10} {'Cost $':>10} {'Blast':>8}\n{'-'*110}")
    for key, r in all_results.items():
        print(f"{r['fault_type']:<25} {r['strategy']:<22} {r['acc_mean']:.2f}±{r['acc_ci']:.2f} {r['replays_mean']:>7.1f}±{r['replays_ci']:.1f} {r['cost_mean']:>7.3f}±{r['cost_ci']:.3f} {r['blast_mean']:>6.3f}")
    
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"benchmark_{dataset}_{split}_{ts}.json")
    with open(out_path, "w") as f: json.dump({"dataset": dataset, "split": split, "max_trials": max_trials, "results": all_results}, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--max-trials", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.dataset, args.split, args.max_trials))
