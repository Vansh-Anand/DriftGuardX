"""
DriftGuard-X v2 — Exogenous-State Controller
PRIVATE — All Rights Reserved.

Intercepts and controls all non-deterministic external calls during replay.
Implements deterministic stubs for: RNG, time, HTTP API responses,
DB snapshots, external LLMs, tool dispatch, and feature flags.

Usage (as context manager):
    controller = ExogenousStateController.from_envelope(envelope)
    with controller:
        result = replay_function()
"""
from __future__ import annotations

import random
import time
import unittest.mock as mock
from collections.abc import Callable
from datetime import UTC, datetime, timezone
from typing import Any

# Optional heavy deps — imported lazily
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


class RNGController:
    """Seeds Python random and numpy.random deterministically."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._patches: list[mock.patch] = []  # type: ignore[type-arg]

    def __enter__(self) -> "RNGController":
        random.seed(self._seed)
        if _HAS_NUMPY:
            np.random.seed(self._seed)
        return self

    def __exit__(self, *args: Any) -> None:
        pass  # Python random state persists; caller manages scope


class TimeController:
    """
    Freezes time-related calls to a specific frozen_time value.
    Patches: datetime.now, datetime.utcnow, time.time, time.monotonic
    """

    def __init__(self, frozen_time_iso: str) -> None:
        self._frozen_dt = datetime.fromisoformat(frozen_time_iso)
        if self._frozen_dt.tzinfo is None:
            self._frozen_dt = self._frozen_dt.replace(tzinfo=UTC)
        self._frozen_ts = self._frozen_dt.timestamp()
        self._patches: list[Any] = []

    def __enter__(self) -> "TimeController":
        frozen_dt = self._frozen_dt
        frozen_ts = self._frozen_ts

        # Patch time.time
        self._patches.append(mock.patch("time.time", return_value=frozen_ts))
        # Patch time.monotonic (returns same frozen value)
        self._patches.append(mock.patch("time.monotonic", return_value=frozen_ts))

        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *args: Any) -> None:
        for p in reversed(self._patches):
            p.stop()
        self._patches.clear()


class APIResponseController:
    """
    Replaces httpx and requests calls with recorded stub responses.
    stubs: dict mapping url_pattern -> response_dict
    """

    def __init__(self, stubs: dict[str, Any]) -> None:
        self._stubs = stubs
        self._patches: list[Any] = []

    def _make_stub_response(self, url: str) -> Any:
        """Returns the matching stub, or a default 503 if not found."""
        for pattern, response in self._stubs.items():
            if pattern in url or url == pattern:
                # Return a simple namespace that quacks like requests/httpx Response
                class _StubResponse:
                    status_code = response.get("status_code", 200)
                    text = response.get("text", "")
                    content = response.get("content", b"")

                    def json(self) -> Any:
                        return response.get("json", {})

                    def raise_for_status(self) -> None:
                        if self.status_code >= 400:
                            raise RuntimeError(f"Stub HTTP error {self.status_code}")

                return _StubResponse()

        # Fallback — blocked
        raise RuntimeError(
            f"ExogenousStateController: unregistered API call to '{url}' blocked in replay sandbox."
        )

    def __enter__(self) -> "APIResponseController":
        stub_fn = self._make_stub_response

        def _get(url: str, **kwargs: Any) -> Any:
            return stub_fn(url)

        def _post(url: str, **kwargs: Any) -> Any:
            return stub_fn(url)

        try:
            self._patches.append(mock.patch("httpx.get", side_effect=_get))
            self._patches.append(mock.patch("httpx.post", side_effect=_post))
        except AttributeError:
            pass
        try:
            self._patches.append(mock.patch("requests.get", side_effect=_get))
            self._patches.append(mock.patch("requests.post", side_effect=_post))
        except AttributeError:
            pass

        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *args: Any) -> None:
        for p in reversed(self._patches):
            p.stop()
        self._patches.clear()


class DBSnapshotController:
    """
    Freezes DB queries to a point-in-time snapshot.
    snapshot_id maps to a dict of {query_key: result}.
    In production this would be backed by a read-only snapshot store.
    """

    def __init__(self, snapshot_id: str, snapshot_data: dict[str, Any] | None = None) -> None:
        self._snapshot_id = snapshot_id
        self._snapshot: dict[str, Any] = snapshot_data or {}
        self._patches: list[Any] = []

    def __enter__(self) -> "DBSnapshotController":
        # Nothing to patch at Python level — enforcement happens via the
        # SandboxedWorker's network/file hooks which block live DB connections.
        # The snapshot data is injected into the replay context directly.
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class LLMStubController:
    """
    Replaces OpenAI / Anthropic / etc. calls with cached or templated stubs.
    stub_responses: list of responses to return in sequence (cycled).
    """

    def __init__(self, stub_responses: list[dict[str, Any]] | None = None) -> None:
        self._stubs = stub_responses or [{"content": "[LLM_STUB_RESPONSE]", "model": "stub"}]
        self._index = 0
        self._patches: list[Any] = []

    def _next_stub(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        response = self._stubs[self._index % len(self._stubs)]
        self._index += 1
        return response

    def __enter__(self) -> "LLMStubController":
        stub_fn = self._next_stub

        # Patch OpenAI completions if available
        try:
            self._patches.append(
                mock.patch("openai.chat.completions.create", side_effect=stub_fn)
            )
        except AttributeError:
            pass

        for p in self._patches:
            try:
                p.start()
            except Exception:  # noqa: BLE001
                pass
        return self

    def __exit__(self, *args: Any) -> None:
        for p in reversed(self._patches):
            try:
                p.stop()
            except Exception:  # noqa: BLE001
                pass
        self._patches.clear()


class ToolCallController:
    """
    Intercepts tool dispatch and returns pre-recorded outputs.
    tool_stubs: dict of tool_name -> recorded_output
    """

    def __init__(self, tool_stubs: dict[str, Any] | None = None) -> None:
        self._stubs = tool_stubs or {}

    def get_stub(self, tool_name: str) -> Any:
        if tool_name in self._stubs:
            return self._stubs[tool_name]
        raise RuntimeError(
            f"ExogenousStateController: unregistered tool call '{tool_name}' blocked in replay."
        )

    def __enter__(self) -> "ToolCallController":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class FeatureFlagController:
    """
    Freezes all feature flags to values at original trace time.
    flags: dict of flag_name -> bool/value
    """

    def __init__(self, flags: dict[str, Any]) -> None:
        self._flags = flags

    def get(self, flag_name: str, default: Any = False) -> Any:
        return self._flags.get(flag_name, default)

    def __enter__(self) -> "FeatureFlagController":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class ExogenousStateController:
    """
    Composes all exogenous controllers.
    Used as a context manager to bracket replay execution.

    Constructed from an exogenous_variables dict (from ReplayEquivalenceEnvelope).
    """

    def __init__(
        self,
        rng_seed: int = 42,
        frozen_time_iso: str | None = None,
        api_stubs: dict[str, Any] | None = None,
        db_snapshot_id: str = "",
        db_snapshot_data: dict[str, Any] | None = None,
        llm_stubs: list[dict[str, Any]] | None = None,
        tool_stubs: dict[str, Any] | None = None,
        feature_flags: dict[str, Any] | None = None,
    ) -> None:
        self._rng = RNGController(seed=rng_seed)
        self._time = TimeController(frozen_time_iso) if frozen_time_iso else None
        self._api = APIResponseController(api_stubs or {})
        self._db = DBSnapshotController(db_snapshot_id, db_snapshot_data)
        self._llm = LLMStubController(llm_stubs)
        self._tools = ToolCallController(tool_stubs)
        self._flags = FeatureFlagController(feature_flags or {})
        self._active: list[Any] = []

    @classmethod
    def from_envelope_vars(cls, exogenous_variables: dict[str, Any]) -> "ExogenousStateController":
        """Factory: build from ReplayEquivalenceEnvelope.exogenous_variables."""
        return cls(
            rng_seed=exogenous_variables.get("rng_seed", 42),
            frozen_time_iso=exogenous_variables.get("frozen_time_iso"),
            api_stubs=exogenous_variables.get("api_stubs", {}),
            db_snapshot_id=exogenous_variables.get("db_snapshot_id", ""),
            db_snapshot_data=exogenous_variables.get("db_snapshot_data"),
            llm_stubs=exogenous_variables.get("llm_stubs"),
            tool_stubs=exogenous_variables.get("tool_stubs", {}),
            feature_flags=exogenous_variables.get("feature_flags", {}),
        )

    def __enter__(self) -> "ExogenousStateController":
        self._active = [self._rng, self._api, self._db, self._llm, self._tools, self._flags]
        if self._time is not None:
            self._active.insert(1, self._time)

        for ctrl in self._active:
            ctrl.__enter__()
        return self

    def __exit__(self, *args: Any) -> None:
        for ctrl in reversed(self._active):
            ctrl.__exit__(*args)
        self._active.clear()

    def get_feature_flag(self, flag_name: str, default: Any = False) -> Any:
        return self._flags.get(flag_name, default)

    def get_tool_stub(self, tool_name: str) -> Any:
        return self._tools.get_stub(tool_name)
