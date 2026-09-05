import asyncio
import json
import uuid
import time
from datetime import datetime
from pathlib import Path

from packages.bcrb.src.orchestrator import BCRBOrchestrator
from packages.contracts.src.agent_models import AgentInvocation, AgentIdentity
from packages.contracts.src.bcrb_models import BCRBSession, AblationConfig, StoppingCondition
from packages.rag_benchmark.src.real_fault_injector import GenuineFaultInjector
from packages.rag_benchmark.src.fault_models import FaultScenario, FaultType


async def run_single_ablation(tenant_id: str, config_name: str, ablation_config: AblationConfig, fault_scenario: FaultScenario):
    """Run a single ablation trial for a specific config on a given fault scenario."""
    orchestrator = BCRBOrchestrator(tenant_id=tenant_id)
    
    # 1. Inject fault
    injector = GenuineFaultInjector()
    injector.inject(None, fault_scenario)
    
    # 2. Simulate or execute invocations to gather trace
    # In a real environment we would trigger the RAG pipeline here.
    # For the benchmark we will synthesize some basic agent invocations.
    run_id = str(uuid.uuid4())
    run_uuid = uuid.UUID(run_id)
    tenant_uuid = uuid.uuid4()
    
    # Simple simulated trace (retrieval -> reasoning -> response -> verify)
    invocations = [
        AgentInvocation(
            run_id=run_uuid,
            tenant_id=tenant_uuid,
            agent_name="retrieval",
            agent_identity=AgentIdentity(agent_type="retrieval", agent_id="ret-1", agent_version="1.0"),
            start_time=datetime.now(),
            end_time=datetime.now(),
            metadata={"is_error": fault_scenario.fault_type in [FaultType.RETRIEVAL_FAILURE, FaultType.STALE_CORPUS]}
        ),
        AgentInvocation(
            run_id=run_uuid,
            tenant_id=tenant_uuid,
            agent_name="reasoning",
            agent_identity=AgentIdentity(agent_type="reasoning", agent_id="rea-1", agent_version="1.0"),
            start_time=datetime.now(),
            end_time=datetime.now(),
            metadata={"is_error": fault_scenario.fault_type == FaultType.PROMPT_REGRESSION}
        ),
    ]
    
    session = BCRBSession(
        run_id=run_uuid,
        tenant_id=tenant_uuid,
        budget_usd=1.0,
        total_spent_usd=0.0
    )
    
    # 3. Execute BCRB
    start_t = time.time()
    try:
        session = await orchestrator.execute_session(
            session=session,
            invocations=invocations,
            failure_symptom="benchmark_failure",
            ablation_config=ablation_config
        )
    finally:
        # 4. Restore state
        injector.reset(None)
        
    duration = time.time() - start_t
    
    success = session.stopping_condition_met == StoppingCondition.CONFIDENCE_REACHED
    
    return {
        "config": config_name,
        "success": success,
        "steps_taken": len(session.steps),
        "total_spent_usd": session.total_spent_usd,
        "duration_seconds": duration,
        "stopping_condition": session.stopping_condition_met.value if session.stopping_condition_met else None
    }


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=1, help="Number of random seeds to run")
    args = parser.parse_args()

    tenant_id = "tenant-ablation-test"
    
    # Define Configurations
    configs = {
        "Full DriftGuardX": AblationConfig(),
        "Without GAT": AblationConfig(without_gat=True),
        "Without diffusion": AblationConfig(without_diffusion=True),
        "Without Bayesian update": AblationConfig(without_bayesian=True),
        "Without BCRB utility": AblationConfig(without_bcrb_utility=True),
        "Without replay": AblationConfig(without_replay=True),
        "Without provenance": AblationConfig(without_provenance=True),
        "GAT only": AblationConfig(gat_only=True),
        "Diffusion only": AblationConfig(diffusion_only=True),
        "Symptoms only": AblationConfig(symptoms_only=True),
        "Fixed-order recovery": AblationConfig(fixed_order_recovery=True),
    }
    
    print(f"Starting Ablation Study (Dry-run mode, seeds={args.seeds})...")
    all_results = []
    
    for seed in range(42, 42 + args.seeds):
        print(f"\n--- Running Seed {seed} ---")
        
        # Minimal scenario for dry-run
        scenario = FaultScenario(
            scenario_id=f"scen-{seed}",
            dataset="test",
            split="test",
            query_id="q1",
            seed=seed,
            scenario_name="Ablation Dry Run",
            fault_type=FaultType.PROMPT_REGRESSION,
            fault_component_id="reasoning",
            fault_configuration={},
            expected_failure_property="test",
            allowed_interventions=[],
            ground_truth_metadata={},
            environment_metadata={}
        )

        for config_name, ablation_config in configs.items():
            print(f"Running config: {config_name}")
            try:
                res = await run_single_ablation(tenant_id, config_name, ablation_config, scenario)
                res["seed"] = seed
                all_results.append(res)
                print(f"  -> Result: Success={res['success']}, Steps={res['steps_taken']}, Time={res['duration_seconds']:.2f}s")
            except Exception as e:
                print(f"  -> Failed: {e}")
            
    # Save results
    out_dir = Path("packages/rag_benchmark/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "ablation_results.json"
    
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2)
        
    print(f"\nAblation study complete. Results saved to {out_file}")
    
    if args.seeds == 1:
        print("\n| Configuration | Success | Steps | Time (s) | Spent ($) |")
        print("|---|---|---|---|---|")
        for r in all_results:
            print(f"| {r['config']} | {r['success']} | {r['steps_taken']} | {r['duration_seconds']:.2f} | {r['total_spent_usd']:.4f} |")


if __name__ == "__main__":
    asyncio.run(main())
