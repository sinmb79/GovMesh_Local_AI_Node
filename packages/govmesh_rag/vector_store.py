"""Simple in-memory vector store for MVP tests."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import sqlite3
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StoredChunk:
    doc_id: str
    chunk_id: str
    text: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    sensitive: bool = False


@dataclass(frozen=True)
class SearchResult:
    doc_id: str
    chunk_id: str
    score: float
    snippet: str
    metadata: dict[str, Any]
    sensitive: bool = False


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: list[StoredChunk] = []

    def add(self, chunk: StoredChunk) -> None:
        self._chunks.append(chunk)

    def list_chunks(self) -> list[StoredChunk]:
        return list(self._chunks)

    def search(self, query_vector: list[float], *, top_k: int = 5) -> list[SearchResult]:
        ranked = sorted(
            ((self._cosine(query_vector, chunk.vector), chunk) for chunk in self._chunks),
            key=lambda item: item[0],
            reverse=True,
        )
        results: list[SearchResult] = []
        for score, chunk in ranked[:top_k]:
            results.append(
                SearchResult(
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    score=score,
                    snippet=chunk.text[:240],
                    metadata=chunk.metadata,
                    sensitive=chunk.sensitive,
                )
            )
        return results

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))


class SQLiteVectorStore:
    """Persistent vector store using SQLite JSON payloads for MVP portability."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                create table if not exists chunks (
                    chunk_id text primary key,
                    doc_id text not null,
                    text text not null,
                    vector_json text not null,
                    metadata_json text not null,
                    sensitive integer not null
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def add(self, chunk: StoredChunk) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                insert or replace into chunks
                (chunk_id, doc_id, text, vector_json, metadata_json, sensitive)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.doc_id,
                    chunk.text,
                    json.dumps(chunk.vector),
                    json.dumps(chunk.metadata, ensure_ascii=False),
                    1 if chunk.sensitive else 0,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_chunks(self) -> list[StoredChunk]:
        conn = self._connect()
        try:
            rows = conn.execute("select * from chunks order by doc_id, chunk_id").fetchall()
        finally:
            conn.close()
        return [
            StoredChunk(
                doc_id=row["doc_id"],
                chunk_id=row["chunk_id"],
                text=row["text"],
                vector=json.loads(row["vector_json"]),
                metadata=json.loads(row["metadata_json"]),
                sensitive=bool(row["sensitive"]),
            )
            for row in rows
        ]

    def search(self, query_vector: list[float], *, top_k: int = 5) -> list[SearchResult]:
        ranked = sorted(
            ((InMemoryVectorStore._cosine(query_vector, chunk.vector), chunk) for chunk in self.list_chunks()),
            key=lambda item: item[0],
            reverse=True,
        )
        return [
            SearchResult(
                doc_id=chunk.doc_id,
                chunk_id=chunk.chunk_id,
                score=score,
                snippet=chunk.text[:240],
                metadata=chunk.metadata,
                sensitive=chunk.sensitive,
            )
            for score, chunk in ranked[:top_k]
        ]
