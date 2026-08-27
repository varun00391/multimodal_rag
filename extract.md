# Standalone Hybrid PDF Extraction System

## 1. Purpose

This document defines a standalone extraction application for:

- Born-digital PDF files
- Scanned PDF files
- Mixed PDFs containing both digital and scanned pages
- Multi-page PDFs with different layouts and complexity on each page

The application ends after extraction. Its outputs are structured JSON,
extracted images, page previews when requested, diagnostics, and validation
results.

The following capabilities are explicitly out of scope:

- RAG
- Chunking
- Embeddings
- Vector databases
- Search and retrieval
- Question answering
- Compatibility with an existing Docling-based application
- Migration of an existing normalization or indexing pipeline

The long-term goal is a format-independent extraction platform supporting
documents, spreadsheets, presentations, images, audio, and video. The current
implementation must support only PDFs and scanned PDFs, while keeping its core
schema and adapter architecture extensible.

## 2. Primary Goal

Build an extraction system that produces the most accurate practical result
from heterogeneous PDFs while balancing:

- Extraction quality
- Latency
- API and compute cost
- Privacy and data residency
- Reproducibility
- Fault isolation

No single parser is best for every PDF page. The system must inspect and route
work at page and region level instead of sending every page through one fixed
pipeline.

The initial extractor policy is:

- **PyMuPDF:** page inspection and clean native-text extraction
- **Docling:** complex digital layout, tables, formulas, code, and local OCR
- **Gemini 2.5 Flash:** scans, damaged text layers, image-based tables, forms,
handwriting, difficult visual layouts, and selected fallbacks
- **Groq vision:** optional semantic interpretation of charts, diagrams, graphs,
and other visual regions

Model and provider names are configuration defaults, not permanent contracts.
All extractors must sit behind replaceable adapters.

## 3. Success Criteria

The system should:

1. Accept a valid PDF and create a stable document identifier.
2. Inspect every page before selecting extractors.
3. Identify clean digital, complex digital, scanned, and mixed pages.
4. Build layered extraction tasks for text, structure, tables, formulas, and
  visual regions.
5. Keep related adjacent pages together when context is useful.
6. Preserve original page numbers and source coordinates.
7. Convert all parser responses into one canonical schema.
8. Validate every page and element independently.
9. Retry only failed or low-confidence work.
10. Preserve partial results when some pages cannot be extracted.
11. Report route, model, prompt, timing, token usage, confidence, and failure
  provenance.
12. Allow output from different extractors to be compared against labelled
  ground truth.

“Most accurate” must be measured on a representative benchmark set. It must not
be inferred only from parser confidence or visual inspection of a few files.

## 4. Non-Goals for the PDF Test Application

The first version will not:

- Generate searchable chunks
- Generate text or image embeddings
- Store data in Qdrant or another vector database
- Answer questions about extracted content
- Depend on code in a previous multimodal RAG application
- Read or emit fake Docling internals for compatibility
- Support Office, spreadsheet, audio, or video formats
- Promise perfect extraction for every possible PDF

The system should return explicit uncertainty or failure rather than silently
inventing content.

## 5. Why a Hybrid Extractor Is Required

PDF is a presentation format, not a reliable semantic document format. Two
pages that look identical can have very different internals:

- Correctly ordered embedded text
- Embedded text stored in an incorrect reading order
- Individual positioned glyphs
- A full-page raster scan
- A scan with a low-quality hidden OCR layer
- Vector drawings mixed with text
- Tables represented only by lines and coordinates
- Charts whose meaning is not present in text

Using only PyMuPDF is fast but insufficient for scans and complex structures.
Using only Docling adds avoidable cost to simple pages. Using only a
multimodal LLM adds cost, latency, nondeterminism, and hallucination risk.

The solution is:

```text
inspect -> plan -> group -> extract -> validate -> fallback -> merge
```

## 6. Target Architecture

