import base64
import io
import zipfile

from fastapi.testclient import TestClient

from apps.quarantine_gateway import create_app
from packages.govmesh_common import ApiAuthPolicy


AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def test_quarantine_gateway_approves_only_scanned_clean_imports(tmp_path) -> None:
    app = create_app(storage_dir=tmp_path / "storage", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)

    uploaded = client.post(
        "/imports/upload",
        json={"filename": "model-card.md", "content_text": "clean model card"},
    ).json()
    import_id = uploaded["import_id"]
    assert uploaded["media_type"] == "text/markdown"
    assert uploaded["size_bytes"] > 0

    assert client.get("/imports/approved").json() == []
    assert client.post(f"/imports/{import_id}/approve").status_code == 409
    assert client.post(f"/imports/{import_id}/scan").json()["status"] == "scanned"
    assert client.post(f"/imports/{import_id}/approve").json()["approved"] is True
    assert len(client.get("/imports/approved").json()) == 1
    assert client.get("/audit/verify").json() == {"valid": True}


def test_quarantine_gateway_blocks_risky_imports(tmp_path) -> None:
    app = create_app(storage_dir=tmp_path / "storage", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)

    uploaded = client.post(
        "/imports/upload",
        json={"filename": "payload.ps1", "content_text": "Invoke-Expression bad"},
    ).json()
    import_id = uploaded["import_id"]

    scanned = client.post(f"/imports/{import_id}/scan").json()

    assert scanned["status"] == "blocked"
    assert "risky_extension" in scanned["scan_findings"]
    assert client.post(f"/imports/{import_id}/approve").status_code == 403


def test_quarantine_gateway_scans_zip_entries(tmp_path) -> None:
    app = create_app(storage_dir=tmp_path / "storage", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("bad.ps1", "Write-Host bad")

    uploaded = client.post(
        "/imports/upload",
        json={"filename": "bundle.zip", "content_base64": base64.b64encode(buffer.getvalue()).decode("ascii")},
    ).json()
    scanned = client.post(f"/imports/{uploaded['import_id']}/scan").json()

    assert scanned["media_type"] == "application/zip"
    assert "risky_archive_entry" in scanned["scan_findings"]
    assert scanned["scan_report"]["passed"] is False
    assert "archive" in scanned["scan_report"]["scanners"]


def test_quarantine_gateway_requires_auth_when_enabled(tmp_path) -> None:
    app = create_app(
        storage_dir=tmp_path / "storage",
        audit_path=tmp_path / "audit.jsonl",
        auth_policy=ApiAuthPolicy.single_token("test-token", roles={"importer", "approver", "auditor"}),
        audit_signing_key="test-signing-key",
    )
    client = TestClient(app)

    assert client.get("/imports/approved").status_code == 401
    uploaded = client.post(
        "/imports/upload",
        headers=AUTH_HEADERS,
        json={"filename": "model-card.md", "content_text": "clean model card"},
    ).json()
    import_id = uploaded["import_id"]
    assert client.post(f"/imports/{import_id}/scan", headers=AUTH_HEADERS).json()["status"] == "scanned"
    assert client.post(f"/imports/{import_id}/approve", headers=AUTH_HEADERS).json()["approved"] is True
    assert client.get("/audit/verify", headers=AUTH_HEADERS).json() == {"valid": True}


def test_quarantine_gateway_rejects_large_or_invalid_uploads(tmp_path) -> None:
    app = create_app(storage_dir=tmp_path / "storage", audit_path=tmp_path / "audit.jsonl", max_upload_bytes=5)
    client = TestClient(app)

    too_large = client.post("/imports/upload", json={"filename": "big.txt", "content_text": "123456"})
    invalid_base64 = client.post("/imports/upload", json={"filename": "bad.bin", "content_base64": "not base64!"})

    assert too_large.status_code == 413
    assert invalid_base64.status_code == 422


def test_quarantine_gateway_blocks_zip_traversal(tmp_path) -> None:
    app = create_app(storage_dir=tmp_path / "storage", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    uploaded = client.post(
        "/imports/upload",
        json={"filename": "bundle.zip", "content_base64": base64.b64encode(buffer.getvalue()).decode("ascii")},
    ).json()
    scanned = client.post(f"/imports/{uploaded['import_id']}/scan").json()

    assert "archive_path_traversal" in scanned["scan_findings"]


def test_quarantine_gateway_sanitizes_text_imports(tmp_path) -> None:
    app = create_app(storage_dir=tmp_path / "storage", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)

    uploaded = client.post(
        "/imports/upload",
        json={"filename": "document.txt", "content_text": "resident number 900101-1234567"},
    ).json()
    sanitized = client.post(f"/imports/{uploaded['import_id']}/sanitize").json()

    assert sanitized["cdr_report"]["status"] == "sanitized"
    assert sanitized["cdr_report"]["sanitized_sha256"]
