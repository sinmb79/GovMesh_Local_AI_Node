"""Korean-friendly text chunking."""

from __future__ import annotations

import re


class KoreanTextChunker:
    def __init__(self, *, max_chars: int = 420, overlap_chars: int = 40) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be between 0 and max_chars")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, text: str) -> list[str]:
        normalized = re.sub(r"\r\n?", "\n", text).strip()
        if not normalized:
            return []

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
        chunks: list[str] = []
        for paragraph in paragraphs:
            chunks.extend(self._chunk_paragraph(paragraph))
        return chunks

    def _chunk_paragraph(self, paragraph: str) -> list[str]:
        if len(paragraph) <= self.max_chars:
            return [paragraph]

        sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？다요죠음])\s+", paragraph) if part.strip()]
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if not current:
                current = sentence
                continue
            if len(current) + 1 + len(sentence) <= self.max_chars:
                current = f"{current} {sentence}"
            else:
                chunks.extend(self._hard_split(current))
                current = sentence
        if current:
            chunks.extend(self._hard_split(current))
        return chunks

    def _hard_split(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.max_chars)
            chunks.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(0, end - self.overlap_chars)
        return [chunk for chunk in chunks if chunk]
