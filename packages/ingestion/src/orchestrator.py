import hashlib
import json
import logging
import uuid
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from packages.ingestion.src.storage import MinioStorage
from packages.ingestion.src.scanner import PIISecretScanner
from packages.ingestion.src.chunker import BaseChunker
from packages.ingestion.src.embedder import LocalEmbedder
from apps.api.src.models_ingestion import CorpusVersionORM, IndexVersionORM, DocumentORM, ChunkORM

logger = logging.getLogger(__name__)

class IngestionOrchestrator:
    def __init__(self, db_session: AsyncSession, storage: MinioStorage, tenant_id: uuid.UUID):
        self.db = db_session
        self.storage = storage
        self.scanner = PIISecretScanner()
        self.chunker = BaseChunker()
        self.embedder = LocalEmbedder()
        self.tenant_id = tenant_id

    async def ingest_corpus(self, source_name: str, version_tag: str, documents: List[Dict[str, Any]], license_info: str) -> str:
        """
        Orchestrates full ingestion of a document corpus.
        Returns the corpus manifest_hash.
        """
        # 1. PII Scan all documents before any storage or processing
        safe_docs = []
        for doc in documents:
            text = doc.get("text", "")
            if not self.scanner.scan_text(text):
                safe_docs.append(doc)
            else:
                logger.warning(f"Document rejected due to PII/Secret detection: {doc.get('id', 'unknown')}")

        if not safe_docs:
            raise ValueError("No safe documents to ingest after scanning.")

        # 2. Upload raw docs to MinIO and collect hashes
        doc_records = []
        doc_hashes = []
        for doc in safe_docs:
            doc_hash = self.storage.upload_document(f"raw/{source_name}/{version_tag}/{doc.get('id', uuid.uuid4())}.json", doc)
            doc_hashes.append(doc_hash)
            doc_records.append({"hash": doc_hash, "data": doc})

        # 3. Compute Corpus Manifest Hash (Bind all documents securely)
        doc_hashes.sort()
        manifest = {
            "source": source_name,
            "version": version_tag,
            "documents": doc_hashes,
            "chunk_size": self.chunker.chunk_size,
            "chunk_overlap": self.chunker.chunk_overlap,
            "embedding_model": self.embedder.model_name
        }
        manifest_str = json.dumps(manifest, sort_keys=True)
        manifest_hash = hashlib.sha256(manifest_str.encode('utf-8')).hexdigest()

        # 4. Upload manifest to MinIO
        self.storage.upload_manifest(version_tag, manifest)

        # 5. Store in Postgres (CorpusVersion, IndexVersion)
        corpus = CorpusVersionORM(
            tenant_id=self.tenant_id,
            source_name=source_name,
            version_tag=version_tag,
            manifest_hash=manifest_hash,
            license_info=license_info
        )
        self.db.add(corpus)
        await self.db.flush()

        index = IndexVersionORM(
            tenant_id=self.tenant_id,
            corpus_version_id=corpus.id,
            version_tag=version_tag,
            embedding_model_version=self.embedder.model_name,
            chunking_config_json={"size": self.chunker.chunk_size, "overlap": self.chunker.chunk_overlap}
        )
        self.db.add(index)
        await self.db.flush()

        # 6. Process chunks and embeddings
        for rec in doc_records:
            doc_data = rec["data"]
            doc_orm = DocumentORM(
                tenant_id=self.tenant_id,
                corpus_version_id=corpus.id,
                document_hash=rec["hash"],
                source_metadata_json={"title": doc_data.get("title", "")},
                license_info=license_info,
                minio_object_name=f"raw/{source_name}/{version_tag}/{doc_data.get('id', 'doc')}.json"
            )
            self.db.add(doc_orm)
            await self.db.flush()

            text = doc_data.get("text", "")
            chunks = self.chunker.chunk_text(text)
            embeddings = self.embedder.embed_texts(chunks)

            for i, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
                chunk_orm = ChunkORM(
                    tenant_id=self.tenant_id,
                    document_id=doc_orm.id,
                    index_version_id=index.id,
                    chunk_index=i,
                    text_content=chunk_text,
                    embedding=emb
                )
                self.db.add(chunk_orm)

        await self.db.commit()
        return manifest_hash
