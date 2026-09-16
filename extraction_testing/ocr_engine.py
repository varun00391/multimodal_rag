"""Always-on OCR: PaddleOCR and Tesseract must both be installed.

PaddleOCR is tried first at extract time; Tesseract is the runtime fallback.
Startup fails if either engine is missing.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from image_utils import crop_region

OCR_MIN_CONFIDENCE = 0.75


@dataclass
class OCRWord:
    text: str
    bbox: list[float]
    confidence: float


@dataclass
class OCRResult:
    text: str
    words: list[OCRWord] = field(default_factory=list)
    average_confidence: float | None = None
    engine: str = ""
    error: str | None = None


class OCRError(RuntimeError):
    pass


class PaddleOCREngine:
    def __init__(self, lang: str = "en"):
        from paddleocr import PaddleOCR

        try:
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=False, show_log=False)
        except TypeError:
            try:
                self._ocr = PaddleOCR(lang=lang, use_angle_cls=True)
            except TypeError:
                self._ocr = PaddleOCR(lang=lang)
        self.lang = lang

    def extract(self, image_path: str) -> OCRResult:
        try:
            result = self._ocr.ocr(image_path, cls=True)
        except TypeError:
            result = self._ocr.ocr(image_path)
        except Exception as exc:
            raise OCRError(f"PaddleOCR failed: {exc}") from exc

        words: list[OCRWord] = []
        lines: list[str] = []
        confidences: list[float] = []
        pages = result or []
        rows = pages[0] if pages else []
        for item in rows or []:
            try:
                box, (text, conf) = item
            except (TypeError, ValueError):
                continue
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            words.append(
                OCRWord(
                    text=text,
                    bbox=[min(xs), min(ys), max(xs), max(ys)],
                    confidence=float(conf),
                )
            )
            lines.append(text)
            confidences.append(float(conf))
        avg = sum(confidences) / len(confidences) if confidences else None
        return OCRResult(
            text="\n".join(lines).strip(),
            words=words,
            average_confidence=avg,
            engine="paddleocr",
        )


class TesseractOCREngine:
    def __init__(self, languages: str = "eng", cmd: str = "tesseract"):
        import pytesseract

        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        version = pytesseract.get_tesseract_version()
        if version is None:
            raise OCRError("Tesseract is installed as a Python package but the tesseract binary is missing.")
        self.languages = languages
        self._pytesseract = pytesseract

    def extract(self, image_path: str) -> OCRResult:
        from PIL import Image

        try:
            image = Image.open(image_path)
            data = self._pytesseract.image_to_data(
                image, lang=self.languages, output_type=self._pytesseract.Output.DICT
            )
            text = self._pytesseract.image_to_string(image, lang=self.languages)
        except Exception as exc:
            raise OCRError(f"Tesseract failed: {exc}") from exc

        words: list[OCRWord] = []
        confidences: list[float] = []
        n = len(data.get("text", []))
        for i in range(n):
            raw = (data["text"][i] or "").strip()
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1
            if not raw or conf < 0:
                continue
            confidences.append(conf / 100.0)
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            words.append(
                OCRWord(
                    text=raw,
                    bbox=[float(x), float(y), float(x + w), float(y + h)],
                    confidence=conf / 100.0,
                )
            )
        avg = sum(confidences) / len(confidences) if confidences else None
        return OCRResult(
            text=(text or "").strip(),
            words=words,
            average_confidence=avg,
            engine="tesseract",
        )


class DualOCREngine:
    def __init__(self, paddle: PaddleOCREngine, tesseract: TesseractOCREngine):
        self.paddle = paddle
        self.tesseract = tesseract

    def extract(self, image_path: str) -> OCRResult:
        try:
            result = self.paddle.extract(image_path)
            if result.text:
                return result
        except OCRError:
            pass
        return self.tesseract.extract(image_path)


_ENGINE: DualOCREngine | None = None


def require_ocr_engines() -> DualOCREngine:
    """Fail startup unless both PaddleOCR and Tesseract are usable."""
    from settings import load_settings

    settings = load_settings()
    errors: list[str] = []
    paddle = None
    tesseract = None

    try:
        paddle = PaddleOCREngine(lang=settings["paddle_ocr_lang"])
    except Exception as exc:
        errors.append(f"PaddleOCR is required but not available: {exc}")

    tesseract_cmd = settings["tesseract_cmd"]
    if not shutil.which(tesseract_cmd):
        errors.append(
            f"Tesseract binary is required but was not found ({tesseract_cmd}). "
            "Install tesseract-ocr."
        )
    else:
        try:
            tesseract = TesseractOCREngine(
                languages=settings["ocr_languages"],
                cmd=tesseract_cmd,
            )
        except Exception as exc:
            errors.append(f"Tesseract is required but not available: {exc}")

    if errors or paddle is None or tesseract is None:
        raise OCRError(
            "Both PaddleOCR and Tesseract must be installed.\n- "
            + "\n- ".join(errors)
            + "\nUse the project Dockerfile, or install paddleocr plus the tesseract binary."
        )
    return DualOCREngine(paddle, tesseract)


def get_ocr_engine() -> DualOCREngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = require_ocr_engines()
    return _ENGINE


def active_ocr_engine() -> str:
    get_ocr_engine()
    return "paddleocr+tesseract"


def ocr_image(image_path: str | Path) -> OCRResult:
    return get_ocr_engine().extract(str(image_path))


def ocr_page_region(
    page_image: str | Path,
    bbox: list[float],
    crop_path: str | Path | None = None,
) -> OCRResult:
    if crop_path is None:
        handle, name = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        crop_path = name
    crop = crop_region(page_image, bbox, crop_path)
    return ocr_image(crop)
