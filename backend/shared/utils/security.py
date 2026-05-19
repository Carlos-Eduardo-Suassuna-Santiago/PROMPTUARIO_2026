"""
JWT utilities shared across all microservices.
Services verify tokens but do NOT issue them (only IAM does).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    sub: str          # user_id
    exp: int
    iat: int
    type: str         # "access" | "refresh"
    role: str | None = None         # ADMIN | DOCTOR | ATTENDANT | PATIENT (only in access tokens)
    email: str | None = None        # only in access tokens


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte input limit; truncate UTF-8 bytes to avoid ValueError.
    if not isinstance(password, str):
        password = str(password)
    pw_bytes = password.encode("utf-8")[:72]
    pw_trunc = pw_bytes.decode("utf-8", errors="ignore")
    return pwd_context.hash(pw_trunc)


def verify_password(plain: str, hashed: str) -> bool:
    if not isinstance(plain, str):
        plain = str(plain)
    pw_bytes = plain.encode("utf-8")[:72]
    pw_trunc = pw_bytes.decode("utf-8", errors="ignore")
    return pwd_context.verify(pw_trunc, hashed)


def create_access_token(
    user_id: str,
    role: str,
    email: str,
    secret: str,
    algorithm: str,
    expire_minutes: int = 30,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_refresh_token(
    user_id: str,
    secret: str,
    algorithm: str,
    expire_days: int = 7,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=expire_days)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithm: str) -> TokenPayload:
    try:
        normalized = token.strip()
        # Be tolerant with client formatting mistakes (e.g. quoted token or duplicated Bearer).
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()
        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {'"', "'"}
        ):
            normalized = normalized[1:-1].strip()

        raw = jwt.decode(normalized, secret, algorithms=[algorithm])
        return TokenPayload(**raw)
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
