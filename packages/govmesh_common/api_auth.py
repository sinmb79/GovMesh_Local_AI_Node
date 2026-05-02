"""Header-token authentication helpers for local GovMesh APIs."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Iterable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.govmesh_identity import verify_proxy_identity


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
        trusted_proxy_secret: str | bytes | None = None,
    ) -> None:
        self.enabled = enabled
        self._trusted_proxy_secret = trusted_proxy_secret
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
        return cls(
            token_roles,
            allowed_client_fingerprints=allowed_fingerprints,
            trusted_proxy_secret=os.environ.get("GOVMESH_TRUSTED_PROXY_SECRET"),
        )

    def authenticate(
        self,
        token: str | None,
        required_roles: Iterable[str],
        *,
        client_fingerprint: str | None = None,
        proxy_user: str | None = None,
        proxy_roles: str | None = None,
        proxy_issued_at: str | None = None,
        proxy_signature: str | None = None,
    ) -> Principal:
        if not self.enabled:
            return Principal(actor="anonymous-dev", roles=ALL_ROLES, client_fingerprint=client_fingerprint)
        normalized_fingerprint = _normalize_fingerprint(client_fingerprint) if client_fingerprint else None
        proxy_principal = self._authenticate_proxy(
            proxy_user=proxy_user,
            proxy_roles=proxy_roles,
            proxy_issued_at=proxy_issued_at,
            proxy_signature=proxy_signature,
            client_fingerprint=normalized_fingerprint,
        )
        if proxy_principal is not None:
            if required_roles and not proxy_principal.has_any_role(required_roles):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient API role")
            return proxy_principal
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization: Bearer token is required",
            )
        if self._allowed_client_fingerprints and normalized_fingerprint not in self._allowed_client_fingerprints:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client certificate fingerprint is not allowed")
        roles = self._lookup_roles(token)
        if roles is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")
        principal = Principal(actor="api-token", roles=roles, client_fingerprint=normalized_fingerprint)
        if required_roles and not principal.has_any_role(required_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient API role")
        return principal

    def _authenticate_proxy(
        self,
        *,
        proxy_user: str | None,
        proxy_roles: str | None,
        proxy_issued_at: str | None,
        proxy_signature: str | None,
        client_fingerprint: str | None,
    ) -> Principal | None:
        if not self._trusted_proxy_secret:
            return None
        identity = verify_proxy_identity(
            secret=self._trusted_proxy_secret,
            user_id=proxy_user,
            roles=proxy_roles,
            issued_at=proxy_issued_at,
            signature=proxy_signature,
            client_fingerprint=client_fingerprint,
        )
        if identity is None:
            return None
        if self._allowed_client_fingerprints and identity.client_fingerprint not in self._allowed_client_fingerprints:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client certificate fingerprint is not allowed")
        return Principal(actor=f"sso:{identity.user_id}", roles=identity.roles, client_fingerprint=identity.client_fingerprint)

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
        x_govmesh_user: str | None = Header(default=None, alias="X-GovMesh-User"),
        x_govmesh_roles: str | None = Header(default=None, alias="X-GovMesh-Roles"),
        x_govmesh_issued_at: str | None = Header(default=None, alias="X-GovMesh-Issued-At"),
        x_govmesh_proxy_signature: str | None = Header(default=None, alias="X-GovMesh-Proxy-Signature"),
    ) -> Principal:
        token = credentials.credentials if credentials else None
        return policy.authenticate(
            token,
            required_roles,
            client_fingerprint=x_client_cert_sha256,
            proxy_user=x_govmesh_user,
            proxy_roles=x_govmesh_roles,
            proxy_issued_at=x_govmesh_issued_at,
            proxy_signature=x_govmesh_proxy_signature,
        )

    return dependency


def _normalize_fingerprint(value: str | None) -> str:
    return (value or "").replace(":", "").replace(" ", "").lower()


def _split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for chunk in value.split(";") for item in chunk.split(",") if item.strip()]
