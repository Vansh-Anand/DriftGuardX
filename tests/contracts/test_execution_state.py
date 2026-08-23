"""
Tests for packages/contracts/src/execution_state.py

Covers:
- Canonical state hashing (determinism)
- ExecutionVariableClass classification
- ExecutionStateValue field validation
- ExecutionStateSnapshot integrity
- Duplicate key rejection
- Timezone-aware timestamp enforcement
- Secret key rejection in metadata
- hash_state_value determinism
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from packages.contracts.src.execution_state import (
    ExecutionVariableClass,
    ExecutionStateSnapshot,
    ExecutionStateValue,
    hash_state_value,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_sv(
    key: str = "prompt_hash",
    value: str = "abc",
    variable_class: ExecutionVariableClass = ExecutionVariableClass.FROZEN,
    source: str = "prompt_hash",
) -> ExecutionStateValue:
    return ExecutionStateValue(
        key=key,
        value_hash=hash_state_value(value),
        variable_class=variable_class,
        source=source,
        timestamp=datetime.now(timezone.utc),
    )


def make_snapshot(**overrides) -> ExecutionStateSnapshot:
    defaults = dict(
        run_id=uuid4(),
        trace_id=uuid4(),
        tenant_id=uuid4(),
        captured_at=datetime.now(timezone.utc),
        values=[make_sv()],
    )
    defaults.update(overrides)
    return ExecutionStateSnapshot(**defaults)


# ─── hash_state_value ─────────────────────────────────────────────────────────

class TestHashStateValue:
    def test_returns_64_hex_chars(self):
        h = hash_state_value("hello")
        assert len(h) == 64
        int(h, 16)  # must be valid hex

    def test_deterministic(self):
        h1 = hash_state_value({"model": "gpt-4", "version": "1.0"})
        h2 = hash_state_value({"model": "gpt-4", "version": "1.0"})
        assert h1 == h2

    def test_dict_key_order_invariant(self):
        h1 = hash_state_value({"a": 1, "b": 2})
        h2 = hash_state_value({"b": 2, "a": 1})
        assert h1 == h2, "hash must be key-order invariant"

    def test_different_values_different_hash(self):
        h1 = hash_state_value("v1")
        h2 = hash_state_value("v2")
        assert h1 != h2

    def test_none_value_is_hashable(self):
        h = hash_state_value(None)
        assert len(h) == 64

    def test_non_serialisable_raises(self):
        with pytest.raises(TypeError):
            hash_state_value(object())

    def test_domain_separation(self):
        """Changing just the domain prefix must change the hash."""
        raw = json.dumps({"domain": "DGX-STATE-VALUE-V1", "value": "x"},
                         sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert hash_state_value("x") == expected


# ─── ExecutionVariableClass ───────────────────────────────────────────────────

class TestExecutionVariableClass:
    def test_all_classes_defined(self):
        expected = {"FROZEN", "INTERVENED", "ENDOGENOUS", "EXOGENOUS",
                    "DERIVED", "NONDETERMINISTIC", "UNKNOWN"}
        actual = {m.name for m in ExecutionVariableClass}
        assert expected == actual

    def test_string_values(self):
        assert ExecutionVariableClass.FROZEN.value == "frozen"
        assert ExecutionVariableClass.INTERVENED.value == "intervened"
        assert ExecutionVariableClass.UNKNOWN.value == "unknown"


# ─── ExecutionStateValue ──────────────────────────────────────────────────────

class TestExecutionStateValue:
    def test_valid_construction(self):
        sv = make_sv()
        assert sv.key == "prompt_hash"
        assert len(sv.value_hash) == 64

    def test_invalid_value_hash_length(self):
        with pytest.raises(Exception):
            ExecutionStateValue(
                key="x",
                value_hash="short",
                variable_class=ExecutionVariableClass.FROZEN,
                source="prompt_hash",
                timestamp=datetime.now(timezone.utc),
            )

    def test_non_hex_value_hash_rejected(self):
        with pytest.raises(Exception):
            ExecutionStateValue(
                key="x",
                value_hash="z" * 64,   # 'z' is not hex
                variable_class=ExecutionVariableClass.FROZEN,
                source="prompt_hash",
                timestamp=datetime.now(timezone.utc),
            )

    def test_invalid_source_rejected(self):
        with pytest.raises(Exception):
            ExecutionStateValue(
                key="x",
                value_hash=hash_state_value("v"),
                variable_class=ExecutionVariableClass.FROZEN,
                source="invalid_unknown_source",
                timestamp=datetime.now(timezone.utc),
            )

    def test_secret_key_in_metadata_rejected(self):
        with pytest.raises(Exception):
            ExecutionStateValue(
                key="x",
                value_hash=hash_state_value("v"),
                variable_class=ExecutionVariableClass.FROZEN,
                source="prompt_hash",
                timestamp=datetime.now(timezone.utc),
                metadata={"api_key": "should-be-rejected"},
            )

    def test_password_in_metadata_rejected(self):
        with pytest.raises(Exception):
            ExecutionStateValue(
                key="x",
                value_hash=hash_state_value("v"),
                variable_class=ExecutionVariableClass.FROZEN,
                source="prompt_hash",
                timestamp=datetime.now(timezone.utc),
                metadata={"db_password": "secret123"},
            )

    def test_naive_timestamp_rejected(self):
        with pytest.raises(Exception):
            ExecutionStateValue(
                key="x",
                value_hash=hash_state_value("v"),
                variable_class=ExecutionVariableClass.FROZEN,
                source="prompt_hash",
                timestamp=datetime(2024, 1, 1),  # naive — no tzinfo
            )


# ─── ExecutionStateSnapshot ───────────────────────────────────────────────────

class TestExecutionStateSnapshot:
    def test_valid_snapshot(self):
        snap = make_snapshot()
        assert len(snap.snapshot_hash) == 64

    def test_snapshot_hash_deterministic(self):
        run_id = uuid4()
        trace_id = uuid4()
        tenant_id = uuid4()
        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        sv = ExecutionStateValue(
            key="model_version",
            value_hash=hash_state_value("gpt-4-1"),
            variable_class=ExecutionVariableClass.FROZEN,
            source="model_version",
            timestamp=ts,
        )
        snap1 = ExecutionStateSnapshot(
            run_id=run_id, trace_id=trace_id, tenant_id=tenant_id,
            captured_at=ts, values=[sv],
        )
        snap2 = ExecutionStateSnapshot(
            run_id=run_id, trace_id=trace_id, tenant_id=tenant_id,
            captured_at=ts, values=[sv],
        )
        assert snap1.snapshot_hash == snap2.snapshot_hash

    def test_duplicate_key_rejected(self):
        sv1 = make_sv(key="prompt_hash")
        sv2 = make_sv(key="prompt_hash")
        with pytest.raises(Exception, match="Duplicate state key"):
            make_snapshot(values=[sv1, sv2])

    def test_verify_integrity_passes(self):
        snap = make_snapshot()
        assert snap.verify_integrity() is True

    def test_verify_integrity_fails_after_tampering(self):
        snap = make_snapshot()
        # Tamper with stored hash
        object.__setattr__(snap, "snapshot_hash", "a" * 64)
        assert snap.verify_integrity() is False

    def test_naive_captured_at_rejected(self):
        with pytest.raises(Exception):
            make_snapshot(captured_at=datetime(2024, 1, 1))  # naive

    def test_get_value(self):
        sv = make_sv(key="index_version", source="index_version",
                     variable_class=ExecutionVariableClass.FROZEN)
        snap = make_snapshot(values=[sv])
        result = snap.get_value("index_version")
        assert result is not None
        assert result.key == "index_version"

    def test_get_value_missing_returns_none(self):
        snap = make_snapshot()
        assert snap.get_value("nonexistent") is None

    def test_frozen_keys(self):
        sv1 = make_sv(key="k1", variable_class=ExecutionVariableClass.FROZEN)
        sv2 = make_sv(key="k2", source="model_version",
                      variable_class=ExecutionVariableClass.INTERVENED)
        snap = make_snapshot(values=[sv1, sv2])
        assert snap.frozen_keys() == ["k1"]
        assert snap.intervened_keys() == ["k2"]

    def test_key_order_invariant_hash(self):
        """Snapshot hash must be identical regardless of value insertion order."""
        run_id = uuid4()
        trace_id = uuid4()
        tenant_id = uuid4()
        ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
        sv_a = ExecutionStateValue(
            key="a", value_hash=hash_state_value("va"),
            variable_class=ExecutionVariableClass.FROZEN,
            source="model_version", timestamp=ts,
        )
        sv_b = ExecutionStateValue(
            key="b", value_hash=hash_state_value("vb"),
            variable_class=ExecutionVariableClass.EXOGENOUS,
            source="external_api_response_hash", timestamp=ts,
        )
        snap1 = ExecutionStateSnapshot(
            run_id=run_id, trace_id=trace_id, tenant_id=tenant_id,
            captured_at=ts, values=[sv_a, sv_b],
        )
        snap2 = ExecutionStateSnapshot(
            run_id=run_id, trace_id=trace_id, tenant_id=tenant_id,
            captured_at=ts, values=[sv_b, sv_a],
        )
        assert snap1.snapshot_hash == snap2.snapshot_hash
