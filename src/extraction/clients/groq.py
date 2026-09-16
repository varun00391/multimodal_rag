from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from extraction.settings import Settings


@lru_cache(maxsize=1)
def groq_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))


def get_groq_client(settings: Settings) -> OpenAI | None:
    if not settings.groq_api_key:
        return None
    return groq_client(settings.groq_api_key, settings.groq_base_url)
