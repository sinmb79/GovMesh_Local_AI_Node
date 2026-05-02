"""Signed trusted-proxy identity headers.

GovMesh does not terminate institution SSO directly in the MVP. A gateway can
terminate SSO/mTLS and forward a compact identity assertion signed with a local
shared secret. Unsigned user/role headers are intentionally not trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import time
from typing import Iterable


MAX_CLOCK_SKEW_SECONDS = 300


@dataclass(frozen=True)
class ProxyIdentity:
    user_id: str
    roles: frozenset[str]
    issued_at: int
    client_fingerprint: str | None = None


def sign_proxy_identity(
    *,
    secret: str | bytes,
    user_id: str,
    roles: Iterable[str],
    issued_at: int | None = None,
    client_fingerprint: str | None = None,
) -> str:
    key = _key(secret)
    timestamp = int(issued_at if issued_at is not None else time.time())
    message = _message(user_id=user_id, roles=roles, issued_at=timestamp, client_fingerprint=client_fingerprint)
    return hmac.digest(key, message.encode("utf-8"), "sha256").hex()


def verify_proxy_identity(
    *,
    secret: str | bytes,
    user_id: str | None,
    roles: str | Iterable[str] | None,
    issued_at: str | int | None,
    signature: str | None,
    client_fingerprint: str | None = None,
    now: int | None = None,
) -> ProxyIdentity | None:
    if not user_id or roles is None or issued_at is None or not signature:
        return None
    try:
        timestamp = int(issued_at)
    except (TypeError, ValueError):
        return None
    current = int(now if now is not None else time.time())
    if abs(current - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        return None
    role_items = _roles(roles)
    expected = sign_proxy_identity(
        secret=secret,
        user_id=user_id,
        roles=role_items,
        issued_at=timestamp,
        client_fingerprint=client_fingerprint,
    )
    if not hmac.compare_digest(expected, signature):
        return None
    return ProxyIdentity(
        user_id=user_id,
        roles=frozenset(role_items),
        issued_at=timestamp,
        client_fingerprint=_normalize_fingerprint(client_fingerprint) if client_fingerprint else None,
    )


def _message(
    *,
    user_id: str,
    roles: Iterable[str],
    issued_at: int,
    client_fingerprint: str | None,
) -> str:
    normalized_roles = ",".join(sorted(_roles(roles)))
    fingerprint = _normalize_fingerprint(client_fingerprint) if client_fingerprint else ""
    return f"{user_id}\n{normalized_roles}\n{issued_at}\n{fingerprint}"


def _roles(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        items = [item.strip() for item in value.replace(";", ",").split(",")]
    else:
        items = [str(item).strip() for item in value]
    return sorted({item for item in items if item})


def _normalize_fingerprint(value: str) -> str:
    return value.replace(":", "").replace(" ", "").lower()


def _key(secret: str | bytes) -> bytes:
    return secret.encode("utf-8") if isinstance(secret, str) else secret
