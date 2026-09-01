"""
DriftGuard-X v2 — Agent Models
PRIVATE — All Rights Reserved.
"""
import enum
from typing import Any
from uuid import UUID
from datetime import datetime

from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AgentMessage(DGXBaseModel):
    role: MessageRole
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str | None = None


class AgentTask(DGXBaseModel):
    task_id: UUID = Field(default_factory=_new_uuid)
    description: str
    expected_output: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInvocation(DGXBaseModel):
    invocation_id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    agent_name: str
    system_prompt_hash: str | None = None
    messages: list[AgentMessage] = Field(default_factory=list)
    output_message: AgentMessage | None = None
    tasks: list[AgentTask] = Field(default_factory=list)
    start_time: datetime = Field(default_factory=_utcnow)
    end_time: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
