"""
DriftGuard-X v2 — Tests for Minimum Causal Recovery Cut
"""
import uuid

from packages.contracts.src.graph import CausalGraph, EdgeType, GraphEdge, GraphNode, NodeType
from packages.contracts.src.recovery_models import (
    FailureTarget,
    FaultSource,
    OptimizationMethod,
    RecoveryAction,
    RecoveryInvariant,
)
from packages.recovery.src.causal_cut import CutOptimizer, FailurePathEnumerator
from packages.recovery.src.validation import RecoveryValidator

# --- Helper methods to create mock graphs ---

def _mock_graph(nodes_info: list[str], edges_info: list[str]) -> CausalGraph:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()

    nodes = [
        GraphNode(id=n, type=NodeType.OPERATIONAL_RESOURCE, label=n)
        for n in nodes_info
    ]
    edges = [
        GraphEdge(id=f"{src}->{tgt}", source=src, target=tgt, type=EdgeType.CONTROL_FLOW)
        for src, tgt in [e.split("->") for e in edges_info]
    ]

    return CausalGraph(
        tenant_id=tenant_id,
        run_id=run_id,
        nodes=nodes,
        edges=edges,
        trace_digest="mock_digest"
    )

# --- Test Cases ---

def test_single_node_cut_exists():
    """1. single node cut exists"""
    graph = _mock_graph(
        ["source1", "mid1", "mid2", "target1"],
        ["source1->mid1", "mid1->mid2", "mid2->target1"]
    )

    sources = [FaultSource(node_id="source1", probability=1.0)]
    targets = [FailureTarget(node_id="target1", failure_type="error", severity="high")]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)
    assert len(paths) == 1

    actions = [
        RecoveryAction(target_component="mid1", action_type="block", change_cost=10)
    ]

    cut = CutOptimizer(actions).optimize(paths, sources, targets)

    assert len(cut.selected_actions) == 1
    assert cut.selected_actions[0].target_component == "mid1"
    assert len(cut.residual_failure_paths) == 0

def test_two_node_cut_required():
    """2. two node cut required"""
    graph = _mock_graph(
        ["source1", "mid1", "mid2", "target1"],
        ["source1->mid1", "source1->mid2", "mid1->target1", "mid2->target1"]
    )

    sources = [FaultSource(node_id="source1", probability=1.0)]
    targets = [FailureTarget(node_id="target1", failure_type="error", severity="high")]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)
    assert len(paths) == 2

    actions = [
        RecoveryAction(target_component="mid1", action_type="block", change_cost=10),
        RecoveryAction(target_component="mid2", action_type="block", change_cost=10),
    ]

    cut = CutOptimizer(actions).optimize(paths, sources, targets)

    assert len(cut.selected_actions) == 2
    assert len(cut.residual_failure_paths) == 0

def test_cheap_but_risky_vs_expensive_safe():
    """3. & 4. cheap but risky recovery exists OR expensive but safe recovery exists"""
    # The optimizer should pick the combination with the lowest total cost.
    # Cost = change_cost * 1.0 + blast_radius * 1.5 + regression_risk * 2.0 + expected_downtime * 0.5

    graph = _mock_graph(
        ["source1", "nodeA", "nodeB", "target1"],
        ["source1->nodeA", "nodeA->target1", "source1->nodeB", "nodeB->target1"]
    )
    # paths: source1->nodeA->target1, source1->nodeB->target1

    sources = [FaultSource(node_id="source1", probability=1.0)]
    targets = [FailureTarget(node_id="target1", failure_type="error", severity="high")]
    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)

    # Action 1 hits nodeA (cheap but risky)
    # cost = 5*1 + 10*1.5 + 10*2 = 5 + 15 + 20 = 40
    a1 = RecoveryAction(target_component="nodeA", change_cost=5, blast_radius=10, regression_risk=10, action_type="block")

    # Action 2 hits nodeA (expensive but safe)
    # cost = 20*1 + 1*1.5 + 1*2 = 20 + 1.5 + 2 = 23.5  <- optimizer should pick this one
    a2 = RecoveryAction(target_component="nodeA", change_cost=20, blast_radius=1, regression_risk=1, action_type="block")

    # Action 3 hits nodeB (baseline safe)
    a3 = RecoveryAction(target_component="nodeB", change_cost=10, blast_radius=1, regression_risk=1, action_type="block")

    actions = [a1, a2, a3]

    cut = CutOptimizer(actions).optimize(paths, sources, targets)

    # It should pick a2 and a3
    selected_targets = {a.target_component for a in cut.selected_actions}
    assert "nodeB" in selected_targets
    assert "nodeA" in selected_targets

    # Make sure a2 is picked instead of a1
    picked_a = [a for a in cut.selected_actions if a.target_component == "nodeA"][0]
    assert picked_a.change_cost == 20

