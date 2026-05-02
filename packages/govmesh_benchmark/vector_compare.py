"""Vector store comparison helpers."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from packages.govmesh_rag import InMemoryVectorStore, LocalRAGService, SQLiteVectorStore


def compare_vector_stores(sample_dir: str | Path) -> dict:
    sample_path = Path(sample_dir)
    docs = [
        (path.stem, path.read_text(encoding="utf-8"), str(path))
        for path in sorted(sample_path.rglob("*"))
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    ]
    if not docs:
        raise ValueError("No sample documents found for vector store comparison")

    memory_result = _run_store(LocalRAGService(vector_store=InMemoryVectorStore()), docs)
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_store = SQLiteVectorStore(Path(tmp) / "vectors.sqlite3")
        sqlite_result = _run_store(LocalRAGService(vector_store=sqlite_store), docs)

    return {
        "document_count": len(docs),
        "in_memory": memory_result,
        "sqlite": sqlite_result,
    }


def _run_store(service: LocalRAGService, docs: list[tuple[str, str, str]]) -> dict:
    index_started = time.perf_counter()
    chunk_count = 0
    for doc_id, text, path in docs:
        chunk_count += len(service.index_document(doc_id, text, source_path=path))
    index_ms = (time.perf_counter() - index_started) * 1000

    search_started = time.perf_counter()
    contexts = service.query("근거 문서 개인정보 외부 전송", top_k=5)["contexts"]
    search_ms = (time.perf_counter() - search_started) * 1000
    return {
        "chunk_count": chunk_count,
        "index_ms": index_ms,
        "search_ms": search_ms,
        "top_context_count": len(contexts),
    }
