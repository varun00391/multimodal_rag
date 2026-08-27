# Hybrid PDF Extraction Design

## 1. Purpose

This document defines the recommended PDF extraction architecture for the
Multimodal RAG application.

The current implementation sends the complete PDF through Docling. Docling
provides useful structure, tables, pictures, bounding boxes, and reading order,
but processing every page with the same pipeline creates unnecessary latency.
Many born-digital pages already contain a clean text layer and do not require a
full document-understanding model.

The recommended design is a hybrid, page-aware extraction router:

1. Inspect every page quickly with PyMuPDF.
2. Classify each page independently.
3. Create a layered extraction plan for text, structure, and visual regions. A
   page may use more than one extractor.
4. Select the lowest expected total-cost plan that satisfies quality, latency,
   privacy, and modality requirements.
5. Group only adjacent, related work assigned to the same extractor profile.
6. Normalize every extractor's response into one application-owned schema.
7. Validate output page by page and element by element.
8. Retry only failed or low-confidence work using the extractor most suitable
   for the observed failure.
9. Preserve extractor, model, adapter, schema, prompt, routing-policy, document,
   page, and source-coordinate provenance.
10. Retain searchable visual metadata for relevant figures even when expensive
    vision enrichment is deferred.

The initial extractor policy should be:

- **PyMuPDF:** clean born-digital text and positional extraction.
- **Optimized Docling:** complex digital layouts, tables, formulas, or pages
  where retaining document structure minimizes migration risk. Use a small set
  of cached feature profiles instead of arbitrary per-page model settings.
- **Gemini 2.5 Flash (testing phase):** scans, damaged text layers, difficult
  visual layouts, image-based tables, and failure-specific multimodal fallback.
  Use the available free token allowance during evaluation. Record the exact
  model ID and prompt/schema version for reproducibility.
- **Groq vision enrichment:** analyze chart, figure, graph, and diagram regions
  when their visual meaning is needed. At minimum, retain their crops, nearby
  text, captions, OCR, or image embeddings so retrieval can discover them.

## 2. Why the Current Docling Path Is Slow

The current `rag/ingest.py` configuration performs several expensive operations:

```python
pipeline_options.images_scale = 2.0
pipeline_options.generate_page_images = True
pipeline_options.generate_picture_images = True
pipeline_options.do_table_structure = True
pipeline_options.do_ocr = False
```

This means:

- Every page is rendered as a full-page PNG at 2× scale.
- Picture crops are generated and saved.
- Table-structure recognition runs across the document.
- A new `DocumentConverter` is created inside every `ingest_pdf()` call.
- OCR is disabled, so the current cost is not caused by OCR.
- Scanned pages may still have incomplete text extraction because OCR is off.
- The full Docling document is serialized into `document.json`.

The application also performs figure enrichment after Docling, adding more
extraction-stage latency.

Before replacing Docling, measure these stages independently:

- Converter initialization
- PDF parsing
- Layout detection
- Table-structure recognition
- Full-page rendering
- Picture and table crop generation
- PNG writing
- Docling JSON serialization
- Normalization
- Figure enrichment

Without stage-level timings, a slow image-writing or vision-enrichment stage can
be incorrectly attributed to Docling parsing.

## 3. Target Architecture

```text
PDF upload
   |
   v
Fast document and page inspection with PyMuPDF
   |
   v
Per-page features, policy checks, and routing confidence
   |
   v
Layered page plan (one page can use multiple branches)
   |
   +-- Native text branch ----------> PyMuPDF
   |
   +-- Structure branch ------------> Cached Docling profile
   |
   +-- OCR/understanding branch ----> Gemini 2.5 Flash
   |
   +-- Visual-region branch --------> Crop + searchable metadata
   |                                     |
   |                                     +--> Groq vision when required
   |
   v
Build contiguous extractor-and-profile-specific work groups
   |
   v
Run independent groups concurrently
   |
   v
Parser adapters -> canonical extraction schema
   |
   v
Page-level validation and confidence calculation
   |
   +-- Pass ------------------------> Keep result
   |
   +-- Fail ------------------------> Classify failure and select suitable fallback
   |
   v
Merge by original document, page, region, and reading order
   |
   v
Normalize -> chunk -> embed -> index in Qdrant
```

## 4. Important Routing Principles

### 4.1 PyMuPDF is an inspector and fast extractor

PyMuPDF does not produce one universal extraction confidence score. The router
must calculate its own score from measurable page features.

PyMuPDF can provide:

