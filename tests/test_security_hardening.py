import os
import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("DIRECTAM_BASE_URL", "https://directam.example.com")
os.environ.setdefault("SERVICE_API_KEY", "test")

from app.api.deps import get_request_ip
from app.core.config import settings
from app.main import _validate_media_proxy_url


def _build_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    encoded_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": encoded_headers,
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_media_proxy_rejects_disallowed_redirect_target() -> None:
    with pytest.raises(HTTPException):
        _validate_media_proxy_url("https://evil.example/img.jpg", {"ghlbedovom.com"})


def test_media_proxy_accepts_allowed_subdomain() -> None:
    _validate_media_proxy_url("https://cdn.ghlbedovom.com/img.jpg", {"ghlbedovom.com"})


def test_request_ip_ignores_forwarded_by_default() -> None:
    previous = settings.TRUST_PROXY_HEADERS
    settings.TRUST_PROXY_HEADERS = False
    try:
        request = _build_request(
            headers={"x-forwarded-for": "1.1.1.1, 2.2.2.2"},
            client_host="127.0.0.1",
        )
        assert asyncio.run(get_request_ip(request)) == "127.0.0.1"
    finally:
        settings.TRUST_PROXY_HEADERS = previous


def test_request_ip_uses_forwarded_when_enabled() -> None:
    previous = settings.TRUST_PROXY_HEADERS
    settings.TRUST_PROXY_HEADERS = True
    try:
        request = _build_request(
            headers={"x-forwarded-for": "1.1.1.1, 2.2.2.2"},
            client_host="127.0.0.1",
        )
        assert asyncio.run(get_request_ip(request)) == "1.1.1.1"
    finally:
        settings.TRUST_PROXY_HEADERS = previous
