from scripts.setup_local_env import write_local_env


def test_setup_local_env_writes_ignored_local_files(tmp_path) -> None:
    paths = write_local_env(tmp_path / ".govmesh-local")

    env_text = (tmp_path / ".govmesh-local" / ".env.local").read_text(encoding="utf-8")
    ps_text = (tmp_path / ".govmesh-local" / "env.ps1").read_text(encoding="utf-8")

    assert "GOVMESH_API_TOKEN=" in env_text
    assert "$env:GOVMESH_API_TOKEN=" in ps_text
    assert paths["powershell_file"].endswith("env.ps1")