- Embedded text
- Text blocks, words, spans, fonts, and coordinates
- Page dimensions and rotation
- Images and image bounding boxes
- Vector drawings
- Character and block counts
- Basic table-detection signals

These signals are used to classify the page and estimate whether the native text
layer is trustworthy.

### 4.2 Classify before grouping

Every page must first receive its own extractor assignment. Grouping happens
after classification and must never force a page through the wrong parser.

For example:

```text
Page 1  -> PyMuPDF
Page 2  -> PyMuPDF
Page 3  -> Gemini 2.5 Flash
Page 4  -> Gemini 2.5 Flash
Page 5  -> Gemini 2.5 Flash
Page 6  -> PyMuPDF
```

The execution plan can be:

```text
Pages 1-2 -> PyMuPDF
Pages 3-5 -> Gemini 2.5 Flash
Page 6    -> PyMuPDF
```

Pages 3-5 are grouped only because they are consecutive and already have the
same route.

### 4.3 Preserve page identity

Every temporary sub-document must maintain a mapping between temporary and
original page numbers:

```json
{
  "group_id": "gemini-0003",
  "extractor": "gemini-2.5-flash",
  "temporary_pages": [1, 2, 3],
  "original_pages": [3, 4, 5]
}
```

All output must be converted back to original page numbers before chunking.

### 4.4 Never combine unrelated pages

Do not group:

- Non-consecutive pages
- Pages assigned to different extractors
- Unrelated forms
- Pages from different documents
- Pages with incompatible extraction settings

### 4.5 Use layered routing instead of one exclusive page route

The primary route describes how the page's main text and structure are handled,
but it must not prevent additional region-level work.

For example, a born-digital financial report page can use:

```text
PyMuPDF -> native paragraph text and coordinates
Docling -> table structure and reading order
Groq    -> semantic interpretation of one chart crop
```

This is preferable to sending the entire page to one parser and discarding the
strengths of the others. The page plan should therefore contain tasks rather
than only one extractor:

```json
{
  "page": 12,
  "primary_route": "pymupdf",
  "tasks": [
    {
      "kind": "native_text",
      "extractor": "pymupdf"
    },
    {
      "kind": "table_structure",
      "extractor": "docling",
      "profile": "digital-table"
    },
    {
      "kind": "visual_understanding",
      "extractor": "groq-vision",
      "region": [40, 310, 560, 740],
      "defer_until_retrieved": true
    }
  ]
}
```

Privacy and residency policy must be evaluated before cost and quality routing.
An externally managed extractor must never be selected when document policy
forbids it.

## 5. Page Inspection Features

The router should collect the following metadata for each page.

### 5.1 Text-layer signals

- Character count
- Word count
- Number of text blocks
- Printable-character ratio
- Unicode replacement-character count
- Null/control-character count
- Average word length
- Repeated-character ratio
- Text coverage across the page
- Percentage of words with valid bounding boxes
- Font count and font-size distribution
- Text overlap and duplicate-block ratio

### 5.2 Image and scan signals

- Number of images
- Largest image area
- Total image coverage
- Presence of one nearly full-page image
- Image resolution
- Background image coverage
- Text count despite high image coverage

A page with almost no native text and one image covering most of the page is
probably scanned.

### 5.3 Layout-complexity signals

- Number of columns
- Irregular block ordering
- Number of vector drawings
- Dense alignment of text and lines
- Probable table regions
- Large figures or charts
- Many small text regions
- Rotated text
- Headers, footers, and side notes

### 5.4 Continuity signals

These signals help determine whether neighbouring pages should stay together:

- A table reaches the bottom boundary
- The next page begins with a repeated table header
- A sentence ends without terminal punctuation
- A heading appears near the bottom
- A figure and its caption are on different pages
- Identical columns and fonts continue on the next page
- A numbered list continues
- Footnotes or references continue

## 6. Suggested Page Metadata

```json
{
  "document_id": "document-123",
  "page": 12,
  "width": 612,
  "height": 792,
  "rotation": 0,
  "text": {
    "characters": 42,
    "words": 8,
    "blocks": 2,
    "printable_ratio": 0.71,
    "replacement_character_ratio": 0.04,
    "coverage": 0.03
  },
  "images": {
    "count": 1,
    "largest_coverage": 0.94,
    "total_coverage": 0.94
  },
  "layout": {
    "probable_columns": 1,
    "probable_table": false,
    "large_figure": false,
    "complexity_score": 0.28
  },
  "routing": {
    "extractor": "gemini-2.5-flash",
    "confidence": 0.96,
    "reasons": [
      "Native text layer is sparse",
      "A raster image covers 94% of the page"
    ]
  }
}
```

