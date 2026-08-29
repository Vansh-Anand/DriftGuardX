"""
Unit tests: Exogenous-State Controller.
Tests RNG seeding, time freezing, API stubbing, LLM stubbing, feature flags, and tool stubs.
"""
import os
import random

import pytest

os.environ.setdefault("DGX_CAPABILITY_SECRET", "test-secret-key")

from packages.replay.src.exogenous_controller import (
    APIResponseController,
    ExogenousStateController,
    FeatureFlagController,
    LLMStubController,
    RNGController,
    ToolCallController,
)


class TestRNGController:
    def test_seeded_random_is_deterministic(self):
        with RNGController(seed=42):
            vals1 = [random.random() for _ in range(5)]
        with RNGController(seed=42):
            vals2 = [random.random() for _ in range(5)]
        assert vals1 == vals2

    def test_different_seeds_produce_different_values(self):
        with RNGController(seed=1):
            v1 = random.random()
        with RNGController(seed=999):
            v2 = random.random()
        assert v1 != v2


class TestAPIResponseController:
    def test_registered_url_returns_stub(self):
        stubs = {"https://api.example.com/data": {"json": {"result": "stubbed"}, "status_code": 200}}
        with APIResponseController(stubs) as ctrl:
            # When httpx.get is patched, calling it should return the stub
            # We test through the stub function directly
            response = ctrl._make_stub_response("https://api.example.com/data")
            assert response.json()["result"] == "stubbed"
            assert response.status_code == 200

    def test_unregistered_url_raises(self):
        with APIResponseController({}):
            ctrl = APIResponseController({})
            with pytest.raises(RuntimeError, match="blocked"):
                ctrl._make_stub_response("https://unknown.example.com")


class TestLLMStubController:
    def test_stub_cycles_responses(self):
        stubs = [{"content": "resp1"}, {"content": "resp2"}]
        ctrl = LLMStubController(stub_responses=stubs)
        r1 = ctrl._next_stub()
        r2 = ctrl._next_stub()
        r3 = ctrl._next_stub()  # cycles back to first
        assert r1["content"] == "resp1"
        assert r2["content"] == "resp2"
        assert r3["content"] == "resp1"


class TestFeatureFlagController:
    def test_returns_registered_flag(self):
        flags = {"new_retriever": True, "experimental_mode": False}
        ctrl = FeatureFlagController(flags)
        assert ctrl.get("new_retriever") is True
        assert ctrl.get("experimental_mode") is False

    def test_returns_default_for_unknown_flag(self):
        ctrl = FeatureFlagController({})
        assert ctrl.get("unknown_flag", "DEFAULT") == "DEFAULT"


class TestToolCallController:
    def test_registered_tool_returns_stub(self):
        ctrl = ToolCallController({"web_search": {"results": ["doc1", "doc2"]}})
        result = ctrl.get_stub("web_search")
        assert result["results"][0] == "doc1"

    def test_unregistered_tool_raises(self):
        ctrl = ToolCallController({})
        with pytest.raises(RuntimeError, match="blocked"):
            ctrl.get_stub("unknown_tool")


class TestExogenousStateControllerCompose:
    def test_from_envelope_vars_constructs_correctly(self):
        ctrl = ExogenousStateController.from_envelope_vars({
            "rng_seed": 77,
            "feature_flags": {"flag_a": True},
            "tool_stubs": {"calc": 42},
        })
        assert ctrl._rng._seed == 77
        assert ctrl._flags.get("flag_a") is True
        assert ctrl._tools.get_stub("calc") == 42

    def test_context_manager_exits_cleanly(self):
        ctrl = ExogenousStateController(rng_seed=42)
        with ctrl:
            v = random.random()
        # After exit, random still works (no exception)
        assert isinstance(v, float)
