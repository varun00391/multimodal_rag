from app.inspection.features import (
    ends_with_terminal_punctuation,
    looks_like_list_line,
    looks_like_table_header,
)
from app.models.inspection import ContinuitySignals, PageInspection


def compute_page_continuity(
    current: PageInspection,
    next_page: PageInspection | None,
) -> ContinuitySignals:
    signals = ContinuitySignals()
    if next_page is None:
        return signals

    current_text = str(current.metadata.get("sample_text", ""))
    next_text = str(next_page.metadata.get("sample_text", ""))

    if current.layout.table_candidate_count > 0 and current.height > 0:
        signals.table_continues_to_next = current_text.endswith("|") or (
            current.layout.table_candidate_count > 0
            and current.page * current.height > 0
            and current.text.text_coverage > 0.2
        )

    if next_text:
        first_line = next_text.splitlines()[0] if next_text.splitlines() else ""
        signals.repeated_table_header_on_next = looks_like_table_header(first_line)

    signals.incomplete_sentence = bool(current_text) and not ends_with_terminal_punctuation(
        current_text
    )
    signals.continuing_list = any(
        looks_like_list_line(line) for line in current_text.splitlines()[-3:]
    ) and any(looks_like_list_line(line) for line in next_text.splitlines()[:3])
    signals.continuing_columns_or_fonts = (
        current.layout.probable_columns > 1
        and current.layout.probable_columns == next_page.layout.probable_columns
        and bool(current.text.font_size_distribution)
        and current.text.font_size_distribution == next_page.text.font_size_distribution
    )
    return signals


def enrich_document_continuity(pages: list[PageInspection]) -> list[ContinuitySignals]:
    continuity: list[ContinuitySignals] = []
    for index, page in enumerate(pages):
        next_page = pages[index + 1] if index + 1 < len(pages) else None
        page_continuity = compute_page_continuity(page, next_page)
        page.continuity = page_continuity
        continuity.append(page_continuity)
    return continuity
