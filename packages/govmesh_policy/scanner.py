"""Local-only policy scanner for PII, internal markers, and prompt injection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from packages.govmesh_common import AuditChain, PolicyDecision, sha256_text


@dataclass(frozen=True)
class PolicyPattern:
    kind: str
    pattern: re.Pattern[str]
    risk_level: str
    block_reason: str
    confidence: float = 0.8


@dataclass(frozen=True)
class PolicyFinding:
    kind: str
    start: int
    end: int
    risk_level: str
    block_reason: str
    confidence: float
    match_hash: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "start": self.start,
            "end": self.end,
            "risk_level": self.risk_level,
            "block_reason": self.block_reason,
            "confidence": self.confidence,
            "match_hash": self.match_hash,
        }


PATTERNS = [
    PolicyPattern(
        "resident_registration_number",
        re.compile(r"\b\d{6}-[1-4]\d{6}\b"),
        "blocked",
        "pii_detected",
    ),
    PolicyPattern(
        "phone_number",
        re.compile(r"\b(?:01[016789]|02|0[3-6][1-5])-?\d{3,4}-?\d{4}\b"),
        "high",
        "phone_number_detected",
    ),
    PolicyPattern(
        "email",
        re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
        "high",
        "email_detected",
    ),
    PolicyPattern(
        "bank_account_candidate",
        re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,6}(?:-\d{1,6})?\b"),
        "high",
        "bank_account_candidate_detected",
    ),
    PolicyPattern(
        "internal_document_marker",
        re.compile(r"(대외비|비공개|내부전용|보안문서|외부전송\s*금지)"),
        "high",
        "internal_document_marker_detected",
    ),
    PolicyPattern(
        "prompt_injection_candidate",
        re.compile(r"(이전\s*지시를\s*무시|ignore\s+previous\s+instructions|system\s*prompt|developer\s*message)", re.I),
        "high",
        "prompt_injection_candidate_detected",
    ),
]


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "blocked": 3}


def scan_text(text: str, *, block_high_risk: bool = True) -> PolicyDecision:
    """Scan text and return a user-facing policy decision without leaking raw PII."""

    findings = list(_find(text))
    masked = mask_text(text, findings)
    highest = _highest_risk(findings)
    blocked = highest == "blocked" or (block_high_risk and highest == "high")

    if not findings:
        return PolicyDecision(
            allow=True,
            risk_level="low",
            user_message="정책 위반 후보가 발견되지 않았습니다.",
            masked_text=text,
            findings=[],
        )

    block_reason = _first_block_reason(findings)
    if blocked:
        user_message = "개인정보 또는 내부 보안정책 위반 후보가 있어 처리를 차단했습니다."
        risk_level = "blocked"
    else:
        user_message = "주의가 필요한 정책 위험 후보가 발견되었습니다."
        risk_level = highest

    return PolicyDecision(
        allow=not blocked,
        risk_level=risk_level,
        block_reason=block_reason,
        masked_text=masked,
        user_message=user_message,
        findings=[finding.to_dict() for finding in findings],
    )


def mask_text(text: str, findings: Iterable[PolicyFinding]) -> str:
    """Mask finding spans without changing unrelated text."""

    spans = sorted(((finding.start, finding.end) for finding in findings), reverse=True)
    masked = text
    for start, end in spans:
        width = max(4, end - start)
        masked = masked[:start] + "*" * width + masked[end:]
    return masked


def create_policy_alert(
    audit_chain: AuditChain,
    decision: PolicyDecision,
    *,
    actor: str,
    target_id: str | None = None,
):
    """Append a sanitized policy alert audit event when a decision blocks work."""

    if decision.allow:
        return None
    return audit_chain.append(
        event_type="policy.alert",
        actor=actor,
        target_id=target_id,
        payload={
            "risk_level": decision.risk_level,
            "block_reason": decision.block_reason,
            "finding_kinds": [finding["kind"] for finding in decision.findings],
            "masked_text_sha256_only": decision.masked_text is not None,
        },
    )


def _find(text: str) -> list[PolicyFinding]:
    findings: list[PolicyFinding] = []
    for policy_pattern in PATTERNS:
        for match in policy_pattern.pattern.finditer(text):
            findings.append(
                PolicyFinding(
                    kind=policy_pattern.kind,
                    start=match.start(),
                    end=match.end(),
                    risk_level=policy_pattern.risk_level,
                    block_reason=policy_pattern.block_reason,
                    confidence=policy_pattern.confidence,
                    match_hash=sha256_text(match.group(0)),
                )
            )
    return sorted(findings, key=lambda item: (item.start, item.end, item.kind))


def _highest_risk(findings: list[PolicyFinding]) -> str:
    if not findings:
        return "low"
    return max((finding.risk_level for finding in findings), key=lambda value: RISK_ORDER[value])


def _first_block_reason(findings: list[PolicyFinding]) -> str | None:
    if not findings:
        return None
    return sorted(findings, key=lambda finding: RISK_ORDER[finding.risk_level], reverse=True)[0].block_reason
