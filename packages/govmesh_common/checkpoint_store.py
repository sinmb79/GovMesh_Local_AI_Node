"""Checkpoint store for externally retained audit heads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.govmesh_common.hashing import canonical_json


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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(checkpoint) + "\n")
        return checkpoint

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
