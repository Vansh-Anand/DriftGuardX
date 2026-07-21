"""
DriftGuard-X v2 — LangGraph Adapter

Callback handler to automatically instrument LangGraph node and edge transitions.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from packages.contracts.src.models import ComponentType, SpanKind
from packages.trace_sdk.src.tracer import TraceContext, SpanBuilder


class LangGraphTracer:
    """
    Middleware adapter for LangGraph. Injects into Graph execution
    to capture state transitions and tool outputs.
    """
    def __init__(self, trace_ctx: TraceContext, component_versions: dict[str, dict]):
        self.trace_ctx = trace_ctx
        self.component_versions = component_versions
        self.active_spans: Dict[str, SpanBuilder] = {}

    def on_node_start(self, node_name: str, input_state: Any, **kwargs: Any) -> None:
        """Triggered when a LangGraph node starts processing."""
        # Map node name to component type (defaulting to INTERNAL if unmapped)
        # In a real deployment, this mapping would be configurable.
        comp_type_str = kwargs.get("component_type", "generator")
        try:
            comp_type = ComponentType(comp_type_str)
        except ValueError:
            comp_type = ComponentType.GENERATOR
            
        version_info = self.component_versions.get(node_name, {"id": None, "tag": "v1"})
        
        builder = self.trace_ctx.start_span(node_name, kind=SpanKind.INTERNAL)
        if version_info.get("id"):
            builder.set_component(comp_type, version_info["id"], version_info["tag"])
            
        builder.set_input(input_state)
        self.active_spans[node_name] = builder

    def on_node_end(self, node_name: str, output_state: Any, **kwargs: Any) -> None:
        """Triggered when a LangGraph node completes processing."""
        builder = self.active_spans.pop(node_name, None)
        if builder:
            builder.set_output(output_state)
            builder.finish()
            self.trace_ctx.record_span(builder.build())

    def on_node_error(self, node_name: str, error: Exception, **kwargs: Any) -> None:
        """Triggered when a LangGraph node throws an exception."""
        builder = self.active_spans.pop(node_name, None)
        if builder:
            builder.set_error(type(error).__name__, str(error))
            builder.finish()
            self.trace_ctx.record_span(builder.build())