## 7. Initial Routing Policy

The thresholds below are starting points. They must be calibrated using the
application's real PDF corpus.

The routing objective is not simply to choose the cheapest first call. It is to
select the lowest expected total-cost plan that satisfies:

- Required extraction quality
- End-to-end latency target
- Privacy and data-residency policy
- Required modalities and output structure
- Retry and failure-risk budget

Expected total cost includes parser calls, context overlap, retries, rendering,
temporary storage, vision enrichment, and self-hosted compute.

### 7.1 PyMuPDF route

Choose PyMuPDF when:

- Native text is present and sufficiently dense.
- The printable-character ratio is high.
- Text blocks have valid coordinates.
- Image coverage is low or images are decorative.
- No probable complex table is present.
- Reading order is simple.
- No OCR warning signals are present.

Example starting rule:

```python
use_pymupdf = (
    character_count >= 500
    and printable_ratio >= 0.95
    and replacement_character_ratio <= 0.01
    and image_coverage <= 0.35
    and not probable_complex_table
    and layout_complexity <= 0.45
)
```

PyMuPDF is appropriate for text extraction, headings, coordinates, and embedded
images. It is not by itself a semantic chart or scanned-page understanding
system.

### 7.2 Optimized Docling route

Choose Docling when:

- The PDF has a valid text layer but complex reading order.
- Multiple columns are present.
- A digital table needs structural reconstruction.
- Formula or code blocks are probable.
- Existing Docling-compatible output is valuable during migration.
- The document must remain private and GPU or CPU infrastructure is available.

Use a small, versioned set of warm Docling profiles, such as:

- `digital-layout`: layout and reading order, without page rendering.
- `digital-table`: layout plus table structure.
- `formula-code`: layout, table structure, formulas, and code where required.
- `private-ocr`: local OCR fallback when managed processing is prohibited.

Cache one converter or worker pool per profile. Arbitrary per-page feature
combinations can increase model initialization and cache churn enough to remove
the expected latency benefit.

Docling should not automatically render full-page images for every page. Images
should be created only for:

- Pages selected as visual answer evidence
- Detected figures
- Detected tables
- OCR fallback
- User preview requests

### 7.3 Gemini 2.5 Flash route

Choose Gemini 2.5 Flash when:

- Native text is absent or sparse.
- A raster image covers most of the page.
- Extracted text contains corrupted characters.
- A table exists only as an image.
- The page contains handwriting or difficult forms.
- Charts and visually encoded information need extraction.
- Another extractor's result fails validation.
- Multilingual OCR quality is required.

Gemini 2.5 Flash is a general multimodal model rather than a dedicated OCR
service. Require structured JSON output and provide an explicit extraction
schema and prompt. Do not treat model-reported self-confidence as calibrated
OCR confidence; rely on application validation. Test table structure, reading
order, coordinates, and hallucination rate carefully against ground truth.

Sending documents to the Gemini API must comply with privacy, residency,
retention, and free-tier data-use requirements.

### 7.4 Conservative uncertain route

When the router is uncertain, prefer extraction quality over the cheapest path.
The initial testing implementation should route uncertain pages to Docling or
Gemini and collect telemetry. Thresholds can be tightened after false-positive
and false-negative rates are known.

### 7.5 Groq visual-region route

Groq vision is an element-level enrichment route rather than the primary PDF
parser. Use it when a chart, graph, figure, or diagram contains meaning that
cannot be represented sufficiently by native text, captions, or OCR.

Every potentially useful visual should retain:

- Original page and bounding box
- Image crop or reproducible crop instructions
- Native caption and nearby referring text
- Basic OCR text when applicable
- Optional image embedding
- Enrichment status and prompt/model provenance

Without one of these searchable representations, retrieval may never discover a
visual element that should receive deferred vision analysis.

## 8. Routing Confidence

Keep these confidence concepts separate:

1. **Routing confidence:** confidence that the chosen extractor is appropriate.
2. **Parser confidence:** confidence reported by the extractor, when available.
3. **Validation confidence:** application-calculated confidence that the result
   is usable.

Example:

```json
{
  "routing_confidence": 0.91,
  "parser_confidence": 0.88,
  "validation_confidence": 0.94,
  "overall_confidence": 0.90
}
```

