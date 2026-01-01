from __future__ import annotations

import structlog
import httpx

from app.core.config import settings

logger = structlog.get_logger(__name__)


class InstagramUserClientError(Exception):
    pass


class InstagramUserClient:
    def __init__(self) -> None:
        self.base_url = settings.DIRECTAM_BASE_URL.rstrip("/")
        self.api_token = settings.SERVICE_API_KEY
        self.headers = {"api-key": self.api_token, "api_token": self.api_token}

    async def get_username(self, user_id: str) -> str | None:
        data = await self._post("/instagram-user/username", {"user_id": user_id})
        return data.get("data", {}).get("username")

    async def get_follow_status(self, user_id: str) -> str | None:
        data = await self._post(
            "/instagram-user/follow-status", {"user_id": user_id}
        )
        payload = data.get("data")
        if not isinstance(payload, dict):
            return None
        is_follower = payload.get("is_follower")
        is_following = payload.get("is_following")
        if is_follower is None and is_following is None:
            return None

        def _normalize_bool(value: object) -> str | None:
            if isinstance(value, bool):
                return str(value).lower()
            if isinstance(value, (int, float)):
                return "true" if value != 0 else "false"
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "1", "yes"}:
                    return "true"
                if lowered in {"false", "0", "no"}:
                    return "false"
            return None

        parts = []
        follower_value = _normalize_bool(is_follower)
        if follower_value is not None:
            parts.append(f"is_follower={follower_value}")
        following_value = _normalize_bool(is_following)
        if following_value is not None:
            parts.append(f"is_following={following_value}")
        return ",".join(parts) if parts else None

    async def get_follow_count(self, user_id: str) -> int | None:
        data = await self._post(
            "/instagram-user/follow-count", {"user_id": user_id}
        )
        count = data.get("data", {}).get("follower_count")
        if count is None:
            return None
        try:
            return int(count)
        except (TypeError, ValueError):
            return None

    def _with_api_token(self, payload: dict) -> dict:
        if "api_token" in payload:
            return payload
        return {**payload, "api_token": self.api_token}

    async def _post(self, path: str, payload: dict) -> dict:
        if not self.base_url:
            raise InstagramUserClientError("DIRECTAM_BASE_URL is not configured")
        if not self.api_token:
            raise InstagramUserClientError("SERVICE_API_KEY is not configured")
        url = f"{self.base_url}{path}"
        payload = self._with_api_token(payload)
        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SEC) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise InstagramUserClientError("Invalid JSON response")
                if data.get("success") is not True:
                    raise InstagramUserClientError(f"Request failed: {data}")
                return data
        except httpx.HTTPError as exc:
            logger.error("errors", stage="user_api", path=path, error=str(exc))
            raise InstagramUserClientError(f"Request failed: {exc}") from exc
        except ValueError as exc:
            logger.error("errors", stage="user_api", path=path, error=str(exc))
            raise InstagramUserClientError("Invalid JSON response") from exc
