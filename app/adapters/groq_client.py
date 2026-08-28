from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from openai import AsyncOpenAI

from app.config import Settings


@dataclass(frozen=True)
class GroqCompletion:
    content: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class GroqCompleter(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_seconds: int,
    ) -> GroqCompletion:
        ...


class GroqVisionClient:
    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        if client is None and not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required to call Groq vision.")
        self._client = client or AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url.rstrip("/"),
            timeout=settings.groq_request_timeout_seconds,
        )

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        timeout_seconds: int,
    ) -> GroqCompletion:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=2048,
            response_format={"type": "json_object"},
            timeout=timeout_seconds,
        )
        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        content = choice.message.content or ""
        return GroqCompletion(
            content=content,
            model=getattr(response, "model", None) or model,
            finish_reason=getattr(choice, "finish_reason", None),
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
        )
