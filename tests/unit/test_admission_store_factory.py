import pytest

from packages.replay.src.admission_store import AdmissionReceiptStore, get_admission_receipt_store
from packages.replay.src.postgres_admission_store import (
    PostgresAdmissionReceiptStore,
    normalize_postgres_dsn,
)


def test_postgres_async_url_is_normalized_for_sync_store() -> None:
    assert (
        normalize_postgres_dsn("postgresql+asyncpg://user:pass@db/service")
        == "postgresql://user:pass@db/service"
    )


def test_non_postgres_url_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        normalize_postgres_dsn("sqlite:///local.db")


def test_factory_defaults_to_sqlite_outside_production(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.delenv("DGX_ADMISSION_STORE_BACKEND", raising=False)
    monkeypatch.setenv("DGX_MODE", "test")
    monkeypatch.setenv("DGX_ADMISSION_STORE_PATH", str(tmp_path / "admission.sqlite3"))

    assert isinstance(get_admission_receipt_store(), AdmissionReceiptStore)


def test_factory_selects_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DGX_ADMISSION_STORE_BACKEND", "postgres")
    monkeypatch.setenv("DGX_ADMISSION_DATABASE_URL", "postgresql+asyncpg://user:pass@db/service")

    store = get_admission_receipt_store()

    assert isinstance(store, PostgresAdmissionReceiptStore)
    assert store.database_url == "postgresql://user:pass@db/service"


def test_production_defaults_to_postgres_and_fails_without_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DGX_ADMISSION_STORE_BACKEND", raising=False)
    monkeypatch.delenv("DGX_ADMISSION_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DGX_MODE", "production")

    with pytest.raises(RuntimeError, match="PostgreSQL"):
        get_admission_receipt_store()