```text
PDF upload through HTTP API
   |
   v
Input validation and document hashing
   |
   v
Fast page inspection with PyMuPDF
   |
   v
Privacy policy and page-level routing
   |
   v
Layered extraction plan
   |
   +-- native text ------------> PyMuPDF
   +-- layout/table/formula ----> cached Docling profile
   +-- OCR/visual document ----> Gemini 2.5 Flash
   +-- visual region ----------> crop + optional Groq vision
   |
   v
Contiguous extractor/profile-specific groups
   |
   v
Independent execution with per-extractor concurrency limits
   |
   v
Extractor adapters
   |
   v
Canonical pages and elements
   |
   v
Page- and element-level validation
   |
   +-- pass -> retain
   +-- fail -> failure-specific fallback for failed work only
   |
   v
Merge in original page and reading order
   |
   v
document.json + assets + extraction report
```

## 7. Standalone Application Boundary

The extraction application owns:

- Input validation
- PDF inspection
- Routing
- Group planning
- Parser calls
- OCR and visual-understanding calls
- Coordinate conversion
- Canonical output
- Validation
- Fallback
- Caching
- Metrics and extraction reports

It does not own downstream interpretation or retrieval.

Recommended project structure:

```text
multimodal_rag_app/
  extraction/
    __init__.py
    config.py
    models.py
    errors.py
    service.py
    registry.py
    inspection/
      pdf_inspector.py
      features.py
      continuity.py
    routing/
      policy.py
      planner.py
      grouping.py
      privacy.py
    adapters/
      base.py
      pymupdf_adapter.py
      docling_adapter.py
      gemini_adapter.py
      groq_vision_adapter.py
    validation/
      validator.py
      text.py
      layout.py
      tables.py
      visuals.py
    fallback/
      manager.py
      policy.py
    merge/
      merger.py
      coordinates.py
      deduplication.py
    storage/
      workspace.py
      cache.py
    api/
      app.py
      routes.py
  tests/
    fixtures/
    unit/
    integration/
    benchmark/
```

The directory name may change later. The important boundary is that this
package must not import the previous RAG pipeline.

## 8. Input and Output

### 8.1 Input

The application accepts:

- A PDF uploaded as `multipart/form-data` through the HTTP API
- Optional extraction policy:
  - managed APIs allowed or prohibited
  - requested output modalities
  - maximum cost
  - maximum latency
  - force extractor for benchmarking

### 8.2 Output workspace

```text
output/
  <document-id>/
    source.pdf
    document.json
    extraction-report.json
    inspection.json
    assets/
      pages/
      pictures/
      charts/
      tables/
```

Page images should be generated lazily. They are required for OCR, visual
analysis, explicit previews, or preserved failures, but should not be rendered
for every clean digital page by default.

## 9. Canonical Extraction Schema

The application must own its schema. Docling, PyMuPDF, Gemini, and Groq output
must be treated as external formats converted by adapters.

### 9.1 Document

```json
{
  "schema_version": "1.0",
  "document_id": "sha256-prefix-or-uuid",
  "source": {
    "filename": "report.pdf",
    "media_type": "application/pdf",
    "sha256": "...",
    "size_bytes": 123456
  },
  "status": "completed_with_warnings",
  "page_count": 12,
  "pages": [],
  "summary": {
    "element_counts": {},
    "route_counts": {},
    "failed_pages": [],
    "duration_ms": 0,
    "estimated_cost_usd": 0
  }
}
```

### 9.2 Page

```json
{
  "page": 12,
  "width": 612,
  "height": 792,
  "rotation": 0,
  "primary_route": "pymupdf",
  "routing_confidence": 0.96,
  "validation_confidence": 0.93,
  "overall_confidence": 0.93,
  "routing_reasons": [
    "Native text layer is dense and printable",
    "No complex table was detected"
  ],
  "extraction_routes": [],
  "elements": [],
  "attempts": [],
  "warnings": [],
  "errors": []
}
```

### 9.3 Element

