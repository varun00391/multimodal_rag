from __future__ import annotations

from app.models.canonical import ElementType

PROMPT_VERSION = 1

_ELEMENT_TYPES = ", ".join(item.value for item in ElementType)

SYSTEM_PROMPT = f"""You extract structured content from PDF page images.

Return JSON only with this schema:
{{
  "pages": [
    {{
      "page": <original page number>,
      "elements": [
        {{
          "type": "<one of: {_ELEMENT_TYPES}>",
          "text": "<exact visible text or null>",
          "markdown": "<optional markdown, required for tables>",
          "html": "<optional html, useful for tables>",
          "reading_order": <1-based integer>,
          "bbox": {{"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0}},
          "confidence": <0.0-1.0>,
          "uncertain": <boolean>
        }}
      ]
    }}
  ]
}}

Rules:
- Extract; do not summarize, paraphrase, or invent missing text.
- Preserve exact numbers, units, punctuation, and reading order.
- Bounding boxes are fractions of the page (0-1) with origin at the top-left.
- Return a separate page object for every original page number you were given.
- Represent tables as structured markdown (and html when possible).
- If text is unreadable, set uncertain=true and do not guess.
- Do not include commentary outside JSON.
"""


def user_prompt(page_numbers: list[int]) -> str:
    labeled = ", ".join(str(page) for page in page_numbers)
    return (
        "Extract every labeled page image. "
        f"Original page numbers in order: [{labeled}]. "
        "Each image is labeled with its original page number. "
        "Return one pages[] entry per original page."
    )
