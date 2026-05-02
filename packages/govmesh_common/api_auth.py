"""Header-token authentication helpers for local GovMesh APIs."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Iterable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


ALL_ROLES = frozenset({"agent", "operator", "auditor", "importer", "approver"})


@dataclass(frozen=True)
class Principal:
    actor: str
    roles: frozenset[str]
    client_fingerprint: str | None = None

    def has_any_role(self, required_roles: Iterable[str]) -> bool:
        return bool(self.roles.intersection(required_roles))


class ApiAuthPolicy:
    """Small bearer-token policy for offline and localhost deployments.

    Tokens are intentionally provided by the caller or environment variables;
    this module never creates, stores, or logs secrets.
    """

    def __init__(
        self,
        token_roles: dict[str, Iterable[str]] | None = None,
        *,
        enabled: bool = True,
        allowed_client_fingerprints: Iterable[str] | None = None,
    ) -> None:
        self.enabled = enabled
        self._allowed_client_fingerprints = frozenset(
            _normalize_fingerprint(fingerprint) for fingerprint in (allowed_client_fingerprints or []) if fingerprint
        )
        self._token_roles = {
            token: frozenset(roles)
            for token, roles in (token_roles or {}).items()
            if token and roles
        }
        if self.enabled and not self._token_roles:
            raise ValueError("At least one API token is required when auth is enabled")

    @classmethod
    def disabled(cls) -> "ApiAuthPolicy":
        return cls(enabled=False)

    @classmethod
    def single_token(cls, token: str, roles: Iterable[str] = ALL_ROLES) -> "ApiAuthPolicy":
        return cls({token: roles})

    @classmethod
    def from_env(cls, *, required: bool = True) -> "ApiAuthPolicy":
        token_roles: dict[str, Iterable[str]] = {}
        shared = os.environ.get("GOVMESH_API_TOKEN")
        if shared:
            token_roles[shared] = ALL_ROLES

        role_envs = {
            "GOVMESH_AGENT_TOKEN": ("agent",),
            "GOVMESH_OPERATOR_TOKEN": ("operator", "auditor", "importer", "approver"),
            "GOVMESH_AUDITOR_TOKEN": ("auditor",),
            "GOVMESH_IMPORTER_TOKEN": ("importer",),
            "GOVMESH_APPROVER_TOKEN": ("approver",),
        }
        for env_name, roles in role_envs.items():
            token = os.environ.get(env_name)
            if token:
                token_roles[token] = roles

        if not token_roles and not required:
            return cls.disabled()
        allowed_fingerprints = _split_env_list(os.environ.get("GOVMESH_ALLOWED_CLIENT_FINGERPRINTS"))
        return cls(token_roles, allowed_client_fingerprints=allowed_fingerprints)

    def authenticate(
        self,
        token: str | None,
        required_roles: Iterable[str],
        *,
        client_fingerprint: str | None = None,
    ) -> Principal:
        if not self.enabled:
            return Principal(actor="anonymous-dev", roles=ALL_ROLES, client_fingerprint=client_fingerprint)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization: Bearer token is required",
            )
        normalized_fingerprint = _normalize_fingerprint(client_fingerprint) if client_fingerprint else None
        if self._allowed_client_fingerprints and normalized_fingerprint not in self._allowed_client_fingerprints:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client certificate fingerprint is not allowed")
        roles = self._lookup_roles(token)
        if roles is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")
        principal = Principal(actor="api-token", roles=roles, client_fingerprint=normalized_fingerprint)
        if required_roles and not principal.has_any_role(required_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient API role")
        return principal

    def _lookup_roles(self, token: str) -> frozenset[str] | None:
        for candidate, roles in self._token_roles.items():
            if secrets.compare_digest(candidate, token):
                return roles
        return None


_bearer = HTTPBearer(auto_error=False)


def require_roles(policy: ApiAuthPolicy, *required_roles: str):
    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        x_client_cert_sha256: str | None = Header(default=None, alias="X-Client-Cert-SHA256"),
    ) -> Principal:
        token = credentials.credentials if credentials else None
        return policy.authenticate(token, required_roles, client_fingerprint=x_client_cert_sha256)

    return dependency


def _normalize_fingerprint(value: str | None) -> str:
    return (value or "").replace(":", "").replace(" ", "").lower()


def _split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for chunk in value.split(";") for item in chunk.split(",") if item.strip()]
