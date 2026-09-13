# PDF extraction routing reference

Read this when changing thresholds, Docling profiles, Gemini grouping, or fallback.

## Inspection signals

Per-page features from `PdfInspector` (`app/inspection/pdf_inspector.py`):

- Text: character/word/line/span counts, printable / replacement / control ratios, coverage, duplicate lines, overlapping boxes
- Images: count, largest and total coverage, near-full-page raster (≥ 0.80), DPI estimate
- Layout: columns, block-order irregularity, vector drawings, table/figure candidates, formula/code-like lines

Page classes written into `routing_hints`:

| Hint | Condition |
|---|---|
| `probable_scan` | `character_count < 100` and `largest_image_coverage ≥ 0.80` |
| `pymupdf_fast_path` | See thresholds below |
| `probable_complex_table` | ≥ 2 table candidates, or 1 candidate and layout complexity ≥ 0.45 |
| `figure_regions` | Image coverage in `[groq_min_figure_coverage, groq_max_figure_coverage)` |

## PyMuPDF fast-path defaults

From `app/config.py` (env overrides allowed):

| Setting | Default |
|---|---|
| `PYMUPDF_MIN_CHARACTERS` | 500 |
| `PYMUPDF_MIN_PRINTABLE_RATIO` | 0.95 |
| `PYMUPDF_MAX_REPLACEMENT_RATIO` | 0.01 |
| `PYMUPDF_MAX_IMAGE_COVERAGE` | 0.35 |
| `PYMUPDF_MAX_LAYOUT_COMPLEXITY` | 0.45 |

Fast path also requires: not a complex table, not a scan.

Usable native text (non-fast-path digital plan): printable ≥ 0.90 and replacement ≤ 0.02.

## Privacy

`ExtractionPolicy.allow_managed_apis` gates Gemini and Groq.

| Policy | Scan route | Uncertain digital |
|---|---|---|
| Managed allowed + `EURI_API_KEY` | Gemini OCR | Gemini, 1-page group (`options_hash=uncertain`) |
| Managed allowed, Gemini missing | Do not route | Docling `digital-layout` |
| Managed prohibited | Docling `private-ocr` | Docling `digital-layout` |

Groq requires all of: `visual_understanding`, `GROQ_VISUAL_EXTRACTION_ENABLED`, `GROQ_API_KEY`, and managed APIs allowed.

## Docling profiles

| Profile | Task kind | OCR | Tables | Code | Formulas |
|---|---|---|---|---|---|
| `digital-layout` | `layout` | no | no | no | no |
| `digital-table` | `table_structure` | no | yes | no | no |
| `formula-code` | `formula_code` | no | yes | yes | yes |
| `private-ocr` | `ocr` | yes | yes | no | no |

Default profile is `digital-layout`. One Docling call must use a single profile. Mixed profiles in one adapter call is an error.

Remote Docling services stay off (`enable_remote_services=false`).

## Grouping

Adjacent pages with the same extractor, profile, kind, options, and privacy mode are grouped.

| Extractor / options | Max pages per group |
|---|---|
| Gemini (normal scans) | `GEMINI_TARGET_PAGES_PER_GROUP` (5), cap `GEMINI_MAX_PAGES_PER_GROUP` (10) |
| Gemini `uncertain` / fallback / retry | 1 |
| Docling | `DOCLING_MAX_PAGES_PER_GROUP` (30) |
| Groq / `visual` | 1 |
| PyMuPDF | effectively unlimited (10000) |

Context-only neighbor pages may be passed in but must not be written as extracted output.

## Gemini

- Provider: Euron (`EURI_API_KEY`, `gemini-2.5-flash` by default)
- Render pages to PNG, send images, parse JSON only
- Extract; do not summarize, paraphrase, or invent text
- Bboxes in the model response are page fractions (0–1), top-left; convert to PDF points in the adapter
- Prompt version is settings-pinned (`GEMINI_EXTRACTION_PROMPT_VERSION`)
- Budget guard caps Gemini retries at 2 when enabled

## Fallback map

Chosen by reason code. Attempts capped by `EXTRACTION_MAX_ATTEMPTS_PER_PAGE` (3). Forced extractor disables fallback.

| Code | First target | If managed APIs off / Gemini missing |
|---|---|---|
| `NATIVE_TEXT_CORRUPT` | Gemini | Docling `private-ocr` |
| `NATIVE_TEXT_MISSING` | Gemini | Docling `private-ocr` |
| `READING_ORDER_INVALID` | Docling `digital-layout` | then Gemini if allowed |
| `TABLE_STRUCTURE_INVALID` | Gemini | Docling `private-ocr` |
| `TABLE_EMPTY` | Gemini | Docling `private-ocr` |
| `FORMULA_MISSING` | Docling `formula-code` | then Gemini if allowed |
| `VISUAL_MEANING_MISSING` | Groq vision (figure regions with empty text) | skip |
| `PYMUPDF_EXTRACTION_FAILED` | Docling `digital-layout` | then Gemini if allowed |
| `DOCLING_EXTRACTION_FAILED` | Gemini | Docling `private-ocr` |
| `GEMINI_TIMEOUT` / `GEMINI_EXTRACTION_FAILED` / `GEMINI_RESPONSE_INVALID` | retry Gemini once (transient) | Docling `private-ocr` |
| `EXTRACTION_GROUP_TIMEOUT` | Gemini | Docling `private-ocr` |

Skip fallback (no retry) for: `SCANNED_PAGE_NOT_EXTRACTED`, `GEMINI_NOT_CONFIGURED`, `MANAGED_APIS_PROHIBITED`, `PAGE_NOT_ROUTED` — unless another trigger code is also present.

Do not retry the same extractor+profile except for transient codes, and then at most once.

## Validation

Hard failures (page fails): `NATIVE_TEXT_CORRUPT`, `NATIVE_TEXT_MISSING`, `READING_ORDER_INVALID`, `BBOX_OUT_OF_BOUNDS`, `BBOX_NON_POSITIVE_AREA`, `TABLE_STRUCTURE_INVALID`, `TABLE_EMPTY`, `VISUAL_CROP_MISSING`.

Soft failures lower confidence: printable/replacement issues, duplicate lines, OCR too short, overlap, table markdown/html problems, missing formula/figure meaning.

Min validation confidence default: `0.85`. Routing, parser, and validation confidence stay separate.

## Canonical output

Element types: `heading`, `paragraph`, `list`, `table`, `picture`, `chart`, `diagram`, `formula`, `code`, `key_value`, `form_field`, `header`, `footer`, `footnote`, `page_number`, `unknown`.

Each element keeps: stable id after final reading order, bbox in PDF points top-left, extractor/adapter/model/profile/prompt versions, source page.

A document is ready for chunking (downstream, not this app) when `document.json` validates, original page identity survived grouping/retries, managed APIs were not called when prohibited, and failed pages are explicit.
