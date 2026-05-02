"""Minimal content disarm and reconstruction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from packages.govmesh_common import sha256_file
from packages.govmesh_policy import scan_text


TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".jsonl"}
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class CDRReport:
    status: str
    source_sha256: str
    sanitized_path: str | None
    sanitized_sha256: str | None
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "source_sha256": self.source_sha256,
            "sanitized_path": self.sanitized_path,
            "sanitized_sha256": self.sanitized_sha256,
            "reason": self.reason,
        }


def sanitize_file(path: str | Path, output_dir: str | Path) -> CDRReport:
    source = Path(path)
    source_hash = sha256_file(source)
    if source.suffix.lower() not in TEXT_EXTENSIONS:
        return CDRReport(
            status="manual_review_required",
            source_sha256=source_hash,
            sanitized_path=None,
            sanitized_sha256=None,
            reason="unsupported_file_type",
        )

    text = source.read_text(encoding="utf-8", errors="ignore")
    text = CONTROL_CHARS.sub("", text)
    decision = scan_text(text, block_high_risk=False)
    sanitized_text = decision.masked_text or text

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source.stem}.sanitized{source.suffix.lower()}"
    target.write_text(sanitized_text, encoding="utf-8", newline="\n")
    return CDRReport(
        status="sanitized",
        source_sha256=source_hash,
        sanitized_path=str(target),
        sanitized_sha256=sha256_file(target),
        reason=None,
    )
