import base64
import io
import zipfile

from fastapi.testclient import TestClient

from apps.quarantine_gateway import create_app


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
