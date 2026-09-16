from __future__ import annotations

from pathlib import Path

from extraction.elements import text_element
from extraction.errors import ExtractionError
from extraction.models.cdr import Diagnostic, Unit
from extraction.models.report import ExtractionReport, RouteRecord
from extraction.settings import Settings

VERSION = "1.0"
_MODEL = None


def _load_whisper(settings: Settings):
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ExtractionError(
            "WHISPER_UNAVAILABLE",
            "faster-whisper is not installed. Install extraction-service[media].",
        ) from exc
    _MODEL = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    return _MODEL


def transcribe_audio(settings: Settings, path: Path) -> list[tuple[float, float, str]]:
    model = _load_whisper(settings)
    segments, _info = model.transcribe(str(path))
    return [(float(seg.start), float(seg.end), (seg.text or "").strip()) for seg in segments]


def extract_audio(
    settings: Settings,
    path: Path,
    report: ExtractionReport,
    diagnostics: list[Diagnostic],
) -> list[Unit]:
    try:
        segments = transcribe_audio(settings, path)
    except ExtractionError as exc:
        diagnostics.append(Diagnostic(code=exc.code, message=exc.message, unit_index=1))
        report.routes.append(RouteRecord(unit_type="time_range", index=1, extractor="faster-whisper"))
        return [
            Unit(unit_type="time_range", index=1, primary_route="faster-whisper", error=exc.code)
        ]
    units: list[Unit] = []
    for index, (start, end, text) in enumerate(segments, start=1):
        elements = []
        if text:
            elements.append(
                text_element(
                    unit_type="time_range",
                    unit_index=index,
                    order=1,
                    text=text,
                    extractor="faster-whisper",
                    version=VERSION,
                    element_type="transcript_segment",
                )
            )
        report.routes.append(RouteRecord(unit_type="time_range", index=index, extractor="faster-whisper"))
        units.append(
            Unit(
                unit_type="time_range",
                index=index,
                primary_route="faster-whisper",
                t_start=start,
                t_end=end,
                elements=elements,
                error=None if elements else "TRANSCRIPT_EMPTY",
            )
        )
    if not units:
        diagnostics.append(Diagnostic(code="AUDIO_EMPTY", message="No transcript segments."))
        report.routes.append(RouteRecord(unit_type="time_range", index=1, extractor="faster-whisper"))
        units.append(Unit(unit_type="time_range", index=1, primary_route="faster-whisper", error="AUDIO_EMPTY"))
    return units
