"""Build a public release bundle with checksums."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "dist", "evidence", "reports", ".govmesh-local"}
INCLUDE_ROOT_ITEMS = [
    "README.md",
    "README.en.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    ".env.example",
    "apps",
    "configs",
    "docs",
    "packages",
    "samples",
    "scripts",
    "tests",
]


def build_release_bundle(*, out_dir: str | Path = "dist") -> dict:
    version = _version()
    dist = ROOT / out_dir
    work = dist / f"govmesh-local-ai-node-v{version}"
    zip_path = dist / f"govmesh-local-ai-node-v{version}.zip"
    checksums_path = dist / "SHA256SUMS.txt"
    manifest_path = dist / "release_manifest.json"

    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    copied: list[dict] = []
    for item in INCLUDE_ROOT_ITEMS:
        source = ROOT / item
        if not source.exists():
            continue
        target = work / item
        if source.is_dir():
            _copy_tree(source, target, copied, work)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(_entry(target, work))

    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(work.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(dist).as_posix())

    zip_sha = _sha256(zip_path)
    checksums_path.write_text(f"{zip_sha}  {zip_path.name}\n", encoding="utf-8")
    manifest = {
        "name": "govmesh-local-ai-node",
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "zip": zip_path.name,
        "zip_sha256": zip_sha,
        "file_count": len(copied),
        "files": copied,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "version": version,
        "work_dir": str(work),
        "zip_path": str(zip_path),
        "checksums_path": str(checksums_path),
        "manifest_path": str(manifest_path),
        "zip_sha256": zip_sha,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dist")
    args = parser.parse_args(argv)
    result = build_release_bundle(out_dir=args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _copy_tree(source: Path, target: Path, copied: list[dict], bundle_root: Path) -> None:
    for path in sorted(source.rglob("*")):
        rel_parts = path.relative_to(ROOT).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if path.is_dir():
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied.append(_entry(destination, bundle_root))


def _entry(path: Path, bundle_root: Path) -> dict:
    return {
        "path": path.relative_to(bundle_root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _version() -> str:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return payload["project"]["version"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
