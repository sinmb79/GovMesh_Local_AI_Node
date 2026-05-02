"""Layered file inspection for the Quarantine Gateway."""

from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any
import zipfile

from packages.govmesh_common import sha256_file


RISKY_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".dll", ".scr", ".vbs"}
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar"}
MAX_ARCHIVE_ENTRIES = 200
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_TEXT_SCAN_BYTES = 1024 * 1024


SIGNATURE_RULES = {
    "powershell_invoke_expression": re.compile(rb"Invoke-Expression", re.I),
    "powershell_encoded_command": re.compile(rb"powershell\s+-enc", re.I),
    "prompt_injection_ignore_previous": re.compile(rb"ignore\s+previous\s+instructions", re.I),
    "office_macro_autoopen": re.compile(rb"AutoOpen|Document_Open|Workbook_Open", re.I),
    "office_wscript_shell": re.compile(rb"WScript\.Shell|CreateObject\s*\(", re.I),
    "pdf_javascript": re.compile(rb"/JavaScript|/OpenAction|/JS\b", re.I),
}


@dataclass(frozen=True)
class QuarantineFinding:
    kind: str
    severity: str
    scanner: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "scanner": self.scanner,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class QuarantineReport:
    filename: str
    sha256: str
    size_bytes: int
    media_type: str
    findings: tuple[QuarantineFinding, ...]
    recommended_action: str
    scanners: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.findings

    def finding_kinds(self) -> list[str]:
        return sorted({finding.kind for finding in self.findings})

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "passed": self.passed,
            "recommended_action": self.recommended_action,
            "scanners": list(self.scanners),
            "findings": [finding.to_dict() for finding in self.findings],
        }


def inspect_file(path: str | Path, filename: str | None = None) -> QuarantineReport:
    file_path = Path(path)
    display_name = Path(filename or file_path.name).name
    findings: list[QuarantineFinding] = []
    scanners = ["extension", "signature"]

    suffix = Path(display_name).suffix.lower()
    if suffix in RISKY_EXTENSIONS:
        findings.append(_finding("risky_extension", "blocked", "extension", suffix))

    if zipfile.is_zipfile(file_path):
        scanners.append("archive")
        findings.extend(_inspect_zip(file_path))

    sample = file_path.read_bytes()[:MAX_TEXT_SCAN_BYTES]
    findings.extend(_inspect_signatures(sample))
    media_type = _guess_media_type(file_path, display_name)
    action = "block" if findings else "approve_after_human_review"
    return QuarantineReport(
        filename=display_name,
        sha256=sha256_file(file_path),
        size_bytes=file_path.stat().st_size,
        media_type=media_type,
        findings=tuple(_dedupe_findings(findings)),
        recommended_action=action,
        scanners=tuple(scanners),
    )


def _inspect_zip(path: Path) -> list[QuarantineFinding]:
    findings: list[QuarantineFinding] = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            findings.append(_finding("archive_too_many_entries", "blocked", "archive", str(len(infos))))
        total_uncompressed = 0
        for info in infos:
            name = info.filename
            suffix = Path(name).suffix.lower()
            total_uncompressed += max(0, info.file_size)
            if _is_unsafe_archive_name(name):
                findings.append(_finding("archive_path_traversal", "blocked", "archive", name))
                continue
            if suffix in RISKY_EXTENSIONS:
                findings.append(_finding("risky_archive_entry", "blocked", "archive", name))
            if suffix in ARCHIVE_EXTENSIONS:
                findings.append(_finding("nested_archive", "high", "archive", name))
            if info.compress_size and info.file_size / max(1, info.compress_size) > 100:
                findings.append(_finding("archive_high_compression_ratio", "blocked", "archive", name))
        if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            findings.append(
                _finding("archive_uncompressed_size_limit", "blocked", "archive", str(total_uncompressed))
            )
    return findings


def _inspect_signatures(sample: bytes) -> list[QuarantineFinding]:
    findings: list[QuarantineFinding] = []
    for rule_id, pattern in SIGNATURE_RULES.items():
        if pattern.search(sample):
            findings.append(_finding(rule_id, "high", "signature", rule_id))
    return findings


def _finding(kind: str, severity: str, scanner: str, detail: str) -> QuarantineFinding:
    return QuarantineFinding(kind=kind, severity=severity, scanner=scanner, detail=detail[:160])


def _dedupe_findings(findings: list[QuarantineFinding]) -> list[QuarantineFinding]:
    seen: set[tuple[str, str]] = set()
    deduped: list[QuarantineFinding] = []
    for finding in findings:
        key = (finding.kind, finding.detail)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def _is_unsafe_archive_name(name: str) -> bool:
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    return posix.is_absolute() or windows.is_absolute() or ".." in posix.parts or ".." in windows.parts


def _guess_media_type(path: Path, filename: str) -> str:
    if zipfile.is_zipfile(path):
        return "application/zip"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
