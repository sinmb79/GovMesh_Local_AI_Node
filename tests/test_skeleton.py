from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_scaffold_files_exist() -> None:
    required = [
        "README.md",
        "README.en.md",
        "pyproject.toml",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "docs/BENCHMARKING.md",
        "docs/USER_REQUIREMENTS.md",
        "docs/RISK_REGISTER.md",
        "docs/SECURITY_MODEL.md",
        "docs/API_SPEC.md",
        "docs/RUNBOOK.md",
        "docs/RELEASE_CHECKLIST.md",
        "docs/GETTING_STARTED_KO.md",
        "docs/INSTALL_WINDOWS.md",
        "docs/DISTRIBUTION.md",
    ]

    missing = [path for path in required if not (ROOT / path).exists()]
    assert missing == []


def test_readme_contains_safety_baseline() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "실제 정부 데이터 사용 금지" in readme
    assert "실제 개인정보 사용 금지" in readme
    assert "감사 로그에 raw PII 저장 금지" in readme
    assert "127.0.0.1" in readme


def test_public_readme_does_not_mention_submission_context() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    blocked_terms = [
        "".join(chr(code) for code in (0xD574, 0xCEE4, 0xD1A4)),
        "hack" + "athon",
    ]
    assert all(term not in readme for term in blocked_terms)
