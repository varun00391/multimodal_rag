from app.models.document import DocumentProfile
from app.models.page import PageProfile


def classify_document(profile: DocumentProfile) -> str:
    if profile.is_probably_scanned:
        return "scanned"
    if profile.is_hybrid:
        return "hybrid"
    return "born_digital"


def classify_page(page_profile: PageProfile) -> str:
    if page_profile.is_probably_scanned:
        return "scanned"
    if page_profile.image_count > 0 and page_profile.native_text_chars > 0:
        return "hybrid"
    return "born_digital"
