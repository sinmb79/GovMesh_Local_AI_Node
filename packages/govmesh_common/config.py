"""Environment profile configuration for GovMesh."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GovMeshConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: Literal["local", "secure", "test"]
    bind_host: str = "127.0.0.1"
    control_plane_port: int = Field(default=8787, ge=1, le=65535)
    quarantine_gateway_port: int = Field(default=8790, ge=1, le=65535)
    storage_dir: str = ".govmesh-local"
    external_network: Literal["disabled", "gateway_only"] = "disabled"
    allow_public_bind: bool = False
    max_cpu_percent: int = Field(default=60, ge=1, le=100)
    default_worker_interval_seconds: float = Field(default=5.0, ge=0.1)
    approved_model_registry_path: str = ".govmesh-local/model-registry.json"

    @property
    def control_plane_url(self) -> str:
        return f"http://{self.bind_host}:{self.control_plane_port}"


def load_config(profile: str | None = None, *, config_dir: str | Path | None = None) -> GovMeshConfig:
    selected = profile or os.environ.get("GOVMESH_PROFILE", "local")
    base_dir = Path(config_dir) if config_dir is not None else Path(__file__).resolve().parents[2] / "configs"
    path = base_dir / f"{selected}.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown GovMesh config profile: {selected}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    env_bind = os.environ.get("GOVMESH_BIND_HOST")
    if env_bind:
        payload["bind_host"] = env_bind
    config = GovMeshConfig.model_validate(payload)
    if config.bind_host != "127.0.0.1" and not config.allow_public_bind:
        raise ValueError("Public bind requires allow_public_bind=true")
    return config
