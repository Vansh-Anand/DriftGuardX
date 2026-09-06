"""
DriftGuard-X v2 — LangGraph Adapter

Provides decorators and callbacks to automatically trace LangGraph nodes and map them to DriftGuard components.
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any, TypeVar, cast

from packages.contracts.src.models import ComponentType, PrivacyMode, SpanKind
from packages.trace_sdk.src.decorators import _active_parent_span_id, get_active_trace_context

F = TypeVar("F", bound=Callable[..., Any])


def langgraph_node(
    name: str | None = None,
    version_tag: str = "v1",
    privacy_mode: PrivacyMode = PrivacyMode.DEVELOPMENT_FULL,
) -> Callable[[F], F]:
    """
    Traces a LangGraph node. LangGraph nodes are typically functions that take State and return an update to State.
    """

    def decorator(func: F) -> F:
        func_name = name or func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(state: Any, *args, **kwargs) -> Any:
                ctx = get_active_trace_context()
                if not ctx:
                    return await func(state, *args, **kwargs)

                parent_id = _active_parent_span_id.get()
                builder = ctx.start_span(
                    name=func_name, kind=SpanKind.INTERNAL, parent_span_id=parent_id
                )
                builder.set_attribute("dgx.component.type", str(ComponentType.AGENT.value))
                builder.set_attribute("dgx.component.version_tag", version_tag)
                builder.set_attribute("dgx.agent.type", "langgraph_node")
                builder.set_component_type(ComponentType.AGENT)

                if parent_id:
                    builder.set_attribute("dgx.causal.source_span_id", parent_id)

                # Capture state update
                # In LangGraph, node gets state dict and returns state updates dict.
                builder.set_input({"state": state, "args": args, "kwargs": kwargs})

                token = _active_parent_span_id.set(builder.span_id)
                try:
                    result = await func(state, *args, **kwargs)
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
            def sync_wrapper(state: Any, *args, **kwargs) -> Any:
                ctx = get_active_trace_context()
                if not ctx:
                    return func(state, *args, **kwargs)

                parent_id = _active_parent_span_id.get()
                builder = ctx.start_span(
                    name=func_name, kind=SpanKind.INTERNAL, parent_span_id=parent_id
                )
                builder.set_attribute("dgx.component.type", str(ComponentType.AGENT.value))
                builder.set_attribute("dgx.component.version_tag", version_tag)
                builder.set_attribute("dgx.agent.type", "langgraph_node")
                builder.set_component_type(ComponentType.AGENT)

                if parent_id:
                    builder.set_attribute("dgx.causal.source_span_id", parent_id)

                builder.set_input({"state": state, "args": args, "kwargs": kwargs})

                token = _active_parent_span_id.set(builder.span_id)
                try:
                    result = func(state, *args, **kwargs)
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
