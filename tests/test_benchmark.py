import json

from packages.govmesh_benchmark import run_benchmark
from packages.govmesh_benchmark.cli import main


def test_run_benchmark_writes_json_and_markdown_reports(tmp_path) -> None:
    sample_dir = tmp_path / "samples"
    output_dir = tmp_path / "reports"
    sample_dir.mkdir()
    (sample_dir / "sample.md").write_text(
        "# 샘플\n\n개인정보 없이 근거 문서 검색 성능을 측정합니다.",
        encoding="utf-8",
    )

    report = run_benchmark(sample_dir, output_dir)

    assert report.run_id.startswith("bench_")
    assert report.pc_profile.cpu_count >= 1
    assert {
        "pc_profile",
        "mock_llm",
        "mock_embedding",
        "rag_search",
        "pii_scan",
    } <= {result.name for result in report.results}

    json_report = output_dir / f"{report.run_id}.json"
    markdown_report = output_dir / f"{report.run_id}.md"
    assert json_report.exists()
    assert markdown_report.exists()

    payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert payload["pc_profile"]["recommended_mode"] in {"safe", "balanced", "server"}
    assert "외부 네트워크 호출 없음" in markdown_report.read_text(encoding="utf-8")


def test_benchmark_cli_run_generates_reports(tmp_path) -> None:
    sample_dir = tmp_path / "samples"
    output_dir = tmp_path / "reports"
    sample_dir.mkdir()
    (sample_dir / "sample.md").write_text("정책 근거와 chunk 검색 테스트", encoding="utf-8")

    exit_code = main(["run", "--sample", str(sample_dir), "--out", str(output_dir)])

    assert exit_code == 0
    assert len(list(output_dir.glob("*.json"))) == 1
    assert len(list(output_dir.glob("*.md"))) == 1
