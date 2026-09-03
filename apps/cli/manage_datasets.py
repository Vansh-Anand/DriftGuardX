import hashlib
import json
import logging
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REGISTRY_FILE = DATA_DIR / "dataset_registry.json"

DATASETS = ["scifact", "arguana", "nfcorpus", "fiqa", "hotpotqa", "nq"]


def compute_sha256(filepath: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def is_safe_path(base_path: Path, path: str) -> bool:
    matchpath = os.path.abspath(os.path.join(base_path, path))
    return matchpath.startswith(os.path.abspath(base_path))


def validate_beir_structure(raw_dir: Path) -> bool:
    corpus_exists = (raw_dir / "corpus.jsonl").exists()
    queries_exists = (raw_dir / "queries.jsonl").exists()
    qrels_dir = raw_dir / "qrels"
    qrels_exists = (
        qrels_dir.exists() and qrels_dir.is_dir() and len(list(qrels_dir.glob("*.tsv"))) > 0
    )
    return corpus_exists and queries_exists and qrels_exists


def count_lines(filepath: Path) -> int:
    if not filepath.exists():
        return 0
    with open(filepath, encoding="utf-8") as f:
        return sum(1 for _ in f)


def extract_and_register() -> None:
    if not RAW_DIR.exists():
        RAW_DIR.mkdir(parents=True)

    registry = {}
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE) as f:
            try:
                registry = json.load(f)
            except json.JSONDecodeError:
                registry = {}

    for dataset in DATASETS:
        zip_path = DATA_DIR / f"{dataset}.zip"
        if not zip_path.exists():
            logger.warning(f"Zip file for {dataset} not found at {zip_path}")
            continue

        raw_dataset_dir = RAW_DIR / dataset

        # Check if already processed
        current_hash = compute_sha256(zip_path)
        if (
            dataset in registry
            and registry[dataset].get("sha256") == current_hash
            and raw_dataset_dir.exists()
        ):
            logger.info(f"Dataset {dataset} already extracted and up-to-date.")
            continue

        logger.info(f"Processing {dataset}...")

        # Safely extract
        if not raw_dataset_dir.exists():
            raw_dataset_dir.mkdir(parents=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                if not is_safe_path(raw_dataset_dir, member.filename):
                    logger.error(f"Unsafe path detected in {dataset}.zip: {member.filename}")
                    continue
                # Extract file
                # Need to handle nested directories. Usually BEIR zips have a top-level dir like `scifact/corpus.jsonl`
                # Let's extract everything, but we might need to find the actual root.
                zf.extract(member, raw_dataset_dir)

        # Find BEIR root. It might be directly in raw_dataset_dir or in raw_dataset_dir/<dataset>
        beir_root = raw_dataset_dir
        if not (beir_root / "corpus.jsonl").exists():
            # Check subdirectories
            for subdir in beir_root.iterdir():
                if subdir.is_dir() and (subdir / "corpus.jsonl").exists():
                    beir_root = subdir
                    break

        if not validate_beir_structure(beir_root):
            logger.error(
                f"BEIR structure validation failed for {dataset}. Missing corpus.jsonl, queries.jsonl, or qrels/*.tsv"
            )
            continue

        corpus_count = count_lines(beir_root / "corpus.jsonl")
        queries_count = count_lines(beir_root / "queries.jsonl")

        splits = []
        qrels_count = 0
        qrels_dir = beir_root / "qrels"
        if qrels_dir.exists():
            for tsv_file in qrels_dir.glob("*.tsv"):
                splits.append(tsv_file.stem)
                qrels_count += max(0, count_lines(tsv_file) - 1)  # -1 for header

        # Move files to root of raw_dataset_dir if they were in a subdir to normalize
        if beir_root != raw_dataset_dir:
            import shutil

            for item in beir_root.iterdir():
                dest = raw_dataset_dir / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                shutil.move(str(item), str(raw_dataset_dir))
            shutil.rmtree(beir_root)

        registry[dataset] = {
            "canonical_name": dataset,
            "original_zip_path": str(zip_path.relative_to(ROOT_DIR)),
            "sha256": current_hash,
            "corpus_document_count": corpus_count,
            "query_count": queries_count,
            "qrels_count": qrels_count,
            "available_splits": splits,
            "extraction_timestamp": datetime.now(UTC).isoformat(),
            "preprocessing_chunking_configuration_version": "v1.0.0",
        }

        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=4)

        logger.info(f"Successfully processed and registered {dataset}.")


if __name__ == "__main__":
    extract_and_register()
