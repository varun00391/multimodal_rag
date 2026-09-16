"""Runtime settings for extraction_testing.

Loads Euron credentials from extraction_testing/.env, then the repo .env.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
try:
    REPO_ROOT = HERE.parents[1]
except IndexError:
    REPO_ROOT = HERE.parent

DEFAULT_EURI_BASE_URL = "https://api.euron.one/api/v1/euri"
DEFAULT_EURI_VLM_MODEL = "gemini-2.5-flash"

_SETTINGS: dict[str, str] | None = None


def load_settings() -> dict[str, str]:
    global _SETTINGS
    if _SETTINGS is not None:
        return _SETTINGS
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(HERE.parent / ".env")
    load_dotenv(HERE / ".env", override=True)
    api_key = os.getenv("EURI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "EURI_API_KEY is required for the Euron VLM. "
            "Set it in the repo .env or extraction_testing/.env."
        )
    _SETTINGS = {
        "euri_api_key": api_key,
        "euri_base_url": os.getenv("EURI_BASE_URL", DEFAULT_EURI_BASE_URL).rstrip("/"),
        "euri_vlm_model": os.getenv("EURI_VLM_MODEL", DEFAULT_EURI_VLM_MODEL).strip(),
        "ocr_languages": os.getenv("OCR_LANGUAGES", "eng").strip() or "eng",
        "paddle_ocr_lang": os.getenv("PADDLE_OCR_LANG", "en").strip() or "en",
        "tesseract_cmd": os.getenv("TESSERACT_CMD", "tesseract").strip() or "tesseract",
    }
    return _SETTINGS
