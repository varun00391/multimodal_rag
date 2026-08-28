from __future__ import annotations

PROMPT_VERSION = 1

SYSTEM_PROMPT = """You interpret a cropped PDF figure. Return JSON only:
{
  "type": "chart" | "diagram" | "picture",
  "title": "<visible title or null>",
  "description": "<grounded description of what is visible>",
  "caption": "<visible caption or null>",
  "uncertain": <boolean>
}

Rules:
- Describe only what is visible in the crop. Do not invent values, trends, or labels.
- Preserve exact numbers, units, and series names when they appear.
- If the crop is decorative, a logo, or unreadable, set type to picture, uncertain=true, and keep the description short.
- Do not include commentary outside JSON.
"""


def user_prompt(*, page: int, bbox: list[float], nearby_text: str, caption: str) -> str:
    nearby = nearby_text.strip() or "(none)"
    caption_text = caption.strip() or "(none)"
    return (
        f"Original page {page}. "
        f"Region bbox (PDF points, top-left origin): {bbox}. "
        f"Nearby page text: {nearby}. "
        f"Candidate caption: {caption_text}. "
        "Describe the cropped figure."
    )
