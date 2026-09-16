"""Standalone text extraction (blueprint Step 8).

    native PDF text
      → usable? accept
      → else OCR (PaddleOCR, else Tesseract)
      → else Euron VLM

Clean native text is never sent to OCR or the VLM.
"""

from __future__ import annotations

import string
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from image_utils import crop_region
from native_extractor import NativeObject
from ocr_engine import OCRError, OCR_MIN_CONFIDENCE, ocr_page_region
from pdf_profiler import PageProfile
from region_detector import Region
from region_router import TEXT_TYPES
from vlm_client import TEXT_PROMPT, VLMError, get_vlm_client

MIN_TEXT_CHARS = 1
GARBAGE_RATIO = 0.35


@dataclass
class ExtractedText:
    region_id: str
    page: int
    type: str
    text: str
    source: str
    status: str
    native_usable: bool
    engines: list[str] = field(default_factory=list)
    bbox: list[float] = field(default_factory=list)
    ocr_confidence: float | None = None
    ocr_engine: str | None = None
    vlm_model: str | None = None
    notes: list[str] = field(default_factory=list)


def extract_text_from_regions(
    regions: list[Region],
    native_objects: list[NativeObject],
    page_profile: PageProfile | None = None,
    page_image: str | Path | None = None,
    crops_dir: str | Path | None = None,
) -> list[ExtractedText]:
    results: list[ExtractedText] = []
    for region in regions:
        if region.type not in TEXT_TYPES:
            continue
        results.append(
            _extract_one(
                region,
                native_objects,
                page_image=page_image,
                crops_dir=Path(crops_dir) if crops_dir else None,
            )
        )
    return results


def extracted_text_to_dict(item: ExtractedText) -> dict[str, Any]:
    return asdict(item)


def count_text_status(items: list[ExtractedText]) -> dict[str, int]:
    return dict(Counter(item.status for item in items))


def native_text_is_usable(text: str, min_chars: int, garbage_ratio: float = GARBAGE_RATIO) -> bool:
    cleaned = _normalize(text)
    if len(cleaned) < min_chars:
        return False
    if _printable_ratio(cleaned) < (1.0 - garbage_ratio):
        return False
    return True


def _extract_one(
    region: Region,
    native_objects: list[NativeObject],
    page_image: str | Path | None,
    crops_dir: Path | None,
) -> ExtractedText:
    engines = list(region.engines)
    native_text = _native_text_for_region(region, native_objects)
    usable = native_text_is_usable(native_text, MIN_TEXT_CHARS)
    notes: list[str] = []
    crop_path = crops_dir / f"{region.id}.png" if crops_dir else None

    if usable:
        notes.append("accepted native text; skipped OCR and VLM")
        return ExtractedText(
            region_id=region.id,
            page=region.page,
            type=region.type,
            text=native_text,
            source="native_pdf",
            status="accepted_native",
            native_usable=True,
            engines=engines,
            bbox=list(region.bbox),
            notes=notes,
        )

    ocr_text = ""
    ocr_conf = None
    ocr_engine = None
    if page_image is None:
        notes.append("no page image for OCR")
    else:
        try:
            result = ocr_page_region(page_image, region.bbox, crop_path)
            ocr_text = result.text
            ocr_conf = result.average_confidence
            ocr_engine = result.engine
            notes.append(f"ocr engine={result.engine}")
        except OCRError as exc:
            notes.append(str(exc))

    if ocr_text and (ocr_conf is None or ocr_conf >= OCR_MIN_CONFIDENCE):
        if native_text_is_usable(ocr_text, MIN_TEXT_CHARS):
            return ExtractedText(
                region_id=region.id,
                page=region.page,
                type=region.type,
                text=_normalize(ocr_text),
                source="ocr",
                status="accepted_ocr",
                native_usable=False,
                engines=engines,
                bbox=list(region.bbox),
                ocr_confidence=ocr_conf,
                ocr_engine=ocr_engine,
                notes=notes,
            )
        notes.append("OCR text failed usability check")
    elif ocr_text:
        notes.append(f"OCR confidence too low ({ocr_conf})")

    vlm_text, vlm_model, vlm_note = _vlm_text(page_image, region.bbox, crop_path)
    if vlm_note:
        notes.append(vlm_note)
    if native_text_is_usable(vlm_text, MIN_TEXT_CHARS):
        return ExtractedText(
            region_id=region.id,
            page=region.page,
            type=region.type,
            text=_normalize(vlm_text),
            source="vlm",
            status="accepted_vlm",
            native_usable=False,
            engines=engines,
            bbox=list(region.bbox),
            ocr_confidence=ocr_conf,
            ocr_engine=ocr_engine,
            vlm_model=vlm_model,
            notes=notes,
        )

    return ExtractedText(
        region_id=region.id,
        page=region.page,
        type=region.type,
        text=_normalize(vlm_text or ocr_text or native_text),
        source="none",
        status="unreadable",
        native_usable=False,
        engines=engines,
        bbox=list(region.bbox),
        ocr_confidence=ocr_conf,
        ocr_engine=ocr_engine,
        vlm_model=vlm_model,
        notes=notes,
    )


def _vlm_text(
    page_image: str | Path | None,
    bbox: list[float],
    crop_path: Path | None,
) -> tuple[str, str | None, str]:
    if page_image is None:
        return "", None, "no page image for VLM"
    try:
        path = crop_path if crop_path and crop_path.is_file() else crop_region(page_image, bbox, crop_path)
        payload = get_vlm_client().analyze_image(path, TEXT_PROMPT)
        text = str(payload.get("text") or payload.get("value") or "").strip()
        model = str(payload.get("_model") or "")
        return text, model, f"vlm engine=euron:{model}"
    except VLMError as exc:
        return "", None, str(exc)


def _native_text_for_region(region: Region, native_objects: list[NativeObject]) -> str:
    by_id = {obj.id: obj for obj in native_objects}
    block_parts: list[str] = []
    other_parts: list[str] = []
    for object_id in region.native_object_ids:
        obj = by_id.get(object_id)
        if obj is None or not isinstance(obj.content, str):
            continue
        text = obj.content.strip()
        if not text:
            continue
        if obj.type == "block":
            block_parts.append(text)
        elif obj.type in {"line", "span", "text"}:
            other_parts.append(text)
    if block_parts:
        return _normalize("\n".join(block_parts))
    extra = str((region.extra or {}).get("text") or "").strip()
    if extra:
        return _normalize(extra)
    return _normalize(" ".join(other_parts))


def _normalize(value: str) -> str:
    return " ".join((value or "").split())


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    allowed = set(string.printable)
    good = sum(1 for char in text if char in allowed)
    return good / len(text)
