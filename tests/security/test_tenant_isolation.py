from uuid import uuid4

import pytest

# Assuming we have a mock DB and API router
# We will simulate the tenant isolation logic here as a unit test for the security suite


class MockDB:
    def __init__(self):
        self.traces = {}

    def add_trace(self, tenant_id: str, trace_id: str, data: str):
        if tenant_id not in self.traces:
            self.traces[tenant_id] = {}
        self.traces[tenant_id][trace_id] = data

    def get_trace(self, tenant_id: str, trace_id: str):
        tenant_traces = self.traces.get(tenant_id, {})
        if trace_id not in tenant_traces:
            raise PermissionError("Trace not found or access denied")
        return tenant_traces[trace_id]


@pytest.fixture
def db():
    return MockDB()


@pytest.mark.security
def test_cross_tenant_access_blocked(db):
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    trace_a_id = str(uuid4())

    # Tenant A creates a trace
    db.add_trace(tenant_a, trace_a_id, "Sensitive Trace Data A")

    # Tenant A can access its own trace
    assert db.get_trace(tenant_a, trace_a_id) == "Sensitive Trace Data A"

    # Tenant B attempts to access Tenant A's trace
    with pytest.raises(PermissionError):
        db.get_trace(tenant_b, trace_a_id)
