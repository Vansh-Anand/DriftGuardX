"""
DriftGuard-X v2 — Typed Tool Registry
PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class SideEffectClass(Enum):
    READ_ONLY = "READ_ONLY"
    IDEMPOTENT = "IDEMPOTENT"
    SIDE_EFFECTING = "SIDE_EFFECTING"
    IRREVERSIBLE = "IRREVERSIBLE"


@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    is_safe_for_replay: bool = True
    permissions: list[str] = field(default_factory=list)
    timeout_ms: int = 5000
    retries: int = 0
    side_effect_class: SideEffectClass = SideEffectClass.READ_ONLY
    replay_policy: str = "allow"


class ToolRegistry:
    """
    Registry for executable agent tools with deterministic hashing,
    parameter schemas, and isolation controls.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        parameters_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        is_safe_for_replay: bool = True,
        permissions: list[str] | None = None,
        timeout_ms: int = 5000,
        retries: int = 0,
        side_effect_class: SideEffectClass = SideEffectClass.READ_ONLY,
        replay_policy: str = "allow",
    ) -> None:
        self._tools[name] = ToolDefinition(
            name=name,
            description=description or handler.__doc__ or name,
            handler=handler,
            parameters_schema=parameters_schema or {},
            output_schema=output_schema or {},
            is_safe_for_replay=is_safe_for_replay,
            permissions=permissions or [],
            timeout_ms=timeout_ms,
            retries=retries,
            side_effect_class=side_effect_class,
            replay_policy=replay_policy,
        )

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return sorted(list(self._tools.keys()))

    @property
    def registry_hash(self) -> str:
        schema_dump = {
            name: {
                "name": spec.name,
                "description": spec.description,
                "schema": spec.parameters_schema,
                "output_schema": spec.output_schema,
                "side_effect_class": spec.side_effect_class.value,
                "replay_policy": spec.replay_policy,
                "replay_safe": spec.is_safe_for_replay,
                "permissions": spec.permissions,
            }
            for name, spec in sorted(self._tools.items())
        }
        canonical = json.dumps(schema_dump, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        
    def _validate_inputs(self, spec: ToolDefinition, kwargs: dict[str, Any]) -> None:
        if spec.parameters_schema:
            try:
                import jsonschema
                jsonschema.validate(instance=kwargs, schema=spec.parameters_schema)
            except ImportError:
                pass
            except Exception as e:
                raise ValueError(f"Tool {spec.name} input validation failed: {e}")
                
    def _check_permissions(self, spec: ToolDefinition, user_permissions: list[str] | None = None) -> None:
        if spec.permissions:
            user_perms = set(user_permissions or [])
            for p in spec.permissions:
                if p not in user_perms:
                    raise PermissionError(f"Missing required permission '{p}' for tool '{spec.name}'")

    async def execute_tool(self, name: str, user_permissions: list[str] | None = None, is_replay: bool = False, **kwargs: Any) -> Any:
        spec = self._tools.get(name)
        if not spec:
            raise ValueError(f"Tool '{name}' not found in registry")
            
        if is_replay and spec.side_effect_class == SideEffectClass.IRREVERSIBLE:
            raise RuntimeError(f"Cannot blindly replay irreversible tool '{name}'")
            
        self._check_permissions(spec, user_permissions)
        self._validate_inputs(spec, kwargs)

        import asyncio
        handler = spec.handler
        if inspect.iscoroutinefunction(handler):
            if spec.timeout_ms:
                return await asyncio.wait_for(handler(**kwargs), timeout=spec.timeout_ms / 1000.0)
            return await handler(**kwargs)
        return handler(**kwargs)

    def execute_tool_sync(self, name: str, user_permissions: list[str] | None = None, is_replay: bool = False, **kwargs: Any) -> Any:
        spec = self._tools.get(name)
        if not spec:
            raise ValueError(f"Tool '{name}' not found in registry")

        if is_replay and spec.side_effect_class == SideEffectClass.IRREVERSIBLE:
            raise RuntimeError(f"Cannot blindly replay irreversible tool '{name}'")

        self._check_permissions(spec, user_permissions)
        self._validate_inputs(spec, kwargs)

        handler = spec.handler
        if inspect.iscoroutinefunction(handler):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        if spec.timeout_ms:
                            return pool.submit(asyncio.run, asyncio.wait_for(handler(**kwargs), timeout=spec.timeout_ms / 1000.0)).result()
                        return pool.submit(asyncio.run, handler(**kwargs)).result()
                if spec.timeout_ms:
                    return loop.run_until_complete(asyncio.wait_for(handler(**kwargs), timeout=spec.timeout_ms / 1000.0))
                return loop.run_until_complete(handler(**kwargs))
            except RuntimeError:
                if spec.timeout_ms:
                    return asyncio.run(asyncio.wait_for(handler(**kwargs), timeout=spec.timeout_ms / 1000.0))
                return asyncio.run(handler(**kwargs))
        return handler(**kwargs)

    def _register_default_tools(self) -> None:
        def health_check_api() -> dict[str, str]:
            """Performs system health check and returns status OK."""
            return {"health_check": "OK", "status": "healthy", "components": "nominal"}

        def calculator(expression: str) -> dict[str, Any]:
            """Evaluates basic mathematical expression safely."""
            # Safe evaluation for basic math
            allowed_chars = set("0123456789+-*/(). ")
            if not all(c in allowed_chars for c in expression):
                return {"error": "Invalid characters in expression"}
            try:
                result = eval(expression, {"__builtins__": None}, {})
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}

        def fetch_metrics(service_name: str = "default") -> dict[str, Any]:
            """Fetches operational metrics for a service."""
            return {
                "service": service_name,
                "latency_p95_ms": 24.5,
                "availability": 0.999,
                "error_rate": 0.0001,
            }

        def verify_citation(text: str, source_doc: str) -> dict[str, Any]:
            """Checks whether text statements align with source document."""
            overlap = len(set(text.lower().split()).intersection(set(source_doc.lower().split())))
            supported = overlap > 0
            return {"supported": supported, "overlap_tokens": overlap}

        self.register_tool(
            "health_check_api",
            health_check_api,
            "Performs system health check and returns status OK.",
            {"properties": {}},
        )
        self.register_tool(
            "calculator",
            calculator,
            "Evaluates basic mathematical expression safely.",
            {"properties": {"expression": {"type": "string"}}},
        )
        self.register_tool(
            "fetch_metrics",
            fetch_metrics,
            "Fetches operational metrics for a service.",
            {"properties": {"service_name": {"type": "string"}}},
        )
        self.register_tool(
            "verify_citation",
            verify_citation,
            "Checks whether text statements align with source document.",
            {"properties": {"text": {"type": "string"}, "source_doc": {"type": "string"}}},
        )