Do not calculate the overall confidence as a simple average without calibration.
A conservative starting formula is:

```python
overall_confidence = min(
    routing_confidence,
    parser_confidence or 1.0,
    validation_confidence,
)
```

The formula above is only a temporary safety heuristic. Routing scores, Docling
signals, Gemini outputs, and validation scores are not naturally comparable.
Production thresholds must be calibrated separately for each extractor and task
type against labelled pass/fail outcomes.

Record the original scores separately even after calibration:

```json
{
  "routing_confidence": 0.91,
  "parser_confidence_raw": 0.88,
  "parser_confidence_calibrated": 0.93,
  "validation_confidence": 0.94,
  "calibration_version": "gemini-2.5-flash-table-v1"
}
```

## 9. Single Pages Versus Page Groups

### 9.1 Single-page processing

Advantages:

- Exact parser selection
- Smallest retry unit
- Strong fault isolation
- Suitable for independent forms
- Easy page mapping

Disadvantages:

- More network requests
- More API and scheduling overhead
- Greater rate-limit pressure
- Repeated local model initialization unless services are kept warm
- Loss of cross-page context
- Poorer handling of continuing tables, paragraphs, and captions

### 9.2 Group processing

Advantages:

- Fewer requests
- Better GPU batching
- Better cross-page context
- Lower initialization overhead
- Better throughput
- Less rate-limit pressure

Disadvantages:

- More complicated page mapping
- Larger memory use
- Larger failure unit if validation is not page-aware
- Wasteful retries if the full group is retried
- Very large groups can introduce unrelated context

### 9.3 Recommended adaptive micro-batching

Use contiguous micro-batches:

- PyMuPDF: open the original document once and process all qualifying pages.
- Gemini 2.5 Flash: normally 4-8 consecutive related pages.
- Continuous scanned documents: approximately 10-20 pages.
- Docling: approximately 10-30 consecutive pages with a persistent converter.
- Independent forms: one page at a time.
- Multi-page tables: keep the complete continuing table together.
- Uncertain pages: initially process individually.

These values are operational starting points, not fixed requirements.

## 10. Cross-Page Context

Grouping should be based on continuity, not only identical parser assignment.

For example:

```text
Pages 10-12 -> Gemini 2.5 Flash
```

is useful when page 10 starts a table and pages 11-12 continue it.

If page 12 is unrelated, use:

```text
Pages 10-11 -> Gemini 2.5 Flash
Page 12     -> separate group
```

When context is needed across a group boundary, one neighbouring page can be
included as context. Mark it as context-only and deduplicate its output during
merge:

```json
{
  "group_pages": [20, 21, 22, 23],
  "primary_pages": [21, 22, 23],
  "context_pages": [20]
}
```

Overlap slightly increases page-based API cost and must only be used when
continuity signals justify it.

## 11. Timing and Cost Model

Published parser benchmarks use different documents, hardware, concurrency, and
quality settings. The following figures are planning estimates and must be
verified on the same representative test set.

### 11.1 Example 100-page document

Assume:

- 80 clean digital pages
- 10 complex digital pages
- 10 scanned or difficult visual pages

Possible routes:

- 80 pages through PyMuPDF
- 10 pages through optimized Docling
- 10 pages through Gemini 2.5 Flash

Because independent routes can run concurrently, estimated wall-clock extraction
time is approximately 8-30 seconds after warm-up, depending on hardware, API
queueing, page complexity, and image writing.

This estimate excludes downstream embedding and indexing.

### 11.2 Gemini testing cost

During the testing phase, Gemini API cost can be $0 while requests remain
inside the available free token and rate-limit allowance. Gemini is token-based,
not page-priced, so page count alone cannot determine the paid cost.

```text
Gemini cost =
    input tokens × current input-token rate
    + output tokens × current output-token rate
```

Record actual usage for every extraction group:

```json
{
  "model": "gemini-2.5-flash",
  "input_tokens": 0,
  "output_tokens": 0,
  "cached_input_tokens": 0,
  "estimated_cost_usd": 0,
  "free_tier_applied": true
}
```

Do not assume testing will remain free in production. Recalculate cost using
Google's current pricing, expected PDF tokenization, output verbosity, context
overlap, retries, and request caching before rollout.

### 11.3 Single-page versus group API cost

With Gemini, grouping can affect token cost because repeated system instructions,
schemas, document context, and output wrappers are charged for every request.
For 20 difficult pages:

