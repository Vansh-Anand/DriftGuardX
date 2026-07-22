"""
DriftGuard-X v2 — Replay Planner
PRIVATE — All Rights Reserved.
"""
import asyncio
from typing import List
from uuid import UUID

from packages.contracts.src.models import ComponentType, Intervention, ReplayEpisode, ReplayStatus


class ReplayPlanner:
    """
    Plans and schedules counterfactual replays for candidate interventions.
    """
    
    def __init__(self, max_concurrency: int = 5, timeout_sec: int = 30):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.timeout_sec = timeout_sec
        self.budget_exhausted = False
        self._seen_signatures = set()

    async def execute_exhaustive(self, candidates: List[Intervention]) -> List[ReplayEpisode]:
        """
        Executes an exhaustive replay across all candidates (gold standard).
        """
        tasks = []
        for candidate in candidates:
            # Deduplication
            sig = f"{candidate.target_component_type}_{candidate.to_version_id}"
            if sig in self._seen_signatures:
                continue
            self._seen_signatures.add(sig)
            
            tasks.append(self._run_with_timeout(candidate))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        episodes = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Exception during replay: {result}")
                continue
            if isinstance(result, ReplayEpisode):
                episodes.append(result)
            else:
                print(f"Result is not an Exception or ReplayEpisode: {type(result)} {result}")
                
        return episodes

    async def _run_with_timeout(self, candidate: Intervention) -> ReplayEpisode:
        """
        Wrapper to run a single candidate with timeout and concurrency bounds.
        """
        async with self.semaphore:
            if self.budget_exhausted:
                return self._create_invalid(candidate, "Budget Exhausted")
                
            try:
                # asyncio.wait_for wraps the worker execution
                return await asyncio.wait_for(self._worker_stub(candidate), timeout=self.timeout_sec)
            except asyncio.TimeoutError:
                return self._create_invalid(candidate, "Timeout")
            except Exception as e:
                return self._create_invalid(candidate, f"Error: {str(e)}")
                
    async def _worker_stub(self, candidate: Intervention) -> ReplayEpisode:
        """
        Stub for the actual sandbox worker.
        """
        await asyncio.sleep(0.1)  # simulate work
        
        # Simulate invalidity due to missing artifact
        if candidate.to_version_tag == "missing":
            return self._create_invalid(candidate, "Missing Artifact")
            
        episode = ReplayEpisode(
            tenant_id=candidate.tenant_id,
            run_id=candidate.run_id,
            status=ReplayStatus.COMPLETED,
            swapped_component_type=ComponentType(candidate.target_component_type),
            original_version_id=candidate.from_version_id,
            replay_version_id=candidate.to_version_id,
            original_version_tag=candidate.from_version_tag,
            replay_version_tag=candidate.to_version_tag,
            # Mocking a slight reliability improvement
            original_reliability_score=0.80,
            replay_reliability_score=0.90,
            reliability_improvement=0.10
        )
        return episode

    def _create_invalid(self, candidate: Intervention, reason: str) -> ReplayEpisode:
        return ReplayEpisode(
            tenant_id=candidate.tenant_id,
            run_id=candidate.run_id,
            status=ReplayStatus.INVALID,
            invalid_reason=reason,
            swapped_component_type=ComponentType(candidate.target_component_type),
            original_version_id=candidate.from_version_id,
            replay_version_id=candidate.to_version_id,
            original_version_tag=candidate.from_version_tag,
            replay_version_tag=candidate.to_version_tag
        )
