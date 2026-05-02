"""Lightweight grounding checks for local RAG answers."""

from __future__ import annotations

import re
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣_#-]{3,}")


def verify_grounding(answer: dict[str, Any], contexts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Check whether an answer is tied to the supplied context IDs.

    This is not a factuality proof. It is a release-gate-friendly guard that
    catches the common failure mode where the model answers without citing the
    retrieved evidence it was given.
    """

    contexts = contexts or []
    available_ids = [context.get("chunk_id") for context in contexts if context.get("chunk_id")]
    answer_ids = [item for item in answer.get("evidence_ids", []) if item]
    missing_ids = sorted(set(answer_ids) - set(available_ids))
    text = str(answer.get("text", ""))
    text_mentions = [chunk_id for chunk_id in available_ids if chunk_id in text]
    overlap_score = _overlap_score(text, contexts)

    has_valid_id = bool(answer_ids) and not missing_ids
    mentions_context = bool(text_mentions)
    grounded = bool(contexts) and has_valid_id and (mentions_context or overlap_score >= 0.12)
    score = 0.0
    if grounded:
        score = max(0.65, min(1.0, 0.65 + overlap_score))
    elif has_valid_id:
        score = 0.5

    return {
        "grounded": grounded,
        "score": round(score, 3),
        "requires_review": not grounded,
        "available_evidence_ids": available_ids,
        "answer_evidence_ids": answer_ids,
        "missing_evidence_ids": missing_ids,
        "text_mentions": text_mentions,
    }


def _overlap_score(text: str, contexts: list[dict[str, Any]]) -> float:
    answer_tokens = set(_tokens(text))
    context_tokens: set[str] = set()
    for context in contexts:
        context_tokens.update(_tokens(str(context.get("snippet", ""))))
    if not answer_tokens or not context_tokens:
        return 0.0
    return len(answer_tokens.intersection(context_tokens)) / max(1, min(len(answer_tokens), len(context_tokens)))


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]
