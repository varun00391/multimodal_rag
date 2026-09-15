from __future__ import annotations

import string
from pathlib import Path

import fitz

from app.core.config import get_settings
from app.core.exceptions import CorruptPDFError, EncryptedPDFError, UnsupportedPDFError
from app.models.document import DocumentProfile
from app.models.page import PageProfile
from app.profiling.page_profiler import profile_page


def open_pdf(path: Path) -> fitz.Document:
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise CorruptPDFError(f"Unable to open PDF: {exc}") from exc
    if doc.is_encrypted:
        try:
            if not doc.authenticate(""):
                doc.close()
                raise EncryptedPDFError("PDF is encrypted and requires a password.")
        except EncryptedPDFError:
            raise
        except Exception as exc:
            doc.close()
            raise EncryptedPDFError(f"PDF is encrypted: {exc}") from exc
    return doc


def profile_pdf(path: Path) -> DocumentProfile:
    settings = get_settings()
    doc = open_pdf(path)
    try:
        if doc.page_count < 1:
            raise UnsupportedPDFError("PDF has no pages.")
        if doc.page_count > settings.max_pages:
            raise UnsupportedPDFError(
                f"PDF has {doc.page_count} pages; max allowed is {settings.max_pages}."
            )
        pages: list[PageProfile] = []
        fonts: set[str] = set()
        total_chars = 0
        total_images = 0
        total_vectors = 0
        scanned_pages = 0
        digital_pages = 0
        for index in range(doc.page_count):
            page = doc.load_page(index)
            page_profile = profile_page(page, index + 1)
            pages.append(page_profile)
            total_chars += page_profile.native_text_chars
            total_images += page_profile.image_count
            total_vectors += page_profile.vector_count
            if page_profile.is_probably_scanned:
                scanned_pages += 1
            else:
                digital_pages += 1
            for font in page.get_fonts():
                if len(font) > 3 and font[3]:
                    fonts.add(str(font[3]))
        metadata = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
        is_scanned = scanned_pages == len(pages) and len(pages) > 0
        is_hybrid = scanned_pages > 0 and digital_pages > 0
        is_born_digital = scanned_pages == 0
        return DocumentProfile(
            page_count=doc.page_count,
            pdf_version=(doc.metadata or {}).get("format"),
            encrypted=bool(doc.is_encrypted),
            is_probably_scanned=is_scanned,
            is_hybrid=is_hybrid,
            is_born_digital=is_born_digital,
            native_text_chars=total_chars,
            image_count=total_images,
            vector_count=total_vectors,
            fonts=sorted(fonts),
            metadata=metadata,
            pages=pages,
        )
    finally:
        doc.close()


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    allowed = set(string.printable)
    good = sum(1 for ch in text if ch in allowed)
    return good / len(text)
