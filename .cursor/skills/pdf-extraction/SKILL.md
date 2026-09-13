---
name: pdf-extraction
description: >-
  Routes and extracts born-digital and scanned PDFs in multimodal_rag_app.
  Use when changing inspection, routing, PyMuPDF, Docling, Gemini OCR, Groq
  vision, fallback, validation, canonical document.json, or when the user
  mentions scanned PDFs, native text, private-ocr, or extraction adapters.
---

# PDF extraction

Page-level extraction for `multimodal_rag_app`. The processor stops at
validated canonical output. Do not add chunking, embeddings, indexing, or RAG.

## Hard constraints

- Route each page independently. Mixed digital/scan documents are normal.
- Privacy before quality: never call Gemini or Groq when `allow_managed_apis` is false.
- Adapters emit canonical elements only. Downstream never sees parser-native objects.
- Do not silently drop failed pages. Record errors and keep successful pages.
- Cleaning is not summarization. Do not rewrite policy language or drop content to save tokens.
- Forced-extractor and compare modes are benchmark-only (`EXTRACTION_BENCHMARK_ENABLED=false` in normal deploys).

## Pipeline

```text
inspect → route → group → extract → validate → fallback → merge → document.json
```

Inspection is local PyMuPDF. It never sends the file to a managed API.

## Decision tree

```text
inspect page
  if probable_scan (chars < 100 AND largest image coverage ≥ 0.80):
      Gemini OCR  if managed APIs allowed and EURI_API_KEY set
      else Docling private-ocr  if managed APIs prohibited
      else do not route (explicit failure, not silent)
  else if pymupdf_fast_path:
      PyMuPDF native_text only
  else:
      usable native text?  → PyMuPDF
      formulas/code?       → + Docling formula-code
      complex table?       → Docling digital-table
      else uncertain       → Gemini (1-page group) or Docling digital-layout
  optional: Groq vision on figure regions when visual_understanding is on
```

Usable native text: `character_count > 0`, printable ratio ≥ 0.90, replacement ratio ≤ 0.02.

PyMuPDF fast-path defaults and the fallback table live in [routing-reference.md](routing-reference.md).

## Adapter roles

| Adapter | Use for | Do not use for |
|---|---|---|
| PyMuPDF | Inspection, native text, fonts, image crops, coordinates | OCR / scans |
| Docling | Complex layout, digital tables, formulas, code, local OCR | Managed-API scans when Gemini is allowed |
| Gemini (Euron) | Scans, damaged text, image tables, forms, handwriting | Local-only tenants |
| Groq vision | Optional chart/diagram descriptions | Primary text extraction |

One page may have layered tasks (PyMuPDF paragraphs + Docling table + Groq chart).

## When changing code

1. Classify the page the same way `PdfInspector` does. Do not invent a fifth parser.
2. Edit the matching file in the map below.
3. Keep output in the canonical schema (`heading`, `paragraph`, `list`, `table`, `picture`, `chart`, `diagram`, `formula`, `code`, `key_value`, `form_field`, `header`, `footer`, `footnote`, `page_number`, `unknown`).
4. Bboxes stay top-left PDF points after merge. Gemini returns 0–1 fractions; convert before canonicalize.
5. Fallback is by validation/error code, not “try every extractor.”
6. Group adjacent compatible pages. Uncertain digital, fallback, retry, and Groq groups are 1 page.

## File map

| Change | File |
|---|---|
| Scan vs digital, fast-path flags | `app/inspection/pdf_inspector.py` |
| Text/layout feature math | `app/inspection/features.py` |
| Route choice | `app/routing/policy.py` |
| Privacy gate | `app/routing/privacy.py` |
| Thresholds and concurrency | `app/config.py` |
| Native text | `app/adapters/pymupdf_adapter.py` |
| Layout / local OCR | `app/adapters/docling_adapter.py`, `app/adapters/docling_profiles.py` |
| Scan OCR | `app/adapters/gemini_adapter.py`, `app/adapters/gemini_prompt.py` |
| Figure descriptions | `app/adapters/groq_vision_adapter.py` |
| Grouping | `app/grouping/planner.py` |
| Validation codes | `app/validation/codes.py` |
| Retry map | `app/fallback/policy.py` |
| Orchestration | `app/services/extraction_service.py` |
| Canonical schema | `app/models/canonical.py` |
| Architecture notes | `extract.md` at repo root (or `multimodal_rag_app/extract.md`) |

## Workspace artifacts

```text
output/{document_id}/
  source.pdf
  inspection.json
  routing.json
  document.json
  extraction-report.json
  assets/  pages/ tables/ pictures/ charts/
  raw/
```

`document.json` is the extracted document. `extraction-report.json` is diagnostics.

## Additional resources

- Thresholds, Docling profiles, fallback codes: [routing-reference.md](routing-reference.md)