```text
20 single-page requests = extraction tokens + 20 prompt/schema copies
4 groups of 5 pages      = extraction tokens + 4 prompt/schema copies
1 group of 20 pages      = extraction tokens + 1 prompt/schema copy
```

While free quota is available, the direct charge may remain $0, but grouping
still preserves quota and reduces request/rate-limit pressure.

Token use increases through overlap, verbose output, and retries:

```text
More context pages -> more input tokens
Verbose JSON/Markdown -> more output tokens
Two page retries -> input and output tokens for those pages are paid again
Full group retry -> all group input and output tokens are paid again
```

### 11.4 Latency effect of grouping

Assume 20 difficult pages and a maximum of five concurrent requests. Actual
Gemini latency depends on PDF complexity, token volume, quota, and service load:

- 20 sequential single-page requests: potentially 30-120 seconds.
- 20 single-page requests with concurrency of five: approximately 10-35 seconds.
- Four concurrent five-page groups: approximately 5-20 seconds.
- One 20-page group: approximately 5-25 seconds, but with a larger failure unit.

These are planning ranges, not service-level guarantees.

Four concurrent groups of approximately five related pages usually provide the
best latency, context, and fault-isolation balance.

## 12. Canonical Extraction Schema

The application must own the extraction schema instead of using Docling's schema
as its permanent internal contract.

Suggested document representation:

```json
{
  "schema_version": "1.0",
  "document_id": "document-123",
  "source": {
    "filename": "report.pdf",
    "sha256": "..."
  },
  "pages": [
    {
      "page": 1,
      "width": 612,
      "height": 792,
      "primary_route": "pymupdf",
      "extraction_routes": [
        {
          "task": "native_text",
          "extractor": "pymupdf",
          "extractor_version": "pinned-package-version",
          "adapter_version": "1.0"
        }
      ],
      "routing_confidence": 0.98,
      "validation_confidence": 0.97,
      "elements": []
    }
  ]
}
```

Suggested element representation:

```json
{
  "element_id": "document-123:p12:e4",
  "type": "table",
  "page": 12,
  "reading_order": 4,
  "text": "Table contents",
  "markdown": "| Column A | Column B |",
  "html": "<table>...</table>",
  "bbox": {
    "left": 40,
    "top": 120,
    "right": 550,
    "bottom": 640,
    "coordinate_origin": "top-left"
  },
  "image": "images/document-123_page_12_table_1.png",
  "extractor": {
    "name": "gemini",
    "version": "gemini-2.5-flash",
    "adapter_version": "1.0"
  },
  "confidence": 0.96,
  "provenance": {
    "document_version": "sha256:...",
    "schema_version": "1.0",
    "routing_policy_version": "2026-08-27",
    "profile": "scanned-structured",
    "prompt_version": null,
    "source_page": 12,
    "source_coordinate_system": "pdf-points-bottom-left",
    "canonical_coordinate_system": "pdf-points-top-left"
  },
  "metadata": {}
}
```

Supported element types should include:

- `heading`
- `paragraph`
- `list`
- `table`
- `picture`
- `chart`
- `formula`
- `code`
- `key_value`
- `header`
- `footer`
- `footnote`
- `page_number`

All bounding boxes must use one documented coordinate system.

## 13. Parser Adapters

Implement one adapter for each extractor:

```python
class ExtractionAdapter(Protocol):
    async def extract(
        self,
        pdf_path: Path,
        pages: list[int],
        context_pages: list[int] | None = None,
    ) -> CanonicalExtractionResult:
        ...
```

Initial adapters:

- `PyMuPDFExtractionAdapter`
- `DoclingExtractionAdapter`
- `GeminiFlashExtractionAdapter`

Each adapter is responsible for:

- Calling the parser
- Mapping temporary page numbers to original page numbers
- Converting coordinates
- Mapping parser-specific element types
- Preserving parser confidence
- Extracting or referencing images
- Returning structured parser errors

## 14. Validation

Validate every page independently, even when it was submitted inside a group.

### 14.1 Text validation

- Minimum useful character count
- Printable-character ratio
- Replacement-character ratio
- Duplicate-line ratio
- Excessive repeated symbols
- Missing content relative to inspection metadata
- Suspiciously empty output

### 14.2 Layout validation

- Elements remain inside page bounds
- Bounding boxes have positive area
- Excessive bounding-box overlap is absent
- Reading-order indices are valid
- Headings and paragraphs are not duplicated

### 14.3 Table validation

