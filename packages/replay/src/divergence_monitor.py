"""
DriftGuard-X v2 — Dynamic Causal Divergence Frontier Monitor

Observes the execution state during a counterfactual replay and compares
it against the validity boundary defined by the ReplayEquivalenceEnvelope.
Invalidates the replay immediately if any divergence escapes the
authorized causal frontier.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import logging
from typing import Optional

from packages.contracts.src.divergence import (
    CausalDivergenceReport,
    DivergenceObservation,
    DivergenceType,
)
from packages.contracts.src.envelope import (
    EquivalenceConstraintType,
    ReplayEquivalenceEnvelope,
)
from packages.contracts.src.exogenous import ExogenousReplayStrategy
from packages.contracts.src.execution_state import ExecutionStateValue

logger = logging.getLogger(__name__)


class DivergenceFrontierMonitor:
    """
    Stateful monitor for dynamic causal divergence during replay.

    Takes a sealed ReplayEquivalenceEnvelope and classifies arriving
    ExecutionStateValues from the replay engine. Stops the replay early
    if an unexpected divergence occurs.
    """

    def __init__(self, envelope: ReplayEquivalenceEnvelope):
        # Must verify integrity before trusting the boundary
        if not envelope.verify_integrity():
            raise ValueError(
                "Envelope integrity check failed. Cannot initialize divergence monitor."
            )
        self.envelope = envelope
        self.observations: list[DivergenceObservation] = []
        self.frontier_components: set[str] = set()
        self.escaped_components: set[str] = set()
        
        self._is_valid = True
        self._invalidation_reason: Optional[str] = None
        self._variables_checked = 0

        # Fast lookup indices
        self._frozen = set(envelope.frozen_variables)
        self._intervened = set(envelope.intervened_variables)
        self._allowed_descendants = set(envelope.allowed_descendant_components)
        self._forbidden_components = set(envelope.forbidden_divergence_components)
        self._nondeterministic = set(envelope.nondeterministic_variables)
        
        self._exogenous_strategies: dict[str, ExogenousReplayStrategy] = {
            ev.key: ev.replay_strategy for ev in envelope.exogenous_variables
        }
        self._constraints = {
            ec.variable_key: ec for ec in envelope.equivalence_constraints
        }

    @property
    def is_valid(self) -> bool:
        """Returns True if no unexpected divergence has been observed."""
        return self._is_valid

    def observe(
        self, original_value: Optional[ExecutionStateValue], replay_value: Optional[ExecutionStateValue]
    ) -> DivergenceObservation:
        """
        Compare an original value with the replay value and classify any divergence.

        If original_value is missing, we consider it MISSING_STATE.
        If replay_value is missing, we consider it UNVERIFIABLE.
        """
        self._variables_checked += 1

        # Use whichever key/component is available
        key = (original_value.key if original_value else None) or (replay_value.key if replay_value else "unknown")
        comp_id = (original_value.component_id if original_value else None) or (replay_value.component_id if replay_value else None)

        orig_hash = original_value.value_hash if original_value else None
        rep_hash = replay_value.value_hash if replay_value else None

        # 1. Missing evidence rules
        if not original_value:
            return self._record_and_return(
                key=key,
                comp_id=comp_id,
                orig_hash=orig_hash,
                rep_hash=rep_hash,
                divergence_type=DivergenceType.MISSING_STATE,
                explanation="Original state was not captured or provided."
            )

        if not replay_value:
            # Replay failed to produce a value that was originally captured
            return self._record_and_return(
                key=key,
                comp_id=comp_id,
                orig_hash=orig_hash,
                rep_hash=rep_hash,
                divergence_type=DivergenceType.UNVERIFIABLE,
                explanation="Replay state value was missing or not captured."
            )

        # Are they exactly equal?
        is_exact_match = orig_hash == rep_hash

        # 2. Intervened Variables
        if key in self._intervened:
            if is_exact_match:
                # Warning: An intervention that didn't change anything
                return self._record_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.EXPECTED_INTERVENTION,
                    explanation="Variable is the intervention target (but value did not change)."
                )
            return self._record_and_return(
                key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                divergence_type=DivergenceType.EXPECTED_INTERVENTION,
                explanation="Variable is the intervention target."
            )

        # 3. Exogenous Variables
        if key in self._exogenous_strategies:
            strat = self._exogenous_strategies[key]
            if is_exact_match:
                return self._record_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.PERMITTED_EXOGENOUS_CHANGE,
                    explanation=f"Exogenous variable ({strat}) matched exactly."
                )
            # Diverged exogenous
            if strat == ExogenousReplayStrategy.FORBID_REPLAY:
                return self._invalidate_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.UNEXPECTED_DIVERGENCE,
                    explanation="Exogenous variable diverged and is configured as FORBID_REPLAY."
                )
            # All other strategies permit the change as exogenous divergence
            return self._record_and_return(
                key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                divergence_type=DivergenceType.PERMITTED_EXOGENOUS_CHANGE,
                explanation=f"Exogenous divergence allowed by strategy {strat}."
            )

        # 4. Nondeterministic Variables
        if key in self._nondeterministic:
            if not is_exact_match:
                return self._record_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.PERMITTED_NONDETERMINISM,
                    explanation="Variable is explicitly marked nondeterministic."
                )

        # 5. Causal Descendants (Endogenous)
        if comp_id in self._allowed_descendants and key not in self._frozen:
            if not is_exact_match:
                if comp_id:
                    self.frontier_components.add(comp_id)
                return self._record_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.EXPECTED_CAUSAL_DESCENDANT,
                    explanation="Component is causally downstream of intervention."
                )

        # 6. Frozen / Constrained Variables
        # If it reaches here and doesn't match EXACTLY, we must check tolerance or invalidate
        if not is_exact_match:
            constraint = self._constraints.get(key)
            if not constraint:
                # No specific tolerance constraint and it's not an allowed descendant → INVALID
                return self._invalidate_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.UNEXPECTED_DIVERGENCE,
                    explanation="Variable is frozen but diverged with no tolerance defined."
                )
            
            c_type_str = constraint.constraint_type.value if hasattr(constraint.constraint_type, "value") else str(constraint.constraint_type)
            # Evaluate constraint
            if constraint.constraint_type == EquivalenceConstraintType.EXACT_HASH:
                return self._invalidate_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.UNEXPECTED_DIVERGENCE,
                    constraint_used=c_type_str,
                    explanation="Strict exact_hash constraint violated."
                )
            elif constraint.constraint_type == EquivalenceConstraintType.TOLERANCE:
                # We would normally evaluate numeric values here.
                # For this implementation, if it's numeric tolerance, we would need the raw values, 
                # but we only have hashes. In a real system, the monitor gets raw state or 
                # the caller performs tolerance checking before calling observe.
                # Assuming the caller has handled it or we treat hash mismatch as failure for now
                # except we allow a hook.
                if original_value.metadata.get("raw_value") is not None and replay_value.metadata.get("raw_value") is not None:
                    try:
                        ov = float(original_value.metadata.get("raw_value"))
                        rv = float(replay_value.metadata.get("raw_value"))
                        tol = constraint.tolerance_value or 0.0
                        if abs(ov - rv) <= tol:
                            return self._record_and_return(
                                key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                                divergence_type=DivergenceType.PERMITTED_NONDETERMINISM,
                                constraint_used=c_type_str,
                                explanation=f"Divergence within numerical tolerance {tol}."
                            )
                    except (ValueError, TypeError):
                        pass

                return self._invalidate_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.UNEXPECTED_DIVERGENCE,
                    constraint_used=c_type_str,
                    explanation="Tolerance constraint violated or raw values unavailable."
                )
            else:
                # Other constraints (SEMANTIC_TOLERANCE, SET_EQUALITY) would be evaluated here.
                # If they fail or are unsupported purely by hash:
                return self._invalidate_and_return(
                    key=key, comp_id=comp_id, orig_hash=orig_hash, rep_hash=rep_hash,
                    divergence_type=DivergenceType.UNEXPECTED_DIVERGENCE,
                    constraint_used=c_type_str,
                    explanation=f"Constraint {c_type_str} failed."
                )

        # If it matched exactly and reached here, it's a frozen or unclassified variable that didn't diverge.
        # It's not a divergence observation, but we can log it if we want.
        # We don't need to return an observation for identical frozen state unless tracking all verified states.
        # But for completeness, we return an observation indicating it was verified.
        # To avoid blowing up the report, we return None or just return a dummy.
        # The prompt says "classify observed difference". No difference = no observation needed.
        return None

    def _record_and_return(self, **kwargs) -> DivergenceObservation:
        obs = DivergenceObservation(**kwargs)
        self.observations.append(obs)
        return obs

    def _invalidate_and_return(self, **kwargs) -> DivergenceObservation:
        obs = DivergenceObservation(**kwargs)
        self.observations.append(obs)
        self._is_valid = False
        
        comp_id = kwargs.get("comp_id")
        if comp_id:
            self.escaped_components.add(comp_id)
            
        reason = f"Divergence escaped at {kwargs.get('key')} ({kwargs.get('explanation')})"
        if not self._invalidation_reason:
            self._invalidation_reason = reason
        else:
            self._invalidation_reason += f" | {reason}"
            
        logger.warning(reason)
        return obs

    def generate_report(self) -> CausalDivergenceReport:
        """
        Generate the final cryptographically bound report.
        """
        return CausalDivergenceReport(
            envelope_id=self.envelope.envelope_id,
            replay_id=self.envelope.replay_id,
            observations=self.observations,
            frontier_components=sorted(self.frontier_components),
            escaped_components=sorted(self.escaped_components),
            valid=self._is_valid,
            invalidation_reason=self._invalidation_reason,
        )
