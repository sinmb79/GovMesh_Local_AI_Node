"""Checkpoint store for externally retained audit heads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.govmesh_common.hashing import canonical_json, sha256_text


GENESIS_HASH = "0" * 64


class CheckpointStore:
    """Append-only local checkpoint registry.

    This is not a substitute for WORM storage, but it gives the MVP a concrete
    export boundary that can later be pointed at a WORM bucket or audit vault.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        if checkpoint.get("schema") != "govmesh.audit.checkpoint.v1":
            raise ValueError("Unsupported checkpoint schema")
        previous_hash = self._last_hash()
        unsigned = {**checkpoint, "previous_checkpoint_hash": previous_hash, "checkpoint_hash": None}
        stored = {**unsigned, "checkpoint_hash": _hash_checkpoint(unsigned)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(stored) + "\n")
        return stored

    def list(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        items: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid checkpoint at line {line_number}") from exc
        return items

    def latest_for_source(self, source_path: str) -> dict[str, Any] | None:
        matches = [item for item in self.list() if item.get("source_path") == source_path]
        return matches[-1] if matches else None

    def verify(self) -> bool:
        try:
            items = self.list()
        except ValueError:
            return False
        expected_previous = GENESIS_HASH
        for item in items:
            if item.get("previous_checkpoint_hash") != expected_previous:
                return False
            checkpoint_hash = item.get("checkpoint_hash")
            if not checkpoint_hash:
                return False
            unsigned = {**item, "checkpoint_hash": None}
            if _hash_checkpoint(unsigned) != checkpoint_hash:
                return False
            expected_previous = checkpoint_hash
        return True

    def _last_hash(self) -> str:
        items = self.list()
        if not items:
            return GENESIS_HASH
        last_hash = items[-1].get("checkpoint_hash")
        if not last_hash:
            raise ValueError("Last checkpoint is missing checkpoint_hash")
        return str(last_hash)


def _hash_checkpoint(checkpoint: dict[str, Any]) -> str:
    return sha256_text(canonical_json({key: value for key, value in checkpoint.items() if key != "checkpoint_hash"}))