- Expected rows and columns exist
- Table output is not empty
- Repeated headers are handled
- Multi-page tables are linked
- Markdown and HTML structures are valid

### 14.4 Visual validation

- Expected figures are present
- Image paths exist
- Crops have non-zero dimensions
- Chart pages contain chart or image elements

### 14.5 Cross-parser consistency

For uncertain pages during rollout, occasionally run two extractors and compare:

- Character coverage
- Heading detection
- Table cell counts
- Number of figures
- Reading order

This shadow evaluation creates labelled routing data without affecting the user
response.

## 15. Fallback Policy

Fallback is failure-specific, not a universal progression from a weaker parser
to a stronger parser. Suggested decisions:

```text
Corrupt or missing native text:
    PyMuPDF -> Gemini 2.5 Flash

Incorrect digital reading order or multi-column structure:
    PyMuPDF -> Docling digital-layout profile

Incorrect digital table structure:
    Docling digital-table profile -> Gemini 2.5 Flash when policy permits

Missing formula or code structure:
    PyMuPDF -> Docling formula-code profile

Missing chart or figure meaning:
    Extract region -> Groq vision

Managed API prohibited or unavailable:
    Gemini route -> local Docling/Marker policy fallback

Transient managed-API failure:
    Retry the same extractor with bounded exponential backoff
```

Rules:

- Retry transient network and rate-limit errors with exponential backoff.
- Do not retry invalid input indefinitely.
- Retry only failed pages, not the full group.
- Set a maximum extraction attempt count per page.
- Record every attempt for observability.
- Preserve the failure reason that selected the fallback.
- Do not assume one extractor is universally stronger than another.
- If every extractor fails, preserve the original page image and return a
  structured extraction failure.

## 16. Concurrency and Resource Control

Use separate concurrency limits for each extractor:

```text
PyMuPDF workers: based on CPU and file-descriptor limits
Docling workers: based on GPU memory or CPU RAM
Gemini requests: based on API token, request, and concurrency limits
Vision enrichment: based on Groq rate limits
```

Do not use one global worker pool because each extractor consumes different
resources.

Recommended controls:

- Per-document group limit
- Global extractor semaphore
- Request timeout
- Maximum PDF size
- Maximum rendered-pixel count
- Maximum pages per group
- Retry budget
- Circuit breaker for unavailable managed APIs
- Backpressure from the ingestion queue

## 17. Caching

Cache at page and configuration level:

```text
cache key =
    PDF SHA-256
    + original page number
    + region or task identity
    + extractor name/version
    + adapter version
    + extraction options hash
    + routing policy version
    + prompt version when applicable
    + canonical schema version
```

Cache:

- Inspection metadata
- Routing decision
- Raw parser output
- Canonical page result
- Generated page and element images
- Validation result

Do not return a cached result after parser settings or schema versions change
unless compatibility is guaranteed.

## 18. Observability

Record these fields for every page:

- Document ID and page number
- Selected route
- Routing reasons
- Routing confidence
- Group ID and group size
- Queue duration
- Extraction duration
- Validation duration
- Extractor version
- API or compute cost estimate
- Retry count
- Fallback route
- Output element counts
- Final confidence
- Failure code

Key metrics:

- Pages per second by extractor
- End-to-end extraction latency
- p50, p95, and p99 page latency
- Cost per 1,000 pages
- Percentage routed to each extractor
- Validation failure rate
- Fallback rate
- API retry and rate-limit rate
- Table and image extraction success
- Cache hit rate

## 19. Security and Privacy

Before enabling Gemini 2.5 Flash:

- Confirm whether uploaded PDFs may leave the deployment environment.
- Review API data-retention and training policies.
- Select an appropriate processing region.
- Encrypt files in transit and at rest.
- Avoid logging extracted document text.
- Store API keys only in secrets or environment configuration.
- Delete temporary sub-PDFs after processing.
- Use random temporary filenames.
- Prevent path traversal and decompression-style resource attacks.
- Limit pages, file size, render resolution, and processing time.

Provide an on-prem-only policy that routes all Gemini pages to Docling when
external processing is prohibited. Free-tier terms must be reviewed separately
from paid enterprise API terms before processing sensitive documents.

## 20. Integration with the Current Application

The current extraction flow calls `rag.ingest.ingest_pdf()` from the extraction
service. The existing normalizer requires `docling_document` and traverses
Docling references.

The migration should introduce these boundaries:

