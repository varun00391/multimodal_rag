from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.canonical import ElementType


ALLOWED_ELEMENT_TYPES = {item.value for item in ElementType}


class GeminiBBox(BaseModel):
    left: float
    top: float
    right: float
    bottom: float


class GeminiElement(BaseModel):
    type: str = ElementType.UNKNOWN.value
    text: str | None = None
    markdown: str | None = None
    html: str | None = None
    reading_order: int | None = None
    bbox: GeminiBBox | None = None
    confidence: float | None = None
    uncertain: bool = False

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> str:
        if not isinstance(value, str):
            return ElementType.UNKNOWN.value
        lowered = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "title": ElementType.HEADING.value,
            "header": ElementType.HEADER.value,
            "kv": ElementType.KEY_VALUE.value,
            "keyvalue": ElementType.KEY_VALUE.value,
            "form": ElementType.FORM_FIELD.value,
        }
        mapped = aliases.get(lowered, lowered)
        return mapped if mapped in ALLOWED_ELEMENT_TYPES else ElementType.UNKNOWN.value


class GeminiPageResult(BaseModel):
    page: int
    elements: list[GeminiElement] = Field(default_factory=list)


class GeminiExtractionPayload(BaseModel):
    pages: list[GeminiPageResult] = Field(default_factory=list)


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("Gemini returned an empty response.")
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Gemini response was not valid JSON.") from None
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Gemini JSON must be an object.")
    return value


def parse_gemini_payload(text: str) -> GeminiExtractionPayload:
    data = extract_json_object(text)
    if "pages" not in data and "elements" in data:
        data = {"pages": [{"page": data.get("page", 1), "elements": data.get("elements", [])}]}
    return GeminiExtractionPayload.model_validate(data)
