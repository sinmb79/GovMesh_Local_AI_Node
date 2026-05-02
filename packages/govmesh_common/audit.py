"""Append-only JSONL audit hash chain."""

from __future__ import annotations

import json
import hmac
from pathlib import Path
from typing import Any

from packages.govmesh_common.hashing import canonical_json, sha256_text
from packages.govmesh_common.schemas import AuditEvent, utc_now


GENESIS_HASH = "0" * 64


class AuditChain:
    """Store audit events as a tamper-evident JSONL hash chain."""

    def __init__(self, path: str | Path, *, signing_key: str | bytes | None = None) -> None:
        self.path = Path(path)
        self._signing_key = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key

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
        stored = unsigned.model_copy(update={"event_hash": event_hash, "signature": self._signature(event_hash)})

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
            if self._signing_key is not None and event.signature != self._signature(event.event_hash):
                return False
            expected_previous_hash = event.event_hash

        return True

    def head(self) -> dict[str, Any]:
        """Return the current audit head without exposing event payloads."""

        events = self.list()
        head_hash = events[-1].event_hash if events else GENESIS_HASH
        return {
            "event_count": len(events),
            "head_hash": head_hash,
            "signature": self._signature(head_hash),
        }

    def export_checkpoint(self, path: str | Path, *, label: str | None = None) -> dict[str, Any]:
        """Write a portable audit head checkpoint for external retention."""

        checkpoint = {
            "schema": "govmesh.audit.checkpoint.v1",
            "source_path": str(self.path),
            "label": label,
            "created_at": utc_now().isoformat(),
            **self.head(),
        }
        checkpoint_path = Path(path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_path.write_text(canonical_json(checkpoint) + "\n", encoding="utf-8")
        return checkpoint

    def verify_checkpoint(self, path: str | Path) -> bool:
        """Return True when a saved checkpoint matches the current audit head."""

        try:
            checkpoint = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        head = self.head()
        return (
            checkpoint.get("schema") == "govmesh.audit.checkpoint.v1"
            and checkpoint.get("event_count") == head["event_count"]
            and checkpoint.get("head_hash") == head["head_hash"]
            and checkpoint.get("signature") == head["signature"]
        )

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
        return sha256_text(canonical_json(event.model_dump(mode="json", exclude={"event_hash", "signature"})))

    def _signature(self, event_hash: str | None) -> str | None:
        if self._signing_key is None or event_hash is None:
            return None
        return hmac.digest(self._signing_key, event_hash.encode("ascii"), "sha256").hex()
