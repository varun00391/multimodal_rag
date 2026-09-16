# Multimodal PDF Extraction System — Implementation Blueprint

## 1. Goal

Build a production-oriented PDF extraction system that can process:

- Born-digital PDFs
- Scanned PDFs
- Hybrid PDFs
- Mixed-content pages

and extract:

- Text
- Headings
- Paragraphs
- Lists
- Tables
- Complex tables
- Images
- Figures
- Charts
- Diagrams
- Equations
- Forms
- Captions
- Footnotes
- Headers / footers
- OCR text
- PDF-native objects
- Spatial relationships
- Semantic relationships
- Provenance
- Confidence / validation status

The system must minimize information loss and preserve enough evidence to trace every extracted element back to the source PDF.

---



# 2. Core Mental Model

The implementation should follow:

```text
PRESERVE
   ↓
PROFILE
   ↓
DECOMPOSE
   ↓
ROUTE
   ↓
EXTRACT
   ↓
VALIDATE
   ↓
RECONSTRUCT
   ↓
OUTPUT
```

Expanded:

```text
User uploads PDF
      ↓
Store original PDF
      ↓
Create extraction job
      ↓
PDF profiling
      ↓
Render pages + inspect PDF-native objects
      ↓
Detect regions on each page
      ↓
Classify each region
      ↓
Route each region to specialist extractor
      ↓
Run extraction
      ↓
Reconcile multiple evidence sources
      ↓
Validate / score confidence
      ↓
Human review for exceptions
      ↓
Reconstruct reading order and relationships
      ↓
Create Canonical Document Model
      ↓
Generate JSON / Markdown / assets
```

---



# 3. Most Important Architecture Rule



## Page is NOT the extraction unit.

A page is a canvas.

A single page can contain:

```text
Page 5
 ├── Heading
 ├── Paragraph
 ├── Image
 ├── Table
 ├── Complex Table
 ├── Chart
 ├── Diagram
 └── Caption
```

Therefore:

```text
PDF
 ↓
Pages
 ↓
Regions
 ↓
Elements / sub-elements
```

Extraction decisions should happen primarily at the **region level**, not the whole-page level.

---



# 4. High-Level Architecture

```text
                         ┌───────────────────┐
                         │       USER        │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │   Upload API      │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │  Object Storage   │
                         │   Original PDF   │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │   Job / Queue     │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │   PDF Profiler    │
                         │     PyMuPDF       │
                         └─────────┬─────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
             PDF-native data               Rendered pages
                    │                             │
                    └──────────────┬──────────────┘
                                   ▼
                         ┌───────────────────┐
                         │ Region Detection  │
                         │ Layout Analysis   │
                         └─────────┬─────────┘
                                   │
                  ┌────────────────┼────────────────┐
                  │                │                │
                  ▼                ▼                ▼
                Text             Table           Visual
                  │                │                │
                  ▼                ▼          ┌─────┼─────┐
              Text Engine      Table Engine  Image Chart Diagram
                  │                │           │     │     │
                  └────────────────┼───────────┴─────┴─────┘
                                   ▼
                         ┌───────────────────┐
                         │ Reconciliation    │
                         │ / Evidence Merge  │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │ Validation Engine │
                         └─────────┬─────────┘
                                   │
                          ┌────────┴────────┐
                          ▼                 ▼
                       PASS             CONFLICT
                          │                 │
                          │           Human Review
                          │                 │
                          └────────┬────────┘
                                   ▼
                         ┌───────────────────┐
                         │ Context Builder   │
                         │ Reading Order     │
                         │ Relationships     │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │ Canonical         │
                         │ Document Model    │
                         └─────────┬─────────┘
                                   │
                     ┌─────────────┼─────────────┐
                     ▼             ▼             ▼
                   JSON        Markdown        Assets
```

---



# 5. Recommended Technology Strategy

Use specialized tools rather than a single parser.

