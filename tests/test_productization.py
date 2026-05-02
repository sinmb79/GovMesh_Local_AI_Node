import json

from fastapi.testclient import TestClient

from apps.admin_ui.app import create_app
from packages.govmesh_benchmark import compare_vector_stores
from scripts.create_corpus_template import main as create_corpus_template


def test_vector_store_comparison_reports_memory_and_sqlite(tmp_path) -> None:
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    (sample_dir / "doc.md").write_text("근거 문서와 개인정보 없는 샘플입니다.", encoding="utf-8")

    report = compare_vector_stores(sample_dir)

    assert report["document_count"] == 1
    assert report["in_memory"]["chunk_count"] >= 1
    assert report["sqlite"]["chunk_count"] >= 1


def test_admin_ui_app_serves_dashboard_and_status() -> None:
    app = create_app(
        control_plane_url="http://control-plane",
        status_provider=lambda _: {
            "health": {"ok": True, "schema_version": 1},
            "node_count": 2,
            "online_nodes": 1,
            "task_count": 3,
            "queued_tasks": 1,
            "audit": {"valid": True},
        },
    )
    client = TestClient(app)

    html = client.get("/")
    status = client.get("/api/status")

    assert html.status_code == 200
    assert "GovMesh Admin" in html.text
    assert status.json()["node_count"] == 2


def test_corpus_template_script_writes_jsonl(tmp_path) -> None:
    out = tmp_path / "template.jsonl"

    assert create_corpus_template(["--out", str(out)]) == 0

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert rows
    assert {"id", "text", "should_block", "expected_kinds", "source_class", "reviewer"} <= set(rows[0])