```json
{
  "element_id": "document-123:p12:e4",
  "type": "table",
  "page": 12,
  "reading_order": 4,
  "text": "Table contents",
  "markdown": "| A | B |",
  "html": "<table>...</table>",
  "bbox": {
    "left": 40,
    "top": 120,
    "right": 550,
    "bottom": 640,
    "coordinate_origin": "top-left",
    "unit": "pdf-point"
  },
  "asset": "assets/tables/page_12_table_1.png",
  "confidence": 0.91,
  "extractor": {
    "name": "docling",
    "version": "pinned-version",
    "adapter_version": "1.0",
    "profile": "digital-table",
    "model": null,
    "prompt_version": null
  },
  "provenance": {
    "source_page": 12,
    "source_coordinate_system": "pdf-points-bottom-left",
    "routing_policy_version": "1",
    "attempt": 1
  },
  "metadata": {}
}
```

Supported element types:

- `heading`
- `paragraph`
- `list`
- `table`
- `picture`
- `chart`
- `diagram`
- `formula`
- `code`
- `key_value`
- `form_field`
- `header`
- `footer`
- `footnote`
- `page_number`
- `unknown`

All bounding boxes must use one canonical coordinate system:
PDF points, top-left origin.

## 10. Page Inspection

PyMuPDF performs low-cost inspection for every page before routing.

### 10.1 Text-layer signals

- Character and word count
- Number of text blocks, lines, spans, and fonts
- Printable-character ratio
- Unicode replacement-character ratio
- Null/control-character ratio
- Average word length
- Repeated-character and duplicate-block ratio
- Text coverage across the page
- Percentage of words with valid bounding boxes
- Font-size distribution
- Overlapping text
- Suspicious hidden OCR text

### 10.2 Image and scan signals

- Image count
- Largest image coverage
- Total image coverage
- Presence of a nearly full-page image
- Image dimensions and effective resolution
- Native text amount despite high image coverage
- Difference between visible page and native text layer

A page with little native text and one image covering most of the page is
probably scanned.

### 10.3 Layout signals

- Probable number of columns
- Block-order irregularity
- Vector-drawing count
- Dense alignments of words and lines
- Probable table regions
- Large figures or charts
- Many small text regions
- Rotated text
- Side notes, headers, and footers
- Formula- or code-like regions

### 10.4 Continuity signals

- Table reaches the bottom of a page
- Next page starts with a repeated table header
- Sentence ends without terminal punctuation
- Heading appears near the bottom
- Caption and figure cross a page boundary
- Column and font patterns continue
- Numbered list continues
- Footnotes or references continue

Inspection is evidence for routing, not proof that extraction succeeded.

## 11. Layered Routing

A page can use multiple extractors. `primary_route` identifies how its main
content is extracted, while `tasks` identifies additional region-level work.

```json
{
  "page": 8,
  "primary_route": "pymupdf",
  "tasks": [
    {
      "kind": "native_text",
      "extractor": "pymupdf"
    },
    {
      "kind": "table_structure",
      "extractor": "docling",
      "profile": "digital-table",
      "region": [40, 300, 560, 700]
    },
    {
      "kind": "visual_understanding",
      "extractor": "groq-vision",
      "region": [50, 80, 550, 280],
      "required": true
    }
  ]
}
```

Privacy and residency restrictions must be evaluated before quality, latency,
and cost. A managed extractor must never be selected when policy forbids it.

## 12. Initial Routing Rules

Thresholds below are starting points and must be calibrated.

### 12.1 PyMuPDF

Use PyMuPDF for main extraction when:

- Native text is sufficiently dense
- Printable ratio is high
- Bounding boxes are valid
- Reading order is simple
- Image coverage is low or decorative
- No complex table or OCR warning exists

```python
use_pymupdf = (
    character_count >= 500
    and printable_ratio >= 0.95
    and replacement_character_ratio <= 0.01
    and image_coverage <= 0.35
    and layout_complexity <= 0.45
    and not probable_complex_table
)
```

### 12.2 Docling

Use a cached Docling profile when:

- A valid text layer has complex reading order
- Multiple columns are present
- Digital tables need reconstruction
- Formula or code structure is likely
- Local-only processing is required
- Local OCR is the configured scan fallback

Initial profiles:

- `digital-layout`: layout and reading order
- `digital-table`: layout and table structure
- `formula-code`: layout, tables, formulas, and code
- `private-ocr`: local OCR and structure

Keep one warm converter or worker pool per profile. Do not create arbitrary
feature combinations per page.

### 12.3 Gemini 2.5 Flash

Use Gemini when external processing is permitted and:

- Native text is absent or sparse
- A raster image covers most of the page
- Native text is corrupted
- A table exists only as an image
- Handwriting or a difficult form is present
- Multilingual OCR is needed
- Another result failed validation

Require structured JSON. Record the exact model ID, prompt version, schema
version, token usage, and finish reason.

Gemini self-reported confidence is not a calibrated OCR score. Validate output
against page evidence and, during benchmarking, ground truth.

### 12.4 Groq vision

Groq is an optional region-level extractor for semantic interpretation of:

- Charts
- Graphs
- Diagrams
- Infographics
- Technical figures

For the standalone extractor, visual analysis can run during extraction when
enabled. Always retain the crop, page, bbox, nearby text, caption, and model
provenance.

### 12.5 Uncertain pages

Initially process uncertain pages individually with Docling or Gemini and
collect telemetry. Prefer quality over the cheapest first call while routing
thresholds are uncalibrated.

## 13. Group Planning

Classify before grouping. Grouping must never force a page through an
inappropriate extractor.

```text
Page 1  -> PyMuPDF
Page 2  -> PyMuPDF
Page 3  -> Gemini
Page 4  -> Gemini
Page 5  -> Docling
```

Execution groups:

```text
Pages 1-2 -> PyMuPDF
Pages 3-4 -> Gemini
Page 5    -> Docling
```

Never group:

- Non-consecutive pages
- Different documents
- Incompatible extractors or profiles
- Unrelated forms
- Pages with conflicting privacy requirements

Starting batch sizes:

- PyMuPDF: process qualifying pages from one open document
- Gemini: 4-8 related pages, target 5
- Continuous scanned runs: up to 10-20 pages after testing
- Docling: 10-30 related pages with a warm converter
- Independent forms: one page
- Uncertain pages: one page

Temporary page mappings must be explicit:

```json
{
  "group_id": "gemini-0003",
  "temporary_pages": [1, 2, 3],
  "original_pages": [8, 9, 10],
  "primary_pages": [8, 9, 10],
  "context_pages": []
}
```

Context-only neighbouring pages may be included when continuity requires them.
Their duplicate output must be removed during merge.

## 14. Extractor Adapter Contract

```python
class ExtractionAdapter(Protocol):
    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        tasks: list[ExtractionTask],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        ...
```

Each adapter is responsible for:

- Calling its parser or API
- Mapping temporary pages back to original pages
- Mapping parser-specific element types
- Converting coordinates
- Preserving raw parser confidence
- Saving or referencing extracted assets
- Returning token, cost, and timing information
- Returning structured errors

Raw parser responses may be cached for debugging, but they are not the
application’s public output contract.

## 15. Validation

Validation runs independently for every page, including pages submitted in a
group.

### 15.1 Text

- Minimum useful character count
- Printable-character ratio
- Replacement/control-character ratio
- Duplicate-line ratio
- Repeated-symbol ratio
- Native text expected but missing
- OCR result suspiciously shorter than visible evidence
- Hallucinated content unsupported by source evidence

### 15.2 Layout

- Bounding boxes are within page bounds
- Bounding boxes have positive area
- Reading-order indices are valid
- Excessive overlap is absent
- Headings and paragraphs are not duplicated
- Header/footer repetition is identified

### 15.3 Tables

- Table is not empty
- Expected rows and columns are present
- Cell structure is internally consistent
- Markdown and HTML are valid when emitted
- Repeated headers are handled
- Multi-page tables are linked
- Numeric values can be cross-checked against OCR/native text

