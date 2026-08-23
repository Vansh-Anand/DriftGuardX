import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

from sqlalchemy.future import select

from apps.api.src.database import AsyncSessionLocal
from apps.api.src.models_ingestion import CorpusVersionORM
from packages.ingestion.src.orchestrator import IngestionOrchestrator
from packages.ingestion.src.storage import MinioStorage

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
REGISTRY_FILE = ROOT_DIR / "data" / "dataset_registry.json"

async def run_ingestion(dataset: str, split: str):
    logger.info(f"Starting ingestion for dataset {dataset} (split: {split})")

    if not REGISTRY_FILE.exists():
        logger.error("Dataset registry not found. Run manage_datasets first.")
        sys.exit(1)

    with open(REGISTRY_FILE) as f:
        registry = json.load(f)

    if dataset not in registry:
        logger.error(f"Dataset {dataset} not found in registry.")
        sys.exit(1)

    version_tag = f"{split}_{registry[dataset]['sha256'][:8]}"

    async with AsyncSessionLocal() as session:
        # Check if already ingested
        stmt = select(CorpusVersionORM).where(
            CorpusVersionORM.source_name == dataset,
            CorpusVersionORM.version_tag == version_tag
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            logger.info(f"Dataset {dataset} with version {version_tag} is already ingested.")
            return

    # Load corpus
    corpus_path = ROOT_DIR / "data" / "raw" / dataset / "corpus.jsonl"
    if not corpus_path.exists():
        logger.error(f"Corpus file not found at {corpus_path}")
        sys.exit(1)

    documents = []
    try:
        with open(corpus_path, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    doc = json.loads(line)
                    # Mapping _id to id if necessary
                    if "_id" in doc and "id" not in doc:
                        doc["id"] = doc["_id"]
                    documents.append(doc)
    except Exception as e:
        logger.error(f"Failed to read source file: {e}")
        sys.exit(1)

    if not documents:
        logger.error("No documents found in source file.")
        sys.exit(1)

    logger.info(f"Loaded {len(documents)} documents.")

    # Using a deterministic tenant ID for benchmarks
    tenant_id = uuid.uuid5(uuid.NAMESPACE_DNS, "benchmark.driftguardx.local")
    storage = MinioStorage()

    async with AsyncSessionLocal() as session:
        orchestrator = IngestionOrchestrator(session, storage, tenant_id)

        try:
            manifest_hash = await orchestrator.ingest_corpus(
                source_name=dataset,
                version_tag=version_tag,
                documents=documents,
                license_info="Various BEIR Licenses"
            )
            logger.info(f"Successfully ingested corpus. Manifest Hash: {manifest_hash}")
        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            await session.rollback()
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Ingest a document corpus for DriftGuard-X benchmarks.")
    parser.add_argument("--dataset", required=True, help="Dataset canonical name (e.g. scifact)")
    parser.add_argument("--split", required=True, help="Split name (e.g. test)")
    args = parser.parse_args()

    asyncio.run(run_ingestion(args.dataset, args.split))

if __name__ == "__main__":
    main()
