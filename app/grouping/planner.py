from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.config import Settings
from app.models.inspection import DocumentInspection
from app.models.routing import ExtractionGroup, ExtractionTask, PagePlan


@dataclass(frozen=True)
class GroupKey:
    document_id: str
    extractor: str
    profile: str | None
    kind: str
    options_hash: str | None
    privacy_mode: str | None


class GroupPlanner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_groups(
        self,
        plans: list[PagePlan],
        *,
        document_id: str,
        inspection: DocumentInspection | None = None,
    ) -> list[ExtractionGroup]:
        by_key: dict[GroupKey, list[ExtractionTask]] = defaultdict(list)
        for plan in plans:
            for task in plan.tasks:
                by_key[_key(task, document_id)].append(task)

        groups: list[ExtractionGroup] = []
        counter = 1
        for key, tasks in by_key.items():
            ordered = sorted(tasks, key=lambda item: item.page)
            max_size = self._max_group_size(key)
            for chunk in _consecutive_chunks([task.page for task in ordered], max_size):
                chunk_tasks = [task for task in ordered if task.page in set(chunk)]
                context = self._context_pages(chunk, plans, inspection)
                groups.append(
                    ExtractionGroup(
                        group_id=f"{key.extractor}-{key.kind}-{counter:04d}",
                        document_id=document_id,
                        extractor=key.extractor,
                        profile=key.profile,
                        kind=key.kind,
                        pages=chunk,
                        options_hash=key.options_hash,
                        privacy_mode=key.privacy_mode,
                        context_pages=context,
                        tasks=chunk_tasks,
                        metadata={"temporary_pages": list(range(1, len(chunk) + 1)), "original_pages": chunk},
                    )
                )
                counter += 1
        return groups

    def _max_group_size(self, key: GroupKey) -> int:
        if key.options_hash in {"uncertain", "fallback", "retry", "visual"}:
            return 1
        if key.extractor == "groq-vision":
            return 1
        if key.extractor == "gemini":
            return max(1, min(self._settings.gemini_target_pages_per_group, self._settings.gemini_max_pages_per_group))
        if key.extractor == "docling":
            return max(1, self._settings.docling_max_pages_per_group)
        return 10_000

    @staticmethod
    def _context_pages(
        pages: list[int],
        plans: list[PagePlan],
        inspection: DocumentInspection | None,
    ) -> list[int]:
        if inspection is None:
            return []
        plan_pages = {plan.page for plan in plans}
        by_inspection = {page.page: page for page in inspection.pages}
        context: list[int] = []
        for page_number in pages:
            page = by_inspection.get(page_number)
            if page is None:
                continue
            if page.continuity.table_continues_to_next or page.continuity.figure_caption_split:
                neighbor = page_number + 1
                if neighbor in plan_pages and neighbor not in pages and neighbor not in context:
                    context.append(neighbor)
        return context


def _key(task: ExtractionTask, document_id: str) -> GroupKey:
    return GroupKey(
        document_id=task.document_id or document_id,
        extractor=task.extractor,
        profile=task.profile,
        kind=task.kind,
        options_hash=task.options_hash,
        privacy_mode=task.privacy_mode,
    )


def _consecutive_chunks(pages: list[int], max_size: int) -> list[list[int]]:
    if not pages:
        return []
    ordered = sorted(set(pages))
    runs: list[list[int]] = [[ordered[0]]]
    for page in ordered[1:]:
        if page == runs[-1][-1] + 1:
            runs[-1].append(page)
        else:
            runs.append([page])
    chunks: list[list[int]] = []
    size = max(1, max_size)
    for run in runs:
        for start in range(0, len(run), size):
            chunks.append(run[start : start + size])
    return chunks
