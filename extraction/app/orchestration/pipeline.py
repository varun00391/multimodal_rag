from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ExtractionError, VLMTimeoutError
from app.core.ids import review_id
from app.core.logging import get_logger
from app.context.context_builder import build_canonical_document
from app.db.repository import Repository, get_repository, utcnow
from app.extractors.tables.pymupdf_tables import extract_tables_from_page, find_table_bboxes
from app.extractors.tables.table_ocr import extract_table_via_ocr
from app.extractors.tables.table_reconciler import reconcile_tables
from app.extractors.text.native_pdf import extract_native_page
from app.extractors.text.ocr import ocr_image
from app.extractors.text.text_reconciler import native_text_is_usable, reconcile_text_evidence
from app.extractors.visuals.chart_extractor import extract_chart
from app.extractors.visuals.diagram_extractor import extract_diagram
from app.extractors.visuals.image_extractor import extract_image_region
from app.extractors.vlm.client import VLMClient
from app.extractors.vlm.prompts import REGION_PROMPT
from app.extractors.base import ExtractionEvidence
from app.ingestion.storage import DocumentPaths, get_storage
from app.layout.region_detector import detect_regions
from app.layout.region_tree import build_region_tree
from app.models.common import JobStatus, RegionType, ValidationStatus
from app.models.document import AssetRef, ReviewItem
from app.models.element import ExtractedElement
from app.models.page import PageModel
from app.models.provenance import Provenance, ProvenanceSource
from app.models.region import Region
from app.models.validation import EvidenceCandidate
from app.orchestration.router import route_region
from app.outputs.asset_writer import write_json_asset
from app.outputs.json_writer import write_document_json
from app.outputs.markdown_writer import write_document_markdown
from app.profiling.pdf_profiler import open_pdf, profile_pdf
from app.rendering.crop_renderer import crop_page_image
from app.rendering.page_renderer import render_pages
from app.validation.confidence import build_validation, score_confidence
from app.validation.consistency import table_arithmetic_ok
from app.validation.rules import needs_human_review

logger = get_logger(__name__)


