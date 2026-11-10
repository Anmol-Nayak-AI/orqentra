import re
from dataclasses import dataclass
from time import time

import jwt
from clerk_backend_api.security import TokenVerificationError, VerifyTokenOptions, verify_token

from orqentra.core.config import Settings


class InvalidSession(Exception):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    session_id: str


def verify_session(token: str, settings: Settings) -> VerifiedIdentity:
    if not settings.auth_configured:
        raise RuntimeError("Clerk authentication is not configured.")
    if len(token) > 8192 or token.count(".") != 2:
        raise InvalidSession("Invalid session.")
    try:
        if jwt.get_unverified_header(token).get("alg") != "RS256":
            raise InvalidSession("Invalid session.")
        assert settings.clerk_jwt_key is not None
        claims = verify_token(
            token,
            VerifyTokenOptions(
                jwt_key=settings.clerk_jwt_key.get_secret_value().replace("\\n", "\n"),
                authorized_parties=settings.allowed_origins,
                audience=settings.clerk_audience,
                clock_skew_in_ms=0,
            ),
        )
        # SDK verifies signature/time/audience/azp, but does not validate issuer or require claims.
        if claims.get("iss") != settings.clerk_issuer:
            raise InvalidSession("Invalid session.")
        if any(type(claims.get(k)) is not int for k in ("exp", "iat", "nbf")):
            raise InvalidSession("Invalid session.")
        now = time()
        if not claims["nbf"] <= now < claims["exp"] or claims["iat"] > now:
            raise InvalidSession("Invalid session.")
        if claims["exp"] - claims["iat"] > settings.clerk_max_token_lifetime:
            raise InvalidSession("Invalid session.")
        subject, session = claims.get("sub"), claims.get("sid")
        if not isinstance(subject, str) or not re.fullmatch(r"user_[a-zA-Z0-9_]{1,200}", subject):
            raise InvalidSession("Invalid session.")
        if not isinstance(session, str) or not re.fullmatch(r"sess_[a-zA-Z0-9_]{1,200}", session):
            raise InvalidSession("Invalid session.")
        if claims.get("sts") == "pending" or claims.get("act") is not None:
            raise InvalidSession("Pending or impersonated sessions are not supported.")
        return VerifiedIdentity(subject, session)
    except (TokenVerificationError, jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise InvalidSession("Invalid session.") from None
