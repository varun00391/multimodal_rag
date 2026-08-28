from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from openai import AsyncOpenAI

from app.config import Settings


@dataclass(frozen=True)
class GeminiCompletion:
    content: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class GeminiCompleter(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_seconds: int,
    ) -> GeminiCompletion:
        ...


def message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif hasattr(item, "text") and item.text:
                parts.append(str(item.text))
        return "".join(parts)
    return str(content)


class EuronGeminiClient:
    """OpenAI-compatible Gemini client backed by Euron's EURI gateway."""

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        if client is None and not settings.euri_api_key:
            raise ValueError("EURI_API_KEY is required to call Gemini through Euron.")
        self._client = client or AsyncOpenAI(
            api_key=settings.euri_api_key,
            base_url=settings.euri_base_url.rstrip("/"),
            timeout=settings.gemini_request_timeout_seconds,
        )

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_seconds: int,
    ) -> GeminiCompletion:
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=8192,
                response_format={"type": "json_object"},
                timeout=timeout_seconds,
            )
        except Exception:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=8192,
                timeout=timeout_seconds,
            )
        choice = response.choices[0]
        usage = response.usage
        return GeminiCompletion(
            content=message_text(choice.message.content),
            model=response.model or model,
            finish_reason=choice.finish_reason,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
        )
