from __future__ import annotations

import re

from app.extractors.base import ExtractionEvidence
from app.profiling.pdf_profiler import printable_ratio
from app.validation.reconciliation import reconcile_text_values

_WS_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _WS_RE.sub(" ", (value or "").strip())


def native_text_is_usable(text: str, min_chars: int, garbage_ratio: float) -> bool:
    cleaned = normalize_text(text)
    if len(cleaned) < min_chars:
        return False
    if printable_ratio(cleaned) < (1.0 - garbage_ratio):
        return False
    return True


def reconcile_text_evidence(evidences: list[ExtractionEvidence]) -> dict:
    items = []
    for evidence in evidences:
        if not evidence or not evidence.text:
            continue
        items.append(
            {
                "value": normalize_text(evidence.text),
                "source": evidence.engine,
                "confidence": evidence.confidence,
            }
        )
    return reconcile_text_values(items)
