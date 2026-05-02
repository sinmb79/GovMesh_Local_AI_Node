"""Local release gate for GovMesh MVP."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAKE_PII_PATTERNS = [
    re.compile(r"\b\d{6}-[1-4]\d{6}\b"),
]
ALLOWED_FAKE_PII_FILES = {
    "tests/test_policy.py",
    "tests/test_rag_runtime.py",
    "tests/test_node_agent.py",
    "tests/test_e2e.py",
    "samples/policy_corpus.jsonl",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args(argv)

    checks = [
        ("required files", check_required_files),
        ("fake pii scope", check_fake_pii_scope),
        ("localhost defaults", check_localhost_defaults),
    ]
    failures: list[str] = []
    for name, check in checks:
        ok, message = check()
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {message}")
        if not ok:
            failures.append(name)

    if not args.skip_pytest:
        completed = subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT, text=True)
        if completed.returncode != 0:
            failures.append("pytest")

    if failures:
        print(f"Release gate failed: {', '.join(failures)}")
        return 1
    print("Release gate passed.")
    return 0


def check_required_files() -> tuple[bool, str]:
    required = [
        "README.md",
        "docs/DEVELOPMENT_STATUS.md",
        "docs/RUNBOOK.md",
        "docs/CORPUS_COLLECTION.md",
        "docs/RELEASE_CHECKLIST.md",
        "apps/control_plane/app.py",
        "apps/admin_ui/app.py",
        "apps/node_agent/cli.py",
        "apps/quarantine_gateway/app.py",
        "packages/govmesh_policy/scanner.py",
        "packages/govmesh_rag/service.py",
        "packages/govmesh_runtime/providers.py",
        "scripts/build_evidence_package.py",
        "scripts/govmesh_doctor.py",
        "scripts/install_windows_service.ps1",
    ]
    missing = [path for path in required if not (ROOT / path).exists()]
    return (not missing, "all present" if not missing else f"missing {missing}")


def check_fake_pii_scope() -> tuple[bool, str]:
    offenders: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or _skip_path(path):
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in FAKE_PII_PATTERNS) and rel not in ALLOWED_FAKE_PII_FILES:
            offenders.append(rel)
    return (not offenders, "fake PII limited to tests/corpus" if not offenders else ", ".join(offenders))


def check_localhost_defaults() -> tuple[bool, str]:
    files = [
        ROOT / "README.md",
        ROOT / ".env.example",
        ROOT / "docs/RUNBOOK.md",
        ROOT / "apps/control_plane/__main__.py",
        ROOT / "apps/quarantine_gateway/__main__.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in files if "127.0.0.1" not in path.read_text(encoding="utf-8")]
    return (not missing, "localhost defaults present" if not missing else f"missing localhost in {missing}")


def _skip_path(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    return bool(parts & {"__pycache__", ".pytest_cache", ".git", "reports", "dist", "evidence", ".govmesh-local"})


if __name__ == "__main__":
    raise SystemExit(main())
