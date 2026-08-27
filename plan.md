# Standalone PDF Extraction — Implementation Plan

## 1. Scope

Build a standalone HTTP API that extracts structured information from:

- Born-digital PDFs
- Scanned PDFs
- Mixed digital and scanned PDFs
- Multi-page PDFs whose pages contain different layouts and modalities

The application ends after producing validated extraction results. It does not
perform chunking, embeddings, indexing, retrieval, or question answering, and
it must not depend on the previous RAG application.

Users upload PDFs only through the HTTP API. There is no user-facing CLI or
local-path input mode.

## 2. Initial Technology Choices

- FastAPI: HTTP API
- Pydantic: canonical schemas and request validation
- PyMuPDF: PDF validation, inspection, rendering, and native extraction
- Docling: complex layouts, tables, formulas, code, and local OCR
- Gemini 2.5 Flash: scans and difficult visual documents when managed APIs are
  permitted
- Groq vision: optional chart, graph, diagram, and figure interpretation
- SQLite: initial extraction-job storage
- Local filesystem: initial source, JSON, and asset storage

Provider names are replaceable defaults. All extractors must be accessed
through adapters.

## 3. Project Structure

```text
multimodal_rag_app/
  app/
    __init__.py
    main.py
    config.py
    errors.py
    models/
      canonical.py
      inspection.py
      routing.py
      jobs.py
      validation.py
    api/
      routes.py
      dependencies.py
    services/
      extraction_service.py
      job_service.py
    inspection/
      pdf_inspector.py
      features.py
      continuity.py
    routing/
      policy.py
      planner.py
      privacy.py
    grouping/
      planner.py
    adapters/
      base.py
      pymupdf_adapter.py
      docling_adapter.py
      gemini_adapter.py
      groq_vision_adapter.py
    execution/
      executor.py
      limits.py
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
      jobs.py
      cache.py
      reports.py
  tests/
    fixtures/
    unit/
    integration/
    benchmark/
  output/
```

## 4. API and Job Lifecycle

### 4.1 Upload

```text
POST /api/v1/extractions
Content-Type: multipart/form-data
```

Fields:

- `file`: required PDF
- `allow_managed_apis`: whether Gemini/Groq may receive document data
- `visual_understanding`: whether semantic visual extraction is required
- `page_start`: optional
- `page_end`: optional
- `force_extractor`: authorized benchmark option
- `compare_extractors`: authorized benchmark option

Response:

```json
{
  "job_id": "job-123",
  "status": "queued"
}
```

### 4.2 Result endpoints

```text
GET /api/v1/extractions/{job_id}
GET /api/v1/extractions/{job_id}/document
GET /api/v1/extractions/{job_id}/report
GET /api/v1/extractions/{job_id}/assets/{asset_path}
```

### 4.3 Statuses

```text
queued
validating_input
inspecting
planning
extracting
validating_output
retrying
merging
completed
completed_with_warnings
failed
```

Extraction must run through an internal Python service function, not a CLI
subprocess.

## 5. Input Validation and Workspace

For every upload:

1. Enforce the maximum request size.
2. Ignore the user filename for storage paths.
3. Generate a random internal filename.
4. Verify the PDF signature and MIME type.
5. Open the file with PyMuPDF to confirm it is parseable.
6. Enforce page-count, page-dimension, and rendered-pixel limits.
7. Compute SHA-256.
8. Create an isolated document workspace.

```text
output/<document-id>/
  source.pdf
  inspection.json
  document.json
  extraction-report.json
  raw/
  assets/
    pages/
    tables/
    pictures/
    charts/
```

Full-page images must be rendered only when needed for OCR, visual analysis,
preview, or preserving failed pages.

## 6. Canonical Models

Define the application-owned schema before implementing extractors.

Required models:

- `CanonicalDocument`
- `CanonicalPage`
- `CanonicalElement`
- `BoundingBox`
- `ExtractorProvenance`
- `ExtractionAttempt`
- `ExtractionError`
- `PageInspection`
- `PagePlan`
- `ExtractionTask`
- `ExtractionGroup`
- `ValidationResult`

Canonical element types:

```text
heading
paragraph
list
table
picture
chart
diagram
formula
code
key_value
form_field
header
footer
footnote
page_number
unknown
```

All canonical bounding boxes use PDF points with a top-left origin.

No canonical model may expose Docling, PyMuPDF, Gemini, or Groq objects.

## 7. PyMuPDF Page Inspection

Open each PDF once and collect the following per page.

