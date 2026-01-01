from __future__ import annotations

import structlog
import httpx

from app.core.config import settings
from app.schemas.send import Button, QuickReplyOption, TemplateElement

logger = structlog.get_logger(__name__)


class SenderError(Exception):
    pass


class Sender:
    def __init__(self) -> None:
        self.base_url = settings.DIRECTAM_BASE_URL.rstrip("/")
        self.api_token = settings.SERVICE_API_KEY
        self.headers = {"api-key": self.api_token, "api_token": self.api_token}

    async def send_text(self, receiver_id: str, text: str) -> dict:
        return await self._post(
            "/send/text",
            {"receiver_id": receiver_id, "text": text},
        )

    async def send_button_text(
        self, receiver_id: str, text: str, buttons: list[Button]
    ) -> dict:
        payload = {
            "receiver_id": receiver_id,
            "text": text,
            "buttons": [button.model_dump(exclude_none=True) for button in buttons],
        }
        return await self._post("/send/button-text", payload)

    async def send_quick_reply(
        self, receiver_id: str, text: str, quick_replies: list[QuickReplyOption]
    ) -> dict:
        payload = {
            "receiver_id": receiver_id,
            "text": text,
            "quick_replies": [
                reply.model_dump(exclude_none=True) for reply in quick_replies
            ],
        }
        return await self._post("/send/quick-reply", payload)

    async def send_generic_template(
        self, receiver_id: str, elements: list[TemplateElement]
    ) -> dict:
        payload = {
            "receiver_id": receiver_id,
            "elements": [element.model_dump(exclude_none=True) for element in elements],
        }
        return await self._post("/send/generic-template", payload)

    async def send_photo(self, receiver_id: str, image_url: str) -> dict:
        return await self._post(
            "/send/photo",
            {"receiver_id": receiver_id, "image_url": image_url},
        )

    async def send_video(self, receiver_id: str, video_url: str) -> dict:
        return await self._post(
            "/send/video",
            {"receiver_id": receiver_id, "video_url": video_url},
        )

    async def send_audio(self, receiver_id: str, audio_url: str) -> dict:
        return await self._post(
            "/send/audio",
            {"receiver_id": receiver_id, "audio_url": audio_url},
        )

    def _with_api_token(self, payload: dict) -> dict:
        if "api_token" in payload:
            return payload
        return {**payload, "api_token": self.api_token}

    async def _post(self, path: str, payload: dict) -> dict:
        if not self.base_url:
            raise SenderError("DIRECTAM_BASE_URL is not configured")
        if not self.api_token:
            raise SenderError("SERVICE_API_KEY is not configured")
        url = f"{self.base_url}{path}"
        payload = self._with_api_token(payload)
        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SEC) as client:
                response = await client.post(url, json=payload, headers=self.headers)
        except httpx.HTTPError as exc:
            logger.error("errors", stage="send_http", path=path, error=str(exc))
            raise SenderError(f"Send failed: {exc}") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = response.text
            logger.error(
                "errors",
                stage="send_http",
                path=path,
                status_code=response.status_code,
                response=body,
            )
            raise SenderError(f"Send failed: {response.status_code} {body}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            logger.error(
                "errors",
                stage="send_http",
                path=path,
                status_code=response.status_code,
                response=response.text,
            )
            raise SenderError("Send failed: invalid JSON response") from exc

        if not isinstance(data, dict) or data.get("success") is not True:
            raise SenderError(f"Send failed: {data}")

        return data
