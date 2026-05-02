"""Local RAG service with policy-aware chunk masking."""

from __future__ import annotations

from pathlib import Path

from packages.govmesh_policy import scan_text
from packages.govmesh_rag.chunker import KoreanTextChunker
from packages.govmesh_rag.embeddings import MockEmbeddingProvider
from packages.govmesh_rag.vector_store import InMemoryVectorStore, SearchResult, StoredChunk


class LocalRAGService:
    def __init__(
        self,
        *,
        chunker: KoreanTextChunker | None = None,
        embedding_provider: MockEmbeddingProvider | None = None,
        vector_store: InMemoryVectorStore | None = None,
    ) -> None:
        self.chunker = chunker or KoreanTextChunker()
        self.embedding_provider = embedding_provider or MockEmbeddingProvider()
        self.vector_store = vector_store or InMemoryVectorStore()

    def index_document(self, doc_id: str, text: str, *, source_path: str | None = None) -> list[str]:
        chunk_ids: list[str] = []
        for index, chunk in enumerate(self.chunker.chunk(text)):
            decision = scan_text(chunk, block_high_risk=False)
            stored_text = decision.masked_text or chunk
            sensitive = bool(decision.findings)
            chunk_id = f"{doc_id}#chunk-{index:04d}"
            self.vector_store.add(
                StoredChunk(
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    text=stored_text,
                    vector=self.embedding_provider.embed(stored_text),
                    metadata={"source_path": source_path, "finding_count": len(decision.findings)},
                    sensitive=sensitive,
                )
            )
            chunk_ids.append(chunk_id)
        return chunk_ids

    def index_file(self, path: str | Path, *, doc_id: str | None = None) -> list[str]:
        file_path = Path(path)
        return self.index_document(
            doc_id or file_path.stem,
            file_path.read_text(encoding="utf-8"),
            source_path=str(file_path),
        )

    def query(self, query: str, *, top_k: int = 5) -> dict:
        query_vector = self.embedding_provider.embed(query)
        results = self.vector_store.search(query_vector, top_k=top_k)
        return {
            "query": query,
            "contexts": [self._to_context(result) for result in results],
        }

    @staticmethod
    def _to_context(result: SearchResult) -> dict:
        return {
            "doc_id": result.doc_id,
            "chunk_id": result.chunk_id,
            "score": result.score,
            "snippet": result.snippet,
            "sensitive": result.sensitive,
            "metadata": result.metadata,
        }