class ExtractionPipeline:
    def __init__(self, repo: Repository | None = None):
        self.repo = repo or get_repository()
        self.storage = get_storage()
        self.settings = get_settings()
        self.vlm = VLMClient()

    def run(self, document_id: str, job_id: str) -> None:
        paths = self.storage.document_paths(document_id)
        document = self.repo.get_document(document_id)
        warnings: list[str] = []
        try:
            self._set_status(document_id, job_id, JobStatus.PROFILING, "profiling")
            profile = profile_pdf(paths.original)
            write_json_asset(paths.profile_json, profile.model_dump())
            self.repo.update_document(document_id, page_count=profile.page_count)

            rendered = render_pages(paths.original, paths, self.settings.render_dpi)
            render_by_page = {item["page"]: item for item in rendered}

            self._set_status(document_id, job_id, JobStatus.REGION_DETECTION, "region_detection")
            pages: list[PageModel] = []
            assets: list[AssetRef] = [
                AssetRef(id="original", kind="pdf", path="original.pdf")
            ]
            review_regions: list[tuple[Region, str]] = []

            doc = open_pdf(paths.original)
            try:
                for page_profile in profile.pages:
                    page = doc.load_page(page_profile.page_number - 1)
                    native = extract_native_page(page, page_profile.page_number, self.settings.render_dpi)
                    write_json_asset(
                        paths.native / f"page_{page_profile.page_number:03d}.json",
                        [obj.model_dump() for obj in native],
                    )
                    table_models = extract_tables_from_page(
                        page, page_profile.page_number, self.settings.render_dpi
                    )
                    table_bboxes = find_table_bboxes(page)
                    regions = detect_regions(
                        page_profile.page_number,
                        page_profile,
                        native,
                        self.settings.render_dpi,
                        table_bboxes,
                    )
                    regions = build_region_tree(regions)
                    page_render = render_by_page[page_profile.page_number]
                    page_image = Path(page_render["path"])
                    assets.append(
                        AssetRef(
                            id=f"page_{page_profile.page_number:03d}",
                            kind="page_image",
                            path=page_render["relative_path"],
                            page=page_profile.page_number,
                        )
                    )
                    tables_by_index = list(table_models)
                    table_cursor = 0
                    self._set_status(document_id, job_id, JobStatus.EXTRACTING, "extracting")
                    for region in regions:
                        try:
                            self._extract_region(
                                document_id=document_id,
                                paths=paths,
                                pdf_path=paths.original,
                                page_image=page_image,
                                page_profile=page_profile,
                                region=region,
                                native=native,
                                table_models=tables_by_index,
                                table_cursor=table_cursor,
                                warnings=warnings,
                                assets=assets,
                            )
                            if region.type in {RegionType.TABLE, RegionType.COMPLEX_TABLE}:
                                table_cursor += 1
                        except VLMTimeoutError:
                            warnings.append("VLM_TIMEOUT")
                            region.element = region.element or self._empty_element(region)
                            region.element.warnings.append("VLM_TIMEOUT")
                        except Exception:
                            logger.exception("Region %s failed", region.id)
                            warnings.append(f"PARTIAL_EXTRACTION:{region.id}")
                            region.element = region.element or self._empty_element(region)
                            region.element.warnings.append("PARTIAL_EXTRACTION")
                        if region.element and needs_human_review(
                            region,
                            region.element.validation,
                            self.settings.review_confidence_threshold,
                        ):
                            reason = ", ".join(region.element.validation.reasons) or region.element.validation.status.value
                            review_regions.append((region, reason))

                    pages.append(
                        PageModel(
                            page_number=page_profile.page_number,
                            width=page_profile.width,
                            height=page_profile.height,
                            width_px=page_render["width_px"],
                            height_px=page_render["height_px"],
                            dpi=self.settings.render_dpi,
                            image_path=page_render["relative_path"],
                            profile=page_profile,
                            native_objects=[
                                obj
                                for obj in native
                                if obj.type
                                in {"block", "image", "drawing", "annotation", "link", "image_block"}
                            ],
                            regions=regions,
                        )
                    )
            finally:
                doc.close()

            self._set_status(document_id, job_id, JobStatus.VALIDATING, "validating")
            for region, reason in review_regions:
                item = ReviewItem(
                    id=review_id(),
                    document_id=document_id,
                    region_id=region.id,
                    page_number=region.page,
                    status="PENDING",
                    reason=reason,
                    bbox=region.bbox,
                    candidates=[c.model_dump() for c in region.element.validation.candidates]
                    if region.element
                    else [],
                    confidence=region.element.validation.confidence if region.element else None,
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                self.repo.create_review_item(item)

            if review_regions:
                write_json_asset(
                    paths.validation / "review_items.json",
                    [{"region_id": r.id, "reason": reason} for r, reason in review_regions],
                )

            halt = review_regions and self.settings.halt_pipeline_on_review
            if halt:
                self._set_status(document_id, job_id, JobStatus.REVIEW_REQUIRED, "review_required")

            self._set_status(document_id, job_id, JobStatus.RECONSTRUCTING, "reconstructing")
            canonical = build_canonical_document(
                document_id=document_id,
                filename=document.filename,
                profile=profile,
                pages=pages,
                assets=assets,
                warnings=sorted(set(warnings)),
            )
            canonical.document["sha256"] = document.sha256
            write_document_json(paths.document_json, canonical)
            write_document_markdown(paths.document_md, canonical)

            final_status = JobStatus.COMPLETED
            if warnings and not review_regions:
                final_status = JobStatus.PARTIAL_SUCCESS
            if review_regions and not halt:
                final_status = (
                    JobStatus.PARTIAL_SUCCESS if warnings else JobStatus.COMPLETED
                )
                if any(
                    region.element and region.element.validation.status == ValidationStatus.CONFLICT
                    for region, _ in review_regions
                ):
                    final_status = JobStatus.PARTIAL_SUCCESS
            if halt:
                final_status = JobStatus.REVIEW_REQUIRED
            self.repo.update_document(
                document_id,
                status=final_status,
                page_count=profile.page_count,
                warnings=sorted(set(warnings)),
            )
            self.repo.update_job(
                job_id,
                status=final_status,
                current_step="done",
                finished=True,
            )
        except ExtractionError as exc:
            logger.exception("Extraction failed for %s", document_id)
            self.repo.update_document(document_id, status=JobStatus.FAILED, error_code=exc.code)
            self.repo.update_job(
                job_id,
                status=JobStatus.FAILED,
                current_step="failed",
                error_code=exc.code,
                error_message=exc.message,
                finished=True,
            )
        except Exception as exc:
            logger.exception("Unexpected extraction failure for %s", document_id)
            self.repo.update_document(document_id, status=JobStatus.FAILED, error_code="EXTRACTION_ERROR")
            self.repo.update_job(
                job_id,
                status=JobStatus.FAILED,
                current_step="failed",
                error_code="EXTRACTION_ERROR",
                error_message=str(exc),
                finished=True,
            )

    def _set_status(self, document_id: str, job_id: str, status: JobStatus, step: str) -> None:
        self.repo.update_job(job_id, status=status, current_step=step)
        self.repo.update_document(document_id, status=status)

    def _empty_element(self, region: Region) -> ExtractedElement:
        return ExtractedElement(
            id=region.id,
            type=region.type,
            page=region.page,
            bbox=region.bbox,
            bbox_pdf=region.bbox_pdf,
            content={},
            provenance=Provenance(page=region.page, bbox=region.bbox),
        )

    def _extract_region(
        self,
        *,
        document_id: str,
        paths: DocumentPaths,
        pdf_path: Path,
        page_image: Path,
        page_profile,
        region: Region,
        native,
        table_models,
        table_cursor: int,
        warnings: list[str],
        assets: list[AssetRef],
    ) -> None:
        engines = route_region(region, page_profile)
        crop_path = paths.regions / f"{region.id}.{self.settings.render_image_format}"
        crop_page_image(page_image, region.bbox, crop_path)
        assets.append(
            AssetRef(
                id=f"region_{region.id}",
                kind="region_crop",
                path=str(crop_path.relative_to(paths.root)),
                page=region.page,
                region_id=region.id,
            )
        )
        evidences: list[ExtractionEvidence] = []
        content: dict = {}
        native_text = self._native_text_for_region(region, native)
        if "native_text" in engines and native_text:
            usable = native_text_is_usable(
                native_text,
                self.settings.min_native_text_chars if region.type == RegionType.PARAGRAPH else 1,
                self.settings.native_text_garbage_ratio,
            )
            evidences.append(
                ExtractionEvidence(
                    engine="pymupdf",
                    text=native_text,
                    confidence=0.95 if usable else 0.4,
                    bbox=region.bbox,
                )
            )
            if usable:
                content["text"] = native_text

        need_ocr = "ocr" in engines or (
            "ocr_fallback" in engines and not content.get("text")
        )
        ocr_result = None
        if need_ocr and self.settings.ocr_enabled:
            try:
                ocr_result = ocr_image(crop_path)
                write_json_asset(
                    paths.ocr / f"{region.id}.json",
                    {
                        "text": ocr_result.text,
                        "average_confidence": ocr_result.average_confidence,
                        "words": [word.__dict__ for word in ocr_result.words],
                        "engine": ocr_result.engine,
                    },
                )
                evidences.append(
                    ExtractionEvidence(
                        engine=ocr_result.engine,
                        model_version=ocr_result.model_version,
                        text=ocr_result.text,
                        confidence=ocr_result.average_confidence,
                        bbox=region.bbox,
                    )
                )
                if not content.get("text"):
                    content["text"] = ocr_result.text
            except Exception as exc:
                warnings.append("OCR_FAILED")
                logger.warning("OCR failed for %s: %s", region.id, exc)

        if region.type in {RegionType.TABLE, RegionType.COMPLEX_TABLE}:
            primary = table_models[table_cursor] if table_cursor < len(table_models) else None
            secondary = None
            if (primary is None or not primary.rows or page_profile.is_probably_scanned) and self.settings.ocr_enabled:
                try:
                    secondary, ocr_table = extract_table_via_ocr(
                        crop_path, region.page, region.bbox, f"{region.id}_ocr_table"
                    )
                    write_json_asset(
                        paths.tables / f"{region.id}_ocr.json",
                        secondary.model_dump(),
                    )
                except Exception as exc:
                    warnings.append("TABLE_EXTRACTION_FAILED")
                    logger.warning("OCR table failed for %s: %s", region.id, exc)
            merged = reconcile_tables(primary, secondary)
            table = merged.get("table")
            if table is not None:
                if table.is_complex:
                    region.type = RegionType.COMPLEX_TABLE
                arith = table_arithmetic_ok(table) if self.settings.enable_arithmetic_checks else None
                content["table"] = table.model_dump()
                write_json_asset(paths.tables / f"{region.id}.json", table.model_dump())
                content["arithmetic_ok"] = arith
                if arith is False:
                    warnings.append("ARITHMETIC_INCONSISTENCY")
            if merged.get("status") == ValidationStatus.CONFLICT.value:
                evidences.append(
                    ExtractionEvidence(engine="table_conflict", text=str(merged.get("value") or ""))
                )

        xref = None
        for native_id in region.native_object_ids:
            match = next((obj for obj in native if obj.id == native_id), None)
            if match and match.extra.get("xref"):
                xref = int(match.extra["xref"])
                break

        figure = None
        if any(name in engines for name in ("image_extractor", "pdf_vectors")) or region.type in {
            RegionType.IMAGE,
            RegionType.FIGURE,
            RegionType.CHART,
            RegionType.DIAGRAM,
            RegionType.SIGNATURE,
        }:
            figure = extract_image_region(
                pdf_path=pdf_path,
                paths=paths,
                page_image=page_image,
                page_number=region.page,
                region_id=region.id,
                bbox_px=region.bbox,
                xref=xref,
            )
            content["figure"] = figure.model_dump()
            if figure.original_asset:
                assets.append(
                    AssetRef(
                        id=f"image_{region.id}",
                        kind="embedded_image",
                        path=figure.original_asset,
                        page=region.page,
                        region_id=region.id,
                    )
                )

        if region.type == RegionType.CHART and "vlm" in engines:
            chart, evidence = extract_chart(crop_path, self.vlm if self.vlm.enabled else None)
            content["chart"] = chart.model_dump()
            if evidence.get("ocr_text"):
                evidences.append(
                    ExtractionEvidence(
                        engine="ocr",
                        text=evidence["ocr_text"],
                        confidence=evidence.get("ocr_confidence"),
                    )
                )
            if figure:
                figure.chart = chart
                figure.ocr_text = evidence.get("ocr_text")
                content["figure"] = figure.model_dump()

        if region.type == RegionType.DIAGRAM and ("vlm" in engines or "pdf_vectors" in engines):
            diagram, evidence = extract_diagram(
                crop_path,
                self.vlm if self.vlm.enabled else None,
                vector_count=page_profile.vector_count,
            )
            content["diagram"] = diagram.model_dump()
            if evidence.get("ocr_text"):
                evidences.append(
                    ExtractionEvidence(
                        engine="ocr",
                        text=evidence["ocr_text"],
                        confidence=evidence.get("ocr_confidence"),
                    )
                )
            if figure:
                figure.diagram = diagram
                figure.ocr_text = evidence.get("ocr_text")
                content["figure"] = figure.model_dump()

        if "vlm" in engines or "vlm_verify" in engines:
            if self.vlm.enabled:
                payload = self.vlm.analyze_image(crop_path, REGION_PROMPT)
                if payload:
                    evidences.append(
                        ExtractionEvidence(
                            engine="vlm",
                            model_version=self.settings.vlm_model,
                            text=str(payload.get("text") or json.dumps(payload)),
                            data=payload,
                            confidence=0.7,
                        )
                    )
                    if not content.get("text") and payload.get("text"):
                        content["text"] = payload["text"]

        if region.children:
            content["children"] = region.children
        if region.extra.get("text") and region.type == RegionType.CAPTION:
            content["text"] = region.extra["text"]

        reconciled = reconcile_text_evidence(evidences) if evidences else {
            "status": ValidationStatus.VERIFIED.value if content.get("text") or content.get("table") else ValidationStatus.PARTIAL.value,
            "value": content.get("text") or "",
            "sources": [e.engine for e in evidences],
            "candidates": [],
        }
        if reconciled.get("value") and not content.get("text"):
            content["text"] = reconciled["value"]

        sources = []
        seen = set()
        for evidence in evidences:
            if evidence.engine in seen:
                continue
            seen.add(evidence.engine)
            sources.append(ProvenanceSource(engine=evidence.engine, model_version=evidence.model_version))
        if not sources and content:
            sources.append(ProvenanceSource(engine="pymupdf"))

        agreement = 1.0
        if reconciled.get("status") == ValidationStatus.CONFLICT.value:
            agreement = 0.3
        elif len(reconciled.get("sources") or []) > 1:
            agreement = 1.0
        elif evidences:
            agreement = 0.7
        quality = 0.5
        if evidences:
            confs = [e.confidence for e in evidences if e.confidence is not None]
            quality = sum(confs) / len(confs) if confs else 0.6
        structural = 1.0
        if content.get("arithmetic_ok") is False:
            structural = 0.4
        semantic = 1.0 if content else 0.2
        visual = 1.0 if content.get("figure") else 0.8
        confidence = score_confidence(
            source_agreement=agreement,
            extraction_quality=quality,
            structural_consistency=structural,
            semantic_consistency=semantic,
            visual_confidence=visual,
        )
        status = ValidationStatus(reconciled.get("status") or ValidationStatus.PARTIAL.value)
        if confidence < self.settings.confidence_medium and status != ValidationStatus.CONFLICT:
            status = ValidationStatus.LOW_CONFIDENCE
        reasons = []
        if status == ValidationStatus.CONFLICT:
            reasons.append("EXTRACTION_CONFLICT")
        if content.get("arithmetic_ok") is False:
            reasons.append("ARITHMETIC_INCONSISTENCY")
        if not content.get("text") and not content.get("table") and not content.get("figure"):
            reasons.append("UNREADABLE_REGION")
            status = ValidationStatus.UNREADABLE
        candidates = [
            EvidenceCandidate(**item) if isinstance(item, dict) else item
            for item in reconciled.get("candidates") or []
        ]
        validation = build_validation(
            confidence=confidence,
            status=status,
            reasons=reasons,
            candidates=candidates,
            checks={
                "source_agreement": agreement,
                "extraction_quality": quality,
                "structural_consistency": structural,
            },
        )
        region.element = ExtractedElement(
            id=region.id,
            type=region.type,
            page=region.page,
            bbox=region.bbox,
            bbox_pdf=region.bbox_pdf,
            parent_id=region.parent_id,
            children=region.children,
            content=content,
            provenance=Provenance(
                document_id=document_id,
                page=region.page,
                bbox=region.bbox,
                sources=sources,
            ),
            validation=validation,
            assets=[str(crop_path.relative_to(paths.root))],
            warnings=list({item for item in warnings if region.id in item} ),
        )

    def _native_text_for_region(self, region: Region, native) -> str:
        if region.extra.get("text"):
            return str(region.extra["text"])
        texts = []
        native_by_id = {obj.id: obj for obj in native}
        for native_id in region.native_object_ids:
            obj = native_by_id.get(native_id)
            if obj and isinstance(obj.content, str):
                texts.append(obj.content)
        return "\n".join(texts).strip()
