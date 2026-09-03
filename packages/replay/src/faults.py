"""
DriftGuard-X v2 — Fault Injection Laboratory
PRIVATE — All Rights Reserved.
"""

from pydantic import BaseModel


class FaultRecipe(BaseModel):
    id: str
    name: str
    description: str
    preconditions: list[str]
    affected_component_type: str
    primary_root_cause: str
    expected_symptoms: list[str]
    safe_alternatives: list[str]
    risk_tier: str  # e.g., low, medium, high
    cleanup_action: str


def get_all_fault_recipes() -> list[FaultRecipe]:
    return [
        FaultRecipe(
            id="fault_01",
            name="Stale Index",
            description="Simulates a retrieval index that hasn't been updated with latest knowledge.",
            preconditions=["Has Retriever"],
            affected_component_type="retriever",
            primary_root_cause="Cron job failure for index rebuild.",
            expected_symptoms=["Faithfulness drop", "Task success drop", "Missing evidence"],
            safe_alternatives=["Fallback to v-1 index", "Real-time search tool"],
            risk_tier="low",
            cleanup_action="Restore index version pointer.",
        ),
        FaultRecipe(
            id="fault_02",
            name="Changed Embeddings",
            description="Simulates swapping embedding models leading to vector mismatch.",
            preconditions=["Has Retriever", "Has Embedder"],
            affected_component_type="index",
            primary_root_cause="Embedding model upgrade without index re-embed.",
            expected_symptoms=["Retrieval precision drops to zero"],
            safe_alternatives=["Rollback model", "Trigger re-embed"],
            risk_tier="high",
            cleanup_action="Revert embedding provider.",
        ),
        FaultRecipe(
            id="fault_03",
            name="Bad Chunking",
            description="Simulates chunk size/overlap regression splitting context mid-sentence.",
            preconditions=["Has Chunker"],
            affected_component_type="chunker",
            primary_root_cause="Config drift in ingest pipeline.",
            expected_symptoms=["Low retrieval recall", "Hallucinations"],
            safe_alternatives=["Revert chunk size config"],
            risk_tier="medium",
            cleanup_action="Restore chunk config.",
        ),
        FaultRecipe(
            id="fault_04",
            name="Reranker Regression",
            description="Simulates a reranker prioritizing low-relevance cross-encoder scores.",
            preconditions=["Has Reranker"],
            affected_component_type="reranker",
            primary_root_cause="Model weights corruption or bad fine-tune.",
            expected_symptoms=["Top-K metrics drop"],
            safe_alternatives=["Bypass reranker (use raw ANN scores)"],
            risk_tier="medium",
            cleanup_action="Disable reranker step.",
        ),
        FaultRecipe(
            id="fault_05",
            name="Prompt Drift",
            description="Simulates a prompt injection or poorly reviewed prompt edit.",
            preconditions=["Has Prompt"],
            affected_component_type="prompt",
            primary_root_cause="Human error in prompt registry.",
            expected_symptoms=["Formatting errors", "Tone violations", "Refusals"],
            safe_alternatives=["Rollback prompt version"],
            risk_tier="low",
            cleanup_action="Revert prompt.",
        ),
        FaultRecipe(
            id="fault_06",
            name="Model Route Regression",
            description="Simulates a router sending complex queries to a weak model.",
            preconditions=["Has Model Router"],
            affected_component_type="router",
            primary_root_cause="Classification threshold drift.",
            expected_symptoms=["Task failure", "Low reasoning scores"],
            safe_alternatives=["Force route to strong model"],
            risk_tier="medium",
            cleanup_action="Adjust threshold.",
        ),
        FaultRecipe(
            id="fault_07",
            name="Citation Corruption",
            description="Simulates the generator mismatching facts with source IDs.",
            preconditions=["Has Generator"],
            affected_component_type="generator",
            primary_root_cause="Context window attention decay.",
            expected_symptoms=["Citation consistency drop"],
            safe_alternatives=["Increase temperature slightly", "Shorten context"],
            risk_tier="low",
            cleanup_action="None (generator tweak).",
        ),
        FaultRecipe(
            id="fault_08",
            name="Tool Schema Mismatch",
            description="Simulates an API schema change that the agent prompt doesn't know about.",
            preconditions=["Has Tool"],
            affected_component_type="tool",
            primary_root_cause="Backend API deployed breaking change.",
            expected_symptoms=["Agent loops on validation errors", "Task failure"],
            safe_alternatives=["Rollback API", "Update agent schema"],
            risk_tier="high",
            cleanup_action="Deploy synchronized versions.",
        ),
        FaultRecipe(
            id="fault_09",
            name="Wrong Arguments",
            description="Simulates the agent hallucinating tool arguments.",
            preconditions=["Has Tool"],
            affected_component_type="generator",
            primary_root_cause="Weak instruction following.",
            expected_symptoms=["Tool validation failure"],
            safe_alternatives=["Add parameter hints to prompt"],
            risk_tier="low",
            cleanup_action="None.",
        ),
        FaultRecipe(
            id="fault_10",
            name="Timeout",
            description="Simulates a downstream tool or retriever timing out.",
            preconditions=["Network Bound Component"],
            affected_component_type="operational_resource",
            primary_root_cause="Network partition or DB lock.",
            expected_symptoms=["Pipeline abort", "Latency spike"],
            safe_alternatives=["Retry", "Fallback cache"],
            risk_tier="medium",
            cleanup_action="None (transient).",
        ),
        FaultRecipe(
            id="fault_11",
            name="Repeated Tool Call",
            description="Simulates an agent getting stuck in an infinite tool-call loop.",
            preconditions=["Has Tool", "Has Memory"],
            affected_component_type="generator",
            primary_root_cause="Model failing to interpret tool response.",
            expected_symptoms=["Budget exhaustion", "Timeout"],
            safe_alternatives=["Hard max_steps limit"],
            risk_tier="high",
            cleanup_action="Enforce budget limit.",
        ),
        FaultRecipe(
            id="fault_12",
            name="Poisoned Memory",
            description="Simulates a previous turn storing malicious instructions in episodic memory.",
            preconditions=["Has Memory"],
            affected_component_type="memory",
            primary_root_cause="Prompt injection in turn N-1.",
            expected_symptoms=["Security violation", "Policy block"],
            safe_alternatives=["Clear memory context"],
            risk_tier="high",
            cleanup_action="Wipe session memory.",
        ),
        FaultRecipe(
            id="fault_13",
            name="Conflicting Memory",
            description="Simulates memory containing a fact that contradicts the current retrieval.",
            preconditions=["Has Memory", "Has Retriever"],
            affected_component_type="memory",
            primary_root_cause="State tracking bug.",
            expected_symptoms=["Hallucination", "Task failure"],
            safe_alternatives=["Prioritize retrieval over memory"],
            risk_tier="medium",
            cleanup_action="Fix state merging logic.",
        ),
        FaultRecipe(
            id="fault_14",
            name="Policy Weakening",
            description="Simulates a guardrail failing to block a PII leak.",
            preconditions=["Has Guardrail"],
            affected_component_type="guardrail",
            primary_root_cause="Regex or classifier regression.",
            expected_symptoms=["PII leak in trace"],
            safe_alternatives=["Rollback policy"],
            risk_tier="high",
            cleanup_action="Revert guardrail rules.",
        ),
        FaultRecipe(
            id="fault_15",
            name="Policy Overblocking",
            description="Simulates a guardrail blocking a benign query.",
            preconditions=["Has Guardrail"],
            affected_component_type="guardrail",
            primary_root_cause="Over-sensitive classification.",
            expected_symptoms=["False positive rejection"],
            safe_alternatives=["Adjust threshold"],
            risk_tier="low",
            cleanup_action="Tune classifier.",
        ),
        FaultRecipe(
            id="fault_16",
            name="Latency Spike",
            description="Simulates provider API latency increasing 10x.",
            preconditions=["External Provider"],
            affected_component_type="provider",
            primary_root_cause="Provider overload.",
            expected_symptoms=["Timeout cascading"],
            safe_alternatives=["Switch to backup provider"],
            risk_tier="medium",
            cleanup_action="Wait for provider resolution.",
        ),
        FaultRecipe(
            id="fault_17",
            name="Provider Error",
            description="Simulates a 503 Service Unavailable from the LLM.",
            preconditions=["External Provider"],
            affected_component_type="provider",
            primary_root_cause="Provider outage.",
            expected_symptoms=["Pipeline abort"],
            safe_alternatives=["Switch to backup provider"],
            risk_tier="high",
            cleanup_action="Wait for provider resolution.",
        ),
        FaultRecipe(
            id="fault_18",
            name="Budget Exhaustion",
            description="Simulates hitting the token budget limit.",
            preconditions=["Budget Tracking"],
            affected_component_type="operational_resource",
            primary_root_cause="Excessive input context or loops.",
            expected_symptoms=["Pipeline abort (429)"],
            safe_alternatives=["Increase budget tier"],
            risk_tier="low",
            cleanup_action="None.",
        ),
    ]


class FaultInjector:
    """
    Applies fault conditions to deterministic providers for testing replays.
    """

    def __init__(self):
        self.active_faults: dict[str, FaultRecipe] = {}

    def inject(self, recipe_id: str) -> None:
        recipes = {r.id: r for r in get_all_fault_recipes()}
        if recipe_id in recipes:
            self.active_faults[recipe_id] = recipes[recipe_id]

    def clear(self) -> None:
        self.active_faults.clear()
