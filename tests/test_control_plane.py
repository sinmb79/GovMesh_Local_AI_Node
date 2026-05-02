from fastapi.testclient import TestClient
import time

from apps.control_plane import create_app
from packages.govmesh_common import ApiAuthPolicy
from packages.govmesh_identity import sign_proxy_identity


AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def test_control_plane_node_task_audit_and_benchmark_flow(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "control.sqlite3", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)

    node_response = client.post(
        "/nodes/register",
        json={
            "hostname": "sample-pc",
            "os": "Windows 11",
            "agent_version": "0.2.0",
            "cpu_count": 8,
            "memory_total_mb": 16384,
            "disk_free_mb": 100000,
        },
    )
    assert node_response.status_code == 200
    node_id = node_response.json()["node_id"]

    heartbeat = client.post(f"/nodes/{node_id}/heartbeat", json={"status": "online"})
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "online"

    task_response = client.post("/tasks", json={"task_type": "scan_pii", "payload": {"text": "clean"}})
    assert task_response.status_code == 200
    task_id = task_response.json()["task_id"]

    next_response = client.get("/tasks/next", params={"node_id": node_id})
    assert next_response.status_code == 200
    assert next_response.json()["assigned_node_id"] == node_id

    result_response = client.post(f"/tasks/{task_id}/result", json={"status": "succeeded", "result": {"ok": True}})
    assert result_response.status_code == 200
    assert result_response.json()["status"] == "succeeded"

    benchmark_response = client.post(
        "/benchmarks",
        json={"benchmark_type": "pc_profile", "status": "succeeded", "metrics": {"cpu": 8}},
    )
    assert benchmark_response.status_code == 200
    assert client.get("/audit/verify").json() == {"valid": True}
    assert len(client.get("/audit/events").json()) >= 5
    assert client.get("/health").json()["schema_version"] == 1


def test_control_plane_requires_roles_when_auth_enabled(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "control.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        auth_policy=ApiAuthPolicy.single_token("test-token", roles={"operator", "auditor"}),
        audit_signing_key="test-signing-key",
    )
    client = TestClient(app)

    unauthenticated = client.get("/nodes")
    assert unauthenticated.status_code == 401

    node_response = client.post(
        "/nodes/register",
        headers=AUTH_HEADERS,
        json={
            "hostname": "sample-pc",
            "os": "Windows 11",
            "agent_version": "0.2.0",
            "cpu_count": 8,
            "memory_total_mb": 16384,
            "disk_free_mb": 100000,
        },
    )
    assert node_response.status_code == 200
    assert client.get("/nodes", headers=AUTH_HEADERS).status_code == 200
    audit_events = client.get("/audit/events", headers=AUTH_HEADERS).json()
    assert audit_events[0]["signature"]
    assert client.get("/audit/verify", headers=AUTH_HEADERS).json() == {"valid": True}


def test_control_plane_can_require_client_certificate_fingerprint(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "control.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        auth_policy=ApiAuthPolicy(
            {"test-token": {"operator", "auditor"}},
            allowed_client_fingerprints={"AA:BB:CC"},
        ),
    )
    client = TestClient(app)

    assert client.get("/nodes", headers=AUTH_HEADERS).status_code == 403
    assert client.get(
        "/nodes",
        headers={**AUTH_HEADERS, "X-Client-Cert-SHA256": "aa bb cc"},
    ).status_code == 200


def test_control_plane_accepts_signed_sso_proxy_headers(tmp_path) -> None:
    issued_at = str(int(time.time()))
    signature = sign_proxy_identity(
        secret="proxy-secret",
        user_id="operator-1",
        roles={"operator", "auditor"},
        issued_at=int(issued_at),
    )
    app = create_app(
        db_path=tmp_path / "control.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        auth_policy=ApiAuthPolicy({"fallback-token": {"operator"}}, trusted_proxy_secret="proxy-secret"),
    )
    client = TestClient(app)

    headers = {
        "X-GovMesh-User": "operator-1",
        "X-GovMesh-Roles": "operator,auditor",
        "X-GovMesh-Issued-At": issued_at,
        "X-GovMesh-Proxy-Signature": signature,
    }

    assert client.get("/nodes", headers=headers).status_code == 200
    assert client.get("/audit/verify", headers=headers).status_code == 200


def test_control_plane_filters_and_retries_failed_tasks(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "control.sqlite3", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)

    client.post(
        "/nodes/register",
        json={
            "hostname": "sample-pc",
            "os": "Windows 11",
            "agent_version": "0.2.0",
            "cpu_count": 8,
            "memory_total_mb": 16384,
            "disk_free_mb": 100000,
        },
    )
    assert len(client.get("/nodes", params={"status": "registered"}).json()) == 1

    task = client.post("/tasks", json={"task_type": "scan_pii", "payload": {"text": "clean"}}).json()
    task_id = task["task_id"]

    failed = client.post(
        f"/tasks/{task_id}/result",
        json={"status": "failed", "error": "temporary", "retry": True},
    ).json()

    assert failed["status"] == "queued"
    assert failed["retry_count"] == 1
    assert len(client.get("/tasks", params={"status": "queued"}).json()) == 1


def test_skill_registry_requires_approval_before_deploy_and_execution(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "control.sqlite3", audit_path=tmp_path / "audit.jsonl")
    client = TestClient(app)

    draft = client.post(
        "/skills/drafts",
        json={
            "title": "샘플 검토",
            "description": "테스트 skill",
            "body": "검토 절차",
            "created_by": "tester",
        },
    ).json()
    skill_id = draft["skill_id"]

    assert client.post(f"/skills/{skill_id}/execute-check").status_code == 403
    assert client.post(f"/skills/{skill_id}/deploy").status_code == 403
    assert client.post(f"/skills/{skill_id}/review").json()["status"] == "review"
    assert client.post(f"/skills/{skill_id}/approve", json={"reviewer": "boss"}).json()["status"] == "approved"
    assert client.post(f"/skills/{skill_id}/deploy").json()["status"] == "deployed"
    assert client.post(f"/skills/{skill_id}/execute-check").json()["allowed"] is True


def test_control_plane_review_queue_flow(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "control.sqlite3",
        audit_path=tmp_path / "audit.jsonl",
        review_path=tmp_path / "reviews.jsonl",
    )
    client = TestClient(app)

    created = client.post(
        "/reviews",
        json={
            "target_type": "rag_answer",
            "target_id": "answer-1",
            "reason": "grounding_required",
            "summary": "Needs review",
            "content": "raw answer should not be stored",
            "evidence_ids": ["doc#1"],
        },
    ).json()
    review_id = created["review_id"]
    decided = client.post(
        f"/reviews/{review_id}/decision",
        json={"decision": "approved", "reviewer": "operator", "reason": "ok"},
    ).json()

    assert created["content_hash"]
    assert decided["status"] == "approved"
    assert client.get("/reviews", params={"status": "open"}).json() == []
    assert "raw answer should not be stored" not in (tmp_path / "reviews.jsonl").read_text(encoding="utf-8")
