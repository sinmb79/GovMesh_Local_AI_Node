"""Small admin TUI-style status command for MVP operations."""

from __future__ import annotations

import argparse
import json
from typing import Any

import httpx
import uvicorn

from apps.admin_ui.app import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m apps.admin_ui")
    parser.add_argument("--control-plane", required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8795)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.serve:
        uvicorn.run(create_app(control_plane_url=args.control_plane), host=args.host, port=args.port)
        return 0
    print(json.dumps(build_status_snapshot(args.control_plane), ensure_ascii=False, indent=2))
    return 0


def build_status_snapshot(control_plane: str) -> dict[str, Any]:
    base = control_plane.rstrip("/")
    with httpx.Client(timeout=5) as client:
        health = client.get(f"{base}/health")
        health.raise_for_status()
        nodes = client.get(f"{base}/nodes")
        nodes.raise_for_status()
        tasks = client.get(f"{base}/tasks")
        tasks.raise_for_status()
        audit = client.get(f"{base}/audit/verify")
        audit.raise_for_status()
    node_items = nodes.json()
    task_items = tasks.json()
    return {
        "health": health.json(),
        "node_count": len(node_items),
        "online_nodes": sum(1 for node in node_items if node.get("status") == "online"),
        "task_count": len(task_items),
        "queued_tasks": sum(1 for task in task_items if task.get("status") == "queued"),
        "audit": audit.json(),
    }
