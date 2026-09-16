"""Euron VLM client (always on).

OpenAI-compatible chat completions at:

    POST {EURI_BASE_URL}/chat/completions

Default vision model: gemini-2.5-flash
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from settings import load_settings

TEXT_PROMPT = """
Extract the visible text from this document region.
Return JSON only:
{"text": string, "notes": string or null}
Use only what is visible. Do not invent text.
""".strip()

CHART_PROMPT = """
You are extracting structured data from a chart image.
Return JSON only with this shape:
{
  "title": string or null,
  "x_axis": string or null,
  "y_axis": string or null,
  "units": string or null,
  "legend": [string],
  "series": [{"name": string, "values": [number or string]}],
  "data_labels": [string],
  "visible_values": [string],
  "trend": string or null,
  "caption": string or null
}
Do not invent values that are not visible. If a field is unknown, use null or [].
""".strip()

DIAGRAM_PROMPT = """
You are extracting a diagram/flowchart from an image.
Return JSON only with this shape:
{
  "nodes": [{"id": string, "label": string}],
  "edges": [{"from": string, "to": string, "label": string}],
  "groups": [string],
  "caption": string or null
}
Preserve visible labels. Do not invent nodes that are not shown.
""".strip()

REGION_PROMPT = """
Extract the visible content of this document region.
Return JSON only:
{
  "type": "heading|paragraph|list|table|image|chart|diagram|form|other",
  "text": string,
  "tables": [{"headers": [string], "rows": [[string]]}],
  "notes": string or null
}
Use only what is visible.
""".strip()

PROMPT_BY_TYPE = {
    "chart": CHART_PROMPT,
    "diagram": DIAGRAM_PROMPT,
    "figure": REGION_PROMPT,
    "image": REGION_PROMPT,
    "table": REGION_PROMPT,
    "complex_table": REGION_PROMPT,
}


class VLMError(RuntimeError):
    pass


class EuronVLMClient:
    def __init__(self):
        settings = load_settings()
        self.api_key = settings["euri_api_key"]
        self.base_url = settings["euri_base_url"]
        self.model = settings["euri_vlm_model"]
        self.timeout = 60.0
        self.max_tokens = 2048
        self._disabled_reason: str | None = None

    def analyze_image(self, image_path: str | Path, prompt: str) -> dict[str, Any]:
        if self._disabled_reason:
            raise VLMError(self._disabled_reason)
        path = Path(image_path)
        if not path.is_file():
            raise VLMError(f"Image not found for VLM: {path}")
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise VLMError("Euron VLM request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:400]
            if exc.response.status_code in {401, 403}:
                self._disabled_reason = (
                    "Euron API key is invalid or inactive. "
                    "Update EURI_API_KEY and rerun."
                )
                raise VLMError(self._disabled_reason) from exc
            raise VLMError(f"Euron VLM HTTP {exc.response.status_code}: {body}") from exc
        except Exception as exc:
            raise VLMError(f"Euron VLM failed: {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise VLMError(f"Unexpected Euron VLM response: {data!r}") from exc
        parsed = _parse_json(text if isinstance(text, str) else json.dumps(text))
        parsed["_model"] = self.model
        parsed["_provider"] = "euron"
        return parsed


_CLIENT: EuronVLMClient | None = None


def get_vlm_client() -> EuronVLMClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = EuronVLMClient()
    return _CLIENT


def prompt_for_region_type(region_type: str) -> str:
    return PROMPT_BY_TYPE.get(region_type, TEXT_PROMPT)


def _parse_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"text": raw}
