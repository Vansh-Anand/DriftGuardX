import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from apps.api.src.models import _JSON_TYPE, Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ManifestORM(Base):
    __tablename__ = "manifests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Store the canonical JSON payload
    payload: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)

    # Dependencies we might query against for verification
    corpus_version_id: Mapped[str] = mapped_column(String, nullable=True)
    model_identifier: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