### Text signals

- Character, word, block, line, and span counts
- Printable-character ratio
- Replacement/control-character ratio
- Text coverage
- Duplicate and overlapping text
- Valid bounding-box ratio
- Font and font-size distribution
- Suspicious hidden OCR

### Image and scan signals

- Image count
- Largest image coverage
- Total image coverage
- Near-full-page raster image
- Image dimensions and effective resolution
- Native-text amount despite high image coverage

Initial scan signal:

```python
probable_scan = (
    character_count < 100
    and largest_image_coverage >= 0.80
)
```

### Layout signals

- Probable columns
- Irregular block order
- Vector drawings
- Table candidates
- Figure/chart candidates
- Rotated text
- Side notes, headers, and footers
- Formula- and code-like regions

### Continuity signals

- Table continues onto the next page
- Repeated table header
- Incomplete sentence
- Continuing list
- Figure/caption split
- Continuing columns or fonts

Write all inspection output to `inspection.json`.

## 8. Extractor Adapter Interface

```python
class ExtractionAdapter(Protocol):
    name: str

    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        tasks: list[ExtractionTask],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        ...
```

Each adapter must:

- Call its parser or API
- Preserve original page identity
- Convert parser-specific element types
- Convert source coordinates
- Save or reference assets
- Return canonical pages/elements
- Return parser confidence, timing, usage, and cost
- Return structured warnings and errors

Raw parser output may be retained for diagnostics but is not the public
contract.

## 9. PyMuPDF Adapter

Implement the first forced-extractor path.

Extract:

- Paragraphs and text blocks
- Words, spans, fonts, and coordinates
- Heading candidates
- Lists
- Embedded images
- Basic reading order
- Simple tables when confidence is high

Test it independently before introducing routing.

## 10. Docling Adapter

Create warm, versioned profiles during application startup:

- `digital-layout`
- `digital-table`
- `formula-code`
- `private-ocr`

Avoid full-page rendering by default. Enable only the capabilities required by
the selected profile.

When processing selected pages, create a temporary sub-PDF if necessary and
record:

```json
{
  "temporary_pages": [1, 2],
  "original_pages": [8, 9]
}
```

Map all results back to original page numbers and delete temporary files.

## 11. Gemini Adapter

Use Gemini when managed processing is allowed and the page is scanned,
corrupted, image-based, handwritten, multilingual, or otherwise difficult.

Implementation:

1. Render assigned pages at a controlled resolution.
2. Label every input with its original page number.
3. Group only related consecutive pages.
4. Require structured JSON.
5. Validate the response schema.
6. Convert normalized coordinates to canonical PDF points.
7. Record model, prompt version, tokens, finish reason, latency, and cost.

The prompt must instruct the model to:

- Extract rather than summarize
- Preserve exact numbers and units
- Preserve reading order
- Return tables as structured cells
- Avoid unsupported inference
- Mark uncertainty
- Return results separately for every original page

Do not trust model-reported confidence without application validation.

## 12. Groq Vision Adapter

Use Groq only for meaningful visual regions such as:

- Charts
- Graphs
- Diagrams
- Infographics
- Technical figures

Send:

- Region crop
- Original page number
- Bounding box
- Caption
- Nearby text

Attach structured visual output to the corresponding canonical visual element.
Do not invoke it for decorative images or logos.

## 13. Multi-Label Routing

Classification produces multiple tasks, not one exclusive page label.

