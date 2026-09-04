import uuid
from typing import Any
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.rag_pipeline.src.interfaces import RetrievedChunk, RetrieverAdapter


class PgRetrievedChunk:
    def __init__(
        self,
        chunk_id: str,
        text_content: str,
        score: float,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ):
        self.chunk_id = chunk_id
        self.text_content = text_content
        self.score = score
        self.document_id = document_id
        self.metadata = metadata or {}


class PostgresHybridRetriever(RetrieverAdapter):
    """
    Production-grade hybrid retriever combining pgvector cosine similarity
    and PostgreSQL full-text search (tsvector/plainto_tsquery) via Reciprocal Rank Fusion (RRF).
    Enforces strict tenant isolation and corpus version scoping.
    Includes transparent dialect fallback for SQLite-based testing environments.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        embedding_adapter: Any,
        tenant_id: str | uuid.UUID,
        k_rrf: int = 60,
    ):
        self.db = db_session
        self.embedding_adapter = embedding_adapter
        self.tenant_id = str(tenant_id)
        self.k_rrf = k_rrf

    async def retrieve(
        self, query: str, corpus_version_id: str, top_k: int
    ) -> list[RetrievedChunk]:
        # 1. Embed query
        query_embedding = await self.embedding_adapter.embed(query)

        # Detect dialect to determine if native pgvector/FTS is available
        dialect_name = "postgresql"
        bind = getattr(self.db, "bind", None)
        if bind is not None and not callable(bind):
            dialect = getattr(bind, "dialect", None)
            if dialect is not None and hasattr(dialect, "name") and isinstance(dialect.name, str):
                dialect_name = dialect.name.lower()
        elif hasattr(self.db, "sync_session"):
            sync_session = getattr(self.db, "sync_session", None)
            if sync_session is not None and hasattr(sync_session, "bind"):
                s_bind = getattr(sync_session, "bind", None)
                if s_bind is not None and hasattr(s_bind, "dialect"):
                    s_dialect = getattr(s_bind, "dialect", None)
                    if s_dialect is not None and hasattr(s_dialect, "name") and isinstance(s_dialect.name, str):
                        dialect_name = s_dialect.name.lower()

        if "sqlite" in dialect_name:
            return await self._retrieve_sqlite_fallback(
                query=query,
                query_embedding=query_embedding,
                corpus_version_id=corpus_version_id,
                top_k=top_k,
            )

        # 2. Native PostgreSQL Hybrid RRF Query
        sql = text(
            """
            WITH vector_search AS (
                SELECT c.id, c.text_content, c.document_id,
                       c.embedding <=> :embedding AS vector_distance,
                       RANK() OVER (ORDER BY c.embedding <=> :embedding ASC) as vector_rank
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE (CAST(d.corpus_version_id AS TEXT) = :corpus_version_id)
                  AND (CAST(c.tenant_id AS TEXT) = :tenant_id)
                ORDER BY vector_distance ASC
                LIMIT :top_k_pool
            ),
            fts_search AS (
                SELECT c.id, c.text_content, c.document_id,
                       ts_rank_cd(to_tsvector('english', c.text_content), plainto_tsquery('english', :query)) as fts_score,
                       RANK() OVER (ORDER BY ts_rank_cd(to_tsvector('english', c.text_content), plainto_tsquery('english', :query)) DESC) as fts_rank
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE (CAST(d.corpus_version_id AS TEXT) = :corpus_version_id)
                  AND (CAST(c.tenant_id AS TEXT) = :tenant_id)
                  AND to_tsvector('english', c.text_content) @@ plainto_tsquery('english', :query)
                ORDER BY fts_score DESC
                LIMIT :top_k_pool
            )
            SELECT
                COALESCE(v.id, f.id) as chunk_id,
                COALESCE(v.text_content, f.text_content) as text_content,
                COALESCE(v.document_id, f.document_id) as document_id,
                COALESCE(1.0 / (:k_rrf + v.vector_rank), 0.0) + COALESCE(1.0 / (:k_rrf + f.fts_rank), 0.0) as rrf_score
            FROM vector_search v
            FULL OUTER JOIN fts_search f ON v.id = f.id
            ORDER BY rrf_score DESC
            LIMIT :top_k
            """
        )

        result = await self.db.execute(
            sql,
            {
                "embedding": str(query_embedding),
                "query": query,
                "corpus_version_id": str(corpus_version_id),
                "tenant_id": str(self.tenant_id),
                "k_rrf": self.k_rrf,
                "top_k_pool": max(top_k * 5, 20),
                "top_k": top_k,
            },
        )

        chunks = []
        for row in result.mappings():
            chunks.append(
                PgRetrievedChunk(
                    chunk_id=str(row["chunk_id"]),
                    text_content=row["text_content"],
                    score=float(row["rrf_score"]),
                    document_id=str(row["document_id"]),
                    metadata={"retriever": "pgvector_fts_hybrid", "rrf_score": float(row["rrf_score"])},
                )
            )

        return chunks

    async def _retrieve_sqlite_fallback(
        self,
        query: str,
        query_embedding: list[float] | np.ndarray,
        corpus_version_id: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        In-memory / SQLite fallback computing exact vector cosine similarity
        and text term overlap, applying the identical RRF formula.
        """
        sql = text(
            """
            SELECT c.id, c.text_content, c.document_id, c.embedding
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE (CAST(d.corpus_version_id AS TEXT) = :corpus_version_id)
              AND (CAST(c.tenant_id AS TEXT) = :tenant_id)
            """
        )

        result = await self.db.execute(
            sql,
            {
                "corpus_version_id": str(corpus_version_id),
                "tenant_id": str(self.tenant_id),
            },
        )
        rows = list(result.mappings())
        if not rows:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        query_tokens = set(query.lower().split())

        vector_scores: list[tuple[str, float, dict[str, Any]]] = []
        text_scores: list[tuple[str, float, dict[str, Any]]] = []

        for row in rows:
            chunk_id = str(row["id"])
            text_content = row["text_content"]
            emb = row["embedding"]

            # Compute vector similarity if embedding present
            sim = 0.0
            if emb is not None:
                if isinstance(emb, str):
                    import json
                    try:
                        emb = json.loads(emb)
                    except Exception:
                        emb = [float(x) for x in emb.strip("[]").split(",") if x.strip()]
                c_vec = np.array(emb, dtype=np.float32)
                c_norm = np.linalg.norm(c_vec)
                if c_norm > 0:
                    sim = float(np.dot(q_vec, c_vec / c_norm))
            vector_scores.append((chunk_id, sim, row))

            # Compute text overlap
            c_tokens = set(text_content.lower().split())
            overlap = len(query_tokens.intersection(c_tokens)) / max(len(query_tokens), 1)
            text_scores.append((chunk_id, overlap, row))

        # Rank vector (descending similarity)
        vector_scores.sort(key=lambda x: x[1], reverse=True)
        vector_ranks = {cid: rank + 1 for rank, (cid, _, _) in enumerate(vector_scores)}

        # Rank text (descending overlap)
        text_scores.sort(key=lambda x: x[1], reverse=True)
        text_ranks = {cid: rank + 1 for rank, (cid, _, _) in enumerate(text_scores)}

        # Compute RRF
        combined_scores = []
        for row in rows:
            cid = str(row["id"])
            v_rank = vector_ranks.get(cid, 9999)
            t_rank = text_ranks.get(cid, 9999)
            rrf = (1.0 / (self.k_rrf + v_rank)) + (1.0 / (self.k_rrf + t_rank))
            combined_scores.append((rrf, row))

        combined_scores.sort(key=lambda x: x[0], reverse=True)

        return [
            PgRetrievedChunk(
                chunk_id=str(row["id"]),
                text_content=row["text_content"],
                score=float(score),
                document_id=str(row["document_id"]),
                metadata={"retriever": "sqlite_hybrid_rrf", "rrf_score": float(score)},
            )
            for score, row in combined_scores[:top_k]
        ]
