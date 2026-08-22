from typing import List, Any
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from packages.rag_pipeline.src.interfaces import RetrieverAdapter, RetrievedChunk
from apps.api.src.models_ingestion import ChunkORM

class PgRetrievedChunk:
    def __init__(self, chunk_id: str, text_content: str, score: float, document_id: str):
        self.chunk_id = chunk_id
        self.text_content = text_content
        self.score = score
        self.document_id = document_id
        self.metadata = {}

class PostgresHybridRetriever(RetrieverAdapter):
    def __init__(self, db_session: AsyncSession, embedding_adapter: Any):
        self.db = db_session
        self.embedding_adapter = embedding_adapter

    async def retrieve(self, query: str, corpus_version_id: str, top_k: int) -> List[RetrievedChunk]:
        # 1. Embed query
        query_embedding = await self.embedding_adapter.embed(query)
        
        # 2. RRF SQL Query combining pgvector and tsvector
        # Warning: For this to work efficiently in prod, we'd need appropriate indexes on tsvector and vector
        sql = text("""
            WITH vector_search AS (
                SELECT c.id, c.text_content, c.document_id,
                       c.embedding <=> :embedding AS vector_score,
                       RANK() OVER (ORDER BY c.embedding <=> :embedding) as vector_rank
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.corpus_version_id = :corpus_version_id
                ORDER BY vector_score
                LIMIT :top_k_pool
            ),
            keyword_search AS (
                SELECT c.id, c.text_content, c.document_id,
                       ts_rank_cd(to_tsvector('english', c.text_content), plainto_tsquery('english', :query)) as bm25_score,
                       RANK() OVER (ORDER BY ts_rank_cd(to_tsvector('english', c.text_content), plainto_tsquery('english', :query)) DESC) as keyword_rank
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.corpus_version_id = :corpus_version_id
                  AND to_tsvector('english', c.text_content) @@ plainto_tsquery('english', :query)
                ORDER BY bm25_score DESC
                LIMIT :top_k_pool
            )
            SELECT 
                COALESCE(v.id, k.id) as chunk_id,
                COALESCE(v.text_content, k.text_content) as text_content,
                COALESCE(v.document_id, k.document_id) as document_id,
                -- RRF formula: 1 / (k + rank) where k=60 is standard
                COALESCE(1.0 / (60 + v.vector_rank), 0.0) + COALESCE(1.0 / (60 + k.keyword_rank), 0.0) as rrf_score
            FROM vector_search v
            FULL OUTER JOIN keyword_search k ON v.id = k.id
            ORDER BY rrf_score DESC
            LIMIT :top_k
        """)
        
        # We fetch a larger pool for ranking
        result = await self.db.execute(sql, {
            "embedding": str(query_embedding),
            "query": query,
            "corpus_version_id": corpus_version_id,
            "top_k_pool": top_k * 5,
            "top_k": top_k
        })
        
        chunks = []
        for row in result.mappings():
            chunks.append(PgRetrievedChunk(
                chunk_id=str(row["chunk_id"]),
                text_content=row["text_content"],
                score=float(row["rrf_score"]),
                document_id=str(row["document_id"])
            ))
            
        return chunks
