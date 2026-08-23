"""
DriftGuard-X v2 — E2E tests for the four compute/memory/storage/network optimisations.
"""

# ────────────────────────────────────────────────────────────────────────────
# Enhancement 1: JIT Graph Hydration
# ────────────────────────────────────────────────────────────────────────────

from packages.replay.src.jit_hydration import JITGraphHydrator, LazyStateStore


class TestJITGraphHydration:
    def _make_store(self):
        raw = {
            "node_a": {"value": 1},
            "node_b": {"value": 2},
            "node_c": {"value": 3},
            "node_d": {"value": 4},
            "node_e": {"value": 5},
        }
        return LazyStateStore(raw)

    def test_lazy_store_starts_empty(self):
        store = self._make_store()
        assert store.hydrated_count == 0
        assert store.total_variables == 5

    def test_jit_hydrates_only_neighbourhood(self):
        store = self._make_store()
        graph = {
            "node_a": ["node_b", "node_c"],
            "node_b": ["node_d"],
            "node_c": [],
            "node_d": [],
            "node_e": [],   # Disconnected node — should NOT be hydrated
        }
        hydrator = JITGraphHydrator(graph, store)
        result = hydrator.hydrate_for_node("node_a", depth=1)

        # node_a plus its direct neighbours (node_b, node_c) = 3 variables
        assert "node_a" in result
        assert "node_b" in result
        assert "node_c" in result
        assert "node_e" not in result   # disconnected — zero RAM cost
        assert store.hydrated_count == 3  # Only 3 of 5 variables were hydrated

    def test_jit_depth_2_extends_neighbourhood(self):
        store = self._make_store()
        graph = {
            "node_a": ["node_b"],
            "node_b": ["node_c"],
            "node_c": [],
            "node_d": [],
            "node_e": [],
        }
        hydrator = JITGraphHydrator(graph, store)
        result = hydrator.hydrate_for_node("node_a", depth=2)
        # depth=2: node_a -> node_b -> node_c
        assert "node_a" in result
        assert "node_b" in result
        assert "node_c" in result
        assert "node_d" not in result
        assert "node_e" not in result

    def test_missing_state_variable_returns_none(self):
        store = LazyStateStore({"node_a": 42})
        graph = {"node_a": ["ghost_node"]}
        hydrator = JITGraphHydrator(graph, store)
        result = hydrator.hydrate_for_node("node_a", depth=1)
        assert "ghost_node" in result
        assert result["ghost_node"] is None


# ────────────────────────────────────────────────────────────────────────────
# Enhancement 2: Semantic Circuit Breaker
# ────────────────────────────────────────────────────────────────────────────

from packages.replay.src.semantic_circuit_breaker import CircuitState, SemanticCircuitBreaker


class TestSemanticCircuitBreaker:
    def test_trips_on_sql_delete(self):
        scb = SemanticCircuitBreaker()
        tripped = scb.inspect("DELETE FROM users WHERE id = 42")
        assert tripped is True
        assert scb.state == CircuitState.TRIPPED

    def test_trips_on_http_post_keyword(self):
        scb = SemanticCircuitBreaker()
        assert scb.inspect("requests.post('https://api.example.com/resource', json=data)")

    def test_trips_on_python_ast_delete_call(self):
        scb = SemanticCircuitBreaker()
        source = """
def agent_step():
    db.delete(record_id)
"""
        assert scb.inspect(source)

    def test_safe_read_passes_through(self):
        scb = SemanticCircuitBreaker()
        safe = scb.inspect("SELECT * FROM documents WHERE tenant_id = 7")
        assert safe is False
        assert scb.state == CircuitState.CLOSED

    def test_execute_with_breaker_returns_mock_on_trip(self):
        scb = SemanticCircuitBreaker()

        def real_network_call():
            raise AssertionError("Should NOT be called!")

        result = scb.execute_with_breaker(
            "UPDATE accounts SET balance = 0",
            real_network_call,
        )
        assert result["intercepted"] is True
        assert result["status"] == 200
        assert "mock" in result["body"]

    def test_execute_with_breaker_calls_live_on_safe(self):
        scb = SemanticCircuitBreaker()

        def real_call():
            return {"data": "real_payload"}

        result = scb.execute_with_breaker("GET /api/status", real_call)
        assert result["intercepted"] is False
        assert result["result"]["data"] == "real_payload"

    def test_trip_log_records_trigger(self):
        scb = SemanticCircuitBreaker()
        scb.inspect("DROP TABLE sessions")
        assert len(scb.trip_log) == 1
        assert scb.trip_log[0]["trigger"] == "DROP"


