"""Benchmark schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class BenchmarkModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PCProfile(BenchmarkModel):
    hostname: str
    os: str
    python_version: str
    cpu_count: int = Field(ge=1)
    memory_total_mb: int = Field(ge=0)
    disk_free_mb: int = Field(ge=0)
    has_gpu: bool = False
    gpu_name: str | None = None
    recommended_mode: Literal["safe", "balanced", "server"]
    recommended_model_size: str
    recommended_context_length: int = Field(ge=512)
    recommended_cpu_threads: int = Field(ge=1)


class BenchmarkResult(BenchmarkModel):
    name: str
    status: Literal["succeeded", "failed"]
    metrics: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    elapsed_ms: float = Field(ge=0)
    error: str | None = None


class BenchmarkReport(BenchmarkModel):
    run_id: str = Field(default_factory=lambda: f"bench_{uuid4().hex}")
    sample_dir: str
    pc_profile: PCProfile
    results: list[BenchmarkResult]
    json_report_path: str
    markdown_report_path: str
    created_at: datetime = Field(default_factory=utc_now)
