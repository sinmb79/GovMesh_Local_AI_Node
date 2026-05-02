"""FastAPI control plane for node, task, audit, benchmark, and skill workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from apps.control_plane.repository import SQLiteRepository
from packages.govmesh_common import (
    ApiAuthPolicy,
    AuditChain,
    AuditEvent,
    BenchmarkRun,
    GovSkillRegistry,
    Node,
    Principal,
    Task,
    require_roles,
)
from packages.govmesh_common.schemas import utc_now
from packages.govmesh_review import ReviewDecision, ReviewQueue


class NodeRegisterRequest(BaseModel):
    hostname: str
    os: str
    agent_version: str
    cpu_count: int = Field(ge=1)
    memory_total_mb: int = Field(ge=1)
    disk_free_mb: int = Field(ge=0)
    has_gpu: bool = False
    gpu_name: str | None = None


class HeartbeatRequest(BaseModel):
    status: Literal["online", "offline", "disabled"] = "online"
    cpu_count: int | None = Field(default=None, ge=1)
    memory_total_mb: int | None = Field(default=None, ge=1)
    disk_free_mb: int | None = Field(default=None, ge=0)


class TaskCreateRequest(BaseModel):
    task_type: Literal["scan_pii", "index_document", "embed", "verify_hash", "rag_query", "benchmark"]
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=100, ge=0)


class TaskResultRequest(BaseModel):
    status: Literal["succeeded", "failed", "blocked"]
    result: dict[str, Any] | None = None
    error: str | None = None
    retry: bool = False


class SkillDraftRequest(BaseModel):
    title: str
    description: str
    body: str
    created_by: str


class ReviewRequest(BaseModel):
    reviewer: str = "reviewer"
    reason: str | None = None


def create_app(
    *,
    db_path: str | Path = ".govmesh-local/control-plane.sqlite3",
    audit_path: str | Path = ".govmesh-local/control-plane-audit.jsonl",
    review_path: str | Path = ".govmesh-local/reviews.jsonl",
    auth_policy: ApiAuthPolicy | None = None,
    audit_signing_key: str | None = None,
) -> FastAPI:
    repo = SQLiteRepository(db_path)
    audit = AuditChain(audit_path, signing_key=audit_signing_key)
    reviews = ReviewQueue(review_path)
    skills = GovSkillRegistry()
    auth = auth_policy or ApiAuthPolicy.disabled()
    app = FastAPI(title="GovMesh Control Plane", version="0.3.1")
    require_agent = require_roles(auth, "agent", "operator")
    require_operator = require_roles(auth, "operator")
    require_auditor = require_roles(auth, "auditor", "operator")

    @app.post("/nodes/register", response_model=Node)
    def register_node(request: NodeRegisterRequest, principal: Principal = Depends(require_agent)) -> Node:
        node = repo.save_node(Node(**request.model_dump()))
        audit.append(
            event_type="node.registered",
            actor=principal.actor,
            target_id=node.node_id,
            payload={"hostname": node.hostname},
        )
        return node

    @app.post("/nodes/{node_id}/heartbeat", response_model=Node)
    def heartbeat(node_id: str, request: HeartbeatRequest, principal: Principal = Depends(require_agent)) -> Node:
        try:
            node = repo.get_node(node_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Node not found") from exc
        update = {"status": request.status, "last_heartbeat_at": utc_now()}
        for field in ("cpu_count", "memory_total_mb", "disk_free_mb"):
            value = getattr(request, field)
            if value is not None:
                update[field] = value
        node = repo.save_node(node.model_copy(update=update))
        audit.append(
            event_type="node.heartbeat",
            actor=principal.actor,
            target_id=node.node_id,
            payload={"status": node.status},
        )
        return node

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "schema_version": repo.schema_version()}

    @app.get("/nodes", response_model=list[Node])
    def list_nodes(
        status: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        _: Principal = Depends(require_operator),
    ) -> list[Node]:
        return repo.list_nodes(status=status, limit=limit, offset=offset)

    @app.post("/tasks", response_model=Task)
    def create_task(request: TaskCreateRequest, principal: Principal = Depends(require_operator)) -> Task:
        task = repo.save_task(Task(**request.model_dump()))
        audit.append(
            event_type="task.created",
            actor=principal.actor,
            target_id=task.task_id,
            payload={"task_type": task.task_type},
        )
        return task

    @app.get("/tasks", response_model=list[Task])
    def list_tasks(
        status: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        _: Principal = Depends(require_operator),
    ) -> list[Task]:
        return repo.list_tasks(status=status, limit=limit, offset=offset)

    @app.get("/tasks/next", response_model=Task | None)
    def next_task(
        node_id: str | None = Query(default=None),
        principal: Principal = Depends(require_agent),
    ) -> Task | None:
        task = repo.next_task()
        if task is None:
            return None
        update = {"status": "assigned"}
        if node_id:
            update["assigned_node_id"] = node_id
        task = repo.save_task(task.model_copy(update=update))
        audit.append(
            event_type="task.assigned",
            actor=principal.actor,
            target_id=task.task_id,
            payload={"node_id": node_id},
        )
        return task

    @app.post("/tasks/{task_id}/result", response_model=Task)
    def task_result(task_id: str, request: TaskResultRequest, principal: Principal = Depends(require_agent)) -> Task:
        try:
            task = repo.get_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        if request.status == "failed" and request.retry:
            task = repo.retry_task(task_id, error=request.error)
            event_type = "task.retry_scheduled"
        else:
            task = repo.save_task(
                task.model_copy(
                    update={
                        "status": request.status,
                        "result": request.result,
                        "error": request.error,
                        "updated_at": utc_now(),
                    }
                )
            )
            event_type = "task.result"
        audit.append(
            event_type=event_type,
            actor=principal.actor,
            target_id=task.task_id,
            payload={"status": task.status, "retry_count": task.retry_count},
        )
        return task

    @app.post("/audit/events", response_model=AuditEvent)
    def append_audit(event: AuditEvent, principal: Principal = Depends(require_operator)) -> AuditEvent:
        sanitized = event.model_copy(
            update={
                "actor": principal.actor,
                "previous_hash": None,
                "event_hash": None,
                "signature": None,
            }
        )
        return audit.append(sanitized)

    @app.get("/audit/events", response_model=list[AuditEvent])
    def list_audit(_: Principal = Depends(require_auditor)) -> list[AuditEvent]:
        return audit.list()

    @app.get("/audit/verify")
    def verify_audit(_: Principal = Depends(require_auditor)) -> dict[str, bool]:
        return {"valid": audit.verify()}

    @app.post("/benchmarks", response_model=BenchmarkRun)
    def record_benchmark(run: BenchmarkRun, principal: Principal = Depends(require_operator)) -> BenchmarkRun:
        saved = repo.save_benchmark(run)
        audit.append(
            event_type="benchmark.recorded",
            actor=principal.actor,
            target_id=saved.run_id,
            payload={"benchmark_type": saved.benchmark_type, "status": saved.status},
        )
        return saved

    @app.get("/benchmarks", response_model=list[BenchmarkRun])
    def list_benchmarks(_: Principal = Depends(require_operator)) -> list[BenchmarkRun]:
        return repo.list_benchmarks()

    @app.post("/reviews")
    def create_review(request: dict[str, Any], principal: Principal = Depends(require_operator)):
        item = reviews.create(
            target_type=request["target_type"],
            target_id=request["target_id"],
            reason=request["reason"],
            summary=request.get("summary", ""),
            risk_level=request.get("risk_level", "medium"),
            content=request.get("content"),
            evidence_ids=request.get("evidence_ids") or [],
            created_by=principal.actor,
        )
        audit.append(event_type="review.created", actor=principal.actor, target_id=item.review_id, payload={"target_id": item.target_id})
        return item

    @app.get("/reviews")
    def list_reviews(
        status: str | None = Query(default=None),
        _: Principal = Depends(require_operator),
    ):
        return reviews.list(status=status)

    @app.post("/reviews/{review_id}/decision")
    def decide_review(review_id: str, request: ReviewDecision, principal: Principal = Depends(require_operator)):
        try:
            item = reviews.decide(review_id, request)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Review not found") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        audit.append(
            event_type="review.decided",
            actor=principal.actor,
            target_id=review_id,
            payload={"status": item.status, "target_id": item.target_id},
        )
        return item

    @app.post("/skills/drafts")
    def create_skill(request: SkillDraftRequest, _: Principal = Depends(require_operator)):
        skill = skills.create_draft(**request.model_dump())
        audit.append(event_type="skill.draft.created", actor=request.created_by, target_id=skill.skill_id)
        return skill

    @app.post("/skills/{skill_id}/review")
    def request_skill_review(skill_id: str, _: Principal = Depends(require_operator)):
        try:
            skill = skills.request_review(skill_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill not found") from exc
        audit.append(event_type="skill.review.requested", actor="control-plane", target_id=skill_id)
        return skill

    @app.post("/skills/{skill_id}/approve")
    def approve_skill(skill_id: str, request: ReviewRequest, _: Principal = Depends(require_operator)):
        try:
            skill = skills.approve(skill_id, reviewer=request.reviewer, reason=request.reason)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill not found") from exc
        audit.append(event_type="skill.approved", actor=request.reviewer, target_id=skill_id)
        return skill

    @app.post("/skills/{skill_id}/reject")
    def reject_skill(skill_id: str, request: ReviewRequest, _: Principal = Depends(require_operator)):
        try:
            skill = skills.reject(skill_id, reviewer=request.reviewer, reason=request.reason)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill not found") from exc
        audit.append(event_type="skill.rejected", actor=request.reviewer, target_id=skill_id)
        return skill

    @app.post("/skills/{skill_id}/deploy")
    def deploy_skill(skill_id: str, _: Principal = Depends(require_operator)):
        try:
            skill = skills.deploy(skill_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill not found") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        audit.append(event_type="skill.deployed", actor="control-plane", target_id=skill_id)
        return skill

    @app.post("/skills/{skill_id}/execute-check")
    def execute_check(skill_id: str, _: Principal = Depends(require_operator)):
        try:
            skill = skills.ensure_executable(skill_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Skill not found") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"allowed": True, "skill_id": skill.skill_id}

    @app.get("/skills")
    def list_skills(_: Principal = Depends(require_operator)):
        return skills.list()

    return app
