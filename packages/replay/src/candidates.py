"""
DriftGuard-X v2 — Candidate Generation
PRIVATE — All Rights Reserved.
"""
from uuid import UUID

from packages.contracts.src.models import ComponentType, Diagnosis, Intervention, InterventionType
from packages.replay.src.catalog import InterventionCatalog


class CandidateGenerator:
    """
    Generates viable intervention candidates based on a Diagnosis and the Graph.
    """

    @staticmethod
    def generate(diagnosis: Diagnosis) -> list[Intervention]:
        """
        Generate candidates covering root causes and diffusion symptoms.
        """
        candidates = []
        catalog = InterventionCatalog.get_catalog()

        # We target the root cause component specifically
        target_component = diagnosis.root_cause_component
        if not target_component:
            return []

        schemas = catalog.get(ComponentType(target_component), [])
        for schema in schemas:
            # Generate an unapplied Intervention proposal
            intervention = Intervention(
                run_id=diagnosis.run_id,
                tenant_id=diagnosis.tenant_id,
                intervention_type=InterventionType(schema.intervention_type),
                target_component_type=ComponentType(target_component),
                from_version_id=UUID(int=0),  # Placeholder: actual version fetched in planner
                to_version_id=UUID(int=1),    # Placeholder: safe alternative version
                from_version_tag="current",
                to_version_tag="proposed_safe_alt",
                rationale=f"Generated from schema: {schema.description}",
                requires_human_approval=len(schema.required_approvals) > 0
            )
            candidates.append(intervention)

        return candidates
