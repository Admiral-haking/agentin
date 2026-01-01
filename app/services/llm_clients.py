from __future__ import annotations

import structlog
import httpx

from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMError(Exception):
    pass


def _provider_config(provider: str) -> tuple[str, str | None, str]:
    if provider == "openai":
        return settings.OPENAI_BASE_URL, settings.OPENAI_API_KEY, settings.OPENAI_MODEL
    if provider == "deepseek":
        return (
            settings.DEEPSEEK_BASE_URL,
            settings.DEEPSEEK_API_KEY,
            settings.DEEPSEEK_MODEL,
        )
    raise LLMError(f"Unknown provider: {provider}")


async def generate_reply(
    provider: str,
    messages: list[dict[str, str]],
) -> tuple[str, dict]:
    base_url, api_key, model = _provider_config(provider)
    if not api_key:
        raise LLMError(f"Missing API key for provider: {provider}")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SEC) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LLMError(f"{provider} request failed: {exc}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise LLMError(f"{provider} returned no choices")

    content = choices[0].get("message", {}).get("content")
    if not content:
        raise LLMError(f"{provider} returned empty content")

    usage = data.get("usage") or {}
    return content, usage
