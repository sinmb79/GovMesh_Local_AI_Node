import time

from packages.govmesh_identity import sign_proxy_identity, verify_proxy_identity


def test_signed_proxy_identity_round_trips() -> None:
    issued_at = int(time.time())
    signature = sign_proxy_identity(
        secret="proxy-secret",
        user_id="user-1",
        roles={"operator", "auditor"},
        issued_at=issued_at,
        client_fingerprint="AA:BB",
    )

    identity = verify_proxy_identity(
        secret="proxy-secret",
        user_id="user-1",
        roles="auditor,operator",
        issued_at=issued_at,
        signature=signature,
        client_fingerprint="aa bb",
        now=issued_at,
    )

    assert identity is not None
    assert identity.user_id == "user-1"
    assert identity.roles == {"auditor", "operator"}
    assert identity.client_fingerprint == "aabb"


def test_signed_proxy_identity_rejects_tampering() -> None:
    issued_at = int(time.time())
    signature = sign_proxy_identity(secret="proxy-secret", user_id="user-1", roles={"operator"}, issued_at=issued_at)

    identity = verify_proxy_identity(
        secret="proxy-secret",
        user_id="user-1",
        roles="approver",
        issued_at=issued_at,
        signature=signature,
        now=issued_at,
    )

    assert identity is None
