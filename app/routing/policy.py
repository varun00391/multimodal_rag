from __future__ import annotations

from app.adapters.docling_profiles import (
    PROFILE_DIGITAL_LAYOUT,
    PROFILE_DIGITAL_TABLE,
    PROFILE_FORMULA_CODE,
    PROFILE_PRIVATE_OCR,
    parse_extractor_ref,
    require_profile,
    resolve_docling_profile,
)
from app.config import Settings
from app.models.inspection import DocumentInspection, PageInspection
from app.models.jobs import ExtractionPolicy
from app.models.routing import ExtractionTask, PagePlan
from app.routing.privacy import managed_apis_allowed, privacy_mode

SUPPORTED_FORCE_EXTRACTORS = {
    "pymupdf",
    "docling",
    "docling:digital-layout",
    "docling:digital-table",
    "docling:formula-code",
    "docling:private-ocr",
    "gemini",
    "groq-vision",
}


class RoutingPolicy:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_plans(
        self,
        inspection: DocumentInspection,
        policy: ExtractionPolicy,
        *,
        document_id: str,
        gemini_ready: bool,
        groq_ready: bool = False,
    ) -> list[PagePlan]:
        if policy.force_extractor and policy.force_extractor not in SUPPORTED_FORCE_EXTRACTORS:
            raise ValueError(f"Unsupported force_extractor '{policy.force_extractor}'.")
        return [
            self.plan_page(
                page,
                policy,
                document_id=document_id,
                gemini_ready=gemini_ready,
                groq_ready=groq_ready,
            )
            for page in inspection.pages
        ]

    def plan_page(
        self,
        page: PageInspection,
        policy: ExtractionPolicy,
        *,
        document_id: str,
        gemini_ready: bool,
        groq_ready: bool = False,
    ) -> PagePlan:
        if policy.force_extractor:
            return self._forced_plan(
                page,
                policy,
                document_id=document_id,
                gemini_ready=gemini_ready,
                groq_ready=groq_ready,
            )

        mode = privacy_mode(policy)
        if page.probable_scan:
            plan = self._scan_plan(
                page,
                document_id=document_id,
                allow_managed=managed_apis_allowed(policy),
                gemini_ready=gemini_ready,
                privacy=mode,
            )
        else:
            plan = self._digital_plan(
                page,
                document_id=document_id,
                allow_managed=managed_apis_allowed(policy),
                gemini_ready=gemini_ready,
                privacy=mode,
            )
        return self._add_visual_tasks(
            plan,
            page,
            policy,
            document_id=document_id,
            groq_ready=groq_ready,
        )

    def _forced_plan(
        self,
        page: PageInspection,
        policy: ExtractionPolicy,
        *,
        document_id: str,
        gemini_ready: bool,
        groq_ready: bool = False,
    ) -> PagePlan:
        extractor, profile = parse_extractor_ref(policy.force_extractor)
        if extractor in {"groq-vision", "groq"}:
            if not managed_apis_allowed(policy):
                return PagePlan(
                    page=page.page,
                    primary_route=None,
                    reasons=["Forced Groq vision blocked because managed APIs are prohibited"],
                )
            if not groq_ready:
                return PagePlan(
                    page=page.page,
                    primary_route=None,
                    reasons=["Forced Groq vision blocked because GROQ_API_KEY is not configured"],
                )
            plan = PagePlan(
                page=page.page,
                primary_route="groq-vision",
                reasons=["Forced Groq vision extraction path"],
            )
            return self._add_visual_tasks(
                plan,
                page,
                policy,
                document_id=document_id,
                groq_ready=True,
                force=True,
            )
        if extractor == "gemini":
            if not managed_apis_allowed(policy):
                return PagePlan(
                    page=page.page,
                    primary_route=None,
                    reasons=["Forced Gemini blocked because managed APIs are prohibited"],
                )
            if not gemini_ready:
                return PagePlan(
                    page=page.page,
                    primary_route=None,
                    reasons=["Forced Gemini blocked because EURI_API_KEY is not configured"],
                )
            task = _task(document_id, page.page, "ocr", "gemini", privacy_mode="managed", required=True)
            return PagePlan(
                page=page.page,
                primary_route="gemini",
                tasks=[task],
                reasons=["Forced Gemini extraction path"],
            )
        if extractor == "docling":
            spec = require_profile(profile or resolve_docling_profile("docling") or PROFILE_DIGITAL_LAYOUT)
            kind = {
                PROFILE_DIGITAL_LAYOUT: "layout",
                PROFILE_DIGITAL_TABLE: "table_structure",
                PROFILE_FORMULA_CODE: "formula_code",
                PROFILE_PRIVATE_OCR: "ocr",
            }[spec.name]
            privacy = "local" if spec.name == PROFILE_PRIVATE_OCR else None
            task = _task(
                document_id,
                page.page,
                kind,
                "docling",
                profile=spec.name,
                privacy_mode=privacy,
                required=True,
            )
            return PagePlan(
                page=page.page,
                primary_route="docling",
                tasks=[task],
                reasons=[f"Forced Docling profile '{spec.name}'"],
            )
        task = _task(document_id, page.page, "native_text", "pymupdf", required=True)
        return PagePlan(
            page=page.page,
            primary_route="pymupdf",
            tasks=[task],
            reasons=["Forced PyMuPDF extraction path"],
        )

    def _scan_plan(
        self,
        page: PageInspection,
        *,
        document_id: str,
        allow_managed: bool,
        gemini_ready: bool,
        privacy: str,
    ) -> PagePlan:
        if allow_managed and gemini_ready:
            task = _task(
                document_id,
                page.page,
                "ocr",
                "gemini",
                privacy_mode="managed",
                required=True,
            )
            return PagePlan(
                page=page.page,
                primary_route="gemini",
                tasks=[task],
                reasons=["Scanned page routed to managed Gemini OCR"],
            )
        if allow_managed and not gemini_ready:
            return PagePlan(
                page=page.page,
                primary_route=None,
                reasons=["Scanned page needs Gemini but the managed extractor is not configured"],
            )
        task = _task(
            document_id,
            page.page,
            "ocr",
            "docling",
            profile=PROFILE_PRIVATE_OCR,
            privacy_mode="local",
            required=True,
        )
        return PagePlan(
            page=page.page,
            primary_route="docling",
            tasks=[task],
            reasons=["Scanned page routed to local Docling OCR because managed APIs are prohibited"],
        )

    def _digital_plan(
        self,
        page: PageInspection,
        *,
        document_id: str,
        allow_managed: bool,
        gemini_ready: bool,
        privacy: str,
    ) -> PagePlan:
        tasks: list[ExtractionTask] = []
        reasons: list[str] = []
        primary: str | None = None

        if page.use_pymupdf_fast_path:
            tasks.append(_task(document_id, page.page, "native_text", "pymupdf", required=True))
            return PagePlan(
                page=page.page,
                primary_route="pymupdf",
                tasks=tasks,
                reasons=["PyMuPDF fast path: dense printable native text"],
            )

        has_native_text = (
            page.text.character_count > 0
            and page.text.printable_ratio >= 0.90
            and page.text.replacement_character_ratio <= 0.02
        )
        if has_native_text:
            tasks.append(
                _task(
                    document_id,
                    page.page,
                    "native_text",
                    "pymupdf",
                    privacy_mode=privacy,
                    required=True,
                )
            )
            primary = "pymupdf"
            reasons.append("Native text layer is usable")

        formula_or_code = page.layout.formula_like_regions > 0 or page.layout.code_like_regions > 0
        if formula_or_code:
            tasks.append(
                _task(
                    document_id,
                    page.page,
                    "formula_code",
                    "docling",
                    profile=PROFILE_FORMULA_CODE,
                    privacy_mode=privacy,
                    required=True,
                )
            )
            primary = primary or "docling"
            reasons.append("Formula or code structure needs Docling")
        elif page.probable_complex_table:
            tasks.append(
                _task(
                    document_id,
                    page.page,
                    "table_structure",
                    "docling",
                    profile=PROFILE_DIGITAL_TABLE,
                    privacy_mode=privacy,
                    required=True,
                )
            )
            primary = primary or "docling"
            reasons.append("Complex digital table routed to Docling")
        elif not has_native_text:
            if allow_managed and gemini_ready:
                tasks.append(
                    _task(
                        document_id,
                        page.page,
                        "ocr",
                        "gemini",
                        privacy_mode="managed",
                        required=True,
                        options_hash="uncertain",
                    )
                )
                primary = "gemini"
                reasons.append("Uncertain digital page routed to one-page Gemini")
            else:
                tasks.append(
                    _task(
                        document_id,
                        page.page,
                        "layout",
                        "docling",
                        profile=PROFILE_DIGITAL_LAYOUT,
                        privacy_mode=privacy,
                        required=True,
                    )
                )
                primary = "docling"
                reasons.append("Uncertain digital page routed to Docling layout")

        if not tasks:
            tasks.append(
                _task(
                    document_id,
                    page.page,
                    "native_text",
                    "pymupdf",
                    privacy_mode=privacy,
                    required=True,
                )
            )
            primary = "pymupdf"
            reasons.append("Conservative PyMuPDF fallback")

        return PagePlan(page=page.page, primary_route=primary, tasks=tasks, reasons=reasons)

    def _add_visual_tasks(
        self,
        plan: PagePlan,
        page: PageInspection,
        policy: ExtractionPolicy,
        *,
        document_id: str,
        groq_ready: bool,
        force: bool = False,
    ) -> PagePlan:
        if not page.figure_regions:
            if force:
                plan.reasons.append("No meaningful visual regions were detected")
            return plan
        if not force and not (
            policy.visual_understanding
            and self._settings.groq_visual_extraction_enabled
            and groq_ready
            and managed_apis_allowed(policy)
        ):
            return plan
        for region in page.figure_regions:
            plan.tasks.append(
                _task(
                    document_id,
                    page.page,
                    "visual_understanding",
                    "groq-vision",
                    privacy_mode="managed",
                    required=False,
                    options_hash="visual",
                    region=list(region),
                )
            )
        plan.reasons.append("Meaningful visual regions routed to Groq vision")
        if plan.primary_route is None:
            plan.primary_route = "groq-vision"
        return plan


def _task(
    document_id: str,
    page: int,
    kind: str,
    extractor: str,
    *,
    profile: str | None = None,
    privacy_mode: str | None = None,
    required: bool = False,
    options_hash: str | None = None,
    region: list[float] | None = None,
) -> ExtractionTask:
    return ExtractionTask(
        document_id=document_id,
        page=page,
        kind=kind,
        extractor=extractor,
        profile=profile,
        required=required,
        options_hash=options_hash,
        privacy_mode=privacy_mode,
        region=region,
    )
