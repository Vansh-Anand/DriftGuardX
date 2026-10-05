"""Persistent models for distributed replay/recovery admission."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from apps.api.src.models import Base

_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class AdmissionResourcePoolORM(Base):
    __tablename__ = "admission_resource_pools"

    pool_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    budget_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    spent_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdmissionReceiptORM(Base):
    __tablename__ = "admission_receipts"
    __table_args__ = (
        UniqueConstraint("binding_hash", name="uq_admission_receipts_binding_hash"),
        Index("ix_admission_receipts_tenant_status", "tenant_id", "status"),
        Index("ix_admission_receipts_pool_status", "resource_pool_id", "status"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(_JSON_TYPE, nullable=False)
    reserved_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    resource_pool_id: Mapped[str] = mapped_column(
        ForeignKey("admission_resource_pools.pool_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdmissionAuditEventORM(Base):
    __tablename__ = "admission_audit_events"
    __table_args__ = (
        UniqueConstraint("receipt_id", "sequence", name="uq_admission_event_sequence"),
        UniqueConstraint("event_hash", name="uq_admission_event_hash"),
        Index("ix_admission_events_receipt_sequence", "receipt_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admission_receipts.receipt_id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(_JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdmissionExecutionAttestationORM(Base):
    __tablename__ = "admission_execution_attestations"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admission_receipts.receipt_id", ondelete="CASCADE"), primary_key=True
    )
    attestation_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(_JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