## PDF-native extraction

Primary:

```text
PyMuPDF
```

Responsibilities:

- Open PDF
- Inspect pages
- Extract native text
- Extract words / spans / blocks
- Extract coordinates
- Extract images
- Extract vector / drawing information
- Extract links / annotations where useful
- Render pages

Do not make PyMuPDF responsible for semantic classification.

---



## OCR

Use OCR as an evidence source, especially for scanned or rasterized regions.

Candidates to benchmark:

```text
PaddleOCR
Google Cloud Document AI
Azure AI Document Intelligence
AWS Textract
ABBYY
Tesseract (fallback / baseline)
```

The implementation should allow OCR engines to be swapped.

Define a common interface:

```python
class OCREngine:
    def extract(self, image_path: str) -> "OCRResult":
        ...
```

---



## Layout / Region detection

Responsibilities:

- Detect regions
- Classify region type
- Produce bounding boxes
- Detect hierarchy where possible

Possible tooling:

```text
Docling
layout detection models
custom object-detection / document-layout models
```

Do not assume one library is responsible for the whole pipeline.

---



## Table extraction

Use a specialized table pipeline.

Possible stack:

```text
Docling / table extraction
+
OCR or native text
+
VLM verification for complex cases
```

Tables should preserve:

- Rows
- Columns
- Cell boundaries
- Row span
- Column span
- Merged cells
- Header hierarchy
- Units
- Footnotes
- Caption
- Source coordinates

---



## Visual understanding

Use a VLM selectively.

Good candidates:

```text
Charts
Diagrams
Complex figures
Images containing text
Screenshots
Visual relationships
Ambiguous regions
```

Do not send every page or every image to the VLM.

Route only when necessary.

---



# 6. Project Structure

Recommended initial repository:

```text
pdf-extractor/
│
├── app/
│   ├── api/
│   │   ├── routes_documents.py
│   │   ├── routes_jobs.py
│   │   └── routes_review.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   │
│   ├── ingestion/
│   │   ├── upload.py
│   │   ├── storage.py
│   │   └── hashing.py
│   │
│   ├── profiling/
│   │   ├── pdf_profiler.py
│   │   ├── page_profiler.py
│   │   └── pdf_classifier.py
│   │
│   ├── rendering/
│   │   ├── page_renderer.py
│   │   └── crop_renderer.py
│   │
│   ├── layout/
│   │   ├── region_detector.py
│   │   ├── region_classifier.py
│   │   └── region_tree.py
│   │
│   ├── extractors/
│   │   ├── base.py
│   │   ├── text/
│   │   │   ├── native_pdf.py
│   │   │   ├── ocr.py
│   │   │   └── text_reconciler.py
│   │   ├── tables/
│   │   │   ├── docling.py
│   │   │   ├── table_ocr.py
│   │   │   └── table_reconciler.py
│   │   ├── visuals/
│   │   │   ├── image_extractor.py
│   │   │   ├── chart_extractor.py
│   │   │   └── diagram_extractor.py
│   │   └── vlm/
│   │       ├── client.py
│   │       └── prompts.py
│   │
│   ├── orchestration/
│   │   ├── planner.py
│   │   ├── router.py
│   │   └── pipeline.py
│   │
│   ├── validation/
│   │   ├── confidence.py
│   │   ├── reconciliation.py
│   │   ├── consistency.py
│   │   └── rules.py
│   │
│   ├── context/
│   │   ├── reading_order.py
│   │   ├── relationships.py
│   │   └── context_builder.py
│   │
│   ├── models/
│   │   ├── document.py
│   │   ├── page.py
│   │   ├── region.py
│   │   ├── element.py
│   │   ├── table.py
│   │   ├── figure.py
│   │   ├── provenance.py
│   │   └── validation.py
│   │
│   ├── outputs/
│   │   ├── json_writer.py
│   │   ├── markdown_writer.py
│   │   └── asset_writer.py
│   │
│   └── workers/
│       ├── extraction_worker.py
│       └── review_worker.py
│
├── tests/
├── configs/
├── scripts/
├── docker/
├── requirements.txt
└── README.md
```

