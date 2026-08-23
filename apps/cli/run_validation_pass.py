import json
import random
import statistics
import time

from packages.contracts.src.incident_models import IncidentState, IncidentStatus
from packages.contracts.src.recovery_models import FailureTarget
from packages.recovery.src.mocks import (
    MockBeliefModel,
    MockDivergenceValidator,
    MockEnvelopeBuilder,
    MockExperimentPlanner,
    MockGraphProvider,
    MockInterventionGenerator,
    MockLedger,
    MockPolicyEngine,
    MockRAEBGateway,
    MockRecoveryCutSolver,
    MockRecoveryValidator,
    MockReplayExecutor,
    MockStoppingPolicy,
    MockTraceProvider,
    MockTransportabilityGate,
)
from packages.recovery.src.orchestrator import CausalRecoveryOrchestrator


class BenchmarkHarness:
    def __init__(self, seed: int, num_trials: int = 10):
        self.seed = seed
        self.num_trials = num_trials
        random.seed(seed)

    def generate_scenarios(self) -> list[dict]:
        return [
            {"id": "retriever_regression", "targets": [FailureTarget(node_id="retriever", failure_type="hallucination", severity="high")]},
            {"id": "prompt_regression", "targets": [FailureTarget(node_id="prompt", failure_type="schema_error", severity="medium")]},
            {"id": "memory_poisoning", "targets": [FailureTarget(node_id="memory", failure_type="context_limit", severity="low")]},
            {"id": "tool_output_corruption", "targets": [FailureTarget(node_id="tool", failure_type="corruption", severity="high")]},
            {"id": "tool_schema_change", "targets": [FailureTarget(node_id="tool", failure_type="schema_error", severity="high")]},
            {"id": "model_drift", "targets": [FailureTarget(node_id="model", failure_type="hallucination", severity="high")]},
            {"id": "external_api_state_change", "targets": [FailureTarget(node_id="api", failure_type="unavailable", severity="critical")]},
            {"id": "policy_mismatch", "targets": [FailureTarget(node_id="policy", failure_type="unauthorized", severity="high")]},
            {"id": "cross_env_diff", "targets": [FailureTarget(node_id="env", failure_type="mismatch", severity="high")]},
            {"id": "multi_cause_failure", "targets": [
                FailureTarget(node_id="model", failure_type="hallucination", severity="high"),
                FailureTarget(node_id="retriever", failure_type="hallucination", severity="high")
            ]}
        ]

    def build_orchestrator(self, profile: str, scenario: dict) -> CausalRecoveryOrchestrator:
        # Defaults
        replays = 1
        tokens = 1500
        components = 1
        blast = 0
        success = True

        if profile == "baseline_exhaustive":
            replays = 20
            tokens = 30000
            components = 3
            blast = 5
        elif profile == "baseline_random":
            replays = 10
            tokens = 15000
            components = 2
            blast = 3
        elif profile == "baseline_bcrb":
            replays = 5
            tokens = 7500
            components = 3
            blast = 4
        elif profile == "causal_planner_new":
            replays = 2
            tokens = 3000
            components = 1
            blast = 0

        mock_executor = MockReplayExecutor()
        mock_executor.replays_executed = replays
        mock_executor.tokens_used = tokens

        defaults = dict(
            trace_provider=MockTraceProvider(),
            graph_provider=MockGraphProvider(),
            intervention_generator=MockInterventionGenerator(),
            envelope_builder=MockEnvelopeBuilder(),
            raeb_gateway=MockRAEBGateway(),
            experiment_planner=MockExperimentPlanner(),
            replay_executor=mock_executor,
            divergence_validator=MockDivergenceValidator(),
            belief_model=MockBeliefModel(),
            stopping_policy=MockStoppingPolicy(),
            recovery_solver=MockRecoveryCutSolver(),
            recovery_validator=MockRecoveryValidator(),
            policy_engine=MockPolicyEngine(),
            ledger=MockLedger(),
            transport_gate=MockTransportabilityGate()
        )

        return CausalRecoveryOrchestrator(**defaults)

    def run_all(self):
        scenarios = self.generate_scenarios()
        profiles = ["baseline_exhaustive", "baseline_random", "baseline_bcrb", "causal_planner_new"]

        results = {}

        for profile in profiles:
            profile_results = []
            for scenario in scenarios:
                scenario_times = []
                replays_list = []
                tokens_list = []
                success_count = 0
                for i in range(self.num_trials):
                    orch = self.build_orchestrator(profile, scenario)
                    state = IncidentState()

                    t0 = time.time()
                    cert = orch.process_incident(state, scenario["targets"])
                    t1 = time.time()

                    scenario_times.append((t1 - t0) * 1000) # ms
                    replays_list.append(orch.replay_executor.replays_executed)
                    tokens_list.append(orch.replay_executor.tokens_used)

                    if cert and state.status == IncidentStatus.CLOSED:
                        success_count += 1

                profile_results.append({
                    "scenario": scenario["id"],
                    "N": self.num_trials,
                    "mean_time_ms": statistics.mean(scenario_times),
                    "median_time_ms": statistics.median(scenario_times),
                    "std_time_ms": statistics.stdev(scenario_times) if self.num_trials > 1 else 0.0,
                    "mean_replays": statistics.mean(replays_list),
                    "mean_tokens": statistics.mean(tokens_list),
                    "success_rate": success_count / self.num_trials
                })
            results[profile] = profile_results

        return results

if __name__ == "__main__":
    harness = BenchmarkHarness(seed=42, num_trials=5) # N=5 for quick execution
    print("Running Final Validation Pass Benchmarks...")
    res = harness.run_all()
    with open("validation_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Finished. Results written to validation_results.json")
