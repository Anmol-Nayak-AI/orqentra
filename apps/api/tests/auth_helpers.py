from time import time
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://unit-test.clerk.invalid"
ORIGIN = "http://127.0.0.1:8080"
PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC = (
    PRIVATE.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(subject: str = "user_fixture", **changes: Any) -> str:
    now = int(time())
    claims: dict[str, Any] = {
        "sub": subject,
        "sid": "sess_fixture",
        "iss": ISSUER,
        "azp": ORIGIN,
        "iat": now,
        "nbf": now - 1,
        "exp": now + 60,
    }
    claims.update(changes)
    for key in [k for k, v in claims.items() if v is None]:
        del claims[key]
    return jwt.encode(claims, PRIVATE, algorithm="RS256", headers={"kid": "fixture"})