---



# 7. Step-by-Step Runtime Workflow



## Step 1 — Upload

Endpoint:

```http
POST /documents
```

Input:

```text
multipart/form-data
PDF file
```

Actions:

1. Validate file.
2. Calculate hash.
3. Store original.
4. Create document record.
5. Create extraction job.

Response:

```json
{
  "document_id": "doc_123",
  "job_id": "job_456",
  "status": "QUEUED"
}
```

---



# 8. Step 2 — PDF Profiling

`pdf_profiler.py`

Inspect:

```text
page_count
PDF version
encrypted?
page dimensions
native text count
image count
vector object count
OCR layer presence
fonts
annotations
metadata
```

Per-page profile:

```json
{
  "page_number": 5,
  "native_text_chars": 1520,
  "image_count": 2,
  "vector_count": 180,
  "has_ocr_layer": false,
  "is_probably_scanned": false
}
```

This is **profiling**, not final content classification.

---



# 9. Step 3 — Render Pages

Render pages to images:

```text
artifacts/pages/page_001.png
artifacts/pages/page_002.png
...
```

Recommended metadata:

```json
{
  "page": 5,
  "width_px": 2480,
  "height_px": 3508,
  "dpi": 300
}
```

Keep the rendering configuration reproducible.

---



# 10. Step 4 — Native PDF Extraction

Extract page-native objects:

```text
words
lines
spans
blocks
images
drawings
links
annotations
```

Store every object with:

```text
id
page
bbox
content
object type
source = pymupdf
```

Example:

```json
{
  "id": "native_text_100",
  "type": "text",
  "page": 5,
  "bbox": [100, 200, 450, 230],
  "text": "Revenue increased by 15%",
  "source": "pymupdf"
}
```

---



# 11. Step 5 — Region Detection

Input:

```text
page image
+
native PDF objects
```

Output:

```json
[
  {
    "id": "r1",
    "type": "heading",
    "bbox": [50, 40, 500, 80]
  },
  {
    "id": "r2",
    "type": "paragraph",
    "bbox": [50, 100, 500, 170]
  },
  {
    "id": "r3",
    "type": "table",
    "bbox": [50, 200, 560, 500]
  },
  {
    "id": "r4",
    "type": "chart",
    "bbox": [60, 550, 550, 850]
  },
  {
    "id": "r5",
    "type": "diagram",
    "bbox": [60, 900, 550, 1250]
  }
]
```

This is the key routing decision.

---



# 12. Step 6 — Build the Region Tree

Regions may contain sub-regions.

Example:

```text
Figure
 ├── Chart
 │    ├── Plot
 │    ├── Legend
 │    ├── Axis labels
 │    └── Data labels
 └── Caption
```

Table:

```text
Table
 ├── Header
 ├── Body
 │    ├── Row
 │    │    ├── Cell
 │    │    └── Cell
 │    └── Row
 └── Footnote
```

The data model must allow parent/child relationships.

---



# 13. Step 7 — Region Routing

The router decides which extractor(s) to invoke.

Pseudo-logic:

```python
def route_region(region):
    if region.type in {"heading", "paragraph", "list", "footnote"}:
        return ["native_text", "ocr_fallback"]

    if region.type in {"table", "complex_table"}:
        return ["table_engine", "ocr", "vlm_verify"]

    if region.type == "image":
        return ["image_extractor"]

    if region.type == "chart":
        return ["ocr", "vlm"]

    if region.type == "diagram":
        return ["pdf_vectors", "ocr", "vlm"]

    if region.type in {"form", "screenshot", "scanned_document"}:
        return ["ocr", "layout", "vlm"]

    return ["vlm"]
```