Example:

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
      "region": [40, 180, 570, 380]
    },
    {
      "kind": "visual_understanding",
      "extractor": "groq-vision",
      "region": [50, 400, 550, 720]
    }
  ]
}
```

Routing procedure:

1. Apply privacy policy.
2. Select the primary extractor.
3. Add table/formula/visual tasks where required.
4. Avoid redundant work when one extractor can reliably handle several tasks.
5. Route uncertain pages conservatively.

Initial PyMuPDF fast-path rule:

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

## 14. Task Grouping

Group tasks, not complete page plans.

Group key:

```python
GroupKey(
    document_id=task.document_id,
    extractor=task.extractor,
    profile=task.profile,
    kind=task.kind,
    options_hash=task.options_hash,
    privacy_mode=task.privacy_mode,
)
```

After keys match, group only when pages are:

- Consecutive
- Related
- Within the extractor’s maximum batch size
- Compatible in resolution and options

A page may occur in several groups:

```text
Page 8 -> PyMuPDF native-text group
Page 8 -> Docling table group
Page 8 -> Groq chart-region group
```

Starting limits:

- PyMuPDF: qualifying pages from one open document
- Gemini: 4-8 related pages, target 5
- Continuous scans: up to 10-20 after benchmarking
- Docling: 10-30 related pages
- Independent forms and uncertain pages: one page

## 15. Concurrent Execution

Use independent semaphores:

```python
semaphores = {
    "pymupdf": asyncio.Semaphore(cpu_limit),
    "docling": asyncio.Semaphore(docling_limit),
    "gemini": asyncio.Semaphore(gemini_limit),
    "groq-vision": asyncio.Semaphore(groq_limit),
}
```

The executor:

1. Selects an adapter.
2. Acquires its resource limit.
3. Applies a timeout.
4. Records an attempt.
5. Executes extraction.
6. Converts exceptions to structured errors.
7. Returns partial results without cancelling unrelated groups.

Run CPU-heavy synchronous parsing outside FastAPI’s event loop.

## 16. Validation

Validate every returned page independently.

### Text

- Useful character count
- Printable and replacement ratios
- Duplicate lines and repeated symbols
- Missing expected text
- Unsupported or suspicious content

### Layout

- Bboxes inside page boundaries
- Positive bbox area
- Valid reading order
- Excessive overlap
- Duplicate paragraphs/headings

### Tables

- Non-empty rows/columns
- Consistent cell structure
- Valid Markdown/HTML when present
- Expected region was extracted
- Numeric values agree with visible evidence when cross-checking is possible

### Visuals

- Crop exists and has non-zero dimensions
- Bbox matches the page
- Expected visual element exists
- Description is grounded in the crop

Validation output must include machine-readable failure codes.

## 17. Failure-Specific Fallback

```python
FALLBACKS = {
    "NATIVE_TEXT_CORRUPT": "gemini",
    "READING_ORDER_INVALID": "docling:digital-layout",
    "TABLE_STRUCTURE_INVALID": "gemini",
    "FORMULA_MISSING": "docling:formula-code",
    "VISUAL_MEANING_MISSING": "groq-vision",
}
```

Rules:

- Check privacy policy before selecting a managed fallback
- Use `private-ocr` when managed APIs are prohibited
- Retry only failed pages or regions
- Apply bounded backoff to transient API failures
- Cap attempts per task/page
- Preserve every attempt and reason
- Preserve the page image and return an explicit failure if all routes fail

## 18. Merge and Deduplication

For each original page:

1. Normalize coordinates.
2. Combine results by page and region.
3. Detect overlapping elements.
4. Remove duplicate text.
5. Apply type-specific precedence.
6. Attach visual descriptions to visual elements.
7. Sort by reading order.
8. Assign stable element IDs.

Examples:

- Prefer Docling’s structured table over duplicate PyMuPDF plain table text.
- Keep PyMuPDF paragraphs outside the table region.
- Attach Groq’s description to the existing chart element.
- Never apply a universal “one extractor always wins” rule.

Conflicting claims must produce diagnostics rather than being silently removed.

## 19. Final Output

`document.json` contains canonical extraction output only.

`extraction-report.json` contains:

- Inspection features
- Routing decisions and reasons
- Task groups
- Extraction attempts
- Failures and fallbacks
- Durations
- Token usage and cost
- Validation results
- Extractor, adapter, model, profile, and prompt versions

Use `completed_with_warnings` when usable partial output exists.

## 20. End-to-End Service Flow

```python
async def process_extraction_job(job_id: str) -> None:
    job = await jobs.mark_validating(job_id)
    pdf = await input_service.validate(job.source_path)

    await jobs.mark_inspecting(job_id)
    inspection = await inspector.inspect(pdf)

    await jobs.mark_planning(job_id)
    plans = router.create_plans(inspection, job.policy)
    groups = group_planner.create_groups(plans)

    await jobs.mark_extracting(job_id)
    results = await executor.run(pdf, groups)

    await jobs.mark_validating_output(job_id)
    validations = validator.validate(results, inspection)

    await jobs.mark_retrying(job_id)
    resolved = await fallback_manager.resolve(
        pdf,
        results,
        validations,
        inspection,
        job.policy,
    )

    await jobs.mark_merging(job_id)
    document = merger.build(resolved)

    await storage.write_results(job_id, document)
    await jobs.complete(job_id, document.status)
