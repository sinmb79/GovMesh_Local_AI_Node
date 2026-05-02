"""Build a local evidence package for security and release review."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/latest")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args(argv)

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    if not args.skip_pytest:
        _run([sys.executable, "-m", "pytest"], out / "pytest.txt")
    _run([sys.executable, "scripts/release_gate.py", "--skip-pytest"], out / "release_gate.txt")

    manifest = _build_manifest()
    (out / "file_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "test_command": "python -m pytest",
        "release_gate": "python scripts/release_gate.py",
        "file_count": len(manifest),
        "security_notes": [
            "local-only default",
            "127.0.0.1 bind default",
            "fake PII restricted to tests/corpus",
            "approved model registry required for local llama.cpp execution",
        ],
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
    return 0


def _run(command: list[str], output: Path) -> None:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    output.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _build_manifest() -> list[dict]:
    entries: list[dict] = []
    skip_dirs = {".git", "__pycache__", ".pytest_cache", "dist", "reports", "evidence", ".govmesh-local"}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in skip_dirs for part in path.relative_to(ROOT).parts):
            continue
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return entries


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
