"""AI Quarantine Gateway MVP."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
import zipfile
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from packages.govmesh_common import AuditChain, sha256_file


RISKY_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".dll", ".scr", ".vbs"}
RISKY_STRINGS = ("Invoke-Expression", "powershell -enc", "ignore previous instructions", "이전 지시를 무시")


class ImportUploadRequest(BaseModel):
    filename: str
    content_text: str | None = None
    content_base64: str | None = None
    source: str = "external"


class ImportRecord(BaseModel):
    import_id: str
    filename: str
    path: str
    sha256: str
    size_bytes: int
    media_type: str
    status: str
    scan_findings: list[str] = []
    approved: bool = False


def create_app(
    *,
    storage_dir: str | Path = ".govmesh-local/quarantine",
    audit_path: str | Path = ".govmesh-local/quarantine-audit.jsonl",
) -> FastAPI:
    storage = Path(storage_dir)
    storage.mkdir(parents=True, exist_ok=True)
    audit = AuditChain(audit_path)
    records: dict[str, ImportRecord] = {}
    registry: dict[str, ImportRecord] = {}
    app = FastAPI(title="GovMesh Quarantine Gateway", version="0.2.0")

    @app.post("/imports/upload", response_model=ImportRecord)
    def upload(request: ImportUploadRequest) -> ImportRecord:
        if request.content_text is None and request.content_base64 is None:
            raise HTTPException(status_code=422, detail="content_text or content_base64 is required")
        safe_name = Path(request.filename).name
        import_id = f"import_{uuid4().hex}"
        path = storage / f"{import_id}_{safe_name}"
        if request.content_base64 is not None:
            path.write_bytes(base64.b64decode(request.content_base64))
        else:
            path.write_text(request.content_text or "", encoding="utf-8")
        record = ImportRecord(
            import_id=import_id,
            filename=safe_name,
            path=str(path),
            sha256=sha256_file(path),
            size_bytes=path.stat().st_size,
            media_type=_guess_media_type(path, safe_name),
            status="uploaded",
        )
        records[import_id] = record
        audit.append(event_type="import.uploaded", actor="quarantine", target_id=import_id, payload={"sha256": record.sha256})
        return record

    @app.get("/imports/approved", response_model=list[ImportRecord])
    def approved() -> list[ImportRecord]:
        return list(registry.values())

    @app.get("/imports/{import_id}", response_model=ImportRecord)
    def get_import(import_id: str) -> ImportRecord:
        return _get(records, import_id)

    @app.post("/imports/{import_id}/scan", response_model=ImportRecord)
    def scan(import_id: str) -> ImportRecord:
        record = _get(records, import_id)
        findings = _scan_file(Path(record.path), record.filename)
        status = "blocked" if findings else "scanned"
        record = record.model_copy(update={"scan_findings": findings, "status": status})
        records[import_id] = record
        audit.append(event_type="import.scanned", actor="quarantine", target_id=import_id, payload={"finding_count": len(findings)})
        return record

    @app.post("/imports/{import_id}/approve", response_model=ImportRecord)
    def approve(import_id: str) -> ImportRecord:
        record = _get(records, import_id)
        if record.status == "uploaded":
            raise HTTPException(status_code=409, detail="Import must be scanned before approval")
        if record.scan_findings:
            raise HTTPException(status_code=403, detail="Blocked imports cannot be approved")
        record = record.model_copy(update={"status": "approved", "approved": True})
        records[import_id] = record
        registry[import_id] = record
        audit.append(event_type="import.approved", actor="quarantine", target_id=import_id, payload={"sha256": record.sha256})
        return record

    @app.post("/imports/{import_id}/reject", response_model=ImportRecord)
    def reject(import_id: str) -> ImportRecord:
        record = _get(records, import_id).model_copy(update={"status": "rejected", "approved": False})
        records[import_id] = record
        registry.pop(import_id, None)
        audit.append(event_type="import.rejected", actor="quarantine", target_id=import_id)
        return record

    @app.get("/audit/verify")
    def verify_audit() -> dict[str, bool]:
        return {"valid": audit.verify()}

    return app


def _get(records: dict[str, ImportRecord], import_id: str) -> ImportRecord:
    try:
        return records[import_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Import not found") from exc


def _scan_file(path: Path, filename: str) -> list[str]:
    findings: list[str] = []
    if Path(filename).suffix.lower() in RISKY_EXTENSIONS:
        findings.append("risky_extension")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if Path(name).suffix.lower() in RISKY_EXTENSIONS:
                    findings.append("risky_archive_entry")
                    break
    text = path.read_text(encoding="utf-8", errors="ignore")
    for risky in RISKY_STRINGS:
        if risky.lower() in text.lower():
            findings.append("risky_string")
            break
    return findings


def _guess_media_type(path: Path, filename: str) -> str:
    if zipfile.is_zipfile(path):
        return "application/zip"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
