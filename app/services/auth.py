from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.utils.time import utc_now

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthError(Exception):
    pass


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def _token_payload(subject: str, role: str, expires_delta: timedelta) -> dict:
    expire = utc_now() + expires_delta
    return {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iat": utc_now(),
    }


def create_access_token(subject: str, role: str) -> str:
    payload = _token_payload(
        subject,
        role,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthError("Invalid token") from exc


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
