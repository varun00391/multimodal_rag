from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.core.exceptions import OCRFailedError


@dataclass
class OCRWord:
    text: str
    bbox: list[float]
    confidence: float
    block: int | None = None
    line: int | None = None


@dataclass
class OCRResult:
    text: str
    words: list[OCRWord] = field(default_factory=list)
    average_confidence: float | None = None
    engine: str = ""
    model_version: str = ""


class OCREngine(Protocol):
    def extract(self, image_path: str) -> OCRResult:
        ...


class TesseractOCREngine:
    def __init__(self):
        settings = get_settings()
        self.languages = settings.ocr_languages
        self.cmd = settings.tesseract_cmd

    def extract(self, image_path: str) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image
        except Exception as exc:
            raise OCRFailedError(f"Tesseract dependencies are missing: {exc}") from exc

        if self.cmd:
            pytesseract.pytesseract.tesseract_cmd = self.cmd
        try:
            image = Image.open(image_path)
            data = pytesseract.image_to_data(
                image, lang=self.languages, output_type=pytesseract.Output.DICT
            )
            text = pytesseract.image_to_string(image, lang=self.languages)
        except Exception as exc:
            raise OCRFailedError(f"Tesseract failed: {exc}") from exc

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
                    block=int(data.get("block_num", [0])[i]),
                    line=int(data.get("line_num", [0])[i]),
                )
            )
        avg = sum(confidences) / len(confidences) if confidences else None
        return OCRResult(
            text=(text or "").strip(),
            words=words,
            average_confidence=avg,
            engine="tesseract",
            model_version=self.languages,
        )


class PaddleOCREngine:
    def __init__(self):
        settings = get_settings()
        self.lang = settings.paddle_ocr_lang
        self.use_gpu = settings.paddle_ocr_use_gpu
        self._ocr = None

    def _client(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
            except Exception as exc:
                raise OCRFailedError(
                    "PaddleOCR is not installed. Set OCR_ENGINE=tesseract or install paddleocr."
                ) from exc
            self._ocr = PaddleOCR(use_angle_cls=True, lang=self.lang, use_gpu=self.use_gpu)
        return self._ocr

    def extract(self, image_path: str) -> OCRResult:
        try:
            result = self._client().ocr(image_path, cls=True)
        except Exception as exc:
            raise OCRFailedError(f"PaddleOCR failed: {exc}") from exc
        words: list[OCRWord] = []
        lines: list[str] = []
        confidences: list[float] = []
        pages = result or []
        rows = pages[0] if pages else []
        for item in rows or []:
            box, (text, conf) = item
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
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
            model_version=self.lang,
        )


def get_ocr_engine() -> OCREngine:
    settings = get_settings()
    if settings.ocr_engine.lower() == "paddle":
        return PaddleOCREngine()
    return TesseractOCREngine()


def ocr_image(image_path: Path) -> OCRResult:
    return get_ocr_engine().extract(str(image_path))


def words_to_page_space(words: list[OCRWord], crop_bbox_px: list[float]) -> list[OCRWord]:
    dx, dy = crop_bbox_px[0], crop_bbox_px[1]
    shifted: list[OCRWord] = []
    for word in words:
        x0, y0, x1, y1 = word.bbox
        shifted.append(
            OCRWord(
                text=word.text,
                bbox=[x0 + dx, y0 + dy, x1 + dx, y1 + dy],
                confidence=word.confidence,
                block=word.block,
                line=word.line,
            )
        )
    return shifted
