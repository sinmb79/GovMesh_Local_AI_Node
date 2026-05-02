"""Pydantic schemas shared across GovMesh services."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class GovMeshModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Node(GovMeshModel):
    node_id: str = Field(default_factory=lambda: f"node_{uuid4().hex}")
    hostname: str
    os: str
    agent_version: str
    status: Literal["registered", "online", "offline", "disabled"] = "registered"
    cpu_count: int = Field(ge=1)
    memory_total_mb: int = Field(ge=1)
    disk_free_mb: int = Field(ge=0)
    has_gpu: bool = False
    gpu_name: str | None = None
    last_heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Task(GovMeshModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid4().hex}")
    task_type: Literal[
        "scan_pii",
        "index_document",
        "embed",
        "verify_hash",
        "rag_query",
        "benchmark",
    ]
    status: Literal["queued", "assigned", "running", "succeeded", "failed", "blocked"] = "queued"
    priority: int = Field(default=100, ge=0)
    assigned_node_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AuditEvent(GovMeshModel):
    event_id: str = Field(default_factory=lambda: f"audit_{uuid4().hex}")
    event_type: str
    actor: str
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    previous_hash: str | None = None
    event_hash: str | None = None
    signature: str | None = None


class FileRegistryEntry(GovMeshModel):
    file_id: str = Field(default_factory=lambda: f"file_{uuid4().hex}")
    path: str
    sha256: str
    size_bytes: int = Field(ge=0)
    media_type: str | None = None
    source: Literal["sample", "local", "quarantine", "registry"] = "local"
    approval_status: Literal["draft", "pending_review", "approved", "rejected"] = "draft"
    license: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class BenchmarkRun(GovMeshModel):
    run_id: str = Field(default_factory=lambda: f"bench_{uuid4().hex}")
    node_id: str | None = None
    benchmark_type: Literal["pc_profile", "mock_llm", "mock_embedding", "rag_search", "pii_scan"]
    status: Literal["pending", "running", "succeeded", "failed"] = "pending"
    metrics: dict[str, Any] = Field(default_factory=dict)
    report_path: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class PolicyDecision(GovMeshModel):
    allow: bool
    risk_level: Literal["low", "medium", "high", "blocked"]
    block_reason: str | None = None
    masked_text: str | None = None
    user_message: str
    findings: list[dict[str, Any]] = Field(default_factory=list)


class SkillDraft(GovMeshModel):
    skill_id: str = Field(default_factory=lambda: f"skill_{uuid4().hex}")
    title: str
    description: str
    body: str
    status: Literal["draft", "review", "approved", "rejected", "deployed"] = "draft"
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SkillVersion(GovMeshModel):
    version_id: str = Field(default_factory=lambda: f"skillver_{uuid4().hex}")
    skill_id: str
    version: int = Field(ge=1)
    body_hash: str
    status: Literal["draft", "review", "approved", "rejected", "deployed"]
    created_at: datetime = Field(default_factory=utc_now)


class SkillApproval(GovMeshModel):
    approval_id: str = Field(default_factory=lambda: f"approval_{uuid4().hex}")
    skill_id: str
    reviewer: str
    decision: Literal["approved", "rejected"]
    reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
