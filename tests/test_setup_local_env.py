import subprocess
import sys
from pathlib import Path

from scripts.setup_local_env import write_local_env


ROOT = Path(__file__).resolve().parents[1]


def test_setup_local_env_writes_ignored_local_files(tmp_path) -> None:
    paths = write_local_env(tmp_path / ".govmesh-local")

    env_text = (tmp_path / ".govmesh-local" / ".env.local").read_text(encoding="utf-8")
    ps_text = (tmp_path / ".govmesh-local" / "env.ps1").read_text(encoding="utf-8")

    assert "GOVMESH_API_TOKEN=" in env_text
    assert "$env:GOVMESH_API_TOKEN=" in ps_text
    assert paths["powershell_file"].endswith("env.ps1")


def test_setup_local_env_script_runs_directly(tmp_path) -> None:
    output_dir = tmp_path / ".govmesh-local"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "setup_local_env.py"), "--out", str(output_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_dir / ".env.local").exists()
    assert (output_dir / "env.ps1").exists()
