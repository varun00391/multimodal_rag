from __future__ import annotations

import zipfile
from pathlib import Path

from extraction.errors import ExtractionError

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLS = "application/vnd.ms-excel"
CSV = "text/csv"
TSV = "text/tab-separated-values"
ZIP = "application/zip"
PNG = "image/png"
JPEG = "image/jpeg"
TIFF = "image/tiff"
WEBP = "image/webp"
GIF = "image/gif"
WAV = "audio/wav"
MP3 = "audio/mpeg"
M4A = "audio/mp4"
OGG = "audio/ogg"
MP4 = "video/mp4"
WEBM = "video/webm"
MKV = "video/x-matroska"
AVI = "video/x-msvideo"

OFFICE_TYPES = {DOCX, PPTX, XLSX, XLS}
TABULAR_TYPES = {CSV, TSV, XLSX, XLS}
IMAGE_TYPES = {PNG, JPEG, TIFF, WEBP, GIF}
AUDIO_TYPES = {WAV, MP3, M4A, OGG}
VIDEO_TYPES = {MP4, WEBM, MKV, AVI}

EXTENSION_MAP = {
    ".pdf": PDF,
    ".docx": DOCX,
    ".pptx": PPTX,
    ".xlsx": XLSX,
    ".xls": XLS,
    ".csv": CSV,
    ".tsv": TSV,
    ".zip": ZIP,
    ".png": PNG,
    ".jpg": JPEG,
    ".jpeg": JPEG,
    ".tif": TIFF,
    ".tiff": TIFF,
    ".webp": WEBP,
    ".gif": GIF,
    ".wav": WAV,
    ".mp3": MP3,
    ".m4a": M4A,
    ".ogg": OGG,
    ".mp4": MP4,
    ".webm": WEBM,
    ".mkv": MKV,
    ".avi": AVI,
}


def _sniff_office_zip(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return None
    if any(name.startswith("word/") for name in names):
        return DOCX
    if any(name.startswith("ppt/") for name in names):
        return PPTX
    if any(name.startswith("xl/") for name in names):
        return XLSX
    return ZIP


def detect_media_type(path: Path, filename: str | None = None) -> str:
    header = path.read_bytes()[:16]
    suffix = Path(filename or path.name).suffix.lower()
    if header.startswith(b"%PDF"):
        return PDF
    if header.startswith(b"\x89PNG"):
        return PNG
    if header.startswith(b"\xff\xd8\xff"):
        return JPEG
    if header.startswith(b"GIF8"):
        return GIF
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return WEBP
    if header.startswith(b"II*\x00") or header.startswith(b"MM\x00*"):
        return TIFF
    if header.startswith(b"PK"):
        sniffed = _sniff_office_zip(path)
        if sniffed:
            return sniffed
    if suffix in EXTENSION_MAP:
        return EXTENSION_MAP[suffix]
    raise ExtractionError("UNSUPPORTED_TYPE", f"Unsupported file type: {filename or path.name}")


def family_for(media_type: str) -> str:
    if media_type == PDF:
        return "pdf"
    if media_type in {DOCX, PPTX}:
        return "office"
    if media_type in TABULAR_TYPES:
        return "tabular"
    if media_type in IMAGE_TYPES:
        return "image"
    if media_type in AUDIO_TYPES:
        return "audio"
    if media_type in VIDEO_TYPES:
        return "video"
    if media_type == ZIP:
        return "archive"
    return "unknown"
