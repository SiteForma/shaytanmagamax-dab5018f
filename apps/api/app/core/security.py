from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from apps.api.app.core.config import Settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    algorithm, salt_b64, digest_b64 = password_hash.split("$", maxsplit=2)
    if algorithm != "scrypt":
        return False
    salt = base64.b64decode(salt_b64.encode())
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(base64.b64encode(digest).decode(), digest_b64)


def create_access_token(
    settings: Settings, subject: str, extra: dict[str, Any] | None = None
) -> str:
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_expires_minutes),
        "iat": datetime.now(tz=UTC),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