This is a starting point, not a hard-coded final design.

---



# 14. Step 8 — Text Extraction Strategy

For text regions:

```text
Native PDF extraction
        ↓
Is text usable?
   ┌────┴────┐
  YES       NO
   │         │
   ▼         ▼
 accept      OCR
             ↓
        Is confidence good?
          ┌──┴──┐
         YES    NO
          │      │
          ▼      ▼
        accept   VLM
```

Do not OCR clean native text unnecessarily.

---



# 15. Step 9 — Table Extraction Strategy

For a normal table:

```text
Table region
   ↓
Table parser
   ↓
cells + structure
   ↓
validate
```

For a difficult table:

```text
Table region
   ↓
Table engine
   +
OCR/native text
   +
VLM verification
   ↓
Reconcile
   ↓
Validated table
```

Preserve:

```text
cell text
bbox
row index
column index
row span
column span
header relationships
footnotes
caption
```

---



# 16. Step 10 — Image Extraction

For an image region:

1. Prefer original embedded image if available.
2. Otherwise crop from the rendered page.
3. Preserve page bbox.
4. Determine whether the image contains meaningful text or structure.
5. If yes, route to OCR/VLM.

Example:

```text
Image
 ├── original_asset
 ├── bbox
 ├── page
 ├── image_type
 └── optional_description
```

---



# 17. Step 11 — Chart Extraction

For charts:

```text
Chart
 ↓
OCR
 ↓
VLM
 ↓
Chart interpretation
```

Try to preserve:

```text
title
x-axis
y-axis
units
legend
series
data labels
visible values
trend
caption
```

Do not rely only on a generated textual summary.

Always preserve the original chart image.

---



# 18. Step 12 — Diagram Extraction

For diagrams:

Use multiple evidence sources:

```text
PDF vector objects
+
OCR
+
VLM
```

Extract:

```text
nodes
labels
arrows
connectors
relationships
groups
caption
```

Example:

```json
{
  "type": "diagram",
  "nodes": [
    {"id": "n1", "label": "Client"},
    {"id": "n2", "label": "API"},
    {"id": "n3", "label": "Database"}
  ],
  "edges": [
    {"from": "n1", "to": "n2"},
    {"from": "n2", "to": "n3"}
  ]
}
```

---



# 19. Step 13 — Evidence Reconciliation

This component combines outputs from different tools.

Example:

```text
Native PDF:
INV-1023

OCR:
INV-1023

VLM:
INV-1023
```

Result:

```json
{
  "value": "INV-1023",
  "sources": ["pymupdf", "ocr", "vlm"],
  "status": "AGREED"
}
```

Conflict:

```text
Native PDF:
INV-1023

OCR:
INV-1033

VLM:
INV-1023
```

Result:

```json
{
  "candidates": [
    {
      "value": "INV-1023",
      "sources": ["pymupdf", "vlm"]
    },
    {
      "value": "INV-1033",
      "sources": ["ocr"]
    }
  ],
  "status": "CONFLICT"
}
```

Never silently discard the rejected candidate.

---



# 20. Step 14 — Validation Engine

Validation can include:

## Evidence agreement

```text
Native = OCR = VLM
```



## OCR confidence

```text
word_confidence
```



## Structural consistency

```text
table rows/columns make sense
```



## Arithmetic consistency

```text
qty × price = total
subtotal + tax = grand total
```



## Cross-reference consistency

```text
"Figure 5" mentioned in text
→ Figure 5 exists
```



## Spatial consistency

```text
caption is near figure
```

---



# 21. Step 15 — Confidence Score

Create a normalized confidence score.

Example conceptual formula:

```text
confidence =
    source_agreement
  + extraction_quality
  + structural_consistency
  + semantic_consistency
  + visual_confidence
```

Do not treat this as a mathematically universal formula.

Start with a rule-based score.

Example:

