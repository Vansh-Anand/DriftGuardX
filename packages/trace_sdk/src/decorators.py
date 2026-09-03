"""
DriftGuard-X v2 — Decorators

Provides automatic instrumentation for external agent tools, functions, and components.
"""

import functools
import inspect
from typing import Any, Callable, TypeVar, cast
from contextvars import ContextVar

from packages.contracts.src.models import ComponentType, PrivacyMode, SpanKind
from packages.trace_sdk.src.tracer import TraceContext, SpanBuilder, hash_payload

F = TypeVar('F', bound=Callable[..., Any])

# Context variable to hold the active trace context if not explicitly passed
_active_trace_context: ContextVar[TraceContext | None] = ContextVar("active_trace_context", default=None)
# Context variable to track causal parent spans in async/sync call chains
_active_parent_span_id: ContextVar[str | None] = ContextVar("active_parent_span_id", default=None)


def set_active_trace_context(ctx: TraceContext | None) -> None:
    _active_trace_context.set(ctx)

def get_active_trace_context() -> TraceContext | None:
    return _active_trace_context.get()


def trace_component(
    component_type: ComponentType | str,
    name: str | None = None,
    version_tag: str = "v1",
    kind: SpanKind = SpanKind.INTERNAL,
    privacy_mode: PrivacyMode = PrivacyMode.DEVELOPMENT_FULL,
    capture_args: bool = True,
    capture_return: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to automatically trace synchronous and asynchronous functions.
    Preserves causal edges, correctly extracts exceptions to ERROR spans, and respects privacy rules.
    """
    def decorator(func: F) -> F:
        func_name = name or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                ctx = get_active_trace_context()
                if not ctx:
                    return await func(*args, **kwargs)

                parent_id = _active_parent_span_id.get()
                builder = ctx.start_span(name=func_name, kind=kind, parent_span_id=parent_id)
                builder.set_attribute("dgx.component.type", str(component_type))
                builder.set_attribute("dgx.component.version_tag", version_tag)
                
                # Explicitly set the private component type for building the contract
                builder.set_component_type(component_type)
                
                if parent_id:
                    builder.set_attribute("dgx.causal.source_span_id", parent_id)

                if capture_args:
                    builder.set_input({"args": args, "kwargs": kwargs})
                
                token = _active_parent_span_id.set(builder.span_id)
                try:
                    result = await func(*args, **kwargs)
                    if capture_return:
                        builder.set_output(result)
                    return result
                except Exception as e:
                    builder.set_error(type(e).__name__, str(e))
                    raise
                finally:
                    _active_parent_span_id.reset(token)
                    builder.finish(privacy_mode=privacy_mode)
                    ctx.record_span(builder.build())

            return cast(F, async_wrapper)
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                ctx = get_active_trace_context()
                if not ctx:
                    return func(*args, **kwargs)

                parent_id = _active_parent_span_id.get()
                builder = ctx.start_span(name=func_name, kind=kind, parent_span_id=parent_id)
                builder.set_attribute("dgx.component.type", str(component_type))
                builder.set_attribute("dgx.component.version_tag", version_tag)
                
                builder.set_component_type(component_type)
                
                if parent_id:
                    builder.set_attribute("dgx.causal.source_span_id", parent_id)

                if capture_args:
                    builder.set_input({"args": args, "kwargs": kwargs})

                token = _active_parent_span_id.set(builder.span_id)
                try:
                    result = func(*args, **kwargs)
                    if capture_return:
                        builder.set_output(result)
                    return result
                except Exception as e:
                    builder.set_error(type(e).__name__, str(e))
                    raise
                finally:
                    _active_parent_span_id.reset(token)
                    builder.finish(privacy_mode=privacy_mode)
                    ctx.record_span(builder.build())

            return cast(F, sync_wrapper)

    return decorator
