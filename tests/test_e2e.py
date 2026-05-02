from fastapi.testclient import TestClient

from apps.control_plane import create_app
from packages.govmesh_benchmark import run_benchmark
from packages.govmesh_common import AuditChain
from packages.govmesh_policy import create_policy_alert, scan_text
from packages.govmesh_rag import LocalRAGService
from packages.govmesh_runtime import MockLLMProvider, generate_with_policy


def test_govmesh_mvp_e2e_local_only_no_raw_pii_logs(tmp_path) -> None:
    sample_dir = tmp_path / "samples"
    report_dir = tmp_path / "reports"
    sample_dir.mkdir()
    (sample_dir / "guide.md").write_text(
        "AI 답변은 근거 문서와 chunk ID를 포함해야 합니다. 외부 전송은 금지됩니다.",
        encoding="utf-8",
    )

    app = create_app(db_path=tmp_path / "control.sqlite3", audit_path=tmp_path / "control-audit.jsonl")
    client = TestClient(app)
    node_id = client.post(
        "/nodes/register",
        json={
            "hostname": "e2e-pc",
            "os": "Windows 11",
            "agent_version": "0.2.0",
            "cpu_count": 8,
            "memory_total_mb": 16384,
            "disk_free_mb": 100000,
        },
    ).json()["node_id"]
    client.post(f"/nodes/{node_id}/heartbeat", json={"status": "online"})

    audit = AuditChain(tmp_path / "policy-audit.jsonl")
    blocked_decision = scan_text("주민번호 900101-1234567 처리해줘")
    create_policy_alert(audit, blocked_decision, actor="e2e", target_id="blocked-query")

    rag = LocalRAGService()
    rag.index_file(sample_dir / "guide.md", doc_id="guide")
    rag_result = rag.query("근거 문서와 chunk ID", top_k=2)

    allowed_decision = scan_text("근거 문서와 chunk ID 기준으로 요약해줘")
    provider = MockLLMProvider()
    answer = generate_with_policy(
        provider,
        "근거 문서와 chunk ID 기준으로 요약해줘",
        allowed_decision,
        contexts=rag_result["contexts"],
    )

    report = run_benchmark(sample_dir, report_dir)

    assert blocked_decision.allow is False
    assert audit.verify() is True
    assert answer["blocked"] is False
    assert answer["evidence_ids"]
    assert provider.called_count == 1
    assert report.json_report_path
    assert client.get("/audit/verify").json() == {"valid": True}
    assert "900101-1234567" not in (tmp_path / "policy-audit.jsonl").read_text(encoding="utf-8")
