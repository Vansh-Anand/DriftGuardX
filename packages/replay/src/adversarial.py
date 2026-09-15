"""Adversarial constructs that falsify causal DAG assumptions."""

from typing import Any


class ConfoundingInjector:
    """Simulates a hidden confounder, such as an unobserved network partition,
    that simultaneously affects two distinct components in the DAG
    (e.g., Retriever and LLM) without being explicitly modeled.
    """

    def __init__(self, target_components: list[str], error_rate: float = 1.0):
        self.target_components = set(target_components)
        self.error_rate = error_rate
        self.is_active = False

    def trigger_confounder(self) -> None:
        """Activates the unobserved confounding event."""
        self.is_active = True

    def inject_if_active(self, component_name: str, telemetry: dict[str, Any]) -> dict[str, Any]:
        """If the confounder is active, mutate the telemetry of the targeted
        components to simulate a simultaneous failure.
        """
        if not self.is_active or component_name not in self.target_components:
            return telemetry

        mutated_telemetry = telemetry.copy()
        mutated_telemetry["latency_ms"] = telemetry.get("latency_ms", 10.0) * 50.0
        mutated_telemetry["status"] = "ERROR_UNOBSERVED_CONFOUNDER"
        return mutated_telemetry


class CyclicPoisoner:
    """Simulates an adversarial cycle where the Generator's output poisons
    the Vector DB used by the Retriever, violating DAG acyclicity.
    """

    def __init__(self, target_retriever: Any):
        # target_retriever is a reference to a mock/in-memory DB
        self.target_retriever = target_retriever
        self.is_active = False

    def trigger_cycle(self) -> None:
        """Activates the adversarial cycle."""
        self.is_active = True

    def poison_on_generation(self, generated_text: str) -> None:
        """
        Write the generated text back into the retriever's index,
        creating a causal loop for the next query.
        """
        if self.is_active:
            # Assume target_retriever has an add_document or similar method
            if hasattr(self.target_retriever, "add_document"):
                self.target_retriever.add_document(
                    doc_id="poisoned_doc", content=f"POISONED FEEDBACK: {generated_text}"
                )
