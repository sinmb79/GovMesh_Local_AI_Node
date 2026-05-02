import httpx
from fastapi.testclient import TestClient

from apps.admin_ui.cli import build_status_snapshot
from apps.control_plane import create_app


class ASGITransportWrapper(httpx.BaseTransport):
    def __init__(self, app):
        self._transport = httpx.ASGITransport(app=app)

    def handle_request(self, request):
        raise RuntimeError("sync wrapper should be monkeypatched by test")


def test_admin_status_snapshot(monkeypatch, tmp_path) -> None:
    app = create_app(db_path=tmp_path / "control.sqlite3", audit_path=tmp_path / "audit.jsonl")
    test_client = TestClient(app)
    test_client.post(
        "/nodes/register",
        json={
            "hostname": "admin-pc",
            "os": "Windows 11",
            "agent_version": "0.2.0",
            "cpu_count": 8,
            "memory_total_mb": 16384,
            "disk_free_mb": 100000,
        },
    )
    test_client.post("/tasks", json={"task_type": "scan_pii", "payload": {"text": "clean"}})

    class FakeResponse:
        def __init__(self, response):
            self._response = response

        def raise_for_status(self):
            self._response.raise_for_status()

        def json(self):
            return self._response.json()

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, **kwargs):
            path = "/" + url.split("/", 3)[3]
            return FakeResponse(test_client.get(path))

    monkeypatch.setattr(httpx, "Client", FakeClient)

    snapshot = build_status_snapshot("http://control-plane")

    assert snapshot["health"]["ok"] is True
    assert snapshot["node_count"] == 1
    assert snapshot["task_count"] == 1
    assert snapshot["audit"]["valid"] is True
