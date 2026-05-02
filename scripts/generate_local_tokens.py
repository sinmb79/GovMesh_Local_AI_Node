"""Generate local GovMesh token environment lines."""

from __future__ import annotations

import argparse
import secrets


TOKEN_NAMES = [
    "GOVMESH_API_TOKEN",
    "GOVMESH_AGENT_TOKEN",
    "GOVMESH_OPERATOR_TOKEN",
    "GOVMESH_AUDITOR_TOKEN",
    "GOVMESH_IMPORTER_TOKEN",
    "GOVMESH_APPROVER_TOKEN",
    "GOVMESH_AUDIT_SIGNING_KEY",
    "GOVMESH_TRUSTED_PROXY_SECRET",
]


def generate_tokens(*, bytes_per_token: int = 32) -> dict[str, str]:
    return {name: secrets.token_urlsafe(bytes_per_token) for name in TOKEN_NAMES}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--powershell", action="store_true", help="print PowerShell environment commands")
    args = parser.parse_args(argv)
    tokens = generate_tokens()
    for name, value in tokens.items():
        if args.powershell:
            print(f'$env:{name}="{value}"')
        else:
            print(f"{name}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
