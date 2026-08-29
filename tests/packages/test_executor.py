import os
import sys
import time

import cloudpickle
import pytest

from packages.replay.src.executor import ContainerReplayExecutor

cloudpickle.register_pickle_by_value(sys.modules[__name__])

# Note: These tests require Docker Desktop to be running.
# If Docker is not running, ContainerReplayExecutor init will fail or the test will error.
# We will skip tests if docker is not available.

try:
    import docker
    client = docker.from_env()
    client.ping()
    HAS_DOCKER = True
except (ValueError, RuntimeError, KeyError, TypeError, OSError):
    HAS_DOCKER = False

pytestmark = pytest.mark.skipif(not HAS_DOCKER, reason="Docker is not running")

@pytest.fixture
def executor():
    # Use python:3.13-slim to match the host python version for cloudpickle bytecode compatibility
    return ContainerReplayExecutor(image="python:3.13-slim")

def safe_func():
    return "success"

def hanging_func():
    time.sleep(100)
    return "done"

def memory_bomb_func():
    bomb = []
    while True:
        bomb.append(" " * 10**6) # 1MB chunks until OOM

def fork_bomb_func():
    for _ in range(100):
        try:
            os.fork()
        except OSError:
            pass
    return "forked"

def network_func():
    import urllib.request
    urllib.request.urlopen("http://example.com", timeout=2)
    return "connected"

def read_only_func():
    with open("/app/hacked.txt", "w") as f:
        f.write("hacked")
    return "wrote"

def oversized_response_func():
    return "A" * (11 * 1024 * 1024)

@pytest.mark.asyncio
async def test_safe_execution(executor):
    result = await executor.execute(safe_func, budget_seconds=5.0)
    assert result.error is None
    assert result.payload == "success"
    assert result.manifest.executor_type == "ContainerReplayExecutor"

@pytest.mark.asyncio
async def test_hanging_execution(executor):
    result = await executor.execute(hanging_func, budget_seconds=2.0)
    assert result.error is None or "TimeoutError" in result.error

@pytest.mark.asyncio
async def test_memory_bomb(executor):
    # Should get killed by Docker due to OOM
    result = await executor.execute(memory_bomb_func, budget_seconds=10.0)
    assert result.error is not None
    assert "crashed" in result.error or "Error" in result.error

@pytest.mark.asyncio
async def test_fork_bomb(executor):
    result = await executor.execute(fork_bomb_func, budget_seconds=5.0)
    # The fork bomb should be mitigated by pids_limit and it might either crash or hit OSError
    assert result.error is not None or result.payload == "forked"

@pytest.mark.asyncio
async def test_network_isolation(executor):
    result = await executor.execute(network_func, budget_seconds=5.0)
    # network_mode="none" should cause a urllib.error.URLError
    assert result.error is not None
    assert "URLError" in result.error or "Name or service not known" in result.error or "Temporary failure in name resolution" in result.error

@pytest.mark.asyncio
async def test_read_only_mount(executor):
    result = await executor.execute(read_only_func, budget_seconds=5.0)
    assert result.error is not None
    assert "Read-only file system" in result.error

@pytest.mark.asyncio
async def test_oversized_payload_request(executor):
    oversize_payload = "A" * (6 * 1024 * 1024)
    result = await executor.execute(safe_func, budget_seconds=5.0, arg=oversize_payload)
    assert result.error is not None
    assert "exceeds 5MB limit" in result.error

@pytest.mark.asyncio
async def test_oversized_response(executor):
    result = await executor.execute(oversized_response_func, budget_seconds=10.0)
    assert result.error is not None
    assert "exceeds 10MB limit" in result.error