```

## 21. Testing

### Unit tests

- PDF validation and limits
- Printable/garbage-character calculations
- Scan classification
- Coordinate conversion
- Task generation
- Group boundaries
- Temporary/original page mapping
- Duplicate detection
- Fallback selection
- Managed-API prohibition

### Adapter tests

Exercise each route independently through authorized API options:

- PyMuPDF only
- Docling `digital-layout`
- Docling `digital-table`
- Docling `private-ocr`
- Gemini only
- Groq vision only

### Integration fixtures

- Simple digital PDF
- Multi-column PDF
- Table-heavy PDF
- Fully scanned PDF
- Mixed digital/scanned PDF
- Chart-heavy PDF
- Multi-page table
- Rotated or poor-quality scan
- Page containing paragraphs, table, and chart together

The mixed-content page must verify:

```text
PyMuPDF extracts paragraphs
Docling extracts table structure
Groq interprets the chart
Merger removes duplicate table text
```

## 22. Implementation Order

### Phase 1: API foundation

1. Create FastAPI project.
2. Add configuration and error handling.
3. Add upload endpoint.
4. Add job models and statuses.
5. Add result endpoints.
6. Add workspace and input validation.

Acceptance:

- A valid PDF upload returns `202 Accepted` and a job ID.
- Invalid or oversized files are rejected.
- Job status is retrievable.

### Phase 2: Canonical schema and PyMuPDF baseline

1. Define all canonical and inspection models.
2. Implement PyMuPDF inspector.
3. Implement PyMuPDF adapter.
4. Write `inspection.json` and `document.json`.

Acceptance:

- Simple digital PDFs produce valid canonical text and coordinates.
- Scanned pages are identified but not yet fully extracted.

### Phase 3: Docling baseline

1. Implement warm profiles.
2. Add selected-page/sub-PDF processing.
3. Add original-page mapping.
4. Convert Docling output to canonical elements.

Acceptance:

- Complex layouts and digital tables produce canonical output.
- Local OCR works in local-only mode.

### Phase 4: Gemini baseline

1. Add structured extraction schema and versioned prompt.
2. Add rendered-page submission.
3. Add batching and page mapping.
4. Add API timeout, retry, token, and cost capture.

Acceptance:

- Scanned pages produce structured canonical output.
- Malformed responses are rejected.
- Managed APIs are never called when prohibited.

### Phase 5: Validators

1. Implement text validation.
2. Implement bbox/layout validation.
3. Implement table validation.
4. Implement visual validation.

Acceptance:

- Every page receives validation results and machine-readable failures.

### Phase 6: Router and grouping

1. Implement privacy-first multi-label routing.
2. Implement layered tasks.
3. Implement contiguous grouping.
4. Add context-only pages.
5. Add per-extractor concurrency controls.

Acceptance:

- A mixed PDF uses different extractors for appropriate pages and regions.
- One page can participate in multiple task groups.

### Phase 7: Fallback and merge

1. Implement failure-specific fallback.
2. Retry only failed work.
3. Implement coordinate normalization.
4. Implement deduplication and reading-order merge.

Acceptance:

- One failed page does not discard successful pages.
- Duplicate table text is removed without losing surrounding paragraphs.

### Phase 8: Groq visual semantics

1. Detect and crop meaningful visual regions.
2. Implement Groq structured output.
3. Attach results to canonical visual elements.

Acceptance:

- Charts and diagrams receive grounded descriptions when enabled.

### Phase 9: Reporting, caching, and hardening

1. Add extraction report.
2. Add version-aware cache.
3. Persist job state.
4. Add circuit breakers and resource limits.
5. Add metrics and structured logs.

Acceptance:

- Repeated identical extraction can use compatible cached results.
- Provider failures do not crash unrelated extraction groups.

### Phase 10: Calibration

1. Collect 20-50 documents and at least 500 representative pages.
2. Create labelled ground truth.
3. Measure all individual extractors.
4. Measure hybrid routing with and without fallback.
5. Tune routing thresholds and group sizes.
6. Calibrate confidence by extractor and task.

Acceptance:

- Hybrid extraction measurably improves quality or cost-adjusted quality over
  the strongest single-extractor baseline.

## 23. Development Principle

Implement and measure forced PyMuPDF, Docling, and Gemini paths before enabling
automatic routing. This isolates failures:

```text
input -> adapter -> canonical output -> validation
```

Only after those paths are trustworthy should the complete pipeline become:

```text
API upload
  -> inspect
  -> multi-label plan
  -> task grouping
  -> concurrent extraction
  -> validation
  -> failure-specific fallback
  -> merge
  -> canonical document and report
```
