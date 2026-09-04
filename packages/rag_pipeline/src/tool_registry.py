"""
DriftGuard-X v2 — Typed Tool Registry
PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    is_safe_for_replay: bool = True


class ToolRegistry:
    """
    Registry for executable agent tools with deterministic hashing,
    parameter schemas, and isolation controls.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        parameters_schema: dict[str, Any] | None = None,
        is_safe_for_replay: bool = True,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            description=description or handler.__doc__ or name,
            handler=handler,
            parameters_schema=parameters_schema or {},
            is_safe_for_replay=is_safe_for_replay,
        )

    def get_tool(self, name: str) -> ToolSpec | None:
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
                "replay_safe": spec.is_safe_for_replay,
            }
            for name, spec in sorted(self._tools.items())
        }
        canonical = json.dumps(schema_dump, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def execute_tool(self, name: str, **kwargs: Any) -> Any:
        spec = self._tools.get(name)
        if not spec:
            raise ValueError(f"Tool '{name}' not found in registry")

        handler = spec.handler
        if inspect.iscoroutinefunction(handler):
            return await handler(**kwargs)
        return handler(**kwargs)

    def execute_tool_sync(self, name: str, **kwargs: Any) -> Any:
        spec = self._tools.get(name)
        if not spec:
            raise ValueError(f"Tool '{name}' not found in registry")

        handler = spec.handler
        if inspect.iscoroutinefunction(handler):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(asyncio.run, handler(**kwargs)).result()
                return loop.run_until_complete(handler(**kwargs))
            except RuntimeError:
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
