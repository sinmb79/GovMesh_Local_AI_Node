"""Approved local model registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from packages.govmesh_common import sha256_file


class ModelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(default_factory=lambda: f"model_{uuid4().hex}")
    name: str
    provider: Literal["llama.cpp", "ollama", "mock"]
    path: str
    sha256: str
    license: str
    license_review_status: Literal["pending", "approved", "rejected"] = "pending"
    approved: bool = False
    approved_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ModelRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def register_local_model(
        self,
        *,
        name: str,
        provider: Literal["llama.cpp", "ollama", "mock"],
        path: str | Path,
        license: str,
    ) -> ModelRecord:
        model_path = Path(path)
        if provider != "mock" and not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        record = ModelRecord(
            name=name,
            provider=provider,
            path=str(model_path),
            sha256=sha256_file(model_path) if model_path.exists() else "0" * 64,
            license=license,
        )
        records = self.list()
        records.append(record)
        self._write(records)
        return record

    def approve_license(self, model_id: str, *, approved_by: str) -> ModelRecord:
        records = self.list()
        updated: list[ModelRecord] = []
        found: ModelRecord | None = None
        for record in records:
            if record.model_id == model_id:
                found = record.model_copy(
                    update={
                        "license_review_status": "approved",
                        "approved": True,
                        "approved_by": approved_by,
                        "updated_at": datetime.now(UTC),
                    }
                )
                updated.append(found)
            else:
                updated.append(record)
        if found is None:
            raise KeyError(model_id)
        self._write(updated)
        return found

    def get_approved(self, model_id: str) -> ModelRecord:
        record = self.get(model_id)
        if not record.approved or record.license_review_status != "approved":
            raise PermissionError("Model is not approved")
        return record

    def get(self, model_id: str) -> ModelRecord:
        for record in self.list():
            if record.model_id == model_id:
                return record
        raise KeyError(model_id)

    def list(self) -> list[ModelRecord]:
        return [ModelRecord.model_validate(item) for item in json.loads(self.path.read_text(encoding="utf-8"))]

    def _write(self, records: list[ModelRecord]) -> None:
        self.path.write_text(
            json.dumps([record.model_dump(mode="json") for record in records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
