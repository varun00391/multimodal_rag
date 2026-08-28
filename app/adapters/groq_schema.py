from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.adapters.gemini_schema import extract_json_object
from app.models.canonical import ElementType

ALLOWED_VISUAL_TYPES = {
    ElementType.CHART.value,
    ElementType.DIAGRAM.value,
    ElementType.PICTURE.value,
}


class GroqVisualPayload(BaseModel):
    type: str = ElementType.CHART.value
    title: str | None = None
    description: str | None = None
    caption: str | None = None
    uncertain: bool = False

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> str:
        if not isinstance(value, str):
            return ElementType.CHART.value
        lowered = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "graph": ElementType.CHART.value,
            "plot": ElementType.CHART.value,
            "infographic": ElementType.DIAGRAM.value,
            "figure": ElementType.DIAGRAM.value,
            "image": ElementType.PICTURE.value,
            "photo": ElementType.PICTURE.value,
            "logo": ElementType.PICTURE.value,
        }
        mapped = aliases.get(lowered, lowered)
        return mapped if mapped in ALLOWED_VISUAL_TYPES else ElementType.CHART.value


def parse_groq_payload(text: str) -> GroqVisualPayload:
    data = extract_json_object(text)
    if "description" not in data and "text" in data:
        data["description"] = data.get("text")
    return GroqVisualPayload.model_validate(data)
