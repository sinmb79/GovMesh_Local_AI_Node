"""Persistent human review queue.

The queue stores sanitized summaries, hashes, and evidence IDs rather than raw
documents or prompts. It is deliberately simple JSONL so it remains portable in
air-gapped Windows environments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from packages.govmesh_common import canonical_json, sha256_text
from packages.govmesh_common.schemas import utc_now


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str = Field(default_factory=lambda: f"review_{uuid4().hex}")
    target_type: Literal["rag_answer", "import", "skill", "model", "policy"]
    target_id: str
    reason: str
    risk_level: Literal["low", "medium", "high", "blocked"] = "medium"
    summary: str
    content_hash: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["open", "approved", "rejected", "needs_more_info"] = "open"
    created_by: str = "system"
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())
    decided_by: str | None = None
    decision_reason: str | None = None
    decided_at: str | None = None


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected", "needs_more_info"]
    reviewer: str
    reason: str | None = None


class ReviewQueue:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        target_type: Literal["rag_answer", "import", "skill", "model", "policy"],
        target_id: str,
        reason: str,
        summary: str,
        risk_level: Literal["low", "medium", "high", "blocked"] = "medium",
        content: str | None = None,
        evidence_ids: list[str] | None = None,
        created_by: str = "system",
    ) -> ReviewItem:
        item = ReviewItem(
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            risk_level=risk_level,
            summary=summary[:500],
            content_hash=sha256_text(content) if content is not None else None,
            evidence_ids=evidence_ids or [],
            created_by=created_by,
        )
        self._append(item)
        return item

    def list(self, *, status: str | None = None) -> list[ReviewItem]:
        items = self._read_all()
        if status is not None:
            items = [item for item in items if item.status == status]
        return items

    def get(self, review_id: str) -> ReviewItem:
        for item in reversed(self._read_all()):
            if item.review_id == review_id:
                return item
        raise KeyError(review_id)

    def decide(self, review_id: str, decision: ReviewDecision) -> ReviewItem:
        item = self.get(review_id)
        if item.status != "open":
            raise PermissionError("Review is already decided")
        updated = item.model_copy(
            update={
                "status": decision.decision,
                "decided_by": decision.reviewer,
                "decision_reason": decision.reason,
                "decided_at": utc_now().isoformat(),
            }
        )
        self._append(updated)
        return updated

    def _append(self, item: ReviewItem) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(item.model_dump(mode="json")) + "\n")

    def _read_all(self) -> list[ReviewItem]:
        if not self.path.exists():
            return []
        latest: dict[str, ReviewItem] = {}
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                item = ReviewItem.model_validate(json.loads(line))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid review item at line {line_number}") from exc
            latest[item.review_id] = item
        return sorted(latest.values(), key=lambda item: item.created_at)
