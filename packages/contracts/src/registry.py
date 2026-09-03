"""
DriftGuard-X v2 — Version Registry Interface
PRIVATE — All Rights Reserved.
"""

from abc import ABC, abstractmethod
from uuid import UUID

from packages.contracts.src.models import ComponentType, ComponentVersion


class VersionRegistry(ABC):
    """
    Interface for the Versioned State Registry containing configuration,
    artifact hashes, deployment time, compatibility, and rollback pointers.
    """

    @abstractmethod
    async def get_version(self, tenant_id: UUID, version_id: UUID) -> ComponentVersion | None:
        """Retrieve a specific component version by ID."""
        pass

    @abstractmethod
    async def get_latest_stable_version(
        self, tenant_id: UUID, component_type: ComponentType, component_name: str
    ) -> ComponentVersion | None:
        """Retrieve the latest stable version for a component."""
        pass

    @abstractmethod
    async def list_versions(
        self, tenant_id: UUID, component_type: ComponentType, component_name: str
    ) -> list[ComponentVersion]:
        """List all versions of a specific component."""
        pass

    @abstractmethod
    async def register_version(
        self, tenant_id: UUID, version: ComponentVersion
    ) -> ComponentVersion:
        """Register a new component version."""
        pass

    @abstractmethod
    async def mark_state(
        self, tenant_id: UUID, version_id: UUID, state: str, rollback_pointer: UUID | None = None
    ) -> ComponentVersion:
        """Transition a version to a new lifecycle state."""
        pass
