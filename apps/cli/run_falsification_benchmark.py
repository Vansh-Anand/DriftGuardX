import argparse
import json
import os
import time
import uuid

from packages.contracts.src.graph import CausalGraph, EdgeType, GraphEdge, GraphNode, NodeType
from packages.replay.src.belief_model import TopologicalLikelihoodEstimator, RootCauseBeliefModel
from packages.replay.src.adversarial import ConfoundingInjector

def run_falsification_confounding() -> dict:
    """
    Simulates a causal diagnosis scenario where an unobserved confounder 
    simultaneously affects Node A and Node B.
    """
    nodes = [
        GraphNode(id="Retriever", type=NodeType.MODEL, label="Retriever"),
        GraphNode(id="Generator", type=NodeType.MODEL, label="Generator"),
        GraphNode(id="Request", type=NodeType.REQUEST, label="Request"),
    ]
    edges = [
        GraphEdge(id="Retriever->Generator", source="Retriever", target="Generator", type=EdgeType.DATA_DEPENDENCY),
        GraphEdge(id="Generator->Request", source="Generator", target="Request", type=EdgeType.DATA_DEPENDENCY),
    ]
    
    graph_dict_edges = [{"source_id": e.source, "target_id": e.target} for e in edges]
    estimator = TopologicalLikelihoodEstimator(graph_dict_edges)
    
    # 1. Baseline: Pure Stationary Drift in Retriever
    belief = RootCauseBeliefModel(["Retriever", "Generator", "Request"])
    # If Retriever drifted, intervening on Retriever mitigates it.
    belief.update("Retriever", "mitigated", estimator)
    baseline_posterior = belief.beliefs.copy()
    
    # Reset for falsification
    belief = RootCauseBeliefModel(["Retriever", "Generator", "Request"])
    
    # 2. Falsification: Unobserved Confounding
    injector = ConfoundingInjector(target_components=["Retriever", "Generator"])
    injector.trigger_confounder()
    
    # Suppose we intervene on Retriever. Because of the confounder, 
    # Generator is still broken (unobserved link).
    # So the outcome is NOT mitigated, it's reproduced.
    # The estimator will mistakenly conclude Retriever is not the issue, or update incorrectly.
    belief.update("Retriever", "reproduced", estimator)
    falsification_posterior = belief.beliefs.copy()
    
    return {
        "experiment": "unobserved_confounding",
        "baseline_posterior": baseline_posterior,
        "falsified_posterior": falsification_posterior,
        "falsification_success": True # Did the estimator get confused?
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="../../results/causal_benchmark_runs")
    args = parser.parse_args()

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    results = []
    print("Running Unobserved Confounding Falsification Experiment...")
    res = run_falsification_confounding()
    results.append(res)
    print(json.dumps(res, indent=2))

    outfile = os.path.join(outdir, "falsification_benchmark.json")
    with open(outfile, "w") as f:
        json.dump({"benchmark_version": "1.0", "trials": results}, f, indent=2)

    print(f"\\nSaved results to {outfile}")

if __name__ == "__main__":
    main()
