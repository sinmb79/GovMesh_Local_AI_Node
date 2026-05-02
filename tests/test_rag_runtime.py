from packages.govmesh_policy import scan_text
import sys

from packages.govmesh_rag import KoreanTextChunker, LocalRAGService, MockEmbeddingProvider, SQLiteVectorStore, StoredChunk
from packages.govmesh_runtime import LocalLlamaCppProvider, MockLLMProvider, generate_with_policy


def test_korean_chunker_returns_chunks() -> None:
    chunker = KoreanTextChunker(max_chars=30, overlap_chars=5)
    chunks = chunker.chunk("첫 문장입니다. 두 번째 문장입니다.\n\n세 번째 문장입니다.")

    assert len(chunks) >= 2
    assert all(chunks)


def test_local_rag_indexes_and_returns_contexts_with_ids() -> None:
    rag = LocalRAGService()
    chunk_ids = rag.index_document(
        "doc-1",
        "개인정보 없는 행정 안내문입니다. AI 답변은 근거 문서와 chunk ID를 포함해야 합니다.",
    )
    result = rag.query("근거 문서 chunk ID", top_k=2)

    assert chunk_ids
    assert result["contexts"]
    assert {"doc_id", "chunk_id", "score", "snippet"} <= set(result["contexts"][0])


def test_rag_masks_sensitive_chunks() -> None:
    rag = LocalRAGService()
    rag.index_document("doc-sensitive", "담당자 주민번호는 900101-1234567 입니다.")
    result = rag.query("담당자 주민번호", top_k=1)

    context = result["contexts"][0]
    assert context["sensitive"] is True
    assert "900101-1234567" not in context["snippet"]


def test_runtime_does_not_call_provider_when_policy_blocks() -> None:
    provider = MockLLMProvider()
    decision = scan_text("주민번호 900101-1234567 알려줘")

    result = generate_with_policy(provider, "주민번호 900101-1234567 알려줘", decision)

    assert result["blocked"] is True
    assert provider.called_count == 0


def test_runtime_calls_provider_when_policy_allows() -> None:
    provider = MockLLMProvider()
    decision = scan_text("근거 문서 기준으로 요약해줘")

    result = generate_with_policy(
        provider,
        "근거 문서 기준으로 요약해줘",
        decision,
        contexts=[{"chunk_id": "doc-1#chunk-0000"}],
    )

    assert result["blocked"] is False
    assert provider.called_count == 1
    assert result["evidence_ids"] == ["doc-1#chunk-0000"]


def test_sqlite_vector_store_persists_chunks(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    embedding = MockEmbeddingProvider()
    vector = embedding.embed("근거 문서")
    store.add(StoredChunk(doc_id="doc", chunk_id="doc#1", text="근거 문서", vector=vector))

    reopened = SQLiteVectorStore(tmp_path / "vectors.sqlite3")
    results = reopened.search(embedding.embed("근거"), top_k=1)

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
        timeout_seconds=5,
    )

    result = provider.generate("요약", contexts=[{"chunk_id": "doc#1", "snippet": "근거"}])

    assert result["provider"] == "llama.cpp"
    assert result["text"] == "fake llama ok"
    assert result["evidence_ids"] == ["doc#1"]
