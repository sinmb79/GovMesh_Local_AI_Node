from pathlib import Path
import sys

from packages.govmesh_common import sha256_file
from packages.govmesh_quarantine import ExternalScannerConfig, run_external_scanner, sanitize_file


def test_external_scanner_requires_pinned_executable_and_auxiliary(tmp_path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("clean", encoding="utf-8")
    scanner = tmp_path / "scanner.py"
    scanner.write_text(
        "import json, sys\n"
        "text=open(sys.argv[1], encoding='utf-8').read()\n"
        "findings=[] if 'bad' not in text else [{'kind':'demo_bad','severity':'high','detail':'bad text'}]\n"
        "print(json.dumps({'findings': findings}))\n",
        encoding="utf-8",
    )
    config = ExternalScannerConfig(
        name="demo-yara",
        executable_path=sys.executable,
        expected_executable_sha256=sha256_file(Path(sys.executable)),
        args_template=(str(scanner), "{file}"),
        expected_auxiliary_hashes={str(scanner): sha256_file(scanner)},
    )

    clean = run_external_scanner(config, sample)
    sample.write_text("bad", encoding="utf-8")
    dirty = run_external_scanner(config, sample)

    assert clean.ok is True
    assert dirty.ok is False
    assert dirty.findings[0].scanner == "demo-yara"


def test_external_scanner_rejects_unpinned_auxiliary(tmp_path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("clean", encoding="utf-8")
    scanner = tmp_path / "scanner.py"
    scanner.write_text("print('{}')\n", encoding="utf-8")
    config = ExternalScannerConfig(
        name="demo-yara",
        executable_path=sys.executable,
        expected_executable_sha256=sha256_file(Path(sys.executable)),
        args_template=(str(scanner), "{file}"),
        expected_auxiliary_hashes={str(scanner): "0" * 64},
    )

    try:
        run_external_scanner(config, sample)
    except PermissionError as exc:
        assert "auxiliary hash mismatch" in str(exc)
    else:
        raise AssertionError("scanner should reject unpinned auxiliary files")


def test_cdr_sanitizes_text_and_masks_pii(tmp_path) -> None:
    source = tmp_path / "document.txt"
    source.write_text("resident number 900101-1234567\x00", encoding="utf-8")

    report = sanitize_file(source, tmp_path / "sanitized")

    assert report.status == "sanitized"
    assert report.sanitized_path is not None
    sanitized = Path(report.sanitized_path).read_text(encoding="utf-8")
    assert "900101-1234567" not in sanitized
    assert "\x00" not in sanitized


def test_cdr_requires_manual_review_for_unsupported_files(tmp_path) -> None:
    source = tmp_path / "document.pdf"
    source.write_bytes(b"%PDF test")

    report = sanitize_file(source, tmp_path / "sanitized")

    assert report.status == "manual_review_required"
    assert report.reason == "unsupported_file_type"
