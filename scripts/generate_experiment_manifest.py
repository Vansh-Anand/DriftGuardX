"""Generate a content-addressed manifest binding source, locks, commands, and results."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("apps", "packages", "tests", "scripts", "deploy", "infra", ".github")
SOURCE_FILES = ("pyproject.toml", "Makefile", "pytest.ini")
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "htmlcov",
    "node_modules",
    "playwright-report",
    "results",
    "test-results",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def source_inventory() -> dict[str, str]:
    candidates = [REPO_ROOT / path for path in SOURCE_FILES]
    for root_name in SOURCE_ROOTS:
        root = REPO_ROOT / root_name
        if root.exists():
            candidates.extend(path for path in root.rglob("*") if path.is_file())

    inventory: dict[str, str] = {}
    for path in sorted(set(candidates)):
        relative = path.relative_to(REPO_ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        inventory[relative.as_posix()] = sha256_file(path)
    return inventory


def artifact_record(raw_path: str) -> dict[str, Any]:
    path = (REPO_ROOT / raw_path).resolve()
    path.relative_to(REPO_ROOT.resolve())
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", action="append", default=[], help="Result artifact path")
    parser.add_argument("--command", action="append", default=[], help="Exact benchmark command")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--evidence-kind", default="synthetic_simulation")
    parser.add_argument("--release", default="2.0.0-rc.1")
    parser.add_argument("--output-dir", default="releases/2.0.0-rc.1")
    args = parser.parse_args()

    inventory = source_inventory()
    source_digest = sha256_bytes(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    )
    lock_paths = ["uv.lock", "requirements.lock", "apps/web/package-lock.json"]
    manifest = {
        "schema_version": "1.0",
        "release": args.release,
        "evidence_kind": args.evidence_kind,
        "evidence_notice": (
            "Controlled synthetic or mocked-integration evidence only; this manifest does not "
            "establish production effectiveness, safety certification, or patentability."
        ),
        "source": {
            "git_head": git("rev-parse", "HEAD"),
            "git_dirty": bool(git("status", "--porcelain")),
            "tracked_diff_sha256": sha256_bytes(
                subprocess.run(
                    ["git", "diff", "--binary", "HEAD"],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                ).stdout
            ),
            "inventory_sha256": source_digest,
            "files": inventory,
        },
        "dependency_locks": [artifact_record(path) for path in lock_paths],
        "experiment": {"commands": args.command, "seed": args.seed},
        "results": [artifact_record(path) for path in args.result],
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest_id = sha256_bytes(canonical)
    document = {"manifest_sha256": manifest_id, **manifest}

    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"experiment-manifest-{manifest_id}.json"
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if output_path.exists() and output_path.read_text(encoding="utf-8") != rendered:
        raise RuntimeError(f"Refusing to overwrite immutable manifest: {output_path}")
    output_path.write_text(rendered, encoding="utf-8", newline="\n")
    print(output_path.relative_to(REPO_ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