### 15.4 Visuals

- Expected figures are present
- Crops exist and have non-zero dimensions
- Bboxes align with the source page
- Chart/diagram pages contain appropriate elements
- Visual descriptions refer only to visible content

### 15.5 Cross-parser checks

For selected uncertain or benchmark pages, run two extractors and compare:

- Character coverage
- Normalized text distance
- Heading count and hierarchy
- Table dimensions and cell values
- Figure count
- Reading order
- Bounding-box overlap

Shadow comparisons must not overwrite the selected result automatically. They
produce evaluation evidence for policy calibration.

## 16. Confidence

Keep three concepts separate:

1. **Routing confidence:** appropriateness of the chosen extractor
2. **Parser confidence:** extractor-reported value, if available
3. **Validation confidence:** application-calculated usability score

Do not calculate a simple average. A conservative temporary rule is:

```python
overall_confidence = min(
    routing_confidence,
    parser_confidence_calibrated or 1.0,
    validation_confidence,
)
```

Scores from different extractors and task types are not naturally comparable.
Calibrate them independently against labelled pass/fail outcomes.

## 17. Failure-Specific Fallback

Fallback selection depends on the observed failure:

```text
Missing or corrupt native text:
    PyMuPDF -> Gemini

Incorrect digital reading order:
    PyMuPDF -> Docling digital-layout

Incorrect digital table structure:
    Docling digital-table -> Gemini when allowed

Missing formula or code structure:
    PyMuPDF -> Docling formula-code

Missing chart or diagram meaning:
    region crop -> Groq vision

Managed API prohibited:
    Gemini candidate -> Docling private-ocr

Transient API failure:
    bounded retry of the same extractor
```

Rules:

- Retry only failed pages or regions
- Use bounded exponential backoff for transient failures
- Do not retry invalid input indefinitely
- Cap attempts per page
- Preserve every attempt and failure reason
- Do not assume one extractor is universally stronger
- If all extractors fail, retain a source page image and emit a structured
extraction failure

## 18. Merge and Deduplication

Merge by:

1. Original document
2. Original page
3. Region
4. Reading order

The merger must:

- Convert all page numbers before combining results
- Normalize coordinates before geometric comparison
- Deduplicate context-page output
- Deduplicate overlapping output from layered tasks
- Prefer structural table output over duplicate plain table text while
retaining source text in provenance
- Detect incompatible extractor claims and emit a warning
- Assign stable element IDs only after final ordering

Never silently discard conflicting content. Keep the selected result and record
the alternative in diagnostics when useful.

## 19. Concurrency and Resource Control

Use separate limits:

- PyMuPDF workers: CPU and file-descriptor based
- Docling workers: GPU/CPU memory based
- Gemini requests: API quotas and token limits
- Groq requests: provider rate limits

Controls:

- Per-document group limit
- Global per-extractor semaphore
- Request timeout
- Maximum PDF size and pages
- Maximum rendered-pixel count
- Maximum pages per group
- Retry and cost budgets
- Managed-provider circuit breaker
- Queue backpressure

Independent groups can execute concurrently, but results must be merged
deterministically.

## 20. Caching

Cache key:

```text
PDF SHA-256
+ original page or region
+ task identity
+ extractor and model version
+ adapter version
+ extraction options hash
+ routing policy version
+ prompt version
+ canonical schema version
```

Cache:

- Inspection metadata
- Routing decision
- Raw parser output
- Canonical page result
- Assets
- Validation result

Do not reuse incompatible cache entries after a prompt, parser, adapter,
policy, or schema change.

## 21. Security and Privacy

Before calling a managed API:

- Confirm the document may leave the local environment
- Review retention and model-training terms
- Select an allowed processing region
- Encrypt files in transit and at rest
- Avoid logging document text
- Store keys only in secrets or environment configuration

For all inputs:

- Verify the file is actually a PDF
- Limit file size, pages, render dimensions, and execution time
- Use randomized temporary paths
- Prevent path traversal
- Delete temporary split PDFs
- Treat parser output as untrusted data
- Avoid rendering or decompressing unbounded content

