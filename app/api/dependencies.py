from functools import lru_cache

from fastapi import Depends

from app.adapters.docling_adapter import DoclingAdapter
from app.adapters.gemini_adapter import GeminiAdapter
from app.adapters.groq_vision_adapter import GroqVisionAdapter
from app.adapters.pymupdf_adapter import PyMuPDFAdapter
from app.config import Settings, get_settings
from app.inspection.pdf_inspector import PdfInspector
from app.services.extraction_service import ExtractionService
from app.services.job_service import JobService
from app.storage.jobs import JobStore
from app.storage.workspace import InputValidator, WorkspaceManager


@lru_cache
def get_job_store() -> JobStore:
    return JobStore(get_settings())


@lru_cache
def get_docling_adapter() -> DoclingAdapter:
    return DoclingAdapter(get_settings())


@lru_cache
def get_gemini_adapter() -> GeminiAdapter:
    return GeminiAdapter(get_settings())


@lru_cache
def get_groq_adapter() -> GroqVisionAdapter:
    return GroqVisionAdapter(get_settings())


def get_workspace_manager(settings: Settings = Depends(get_settings)) -> WorkspaceManager:
    return WorkspaceManager(settings)


def get_input_validator(settings: Settings = Depends(get_settings)) -> InputValidator:
    return InputValidator(settings)


def get_inspector(settings: Settings = Depends(get_settings)) -> PdfInspector:
    return PdfInspector(settings)


def get_pymupdf_adapter(settings: Settings = Depends(get_settings)) -> PyMuPDFAdapter:
    return PyMuPDFAdapter(settings)


def get_job_service(job_store: JobStore = Depends(get_job_store)) -> JobService:
    return JobService(job_store)


def get_extraction_service(
    job_service: JobService = Depends(get_job_service),
    settings: Settings = Depends(get_settings),
    inspector: PdfInspector = Depends(get_inspector),
    pymupdf_adapter: PyMuPDFAdapter = Depends(get_pymupdf_adapter),
    docling_adapter: DoclingAdapter = Depends(get_docling_adapter),
    gemini_adapter: GeminiAdapter = Depends(get_gemini_adapter),
    groq_adapter: GroqVisionAdapter = Depends(get_groq_adapter),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
) -> ExtractionService:
    return ExtractionService(
        job_service=job_service,
        settings=settings,
        inspector=inspector,
        pymupdf_adapter=pymupdf_adapter,
        docling_adapter=docling_adapter,
        gemini_adapter=gemini_adapter,
        groq_adapter=groq_adapter,
        workspace_manager=workspace_manager,
    )
