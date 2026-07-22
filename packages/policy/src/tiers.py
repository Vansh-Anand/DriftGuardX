"""
DriftGuard-X v2 — Risk Tier Registry
PRIVATE — All Rights Reserved.

Maps every DriftGuard-X action to a risk tier (LOW/MEDIUM/HIGH/CRITICAL).

Tier Definitions:
  LOW      — Read-only, diagnostic, or non-mutating actions.
  MEDIUM   — Controlled mutations in sandboxed/staging environments.
  HIGH     — Production mutations; require at least one human approver.
  CRITICAL — Irreversible or safety-critical; require two-person control.
"""
from __future__ import annotations

from packages.policy.src.hierarchy import RiskTier

# ─── Action → Risk Tier Map ───────────────────────────────────────────────────

ACTION_TIER_MAP: dict[str, RiskTier] = {

    # ── LOW: Read-only ─────────────────────────────────────────────────────────
    "read_trace":                RiskTier.LOW,
    "list_runs":                 RiskTier.LOW,
    "get_run":                   RiskTier.LOW,
    "get_replay":                RiskTier.LOW,
    "read_diagnosis":            RiskTier.LOW,
    "health_check":              RiskTier.LOW,
    "ingest_spans":              RiskTier.LOW,
    "create_run":                RiskTier.LOW,   # synthetic/mock
    "list_candidates":           RiskTier.LOW,
    "get_certificate":           RiskTier.LOW,
    "read_policy":               RiskTier.LOW,
    "shadow_evaluate_policy":    RiskTier.LOW,
    "view_approval_queue":       RiskTier.LOW,

    # ── MEDIUM: Controlled mutations ──────────────────────────────────────────
    "create_replay":             RiskTier.MEDIUM,
    "schedule_replay":           RiskTier.MEDIUM,
    "cancel_replay":             RiskTier.MEDIUM,
    "mutate_staging_kb":         RiskTier.MEDIUM,
    "create_intervention":       RiskTier.MEDIUM,
    "submit_diagnosis":          RiskTier.MEDIUM,
    "request_approval":          RiskTier.MEDIUM,
    "approve_action":            RiskTier.MEDIUM,
    "deny_action":               RiskTier.MEDIUM,

    # ── HIGH: Production mutations (require 1 human approver) ─────────────────
    "apply_intervention":        RiskTier.HIGH,
    "apply_repair_decision":     RiskTier.HIGH,
    "apply_rollback":            RiskTier.HIGH,
    "promote_component_version": RiskTier.HIGH,
    "update_policy":             RiskTier.HIGH,
    "activate_policy":           RiskTier.HIGH,
    "revoke_certificate":        RiskTier.HIGH,
    "flush_cache":               RiskTier.HIGH,
    "update_model_config":       RiskTier.HIGH,

    # ── CRITICAL: Two-person control required ─────────────────────────────────
    "delete_memory":             RiskTier.CRITICAL,
    "mutate_production_kb":      RiskTier.CRITICAL,
    "grant_permissions":         RiskTier.CRITICAL,
    "execute_arbitrary_shell":   RiskTier.CRITICAL,
    "modify_external_system":    RiskTier.CRITICAL,
    "publish_source_code":       RiskTier.CRITICAL,
    "delete_trace":              RiskTier.CRITICAL,
    "overwrite_experiment":      RiskTier.CRITICAL,
    "deactivate_safety_gate":    RiskTier.CRITICAL,
    "break_glass_override":      RiskTier.CRITICAL,
}

# ─── Approval Requirements by Tier ───────────────────────────────────────────

TIER_APPROVAL_REQUIREMENTS: dict[RiskTier, dict] = {
    RiskTier.LOW: {
        "required_approvers": 0,
        "two_person_control": False,
        "auto_approve": True,
    },
    RiskTier.MEDIUM: {
        "required_approvers": 1,
        "two_person_control": False,
        "auto_approve": False,
    },
    RiskTier.HIGH: {
        "required_approvers": 1,
        "two_person_control": True,    # approver != requester
        "auto_approve": False,
    },
    RiskTier.CRITICAL: {
        "required_approvers": 2,
        "two_person_control": True,
        "auto_approve": False,
    },
}


def get_tier(action: str) -> RiskTier:
    """
    Return the risk tier for a given action.
    Unknown actions default to HIGH (conservative).
    """
    return ACTION_TIER_MAP.get(action.lower(), RiskTier.HIGH)


def get_approval_requirements(action: str) -> dict:
    """Return the approval requirements dict for a given action."""
    tier = get_tier(action)
    return TIER_APPROVAL_REQUIREMENTS[tier]
