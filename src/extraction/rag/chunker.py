from __future__ import annotations

from extraction.models.cdr import CanonicalDocument, Element, TableData, Unit
from extraction.rag.models import ChildChunk
from extraction.settings import Settings


def table_to_markdown(table: TableData) -> str:
    columns = [str(column) for column in table.columns] if table.columns else []
    rows = table.rows or []
    width = len(columns)
    if width == 0:
        width = max((len(row) for row in rows), default=0)
        columns = [f"c{index}" for index in range(1, width + 1)]
    header = _markdown_row(columns, width)
    divider = "| " + " | ".join("---" for _ in range(width)) + " |"
    body = [_markdown_row(row, width) for row in rows]
    return "\n".join([header, divider, *body])


def _markdown_row(cells: list[str], width: int) -> str:
    padded = [str(cell or "").replace("\n", " ").strip() for cell in cells]
    if len(padded) < width:
        padded.extend([""] * (width - len(padded)))
    return "| " + " | ".join(padded[:width]) + " |"


def _split_with_overlap(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = max(size - overlap, 1)
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += step
    return [chunk for chunk in chunks if chunk]


def _pack_paragraphs(parts: list[tuple[str, str]], size: int, overlap: int) -> list[tuple[list[str], str]]:
    packed: list[tuple[list[str], str]] = []
    buffer_ids: list[str] = []
    buffer_text: list[str] = []
    buffer_len = 0

    def flush() -> None:
        nonlocal buffer_ids, buffer_text, buffer_len
        text = "\n\n".join(buffer_text).strip()
        if text:
            packed.append((list(buffer_ids), text))
        buffer_ids = []
        buffer_text = []
        buffer_len = 0

    for element_id, text in parts:
        text = text.strip()
        if not text:
            continue
        if len(text) > size:
            flush()
            for piece in _split_with_overlap(text, size, overlap):
                packed.append(([element_id], piece))
            continue
        extra = len(text) + (2 if buffer_text else 0)
        if buffer_text and buffer_len + extra > size:
            flush()
        buffer_ids.append(element_id)
        buffer_text.append(text)
        buffer_len += extra
    flush()
    return packed


def _table_row_groups(table: TableData, size: int) -> list[str]:
    markdown = table_to_markdown(table)
    if len(markdown) <= size:
        return [markdown]
    columns = [str(column) for column in table.columns] if table.columns else []
    rows = table.rows or []
    width = len(columns) or max((len(row) for row in rows), default=0)
    if not columns:
        columns = [f"c{index}" for index in range(1, width + 1)]
    header = _markdown_row(columns, width)
    divider = "| " + " | ".join("---" for _ in range(width)) + " |"
    prefix = f"{header}\n{divider}"
    groups: list[str] = []
    current_rows: list[str] = []
    current = prefix
    for row in rows:
        line = _markdown_row(row, width)
        candidate = f"{current}\n{line}"
        if current_rows and len(candidate) > size:
            groups.append(current)
            current = f"{prefix}\n{line}"
            current_rows = [line]
        else:
            current = candidate
            current_rows.append(line)
    if current_rows:
        groups.append(current)
    return groups or [markdown]


def _prefix(filename: str, unit: Unit, extra: str = "") -> str:
    label = f"{filename} | {unit.unit_type} {unit.index}"
    if unit.label:
        label += f" ({unit.label})"
    if unit.t_start is not None or unit.t_end is not None:
        start = unit.t_start if unit.t_start is not None else ""
        end = unit.t_end if unit.t_end is not None else ""
        label += f" | {start}-{end}s"
    if extra:
        label += f" | {extra}"
    return label


def _element_text(element: Element) -> str:
    if element.table is not None:
        return table_to_markdown(element.table)
    if (element.text or "").strip():
        return element.text.strip()
    if element.asset_path:
        return f"[image: {element.asset_path}]"
    return ""


def _render_unit(unit: Unit) -> str:
    parts = [_element_text(element) for element in unit.elements]
    return "\n\n".join(part for part in parts if part).strip()


def _make_child(
    *,
    document: CanonicalDocument,
    unit: Unit,
    child_id: str,
    parent_id: str,
    parent_type: str,
    parent_text: str,
    child_text: str,
    element_type: str,
    modality: str,
    element_ids: list[str],
    asset_path: str | None = None,
    extra_prefix: str = "",
) -> ChildChunk:
    filename = document.source.filename
    embed_text = f"{_prefix(filename, unit, extra_prefix)}\n{child_text}".strip()
    return ChildChunk(
        child_id=child_id,
        parent_id=parent_id,
        parent_type=parent_type,
        parent_text=parent_text,
        child_text=child_text,
        embed_text=embed_text,
        element_type=element_type,
        modality=modality,
        unit_type=unit.unit_type,
        unit_index=unit.index,
        element_ids=element_ids,
        asset_path=asset_path,
        t_start=unit.t_start,
        t_end=unit.t_end,
        filename=filename,
        media_type=document.source.media_type,
        document_id=document.document_id,
    )


def chunk_document(document: CanonicalDocument, settings: Settings) -> list[ChildChunk]:
    size = max(settings.rag_chunk_chars, 64)
    overlap = min(max(settings.rag_chunk_overlap, 0), size - 1)
    children: list[ChildChunk] = []
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"{document.document_id}:c:{counter}"

    for unit in document.units:
        unit_parent_id = f"{document.document_id}:unit:{unit.unit_type}:{unit.index}"
        unit_parent_text = _render_unit(unit)
        prose: list[tuple[str, str]] = []
        tables: list[Element] = []
        pictures: list[Element] = []
        for element in unit.elements:
            if element.table is not None:
                tables.append(element)
            elif element.type == "picture" or element.asset_path:
                pictures.append(element)
            elif (element.text or "").strip():
                prose.append((element.element_id, element.text.strip()))

        if not unit_parent_text and not pictures:
            continue

        for element_ids, text in _pack_paragraphs(prose, size, overlap):
            children.append(
                _make_child(
                    document=document,
                    unit=unit,
                    child_id=next_id(),
                    parent_id=unit_parent_id,
                    parent_type="unit",
                    parent_text=unit_parent_text,
                    child_text=text,
                    element_type="paragraph",
                    modality="text",
                    element_ids=element_ids,
                )
            )

        for element in tables:
            markdown = table_to_markdown(element.table) if element.table else ""
            if not markdown:
                continue
            if len(markdown) <= size:
                children.append(
                    _make_child(
                        document=document,
                        unit=unit,
                        child_id=next_id(),
                        parent_id=unit_parent_id,
                        parent_type="unit",
                        parent_text=unit_parent_text,
                        child_text=markdown,
                        element_type="table",
                        modality="text",
                        element_ids=[element.element_id],
                    )
                )
                continue
            table_parent_id = f"{document.document_id}:table:{element.element_id}"
            for group in _table_row_groups(element.table, size):
                children.append(
                    _make_child(
                        document=document,
                        unit=unit,
                        child_id=next_id(),
                        parent_id=table_parent_id,
                        parent_type="table",
                        parent_text=markdown,
                        child_text=group,
                        element_type="table",
                        modality="text",
                        element_ids=[element.element_id],
                        extra_prefix="table",
                    )
                )

        for element in pictures:
            caption = (element.text or "").strip() or f"[image: {element.asset_path}]"
            if not element.asset_path and not (element.text or "").strip():
                continue
            children.append(
                _make_child(
                    document=document,
                    unit=unit,
                    child_id=next_id(),
                    parent_id=unit_parent_id,
                    parent_type="unit",
                    parent_text=unit_parent_text or caption,
                    child_text=caption,
                    element_type="picture",
                    modality="image" if element.asset_path else "text",
                    element_ids=[element.element_id],
                    asset_path=element.asset_path,
                )
            )

    return children
