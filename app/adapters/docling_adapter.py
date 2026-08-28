from __future__ import annotations

import asyncio
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

import fitz

from app.adapters.docling_mapping import (
    ADAPTER_VERSION,
    canonical_bbox_from_docling,
    element_type_for_label,
    item_label,
    item_provenances,
    item_text,
    iterate_document_items,
    picture_image,
    provenance_page_number,
    table_exports,
)
from app.adapters.docling_pages import (
    needs_sub_pdf,
    page_geometries,
    page_mapping,
    write_sub_pdf,
)
from app.adapters.docling_profiles import (
    DEFAULT_PROFILE,
    KNOWN_PROFILES,
    build_docling_converter,
    docling_version,
    require_profile,
)
from app.config import Settings
from app.models.canonical import (
    CanonicalElement,
    CanonicalExtractionResult,
    CanonicalPage,
    ElementProvenance,
    ElementType,
    ExtractionAttempt,
    ExtractionError,
    ExtractorProvenance,
)
from app.models.routing import ExtractionTask

logger = logging.getLogger(__name__)

ConverterFactory = Callable[[str, Settings], Any]


class DoclingAdapter:
    name = "docling"

    def __init__(
        self,
        settings: Settings,
        *,
        converter_factory: ConverterFactory | None = None,
    ) -> None:
        self._settings = settings
        self._converter_factory = converter_factory or build_docling_converter
        self._converters: dict[str, Any] = {}
        self._init_lock = threading.Lock()
        self._profile_locks = {profile: threading.Lock() for profile in KNOWN_PROFILES}

    def warm_profiles(self, profiles: tuple[str, ...] | None = None) -> list[str]:
        warmed: list[str] = []
        for profile in profiles or KNOWN_PROFILES:
            self.get_converter(profile)
            warmed.append(profile)
        return warmed

    def get_converter(self, profile: str) -> Any:
        spec = require_profile(profile)
        with self._init_lock:
            converter = self._converters.get(spec.name)
            if converter is None:
                converter = self._converter_factory(spec.name, self._settings)
                self._converters[spec.name] = converter
            return converter

    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        tasks: list[ExtractionTask],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        started = time.perf_counter()
        profile = self._resolve_profile(tasks)
        requested = list(pages)
        extras = [page for page in (context_pages or []) if page not in requested]
        result = await asyncio.to_thread(self._extract_sync, pdf_path, requested + extras, profile)
        keep = set(requested)
        result.pages = [page for page in result.pages if page.page in keep]
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        if result.attempts:
            result.attempts[0].duration_ms = result.duration_ms
        return result

    def _resolve_profile(self, tasks: list[ExtractionTask]) -> str:
        profiles = {task.profile for task in tasks if task.profile}
        if len(profiles) > 1:
            raise ValueError(f"Docling adapter received mixed profiles in one call: {sorted(profiles)}")
        if profiles:
            return require_profile(next(iter(profiles))).name
        return DEFAULT_PROFILE

    def _extract_sync(
        self,
        pdf_path: Path,
        pages: list[int],
        profile: str,
    ) -> CanonicalExtractionResult:
        spec = require_profile(profile)
        requested = list(pages)
        warnings: list[str] = []
        errors: list[ExtractionError] = []
        mapping = page_mapping(requested)
        geometries = page_geometries(pdf_path, requested)
        input_path = pdf_path
        temp_path: Path | None = None

        try:
            with fitz.open(pdf_path) as source_document:
                total_pages = source_document.page_count
            if needs_sub_pdf(requested, total_pages):
                temp_dir = pdf_path.parent / "raw"
                temp_dir.mkdir(parents=True, exist_ok=True)
                handle = tempfile.NamedTemporaryFile(
                    prefix=f"docling-{profile}-",
                    suffix=".pdf",
                    dir=temp_dir,
                    delete=False,
                )
                handle.close()
                temp_path = Path(handle.name)
                write_sub_pdf(pdf_path, requested, temp_path)
                input_path = temp_path
                warnings.append(
                    "Created a temporary sub-PDF for selected-page Docling extraction."
                )

            converter = self.get_converter(profile)
            with self._profile_locks[profile]:
                conversion = converter.convert(str(input_path))

            document = getattr(conversion, "document", conversion)
            extracted_pages = self._document_to_pages(
                document=document,
                pdf_path=pdf_path,
                requested_pages=requested,
                original_pages=mapping["original_pages"],
                geometries=geometries,
                profile=spec.name,
                profile_version=spec.version,
            )
            self._write_raw_output(pdf_path, profile, document)
        except Exception as exc:
            logger.exception("Docling extraction failed for profile %s", profile)
            errors.append(
                ExtractionError(
                    code="DOCLING_EXTRACTION_FAILED",
                    message=str(exc),
                    details={"profile": profile},
                )
            )
            extracted_pages = [
                self._empty_page(
                    page_number=page_number,
                    width=geometries[page_number][0],
                    height=geometries[page_number][1],
                    rotation=geometries[page_number][2],
                    profile=spec.name,
                    error=errors[0],
                )
                for page_number in requested
            ]
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

        attempt_status = "failed" if errors else "completed"
        attempt = ExtractionAttempt(
            attempt=1,
            extractor=self.name,
            profile=spec.name,
            status=attempt_status,
            element_count=sum(len(page.elements) for page in extracted_pages),
            warnings=warnings,
            errors=errors,
        )
        for page in extracted_pages:
            page.attempts = [attempt.model_copy(deep=True)]

        return CanonicalExtractionResult(
            pages=extracted_pages,
            attempts=[attempt],
            warnings=warnings,
            errors=errors,
            metadata={
                **mapping,
                "profile": spec.name,
                "profile_version": spec.version,
                "adapter_version": ADAPTER_VERSION,
                "docling_version": docling_version(),
            },
        )

    def _document_to_pages(
        self,
        *,
        document: Any,
        pdf_path: Path,
        requested_pages: list[int],
        original_pages: list[int],
        geometries: dict[int, tuple[float, float, int]],
        profile: str,
        profile_version: str,
    ) -> list[CanonicalPage]:
        document_id = pdf_path.parent.name
        elements_by_page: dict[int, list[CanonicalElement]] = {
            page_number: [] for page_number in requested_pages
        }
        picture_index_by_page: dict[int, int] = {page_number: 0 for page_number in requested_pages}

        for item in iterate_document_items(document):
            provenances = item_provenances(item)
            if not provenances:
                continue
            first_prov = provenances[0]
            page_number = provenance_page_number(first_prov, original_pages)
            if page_number not in elements_by_page:
                continue

            _width, height, _rotation = geometries[page_number]
            bbox = canonical_bbox_from_docling(getattr(first_prov, "bbox", None), height)
            element_type = element_type_for_label(item_label(item))
            reading_order = len(elements_by_page[page_number]) + 1
            text, markdown, html = self._content_for_item(item, document, element_type)
            asset = None
            if element_type in {ElementType.PICTURE, ElementType.CHART, ElementType.DIAGRAM}:
                picture_index_by_page[page_number] += 1
                asset = self._save_picture(
                    item=item,
                    document=document,
                    pdf_path=pdf_path,
                    page_number=page_number,
                    picture_index=picture_index_by_page[page_number],
                )

            elements_by_page[page_number].append(
                CanonicalElement(
                    element_id=f"{document_id}:p{page_number}:e{reading_order}",
                    type=element_type,
                    page=page_number,
                    reading_order=reading_order,
                    text=text,
                    markdown=markdown,
                    html=html,
                    bbox=bbox,
                    asset=asset,
                    confidence=0.75 if profile == "private-ocr" else 0.88,
                    extractor=ExtractorProvenance(
                        name=self.name,
                        version=docling_version(),
                        adapter_version=ADAPTER_VERSION,
                        profile=profile,
                    ),
                    provenance=ElementProvenance(source_page=page_number),
                    metadata={
                        "docling_label": item_label(item),
                        "profile": profile,
                        "profile_version": profile_version,
                    },
                )
            )

        pages: list[CanonicalPage] = []
        for page_number in requested_pages:
            width, height, rotation = geometries[page_number]
            elements = elements_by_page[page_number]
            warnings: list[str] = []
            errors: list[ExtractionError] = []
            if not elements:
                warnings.append("Docling returned no elements for this page.")
            pages.append(
                CanonicalPage(
                    page=page_number,
                    width=width,
                    height=height,
                    rotation=rotation,
                    primary_route=self.name,
                    routing_confidence=0.8,
                    overall_confidence=0.8 if elements else 0.0,
                    routing_reasons=[f"Docling profile '{profile}'"],
                    extraction_routes=[self.name],
                    elements=elements,
                    warnings=warnings,
                    errors=errors,
                )
            )
        return pages

    @staticmethod
    def _content_for_item(
        item: Any,
        document: Any,
        element_type: ElementType,
    ) -> tuple[str | None, str | None, str | None]:
        if element_type == ElementType.TABLE:
            return table_exports(item, document)
        text = item_text(item)
        markdown = None
        if element_type == ElementType.HEADING and text:
            markdown = f"## {text.strip()}"
        elif element_type == ElementType.LIST and text:
            markdown = "\n".join(
                f"- {line.lstrip('•-*0123456789.) ')}"
                for line in text.splitlines()
                if line.strip()
            )
        elif element_type == ElementType.FORMULA and text:
            markdown = f"${text.strip()}$"
        elif element_type == ElementType.CODE and text:
            markdown = f"```\n{text.rstrip()}\n```"
        return text, markdown, None

    def _save_picture(
        self,
        *,
        item: Any,
        document: Any,
        pdf_path: Path,
        page_number: int,
        picture_index: int,
    ) -> str | None:
        image = picture_image(item, document)
        if image is None:
            return None
        assets_dir = pdf_path.parent / "assets" / "pictures"
        assets_dir.mkdir(parents=True, exist_ok=True)
        filename = f"page_{page_number}_picture_{picture_index}.png"
        target = assets_dir / filename
        try:
            if hasattr(image, "save"):
                image.save(target)
            elif isinstance(image, (bytes, bytearray)):
                target.write_bytes(image)
            else:
                return None
        except Exception:
            logger.exception("Failed to save Docling picture for page %s", page_number)
            return None
        return f"assets/pictures/{filename}"

    def _write_raw_output(self, pdf_path: Path, profile: str, document: Any) -> None:
        raw_dir = pdf_path.parent / "raw"
        if not raw_dir.exists():
            return
        raw_path = raw_dir / f"docling-{profile}.json"
        saver = getattr(document, "save_as_json", None)
        if callable(saver):
            try:
                saver(raw_path)
            except Exception:
                logger.debug("Unable to persist raw Docling JSON for profile %s", profile)

    @staticmethod
    def _empty_page(
        *,
        page_number: int,
        width: float,
        height: float,
        rotation: int,
        profile: str,
        error: ExtractionError,
    ) -> CanonicalPage:
        page_error = error.model_copy(update={"page": page_number})
        return CanonicalPage(
            page=page_number,
            width=width,
            height=height,
            rotation=rotation,
            primary_route=DoclingAdapter.name,
            routing_confidence=0.0,
            overall_confidence=0.0,
            routing_reasons=[f"Docling profile '{profile}'"],
            extraction_routes=[DoclingAdapter.name],
            errors=[page_error],
        )
