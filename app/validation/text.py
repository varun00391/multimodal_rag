from __future__ import annotations

from collections import Counter

from app.inspection.features import (
    duplicate_line_ratio,
    printable_ratio,
    replacement_ratio,
)
from app.models.canonical import CanonicalPage
from app.models.inspection import PageInspection
from app.models.validation import ValidationFailure

MIN_USEFUL_CHARACTERS = 20
MIN_PRINTABLE_RATIO = 0.90
MAX_REPLACEMENT_RATIO = 0.02
MAX_DUPLICATE_LINE_RATIO = 0.40
MAX_REPEATED_SYMBOL_RATIO = 0.45
OCR_MIN_CHARACTERS = 20


def repeated_symbol_ratio(text: str) -> float:
    compact = "".join(text.split())
    if len(compact) < 8:
        return 0.0
    counts = Counter(compact)
    return max(counts.values()) / len(compact)


def page_text(page: CanonicalPage) -> str:
    return "\n".join(element.text.strip() for element in page.elements if element.text)


def validate_text(page: CanonicalPage, inspection: PageInspection | None) -> list[ValidationFailure]:
    if any(error.code == "SCANNED_PAGE_NOT_EXTRACTED" for error in page.errors):
        return []

    failures: list[ValidationFailure] = []
    text = page_text(page)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    native_expected = bool(
        inspection
        and not inspection.probable_scan
        and inspection.text.character_count >= 80
    )
    ocr_route = page.primary_route in {"gemini", "docling"} and bool(
        inspection and inspection.probable_scan
    )

    if native_expected and len(text) < MIN_USEFUL_CHARACTERS:
        failures.append(
            ValidationFailure(
                code="NATIVE_TEXT_MISSING",
                message="Native text was expected but the extracted text is missing or too short.",
                details={"character_count": len(text)},
            )
        )
    elif ocr_route and len(text) < OCR_MIN_CHARACTERS:
        failures.append(
            ValidationFailure(
                code="OCR_TOO_SHORT",
                message="OCR output is suspiciously shorter than a scanned page should produce.",
                details={"character_count": len(text)},
            )
        )

    if not text:
        return failures

    printable = printable_ratio(text)
    replacement = replacement_ratio(text)
    if native_expected and (printable < 0.80 or replacement > 0.05):
        failures.append(
            ValidationFailure(
                code="NATIVE_TEXT_CORRUPT",
                message="Extracted native text looks corrupt or unprintable.",
                details={"printable_ratio": round(printable, 4), "replacement_ratio": round(replacement, 4)},
            )
        )
    elif printable < MIN_PRINTABLE_RATIO:
        failures.append(
            ValidationFailure(
                code="PRINTABLE_RATIO_LOW",
                message="Extracted text has a low printable-character ratio.",
                details={"printable_ratio": round(printable, 4)},
            )
        )
    if replacement > MAX_REPLACEMENT_RATIO and "NATIVE_TEXT_CORRUPT" not in {item.code for item in failures}:
        failures.append(
            ValidationFailure(
                code="REPLACEMENT_RATIO_HIGH",
                message="Extracted text contains many replacement characters.",
                details={"replacement_ratio": round(replacement, 4)},
            )
        )

    dup_ratio = duplicate_line_ratio(lines)
    if dup_ratio > MAX_DUPLICATE_LINE_RATIO:
        failures.append(
            ValidationFailure(
                code="DUPLICATE_LINES",
                message="Extracted text repeats the same lines excessively.",
                details={"duplicate_line_ratio": round(dup_ratio, 4)},
            )
        )

    symbol_ratio = repeated_symbol_ratio(text)
    if symbol_ratio > MAX_REPEATED_SYMBOL_RATIO:
        failures.append(
            ValidationFailure(
                code="REPEATED_SYMBOLS",
                message="Extracted text is dominated by a repeated symbol.",
                details={"repeated_symbol_ratio": round(symbol_ratio, 4)},
            )
        )
    return failures
