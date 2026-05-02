"""Create local GovMesh environment files from generated tokens."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.generate_local_tokens import generate_tokens


def write_local_env(output_dir: str | Path = ".govmesh-local") -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tokens = generate_tokens()
    env_lines = [f"{name}={value}" for name, value in tokens.items()]
    ps_lines = [f'$env:{name}="{value}"' for name, value in tokens.items()]
    (out / ".env.local").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    (out / "env.ps1").write_text("\n".join(ps_lines) + "\n", encoding="utf-8")
    return {
        "env_file": str(out / ".env.local"),
        "powershell_file": str(out / "env.ps1"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".govmesh-local")
    args = parser.parse_args(argv)
    paths = write_local_env(args.out)
    print(paths["powershell_file"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