```text
0.90 - 1.00 → HIGH
0.75 - 0.89 → MEDIUM
0.00 - 0.74 → LOW
```

Make thresholds configurable.

---



# 22. Step 16 — Human Review

Only route exceptions.

Example trigger conditions:

```python
needs_review = (
    confidence < threshold
    or status == "CONFLICT"
    or table_structure_uncertain
    or unreadable_region
)
```

Review UI should display:

```text
Original page
+
highlighted bbox
+
candidate values
+
sources
+
confidence
+
reason for review
```

Human corrections should be stored as feedback data.

---



# 23. Step 17 — Reading Order

After individual regions are extracted, determine document reading order.

Example:

```text
Heading
 ↓
Paragraph 1
 ↓
Paragraph 2
 ↓
Table
 ↓
Table caption
 ↓
Paragraph 3
 ↓
Figure
 ↓
Figure caption
```

For multi-column layouts:

```text
Column 1 → P1 → P2 → P3
Column 2 → P4 → P5 → P6
```

Reading order should be stored separately from spatial position.

---



# 24. Step 18 — Context and Relationships

Build relationships such as:

```text
paragraph → references → figure
paragraph → explains → table
figure → has_caption → caption
table → has_footnote → footnote
section → contains → paragraph
section → contains → table
```

This can be represented as a graph:

```text
Node = extracted element
Edge = relationship
```

Do not discard spatial relationships just because semantic relationships exist.

Keep both.

---



# 25. Step 19 — Canonical Document Model

This is the most important internal data contract.

Example:

```json
{
  "document": {
    "id": "doc_123",
    "filename": "invoice.pdf",
    "page_count": 5
  },

  "pages": [
    {
      "page_number": 1,
      "width": 2480,
      "height": 3508,

      "regions": [
        {
          "id": "r1",
          "type": "heading",
          "bbox": [50, 40, 500, 80],
          "reading_order": 1,
          "content": {
            "text": "Invoice"
          },
          "provenance": {
            "sources": ["pymupdf"]
          },
          "validation": {
            "confidence": 0.99,
            "status": "VERIFIED"
          }
        }
      ]
    }
  ],

  "relationships": [],

  "assets": []
}
```

Every element should aim to preserve:

```text
id
type
content
page
bbox
reading_order
parent_id
children
provenance
confidence
validation_status
relationships
```

---



# 26. Provenance Model

Every important extracted value should have provenance.

Example:

```json
{
  "value": "₹125,430",
  "provenance": {
    "document_id": "doc_123",
    "page": 8,
    "bbox": [120, 420, 280, 450],
    "sources": [
      {
        "engine": "pymupdf",
        "model_version": "..."
      },
      {
        "engine": "ocr",
        "model_version": "..."
      }
    ]
  }
}
```

This lets you answer:

> Where did this data come from?

---



# 27. Output Layer

Generate:

```text
document.json
document.md
```

and retain:

```text
original.pdf
page images
cropped regions
original embedded images
figures
table JSON
OCR artifacts
validation artifacts
```

Example:

```text
artifacts/
├── original.pdf
├── document.json
├── document.md
├── pages/
├── regions/
├── images/
├── figures/
├── tables/
├── ocr/
└── validation/
```

---



# 28. API Design



## Upload

```http
POST /documents
```



## Document status

```http
GET /documents/{document_id}
```



## Pages

```http
GET /documents/{document_id}/pages
```



## Regions

```http
GET /documents/{document_id}/regions
```



## Tables

```http
GET /documents/{document_id}/tables
```



## Figures

```http
GET /documents/{document_id}/figures
```



## Full representation

```http
GET /documents/{document_id}/representation
```



## Review queue

```http
GET /documents/{document_id}/review-items
```



## Submit review decision

```http
POST /review-items/{review_id}
```

---



# 29. Job State Machine

Use explicit statuses.

