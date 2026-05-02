import json

from scripts.build_evidence_package import _build_governance_summary


def test_governance_summary_requires_key_modules() -> None:
    manifest = [
        {"path": "docs/SECURITY_MODEL.md"},
        {"path": "docs/RISK_REGISTER.md"},
        {"path": "docs/HARDENING_NOTES.md"},
        {"path": "docs/RELEASE_CHECKLIST.md"},
        {"path": "docs/RUNBOOK.md"},
        {"path": "packages/govmesh_review/queue.py"},
        {"path": "packages/govmesh_quarantine/external.py"},
        {"path": "packages/govmesh_quarantine/cdr.py"},
        {"path": "packages/govmesh_runtime/grounding.py"},
        {"path": "packages/govmesh_identity/proxy_signature.py"},
    ]

    summary = _build_governance_summary(manifest)

    assert summary["all_required_present"] is True
    assert json.dumps(summary)
