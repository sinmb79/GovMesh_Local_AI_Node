from scripts.govmesh_doctor import _parse_ports, build_report


def test_govmesh_doctor_reports_missing_env(monkeypatch) -> None:
    monkeypatch.delenv("GOVMESH_API_TOKEN", raising=False)
    monkeypatch.delenv("GOVMESH_AUDIT_SIGNING_KEY", raising=False)

    report = build_report(ports=[])

    assert report["ok"] is False
    assert {item["name"] for item in report["env"] if not item["ok"]} == {
        "GOVMESH_API_TOKEN",
        "GOVMESH_AUDIT_SIGNING_KEY",
    }


def test_govmesh_doctor_passes_with_required_env(monkeypatch) -> None:
    monkeypatch.setenv("GOVMESH_API_TOKEN", "local-test-token")
    monkeypatch.setenv("GOVMESH_AUDIT_SIGNING_KEY", "local-test-signing-key")

    report = build_report(ports=[])

    assert report["ok"] is True
    assert report["next_actions"] == ["Ready to start local GovMesh services"]


def test_govmesh_doctor_accepts_empty_port_list() -> None:
    assert _parse_ports("") == []
