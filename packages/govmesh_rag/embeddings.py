"""Deterministic local mock embeddings."""

from __future__ import annotations

import math


class MockEmbeddingProvider:
    def __init__(self, *, dimensions: int = 32) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for index, char in enumerate(text):
            bucket = index % self.dimensions
            vector[bucket] += ((ord(char) % 251) + 1) / 251.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