# ────────────────────────────────────────────────────────────────────────────
# Enhancement 3: Merkle-DAG State Deduplication
# ────────────────────────────────────────────────────────────────────────────

from packages.replay.src.merkle_dag import MerkleDAGStore


class TestMerkleDAGDeduplication:
    SHARED_PROMPT = {"prompt": "What is the capital of France?", "model": "gpt-4o"}

    def test_identical_payloads_deduplicated(self):
        store = MerkleDAGStore()
        n1 = store.add_node("trace1/span1", self.SHARED_PROMPT)
        n2 = store.add_node("trace2/span1", self.SHARED_PROMPT)

        # Both nodes map to the same content — store should return the same node
        assert n1.node_hash == n2.node_hash
        # Only 1 blob stored (the shared prompt)
        assert store.blob_count == 1
        # But only 1 logical node (second insert was a dedup)
        assert store.node_count == 1

    def test_different_payloads_stored_separately(self):
        store = MerkleDAGStore()
        store.add_node("n1", {"prompt": "Hello"})
        store.add_node("n2", {"prompt": "World"})
        assert store.blob_count == 2
        assert store.node_count == 2

    def test_parent_hash_changes_node_hash(self):
        store = MerkleDAGStore()
        root = store.add_node("root", {"step": "retrieval"})
        child_a = store.add_node("child_a", {"step": "generation"}, parent_ids=["root"])
        child_b = store.add_node("child_b", {"step": "generation"})  # Same payload, no parent

        # Different ancestry => different hashes even for identical payloads
        assert child_a.node_hash != child_b.node_hash

    def test_chain_integrity_verification(self):
        store = MerkleDAGStore()
        store.add_node("root", {"data": "original"})
        assert store.verify_chain("root") is True

    def test_tampered_node_fails_verification(self):
        store = MerkleDAGStore()
        store.add_node("root", {"data": "original"})
        # Manually tamper with the stored payload
        store._nodes["root"].payload = {"data": "TAMPERED!"}
        assert store.verify_chain("root") is False

    def test_retrieval_by_hash(self):
        store = MerkleDAGStore()
        n = store.add_node("my_node", {"key": "value"})
        retrieved = store.get_by_hash(n.node_hash)
        assert retrieved is not None
        assert retrieved.node_id == "my_node"


# ────────────────────────────────────────────────────────────────────────────
# Enhancement 4: Pre-emptive Compute Shedding
# ────────────────────────────────────────────────────────────────────────────

from packages.evaluation.src.bandit_baselines import CandidateArm
from packages.replay.src.bandit import ResourceAdmittedBCRBController


class TestPreemptiveComputeShedding:
    def test_arms_with_no_history_are_never_shed(self):
        sched = ResourceAdmittedBCRBController(total_budget=10.0)
        arms = [
            CandidateArm(arm_id="arm_a", cost=5.0, prior=0.8),
            CandidateArm(arm_id="arm_b", cost=8.5, prior=0.6),
        ]
        selected = sched.select_arm(arms)
        # First selection — no history, optimistic: nothing should be shed
        assert selected is not None
        assert not sched.shed_log

    def test_arm_shed_when_predicted_to_bust_budget(self):
        sched = ResourceAdmittedBCRBController(total_budget=5.0)
        arms = [
            CandidateArm(arm_id="arm_a", cost=4.0, prior=0.8),  # Fits
            CandidateArm(arm_id="arm_b", cost=3.0, prior=0.7),  # Fits
        ]
        # Seed arm_b's history with costs far above the budget
        sched._cost_history["arm_b"] = [50.0, 51.0, 52.0, 53.0, 54.0]

        selected = sched.select_arm(arms)
        # arm_b should be shed (its historical cost massively exceeds budget)
        assert "arm_b" in sched.shed_log
        # arm_a should survive
        assert selected == "arm_a"

    def test_stop_reason_when_all_arms_shed(self):
        sched = ResourceAdmittedBCRBController(total_budget=5.0)
        arms = [CandidateArm(arm_id="arm_a", cost=4.0, prior=0.8)]
        sched._cost_history["arm_a"] = [100.0, 101.0, 102.0, 103.0, 104.0]

        result = sched.select_arm(arms)
        assert result is None
        assert "Shed" in sched.stop_reason

    def test_cost_history_accumulated_after_update(self):
        sched = ResourceAdmittedBCRBController(total_budget=20.0)
        sched.update("arm_a", reward=0.9, cost=3.0)
        sched.update("arm_a", reward=0.8, cost=4.0)
        history = sched._cost_history["arm_a"]
        assert history == [3.0, 4.0]
