from pathlib import Path

from apps.node_agent.cli import performance_doctor, query_folder, scan_folder


def test_node_agent_performance_doctor_outputs_recommendations() -> None:
    result = performance_doctor()

    assert result["recommended_mode"] in {"safe", "balanced", "server"}
    assert result["recommended_context_length"] >= 512
    assert result["recommended_cpu_threads"] >= 1


def test_node_agent_scan_folder_returns_sanitized_summary(tmp_path) -> None:
    (tmp_path / "clean.md").write_text("깨끗한 샘플", encoding="utf-8")
    (tmp_path / "sensitive.md").write_text("주민번호 900101-1234567", encoding="utf-8")

    result = scan_folder(Path(tmp_path))

    assert result["document_count"] == 2
    assert result["blocked_count"] == 1
    assert "900101-1234567" not in str(result)


def test_node_agent_query_uses_rag_and_mock_runtime(tmp_path) -> None:
    (tmp_path / "sample.md").write_text("AI 답변은 근거 chunk ID를 포함해야 합니다.", encoding="utf-8")

    result = query_folder(Path(tmp_path), "근거 chunk ID는?", top_k=1)

    assert result["contexts"]
    assert result["answer"]["blocked"] is False
    assert result["answer"]["evidence_ids"]
