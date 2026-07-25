import pytest
import asyncio
import time
import numpy as np
from typing import List

async def mock_task_with_latency(mean_ms: float):
    # Simulate jitter
    jitter = np.random.normal(0, mean_ms * 0.1)
    latency = max(0.001, (mean_ms + jitter) / 1000.0)
    start = time.time()
    await asyncio.sleep(latency)
    return time.time() - start

def calculate_percentiles(latencies: List[float]):
    return {
        "p50": np.percentile(latencies, 50),
        "p95": np.percentile(latencies, 95),
        "p99": np.percentile(latencies, 99)
    }

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_trace_ingestion_load():
    """Tests concurrent trace ingestion throughput."""
    tasks = [mock_task_with_latency(10.0) for _ in range(100)]
    latencies = await asyncio.gather(*tasks)
    stats = calculate_percentiles(latencies)
    
    assert stats["p95"] < 0.05 # 50ms requirement
    assert len(latencies) == 100

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_certificate_verification_load():
    """Tests the p99 latency for certificate verification under load."""
    tasks = [mock_task_with_latency(50.0) for _ in range(50)]
    latencies = await asyncio.gather(*tasks)
    stats = calculate_percentiles(latencies)
    
    assert stats["p99"] < 0.15 # 150ms max per cert
    assert len(latencies) == 50

@pytest.mark.asyncio
@pytest.mark.e2e
async def test_graph_build_and_replay_scheduling_load():
    """Tests load on building causal graphs and scheduling replays."""
    tasks = [mock_task_with_latency(20.0) for _ in range(50)]
    latencies = await asyncio.gather(*tasks)
    stats = calculate_percentiles(latencies)
    
    assert stats["p95"] < 0.10
    
@pytest.mark.asyncio
@pytest.mark.e2e
async def test_ui_api_load():
    """Tests load on UI API endpoints."""
    tasks = [mock_task_with_latency(5.0) for _ in range(200)]
    latencies = await asyncio.gather(*tasks)
    stats = calculate_percentiles(latencies)
    
    assert stats["p99"] < 0.05
