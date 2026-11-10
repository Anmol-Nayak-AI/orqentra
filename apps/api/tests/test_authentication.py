from time import time

import jwt
import pytest
from auth_helpers import ISSUER, ORIGIN, OTHER, PUBLIC, token

from orqentra.auth.permissions import Role, permits
from orqentra.auth.verification import InvalidSession, verify_session
from orqentra.core.config import Settings


def configured(**overrides: object) -> Settings:
    values = {"clerk_issuer": ISSUER, "clerk_jwt_key": PUBLIC, "clerk_allowed_origins": ORIGIN}
    values.update(overrides)
    return Settings(**values)


def test_valid_official_sdk_session() -> None:
    assert verify_session(token(), configured()).subject == "user_fixture"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://untrusted.invalid"},
        {"exp": int(time()) - 60},
        {"nbf": int(time()) + 120},
        {"azp": "https://foreign.invalid"},
        {"sub": None},
        {"sid": None},
        {"iat": None},
        {"nbf": None},
        {"exp": None},
        {"iss": None},
        {"azp": None},
        {"sts": "pending"},
        {"act": {"sub": "user_other"}},
        {"sub": "machine_fake"},
    ],
)
def test_rejects_invalid_claims(claims: dict[str, object]) -> None:
    with pytest.raises(InvalidSession):
        verify_session(token(**claims), configured())


@pytest.mark.parametrize("raw", ["not.a.jwt", "", "m2m_fake", "x" * 8193])
def test_malformed_token(raw: str) -> None:
    with pytest.raises(InvalidSession):
        verify_session(raw, configured())


def test_invalid_signature() -> None:
    payload = jwt.decode(token(), options={"verify_signature": False})
    forged = jwt.encode(payload, OTHER, algorithm="RS256")
    with pytest.raises(InvalidSession):
        verify_session(forged, configured())


def test_algorithm_allowlist() -> None:
    raw = jwt.encode({"sub": "user_forged"}, "a" * 64, algorithm="HS256")
    with pytest.raises(InvalidSession):
        verify_session(raw, configured())


def test_audience() -> None:
    with pytest.raises(InvalidSession):
        verify_session(token(aud="wrong"), configured(clerk_audience="orqentra"))
    assert verify_session(token(aud="orqentra"), configured(clerk_audience="orqentra")).subject


@pytest.mark.parametrize(
    "role,permission,allowed",
    [
        (Role.OWNER, "organization.delete", True),
        (Role.ADMIN, "organization.delete", False),
        (Role.ADMIN, "agent.publish", True),
        (Role.MEMBER, "agent.publish", False),
        (Role.MEMBER, "agent.create", True),
        (Role.VIEWER, "agent.update", False),
        (Role.VIEWER, "workspace.read", True),
        (Role.OWNER, "not_a_permission", False),
    ],
)
def test_explicit_permissions(role: Role, permission: str, allowed: bool) -> None:
    assert permits(role, permission) is allowed


def test_escaped_public_pem_configuration() -> None:
    assert verify_session(token(), configured(clerk_jwt_key=PUBLIC.replace("\n", "\\n"))).subject


@pytest.mark.parametrize(
    "values",
    [
        {"clerk_issuer": ISSUER},
        {"clerk_allowed_origins": "*"},
        {"clerk_issuer": ISSUER + "/path"},
        {"clerk_jwt_key": "not a public key"},
        {"clerk_allowed_origins": ORIGIN + "/path"},
    ],
)
def test_invalid_configuration(values: dict[str, object]) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        if len(values) == 1 and values.get("clerk_issuer") == ISSUER:
            Settings(**values)
        else:
            configured(**values)
