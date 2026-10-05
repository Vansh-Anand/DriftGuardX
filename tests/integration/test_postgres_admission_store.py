from __future__ import annotations

import os
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.interfaces import ResourceContext
from packages.replay.src.admission_receipt import ReplayAdmissionReceipt
from packages.replay.src.postgres_admission_store import (
    PostgresAdmissionReceiptStore,
    normalize_postgres_dsn,
)


def _claim_postgres(database_url: str, receipt_id: str, actual: dict[str, str]) -> bool:
    admitted, _ = PostgresAdmissionReceiptStore(database_url).verify(
        receipt_id, actual=actual, require_signature=False
    )
    return admitted


@pytest.mark.integration
def test_postgres_receipt_claim_and_reservation_are_atomic() -> None:
    database_url = os.getenv("DGX_SERVICE_DATABASE_URL", "")
    if not database_url.startswith("postgresql+"):
        pytest.skip("Live PostgreSQL service is not configured")

    tenant_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    pool_id = f"tenant:{tenant_id}:replay"
    store = PostgresAdmissionReceiptStore(database_url, default_budget_usd=2.0)
    receipt = ReplayAdmissionReceipt.issue(
        resource_context=ResourceContext(budget_usd=2.0),
        tenant_id=tenant_id,
        workload_id="pipeline-postgres",
        run_id=run_id,
        manifest_hash="manifest-postgres",
        trace_root_hash="trace-postgres",
        intervention_hash="intervention-postgres",
        current_version="v1",
        candidate_version="v2",
        policy_hash="policy-postgres",
        predicted_cost=1.0,
        uncertainty_margin=0.2,
        rollback_reserve=0.3,
        resource_pool_id=pool_id,
        evidence_ceiling=EvidenceClassification.REAL_CONTROLLED_EXPERIMENT,
        capsule_hash="capsule-postgres",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    actual = {
        "tenant_id": tenant_id,
        "workload_id": "pipeline-postgres",
        "run_id": run_id,
        "manifest_hash": "manifest-postgres",
        "trace_root_hash": "trace-postgres",
        "intervention_hash": "intervention-postgres",
        "current_version": "v1",
        "candidate_version": "v2",
        "policy_hash": "policy-postgres",
        "capsule_hash": "capsule-postgres",
        "resource_pool_id": pool_id,
    }

    import psycopg2

    cleanup_url = normalize_postgres_dsn(database_url)
    with psycopg2.connect(cleanup_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO tenants (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (%s, %s, %s, TRUE, NOW(), NOW())",
            (tenant_id, "Admission Integration", f"admission-{tenant_id}"),
        )
    try:
        store.issue(receipt)
        with ProcessPoolExecutor(max_workers=4) as pool:
            claims = list(
                pool.map(
                    _claim_postgres,
                    [database_url] * 4,
                    [receipt.receipt_id] * 4,
                    [actual] * 4,
                )
            )
        assert claims.count(True) == 1
        store.consume(receipt.receipt_id)
        assert store.verify_event_chain(receipt.receipt_id) == (True, "ok")
    finally:
        with psycopg2.connect(cleanup_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM admission_audit_events WHERE receipt_id = %s", (receipt.receipt_id,)
            )
            cursor.execute(
                "DELETE FROM admission_receipts WHERE receipt_id = %s", (receipt.receipt_id,)
            )
            cursor.execute("DELETE FROM admission_resource_pools WHERE pool_id = %s", (pool_id,))
            cursor.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
