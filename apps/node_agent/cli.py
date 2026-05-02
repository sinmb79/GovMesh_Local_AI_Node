"""Local node-agent CLI."""

from __future__ import annotations

import argparse
import json
import os
import time
import socket
from pathlib import Path
from typing import Any

import httpx

from packages.govmesh_benchmark.runner import collect_pc_profile
from packages.govmesh_policy import scan_text
from packages.govmesh_rag import LocalRAGService
from packages.govmesh_runtime import MockLLMProvider, generate_with_policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m apps.node_agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register")
    register.add_argument("--control-plane", default=None)
    register.add_argument("--agent-version", default="0.3.0")
    register.add_argument("--api-token", default=None)

    heartbeat = subparsers.add_parser("heartbeat")
    heartbeat.add_argument("--control-plane", required=True)
    heartbeat.add_argument("--node-id", required=True)
    heartbeat.add_argument("--api-token", default=None)

    worker = subparsers.add_parser("run-worker")
    worker.add_argument("--control-plane", required=True)
    worker.add_argument("--node-id", required=True)
    worker.add_argument("--api-token", default=None)
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--interval", type=float, default=5.0)
    worker.add_argument("--max-iterations", type=int, default=None)

    scan_folder = subparsers.add_parser("scan-folder")
    scan_folder.add_argument("--path", required=True)

    query = subparsers.add_parser("query")
    query.add_argument("--sample", required=True)
    query.add_argument("--question", required=True)
    query.add_argument("--top-k", type=int, default=3)

    subparsers.add_parser("performance-doctor")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "performance-doctor":
        _print_json(performance_doctor())
        return 0
    if args.command == "scan-folder":
        _print_json(scan_folder(Path(args.path)))
        return 0
    if args.command == "query":
        _print_json(query_folder(Path(args.sample), args.question, top_k=args.top_k))
        return 0
    if args.command == "register":
        _print_json(register(args.control_plane, agent_version=args.agent_version, api_token=args.api_token))
        return 0
    if args.command == "heartbeat":
        _print_json(heartbeat(args.control_plane, args.node_id, api_token=args.api_token))
        return 0
    if args.command == "run-worker":
        if args.once:
            _print_json(run_worker_once(args.control_plane, args.node_id, api_token=args.api_token))
        else:
            _print_json(
                run_worker_loop(
                    args.control_plane,
                    args.node_id,
                    interval=args.interval,
                    max_iterations=args.max_iterations,
                    api_token=args.api_token,
                )
            )
        return 0
    return 1


def performance_doctor() -> dict[str, Any]:
    profile = collect_pc_profile()
    return {
        "hostname": profile.hostname,
        "recommended_mode": profile.recommended_mode,
        "recommended_model_size": profile.recommended_model_size,
        "recommended_context_length": profile.recommended_context_length,
        "recommended_cpu_threads": profile.recommended_cpu_threads,
        "safe_mode": profile.recommended_mode == "safe",
    }


def scan_folder(path: Path) -> dict[str, Any]:
    files = [item for item in sorted(path.rglob("*")) if item.is_file() and item.suffix.lower() in {".md", ".txt"}]
    decisions = []
    for file_path in files:
        decision = scan_text(file_path.read_text(encoding="utf-8"))
        decisions.append(
            {
                "path": str(file_path),
                "allow": decision.allow,
                "risk_level": decision.risk_level,
                "block_reason": decision.block_reason,
                "finding_count": len(decision.findings),
            }
        )
    return {
        "document_count": len(files),
        "blocked_count": sum(1 for decision in decisions if not decision["allow"]),
        "decisions": decisions,
    }


