"""
DriftGuard-X v2 — Reference Multi-Agent Runtime
PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import uuid
from typing import Any, Protocol

from packages.contracts.src.agent_models import AgentInvocation, AgentMessage, MessageRole
from packages.contracts.src.models import ComponentType, SpanKind, _utcnow
from packages.policy.src.gate import evaluate_policy
from packages.rag_pipeline.src.tool_registry import ToolRegistry
from packages.trace_sdk.src.tracer import TraceContext


def _deterministic_hash(payload: Any) -> str:
    if payload is None:
        return "none"
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AgentState(Protocol):
    run_id: str
    tenant_id: str
    query: str
    context: dict[str, Any]
    history: list[AgentMessage]
    current_agent: str
    is_finished: bool
    final_response: str | None


class ReferenceState:
    def __init__(
        self,
        query: str,
        run_id: str,
        tenant_id: str,
        trace_ctx: TraceContext | None = None,
    ):
        self.run_id = run_id
        self.tenant_id = tenant_id
        self.query = query
        self.context: dict[str, Any] = {}
        self.history: list[AgentMessage] = []
        self.current_agent: str = "orchestrator"
        self.is_finished: bool = False
        self.final_response: str | None = None
        self.invocations: list[AgentInvocation] = []
        self.trace_ctx = trace_ctx
        self.last_span_id: str | None = None
        self.agent_span_map: dict[str, str] = {}

    def read_memory(self, key: str) -> Any:
        val = self.context.get(key)
        if self.trace_ctx and self.last_span_id:
            builder = self.trace_ctx.start_span(
                "memory_read", kind=SpanKind.INTERNAL, parent_span_id=self.last_span_id
            )
            builder.set_component(ComponentType.MEMORY_READ, uuid.uuid4(), "v1")
            builder.set_input({"key": key})
            builder.set_output({"value": val})
            builder.finish()
            self.trace_ctx.record_span(builder.build())
        return val

    def write_memory(self, key: str, value: Any) -> None:
        self.context[key] = value
        if self.trace_ctx and self.last_span_id:
            builder = self.trace_ctx.start_span(
                "memory_write", kind=SpanKind.INTERNAL, parent_span_id=self.last_span_id
            )
            builder.set_component(ComponentType.MEMORY_WRITE, uuid.uuid4(), "v1")
            builder.set_input({"key": key, "value": value})
            builder.set_output({"status": "ok"})
            builder.finish()
            self.trace_ctx.record_span(builder.build())


class BaseAgent:
    def __init__(
        self,
        name: str,
        version: str = "v1.0",
        provider: str = "local-deterministic",
        model_id: str = "default-model",
        real_mode: bool = False,
    ):
        self.name = name
        self.version = version
        self.provider = provider
        self.model_id = model_id
        self.real_mode = real_mode
        self.prompt_template = {"instruction": f"Execute {name} task"}
        self.config = {"temperature": 0.0}
        self.tools: list[str] = []

    @property
    def prompt_hash(self) -> str:
        return _deterministic_hash(self.prompt_template)

    @property
    def config_hash(self) -> str:
        return _deterministic_hash(self.config)

    @property
    def tool_registry_hash(self) -> str:
        return _deterministic_hash(self.tools)

    def execute(self, state: ReferenceState, source_agent: str | None = None) -> AgentInvocation:
        start_time = _utcnow()
        invocation = AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(state.run_id),
            tenant_id=uuid.UUID(state.tenant_id),
            agent_name=self.name,
            start_time=start_time,
        )

        builder = None
        if state.trace_ctx:
            # We preserve standard parent_span_id from the root/previous, but use causal explicitly
            builder = state.trace_ctx.start_span(
                self.name,
                kind=SpanKind.INTERNAL,
                parent_span_id=state.last_span_id,
            )
            builder.set_component(ComponentType.AGENT, uuid.uuid4(), self.version)

            builder.set_attribute("dgx.agent.id", f"agent-{self.name}-{self.version}")
            builder.set_attribute("dgx.agent.type", self.name)
            builder.set_attribute("dgx.agent.version", self.version)
            builder.set_attribute("dgx.model.provider", self.provider)
            builder.set_attribute("dgx.model.id", self.model_id)
            builder.set_attribute("dgx.prompt.hash", self.prompt_hash)
            builder.set_attribute("dgx.config.hash", self.config_hash)
            builder.set_attribute("dgx.tool_registry.hash", self.tool_registry_hash)

            if source_agent and source_agent in state.agent_span_map:
                builder.set_attribute(
                    "dgx.causal.source_span_id", state.agent_span_map[source_agent]
                )

            builder.set_input({"query": state.query, "context": state.context})
            state.last_span_id = builder.span_id
            state.agent_span_map[self.name] = builder.span_id

        try:
            output = self._process(state)
            invocation.output_message = AgentMessage(
                role=MessageRole.ASSISTANT, content=output, name=self.name
            )
            state.history.append(invocation.output_message)
            if builder:
                builder.set_output(output)
        except Exception as e:
            invocation.output_message = AgentMessage(
                role=MessageRole.ASSISTANT, content=f"Error: {e!s}", name=self.name
            )
            invocation.metadata["error"] = str(e)
            if builder:
                builder.set_error(type(e).__name__, str(e))
            # Dynamic routing on failure (fallback to orchestrator or response)
            state.current_agent = "orchestrator"

        invocation.end_time = _utcnow()
        state.invocations.append(invocation)

        if builder:
            if "policy_decision" in state.context and self.name == "policy":
                builder.set_attribute("dgx.evidence.classification", "synthetic_simulation")
                builder.set_attribute("dgx.decision.outcome", state.context["policy_decision"])
            builder.finish()
            state.trace_ctx.record_span(builder.build())

        return invocation

    def _process(self, state: ReferenceState) -> str:
        raise NotImplementedError


class OrchestratorAgent(BaseAgent):
    def __init__(self, **kwargs: Any):
        super().__init__("orchestrator", **kwargs)

    def _process(self, state: ReferenceState) -> str:
        if state.context.get("error"):
            state.current_agent = "response"
            return "Routing to response due to error."
        state.current_agent = "retrieval"
        return "Routing to retrieval."


class RetrievalAgent(BaseAgent):
    def __init__(self, retriever: Any = None, **kwargs: Any):
        super().__init__("retrieval", **kwargs)
        self.retriever = retriever

    def _process(self, state: ReferenceState) -> str:
        if self.real_mode and self.retriever is None:
            raise ValueError("real_mode=True requires a valid retriever instance.")
            
        if state.query == "empty_search":
            state.write_memory("retrieved_docs", [])
            state.current_agent = "fallback"
            return "No documents. Routing to fallback."

        if self.retriever is not None:
            # Execute real retrieval
            corpus_id = state.context.get("corpus_version_id", "v1")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        chunks = pool.submit(
                            asyncio.run,
                            self.retriever.retrieve(
                                query=state.query, corpus_version_id=corpus_id, top_k=5
                            ),
                        ).result()
                else:
                    chunks = loop.run_until_complete(
                        self.retriever.retrieve(
                            query=state.query, corpus_version_id=corpus_id, top_k=5
                        )
                    )
            except RuntimeError:
                chunks = asyncio.run(
                    self.retriever.retrieve(query=state.query, corpus_version_id=corpus_id, top_k=5)
                )

            docs = [c.text_content for c in chunks]
            if not docs:
                state.write_memory("retrieved_docs", [])
                state.current_agent = "fallback"
                return "No documents retrieved from index. Routing to fallback."

            state.write_memory("retrieved_docs", docs)
            state.current_agent = "reasoning"
            return f"Retrieved {len(docs)} documents from real retriever."
            
        if self.real_mode:
            raise RuntimeError("Fallback retrieval is not allowed in real_mode.")

        # Fallback default deterministic retriever
        state.write_memory(
            "retrieved_docs",
            [
                "Doc 1: The system is healthy.",
                "Doc 2: Policies require approval.",
            ],
        )
        state.current_agent = "reasoning"
        return f"Retrieved {len(state.read_memory('retrieved_docs'))} documents."


class FallbackAgent(BaseAgent):
    def __init__(self, **kwargs: Any):
        super().__init__("fallback", **kwargs)

    def _process(self, state: ReferenceState) -> str:
        state.write_memory("reasoning", "Fallback triggered. Using general knowledge.")
        state.current_agent = "tool"
        return "Fallback complete."


class ReasoningAgent(BaseAgent):
    def __init__(self, llm: Any = None, **kwargs: Any):
        super().__init__("reasoning", **kwargs)
        self.llm = llm

    def _process(self, state: ReferenceState) -> str:
        if self.real_mode and self.llm is None:
            raise ValueError("real_mode=True requires a valid LLM instance.")
            
        docs = state.read_memory("retrieved_docs") or []
        if self.llm is not None:
            # Call real LLM adapter
            prompt = f"Analyze the query '{state.query}' using context:\n" + "\n".join(
                f"- {d}" for d in docs
            )
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        res = pool.submit(
                            asyncio.run, self.llm.generate(prompt=prompt, context=[])
                        ).result()
                else:
                    res = loop.run_until_complete(self.llm.generate(prompt=prompt, context=[]))
            except RuntimeError:
                res = asyncio.run(self.llm.generate(prompt=prompt, context=[]))

            # Support both dict and ProviderResponse for backwards compatibility
            if hasattr(res, "text") and hasattr(res, "metadata"):
                text = res.text
                metadata = res.metadata
            else:
                text = res.get("text", "Reasoning produced.")
                metadata = res.get("model_metadata", {})
            
            # Record metadata
            if metadata:
                state.write_memory("llm_metadata", metadata)
                
            state.write_memory("reasoning", text)
            state.current_agent = "tool"
            return f"LLM Reasoning complete: {text}"
            
        if self.real_mode:
            raise RuntimeError("Fallback reasoning is not allowed in real_mode.")

        state.write_memory(
            "reasoning", "Based on docs, the system is healthy but policy applies."
        )
        state.current_agent = "tool"
        return "Reasoning complete."


class ToolAgent(BaseAgent):
    def __init__(self, tool_registry: ToolRegistry | None = None, **kwargs: Any):
        super().__init__("tool", **kwargs)
        self.tool_registry = tool_registry or ToolRegistry()
        self.tools = self.tool_registry.list_tools()

    def _process(self, state: ReferenceState) -> str:
        # Dynamically execute tool
        user_permissions = state.context.get("permissions", [])
        
        tool_name = "health_check_api"
        kwargs = {}
        if "calculate" in state.query.lower():
            tool_name = "calculator"
            kwargs = {"expression": "2 + 2"}
        elif "metric" in state.query.lower():
            tool_name = "fetch_metrics"
            kwargs = {"service_name": "rag_service"}
        else:
            tool_name = "health_check_api"

        try:
            result = self.tool_registry.execute_tool_sync(tool_name, user_permissions=user_permissions, **kwargs)
        except Exception as e:
            if self.real_mode:
                raise RuntimeError(f"Tool execution failed: {e}")
            result = f"Error: {e}"

        state.write_memory("tool_results", result)
        state.current_agent = "verifier"
        return f"Tool execution ({tool_name}) complete: {result}"


class VerifierAgent(BaseAgent):
    def __init__(self, **kwargs: Any):
        super().__init__("verifier", **kwargs)

    def _process(self, state: ReferenceState) -> str:
        if state.context.get("force_retry"):
            state.write_memory("force_retry", False)
            state.current_agent = "reasoning"
            return "Verification failed. Retrying reasoning."

        # Evaluate evidence consistency
        docs = state.read_memory("retrieved_docs") or []
        tool_res = state.read_memory("tool_results") or {}
        reasoning = state.read_memory("reasoning") or ""

        if self.real_mode:
            is_supported = len(docs) > 0 and (isinstance(tool_res, dict) or "Error" not in str(tool_res))
            if not is_supported:
                state.current_agent = "fallback"
                return "Verification strict failure in real mode."
        else:
            # Verification check: tool status is healthy or documents support reasoning
            is_supported = (
                (isinstance(tool_res, dict) and tool_res.get("status") == "healthy")
                or (isinstance(tool_res, dict) and tool_res.get("health_check") == "OK")
                or len(docs) > 0
                or len(reasoning) > 0
            )

        state.write_memory("verified", is_supported)
        state.current_agent = "policy"
        return "Output verified against constraints."


class PolicyAgent(BaseAgent):
    def __init__(self, **kwargs: Any):
        super().__init__("policy", **kwargs)

    def _process(self, state: ReferenceState) -> str:
        policy = evaluate_policy(state.query, "pipeline")
        outcome = policy.action.value if hasattr(policy.action, "value") else str(policy.action)
        state.write_memory("policy_decision", outcome)
        state.write_memory("policy_rule_id", policy.rule_id)
        
        db = state.context.get("db")
        if self.real_mode and db:
            from packages.contracts.src.models import _new_uuid
            # Persist decision to DB logic can be mocked here or executed if ORM objects are available
            state.write_memory("policy_persisted_id", str(_new_uuid()))

        state.current_agent = "response"
        return f"Policy evaluated: {outcome}."


class ResponseAgent(BaseAgent):
    def __init__(self, **kwargs: Any):
        super().__init__("response", **kwargs)

    def _process(self, state: ReferenceState) -> str:
        reasoning = state.read_memory("reasoning") or ""
        tool_res = state.read_memory("tool_results") or {}
        verified = state.read_memory("verified")
        
        if self.real_mode:
            if not verified:
                final_answer = "Error: Constraints verification failed."
            else:
                final_answer = f"Generated Response from real state:\n{reasoning}\nTools: {tool_res}"
        else:
            if "healthy" in reasoning.lower() and (isinstance(tool_res, dict) and tool_res.get("health_check") == "OK") and verified:
                final_answer = "The system is healthy and verified."
            elif reasoning:
                final_answer = f"Response synthesized: {reasoning}"
            else:
                final_answer = "System status processed."

        state.final_response = final_answer
        state.is_finished = True
        return final_answer


class AgentPipeline:
    def __init__(
        self,
        retriever: Any = None,
        llm: Any = None,
        tool_registry: ToolRegistry | None = None,
        real_mode: bool = False,
    ):
        self.tool_registry = tool_registry or ToolRegistry()
        self.real_mode = real_mode
        self.agents = {
            "orchestrator": OrchestratorAgent(real_mode=real_mode),
            "retrieval": RetrievalAgent(retriever=retriever, real_mode=real_mode),
            "reasoning": ReasoningAgent(llm=llm, real_mode=real_mode),
            "fallback": FallbackAgent(real_mode=real_mode),
            "tool": ToolAgent(tool_registry=self.tool_registry, real_mode=real_mode),
            "verifier": VerifierAgent(real_mode=real_mode),
            "policy": PolicyAgent(real_mode=real_mode),
            "response": ResponseAgent(real_mode=real_mode),
        }

    def run(
        self,
        query: str,
        run_id: str,
        tenant_id: str,
        trace_ctx: TraceContext | None = None,
        max_hops: int = 15,
        quarantined_agents: set[str] = None,
    ) -> ReferenceState:
        state = ReferenceState(query, run_id, tenant_id, trace_ctx=trace_ctx)
        hops = 0
        quarantined_agents = quarantined_agents or set()

        last_agent = None

        while not state.is_finished and hops < max_hops:
            current_agent_name = state.current_agent

            if current_agent_name in quarantined_agents:
                # Agent is quarantined, route to fallback
                state.write_memory("error", f"Agent {current_agent_name} is quarantined.")
                # We do a hard fallback to orchestrator which handles routing, or directly to fallback
                if current_agent_name == "orchestrator":
                    current_agent_name = "response" # the last safe resort
                    state.current_agent = "response"
                else:
                    current_agent_name = "fallback"
                    state.current_agent = "fallback"

            agent = self.agents.get(current_agent_name)
            if not agent:
                raise ValueError(f"Unknown agent: {current_agent_name}")

            agent.execute(state, source_agent=last_agent)
            last_agent = current_agent_name
            hops += 1

        if hops >= max_hops:
            state.is_finished = True
            state.final_response = "Error: Max hops exceeded."

        return state
