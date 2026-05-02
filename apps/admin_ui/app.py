"""Minimal operator dashboard for GovMesh."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def create_app(
    *,
    control_plane_url: str,
    api_token: str | None = None,
    status_provider: Callable[..., dict[str, Any]] | None = None,
) -> FastAPI:
    from apps.admin_ui.cli import build_status_snapshot

    provider = status_provider or build_status_snapshot
    app = FastAPI(title="GovMesh Admin UI", version="0.3.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _html()

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        if status_provider is not None:
            return provider(control_plane_url)
        return provider(control_plane_url, api_token=api_token)

    return app


def _html() -> str:
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GovMesh Admin</title>
  <style>
    :root { color-scheme: light; font-family: Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #f4f6f8; color: #15202b; }
    header { background: #243447; color: white; padding: 16px 24px; }
    main { max-width: 1120px; margin: 0 auto; padding: 20px; }
    h1 { margin: 0; font-size: 20px; font-weight: 650; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
    .metric { background: white; border: 1px solid #d9e0e7; border-radius: 6px; padding: 14px; }
    .label { color: #5d6975; font-size: 12px; }
    .value { font-size: 26px; font-weight: 700; margin-top: 8px; }
    table { width: 100%; margin-top: 18px; border-collapse: collapse; background: white; border: 1px solid #d9e0e7; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #edf1f4; font-size: 14px; }
    th { color: #435160; background: #f9fafb; }
    .ok { color: #126b39; font-weight: 700; }
    .bad { color: #a12727; font-weight: 700; }
  </style>
</head>
<body>
  <header><h1>GovMesh Admin</h1></header>
  <main>
    <section class="grid" id="metrics"></section>
    <table>
      <thead><tr><th>항목</th><th>값</th></tr></thead>
      <tbody id="details"></tbody>
    </table>
  </main>
  <script>
    const metrics = document.getElementById('metrics');
    const details = document.getElementById('details');
    const addMetric = (label, value) => {
      const item = document.createElement('div');
      item.className = 'metric';
      item.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
      metrics.appendChild(item);
    };
    const addRow = (label, value, klass = '') => {
      const row = document.createElement('tr');
      row.innerHTML = `<td>${label}</td><td class="${klass}">${value}</td>`;
      details.appendChild(row);
    };
    fetch('/api/status').then(r => r.json()).then(data => {
      addMetric('Nodes', data.node_count ?? 0);
      addMetric('Online', data.online_nodes ?? 0);
      addMetric('Tasks', data.task_count ?? 0);
      addMetric('Queued', data.queued_tasks ?? 0);
      addRow('Health', data.health?.ok ? 'OK' : 'FAIL', data.health?.ok ? 'ok' : 'bad');
      addRow('Schema', data.health?.schema_version ?? '-');
      addRow('Audit', data.audit?.valid ? 'VALID' : 'INVALID', data.audit?.valid ? 'ok' : 'bad');
    }).catch(() => {
      addMetric('Status', 'ERR');
      addRow('Health', 'UNAVAILABLE', 'bad');
    });
  </script>
</body>
</html>
"""
