"""AI Quarantine Gateway MVP."""

from __future__ import annotations

import base64
import binascii
import mimetypes
from pathlib import Path
import zipfile
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from packages.govmesh_common import ApiAuthPolicy, AuditChain, Principal, require_roles, sha256_file
from packages.govmesh_quarantine import inspect_file, sanitize_file


DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


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
    scan_report: dict[str, Any] | None = None
    cdr_report: dict[str, Any] | None = None
    approved: bool = False


def create_app(
    *,
    storage_dir: str | Path = ".govmesh-local/quarantine",
    audit_path: str | Path = ".govmesh-local/quarantine-audit.jsonl",
    auth_policy: ApiAuthPolicy | None = None,
    audit_signing_key: str | None = None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> FastAPI:
    storage = Path(storage_dir)
    storage.mkdir(parents=True, exist_ok=True)
    audit = AuditChain(audit_path, signing_key=audit_signing_key)
    auth = auth_policy or ApiAuthPolicy.disabled()
    records: dict[str, ImportRecord] = {}
    registry: dict[str, ImportRecord] = {}
    app = FastAPI(title="GovMesh Quarantine Gateway", version="0.2.0")
    require_importer = require_roles(auth, "importer", "operator")
    require_approver = require_roles(auth, "approver", "operator")
    require_auditor = require_roles(auth, "auditor", "operator")

    @app.post("/imports/upload", response_model=ImportRecord)
    def upload(request: ImportUploadRequest, principal: Principal = Depends(require_importer)) -> ImportRecord:
        if request.content_text is None and request.content_base64 is None:
            raise HTTPException(status_code=422, detail="content_text or content_base64 is required")
        safe_name = Path(request.filename).name
        if not safe_name:
            raise HTTPException(status_code=422, detail="filename is required")
        import_id = f"import_{uuid4().hex}"
        path = storage / f"{import_id}_{safe_name}"
        if request.content_base64 is not None:
            try:
                content = base64.b64decode(request.content_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise HTTPException(status_code=422, detail="content_base64 is invalid") from exc
        else:
            content = (request.content_text or "").encode("utf-8")
        if len(content) > max_upload_bytes:
            raise HTTPException(status_code=413, detail="upload exceeds max_upload_bytes")
        path.write_bytes(content)
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
        audit.append(
            event_type="import.uploaded",
            actor=principal.actor,
            target_id=import_id,
            payload={"sha256": record.sha256, "size_bytes": record.size_bytes, "source": request.source},
        )
        return record

    @app.get("/imports/approved", response_model=list[ImportRecord])
    def approved(_: Principal = Depends(require_importer)) -> list[ImportRecord]:
        return list(registry.values())

    @app.get("/imports/{import_id}", response_model=ImportRecord)
    def get_import(import_id: str, _: Principal = Depends(require_importer)) -> ImportRecord:
        return _get(records, import_id)

    @app.post("/imports/{import_id}/scan", response_model=ImportRecord)
    def scan(import_id: str, principal: Principal = Depends(require_importer)) -> ImportRecord:
        record = _get(records, import_id)
        report = inspect_file(Path(record.path), record.filename)
        findings = report.finding_kinds()
        status = "blocked" if findings else "scanned"
        record = record.model_copy(update={"scan_findings": findings, "scan_report": report.to_dict(), "status": status})
        records[import_id] = record
        audit.append(
            event_type="import.scanned",
            actor=principal.actor,
            target_id=import_id,
            payload={
                "finding_count": len(findings),
                "findings": findings,
                "recommended_action": report.recommended_action,
                "scanner_count": len(report.scanners),
            },
        )
        return record

    @app.post("/imports/{import_id}/approve", response_model=ImportRecord)
    def approve(import_id: str, principal: Principal = Depends(require_approver)) -> ImportRecord:
        record = _get(records, import_id)
        if record.status == "uploaded":
            raise HTTPException(status_code=409, detail="Import must be scanned before approval")
        if record.scan_findings:
            raise HTTPException(status_code=403, detail="Blocked imports cannot be approved")
        record = record.model_copy(update={"status": "approved", "approved": True})
        records[import_id] = record
        registry[import_id] = record
        audit.append(event_type="import.approved", actor=principal.actor, target_id=import_id, payload={"sha256": record.sha256})
        return record

    @app.post("/imports/{import_id}/sanitize", response_model=ImportRecord)
    def sanitize(import_id: str, principal: Principal = Depends(require_importer)) -> ImportRecord:
        record = _get(records, import_id)
        cdr = sanitize_file(record.path, storage / "sanitized")
        record = record.model_copy(update={"cdr_report": cdr.to_dict()})
        records[import_id] = record
        audit.append(
            event_type="import.sanitized",
            actor=principal.actor,
            target_id=import_id,
            payload={"status": cdr.status, "sanitized_sha256": cdr.sanitized_sha256, "reason": cdr.reason},
        )
        return record

    @app.post("/imports/{import_id}/reject", response_model=ImportRecord)
    def reject(import_id: str, principal: Principal = Depends(require_approver)) -> ImportRecord:
        record = _get(records, import_id).model_copy(update={"status": "rejected", "approved": False})
        records[import_id] = record
        registry.pop(import_id, None)
        audit.append(event_type="import.rejected", actor=principal.actor, target_id=import_id)
        return record

    @app.get("/audit/verify")
    def verify_audit(_: Principal = Depends(require_auditor)) -> dict[str, bool]:
        return {"valid": audit.verify()}

    return app


def _get(records: dict[str, ImportRecord], import_id: str) -> ImportRecord:
    try:
        return records[import_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Import not found") from exc


def _guess_media_type(path: Path, filename: str) -> str:
    if zipfile.is_zipfile(path):
        return "application/zip"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
