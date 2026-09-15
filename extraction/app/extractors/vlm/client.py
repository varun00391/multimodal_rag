from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.exceptions import VLMTimeoutError
from app.core.logging import get_logger

logger = get_logger(__name__)


class VLMClient:
    def __init__(self):
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self.settings.vlm_enabled)

    def analyze_image(self, image_path: Path, prompt: str) -> dict | None:
        if not self.enabled:
            return None
        provider = self.settings.vlm_provider.lower()
        try:
            if provider in {"openai", "azure_openai", "openai_compatible"}:
                return self._openai_compatible(image_path, prompt)
            if provider == "anthropic":
                return self._anthropic(image_path, prompt)
            logger.warning("Unknown VLM provider %s", provider)
            return None
        except httpx.TimeoutException as exc:
            raise VLMTimeoutError("VLM request timed out.") from exc
        except Exception:
            logger.exception("VLM analysis failed")
            return None

    def _encode_image(self, image_path: Path) -> tuple[str, str]:
        mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return mime, b64

    def _parse_json(self, text: str) -> dict:
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

    def _openai_compatible(self, image_path: Path, prompt: str) -> dict:
        mime, b64 = self._encode_image(image_path)
        settings = self.settings
        if settings.vlm_provider.lower() == "azure_openai":
            url = (
                f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments/"
                f"{settings.azure_openai_deployment}/chat/completions"
                f"?api-version={settings.azure_openai_api_version}"
            )
            headers = {"api-key": settings.vlm_api_key or settings.azure_openai_endpoint}
            if settings.vlm_api_key:
                headers = {"api-key": settings.vlm_api_key}
            model = settings.azure_openai_deployment or settings.vlm_model
        else:
            url = f"{settings.vlm_base_url.rstrip('/')}/chat/completions"
            headers = {"Authorization": f"Bearer {settings.vlm_api_key}"}
            model = settings.vlm_model
        payload = {
            "model": model,
            "max_tokens": settings.vlm_max_tokens,
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
        with httpx.Client(timeout=settings.vlm_timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        text = data["choices"][0]["message"]["content"]
        return self._parse_json(text)

    def _anthropic(self, image_path: Path, prompt: str) -> dict:
        mime, b64 = self._encode_image(image_path)
        settings = self.settings
        api_key = settings.anthropic_api_key or settings.vlm_api_key
        payload = {
            "model": settings.anthropic_model,
            "max_tokens": settings.vlm_max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64,
                            },
                        },
                    ],
                }
            ],
        }
        with httpx.Client(timeout=settings.vlm_timeout_seconds) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
        return self._parse_json(text)
