"""Append-only JSONL audit hash chain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.govmesh_common.hashing import canonical_json, sha256_text
from packages.govmesh_common.schemas import AuditEvent


GENESIS_HASH = "0" * 64


class AuditChain:
    """Store audit events as a tamper-evident JSONL hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(
        self,
        event: AuditEvent | None = None,
        *,
        event_type: str | None = None,
        actor: str | None = None,
        target_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Append an event and return the stored event with chain hashes."""

        if event is None:
            if event_type is None or actor is None:
                raise ValueError("event_type and actor are required when event is not provided")
            event = AuditEvent(
                event_type=event_type,
                actor=actor,
                target_id=target_id,
                payload=payload or {},
            )

        previous_hash = self._last_hash()
        unsigned = event.model_copy(
            update={"previous_hash": previous_hash, "event_hash": None}
        )
        event_hash = self._hash_event(unsigned)
        stored = unsigned.model_copy(update={"event_hash": event_hash})

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(stored) + "\n")

        return stored

    def list(self) -> list[AuditEvent]:
        """Load audit events from disk in append order."""

        if not self.path.exists():
            return []

        events: list[AuditEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    events.append(AuditEvent.model_validate(json.loads(stripped)))
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ValueError(f"Invalid audit event at line {line_number}") from exc
        return events

    def verify(self) -> bool:
        """Return True when every event hash and previous hash link is valid."""

        try:
            events = self.list()
        except ValueError:
            return False

        expected_previous_hash = GENESIS_HASH
        for event in events:
            if event.previous_hash != expected_previous_hash:
                return False
            if not event.event_hash:
                return False

            unsigned = event.model_copy(update={"event_hash": None})
            if self._hash_event(unsigned) != event.event_hash:
                return False
            expected_previous_hash = event.event_hash

        return True

    def _last_hash(self) -> str:
        events = self.list()
        if not events:
            return GENESIS_HASH
        last_hash = events[-1].event_hash
        if not last_hash:
            raise ValueError("Last audit event is missing event_hash")
        return last_hash

    @staticmethod
    def _hash_event(event: AuditEvent) -> str:
        return sha256_text(canonical_json(event.model_dump(mode="json", exclude={"event_hash"})))
