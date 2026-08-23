"""
DriftGuard-X v2 — Causal Recovery Feature Configuration

A single structured configuration object for all causal-recovery mechanism flags.
This replaces ad-hoc environment variable checks scattered throughout the codebase.

Design constraints
------------------
- Defaults are fail-safe (strict_mode=True, all mechanisms disabled by default).
- Config must be explicitly constructed and injected — no global singleton.
- schema_version enables forward-compatibility checks by the verifier.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

from pydantic import Field, model_validator

from packages.contracts.src.models import DGXBaseModel

_CONFIG_SCHEMA_VERSION = "1.0"


class CausalRecoveryConfig(DGXBaseModel):
    """
    Feature flags and configuration for the three causal recovery mechanisms.

    All mechanisms default to DISABLED.  Enable only after the shared typed
    foundation has been validated in your environment.

    Fields
    ------
    replay_equivalence_enabled
        If True, activates the Replay Equivalence Envelope computation.
        Requires ExecutionStateSnapshot to be captured for every run.

    divergence_frontier_enabled
        If True, activates the Dynamic Causal Divergence Frontier tracker.
        Requires replay_equivalence_enabled=True.

    sequential_planner_enabled
        If True, activates the Risk-Limited Sequential Causal Experiment
        Planner and Evidentiary Stopping Rule.
        Requires the RAEB gateway to be configured.

    recovery_cut_enabled
        If True, activates the Minimum Causal Recovery Cut computation.
        Requires the CausalGraph to be built for each run.

    transportability_enabled
        If True, activates the Causal Recovery Transportability Gate.
        Requires recovery_cut_enabled=True.

    strict_mode
        If True (default), any unrecognised or mis-configured dependency causes
        a hard failure (fail-closed).  If False, degraded operation is permitted
        with warnings logged.  Do NOT disable in production.

    schema_version
        Version of this config schema.  Checked by the verifier before using
        any config-dependent computation path.
    """
    replay_equivalence_enabled: bool = False
    divergence_frontier_enabled: bool = False
    sequential_planner_enabled: bool = False
    recovery_cut_enabled: bool = False
    transportability_enabled: bool = False
    strict_mode: bool = True
    schema_version: str = Field(default=_CONFIG_SCHEMA_VERSION, min_length=1)

    @model_validator(mode="after")
    def validate_dependency_order(self) -> "CausalRecoveryConfig":
        """
        Enforce mechanism dependency ordering:
          divergence_frontier requires replay_equivalence
          transportability requires recovery_cut
        """
        if self.divergence_frontier_enabled and not self.replay_equivalence_enabled:
            raise ValueError(
                "divergence_frontier_enabled requires replay_equivalence_enabled=True"
            )
        if self.transportability_enabled and not self.recovery_cut_enabled:
            raise ValueError(
                "transportability_enabled requires recovery_cut_enabled=True"
            )
        return self

    @classmethod
    def safe_defaults(cls) -> "CausalRecoveryConfig":
        """Factory: all mechanisms off, strict mode on."""
        return cls()

    @classmethod
    def full_pipeline(cls) -> "CausalRecoveryConfig":
        """
        Factory: all mechanisms enabled with strict mode.
        For use in integration tests only — not for production without explicit review.
        """
        return cls(
            replay_equivalence_enabled=True,
            divergence_frontier_enabled=True,
            sequential_planner_enabled=True,
            recovery_cut_enabled=True,
            transportability_enabled=True,
            strict_mode=True,
        )