def query_folder(path: Path, question: str, *, top_k: int = 3) -> dict[str, Any]:
    rag = LocalRAGService()
    for file_path in sorted(path.rglob("*")):
        if file_path.is_file() and file_path.suffix.lower() in {".md", ".txt"}:
            rag.index_file(file_path)
    rag_result = rag.query(question, top_k=top_k)
    policy_decision = scan_text(question)
    provider = MockLLMProvider()
    answer = generate_with_policy(provider, question, policy_decision, contexts=rag_result["contexts"])
    return {"answer": answer, "contexts": rag_result["contexts"]}


def register(control_plane: str | None, *, agent_version: str, api_token: str | None = None) -> dict[str, Any]:
    profile = collect_pc_profile()
    payload = {
        "hostname": socket.gethostname(),
        "os": profile.os,
        "agent_version": agent_version,
        "cpu_count": profile.cpu_count,
        "memory_total_mb": max(1, profile.memory_total_mb),
        "disk_free_mb": profile.disk_free_mb,
        "has_gpu": profile.has_gpu,
        "gpu_name": profile.gpu_name,
    }
    if not control_plane:
        return {"offline": True, "node": payload}
    with httpx.Client(timeout=5) as client:
        response = client.post(f"{control_plane.rstrip('/')}/nodes/register", json=payload, headers=_auth_headers(api_token))
        response.raise_for_status()
        return response.json()


def heartbeat(control_plane: str, node_id: str, *, api_token: str | None = None) -> dict[str, Any]:
    profile = collect_pc_profile()
    payload = {
        "status": "online",
        "cpu_count": profile.cpu_count,
        "memory_total_mb": max(1, profile.memory_total_mb),
        "disk_free_mb": profile.disk_free_mb,
    }
    with httpx.Client(timeout=5) as client:
        response = client.post(
            f"{control_plane.rstrip('/')}/nodes/{node_id}/heartbeat",
            json=payload,
            headers=_auth_headers(api_token),
        )
        response.raise_for_status()
        return response.json()


def run_worker_once(control_plane: str, node_id: str, *, api_token: str | None = None) -> dict[str, Any]:
    headers = _auth_headers(api_token)
    with httpx.Client(timeout=5) as client:
        response = client.get(f"{control_plane.rstrip('/')}/tasks/next", params={"node_id": node_id}, headers=headers)
        response.raise_for_status()
        task = response.json()
        if task is None:
            return {"task": None, "status": "idle"}
        result = _execute_task(task)
        result_response = client.post(
            f"{control_plane.rstrip('/')}/tasks/{task['task_id']}/result",
            json={"status": result["status"], "result": result.get("result"), "error": result.get("error")},
            headers=headers,
        )
        result_response.raise_for_status()
        return result_response.json()


def run_worker_loop(
    control_plane: str,
    node_id: str,
    *,
    interval: float = 5.0,
    max_iterations: int | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    iterations = 0
    processed = 0
    last_result: dict[str, Any] | None = None
    while max_iterations is None or iterations < max_iterations:
        last_result = run_worker_once(control_plane, node_id, api_token=api_token)
        iterations += 1
        if last_result.get("status") != "idle":
            processed += 1
        if max_iterations is not None and iterations >= max_iterations:
            break
        time.sleep(interval)
    return {"iterations": iterations, "processed": processed, "last_result": last_result}


def _execute_task(task: dict[str, Any]) -> dict[str, Any]:
    task_type = task["task_type"]
    payload = task.get("payload") or {}
    try:
        if task_type == "scan_pii":
            decision = scan_text(payload.get("text", ""))
            return {"status": "blocked" if not decision.allow else "succeeded", "result": decision.model_dump(mode="json")}
        if task_type == "rag_query":
            answer = query_folder(Path(payload["sample_dir"]), payload["question"])
            return {"status": "succeeded", "result": answer}
        return {"status": "succeeded", "result": {"message": f"{task_type} acknowledged by MVP worker"}}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _auth_headers(api_token: str | None = None) -> dict[str, str]:
    token = api_token or os.environ.get("GOVMESH_AGENT_TOKEN") or os.environ.get("GOVMESH_API_TOKEN")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}
