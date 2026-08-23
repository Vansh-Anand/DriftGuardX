"""
DriftGuard-X v2 — Python Agent Loop Adapter

Decorator and context manager for standard Python agent loop instrumentation.
"""
import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any

from packages.contracts.src.models import ComponentType, SpanKind
from packages.trace_sdk.src.tracer import TraceContext


def instrument_tool(
    component_type: ComponentType,
    version_id: str,
    version_tag: str,
    name: str | None = None,
):
    """
    Decorator for tracking standard Python functions as Trace spans.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # We must pull TraceContext from kwargs if injected by orchestrator
            # In a real async-context setup, we'd use contextvars
            trace_ctx: TraceContext | None = kwargs.pop("trace_ctx", None)

            if not trace_ctx:
                # If no active trace context, just run it
                return func(*args, **kwargs)

            span_name = name or func.__name__
            builder = trace_ctx.start_span(span_name, kind=SpanKind.INTERNAL)
            builder.set_component(component_type, version_id, version_tag)

            # Combine args and kwargs for input payload hashing
            input_payload = {"args": args, "kwargs": kwargs}
            builder.set_input(input_payload)

            try:
                result = func(*args, **kwargs)
                builder.set_output(result)
                builder.finish()
                trace_ctx.record_span(builder.build())
                return result
            except Exception as e:
                builder.set_error(type(e).__name__, str(e))
                builder.finish()
                trace_ctx.record_span(builder.build())
                raise

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_ctx: TraceContext | None = kwargs.pop("trace_ctx", None)

            if not trace_ctx:
                return await func(*args, **kwargs)

            span_name = name or func.__name__
            builder = trace_ctx.start_span(span_name, kind=SpanKind.INTERNAL)
            builder.set_component(component_type, version_id, version_tag)

            input_payload = {"args": args, "kwargs": kwargs}
            builder.set_input(input_payload)

            try:
                result = await func(*args, **kwargs)
                builder.set_output(result)
                builder.finish()
                trace_ctx.record_span(builder.build())
                return result
            except Exception as e:
                builder.set_error(type(e).__name__, str(e))
                builder.finish()
                trace_ctx.record_span(builder.build())
                raise

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class AgentInstrumentor:
    """
    Provides context-manager based explicit instrumentation for manual agent loops.
    """
    def __init__(self, trace_ctx: TraceContext):
        self.trace_ctx = trace_ctx

    def start_span(
        self,
        name: str,
        component_type: ComponentType,
        version_id: str,
        version_tag: str,
        kind: SpanKind = SpanKind.INTERNAL,
    ):
        builder = self.trace_ctx.start_span(name, kind=kind)
        builder.set_component(component_type, version_id, version_tag)
        return builder

    def record(self, builder):
        self.trace_ctx.record_span(builder.build())
