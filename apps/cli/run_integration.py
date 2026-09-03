"""
DriftGuard-X v2 — End-to-End Orchestrator CLI Runner
PRIVATE — All Rights Reserved.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from packages.contracts.src.incident_models import IncidentState
from packages.contracts.src.recovery_models import FailureTarget
from packages.memory.src.auth import AccessContext
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


def main() -> None:
    parser = argparse.ArgumentParser(description="DriftGuard-X Integration Runner")
    parser.add_argument("--scenario", type=str, default="A", help="Scenario to run (A-F)")
    args = parser.parse_args()

    print(f"Running DriftGuard-X Integration Scenario {args.scenario}...")

    # Defaults
    defaults = dict(
        trace_provider=MockTraceProvider(),
        graph_provider=MockGraphProvider(),
        intervention_generator=MockInterventionGenerator(),
        envelope_builder=MockEnvelopeBuilder(),
        raeb_gateway=MockRAEBGateway(),
        experiment_planner=MockExperimentPlanner(),
        replay_executor=MockReplayExecutor(),
        divergence_validator=MockDivergenceValidator(),
        belief_model=MockBeliefModel(),
        stopping_policy=MockStoppingPolicy(),
        recovery_solver=MockRecoveryCutSolver(),
        recovery_validator=MockRecoveryValidator(),
        policy_engine=MockPolicyEngine(),
        ledger=MockLedger(),
        transport_gate=MockTransportabilityGate(),
    )

    if args.scenario == "A":
        targets = [
            FailureTarget(
                node_id="llm",
                failure_type="hallucination",
                severity="high",
                evidence={"wrong_answer": True},
            )
        ]
    elif args.scenario == "D":
        targets = [
            FailureTarget(node_id="external_api", failure_type="schema_change", severity="high")
        ]
        defaults["recovery_solver"] = MockRecoveryCutSolver(cut="NONE")
    else:
        targets = [FailureTarget(node_id="system", failure_type="generic", severity="low")]

    # We need MockRecoveryCutSolver to handle cut="NONE"
    if (
        "recovery_solver" in defaults
        and hasattr(defaults["recovery_solver"], "cut")
        and defaults["recovery_solver"].cut == "NONE"
    ):
        defaults["recovery_solver"].cut = None

    orch = CausalRecoveryOrchestrator(**defaults)
    state = IncidentState()

    print("\n--- Starting Causal Recovery ---")
    access_context = AccessContext(
        requester_id="local-integration-runner",
        tenant_id="local-validation-tenant",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    cert = orch.process_incident(state, targets, access_context=access_context)

    print("\n--- Transition Log ---")
    if "transition_log" in state.telemetry:
        for t in state.telemetry["transition_log"]:
            print(f"[{t['from']}] -> [{t['to']}]: {t['reason']}")

    print("\n--- Final Status ---")
    print(state.status.value)

    if cert:
        print(f"\nSuccess! Certificate ID: {cert}")
        sys.exit(0)
    else:
        print("\nRecovery Failed or was Rejected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