```text
UPLOADED
   ↓
QUEUED
   ↓
PROFILING
   ↓
REGION_DETECTION
   ↓
EXTRACTING
   ↓
VALIDATING
   ↓
REVIEW_REQUIRED (optional)
   ↓
RECONSTRUCTING
   ↓
COMPLETED
```

Possible failure states:

```text
FAILED
PARTIAL_SUCCESS
CANCELLED
```

---



# 30. Error Handling

Do not hide failures.

Examples:

```text
OCR_FAILED
TABLE_EXTRACTION_FAILED
VLM_TIMEOUT
CORRUPT_PDF
UNSUPPORTED_PDF
LOW_CONFIDENCE
EXTRACTION_CONFLICT
PARTIAL_EXTRACTION
```

A document can still complete with warnings:

```json
{
  "status": "PARTIAL_SUCCESS",
  "warnings": [
    "2 low-confidence regions",
    "1 diagram unresolved"
  ]
}
```

---



# 31. Efficient Routing Strategy

Avoid maximum-compute processing.

Use an escalation strategy.

## Text

```text
PyMuPDF
  ↓ if bad
OCR
  ↓ if ambiguous
VLM
```



## Table

```text
Table extractor
  ↓ if uncertain
OCR + VLM verification
```



## Visual

```text
native image/vector extraction
  ↓ if semantic interpretation needed
VLM
```

This reduces cost and latency.

---



# 32. Important Principle: Preserve Evidence, Not Just Results

For every region, keep:

```text
original page
+
source crop
+
native PDF evidence
+
OCR evidence
+
model result
+
validation result
```

The structured answer is a derived representation.

The original PDF is always the ultimate source of truth.

---



# 33. Example End-to-End Invoice

Input:

```text
invoice.pdf
```

Page contains:

```text
Invoice No: INV-1023
Company logo

Table:
Item | Qty | Price | Total
A    | 2   | 500   | 1000
B    | 3   | 200   | 600

Total: ₹1,600

Signature
```

Pipeline:

```text
PDF
 ↓
Profile
 ↓
Region detection
 ↓
┌─────────────────────────────────┐
│ invoice number → OCR            │
│ logo            → image extract │
│ table           → table engine  │
│ total           → OCR + verify  │
│ signature       → image extract │
└─────────────────────────────────┘
 ↓
Arithmetic validation
2×500 + 3×200 = 1600
 ↓
Context reconstruction
 ↓
Canonical Document Model
 ↓
JSON + Markdown + assets
```

---



# 34. MVP Implementation Order

Do NOT build all capabilities at once.

## Phase 1 — Foundation

Implement:

```text
1. FastAPI upload
2. Local/object storage
3. Job system
4. PyMuPDF profiling
5. Page rendering
6. Native text extraction
7. Basic JSON output
```

Goal:

```text
PDF → basic structured JSON
```

---



## Phase 2 — OCR and scanned PDFs

Add:

```text
8. OCR abstraction
9. PaddleOCR
10. OCR confidence
11. OCR bounding boxes
12. scanned-page handling
13. hybrid-page handling
```

Goal:

```text
digital + scanned + hybrid
```

---



## Phase 3 — Region intelligence

Add:

```text
14. layout detector
15. region classifier
16. region tree
17. region router
```

Goal:

```text
one page → multiple regions → different extractors
```

---



## Phase 4 — Tables and visuals

Add:

```text
18. Docling/table pipeline
19. complex-table handling
20. image extraction
21. chart pipeline
22. diagram pipeline
23. VLM integration
```

Goal:

```text
text + tables + visuals
```

---



## Phase 5 — Validation

Add:

```text
24. evidence reconciliation
25. confidence scoring
26. consistency checks
27. conflict detection
28. human review queue
```

Goal:

```text
reliable extraction
```

---



## Phase 6 — Context

Add:

```text
29. reading order
30. hierarchy
31. relationships
32. captions
33. references
34. context graph
```