```text
Extraction service
  -> PageInspector
  -> RoutingPolicy
  -> GroupPlanner
  -> Extractor adapters
  -> CanonicalResultMerger
  -> ExtractionValidator
  -> canonical document.json

Chunking/indexing service
  -> CanonicalNormalizer
  -> existing chunk/embed/index flow
```

Do not make PyMuPDF or Gemini generate fake Docling internals. Replace the
normalizer's parser-specific dependency with the canonical schema.

During migration, support both formats:

```python
if payload.get("schema_version") == "1.0":
    normalize_canonical_document(payload)
elif payload.get("docling_document"):
    normalize_docling_document(payload)
else:
    raise UnsupportedExtractionSchema(...)
```

## 21. Suggested Configuration

```env
EXTRACTION_ROUTER_ENABLED=true
EXTRACTION_SCHEMA_VERSION=1.0

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

GEMINI_MODEL_ID=gemini-2.5-flash
GEMINI_MIN_PAGES_PER_GROUP=1
GEMINI_TARGET_PAGES_PER_GROUP=5
GEMINI_MAX_PAGES_PER_GROUP=10
GEMINI_MAX_CONCURRENCY=4
GEMINI_REQUEST_TIMEOUT_SECONDS=180
GEMINI_STRUCTURED_OUTPUT_ENABLED=true
GEMINI_EXTRACTION_PROMPT_VERSION=1
GEMINI_FREE_TIER_BUDGET_GUARD_ENABLED=true

EXTRACTION_ROUTING_POLICY_VERSION=2026-08-27
EXTRACTION_MAX_ATTEMPTS_PER_PAGE=3
EXTRACTION_MIN_VALIDATION_CONFIDENCE=0.85
EXTRACTION_CONTEXT_OVERLAP_ENABLED=true
EXTRACTION_CACHE_ENABLED=true

GROQ_VISUAL_ENRICHMENT_ENABLED=true
GROQ_VISUAL_ENRICHMENT_MODE=deferred
GROQ_VISUAL_PROMPT_VERSION=1
```

Thresholds must remain configurable because document characteristics differ
between deployments.

## 22. Implementation Pseudocode

```python
async def extract_pdf(pdf_path: Path) -> CanonicalDocument:
    document_hash = sha256_file(pdf_path)

    inspection = await page_inspector.inspect(pdf_path)

    page_plans = [
        routing_policy.create_layered_plan(page_metadata)
        for page_metadata in inspection.pages
    ]

    groups = group_planner.create_contiguous_groups(
        tasks=[
            task
            for plan in page_plans
            for task in plan.extraction_tasks
        ],
        continuity=inspection.continuity,
    )

    group_results = await asyncio.gather(
        *[
            extractor_registry[group.extractor].extract(
                pdf_path=pdf_path,
                pages=group.primary_pages,
                context_pages=group.context_pages,
            )
            for group in groups
        ],
        return_exceptions=True,
    )

    canonical_pages = result_merger.map_to_original_pages(
        groups,
        group_results,
    )

    for page in canonical_pages:
        validation = validator.validate(page, inspection.pages[page.page - 1])

        if validation.confidence < settings.minimum_confidence:
            page = await fallback_manager.retry_page(
                pdf_path=pdf_path,
                page=page.page,
                previous_attempt=page,
                validation=validation,
                failure_reason=validation.primary_failure_reason,
            )

        page.validation = validation

    visual_elements = visual_planner.discover(canonical_pages)
    await visual_enrichment.store_searchable_representations(visual_elements)
    await visual_enrichment.run_required_ingest_enrichment(visual_elements)

    return result_merger.build_document(
        document_hash=document_hash,
        pages=canonical_pages,
    )
```

## 23. Benchmark Plan

Create a representative test set rather than testing only one PDF.

Suggested categories:

- Clean single-column digital documents
- Multi-column reports
- Table-heavy financial reports
- Scientific papers with formulas
- Scanned documents
- Mixed digital and scanned documents
- Forms
- Chart-heavy presentations
- Multilingual documents
- Poor-quality or rotated scans

Recommended minimum: 20-50 documents and at least 500 representative pages.

Measure:

- Text character error or normalized edit distance
- Reading-order correctness
- Heading hierarchy accuracy
- Table structure accuracy
- Figure and chart recall
- Bounding-box accuracy
- End-to-end latency
- Warm and cold latency
- Peak memory and GPU memory
- API and compute cost
- Cost per successfully validated page, including retries and overlaps
- Retry and fallback rate
- Confidence calibration error by extractor and task
- Retrieval recall for deferred visual elements

