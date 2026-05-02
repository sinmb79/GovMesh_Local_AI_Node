from pathlib import Path
import sys

from packages.govmesh_common import sha256_file
from packages.govmesh_policy import scan_text
from packages.govmesh_rag import KoreanTextChunker, LocalRAGService, MockEmbeddingProvider, SQLiteVectorStore, StoredChunk
from packages.govmesh_runtime import LocalLlamaCppProvider, MockLLMProvider, generate_with_policy, verify_grounding


def test_korean_chunker_returns_chunks() -> None:
    chunker = KoreanTextChunker(max_chars=30, overlap_chars=5)
    chunks = chunker.chunk("first sentence. second sentence.\n\nthird sentence.")

    assert len(chunks) >= 2
    assert all(chunks)


def test_local_rag_indexes_and_returns_contexts_with_ids() -> None:
    rag = LocalRAGService()
    chunk_ids = rag.index_document(
        "doc-1",
        "Clean public guidance. AI answers should include the evidence document chunk ID.",
    )
    result = rag.query("evidence document chunk ID", top_k=2)

    assert chunk_ids
    assert result["contexts"]
    assert {"doc_id", "chunk_id", "score", "snippet"} <= set(result["contexts"][0])


def test_rag_masks_sensitive_chunks() -> None:
    rag = LocalRAGService()
    rag.index_document("doc-sensitive", "resident number 900101-1234567")
    result = rag.query("resident number", top_k=1, include_sensitive=True)

    context = result["contexts"][0]
    assert context["sensitive"] is True
    assert "900101-1234567" not in context["snippet"]


def test_rag_excludes_sensitive_contexts_by_default() -> None:
    rag = LocalRAGService()
    rag.index_document("doc-sensitive", "resident number 900101-1234567")

    result = rag.query("resident number", top_k=1)

    assert result["sensitive_contexts_excluded"] is True
    assert result["contexts"] == []


def test_runtime_does_not_call_provider_when_policy_blocks() -> None:
    provider = MockLLMProvider()
    decision = scan_text("resident number 900101-1234567")

    result = generate_with_policy(provider, "resident number 900101-1234567", decision)

    assert result["blocked"] is True
    assert provider.called_count == 0


def test_runtime_calls_provider_when_policy_allows() -> None:
    provider = MockLLMProvider()
    decision = scan_text("summarize using evidence document")

    result = generate_with_policy(
        provider,
        "summarize using evidence document",
        decision,
        contexts=[{"chunk_id": "doc-1#chunk-0000"}],
    )

    assert result["blocked"] is False
    assert provider.called_count == 1
    assert result["evidence_ids"] == ["doc-1#chunk-0000"]
    assert result["grounding"]["grounded"] is True
    assert result["needs_review"] is False


def test_grounding_requires_available_evidence_ids() -> None:
    report = verify_grounding(
        {"text": "answer without the real source", "evidence_ids": ["doc-2#chunk-0000"]},
        [{"chunk_id": "doc-1#chunk-0000", "snippet": "official evidence"}],
    )

    assert report["grounded"] is False
    assert report["requires_review"] is True
    assert report["missing_evidence_ids"] == ["doc-2#chunk-0000"]


def test_sqlite_vector_store_persists_chunks(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    embedding = MockEmbeddingProvider()
    vector = embedding.embed("evidence document")
    store.add(StoredChunk(doc_id="doc", chunk_id="doc#1", text="evidence document", vector=vector))

    reopened = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    results = reopened.search(embedding.embed("evidence"), top_k=1)

    assert results[0].chunk_id == "doc#1"


def test_local_llamacpp_provider_requires_approval(tmp_path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("fake", encoding="utf-8")
    provider = LocalLlamaCppProvider(executable_path=sys.executable, model_path=model, approved=False)

    try:
        provider.generate("hello")
    except PermissionError as exc:
        assert "approved" in str(exc)
    else:
        raise AssertionError("provider should require approval")


def test_local_llamacpp_provider_can_call_approved_local_executable(tmp_path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("fake", encoding="utf-8")
    script = tmp_path / "fake_llama.py"
    script.write_text("import sys\nprint('fake llama ok')\n", encoding="utf-8")
    provider = LocalLlamaCppProvider(
        executable_path=sys.executable,
        model_path=model,
        approved=True,
        pre_args=[str(script)],
        allow_pre_args=True,
        expected_executable_sha256=sha256_file(Path(sys.executable)),
        expected_model_sha256=sha256_file(model),
        timeout_seconds=5,
    )

    result = provider.generate("summarize", contexts=[{"chunk_id": "doc#1", "snippet": "evidence"}])

    assert result["provider"] == "llama.cpp"
    assert result["text"] == "fake llama ok"
    assert result["evidence_ids"] == ["doc#1"]


def test_local_llamacpp_provider_requires_pinned_hashes(tmp_path) -> None:
    model = tmp_path / "model.gguf"
    model.write_text("fake", encoding="utf-8")
    provider = LocalLlamaCppProvider(
        executable_path=sys.executable,
        model_path=model,
        approved=True,
        allow_unverified_runtime=False,
    )

    try:
        provider.generate("hello")
    except PermissionError as exc:
        assert "hashes" in str(exc)
    else:
        raise AssertionError("provider should require pinned hashes")