An on-prem policy must route scan extraction to local OCR rather than Gemini.

## 22. Observability and Extraction Report

Record per page and attempt:

- Document ID and page
- Inspection features
- Route and routing reasons
- Routing confidence
- Group ID and size
- Queue, extraction, and validation duration
- Extractor, model, profile, and prompt versions
- Input/output tokens and estimated cost
- Output element counts
- Validation failures
- Retry count and fallback route
- Final confidence and status

Aggregate metrics:

- Pages per second by extractor
- End-to-end latency
- p50, p95, and p99 page latency
- Cost per 1,000 pages
- Cost per successfully validated page
- Route distribution
- Validation and fallback rates
- API retry/rate-limit rate
- Table, OCR, and visual success rates
- Cache hit rate

## 23. Configuration

```env
EXTRACTION_SCHEMA_VERSION=1.0
EXTRACTION_ROUTING_POLICY_VERSION=1
EXTRACTION_OUTPUT_DIR=./output
EXTRACTION_ALLOW_MANAGED_APIS=true
EXTRACTION_MAX_FILE_BYTES=104857600
EXTRACTION_MAX_PAGES=500
EXTRACTION_MAX_ATTEMPTS_PER_PAGE=3
EXTRACTION_MIN_VALIDATION_CONFIDENCE=0.85
EXTRACTION_CACHE_ENABLED=true

PYMUPDF_MIN_CHARACTERS=500
PYMUPDF_MIN_PRINTABLE_RATIO=0.95
PYMUPDF_MAX_REPLACEMENT_RATIO=0.01
PYMUPDF_MAX_IMAGE_COVERAGE=0.35
PYMUPDF_MAX_LAYOUT_COMPLEXITY=0.45

DOCLING_MAX_PAGES_PER_GROUP=30
DOCLING_IMAGE_SCALE=1.25
DOCLING_GENERATE_PAGE_IMAGES=false
DOCLING_GENERATE_PICTURE_IMAGES=true
DOCLING_TABLE_STRUCTURE=true

GEMINI_API_KEY=
GEMINI_MODEL_ID=gemini-2.5-flash
GEMINI_TARGET_PAGES_PER_GROUP=5
GEMINI_MAX_PAGES_PER_GROUP=10
GEMINI_MAX_CONCURRENCY=4
GEMINI_REQUEST_TIMEOUT_SECONDS=180
GEMINI_EXTRACTION_PROMPT_VERSION=1
GEMINI_BUDGET_GUARD_ENABLED=true

GROQ_API_KEY=
GROQ_VISUAL_MODEL=
GROQ_VISUAL_EXTRACTION_ENABLED=false
GROQ_VISUAL_PROMPT_VERSION=1
```

All thresholds must remain configurable.

## 24. Core Extraction Flow

```python
async def extract_pdf(
    pdf_path: Path,
    policy: ExtractionPolicy,
) -> CanonicalDocument:
    validated_input = input_validator.validate(pdf_path)
    document_hash = sha256_file(validated_input.path)

    inspection = await page_inspector.inspect(validated_input.path)

    page_plans = [
        routing_policy.create_layered_plan(page, policy)
        for page in inspection.pages
    ]

    groups = group_planner.create_contiguous_groups(
        tasks=[
            task
            for plan in page_plans
            for task in plan.tasks
        ],
        continuity=inspection.continuity,
    )

    group_results = await executor.run(groups, validated_input.path)
    pages = result_merger.map_to_original_pages(groups, group_results)

    for page in pages:
        validation = validator.validate(
            page,
            inspection.page(page.page),
        )

        if validation.confidence < settings.minimum_confidence:
            page = await fallback_manager.retry_failed_work(
                pdf_path=validated_input.path,
                page=page,
                inspection=inspection.page(page.page),
                validation=validation,
                policy=policy,
            )

        page.validation = validator.validate(
            page,
            inspection.page(page.page),
        )

    document = result_merger.build_document(
        document_hash=document_hash,
        pages=pages,
    )

    extraction_report.write(document, inspection, groups)
    return document
```

