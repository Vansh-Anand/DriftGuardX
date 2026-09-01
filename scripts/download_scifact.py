"""Securely materialize the exact SciFact snapshot used by controlled replay."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
DESTINATION = Path("data/raw/scifact")
EXPECTED_SHA256 = {
    "corpus.jsonl": "dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6",
    "queries.jsonl": "8ff84a7c903f722981cd8d595c022660140c51867b27608a6d4910db86080313",
    "qrels/test.tsv": "0864bb985e0ca2367ba217977e72004d549054b2b06666ed9d4825ac7c21284c",
    "qrels/train.tsv": "a53f2114831916c096b6c37d9e54da68cef4efdcdbd5ed46533601af972acf1d",
}


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination_resolved = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if destination_resolved != target and destination_resolved not in target.parents:
            raise ValueError(f"archive contains unsafe path: {member.filename}")
    archive.extractall(destination)


def _find_snapshot(extracted_root: Path) -> Path:
    matches = [path.parent for path in extracted_root.rglob("corpus.jsonl")]
    for match in matches:
        if (match / "queries.jsonl").is_file() and (match / "qrels" / "test.tsv").is_file():
            return match
    raise FileNotFoundError("downloaded archive does not contain a SciFact snapshot")


def _verify(snapshot: Path) -> None:
    for relative_path, expected in EXPECTED_SHA256.items():
        path = snapshot / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"snapshot is missing {relative_path}")
        observed = _digest(path)
        if observed != expected:
            raise ValueError(
                f"SciFact integrity failure for {relative_path}: "
                f"expected {expected}, got {observed}"
            )


def download_and_extract(destination: Path = DESTINATION) -> None:
    """Download with verified TLS, validate content hashes, then install atomically."""
    if destination.exists():
        _verify(destination)
        return

    with tempfile.TemporaryDirectory(prefix="dgx-scifact-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        archive_path = temporary_root / "scifact.zip"
        extracted_root = temporary_root / "extracted"
        extracted_root.mkdir()

        if not URL.startswith("https://"):
            raise ValueError("SciFact source URL must use HTTPS")
        request = urllib.request.Request(URL, headers={"User-Agent": "DriftGuardX/2.0"})
        with (
            urllib.request.urlopen(  # noqa: S310 - URL is an HTTPS constant checked above
                request, timeout=60
            ) as response,
            archive_path.open("wb") as out,
        ):
            shutil.copyfileobj(response, out)

        with zipfile.ZipFile(archive_path) as archive:
            _safe_extract(archive, extracted_root)

        snapshot = _find_snapshot(extracted_root)
        _verify(snapshot)

        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".scifact-install-", dir=destination.parent
        ) as install_directory:
            staged = Path(install_directory) / "snapshot"
            shutil.copytree(snapshot, staged)
            _verify(staged)
            staged.replace(destination)
        _verify(destination)


if __name__ == "__main__":
    download_and_extract()
    print(f"verified SciFact snapshot at {DESTINATION}")