def test_unaffected_subsystem_regression():
    """5. unaffected subsystem regression detected (fails invariant)"""
    graph = _mock_graph(["s1", "m1", "t1"], ["s1->m1", "m1->t1"])
    sources = [FaultSource(node_id="s1", probability=1.0)]
    targets = [FailureTarget(node_id="t1", failure_type="err", severity="high")]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)
    # 'risky_component' triggers the subsystem invariant failure in our mock validator
    actions = [RecoveryAction(target_component="m1", action_type="b", change_cost=1)]

    cut = CutOptimizer(actions).optimize(paths, sources, targets)
    # forcibly rename the component for the mock test trigger
    cut.selected_actions[0].target_component = "risky_component"

    inv = RecoveryInvariant(
        scope="unaffected subsystem",
        metric="regression",
        baseline=0,
        allowed_deviation=0,
        severity="high",
        evidence_source="sim"
    )

    validator = RecoveryValidator(verifier=None)
    res = validator.validate_cut(cut, [inv], "trace1")

    assert res.invariants_satisfied is False
    assert res.eligible_for_canary is False

def test_impossible_recovery():
    """6. impossible recovery (returns empty or signals failure)"""
    graph = _mock_graph(["s1", "m1", "t1"], ["s1->m1", "m1->t1"])
    sources = [FaultSource(node_id="s1", probability=1.0)]
    targets = [FailureTarget(node_id="t1", failure_type="err", severity="high")]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)

    # no actions available that hit m1
    actions = [RecoveryAction(target_component="other_node", action_type="b", change_cost=1)]

    cut = CutOptimizer(actions).optimize(paths, sources, targets)

    assert len(cut.selected_actions) == 0
    assert len(cut.residual_failure_paths) == 1

def test_multiple_failure_targets():
    """7. multiple failure targets"""
    graph = _mock_graph(
        ["s1", "m1", "t1", "t2"],
        ["s1->m1", "m1->t1", "m1->t2"]
    )
    sources = [FaultSource(node_id="s1", probability=1.0)]
    targets = [
        FailureTarget(node_id="t1", failure_type="e1", severity="high"),
        FailureTarget(node_id="t2", failure_type="e2", severity="high"),
    ]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)
    assert len(paths) == 2

    # hitting m1 cuts both paths
    actions = [RecoveryAction(target_component="m1", action_type="b", change_cost=1)]
    cut = CutOptimizer(actions).optimize(paths, sources, targets)

    assert len(cut.selected_actions) == 1
    assert cut.selected_actions[0].target_component == "m1"
    assert len(cut.residual_failure_paths) == 0

def test_cycle_graph():
    """8. cycle/malformed graph"""
    # Graph has a cycle m1 -> m2 -> m1
    graph = _mock_graph(
        ["s1", "m1", "m2", "t1"],
        ["s1->m1", "m1->m2", "m2->m1", "m2->t1"]
    )
    sources = [FaultSource(node_id="s1", probability=1.0)]
    targets = [FailureTarget(node_id="t1", failure_type="err", severity="high")]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)
    # The enumerator should avoid infinite loops and find the path s1->m1->m2->t1
    assert len(paths) == 1
    assert paths[0] == ["s1", "m1", "m2", "t1"]

def test_approximate_solver_path():
    """9. approximate solver path (forced large graph)"""
    graph = _mock_graph(["s1", "m1", "t1"], ["s1->m1", "m1->t1"])
    sources = [FaultSource(node_id="s1", probability=1.0)]
    targets = [FailureTarget(node_id="t1", failure_type="err", severity="high")]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)

    # force the optimizer into approximate mode by lowering the limit
    actions = [RecoveryAction(target_component="m1", action_type="b", change_cost=1)]
    opt = CutOptimizer(actions)
    opt.MAX_EXACT_COMBINATIONS = 0 # Force approximate

    cut = opt.optimize(paths, sources, targets)
    assert cut.optimization_method == OptimizationMethod.APPROXIMATE
    assert len(cut.selected_actions) == 1

def test_unauthorized_recovery_action():
    """10. unauthorized recovery action (fails security capability check)"""
    graph = _mock_graph(["s1", "m1", "t1"], ["s1->m1", "m1->t1"])
    sources = [FaultSource(node_id="s1", probability=1.0)]
    targets = [FailureTarget(node_id="t1", failure_type="err", severity="high")]

    paths = FailurePathEnumerator(graph).enumerate_paths(sources, targets)

    actions = [RecoveryAction(target_component="m1", action_type="b", change_cost=1, required_capability="admin_cap")]
    cut = CutOptimizer(actions).optimize(paths, sources, targets)

    validator = RecoveryValidator(verifier=None)
    # Don't provide the required capability
    res = validator.validate_cut(cut, [], "trace1", provided_capabilities=["user_cap"])

    assert res.failure_resolved is False
    assert res.eligible_for_canary is False
    assert "admin_cap" in res.divergence_report.get("security", "")
