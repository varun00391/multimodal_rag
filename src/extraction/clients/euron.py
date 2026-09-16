from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from openai import OpenAI

from extraction.models.report import ExtractionReport, ModelCall
from extraction.settings import Settings


@lru_cache(maxsize=1)
def _client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))


def describe_image(settings: Settings, path: Path, report: ExtractionReport, purpose: str) -> str | None:
    if not settings.euri_api_key:
        report.model_calls.append(
            ModelCall(
                provider="euron",
                model=settings.euri_vlm_model,
                purpose=purpose,
                skipped=True,
                reason="EURI_API_KEY is not set",
            )
        )
        return None
    import base64
    import mimetypes

    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{encoded}"
    client = _client(settings.euri_api_key, settings.euri_base_url)
    response = client.chat.completions.create(
        model=settings.euri_vlm_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this image for document retrieval. "
                            "Focus on visible text, charts, diagrams, and objects. "
                            "Be concise and factual."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.1,
    )
    text = (response.choices[0].message.content or "").strip()
    tokens = response.usage.total_tokens if response.usage else None
    report.model_calls.append(
        ModelCall(
            provider="euron",
            model=settings.euri_vlm_model,
            purpose=purpose,
            tokens=tokens,
            skipped=False,
        )
    )
    return text or None
