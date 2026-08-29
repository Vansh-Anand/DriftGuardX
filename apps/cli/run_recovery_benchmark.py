import argparse
import json
import os
import time
import uuid

from packages.contracts.src.graph import CausalGraph, EdgeType, GraphEdge, GraphNode, NodeType
from packages.contracts.src.recovery_models import (
    FailureTarget,
    FaultSource,
    RecoveryAction,
)
from packages.rag_benchmark.src.recovery_models import SourceSelectionPolicy, SourceSelector
from packages.recovery.src.causal_cut import CutOptimizer, FailurePathEnumerator
from packages.replay.src.stopping_rule import StoppingOutcome


def generate_topology(topology_type: str) -> tuple[CausalGraph, dict[str, float], StoppingOutcome, str, list[RecoveryAction], list[FailureTarget]]:
    """Generates the causal graph and synthetic diagnosis for a given test topology."""

    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()

    nodes = []
    edges = []
    posterior = {}
    outcome = StoppingOutcome.CONFIRMED
    gt_cause = ""
    actions = []
    targets = [FailureTarget(node_id="output", failure_type="degradation", severity="high")]

    if topology_type == "A":
        # A. fault A -> X -> output, fault B -> X -> output
        nodes = [
            GraphNode(id="A", type=NodeType.MODEL, label="A"),
            GraphNode(id="B", type=NodeType.MODEL, label="B"),
            GraphNode(id="X", type=NodeType.MODEL, label="X"),
            GraphNode(id="output", type=NodeType.REQUEST, label="output")
        ]
        edges = [
            GraphEdge(id="A->X", source="A", target="X", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="B->X", source="B", target="X", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="X->out", source="X", target="output", type=EdgeType.DATA_DEPENDENCY)
        ]
        posterior = {"A": 0.45, "B": 0.45}
        outcome = StoppingOutcome.CONFIRMED # Technically unresolved if they are tied, but for testing CREDIBLE_SET we assume it's credible
        gt_cause = "A" # A is the ground truth

        actions = [
            RecoveryAction(target_component="A", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="B", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="X", action_type="ROLLBACK", change_cost=1.0),
        ]

    elif topology_type == "B":
        # B. fault A -> X -> output, fault B -> Y -> output
        nodes = [
            GraphNode(id="A", type=NodeType.MODEL, label="A"),
            GraphNode(id="B", type=NodeType.MODEL, label="B"),
            GraphNode(id="X", type=NodeType.MODEL, label="X"),
            GraphNode(id="Y", type=NodeType.MODEL, label="Y"),
            GraphNode(id="output", type=NodeType.REQUEST, label="output")
        ]
        edges = [
            GraphEdge(id="A->X", source="A", target="X", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="B->Y", source="B", target="Y", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="X->out", source="X", target="output", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="Y->out", source="Y", target="output", type=EdgeType.DATA_DEPENDENCY)
        ]
        posterior = {"A": 0.45, "B": 0.45}
        outcome = StoppingOutcome.CONFIRMED
        gt_cause = "A"

        actions = [
            RecoveryAction(target_component="A", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="B", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="X", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="Y", action_type="ROLLBACK", change_cost=1.0),
        ]

    elif topology_type == "C":
        # C. cheap high-regression action vs slightly more expensive safe action
        nodes = [
            GraphNode(id="A", type=NodeType.MODEL, label="A"),
            GraphNode(id="output", type=NodeType.REQUEST, label="output")
        ]
        edges = [
            GraphEdge(id="A->out", source="A", target="output", type=EdgeType.DATA_DEPENDENCY)
        ]
        posterior = {"A": 0.95}
        outcome = StoppingOutcome.CONFIRMED
        gt_cause = "A"

        actions = [
            RecoveryAction(target_component="A", action_type="ROLLBACK", change_cost=1.0, regression_risk=10.0, action_id="cheap_risky"),
            RecoveryAction(target_component="A", action_type="PATCH", change_cost=1.5, regression_risk=0.1, action_id="expensive_safe"),
        ]

    elif topology_type == "D":
        # D. whole-pipeline rollback vs minimal component rollback
        nodes = [
            GraphNode(id="pipeline", type=NodeType.MODEL, label="pipeline"),
            GraphNode(id="A", type=NodeType.MODEL, label="A"),
            GraphNode(id="output", type=NodeType.REQUEST, label="output")
        ]
        edges = [
            GraphEdge(id="pipe->A", source="pipeline", target="A", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="A->out", source="A", target="output", type=EdgeType.DATA_DEPENDENCY)
        ]
        posterior = {"A": 0.95}
        outcome = StoppingOutcome.CONFIRMED
        gt_cause = "A"

        actions = [
            RecoveryAction(target_component="pipeline", action_type="ROLLBACK", change_cost=10.0), # whole pipeline is expensive
            RecoveryAction(target_component="A", action_type="ROLLBACK", change_cost=1.0),
        ]

    elif topology_type == "E":
        # E. weak argmax correct but unconfirmed -> unresolved -> NO_AUTOMATIC_RECOVERY
        nodes = [
            GraphNode(id="A", type=NodeType.MODEL, label="A"),
            GraphNode(id="B", type=NodeType.MODEL, label="B"),
            GraphNode(id="C", type=NodeType.MODEL, label="C"),
            GraphNode(id="output", type=NodeType.REQUEST, label="output")
        ]
        edges = [
            GraphEdge(id="A->out", source="A", target="output", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="B->out", source="B", target="output", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="C->out", source="C", target="output", type=EdgeType.DATA_DEPENDENCY)
        ]
        posterior = {"A": 0.35, "B": 0.33, "C": 0.32}
        outcome = StoppingOutcome.UNRESOLVED
        gt_cause = "A"

        actions = [
            RecoveryAction(target_component="A", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="B", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="C", action_type="ROLLBACK", change_cost=1.0),
        ]

    elif topology_type == "F":
        # F. confident wrong diagnosis -> false confirmation
        nodes = [
            GraphNode(id="A", type=NodeType.MODEL, label="A"),
            GraphNode(id="B", type=NodeType.MODEL, label="B"),
            GraphNode(id="output", type=NodeType.REQUEST, label="output")
        ]
        edges = [
            GraphEdge(id="A->out", source="A", target="output", type=EdgeType.DATA_DEPENDENCY),
            GraphEdge(id="B->out", source="B", target="output", type=EdgeType.DATA_DEPENDENCY)
        ]
        posterior = {"A": 0.95, "B": 0.05} # model thinks A
        outcome = StoppingOutcome.CONFIRMED
        gt_cause = "B" # but B is actually the cause

        actions = [
            RecoveryAction(target_component="A", action_type="ROLLBACK", change_cost=1.0),
            RecoveryAction(target_component="B", action_type="ROLLBACK", change_cost=1.0)
        ]

    graph = CausalGraph(tenant_id=tenant_id, run_id=run_id, trace_digest="test", nodes=nodes, edges=edges)
    return graph, posterior, outcome, gt_cause, actions, targets

