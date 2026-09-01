from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import Uuid

from apps.api.src.models import _JSON_TYPE, Base, _utcnow


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    """Use JSON storage for local SQLite while retaining pgvector in Postgres."""
    return "JSON"


class CorpusVersionORM(Base):
    __tablename__ = "corpus_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )

    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    license_info: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    documents: Mapped[list[DocumentORM]] = relationship(
        "DocumentORM", back_populates="corpus_version"
    )
    index_versions: Mapped[list[IndexVersionORM]] = relationship(
        "IndexVersionORM", back_populates="corpus_version"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "source_name", "version_tag", name="uq_corpus_version"),
        Index("ix_corpus_versions_tenant_id", "tenant_id"),
        Index("ix_corpus_versions_manifest_hash", "manifest_hash"),
    )


class IndexVersionORM(Base):
    __tablename__ = "index_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    corpus_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("corpus_versions.id"), nullable=False
    )

    version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    chunking_config_json: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    corpus_version: Mapped[CorpusVersionORM] = relationship(
        "CorpusVersionORM", back_populates="index_versions"
    )
    chunks: Mapped[list[ChunkORM]] = relationship("ChunkORM", back_populates="index_version")

    __table_args__ = (
        UniqueConstraint("corpus_version_id", "version_tag", name="uq_index_version"),
        Index("ix_index_versions_tenant_id", "tenant_id"),
    )


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    corpus_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("corpus_versions.id"), nullable=False
    )

    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_metadata_json: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)
    license_info: Mapped[str] = mapped_column(String(255), nullable=False)
    minio_object_name: Mapped[str] = mapped_column(String(512), nullable=False)

    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    corpus_version: Mapped[CorpusVersionORM] = relationship(
        "CorpusVersionORM", back_populates="documents"
    )
    chunks: Mapped[list[ChunkORM]] = relationship("ChunkORM", back_populates="document")

    __table_args__ = (
        UniqueConstraint("corpus_version_id", "document_hash", name="uq_document_hash_per_corpus"),
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_document_hash", "document_hash"),
    )


class ChunkORM(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    index_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("index_versions.id"), nullable=False
    )

    chunk_index: Mapped[int] = mapped_column(nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)

    # pgvector embedding: Assuming 384 dimensions for all-MiniLM-L6-v2
    embedding = mapped_column(Vector(384))

    document: Mapped[DocumentORM] = relationship("DocumentORM", back_populates="chunks")
    index_version: Mapped[IndexVersionORM] = relationship(
        "IndexVersionORM", back_populates="chunks"
    )

    __table_args__ = (
        Index("ix_chunks_tenant_id", "tenant_id"),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_index_version_id", "index_version_id"),
    )
