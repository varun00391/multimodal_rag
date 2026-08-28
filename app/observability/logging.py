from __future__ import annotations

import json
import logging
from typing import Any

REDACTED_KEYS = {
    "text",
    "markdown",
    "html",
    "content",
    "prompt",
    "messages",
    "page_text",
}


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {"event": event, **_sanitize(fields)}
    logger.info("%s", json.dumps(payload, default=str, ensure_ascii=True))


def _sanitize(fields: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if key.lower() in REDACTED_KEYS:
            continue
        cleaned[key] = value
    return cleaned


def configure_json_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_extraction_json_configured", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    if not root.handlers:
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    root._extraction_json_configured = True  # type: ignore[attr-defined]
