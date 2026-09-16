"""Standalone PDF profiler (blueprint Step 2 — PROFILE, not EXTRACT).

This module inspects a PDF with PyMuPDF and answers:

    What kind of PDF is this, and what evidence exists on each page?

`main.py` then renders each page to PNG (see page_renderer.py).

It does **not** classify regions (heading / table / chart) and does **not**
extract content. Those happen later (DECOMPOSE / ROUTE / EXTRACT).

Document kinds the profiler distinguishes:

    born_digital  — pages have usable native text objects
    scanned       — pages are mostly raster images with little/no native text
    hybrid        — mix of scanned and born-digital pages

A page can also be mixed-content (native text AND images/vectors on the same
canvas). That is a page-level signal, not a document kind.

Usage:

    python main.py
    python main.py /path/to/file.pdf
    python main.py /path/to/folder
    python main.py a.pdf b.pdf
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import fitz

# --- Heuristic thresholds (tunable while testing) -----------------------------

# Below this many selectable characters, a page is treated as text-poor.
MIN_NATIVE_TEXT_CHARS = 20

# Characters per square inch below which a text-poor page with a large image
# is treated as a scan rather than a sparse digital page.
SCANNED_TEXT_DENSITY_PER_INCH2 = 50.0

# Image-area / page-area ratio that looks like a full-page scan.
LARGE_IMAGE_COVER_SCANNED = 0.60

# Same ratio, but used together with native text to flag an OCR text layer.
LARGE_IMAGE_COVER_OCR = 0.70

# A page with native text plus this many vector drawings is treated as mixed
# content (charts/diagrams), rather than a plain text page with a border.
MIN_VECTORS_FOR_MIXED_CONTENT = 12

# Font-name fragments commonly left by Acrobat / OCR engines.
OCR_FONT_MARKERS = ("ocr", "glyphless", "hiddenhorz", "hiddenvert")


@dataclass
class PageProfile:
    page_number: int
    width: float
    height: float
    rotation: int
    mediabox: list[float]
    native_text_chars: int
    native_text_words: int
    text_density_per_inch2: float
    image_count: int
    image_cover_ratio: float
    vector_count: int
    font_count: int
    fonts: list[str]
    annotation_count: int
    link_count: int
    widget_count: int
    invisible_text_chars: int
    has_ocr_layer: bool
    is_probably_scanned: bool
    is_mixed_content: bool
    page_kind: str
    suggested_text_path: str


@dataclass
class DocumentProfile:
    path: str
    page_count: int
    pdf_version: str | None
    encrypted: bool
    file_size_bytes: int
    page_dimensions: list[dict[str, float]]
    native_text_chars: int
    image_count: int
    vector_count: int
    annotation_count: int
    fonts: list[str]
    metadata: dict[str, str]
    ocr_layer_pages: int
    scanned_pages: int
    digital_pages: int
    mixed_content_pages: int
    is_probably_scanned: bool
    is_hybrid: bool
    is_born_digital: bool
    document_kind: str
    pages: list[PageProfile] = field(default_factory=list)


def open_pdf(path: Path) -> fitz.Document:
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise RuntimeError(f"Unable to open PDF: {exc}") from exc

    if doc.is_encrypted:
        try:
            unlocked = doc.authenticate("")
        except Exception as exc:
            doc.close()
            raise RuntimeError(f"PDF is encrypted: {exc}") from exc
        if not unlocked:
            doc.close()
            raise RuntimeError("PDF is encrypted and requires a password.")
    return doc


def profile_pdf(path: str | Path) -> DocumentProfile:
    pdf_path = Path(path).expanduser().resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = open_pdf(pdf_path)
    try:
        if doc.page_count < 1:
            raise RuntimeError("PDF has no pages.")

        pages: list[PageProfile] = []
        fonts: set[str] = set()
        unique_sizes: dict[tuple[float, float], None] = {}
        totals = {
            "chars": 0,
            "images": 0,
            "vectors": 0,
            "annots": 0,
            "scanned": 0,
            "digital": 0,
            "ocr": 0,
            "mixed": 0,
        }

        for index in range(doc.page_count):
            page = doc.load_page(index)
            page_profile = profile_page(page, index + 1)
            pages.append(page_profile)

            totals["chars"] += page_profile.native_text_chars
            totals["images"] += page_profile.image_count
            totals["vectors"] += page_profile.vector_count
            totals["annots"] += page_profile.annotation_count
            fonts.update(page_profile.fonts)
            unique_sizes[(round(page_profile.width, 2), round(page_profile.height, 2))] = None

            if page_profile.is_probably_scanned:
                totals["scanned"] += 1
            else:
                totals["digital"] += 1
            if page_profile.has_ocr_layer:
                totals["ocr"] += 1
            if page_profile.is_mixed_content:
                totals["mixed"] += 1

        scanned_pages = totals["scanned"]
        digital_pages = totals["digital"]
        is_scanned = scanned_pages == len(pages) and len(pages) > 0
        is_hybrid = scanned_pages > 0 and digital_pages > 0
        is_born_digital = scanned_pages == 0
        document_kind = (
            "scanned" if is_scanned else "hybrid" if is_hybrid else "born_digital"
        )

        metadata = {k: str(v) for k, v in (doc.metadata or {}).items() if v}

        return DocumentProfile(
            path=str(pdf_path),
            page_count=doc.page_count,
            pdf_version=metadata.get("format"),
            encrypted=bool(doc.is_encrypted),
            file_size_bytes=pdf_path.stat().st_size,
            page_dimensions=[
                {"width": width, "height": height} for width, height in unique_sizes
            ],
            native_text_chars=totals["chars"],
            image_count=totals["images"],
            vector_count=totals["vectors"],
            annotation_count=totals["annots"],
            fonts=sorted(fonts),
            metadata=metadata,
            ocr_layer_pages=totals["ocr"],
            scanned_pages=scanned_pages,
            digital_pages=digital_pages,
            mixed_content_pages=totals["mixed"],
            is_probably_scanned=is_scanned,
            is_hybrid=is_hybrid,
            is_born_digital=is_born_digital,
            document_kind=document_kind,
            pages=pages,
        )
    finally:
        doc.close()


def profile_page(page: fitz.Page, page_number: int) -> PageProfile:
    rect = page.rect
    text = page.get_text("text") or ""
    stripped = text.strip()
    native_text_chars = len(stripped)
    native_text_words = len(stripped.split()) if stripped else 0

    images = page.get_images(full=True) or []
    drawings = page.get_drawings() or []
    annots = list(page.annots() or [])
    links = page.get_links() or []
    widgets = list(page.widgets() or [])
    font_names = _font_names(page)
    image_cover = _image_cover_ratio(page, images)
    invisible_text_chars = _invisible_text_chars(page)

    area_inch2 = max(1e-6, (rect.width * rect.height) / (72.0 * 72.0))
    density = native_text_chars / area_inch2

    ocr_font_hit = any(_looks_like_ocr_font(name) for name in font_names)
    has_ocr_layer = bool(
        native_text_chars > 0
        and (
            image_cover > LARGE_IMAGE_COVER_OCR
            or invisible_text_chars > 0
            or ocr_font_hit
        )
    )

    is_probably_scanned = native_text_chars < MIN_NATIVE_TEXT_CHARS or (
        density < SCANNED_TEXT_DENSITY_PER_INCH2
        and image_cover > LARGE_IMAGE_COVER_SCANNED
        and native_text_chars < 400
    )
    # Searchable scans still need OCR-aware routing even though text exists.
    if has_ocr_layer and image_cover > LARGE_IMAGE_COVER_SCANNED:
        is_probably_scanned = True

    is_mixed_content = native_text_chars >= MIN_NATIVE_TEXT_CHARS and (
        len(images) > 0 or len(drawings) >= MIN_VECTORS_FOR_MIXED_CONTENT
    )
    page_kind = _classify_page(is_probably_scanned, is_mixed_content, native_text_chars)
    suggested_text_path = _suggest_text_path(is_probably_scanned, has_ocr_layer, native_text_chars)

    return PageProfile(
        page_number=page_number,
        width=float(rect.width),
        height=float(rect.height),
        rotation=int(page.rotation or 0),
        mediabox=[float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
        native_text_chars=native_text_chars,
        native_text_words=native_text_words,
        text_density_per_inch2=round(density, 2),
        image_count=len(images),
        image_cover_ratio=round(image_cover, 4),
        vector_count=len(drawings),
        font_count=len(font_names),
        fonts=font_names,
        annotation_count=len(annots),
        link_count=len(links),
        widget_count=len(widgets),
        invisible_text_chars=invisible_text_chars,
        has_ocr_layer=has_ocr_layer,
        is_probably_scanned=bool(is_probably_scanned),
        is_mixed_content=bool(is_mixed_content),
        page_kind=page_kind,
        suggested_text_path=suggested_text_path,
    )


def profile_to_dict(profile: DocumentProfile) -> dict[str, Any]:
    return asdict(profile)


def _font_names(page: fitz.Page) -> list[str]:
    names: set[str] = set()
    for font in page.get_fonts() or []:
        if len(font) > 3 and font[3]:
            names.add(str(font[3]))
    return sorted(names)


def _looks_like_ocr_font(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in OCR_FONT_MARKERS)


def _image_cover_ratio(page: fitz.Page, images: list) -> float:
    if not images:
        return 0.0
    page_area = max(1.0, page.rect.width * page.rect.height)
    covered = 0.0
    for image in images:
        xref = image[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            continue
        for rect in rects:
            covered += max(0.0, rect.width * rect.height)
    return min(1.0, covered / page_area)


def _invisible_text_chars(page: fitz.Page) -> int:
    """Count characters drawn with PDF text render mode 3 (invisible).

    OCR overlays often write selectable text this way on top of a scan image.
    """
    try:
        trace = page.get_texttrace() or []
    except Exception:
        return 0

    invisible = 0
    for item in trace:
        render_type = item.get("type")
        if render_type != 3:
            continue
        text = item.get("text") or ""
        if text:
            invisible += len(text)
            continue
        chars = item.get("chars") or []
        invisible += len(chars)
    return invisible


def _classify_page(is_scanned: bool, is_mixed: bool, native_text_chars: int) -> str:
    if is_scanned:
        return "scanned"
    if is_mixed:
        return "mixed_content"
    if native_text_chars >= MIN_NATIVE_TEXT_CHARS:
        return "born_digital"
    return "empty"


def _suggest_text_path(is_scanned: bool, has_ocr_layer: bool, native_text_chars: int) -> str:
    if native_text_chars >= MIN_NATIVE_TEXT_CHARS and not is_scanned:
        return "native_pdf"
    if has_ocr_layer:
        return "native_pdf_then_ocr_verify"
    if is_scanned:
        return "ocr"
    return "native_pdf"


def _summary_lines(profile: DocumentProfile) -> list[str]:
    lines = [
        f"PDF:                  {profile.path}",
        f"Kind:                 {profile.document_kind}",
        f"Pages:                {profile.page_count}",
        f"PDF version:          {profile.pdf_version or 'unknown'}",
        f"Encrypted:            {profile.encrypted}",
        f"Native text chars:    {profile.native_text_chars}",
        f"Images:               {profile.image_count}",
        f"Vector objects:       {profile.vector_count}",
        f"Annotations:          {profile.annotation_count}",
        f"Fonts:                {len(profile.fonts)}",
        f"Scanned pages:        {profile.scanned_pages}",
        f"Digital pages:        {profile.digital_pages}",
        f"OCR-layer pages:      {profile.ocr_layer_pages}",
        f"Mixed-content pages:  {profile.mixed_content_pages}",
        "",
        "Per-page:",
    ]
    for page in profile.pages:
        lines.append(
            "  "
            f"p{page.page_number:<4} "
            f"kind={page.page_kind:<14} "
            f"chars={page.native_text_chars:<6} "
            f"images={page.image_count:<3} "
            f"vectors={page.vector_count:<4} "
            f"cover={page.image_cover_ratio:.2f} "
            f"ocr_layer={str(page.has_ocr_layer):<5} "
            f"path={page.suggested_text_path}"
        )
    return lines


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(
        f"{key}={value}"
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    )


HERE = Path(__file__).resolve().parent
INPUTS_DIR = HERE / "inputs"
OUTPUTS_DIR = HERE / "outputs"


def collect_pdfs(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = raw.expanduser().resolve()
        if path.is_file():
            if path.suffix.lower() != ".pdf":
                raise FileNotFoundError(f"Not a PDF file: {path}")
            found.append(path)
            continue
        if path.is_dir():
            found.extend(
                sorted(
                    p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"
                )
            )
            continue
        raise FileNotFoundError(f"PDF not found: {path}")

    unique: list[Path] = []
    seen: set[Path] = set()
    for path in found:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _document_output_dir(pdf_path: Path, out_arg: Path | None, pdf_count: int) -> Path:
    if out_arg and pdf_count == 1:
        if out_arg.suffix.lower() == ".json":
            return out_arg.parent / pdf_path.stem
        return out_arg
    if out_arg:
        return out_arg / pdf_path.stem
    return OUTPUTS_DIR / pdf_path.stem


def _page_image_map(renders: list[dict[str, Any]], doc_dir: Path) -> dict[int, str]:
    mapping = {int(item["page"]): str(item["path"]) for item in renders if item.get("page")}
    if mapping:
        return mapping
    pages_dir = doc_dir / "pages"
    if not pages_dir.is_dir():
        return {}
    for image in sorted(pages_dir.glob("page_*.png")):
        try:
            page_number = int(image.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        mapping[page_number] = str(image)
    return mapping


def _no_pdfs_message() -> str:
    return (
        "No PDF files found.\n\n"
        "Provide your own PDFs in any of these ways:\n"
        f"  1. Copy .pdf files into: {INPUTS_DIR}\n"
        "     then run:  python main.py\n"
        "  2. Pass a file or folder:\n"
        "     python main.py /path/to/file.pdf\n"
        "     python main.py /path/to/folder\n"
        "  3. Edit PDF_PATHS in main.py"
    )


def process_pdf(
    pdf_path: str | Path,
    output_dir: Path | None = None,
    dpi: int | None = None,
    *,
    render: bool = True,
    extract_native: bool = True,
    detect_regions: bool = True,
    save: bool = True,
    include_native: bool = False,
) -> dict[str, Any]:
    """Run the full extraction pipeline on one PDF and return JSON-ready output."""
    from native_extractor import extract_native_and_detect_regions, native_to_dict
    from ocr_engine import active_ocr_engine
    from page_renderer import DEFAULT_DPI, render_pages, renders_to_dict
    from region_detector import region_to_dict
    from region_router import count_routes, route_regions, routing_plan
    from region_tree import regions_as_nested_tree, tree_stats
    from settings import load_settings
    from text_extractor import count_text_status, extract_text_from_regions, extracted_text_to_dict
    from visual_extractor import count_visual_status, extract_visual_regions, visual_to_dict

    pdf_path = Path(pdf_path).expanduser().resolve()
    if dpi is None:
        dpi = DEFAULT_DPI
    settings = load_settings()
    ocr_name = active_ocr_engine()

    profile = profile_pdf(pdf_path)
    payload = profile_to_dict(profile)
    doc_dir = Path(output_dir) if output_dir else _document_output_dir(pdf_path, None, 1)
    renders: list[dict[str, Any]] = []
    native_counts: dict[str, int] = {}
    region_counts: dict[str, int] = {}
    native_by_page: dict[int, list] = {}
    regions_by_page: dict[int, list] = {}
    tree_summary: dict[str, Any] = {}
    route_counts: dict[str, int] = {}
    text_status: dict[str, int] = {}
    visual_status: dict[str, int] = {}
    text_items: list = []
    visual_items: list = []
    routes: list[dict[str, Any]] = []
    serialized_text: list[dict[str, Any]] = []
    serialized_visuals: list[dict[str, Any]] = []
    serialized_regions: list[dict[str, Any]] = []
    nested_tree: list[dict[str, Any]] = []
    serialized_native: dict[str, list[dict[str, Any]]] = {}
    written: list[str] = []

    if render:
        pages_dir = doc_dir / "pages"
        render_records = render_pages(pdf_path, pages_dir, dpi=dpi)
        renders = renders_to_dict(render_records)

    payload["renders"] = renders

    if extract_native:
        native_by_page, detected = extract_native_and_detect_regions(
            pdf_path, profile.pages, dpi
        )
        if not detect_regions:
            detected = {page: [] for page in native_by_page}
        regions_by_page = detected
        for objects in native_by_page.values():
            for obj in objects:
                native_counts[obj.type] = native_counts.get(obj.type, 0) + 1
        for regions in regions_by_page.values():
            for region in regions:
                region_counts[region.type] = region_counts.get(region.type, 0) + 1
        all_regions = [region for regions in regions_by_page.values() for region in regions]
        tree_summary = tree_stats(all_regions)
        profiles_by_page = {page.page_number: page for page in profile.pages}
        for page_number, regions in regions_by_page.items():
            route_regions(regions, profiles_by_page.get(page_number))
        all_regions = [region for regions in regions_by_page.values() for region in regions]
        route_counts = count_routes(all_regions)
        routes = routing_plan(all_regions)

        page_images = _page_image_map(renders, doc_dir)
        crops_dir = doc_dir / "crops"
        for page_number, regions in regions_by_page.items():
            text_items.extend(
                extract_text_from_regions(
                    regions,
                    native_by_page.get(page_number, []),
                    profiles_by_page.get(page_number),
                    page_images.get(page_number),
                    crops_dir,
                )
            )
            visual_items.extend(
                extract_visual_regions(
                    regions,
                    page_images.get(page_number),
                    crops_dir,
                )
            )
        text_status = count_text_status(text_items)
        visual_status = count_visual_status(visual_items)
        serialized_text = [extracted_text_to_dict(item) for item in text_items]
        serialized_visuals = [visual_to_dict(item) for item in visual_items]
        for regions in regions_by_page.values():
            serialized_regions.extend(region_to_dict(region) for region in regions)
            nested_tree.extend(regions_as_nested_tree(regions))
        if include_native:
            serialized_native = {
                str(page_number): [native_to_dict(obj) for obj in objects]
                for page_number, objects in native_by_page.items()
            }

    payload["native_object_counts"] = native_counts
    payload["region_counts"] = region_counts
    payload["region_tree"] = tree_summary
    payload["route_counts"] = route_counts
    payload["text_status"] = text_status
    payload["visual_status"] = visual_status
    payload["ocr_engine"] = ocr_name
    payload["vlm_model"] = settings["euri_vlm_model"]
    payload["vlm_provider"] = "euron"
    payload["output_dir"] = str(doc_dir)

    if save:
        doc_dir.mkdir(parents=True, exist_ok=True)
        profile_path = doc_dir / "profile.json"
        profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written.append(str(profile_path))
        if renders:
            pages_json = doc_dir / "pages.json"
            pages_json.write_text(json.dumps(renders, indent=2), encoding="utf-8")
            written.append(str(pages_json))

        if native_by_page:
            native_dir = doc_dir / "native"
            native_dir.mkdir(parents=True, exist_ok=True)
            for page_number, objects in native_by_page.items():
                page_path = native_dir / f"page_{page_number:03d}.json"
                page_path.write_text(
                    json.dumps([native_to_dict(obj) for obj in objects], indent=2),
                    encoding="utf-8",
                )
            written.append(str(native_dir))

        if regions_by_page:
            regions_dir = doc_dir / "regions"
            regions_dir.mkdir(parents=True, exist_ok=True)
            for page_number, regions in regions_by_page.items():
                serialized = [region_to_dict(region) for region in regions]
                page_path = regions_dir / f"page_{page_number:03d}.json"
                page_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
            regions_json = doc_dir / "regions.json"
            regions_json.write_text(json.dumps(serialized_regions, indent=2), encoding="utf-8")
            written.append(str(regions_json))
            tree_path = doc_dir / "region_tree.json"
            tree_path.write_text(json.dumps(nested_tree, indent=2), encoding="utf-8")
            written.append(str(tree_path))
            routes_path = doc_dir / "routes.json"
            routes_path.write_text(json.dumps(routes, indent=2), encoding="utf-8")
            written.append(str(routes_path))

        if serialized_text:
            text_dir = doc_dir / "text"
            text_dir.mkdir(parents=True, exist_ok=True)
            by_page: dict[int, list] = {}
            for item in serialized_text:
                by_page.setdefault(item["page"], []).append(item)
            for page_number, items in by_page.items():
                page_path = text_dir / f"page_{page_number:03d}.json"
                page_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
            text_json = doc_dir / "text.json"
            text_json.write_text(json.dumps(serialized_text, indent=2), encoding="utf-8")
            written.append(str(text_json))

        if serialized_visuals:
            visuals_json = doc_dir / "visuals.json"
            visuals_json.write_text(json.dumps(serialized_visuals, indent=2), encoding="utf-8")
            written.append(str(visuals_json))

    result: dict[str, Any] = {
        "document": pdf_path.name,
        "output_dir": str(doc_dir),
        "files": written,
        "summary": payload,
        "summary_text": _pipeline_summary_text(profile, payload, renders, doc_dir),
        "text": serialized_text,
        "visuals": serialized_visuals,
        "regions": serialized_regions,
        "region_tree": nested_tree,
        "routes": routes,
        "pages": renders,
    }
    if include_native:
        result["native"] = serialized_native
    return result


def main(argv: list[str] | None = None) -> int:
    from ocr_engine import active_ocr_engine
    from page_renderer import DEFAULT_DPI
    from settings import load_settings

    settings = load_settings()
    ocr_name = active_ocr_engine()

    parser = argparse.ArgumentParser(
        description="Profile, render, detect regions, route extractors, and extract text/visuals."
    )
    parser.add_argument(
        "pdfs",
        nargs="*",
        help="PDF files or folders. If omitted, all PDFs in inputs/ are used.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output folder. Defaults to outputs/<pdf-stem>/.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help=f"Render DPI (default: {DEFAULT_DPI}). Keep this stable so bboxes stay aligned.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print JSON instead of the human-readable summary",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not write profile / pages JSON files",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Profile only; skip writing page PNGs",
    )
    parser.add_argument(
        "--no-native",
        action="store_true",
        help="Skip native object extraction and region detection",
    )
    parser.add_argument(
        "--no-regions",
        action="store_true",
        help="Extract native objects but skip region detection",
    )
    args = parser.parse_args(argv)

    requested = [Path(item) for item in args.pdfs] if args.pdfs else [INPUTS_DIR]
    if not args.pdfs:
        INPUTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        pdf_paths = collect_pdfs(requested)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not pdf_paths:
        print(_no_pdfs_message(), file=sys.stderr)
        return 1

    payloads: list[dict[str, Any]] = []
    summaries: list[str] = []
    written: list[str] = []
    failed = 0

    for pdf_path in pdf_paths:
        doc_dir = _document_output_dir(pdf_path, args.out, len(pdf_paths))
        try:
            result = process_pdf(
                pdf_path,
                output_dir=doc_dir,
                dpi=args.dpi,
                render=not args.no_render,
                extract_native=not args.no_native,
                detect_regions=not args.no_regions,
                save=not args.no_save,
            )
        except Exception as exc:
            print(f"error: {pdf_path}: {exc}", file=sys.stderr)
            failed += 1
            continue

        payload = result["summary"]
        payloads.append(payload)
        written.extend(result.get("files") or [])
        summaries.append(result.get("summary_text") or "")

    if not payloads:
        return 1

    if args.as_json:
        print(json.dumps(payloads if len(payloads) > 1 else payloads[0], indent=2))
    else:
        print("\n\n".join(summaries))
        if written:
            print("\nWrote:")
            for path in written:
                print(f"  {path}")

    return 1 if failed else 0


def _pipeline_summary_text(
    profile: DocumentProfile,
    payload: dict[str, Any],
    renders: list[dict[str, Any]],
    doc_dir: Path,
) -> str:
    native_counts = payload.get("native_object_counts") or {}
    region_counts = payload.get("region_counts") or {}
    tree_summary = payload.get("region_tree") or {}
    route_counts = payload.get("route_counts") or {}
    text_status = payload.get("text_status") or {}
    visual_status = payload.get("visual_status") or {}
    summary = _summary_lines(profile)
    if renders:
        first = renders[0]
        summary.extend(
            [
                "",
                f"Rendered pages:      {len(renders)} @ {first['dpi']} DPI",
                f"Page image size:     {first['width_px']} × {first['height_px']} px",
                f"Pages folder:        {doc_dir / 'pages'}",
            ]
        )
    if native_counts:
        summary.extend(
            [
                "",
                f"Native objects:      {sum(native_counts.values())}",
                f"  {_format_counts(native_counts)}",
            ]
        )
    if region_counts:
        summary.extend(
            [
                f"Regions:             {sum(region_counts.values())}",
                f"  {_format_counts(region_counts)}",
            ]
        )
    if tree_summary:
        relations = tree_summary.get("relations") or {}
        summary.extend(
            [
                f"Region tree:         {tree_summary.get('root_count', 0)} roots, "
                f"{tree_summary.get('nested_count', 0)} nested",
            ]
        )
        if relations:
            summary.append(f"  {_format_counts(relations)}")
    if route_counts:
        summary.extend(
            [
                f"Routes:              {sum(route_counts.values())} engine assignments",
                f"  {_format_counts(route_counts)}",
            ]
        )
    if text_status:
        summary.extend(
            [
                f"Text extracted:      {sum(text_status.values())} text regions",
                f"  {_format_counts(text_status)}",
            ]
        )
    if visual_status:
        summary.extend(
            [
                f"Visual VLM:          {sum(visual_status.values())} regions",
                f"  {_format_counts(visual_status)}",
            ]
        )
    summary.extend(
        [
            "",
            f"OCR engine:          {payload.get('ocr_engine')}",
            f"VLM:                 euron/{payload.get('vlm_model')}",
        ]
    )
    return "\n".join(summary)


if __name__ == "__main__":
    raise SystemExit(main())
