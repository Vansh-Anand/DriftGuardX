import enum
from typing import Any, Optional
from datetime import datetime
from pydantic import Field, field_validator

from packages.contracts.src.models import DGXBaseModel, _utcnow


class ExogenousSourceType(str, enum.Enum):
    """Types of exogenous sources that can affect replay."""
    CLOCK = "clock"
    RANDOMNESS = "randomness"
    DATABASE = "database"
    HTTP_API = "http_api"
    REMOTE_LLM = "remote_llm"
    FILE = "file"
    ENVIRONMENT_VARIABLE = "environment_variable"
    TOOL = "tool"
    FEATURE_FLAG = "feature_flag"
    MESSAGE_QUEUE = "message_queue"
    USER_INPUT = "user_input"
    OTHER = "other"


class SideEffectClass(str, enum.Enum):
    """Classification of external side effects for tool calls."""
    READ_ONLY = "read_only"
    IDEMPOTENT_WRITE = "idempotent_write"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE_WRITE = "irreversible_write"
    UNKNOWN = "unknown"


class ExogenousReplayStrategy(str, enum.Enum):
    """How to handle an exogenous (external) variable during replay."""
    FREEZE_CAPTURED = "freeze_captured"
    RESTORE_SNAPSHOT = "restore_snapshot"
    DETERMINISTIC_STUB = "deterministic_stub"
    REEXECUTE_AND_MARK_CHANGED_REGIME = "reexecute_and_mark_changed_regime"
    UNCONTROLLABLE = "uncontrollable"
    FORBID_REPLAY = "forbid_replay"


class ExogenousStateRecord(DGXBaseModel):
    """
    Record of an exogenous state/variable captured during execution.
    """
    state_id: str = Field(min_length=1, max_length=255)
    key: str = Field(min_length=1, max_length=255)
    source_type: ExogenousSourceType
    source_identifier: str = Field(min_length=1, max_length=255)
    original_value_hash: Optional[str] = Field(default=None, min_length=64, max_length=64)
    captured_value: Optional[Any] = None
    capture_policy: str = "default"
    captured_at: datetime = Field(default_factory=_utcnow)
    replay_strategy: ExogenousReplayStrategy
    reproducibility_level: str = "deterministic"  # deterministic, stochastic, uncontrollable
    sensitivity: str = "normal"  # normal, secret, pii
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("original_value_hash")
    @classmethod
    def validate_sha256_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) != 64:
            raise ValueError("original_value_hash must be a 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("original_value_hash must be hexadecimal")
        return v.lower()


class ToolCallRecord(ExogenousStateRecord):
    """
    Detailed record of a tool call, inheriting from ExogenousStateRecord.
    """
    tool_identity: str = Field(min_length=1, max_length=255)
    tool_version: str = "1.0.0"
    input_hash: Optional[str] = Field(default=None, min_length=64, max_length=64)
    output_hash: Optional[str] = Field(default=None, min_length=64, max_length=64)
    status: str = "success"
    latency_ms: Optional[float] = None
    side_effect_class: SideEffectClass = SideEffectClass.UNKNOWN

    @field_validator("input_hash", "output_hash")
    @classmethod
    def validate_tool_hashes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) != 64:
            raise ValueError("Hash must be a 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Hash must be hexadecimal")
        return v.lower()
