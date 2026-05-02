"""Approval-gated GovMesh skill registry."""

from __future__ import annotations

from packages.govmesh_common.hashing import sha256_text
from packages.govmesh_common.schemas import SkillApproval, SkillDraft, SkillVersion, utc_now


class GovSkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDraft] = {}
        self._versions: dict[str, list[SkillVersion]] = {}
        self._approvals: list[SkillApproval] = []

    def create_draft(self, *, title: str, description: str, body: str, created_by: str) -> SkillDraft:
        draft = SkillDraft(title=title, description=description, body=body, created_by=created_by)
        self._skills[draft.skill_id] = draft
        self._versions[draft.skill_id] = [
            SkillVersion(
                skill_id=draft.skill_id,
                version=1,
                body_hash=sha256_text(body),
                status="draft",
            )
        ]
        return draft

    def request_review(self, skill_id: str) -> SkillDraft:
        return self._transition(skill_id, "review")

    def approve(self, skill_id: str, *, reviewer: str, reason: str | None = None) -> SkillDraft:
        skill = self._transition(skill_id, "approved")
        self._approvals.append(
            SkillApproval(skill_id=skill_id, reviewer=reviewer, decision="approved", reason=reason)
        )
        return skill

    def reject(self, skill_id: str, *, reviewer: str, reason: str | None = None) -> SkillDraft:
        skill = self._transition(skill_id, "rejected")
        self._approvals.append(
            SkillApproval(skill_id=skill_id, reviewer=reviewer, decision="rejected", reason=reason)
        )
        return skill

    def deploy(self, skill_id: str) -> SkillDraft:
        skill = self.get(skill_id)
        if skill.status != "approved":
            raise PermissionError("Only approved skills can be deployed")
        return self._transition(skill_id, "deployed")

    def ensure_executable(self, skill_id: str) -> SkillDraft:
        skill = self.get(skill_id)
        if skill.status != "deployed":
            raise PermissionError("Only deployed skills can be executed")
        return skill

    def get(self, skill_id: str) -> SkillDraft:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise KeyError(f"Unknown skill: {skill_id}") from exc

    def list(self) -> list[SkillDraft]:
        return list(self._skills.values())

    def versions(self, skill_id: str) -> list[SkillVersion]:
        self.get(skill_id)
        return list(self._versions[skill_id])

    def approvals(self) -> list[SkillApproval]:
        return list(self._approvals)

    def _transition(self, skill_id: str, status: str) -> SkillDraft:
        skill = self.get(skill_id).model_copy(update={"status": status, "updated_at": utc_now()})
        self._skills[skill_id] = skill
        versions = self._versions[skill_id]
        versions[-1] = versions[-1].model_copy(update={"status": status})
        return skill
