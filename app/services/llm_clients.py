from __future__ import annotations

import structlog
import httpx

from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMError(Exception):
    pass


def _truncate_content(content: str, limit: int) -> str:
    if limit <= 0 or len(content) <= limit:
        return content
    return content[:limit].rstrip()


def trim_messages(
    messages: list[dict[str, str]],
    max_total_chars: int,
    max_message_chars: int,
) -> list[dict[str, str]]:
    if max_total_chars <= 0 and max_message_chars <= 0:
        return messages

    trimmed: list[dict[str, str]] = []
    total = 0
    idx = 0
    while idx < len(messages) and messages[idx].get("role") == "system":
        content = str(messages[idx].get("content", ""))
        content = _truncate_content(content, max_message_chars)
        trimmed.append({**messages[idx], "content": content})
        total += len(content)
        idx += 1

    tail_source = messages[idx:]
    if tail_source:
        last_msg = tail_source[-1]
        content = str(last_msg.get("content", ""))
        content = _truncate_content(content, max_message_chars)
        trimmed_tail = [{**last_msg, "content": content}]
        total += len(content)
        for msg in reversed(tail_source[:-1]):
            content = str(msg.get("content", ""))
            content = _truncate_content(content, max_message_chars)
            if max_total_chars > 0 and total + len(content) > max_total_chars:
                continue
            trimmed_tail.append({**msg, "content": content})
            total += len(content)
        trimmed_tail.reverse()
        trimmed.extend(trimmed_tail)

    return trimmed


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

    messages = trim_messages(
        messages,
        settings.LLM_MAX_PROMPT_CHARS,
        settings.LLM_MESSAGE_MAX_CHARS,
    )
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": settings.LLM_TEMPERATURE,
    }
    if settings.LLM_MAX_TOKENS > 0:
        payload["max_tokens"] = settings.LLM_MAX_TOKENS
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SEC) as client:
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
