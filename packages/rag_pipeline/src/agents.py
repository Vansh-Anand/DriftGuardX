"""
DriftGuard-X v2 — Reference Multi-Agent Runtime
PRIVATE — All Rights Reserved.
"""

import uuid
from typing import Any, Protocol

from packages.contracts.src.agent_models import AgentInvocation, AgentMessage, MessageRole
from packages.contracts.src.models import ComponentType, SpanKind, _utcnow
from packages.trace_sdk.src.tracer import TraceContext


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
    def __init__(self, query: str, run_id: str, tenant_id: str, trace_ctx: TraceContext | None = None):
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

    def read_memory(self, key: str) -> Any:
        val = self.context.get(key)
        if self.trace_ctx and self.last_span_id:
            builder = self.trace_ctx.start_span("memory_read", kind=SpanKind.INTERNAL, parent_span_id=self.last_span_id)
            builder.set_component(ComponentType.MEMORY_READ, uuid.uuid4(), "v1")
            builder.set_input({"key": key})
            builder.set_output({"value": val})
            builder.finish()
            self.trace_ctx.record_span(builder.build())
        return val

    def write_memory(self, key: str, value: Any) -> None:
        self.context[key] = value
        if self.trace_ctx and self.last_span_id:
            builder = self.trace_ctx.start_span("memory_write", kind=SpanKind.INTERNAL, parent_span_id=self.last_span_id)
            builder.set_component(ComponentType.MEMORY_WRITE, uuid.uuid4(), "v1")
            builder.set_input({"key": key, "value": value})
            builder.set_output({"status": "ok"})
            builder.finish()
            self.trace_ctx.record_span(builder.build())


class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    def execute(self, state: ReferenceState) -> AgentInvocation:
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
            builder = state.trace_ctx.start_span(
                self.name,
                kind=SpanKind.INTERNAL,
                parent_span_id=state.last_span_id
            )
            builder.set_component(ComponentType.AGENT, uuid.uuid4(), "v1")
            
            # Stable identity and version metadata (Prompt #11)
            builder.set_attribute("dgx.agent.id", f"agent-{self.name}")
            builder.set_attribute("dgx.agent.type", self.name)
            builder.set_attribute("dgx.agent.version", "v1.0")
            builder.set_attribute("dgx.model.provider", "openai")
            builder.set_attribute("dgx.model.id", "gpt-4o")
            builder.set_attribute("dgx.prompt.hash", "dummy-prompt-hash")
            builder.set_attribute("dgx.config.hash", "dummy-config-hash")
            builder.set_attribute("dgx.tool_registry.hash", "dummy-tool-registry-hash")

            # Agent-to-agent message/causal relationship (Prompt #12)
            if state.last_span_id:
                builder.set_attribute("dgx.causal.source_span_id", state.last_span_id)
            
            builder.set_input({"query": state.query, "context": state.context})
            state.last_span_id = builder.span_id

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

        invocation.end_time = _utcnow()
        state.invocations.append(invocation)

        if builder:
            # Record agent decision/evidence (Prompt #14)
            if "policy_decision" in state.context and self.name == "policy":
                builder.set_attribute("dgx.evidence.classification", "synthetic_simulation")
                builder.set_attribute("dgx.decision.outcome", state.context["policy_decision"])
            builder.finish()
            state.trace_ctx.record_span(builder.build())

        return invocation

    def _process(self, state: ReferenceState) -> str:
        raise NotImplementedError


class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("orchestrator")

    def _process(self, state: ReferenceState) -> str:
        state.current_agent = "retrieval"
        return "Routing to retrieval."


class RetrievalAgent(BaseAgent):
    def __init__(self):
        super().__init__("retrieval")

    def _process(self, state: ReferenceState) -> str:
        state.write_memory("retrieved_docs", [
            "Doc 1: The system is healthy.",
            "Doc 2: Policies require approval.",
        ])
        state.current_agent = "reasoning"
        return f"Retrieved {len(state.read_memory('retrieved_docs'))} documents."


class ReasoningAgent(BaseAgent):
    def __init__(self):
        super().__init__("reasoning")

    def _process(self, state: ReferenceState) -> str:
        state.write_memory("reasoning", "Based on docs, the system is healthy but policy applies.")
        state.current_agent = "tool"
        return "Reasoning complete."


class ToolAgent(BaseAgent):
    def __init__(self):
        super().__init__("tool")

    def _process(self, state: ReferenceState) -> str:
        state.write_memory("tool_results", {"health_check": "OK"})
        state.current_agent = "verifier"
        return "Tool execution complete."


class VerifierAgent(BaseAgent):
    def __init__(self):
        super().__init__("verifier")

    def _process(self, state: ReferenceState) -> str:
        state.write_memory("verified", True)
        state.current_agent = "policy"
        return "Output verified against constraints."


class PolicyAgent(BaseAgent):
    def __init__(self):
        super().__init__("policy")

    def _process(self, state: ReferenceState) -> str:
        state.write_memory("policy_decision", "allow")
        state.current_agent = "response"
        return "Policy evaluated: allow."


class ResponseAgent(BaseAgent):
    def __init__(self):
        super().__init__("response")

    def _process(self, state: ReferenceState) -> str:
        final_answer = "The system is healthy and verified."
        state.final_response = final_answer
        state.is_finished = True
        return final_answer


class AgentPipeline:
    def __init__(self):
        self.agents = {
            "orchestrator": OrchestratorAgent(),
            "retrieval": RetrievalAgent(),
            "reasoning": ReasoningAgent(),
            "tool": ToolAgent(),
            "verifier": VerifierAgent(),
            "policy": PolicyAgent(),
            "response": ResponseAgent(),
        }

    def run(self, query: str, run_id: str, tenant_id: str, trace_ctx: TraceContext | None = None) -> ReferenceState:
        state = ReferenceState(query, run_id, tenant_id, trace_ctx=trace_ctx)

        while not state.is_finished:
            agent = self.agents.get(state.current_agent)
            if not agent:
                raise ValueError(f"Unknown agent: {state.current_agent}")

            agent.execute(state)

        return state
