import io
import zipfile

from packages.govmesh_quarantine import inspect_file


def test_quarantine_inspection_reports_signature_findings(tmp_path) -> None:
    path = tmp_path / "macro.docm"
    path.write_bytes(b"Sub AutoOpen()\nCreateObject(\"WScript.Shell\")\nEnd Sub")

    report = inspect_file(path)

    assert report.passed is False
    assert "office_macro_autoopen" in report.finding_kinds()
    assert "office_wscript_shell" in report.finding_kinds()
    assert report.recommended_action == "block"


def test_quarantine_inspection_reports_archive_detail(tmp_path) -> None:
    path = tmp_path / "bundle.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.ps1", "Write-Host bad")
    path.write_bytes(buffer.getvalue())

    report = inspect_file(path)

    assert report.media_type == "application/zip"
    assert "archive_path_traversal" in report.finding_kinds()
    assert any(finding.scanner == "archive" for finding in report.findings)
