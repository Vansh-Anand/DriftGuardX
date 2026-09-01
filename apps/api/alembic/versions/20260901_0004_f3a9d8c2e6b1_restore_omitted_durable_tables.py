"""Restore durable tables omitted by legacy no-op revisions.

Revision ID: f3a9d8c2e6b1
Revises: b7e1c9d4f2a6
Create Date: 2026-09-01 19:20:00

Two historical revisions named ingestion and manifest migrations contained no
operations.  Graph and bandit persistence models were also outside Alembic's
metadata.  This revision creates the complete durable schema explicitly so a
fresh deployment and an upgraded deployment converge on the same structure.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "f3a9d8c2e6b1"
down_revision: str | None = "b7e1c9d4f2a6"
branch_labels: str | None = None
depends_on: str | None = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _json_type() -> sa.types.TypeEngine[object]:
    if _is_postgresql():
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _embedding_type() -> sa.types.TypeEngine[object]:
    if _is_postgresql():
        return Vector(384)
    return sa.JSON()


def upgrade() -> None:
    if _is_postgresql():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    json_type = _json_type()
    op.create_table(
        "corpus_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("license_info", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manifest_hash"),
        sa.UniqueConstraint("tenant_id", "source_name", "version_tag", name="uq_corpus_version"),
    )
    op.create_index("ix_corpus_versions_manifest_hash", "corpus_versions", ["manifest_hash"])
    op.create_index("ix_corpus_versions_tenant_id", "corpus_versions", ["tenant_id"])

    op.create_table(
        "index_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("corpus_version_id", sa.Uuid(), nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("embedding_model_version", sa.String(length=128), nullable=False),
        sa.Column("chunking_config_json", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corpus_version_id"], ["corpus_versions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("corpus_version_id", "version_tag", name="uq_index_version"),
    )
    op.create_index("ix_index_versions_tenant_id", "index_versions", ["tenant_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("corpus_version_id", sa.Uuid(), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("source_metadata_json", json_type, nullable=False),
        sa.Column("license_info", sa.String(length=255), nullable=False),
        sa.Column("minio_object_name", sa.String(length=512), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corpus_version_id"], ["corpus_versions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "corpus_version_id", "document_hash", name="uq_document_hash_per_corpus"
        ),
    )
    op.create_index("ix_documents_document_hash", "documents", ["document_hash"])
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("index_version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("embedding", _embedding_type(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["index_version_id"], ["index_versions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_index_version_id", "chunks", ["index_version_id"])
    op.create_index("ix_chunks_tenant_id", "chunks", ["tenant_id"])

    op.create_table(
        "manifests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("corpus_version_id", sa.String(), nullable=True),
        sa.Column("model_identifier", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manifests_manifest_hash", "manifests", ["manifest_hash"])

    op.create_table(
        "causal_graphs",
        sa.Column("graph_hash", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("trace_digest", sa.String(length=64), nullable=False),
        sa.Column("builder_version", sa.String(length=32), nullable=False),
        sa.Column("nodes_json", json_type, nullable=False),
        sa.Column("edges_json", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("graph_hash"),
    )
    op.create_index("ix_causal_graphs_run_id", "causal_graphs", ["run_id"])
    op.create_index("ix_causal_graphs_tenant_id", "causal_graphs", ["tenant_id"])

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("graph_hash", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("edge_type", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("properties_json", json_type, nullable=False),
        sa.ForeignKeyConstraint(["graph_hash"], ["causal_graphs.graph_hash"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_graph_edges_graph_hash", "graph_edges", ["graph_hash"])
    op.create_index("ix_graph_edges_source_id", "graph_edges", ["source_id"])
    op.create_index("ix_graph_edges_target_id", "graph_edges", ["target_id"])

    op.create_table(
        "bandit_states",
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("total_budget", sa.Float(), nullable=False),
        sa.Column("remaining_budget", sa.Float(), nullable=False),
        sa.Column("exploration_constant", sa.Float(), nullable=False),
        sa.Column("pulls_json", json_type, nullable=True),
        sa.Column("rewards_json", json_type, nullable=True),
        sa.Column("total_pulls", sa.Integer(), nullable=True),
        sa.Column("stop_reason", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("run_id"),
    )


def downgrade() -> None:
    op.drop_table("bandit_states")
    op.drop_index("ix_graph_edges_target_id", table_name="graph_edges")
    op.drop_index("ix_graph_edges_source_id", table_name="graph_edges")
    op.drop_index("ix_graph_edges_graph_hash", table_name="graph_edges")
    op.drop_table("graph_edges")
    op.drop_index("ix_causal_graphs_tenant_id", table_name="causal_graphs")
    op.drop_index("ix_causal_graphs_run_id", table_name="causal_graphs")
    op.drop_table("causal_graphs")
    op.drop_index("ix_manifests_manifest_hash", table_name="manifests")
    op.drop_table("manifests")
    op.drop_index("ix_chunks_tenant_id", table_name="chunks")
    op.drop_index("ix_chunks_index_version_id", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_tenant_id", table_name="documents")
    op.drop_index("ix_documents_document_hash", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_index_versions_tenant_id", table_name="index_versions")
    op.drop_table("index_versions")
    op.drop_index("ix_corpus_versions_tenant_id", table_name="corpus_versions")
    op.drop_index("ix_corpus_versions_manifest_hash", table_name="corpus_versions")
    op.drop_table("corpus_versions")
