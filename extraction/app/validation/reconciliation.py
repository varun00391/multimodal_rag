from __future__ import annotations

import re

from app.models.common import ValidationStatus
from app.models.validation import EvidenceCandidate

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w]+", re.UNICODE)


def normalize_value(value: str) -> str:
    text = _WS.sub(" ", (value or "").strip().lower())
    return _PUNCT.sub("", text)


def reconcile_text_values(items: list[dict]) -> dict:
    grouped: dict[str, EvidenceCandidate] = {}
    for item in items:
        value = str(item.get("value") or "").strip()
        if not value:
            continue
        key = normalize_value(value)
        source = str(item.get("source") or "unknown")
        if key not in grouped:
            grouped[key] = EvidenceCandidate(
                value=value,
                sources=[source],
                confidence=item.get("confidence"),
            )
        else:
            if source not in grouped[key].sources:
                grouped[key].sources.append(source)
            conf = item.get("confidence")
            if conf is not None:
                existing = grouped[key].confidence
                grouped[key].confidence = max(conf, existing or 0)
    candidates = sorted(
        grouped.values(),
        key=lambda c: (len(c.sources), c.confidence or 0),
        reverse=True,
    )
    if not candidates:
        return {
            "status": ValidationStatus.UNREADABLE.value,
            "value": "",
            "sources": [],
            "candidates": [],
        }
    if len(candidates) == 1 or (
        len(candidates) > 1
        and normalize_value(candidates[0].value) == normalize_value(candidates[1].value)
    ):
        winner = candidates[0]
        status = (
            ValidationStatus.AGREED.value
            if len(winner.sources) > 1
            else ValidationStatus.VERIFIED.value
        )
        return {
            "status": status,
            "value": winner.value,
            "sources": winner.sources,
            "candidates": [c.model_dump() for c in candidates],
        }
    return {
        "status": ValidationStatus.CONFLICT.value,
        "value": candidates[0].value,
        "sources": candidates[0].sources,
        "candidates": [c.model_dump() for c in candidates],
    }
