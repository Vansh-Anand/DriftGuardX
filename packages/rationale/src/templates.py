"""
DriftGuard-X v2 — Deterministic Rationale Templates
PRIVATE — All Rights Reserved.

Provides fully deterministic fallback rationale text generation.
These templates must be complete enough for operation without any LLM.
"""
from packages.rationale.src.models import RationaleInputContract, RationaleOutput, RationaleStyle


def format_metrics(metrics: dict[str, float]) -> str:
    if not metrics:
        return "None"
    return ", ".join(f"{k}: {v:+.4f}" for k, v in metrics.items())


def format_limitations(limitations: list[str]) -> str:
    if not limitations:
        return "None"
    return "; ".join(limitations)


def generate_operator_summary(contract: RationaleInputContract) -> str:
    cert_status = "CERTIFIED" if contract.is_certified else "UNCERTIFIED"
    bound_info = f"(Bound: {contract.bound_method}, epsilon={contract.epsilon}, delta={contract.delta})" if contract.bound_method else ""
    return (
        f"[Diagnosis] Root cause localized to component `{contract.ranked_cause_component}` "
        f"(Path: {' -> '.join(contract.symptom_to_cause_path)}).\n"
        f"[Evidence] Replay Episode `{contract.replay_episode_id}` shifted version `{contract.original_version_tag}` "
        f"to `{contract.replay_version_tag}`, yielding metric deltas: {format_metrics(contract.metric_deltas)}.\n"
        f"[Policy] Status is {cert_status} {bound_info}. Decision: `{contract.policy_decision}`. "
        f"Action triggered: `{contract.action_type}`.\n"
        f"[Limitations] {format_limitations(contract.limitations)}"
    )


def generate_executive_summary(contract: RationaleInputContract) -> str:
    cert_status = "certified" if contract.is_certified else "uncertified (requires review)"
    return (
        f"The system detected an issue originating in the {contract.ranked_cause_component} component. "
        f"By reverting from {contract.original_version_tag} to {contract.replay_version_tag}, "
        f"metrics improved ({format_metrics(contract.metric_deltas)}). "
        f"This repair is {cert_status}, resulting in policy decision: {contract.policy_decision} ({contract.action_type})."
    )


def generate_incident_ticket(contract: RationaleInputContract) -> str:
    cert_status = "CERTIFIED" if contract.is_certified else "UNCERTIFIED"
    return (
        f"INCIDENT TICKET\n"
        f"-----------------\n"
        f"Run ID: {contract.run_id}\n"
        f"Root Cause: {contract.ranked_cause_component}\n"
        f"Detail: {contract.root_cause_description}\n"
        f"Replay ID: {contract.replay_episode_id}\n"
        f"Versions: {contract.original_version_tag} -> {contract.replay_version_tag}\n"
        f"Deltas: {format_metrics(contract.metric_deltas)}\n"
        f"Certification: {cert_status}\n"
        f"Policy Action: {contract.action_type} ({contract.policy_decision})\n"
        f"Limitations: {format_limitations(contract.limitations)}"
    )


def generate_patent_note(contract: RationaleInputContract) -> str:
    return (
        f"EXPERIMENT RECORD (CONFIDENTIAL)\n"
        f"Method: Bounded counterfactual replay applied to graph path [{' -> '.join(contract.symptom_to_cause_path)}].\n"
        f"Intervention: Component {contract.ranked_cause_component} variant {contract.original_version_tag} replaced by {contract.replay_version_tag}.\n"
        f"Observation: {format_metrics(contract.metric_deltas)}.\n"
        f"Bounding: Method={contract.bound_method}, E={contract.epsilon}, D={contract.delta}.\n"
        f"Note: This does not constitute a claim of global safety or legal compliance."
    )


def generate_template_rationale(contract: RationaleInputContract, style: RationaleStyle) -> RationaleOutput:
    """Generates the requested deterministic template for the input contract."""
    content = ""
    if style == RationaleStyle.OPERATOR_SUMMARY:
        content = generate_operator_summary(contract)
    elif style == RationaleStyle.EXECUTIVE_SUMMARY:
        content = generate_executive_summary(contract)
    elif style == RationaleStyle.INCIDENT_TICKET:
        content = generate_incident_ticket(contract)
    elif style == RationaleStyle.PATENT_NOTE:
        content = generate_patent_note(contract)
    else:
        content = generate_operator_summary(contract)

    return RationaleOutput(
        input_contract_id=contract.id,
        style=style,
        content=content,
        is_llm_generated=False,
        fallback_triggered=True,
    )
