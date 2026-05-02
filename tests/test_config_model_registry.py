import pytest

from packages.govmesh_common import load_config
from packages.govmesh_runtime import ModelRegistry


def test_load_environment_profiles() -> None:
    local = load_config("local")
    secure = load_config("secure")
    test = load_config("test")

    assert local.bind_host == "127.0.0.1"
    assert secure.max_cpu_percent < local.max_cpu_percent
    assert test.default_worker_interval_seconds < local.default_worker_interval_seconds


def test_public_bind_requires_explicit_approval(tmp_path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "bad.json").write_text(
        '{"profile":"local","bind_host":"0.0.0.0","allow_public_bind":false}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_config("bad", config_dir=config_dir)


def test_model_registry_requires_license_approval(tmp_path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_text("fake model", encoding="utf-8")
    registry = ModelRegistry(tmp_path / "registry.json")

    record = registry.register_local_model(
        name="Fake GGUF",
        provider="llama.cpp",
        path=model_file,
        license="test-only",
    )

    with pytest.raises(PermissionError):
        registry.get_approved(record.model_id)

    approved = registry.approve_license(record.model_id, approved_by="boss")

    assert approved.approved is True
    assert registry.get_approved(record.model_id).sha256 == record.sha256
