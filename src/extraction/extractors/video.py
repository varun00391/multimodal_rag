from __future__ import annotations

import subprocess
from pathlib import Path

from extraction.clients.euron import describe_image
from extraction.elements import picture_element
from extraction.errors import ExtractionError
from extraction.extractors.audio import extract_audio
from extraction.models.cdr import Diagnostic, Unit
from extraction.models.report import ExtractionReport, ModelCall, RouteRecord
from extraction.settings import Settings

VERSION = "1.0"
PROMPT_VERSION = "vlm-video-frame-v1"


def _run_ffmpeg(args: list[str]) -> None:
    try:
        subprocess.run(args, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ExtractionError("FFMPEG_UNAVAILABLE", "ffmpeg is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise ExtractionError("FFMPEG_FAILED", exc.stderr[-500:] if exc.stderr else "ffmpeg failed") from exc


def _frame_needs_vision(path: Path) -> bool:
    try:
        import pymupdf

        pix = pymupdf.Pixmap(str(path))
    except Exception:
        return True
    samples = pix.samples
    if not samples:
        return False
    values = list(samples[0 : min(len(samples), 12000) : max(pix.n, 1)])
    if not values:
        return False
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return variance >= 40 and 8 < mean < 247


def extract_video(
    settings: Settings,
    path: Path,
    assets_dir: Path,
    report: ExtractionReport,
    diagnostics: list[Diagnostic],
) -> list[Unit]:
    audio_path = assets_dir / f"{path.stem}-audio.wav"
    _run_ffmpeg(["ffmpeg", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)])
    units = extract_audio(settings, audio_path, report, diagnostics)

    frame_dir = assets_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    interval = max(settings.video_frame_interval_seconds, 1)
    try:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-vf",
                f"fps=1/{interval}",
                str(frame_dir / "frame-%04d.png"),
            ]
        )
    except ExtractionError as exc:
        diagnostics.append(Diagnostic(code=exc.code, message=exc.message))
        return units

    frames = sorted(frame_dir.glob("frame-*.png"))
    for index, frame in enumerate(frames, start=1):
        purpose = f"video-frame-{index}"
        if not _frame_needs_vision(frame):
            report.model_calls.append(
                ModelCall(
                    provider="euron",
                    model=settings.euri_vlm_model,
                    purpose=purpose,
                    skipped=True,
                    reason="frame is near-blank",
                )
            )
            continue
        try:
            description = describe_image(settings, frame, report, purpose=purpose)
        except Exception as exc:
            diagnostics.append(Diagnostic(code="VLM_FAILED", message=str(exc), unit_index=index))
            continue
        if not description:
            continue
        report.routes.append(RouteRecord(unit_type="file", index=index, extractor="euron-vlm"))
        units.append(
            Unit(
                unit_type="file",
                index=index,
                label=frame.name,
                primary_route="euron-vlm",
                t_start=(index - 1) * interval,
                elements=[
                    picture_element(
                        unit_type="file",
                        unit_index=index,
                        order=1,
                        asset_path=f"frames/{frame.name}",
                        extractor="euron-vlm",
                        version=VERSION,
                        text=description,
                        model=settings.euri_vlm_model,
                        prompt_version=PROMPT_VERSION,
                    )
                ],
            )
        )
    return units
