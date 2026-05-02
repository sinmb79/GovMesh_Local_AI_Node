import json
import zipfile
from pathlib import Path

from scripts.build_release_bundle import build_release_bundle


def test_release_bundle_contains_public_docs_and_checksums(tmp_path) -> None:
    result = build_release_bundle(out_dir=tmp_path / "dist")
    zip_path = Path(result["zip_path"])
    manifest_path = Path(result["manifest_path"])
    checksums_path = Path(result["checksums_path"])

    assert zip_path.exists()
    assert checksums_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == "0.3.1"
    assert manifest["zip_sha256"] == result["zip_sha256"]

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())

    assert any(name.endswith("README.md") for name in names)
    assert any(name.endswith("docs/GETTING_STARTED_KO.md") for name in names)
    assert not any("__pycache__" in name for name in names)
    assert not any(".govmesh-local" in name for name in names)
