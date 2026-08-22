import argparse
import asyncio
import json
import logging
import uuid
import sys

from apps.api.src.database import AsyncSessionLocal
from packages.ingestion.src.storage import MinioStorage
from packages.ingestion.src.orchestrator import IngestionOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_ingestion(source_path: str, version_tag: str):
    logger.info(f"Starting ingestion from {source_path} (Version: {version_tag})")
    
    # 1. Read dataset
    # Expecting jsonl format (like scifact corpus.jsonl)
    documents = []
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    documents.append(json.loads(line))
    except Exception as e:
        logger.error(f"Failed to read source file: {e}")
        sys.exit(1)
        
    if not documents:
        logger.error("No documents found in source file.")
        sys.exit(1)
        
    logger.info(f"Loaded {len(documents)} documents.")

    # We assume an open source license for the public scifact dataset
    license_info = "CC BY 4.0"

    # Setup MinIO and Orchestrator
    storage = MinioStorage()
    tenant_id = uuid.uuid4() # Mocking a tenant ID for the CLI context, in real system this is passed
    
    async with AsyncSessionLocal() as session:
        orchestrator = IngestionOrchestrator(session, storage, tenant_id)
        
        try:
            manifest_hash = await orchestrator.ingest_corpus(
                source_name="scifact",
                version_tag=version_tag,
                documents=documents,
                license_info=license_info
            )
            logger.info(f"Successfully ingested corpus. Manifest Hash: {manifest_hash}")
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            await session.rollback()
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Ingest a document corpus for DriftGuard-X.")
    parser.add_argument("--source", required=True, help="Path to the JSONL dataset (e.g. data/scifact/corpus.jsonl)")
    parser.add_argument("--corpus-version", required=True, help="Explicit version tag (e.g. v1)")
    args = parser.parse_args()

    if args.corpus_version.lower() == "latest":
        logger.error("The 'latest' tag is forbidden. You must use explicit, immutable version tags.")
        sys.exit(1)

    asyncio.run(run_ingestion(args.source, args.corpus_version))

if __name__ == "__main__":
    main()
