"""Operator readiness checks for local GovMesh deployments."""

from __future__ import annotations

import argparse
import json
import os
import socket
from typing import Any


REQUIRED_ENV = ["GOVMESH_API_TOKEN", "GOVMESH_AUDIT_SIGNING_KEY"]


def build_report(*, host: str = "127.0.0.1", ports: list[int] | None = None) -> dict[str, Any]:
    if ports is None:
        ports = [8787, 8790, 8795]
    env_checks = [
        {"name": name, "ok": bool(os.environ.get(name)), "message": "set" if os.environ.get(name) else "missing"}
        for name in REQUIRED_ENV
    ]
    port_checks = [{"port": port, "available": _port_available(host, port)} for port in ports]
    checks = env_checks + [{"name": f"port:{item['port']}", "ok": item["available"], "message": "available"} for item in port_checks]
    return {
        "host": host,
        "ok": all(check["ok"] for check in checks),
        "env": env_checks,
        "ports": port_checks,
        "next_actions": _next_actions(env_checks, port_checks),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ports", default="8787,8790,8795")
    args = parser.parse_args(argv)
    ports = _parse_ports(args.ports)
    report = build_report(host=args.host, ports=ports)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def _parse_ports(value: str) -> list[int]:
    if not value.strip():
        return []
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _next_actions(env_checks: list[dict[str, Any]], port_checks: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    missing = [check["name"] for check in env_checks if not check["ok"]]
    busy_ports = [str(check["port"]) for check in port_checks if not check["available"]]
    if missing:
        actions.append("Set required environment variables: " + ", ".join(missing))
    if busy_ports:
        actions.append("Choose another port or stop the process using: " + ", ".join(busy_ports))
    if not actions:
        actions.append("Ready to start local GovMesh services")
    return actions


if __name__ == "__main__":
    raise SystemExit(main())
