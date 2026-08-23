
import pytest

from packages.replay.src.executor import ContainerReplayExecutor

# Simple functions to test the executor

def quick_success():
    return "success"

def hanging_job():
    while True:
        pass

def memory_pressure():
    # Attempt to allocate more than 128MB
    # Each float is 8 bytes, so 20 million floats is ~160MB
    data = [0.0] * 20000000
    return len(data)

def network_access():
    import urllib.request
    try:
        # 1.1.1.1 is Cloudflare DNS, usually highly available
        urllib.request.urlopen("http://1.1.1.1", timeout=2)
        return "network_success"
    except Exception as e:
        raise RuntimeError(f"Network failed: {e!s}")

def oversized_payload():
    # Attempt to write a large file to /tmp (which is limited to 64MB)
    try:
        with open("/tmp/large_file.bin", "wb") as f:
            f.write(b"0" * (70 * 1024 * 1024))
        return "write_success"
    except Exception as e:
        raise RuntimeError(f"Write failed: {e!s}")

def failed_execution():
    raise ValueError("Intentional crash")


@pytest.fixture
def executor():
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return ContainerReplayExecutor()
    except Exception:
        pytest.skip("Docker is not available on this system.")


@pytest.mark.asyncio
async def test_quick_success(executor):
    result = await executor.execute(quick_success, budget_seconds=5.0)
    assert result.error is None
    assert result.payload == "success"
    assert result.manifest.executor_type == "ContainerReplayExecutor"
    assert result.manifest.image_digest is not None

@pytest.mark.asyncio
async def test_hanging_job(executor):
    # The container should be killed after the budget
    result = await executor.execute(hanging_job, budget_seconds=2.0)
    assert result.payload is None
    assert result.error is not None
    assert "TimeoutError" in result.error
    assert result.manifest.execution_time_seconds >= 2.0

@pytest.mark.asyncio
async def test_memory_pressure(executor):
    # The container should be killed by OOM killer due to 128m limit
    result = await executor.execute(memory_pressure, budget_seconds=10.0)
    assert result.payload is None
    assert result.error is not None
    assert "No result file found" in result.error or "memory" in result.error.lower() or "ContainerError" in result.error

@pytest.mark.asyncio
async def test_network_access(executor):
    # The container has network_mode="none", so it should fail to reach the internet
    result = await executor.execute(network_access, budget_seconds=5.0)
    assert result.payload is None
    assert result.error is not None
    assert "Network failed" in result.error or "Name or service not known" in result.error or "Network is unreachable" in result.error

@pytest.mark.asyncio
async def test_oversized_payload(executor):
    # The container has a 64MB tmpfs limit on /tmp
    result = await executor.execute(oversized_payload, budget_seconds=5.0)
    assert result.payload is None
    assert result.error is not None
    assert "No space left on device" in result.error or "Write failed" in result.error

@pytest.mark.asyncio
async def test_failed_execution(executor):
    # The python exception should be caught and bubbled up
    result = await executor.execute(failed_execution, budget_seconds=5.0)
    assert result.payload is None
    assert result.error is not None
    assert "Intentional crash" in result.error

@pytest.mark.asyncio
async def test_cleanup(executor):
    # Ensure containers are cleaned up
    import docker
    client = docker.from_env()

    # Count containers with our image before
    initial_count = len(client.containers.list(all=True, filters={"ancestor": executor.image}))

    # Run a quick job
    await executor.execute(quick_success, budget_seconds=5.0)

    # Count containers after
    final_count = len(client.containers.list(all=True, filters={"ancestor": executor.image}))
    assert final_count == initial_count