Compare:

- Current Docling pipeline
- Optimized Docling
- PyMuPDF only
- Gemini 2.5 Flash only
- Hybrid router
- Marker or MinerU if self-hosted alternatives remain under consideration

## 24. Rollout Plan

### Phase 1: Instrument and optimize Docling

- Add stage-level timing.
- Reuse a warm `DocumentConverter`.
- Define and cache a small set of Docling feature profiles.
- Reduce default image scale to 1.0-1.5.
- Generate full-page images lazily.
- Confirm which extracted crops are actually consumed.
- Add GPU acceleration and batching where available.

### Phase 2: Introduce the canonical schema

- Define typed canonical models.
- Add a Docling adapter.
- Add complete model, adapter, schema, prompt, and policy provenance.
- Update normalization to support canonical input.
- Preserve compatibility with existing indexed documents.

### Phase 3: Add PyMuPDF inspection and fast extraction

- Collect page metadata.
- Implement initial layered routing rules.
- Fast-path clearly safe digital pages.
- Send uncertain pages to Docling.
- Allow additional table or visual-region tasks on PyMuPDF primary pages.
- Run shadow comparisons and tune thresholds.

### Phase 4: Add Gemini 2.5 Flash

- Add the managed API adapter.
- Add privacy-policy routing.
- Configure and record the exact model ID.
- Define a versioned extraction prompt and structured JSON schema.
- Capture token usage and estimated paid cost even while free quota is used.
- Add a free-tier budget and rate-limit guard.
- Add contiguous micro-batching.
- Add concurrency, retries, timeouts, and a circuit breaker.
- Validate every returned page independently.

### Phase 5: Enable confidence fallback

- Implement the failure-reason fallback matrix.
- Calibrate confidence separately by extractor and task type.
- Retry only failed pages.
- Store searchable metadata for deferred visual enrichment.
- Add extraction-quality dashboards and alerts.

### Phase 6: Production tuning

- Tune thresholds using observed failures.
- Adjust group sizes and concurrency.
- Compare cost and latency against the original Docling baseline.
- Pin parser versions where reproducible output is required.

## 25. Final Recommendation

Use individual page classification followed by adaptive contiguous
micro-batching and layered element-level routing.

The recommended production policy is:

1. Inspect each page with PyMuPDF.
2. Apply privacy and residency policy before selecting external services.
3. Build a layered page plan: text, structure, OCR, and visual regions may use
   different extractors on the same page.
4. Use PyMuPDF for reliable native text and positions.
5. Use cached, versioned Docling profiles for complex digital structure, tables,
   formulas, code, and local-only processing.
6. Use Gemini 2.5 Flash during testing for scans, corrupted text layers,
   image-based tables, and suitable failure-specific fallback. Require
   structured output, record token usage, and validate against hallucinations.
7. Keep related adjacent work together, especially multi-page tables, while
   keeping independent forms and uncertain work isolated.
8. Retain searchable crops and metadata for visual elements; use Groq vision
   when their semantic meaning is required.
9. Validate every page and element independently, with separately calibrated
   confidence for each extractor and task.
10. Select fallback by failure reason and retry only failed work.
11. Normalize all output into an application-owned canonical schema with full
    model, adapter, prompt, policy, document, page, and coordinate provenance.
12. Benchmark quality, latency, total cost per successful page, visual retrieval
    recall, and reliability on the real corpus before production rollout.

This approach preserves extraction quality and page context while avoiding the
time and cost of running the heaviest parser on every page.

## 26. References

- [Docling technical report and benchmarks](https://arxiv.org/abs/2501.17887)
- [Docling GPU acceleration guidance](https://docling-project.github.io/docling/getting_started/rtx/)
- [PyMuPDF text-extraction performance](https://pymupdf.readthedocs.io/en/latest/app4.html)
- [Gemini 2.5 Flash model documentation](https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Marker repository and benchmarks](https://github.com/datalab-to/marker)
- [MinerU 2.5 paper](https://arxiv.org/abs/2509.22186)
- [PaddleOCR PP-StructureV3](https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html)
- [LlamaParse pricing](https://developers.llamaindex.ai/llamaparse/general/pricing/)
- [Azure Document Intelligence pricing](https://azure.microsoft.com/en-us/pricing/details/document-intelligence/)
- [Google Document AI pricing](https://cloud.google.com/products/document-ai/pricing)
- [AWS Textract pricing](https://aws.amazon.com/textract/pricing/)

