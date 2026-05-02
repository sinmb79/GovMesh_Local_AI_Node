"""Pinned external scanner adapter for AV/YARA/CDR integrations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any

from packages.govmesh_common import sha256_file
from packages.govmesh_quarantine.inspection import QuarantineFinding


@dataclass(frozen=True)
class ExternalScannerConfig:
    name: str
    executable_path: str
    expected_executable_sha256: str
    args_template: tuple[str, ...]
    expected_auxiliary_hashes: dict[str, str] | None = None
    timeout_seconds: int = 30


@dataclass(frozen=True)
class ExternalScanReport:
    scanner: str
    ok: bool
    findings: tuple[QuarantineFinding, ...]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanner": self.scanner,
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
            "raw": self.raw,
        }


def run_external_scanner(config: ExternalScannerConfig, file_path: str | Path) -> ExternalScanReport:
    executable = Path(config.executable_path)
    if not executable.exists():
        raise FileNotFoundError(f"Scanner executable not found: {executable}")
    if sha256_file(executable) != config.expected_executable_sha256:
        raise PermissionError("Scanner executable hash mismatch")
    for path_text, expected_hash in (config.expected_auxiliary_hashes or {}).items():
        path = Path(path_text)
        if not path.exists() or sha256_file(path) != expected_hash:
            raise PermissionError(f"Scanner auxiliary hash mismatch: {path}")

    command = [str(executable), *[arg.replace("{file}", str(file_path)) for arg in config.args_template]]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=config.timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"{config.name} failed")
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{config.name} did not return JSON") from exc

    findings = tuple(
        QuarantineFinding(
            kind=str(item.get("kind", "external_finding")),
            severity=str(item.get("severity", "high")),
            scanner=config.name,
            detail=str(item.get("detail", ""))[:160],
        )
        for item in payload.get("findings", [])
    )
    return ExternalScanReport(scanner=config.name, ok=not findings, findings=findings, raw=payload)