## 25. HTTP API

Users submit and access extraction jobs only through the HTTP API. There is no
user-facing CLI or local-file input mode.

```text
POST /api/v1/extractions
GET  /api/v1/extractions/{job_id}
GET  /api/v1/extractions/{job_id}/document
GET  /api/v1/extractions/{job_id}/report
GET  /api/v1/extractions/{job_id}/assets/{asset_path}
```

`POST /api/v1/extractions` accepts:

- One PDF as `multipart/form-data`
- Whether managed extraction APIs are permitted
- Optional page range
- Whether visual interpretation is required
- Optional forced extractor/profile for authorized benchmark requests
- Optional comparison mode for authorized benchmark requests

The endpoint validates the upload, persists it in a controlled workspace,
creates an extraction job, and returns a job ID. Extraction runs through an
internal Python service function. It must not depend on a command-line
subprocess.

Forced-extractor and comparison options are testing controls and should be
disabled or access-controlled in normal deployments.

## 26. Implementation Plan

### Phase 0: Benchmark fixtures and current baselines

Goal: define what accuracy means before implementing routing.

- Collect representative digital, scanned, and mixed PDFs
- Create page-level ground truth for text, reading order, tables, and figures
- Establish PyMuPDF-only, Docling-only, and Gemini-only baselines
- Measure cold/warm latency, memory, API tokens, and cost
- Identify sensitive fixtures that must remain local

Deliverable: baseline report and labelled fixtures.

### Phase 1: Standalone foundation

Goal: create an executable extraction application with no dependency on a RAG
pipeline.

- Create the standalone package structure
- Define typed canonical models
- Add configuration and error models
- Add workspace and asset management
- Add input validation and SHA-256 document identity
- Implement the PDF upload and extraction-job API skeleton
- Implement deterministic JSON output

Deliverable: an API that accepts a PDF upload and produces a valid
empty/skeleton canonical document and extraction report.

### Phase 2: PyMuPDF inspection and extraction

- Implement page feature collection
- Implement scan and layout heuristics
- Implement continuity signals
- Implement native text, spans, words, fonts, and images
- Convert coordinates to the canonical system
- Generate `inspection.json`
- Add unit tests for digital and scanned classification

Deliverable: accurate fast extraction for simple born-digital PDFs and detailed
inspection for all PDFs.

### Phase 3: Docling adapter

- Add warm, versioned converter profiles
- Add layout, table, formula, code, and local OCR mappings
- Avoid default full-page rendering
- Convert output directly to canonical elements
- Record profile, version, timing, and parser diagnostics
- Test complex digital and local-only scanned PDFs

Deliverable: complex digital pages and private scans handled locally.

### Phase 4: Gemini adapter

- Define versioned structured-output schema and extraction prompt
- Add page/group submission and original-page mapping
- Add API concurrency, timeout, retry, and budget controls
- Capture token usage and cost
- Reject malformed structured output
- Validate scans, forms, multilingual pages, and image tables

Deliverable: managed extraction path for difficult visual pages.

### Phase 5: Router and adaptive grouping

- Implement layered task planning
- Enforce privacy before managed routing
- Implement conservative initial thresholds
- Group adjacent compatible tasks
- Handle context-only pages
- Run extractor groups concurrently
- Add forced-route and comparison modes

Deliverable: one mixed PDF can use different extractors on different pages and
regions.

### Phase 6: Validation, merge, and fallback

- Implement text, layout, table, and visual validators
- Implement coordinate-aware deduplication
- Implement deterministic reading-order merge
- Add failure-specific fallback rules
- Retry only failed pages or regions
- Preserve partial success and terminal failures

Deliverable: validated canonical output with attempt history.

### Phase 7: Optional visual semantics

- Detect and crop charts, diagrams, and figures
- Add Groq vision adapter
- Require source-grounded structured output
- Validate visual descriptions
- Preserve crops and provenance