Goal:

```text
context-preserving document model
```

---



## Phase 7 — Production

Add:

```text
35. object storage
36. PostgreSQL
37. distributed workers
38. retries
39. observability
40. model versioning
41. audit trail
42. caching
43. metrics
44. evaluation dashboard
```

---



# 35. Initial MVP Scope

The first usable version should support:

```text
✓ Digital PDFs
✓ Scanned PDFs
✓ Hybrid PDFs
✓ Text
✓ Basic tables
✓ Complex tables
✓ Images
✓ Basic figures
✓ OCR
✓ Bounding boxes
✓ Confidence
✓ Provenance
✓ JSON
✓ Markdown
```

Leave advanced features for later:

```text
- handwriting
- advanced chart data reconstruction
- complex engineering drawings
- equations
- multilingual edge cases
- agentic optimization
```

---



# 36. Testing Strategy

Create a benchmark set containing:

```text
1. Simple digital PDF
2. Scanned document
3. Hybrid PDF
4. Multi-column paper
5. Invoice
6. Financial statement
7. Complex table
8. Table with merged cells
9. Chart
10. Diagram
11. Image-heavy report
12. Form
13. Poor scan
14. Rotated scan
15. Long document
```

Measure separately:

```text
Text accuracy
OCR accuracy
Layout accuracy
Table structure accuracy
Reading-order accuracy
Figure detection
Diagram extraction
Relationship accuracy
Confidence calibration
Human-review rate
```

Do not evaluate the entire system only with one score.

---



# 37. Practical Development Rules



## Rule 1

Never make the VLM the entire extraction pipeline.

## Rule 2

Never make OCR the single source of truth.

## Rule 3

Never classify only at page level.

## Rule 4

Never throw away conflicting extraction candidates.

## Rule 5

Never throw away original page/image evidence.

## Rule 6

Every extracted item should have coordinates.

## Rule 7

Every important extracted value should have provenance.

## Rule 8

Confidence should be generated by validation, not blindly copied from a model.

## Rule 9

Context reconstruction happens after extraction.

## Rule 10

Canonical Document Model is the central internal contract.

---



# 38. Recommended First Technical Milestone

Build this small pipeline first:

```text
PDF upload
   ↓
PyMuPDF
   ↓
page profiling
   ↓
page rendering
   ↓
native text extraction
   ↓
basic region detection
   ↓
JSON
```

Then add:

```text
OCR
   ↓
tables
   ↓
VLM
   ↓
validation
   ↓
human review
   ↓
context graph
```

Do not start with the complete agentic architecture.

Get the deterministic evidence pipeline correct first.

---



# 39. Final Implementation Mental Model

When coding, repeatedly ask these questions:

### 1. What exists in the source?

```text
PDF-native objects + rendered pixels
```



### 2. Where is it?

```text
page + bbox
```



### 3. What is it?

```text
text / table / image / chart / diagram / ...
```



### 4. Which extractor is best?

```text
PyMuPDF / OCR / table engine / VLM / combination
```



### 5. Do multiple sources agree?

```text
yes → stronger confidence
no  → conflict
```



### 6. Is the result structurally/semantically consistent?

```text
yes → pass
no  → review
```



### 7. How does it relate to the rest of the document?

```text
reading order + hierarchy + relationships
```



### 8. Can I trace it back to the original PDF?

```text
document → page → bbox → source evidence
```

If the answer to all eight is yes, the system is moving toward a reliable document-understanding platform.

---



# 40. One-Line Architecture

```text
PDF
→ Profile with PyMuPDF
→ Render + inspect native objects
→ Detect regions
→ Route each region to the right specialist
→ Reconcile evidence
→ Validate
→ Human-review exceptions
→ Reconstruct reading order/context
→ Store Canonical Document Model
→ Generate JSON/Markdown/assets
```

This is the implementation blueprint to follow.