def run_baselines(topology_type: str, policy: SourceSelectionPolicy):
    graph, posterior, outcome, gt_cause, available_actions, targets = generate_topology(topology_type)

    # 1. Distinguish Correctness
    top_candidate = max(posterior, key=lambda k: posterior[k]) if posterior else None
    top_posterior = posterior[top_candidate] if top_candidate else 0.0

    sorted_probs = sorted(posterior.values(), reverse=True)
    second_posterior = sorted_probs[1] if len(sorted_probs) > 1 else 0.0
    margin = top_posterior - second_posterior

    argmax_correct = (top_candidate == gt_cause)
    confirmed_correct = (outcome == StoppingOutcome.CONFIRMED and argmax_correct)
    false_confirmation = (outcome == StoppingOutcome.CONFIRMED and not argmax_correct)

    # 2. Select Sources
    sources = SourceSelector.select_sources(posterior, outcome, policy)

    results = {
        "topology": topology_type,
        "selection_policy": policy.value,
        "stopping_telemetry": {
            "stopping_outcome": outcome.value,
            "stopping_reason": "synthetic",
            "top_candidate": top_candidate,
            "top_posterior": top_posterior,
            "second_posterior": second_posterior,
            "margin": margin,
            "entropy": 0.5, # synthetic
            "next_best_eig": 0.0,
            "valid_evidence_count": 5,
            "invalid_evidence_count": 0,
            "resource_state": "ok",
            "argmax_correct": argmax_correct,
            "confirmed_correct": confirmed_correct,
            "false_confirmation": false_confirmation
        },
        "baselines": {}
    }

    if not sources:
        results["baselines"]["all"] = {"recovery_success": False, "status": "NO_AUTOMATIC_RECOVERY"}
        return results

    path_enum = FailurePathEnumerator(graph)
    paths = path_enum.enumerate_paths(sources, targets)

    # Baseline 1: Minimum Causal Recovery Cut
    start_t = time.monotonic()
    optimizer = CutOptimizer(available_actions)
    cut = optimizer.optimize(paths, sources, targets)
    solve_time = time.monotonic() - start_t

    # Evaluate MCRC success on Ground Truth: does the cut block the path from GT to output?
    gt_paths = path_enum.enumerate_paths([FaultSource(node_id=gt_cause, probability=1.0)], targets)
    gt_blocked = True
    for p in gt_paths:
        hit = any(a.target_component in p for a in cut.selected_actions)
        if not hit:
            gt_blocked = False
            break

    # However, if false confirmation happened, we might block A when GT is B. So gt_blocked would be False.
    results["baselines"]["minimum_causal_cut"] = {
        "recovery_success": gt_blocked,
        "cut_size": len(cut.selected_actions),
        "change_cost": cut.total_change_cost,
        "blast_radius": cut.blast_radius,
        "regression_risk": cut.regression_risk,
        "downtime_proxy": cut.expected_downtime,
        "number_of_changed_components": len(cut.selected_actions),
        "solver_mode": getattr(cut.optimization_method, "value", cut.optimization_method),
        "solver_runtime": solve_time,
        "actions_selected": [a.target_component for a in cut.selected_actions]
    }

    # Baseline 2: Whole pipeline rollback (simulated by finding an action that targets 'pipeline' or just changing all sources)
    # Actually, whole pipeline means rollback everything in the graph
    all_cost = sum(a.change_cost for a in available_actions)
    results["baselines"]["whole_pipeline_rollback"] = {
        "recovery_success": True, # rollbacks everything, always fixes it
        "cut_size": len(available_actions),
        "change_cost": all_cost,
        "actions_selected": [a.target_component for a in available_actions]
    }

    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="../../results/causal_benchmark_runs")
    args = parser.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    topologies = ["A", "B", "C", "D", "E", "F"]
    policies = [SourceSelectionPolicy.CONFIRMED_SINGLE, SourceSelectionPolicy.CREDIBLE_SET]

    all_res = []
    for t in topologies:
        for p in policies:
            res = run_baselines(t, p)
            all_res.append(res)

    print(json.dumps(all_res, indent=2))

    with open(os.path.join(outdir, "recovery_cut_benchmark.json"), "w") as f:
        json.dump({"benchmark_version": "1.0", "trials": all_res}, f, indent=2)

    print(f"\\nSaved results to {outdir}/recovery_cut_benchmark.json")

if __name__ == "__main__":
    main()
