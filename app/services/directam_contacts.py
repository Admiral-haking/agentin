from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class DirectamContactsClientError(Exception):
    pass


def _get_by_path(payload: Any, path: str | None) -> Any:
    if not path:
        return None
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list):
            try:
                idx = int(part)
            except ValueError:
                return None
            if idx < 0 or idx >= len(value):
                return None
            value = value[idx]
        else:
            return None
    return value


class DirectamContactsClient:
    def __init__(self) -> None:
        self.base_url = settings.DIRECTAM_BASE_URL.rstrip("/")
        self.path = settings.DIRECTAM_CONTACTS_PATH
        self.method = settings.DIRECTAM_CONTACTS_METHOD.upper()
        self.api_token = settings.SERVICE_API_KEY
        self.headers = {"api-key": self.api_token, "api_token": self.api_token}
        self.body = settings.DIRECTAM_CONTACTS_BODY
        self.data_path = settings.DIRECTAM_CONTACTS_DATA_PATH

    def _validate(self) -> None:
        if not self.base_url:
            raise DirectamContactsClientError("DIRECTAM_BASE_URL is not configured")
        if not self.api_token:
            raise DirectamContactsClientError("SERVICE_API_KEY is not configured")
        if not self.path:
            raise DirectamContactsClientError("DIRECTAM_CONTACTS_PATH is not configured")
        if self.method not in {"GET", "POST"}:
            raise DirectamContactsClientError("DIRECTAM_CONTACTS_METHOD must be GET or POST")

    def _parse_body(self) -> dict | None:
        if not self.body:
            return None
        try:
            data = json.loads(self.body)
        except json.JSONDecodeError as exc:
            raise DirectamContactsClientError(
                "DIRECTAM_CONTACTS_BODY must be valid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise DirectamContactsClientError(
                "DIRECTAM_CONTACTS_BODY must be a JSON object"
            )
        return data

    def _with_api_token(self, payload: dict | None) -> dict:
        data = dict(payload or {})
        data.setdefault("api_token", self.api_token)
        return data

    def _token_params(self) -> dict:
        return {"api_token": self.api_token}

    async def fetch_contacts(self) -> list[dict[str, Any]]:
        self._validate()
        url = f"{self.base_url}{self.path}"
        body = self._parse_body()
        params = self._token_params()

        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SEC) as client:
                if self.method == "GET":
                    response = await client.get(url, headers=self.headers, params=params)
                else:
                    payload = self._with_api_token(body)
                    response = await client.post(
                        url,
                        json=payload,
                        headers=self.headers,
                        params=params,
                    )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("errors", stage="contacts_api", path=self.path, error=str(exc))
            raise DirectamContactsClientError(f"Request failed: {exc}") from exc
        except ValueError as exc:
            logger.error("errors", stage="contacts_api", path=self.path, error=str(exc))
            raise DirectamContactsClientError("Invalid JSON response") from exc

        if isinstance(data, dict) and data.get("success") is False:
            raise DirectamContactsClientError(f"Request failed: {data}")

        items: Any = data
        if self.data_path:
            items = _get_by_path(data, self.data_path)

        if not isinstance(items, list):
            raise DirectamContactsClientError(
                "DIRECTAM_CONTACTS_DATA_PATH did not resolve to a list"
            )

        contacts: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                contacts.append(item)
        return contacts


def extract_contact_fields(contact: dict[str, Any]) -> tuple[str | None, str | None, str | None, int | None]:
    id_path = settings.DIRECTAM_CONTACTS_ID_FIELD
    username_path = settings.DIRECTAM_CONTACTS_USERNAME_FIELD
    follow_status_path = settings.DIRECTAM_CONTACTS_FOLLOW_STATUS_FIELD
    follower_count_path = settings.DIRECTAM_CONTACTS_FOLLOWER_COUNT_FIELD

    external_id = _get_by_path(contact, id_path)
    username = _get_by_path(contact, username_path) if username_path else None
    follow_status = _get_by_path(contact, follow_status_path) if follow_status_path else None
    follower_count = _get_by_path(contact, follower_count_path) if follower_count_path else None

    external_id = str(external_id) if external_id is not None else None
    username = str(username) if username is not None else None
    follow_status = str(follow_status) if follow_status is not None else None

    count_value = None
    if follower_count is not None:
        try:
            count_value = int(follower_count)
        except (TypeError, ValueError):
            count_value = None

    return external_id, username, follow_status, count_value
