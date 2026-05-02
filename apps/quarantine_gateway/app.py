"""AI Quarantine Gateway MVP."""

from __future__ import annotations

import base64
import binascii
import mimetypes
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import zipfile
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from packages.govmesh_common import ApiAuthPolicy, AuditChain, Principal, require_roles, sha256_file


RISKY_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".dll", ".scr", ".vbs"}
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 200
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_TEXT_SCAN_BYTES = 1024 * 1024
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
        findings = _scan_file(Path(record.path), record.filename)
        status = "blocked" if findings else "scanned"
        record = record.model_copy(update={"scan_findings": findings, "status": status})
        records[import_id] = record
        audit.append(
            event_type="import.scanned",
            actor=principal.actor,
            target_id=import_id,
            payload={"finding_count": len(findings), "findings": findings},
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


def _scan_file(path: Path, filename: str) -> list[str]:
    findings: list[str] = []
    if Path(filename).suffix.lower() in RISKY_EXTENSIONS:
        findings.append("risky_extension")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                findings.append("archive_too_many_entries")
            total_uncompressed = 0
            for info in infos:
                name = info.filename
                total_uncompressed += max(0, info.file_size)
                if _is_unsafe_archive_name(name):
                    findings.append("archive_path_traversal")
                    break
                if Path(name).suffix.lower() in RISKY_EXTENSIONS:
                    findings.append("risky_archive_entry")
                    break
                if Path(name).suffix.lower() in {".zip", ".7z", ".rar"}:
                    findings.append("nested_archive")
                    break
                if info.compress_size and info.file_size / max(1, info.compress_size) > 100:
                    findings.append("archive_high_compression_ratio")
                    break
            if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                findings.append("archive_uncompressed_size_limit")
    text = path.read_bytes()[:MAX_TEXT_SCAN_BYTES].decode("utf-8", errors="ignore")
    for risky in RISKY_STRINGS:
        if risky.lower() in text.lower():
            findings.append("risky_string")
            break
    return sorted(set(findings))


def _is_unsafe_archive_name(name: str) -> bool:
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    return posix.is_absolute() or windows.is_absolute() or ".." in posix.parts or ".." in windows.parts


def _guess_media_type(path: Path, filename: str) -> str:
    if zipfile.is_zipfile(path):
        return "application/zip"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
