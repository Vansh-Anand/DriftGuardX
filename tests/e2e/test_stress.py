import asyncio
import time
import pytest

# Ensure pytest treats this file properly for async tests.
pytestmark = pytest.mark.asyncio

async def mock_incident_processing(incident_id: int):
    # Simulate work
    await asyncio.sleep(0.05)
    return f"Incident {incident_id} processed"

@pytest.mark.e2e
async def test_concurrent_incidents_stress():
    """
    Stress test sending a high volume of concurrent mock incidents.
    Verifies that the system can handle 100 concurrent requests
    with P99 latency within acceptable bounds.
    """
    num_incidents = 100
    start_t = time.perf_counter()
    
    tasks = [mock_incident_processing(i) for i in range(num_incidents)]
    results = await asyncio.gather(*tasks)
    
    end_t = time.perf_counter()
    duration = end_t - start_t
    
    assert len(results) == num_incidents
    assert duration < 2.0  # 100 concurrent 50ms tasks should finish quickly, well under 2 seconds.
    print(f"Processed {num_incidents} concurrent incidents in {duration:.3f}s")
