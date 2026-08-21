"""
DriftGuard-X v2 — Deterministic Replay Engine

Executes a version-pinned replay of a prior run:
1. Loads the original run and its span trace
2. Swaps exactly one component version (e.g., retriever v2 → v1)
3. Pins all other component versions to the original run's versions
4. Re-executes the deterministic mock pipeline
5. Computes before/after reliability vectors
6. Stores the ReplayEpisode (never mutates production state)

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from packages.contracts.src.models import (
    ComponentType,
    ComponentVersion,
    ComponentVersionState,
    Intervention,
    InterventionType,
    ReplayEpisode,
    ReplayStatus,
    RequestRun,
    RunStatus,
    SpanRecord,
    TraceArtifact,
)
from packages.evaluation.src.reliability import (
    aggregate_reliability_score,
    compute_reliability_delta,
    compute_reliability_vector,
)
from packages.trace_sdk.src.tracer import TraceContext, hash_payload


# ─── Version Registry ─────────────────────────────────────────────────────────

class VersionRegistry:
    """
    Registry of all known component versions.
    In Prompt 01: purely in-memory deterministic registry.
    """

    def __init__(self) -> None:
        self._versions: dict[UUID, ComponentVersion] = {}

    def register(self, cv: ComponentVersion) -> None:
        self._versions[cv.id] = cv

    def get(self, version_id: UUID) -> ComponentVersion | None:
        return self._versions.get(version_id)

    def get_by_type_and_tag(
        self, component_type: ComponentType, version_tag: str
    ) -> ComponentVersion | None:
        for cv in self._versions.values():
            if cv.component_type == component_type and cv.version_tag == version_tag:
                return cv
        return None

    def list_by_type(self, component_type: ComponentType) -> list[ComponentVersion]:
        return [cv for cv in self._versions.values() if cv.component_type == component_type]


# ─── Component Executor Interface ─────────────────────────────────────────────

class ComponentExecutor:
    """
    Interface for executing a pipeline component.
    All implementations must be deterministic given the same input + seed.
    """

    def execute(
        self,
        inputs: dict[str, Any],
        *,
        version: ComponentVersion,
        seed: int = 42,
    ) -> dict[str, Any]:
        raise NotImplementedError


# ─── Mock Component Executors (Prompt 01) ─────────────────────────────────────

class MockRetrieverV1(ComponentExecutor):
    """Stable retriever — returns fresh, accurate documents."""

    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        query = inputs.get("query", "")
        return {
            "documents": [
                {"id": "doc-001", "text": f"[FRESH] Accurate document for: {query}", "score": 0.92},
                {"id": "doc-002", "text": f"[FRESH] Supporting document for: {query}", "score": 0.87},
            ],
            "retriever_version": version.version_tag,
            "is_stale": False,
            "faithfulness_hint": 0.90,
        }


class MockRetrieverV2Experimental(ComponentExecutor):
    """
    Experimental retriever v2 — KNOWN ISSUE: returns stale evidence.
    This is the component that triggers the golden demo reliability failure.
    """

    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        query = inputs.get("query", "")
        return {
            "documents": [
                {"id": "doc-old-001", "text": f"[STALE-2021] Outdated document for: {query}", "score": 0.61},
                {"id": "doc-old-002", "text": f"[STALE-2020] Deprecated content for: {query}", "score": 0.55},
            ],
            "retriever_version": version.version_tag,
            "is_stale": True,
            "faithfulness_hint": 0.35,  # LOW — triggers reliability failure
        }


class MockRerankerV1(ComponentExecutor):
    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        docs = inputs.get("documents", [])
        # Deterministic sort by score desc
        sorted_docs = sorted(docs, key=lambda d: d.get("score", 0), reverse=True)
        return {"ranked_documents": sorted_docs, "reranker_version": version.version_tag}


class MockGeneratorV1(ComponentExecutor):
    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        docs = inputs.get("ranked_documents", [])
        query = inputs.get("query", "")
        context = " | ".join(d.get("text", "") for d in docs[:2])
        is_stale = any("STALE" in d.get("text", "") for d in docs)
        return {
            "response": f"Based on retrieved context: {context[:200]}",
            "is_stale_context": is_stale,
            "faithfulness_score": 0.35 if is_stale else 0.90,
            "token_count_input": 128,
            "token_count_output": 64,
            "generator_version": version.version_tag,
        }


class MockMemoryReadV1(ComponentExecutor):
    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        partition_id = inputs.get("partition_id", "default_partition")
        requester_role = inputs.get("requester_role", "agent")
        tenant_id = inputs.get("tenant_id", "default_tenant")
        from packages.memory.src.store import global_provenance_store
        
        entries = global_provenance_store.read(partition_id, tenant_id=tenant_id, requester_role=requester_role)
        return {"memory_entries": entries, "memory_read_version": version.version_tag}


class MockMemoryWriteV1(ComponentExecutor):
    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        # Never mutates persistent state in prototype
        return {"written": False, "reason": "memory_write disabled in prototype", "memory_write_version": version.version_tag}


class MockToolCallV1(ComponentExecutor):
    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        return {"tool_result": None, "tool_called": False, "tool_call_version": version.version_tag}


class MockPolicyCheckV1(ComponentExecutor):
    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        return {"policy_result": "allow", "policy_rule": "ALLOW_SYNTHETIC_READ", "policy_check_version": version.version_tag}


class MockFinalResponseV1(ComponentExecutor):
    def execute(self, inputs: dict[str, Any], *, version: ComponentVersion, seed: int = 42) -> dict[str, Any]:
        return {
            "final_response": inputs.get("response", ""),
            "faithfulness_score": inputs.get("faithfulness_score", 0.5),
            "final_response_version": version.version_tag,
        }


# ─── Executor Registry ────────────────────────────────────────────────────────

_EXECUTOR_MAP: dict[tuple[str, str], ComponentExecutor] = {
    (ComponentType.RETRIEVER, "v1"): MockRetrieverV1(),
    (ComponentType.RETRIEVER, "v2-exp"): MockRetrieverV2Experimental(),
    (ComponentType.RERANKER, "v1"): MockRerankerV1(),
    (ComponentType.GENERATOR, "v1"): MockGeneratorV1(),
    (ComponentType.MEMORY_READ, "v1"): MockMemoryReadV1(),
    (ComponentType.MEMORY_WRITE, "v1"): MockMemoryWriteV1(),
    (ComponentType.TOOL_CALL, "v1"): MockToolCallV1(),
    (ComponentType.POLICY_CHECK, "v1"): MockPolicyCheckV1(),
    (ComponentType.FINAL_RESPONSE, "v1"): MockFinalResponseV1(),
}


def get_executor(component_type: ComponentType, version_tag: str) -> ComponentExecutor:
    key = (component_type, version_tag)
    executor = _EXECUTOR_MAP.get(key)
    if executor is None:
        raise ValueError(f"No executor for {component_type}:{version_tag}")
    return executor


# ─── Replay Engine ────────────────────────────────────────────────────────────

class ReplayEngine:
    """
    Executes deterministic version-pinned replays.

    Safety contract:
    - Never mutates production state
    - All other component versions are pinned to original run
    - Replay is recorded as ReplayEpisode but NOT applied
    """

    def __init__(self, version_registry: VersionRegistry) -> None:
        self._registry = version_registry

    def execute_replay(
        self,
        *,
        original_run: RequestRun,
        original_trace: TraceArtifact,
        intervention: Intervention,
        replay_version: ComponentVersion,
        original_reliability_vector: dict[str, float],
        request_inputs: dict[str, Any],
        seed: int = 42,
    ) -> tuple[ReplayEpisode, TraceArtifact]:
        """
        Execute a deterministic replay with one component version swapped.

        Returns (ReplayEpisode, new TraceArtifact) — does NOT persist automatically.
        Caller is responsible for persistence.
        """
        replay_id = uuid4()
        tenant_id = original_run.tenant_id
        pipeline_id = original_run.pipeline_id

        # Build pinned version map from original trace
        pinned_versions: dict[str, str] = {}
        for span in original_trace.spans:
            if span.component_type and span.component_version_id:
                ct = str(span.component_type)
                if ct != str(intervention.target_component_type):
                    pinned_versions[ct] = str(span.component_version_id)

        # Create TraceContext for replay
        ctx = TraceContext(
            tenant_id=tenant_id,
            pipeline_id=pipeline_id,
            run_id=replay_id,
        )

        # Execute pipeline with swapped component
        pipeline_order = [
            ComponentType.MEMORY_READ,
            ComponentType.RETRIEVER,
            ComponentType.RERANKER,
            ComponentType.GENERATOR,
            ComponentType.TOOL_CALL,
            ComponentType.POLICY_CHECK,
            ComponentType.MEMORY_WRITE,
            ComponentType.FINAL_RESPONSE,
        ]

        current_inputs = dict(request_inputs)
        if "tenant_id" not in current_inputs:
            current_inputs["tenant_id"] = str(tenant_id)
        if "partition_id" not in current_inputs:
            current_inputs["partition_id"] = f"{tenant_id}_{replay_id}"
            
        all_spans: list[SpanRecord] = []
        root_span_id: str | None = None

        # Root span
        root_builder = ctx.start_span("replay_pipeline", parent_span_id=None)
        root_span_id = root_builder.span_id

        faithfulness_score: float = 1.0

        for component_type in pipeline_order:
            # Determine which version to use
            if component_type == intervention.target_component_type:
                cv = replay_version
            else:
                # Use original version from pinned map
                original_span = next(
                    (s for s in original_trace.spans if s.component_type == component_type),
                    None,
                )
                if original_span and original_span.component_version_id:
                    cv_obj = self._registry.get(original_span.component_version_id)
                    cv = cv_obj if cv_obj else replay_version  # fallback
                else:
                    continue  # skip components not in original

            executor = get_executor(component_type, cv.version_tag)

            # Time and execute with strict timeout enforcement
            start = datetime.now(timezone.utc)
            try:
                import concurrent.futures
                
                # Execute with a strict 30-second bounded timeout to prevent Replay DoS
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as tp:
                    future = tp.submit(executor.execute, current_inputs, version=cv, seed=seed)
                    output = future.result(timeout=30.0)
                    
                # Enforce payload size limit (e.g., 5MB roughly 5_000_000 chars of string repr)
                if len(str(output)) > 5_000_000:
                    raise MemoryError("Component output exceeded resource bounds")
                    
                error_type = None
                error_msg = None
            except concurrent.futures.TimeoutError:
                output = {}
                error_type = "TimeoutError"
                error_msg = "Execution exceeded hard timeout limit (30.0s)"
            except Exception as e:
                output = {}
                error_type = type(e).__name__
                error_msg = str(e)
            finally:
                end = datetime.now(timezone.utc)

            # Build span
            builder = ctx.start_span(
                f"{component_type.value}/{cv.version_tag}",
                parent_span_id=root_span_id,
            )
            builder.set_component(component_type, cv.id, cv.version_tag)
            builder.set_input(current_inputs)
            builder.set_output(output)

            latency = (end - start).total_seconds() * 1000
            builder._start_time = start
            builder._end_time = end
            builder._latency_ms = latency

            if error_type:
                builder.set_error(error_type, error_msg or "")
            else:
                builder._status_code = "OK"

            # Track tokens for generator
            if component_type == ComponentType.GENERATOR:
                builder.set_tokens(
                    output.get("token_count_input", 0),
                    output.get("token_count_output", 0),
                )
                faithfulness_score = float(output.get("faithfulness_score", 1.0))

            if component_type == ComponentType.POLICY_CHECK:
                builder.set_policy(output.get("policy_result", "allow"))

            span = builder.build()
            all_spans.append(span)

            # Pass outputs to next component
            current_inputs = {**current_inputs, **output}

        # Finish root span
        root_builder._end_time = datetime.now(timezone.utc)
        root_builder._latency_ms = (
            (root_builder._end_time - root_builder._start_time).total_seconds() * 1000
        )
        root_builder._status_code = "OK"
        root_span = root_builder.build()
        all_spans.insert(0, root_span)

        # Build replay trace
        replay_trace = TraceArtifact(
            run_id=replay_id,
            tenant_id=tenant_id,
            pipeline_id=pipeline_id,
            spans=all_spans,
            root_span_id=root_span.span_id,
        )

        # Compute reliability vectors
        replay_vector = compute_reliability_vector(
            replay_trace, faithfulness_score=faithfulness_score
        )
        replay_score = aggregate_reliability_score(replay_vector)
        delta = compute_reliability_delta(original_reliability_vector, replay_vector)

        original_score = aggregate_reliability_score(original_reliability_vector)

        # Build ReplayEpisode
        episode = ReplayEpisode(
            replay_id=replay_id,
            run_id=original_run.id,
            tenant_id=tenant_id,
            swapped_component_type=ComponentType(replay_version.component_type),
            original_version_id=intervention.from_version_id,
            replay_version_id=intervention.to_version_id,
            original_version_tag=intervention.from_version_tag,
            replay_version_tag=intervention.to_version_tag,
            pinned_version_ids=pinned_versions,
            original_reliability_vector=original_reliability_vector,
            replay_reliability_vector=replay_vector,
            reliability_delta=delta,
            original_reliability_score=original_score,
            replay_reliability_score=replay_score,
            reliability_improvement=round(replay_score - original_score, 4),
            original_request_hash=original_run.request_hash,
            replay_response_hash=hash_payload(current_inputs.get("final_response", "")),
            seed=seed,
            completed_at=datetime.now(timezone.utc),
            is_synthetic=original_run.is_synthetic,
            status=ReplayStatus.COMPLETED,
        )

        return episode, replay_trace