Deliverable: optional semantic extraction from meaningful visual regions.

### Phase 8: API hardening and production controls

- Add persistent job status and result retrieval
- Add queueing and per-extractor concurrency limits
- Add cache and circuit breakers
- Add metrics and structured logs
- Add file/resource limits and cleanup

Deliverable: standalone extraction service suitable for controlled testing.

### Phase 9: Calibration

- Run at least 20-50 representative documents and 500 pages
- Measure false routing decisions
- Tune page and grouping thresholds
- Calibrate confidence by extractor and task
- Compare hybrid quality, latency, and cost against baselines
- Pin versions used for reproducible releases

Deliverable: evidence-backed routing policy and go/no-go report.

## 27. Benchmark Plan

Corpus categories:

- Clean single-column digital documents
- Multi-column reports
- Table-heavy reports
- Scientific papers with formulas
- Scanned documents
- Mixed digital/scanned documents
- Forms and key-value documents
- Chart-heavy reports or presentations exported as PDF
- Multilingual documents
- Rotated and low-quality scans
- Handwritten pages when relevant

Metrics:

- Character error rate or normalized text edit distance
- Word accuracy
- Reading-order correctness
- Heading hierarchy accuracy
- Table structure and cell-value accuracy
- Formula accuracy
- Figure/chart recall
- Bounding-box accuracy
- Hallucination rate
- Page validation precision and recall
- End-to-end, cold, and warm latency
- Peak CPU/GPU memory
- API and compute cost
- Cost per successfully validated page
- Retry and fallback rate
- Confidence calibration error

Compare:

- PyMuPDF only
- Optimized Docling only
- Gemini only
- Hybrid router without fallback
- Hybrid router with validation and fallback
- Other parsers only if they are serious deployment candidates

## 28. Acceptance Gates

Before calling the PDF extractor ready:

- Every result validates against the canonical schema
- Original page identity survives grouping and retries
- Managed APIs are never called in local-only mode
- A page failure does not discard successful pages
- Cache invalidation respects model, prompt, adapter, policy, and schema versions
- Forced-extractor benchmark mode works
- Mixed PDFs use different routes when appropriate
- Scanned pages produce OCR-backed text or explicit failure
- Complex tables preserve tested structure above an agreed threshold
- Hallucination and unsupported-content rates are measured
- Quality improves over the best single-parser baseline enough to justify the
router’s added complexity

## 29. Future Format Expansion

Future format support should reuse:

- Canonical elements
- Extractor adapter concepts
- Validation results
- Provenance
- Attempts and errors
- Caching
- Metrics

Format-specific units may differ:

- PDF/image: page and region
- XLS/XLSX: workbook, sheet, range, cell
- DOC/DOCX: section, paragraph, table, image
- PPT/PPTX: slide and shape
- Audio: time range and speaker
- Video: time range, transcript segment, frame, and scene

Do not implement these formats during the PDF test. First verify that the
canonical schema can be extended without making every field page-specific.

## 30. Final Recommendation

Implement a standalone, page-aware hybrid PDF extraction engine:

1. Inspect every page with PyMuPDF.
2. Apply privacy policy before selecting managed extractors.
3. Build layered text, structure, OCR, and visual tasks.
4. Use PyMuPDF for reliable native text and geometry.
5. Use cached Docling profiles for complex digital structure and local OCR.
6. Use Gemini 2.5 Flash for permitted scans and difficult visual documents.
7. Use Groq only for optional region-level visual semantics.
8. Group only adjacent, related, compatible work.
9. Validate every page and element.
10. Select fallbacks by failure reason and retry only failed work.
11. Merge into an application-owned canonical schema with complete provenance.
12. Benchmark against single-parser baselines before claiming higher accuracy.

This application must remain independent of RAG, chunking, embeddings,
retrieval, and vector storage. Its only responsibility is to transform PDFs and
scanned PDFs into accurate, structured, validated extraction outputs.