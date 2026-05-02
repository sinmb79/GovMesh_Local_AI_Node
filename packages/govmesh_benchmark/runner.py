"""Local-only benchmark runner."""

from __future__ import annotations

import json
import math
import os
import platform
import re
import socket
import time
from pathlib import Path
from statistics import median
from typing import Callable

from packages.govmesh_benchmark.schemas import BenchmarkReport, BenchmarkResult, PCProfile
from packages.govmesh_benchmark.vector_compare import compare_vector_stores
from packages.govmesh_policy import evaluate_policy_corpus


PII_PATTERNS = [
    re.compile(r"\b\d{6}-\d{7}\b"),
    re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"),
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,6}\b"),
]


def run_benchmark(sample_dir: Path, output_dir: Path) -> BenchmarkReport:
    """Run deterministic local-only benchmarks and write JSON/Markdown reports."""

    sample_dir = sample_dir.resolve()
    output_dir = output_dir.resolve()
    if not sample_dir.exists() or not sample_dir.is_dir():
        raise FileNotFoundError(f"Sample directory does not exist: {sample_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    pc_profile = collect_pc_profile()
    documents = _load_documents(sample_dir)

    results = [
        _timed("pc_profile", lambda: {"profile_collected": True}),
        _timed("mock_llm", lambda: _benchmark_mock_llm(documents)),
        _timed("mock_embedding", lambda: _benchmark_mock_embedding(documents)),
        _timed("rag_search", lambda: _benchmark_rag_search(documents)),
        _timed("vector_store_compare", lambda: compare_vector_stores(sample_dir)),
        _timed("pii_scan", lambda: _benchmark_pii_scan(documents)),
    ]
    policy_corpus = Path("samples/policy_corpus.jsonl")
    if policy_corpus.exists():
        results.append(_timed("policy_corpus", lambda: evaluate_policy_corpus(policy_corpus)))

    report = BenchmarkReport(
        sample_dir=str(sample_dir),
        pc_profile=pc_profile,
        results=results,
        json_report_path="",
        markdown_report_path="",
    )
    json_path = output_dir / f"{report.run_id}.json"
    markdown_path = output_dir / f"{report.run_id}.md"
    report = report.model_copy(
        update={
            "json_report_path": str(json_path),
            "markdown_report_path": str(markdown_path),
        }
    )

    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    return report


def collect_pc_profile() -> PCProfile:
    cpu_count = os.cpu_count() or 1
    memory_total_mb = _memory_total_mb()
    disk_free_mb = _disk_free_mb(Path.cwd())
    mode, model_size, context_length = _recommend_mode(cpu_count, memory_total_mb)

    return PCProfile(
        hostname=socket.gethostname(),
        os=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        cpu_count=cpu_count,
        memory_total_mb=memory_total_mb,
        disk_free_mb=disk_free_mb,
        recommended_mode=mode,
        recommended_model_size=model_size,
        recommended_context_length=context_length,
        recommended_cpu_threads=max(1, min(cpu_count, math.ceil(cpu_count * 0.75))),
    )


def _recommend_mode(cpu_count: int, memory_total_mb: int) -> tuple[str, str, int]:
    if cpu_count <= 4 or memory_total_mb < 12_000:
        return "safe", "mock/0.5B-class", 1024
    if cpu_count < 8 or memory_total_mb < 28_000:
        return "balanced", "1.5B-2.4B GGUF-class", 2048
    return "server", "4B-8B GGUF-class", 4096


def _memory_total_mb() -> int:
    if platform.system().lower() == "windows":
        return _windows_memory_total_mb()
    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return int(pages * page_size / (1024 * 1024))
        except (ValueError, OSError, AttributeError):
            return 0
    return 0


def _windows_memory_total_mb() -> int:
    import ctypes

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return int(status.ullTotalPhys / (1024 * 1024))
    return 0


def _disk_free_mb(path: Path) -> int:
    usage = __import__("shutil").disk_usage(path)
    return int(usage.free / (1024 * 1024))


def _load_documents(sample_dir: Path) -> list[tuple[Path, str]]:
    documents: list[tuple[Path, str]] = []
    for path in sorted(sample_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
            documents.append((path, path.read_text(encoding="utf-8")))
    if not documents:
        raise ValueError(f"No .txt or .md sample documents found in {sample_dir}")
    return documents


def _timed(name: str, fn: Callable[[], dict]) -> BenchmarkResult:
    started = time.perf_counter()
    try:
        metrics = fn()
        status = "succeeded"
        error = None
    except Exception as exc:  # pragma: no cover - defensive benchmark isolation
        metrics = {}
        status = "failed"
        error = str(exc)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return BenchmarkResult(name=name, status=status, metrics=metrics, elapsed_ms=elapsed_ms, error=error)


def _benchmark_mock_llm(documents: list[tuple[Path, str]]) -> dict:
    joined = "\n".join(text for _, text in documents)
    cold_start_started = time.perf_counter()
    vocabulary = sorted(set(joined.split()))
    cold_start_ms = (time.perf_counter() - cold_start_started) * 1000

    warm_started = time.perf_counter()
    answer = " ".join(vocabulary[: min(32, len(vocabulary))])
    warm_ms = (time.perf_counter() - warm_started) * 1000

    token_count = max(1, len(answer.split()))
    return {
        "cold_start_ms": cold_start_ms,
        "warm_start_ms": warm_ms,
        "tokens_generated": token_count,
        "tokens_per_sec": token_count / max(warm_ms / 1000, 0.000001),
    }


def _benchmark_mock_embedding(documents: list[tuple[Path, str]]) -> dict:
    vectors = [_mock_embedding(text) for _, text in documents]
    char_count = sum(len(text) for _, text in documents)
    return {
        "document_count": len(documents),
        "char_count": char_count,
        "embedding_dimensions": len(vectors[0]) if vectors else 0,
        "docs_min": len(documents) * 60,
    }


def _benchmark_rag_search(documents: list[tuple[Path, str]]) -> dict:
    chunks = []
    for path, text in documents:
        for index, chunk in enumerate(_chunk_text(text)):
            chunks.append((f"{path.name}:{index}", chunk, _mock_embedding(chunk)))

    query = "근거 문서 정책 개인정보 외부 전송"
    query_vector = _mock_embedding(query)
    latencies: list[float] = []
    top_scores: list[float] = []
    for _ in range(5):
        started = time.perf_counter()
        ranked = sorted(
            ((_cosine(query_vector, vector), chunk_id) for chunk_id, _, vector in chunks),
            reverse=True,
        )
        latencies.append((time.perf_counter() - started) * 1000)
        if ranked:
            top_scores.append(ranked[0][0])

    return {
        "chunk_count": len(chunks),
        "search_latency_p50_ms": median(latencies),
        "search_latency_p95_ms": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
        "top_score": max(top_scores) if top_scores else 0.0,
    }


def _benchmark_pii_scan(documents: list[tuple[Path, str]]) -> dict:
    findings = []
    char_count = 0
    for path, text in documents:
        char_count += len(text)
        for pattern in PII_PATTERNS:
            for match in pattern.finditer(text):
                findings.append({"document": path.name, "start": match.start(), "end": match.end()})
    return {
        "document_count": len(documents),
        "char_count": char_count,
        "findings_count": len(findings),
        "raw_pii_in_report": False,
    }


def _chunk_text(text: str, *, max_chars: int = 260) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue
        for start in range(0, len(paragraph), max_chars):
            chunks.append(paragraph[start : start + max_chars])
    return chunks


def _mock_embedding(text: str, *, dimensions: int = 16) -> list[float]:
    vector = [0.0] * dimensions
    for index, char in enumerate(text):
        vector[index % dimensions] += (ord(char) % 97) / 97.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _render_markdown(report: BenchmarkReport) -> str:
    lines = [
        f"# GovMesh Benchmark Report",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Sample Dir: `{report.sample_dir}`",
        f"- Created At: `{report.created_at.isoformat()}`",
        "",
        "## PC Profile",
        "",
        f"- Hostname: `{report.pc_profile.hostname}`",
        f"- OS: `{report.pc_profile.os}`",
        f"- Python: `{report.pc_profile.python_version}`",
        f"- CPU Count: `{report.pc_profile.cpu_count}`",
        f"- Memory Total MB: `{report.pc_profile.memory_total_mb}`",
        f"- Disk Free MB: `{report.pc_profile.disk_free_mb}`",
        f"- Recommended Mode: `{report.pc_profile.recommended_mode}`",
        f"- Recommended Model Size: `{report.pc_profile.recommended_model_size}`",
        f"- Recommended Context Length: `{report.pc_profile.recommended_context_length}`",
        "",
        "## Results",
        "",
        "| Name | Status | Elapsed ms | Key Metrics |",
        "|---|---|---:|---|",
    ]
    for result in report.results:
        key_metrics = ", ".join(f"{key}={value}" for key, value in result.metrics.items())
        lines.append(f"| {result.name} | {result.status} | {result.elapsed_ms:.3f} | {key_metrics} |")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- 외부 네트워크 호출 없음",
            "- 실제 정부 데이터 사용 없음",
            "- raw PII report 저장 없음",
        ]
    )
    return "\n".join(lines) + "\n"
