from __future__ import annotations

from pathlib import Path

from extraction.errors import ExtractionError

_OCR = None


def _load_ocr():
    global _OCR
    if _OCR is not None:
        return _OCR
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise ExtractionError(
            "OCR_UNAVAILABLE",
            "PaddleOCR is not installed. Install extraction-service[media].",
        ) from exc
    try:
        _OCR = PaddleOCR(lang="en", use_angle_cls=True)
    except TypeError:
        _OCR = PaddleOCR(lang="en")
    return _OCR


def ocr_image(path: Path) -> tuple[str, float | None]:
    engine = _load_ocr()
    result = None
    if hasattr(engine, "ocr"):
        result = engine.ocr(str(path))
    elif hasattr(engine, "predict"):
        result = engine.predict(str(path))
    else:
        raise ExtractionError("OCR_UNAVAILABLE", "Unsupported PaddleOCR API.")
    lines: list[str] = []
    scores: list[float] = []
    if not result:
        return "", None
    first = result[0] if isinstance(result, list) else result
    if first is None:
        return "", None
    if isinstance(first, dict):
        rec_texts = first.get("rec_texts") or first.get("text") or []
        rec_scores = first.get("rec_scores") or []
        if isinstance(rec_texts, str):
            rec_texts = [rec_texts]
        lines.extend(str(item) for item in rec_texts)
        scores.extend(float(item) for item in rec_scores if item is not None)
    else:
        for item in first:
            if not item:
                continue
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                payload = item[1]
                if isinstance(payload, (list, tuple)) and payload:
                    lines.append(str(payload[0]))
                    if len(payload) > 1:
                        try:
                            scores.append(float(payload[1]))
                        except (TypeError, ValueError):
                            pass
                else:
                    lines.append(str(payload))
    text = "\n".join(line.strip() for line in lines if str(line).strip())
    confidence = sum(scores) / len(scores) if scores else None
    return text, confidence
