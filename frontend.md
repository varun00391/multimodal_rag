# Extraction Studio — Frontend Specification

This document is the implementation contract for the user interface of
`multimodal_rag_app`. It covers product intent, visual system, layout, screens,
components, interaction, data mapping, API gaps, and build order.

The backend is a standalone hybrid PDF extraction API. The UI is **not** a RAG
chat, search product, or knowledge base. It is an extraction review studio:
upload a PDF, watch the pipeline, and judge canonical output against the
original page.

**Product name:** Extract
**Window title:** Extract — Hybrid PDF Studio
**Default theme:** dark studio (light theme is specified and must ship)

---

## 1. Purpose

The UI exists so a person can answer four questions without reading JSON:

1. Did we extract this page correctly?
2. Did we hit the right regions (bounding boxes)?
3. Is the reconstructed structure usable (headings, tables, charts)?
4. If not, which extractor, fallback, and validation code failed?

Phase 10 calibration and day-to-day extraction review share this UI.

### 1.1 In scope (v1)

- Upload a PDF and set extraction policy
- Job list with live status
- Page-by-page review: original PDF + bbox overlays + reconstructed reading order
- Element inspector (type, text, extractor, confidence, validation)
- Extraction report (routing, fallbacks, validation, timing, cost)
- Raw JSON view and download of `document.json` and `extraction-report.json`
- Asset preview (pictures, charts, retained page images)

### 1.2 Out of scope (v1)

- Chat, Q&A, RAG, embeddings, search
- Multi-user auth, sharing, comments
- Ground-truth labeling workflow
- Side-by-side extractor compare layout
- Ops metrics dashboard (`GET /api/v1/metrics` stays an API endpoint)
- Mobile-first layout (desktop is the target; tablet is usable, phone is not)
- Editing or correcting extraction output

---

## 2. Audience and principles

**Primary user:** the person running and judging this extractor (developer,
calibrator, document engineer).

**Secondary user:** anyone who wants structured output from a PDF and needs to
see whether it is trustworthy.

Principles:

1. **The page is the hero.** Chrome is dense and quiet. The PDF and the
   reconstruction get the pixels.
2. **Partial success is normal.** `completed_with_warnings` is a first-class
   result, not a soft error. Failed pages stay visible and red; successful
   pages stay usable.
3. **Privacy is visible.** Managed-API permission is a first-class control with
   explicit copy, not a buried checkbox.
4. **Provenance is one click away.** Every element shows which extractor
   produced it. The default view does not dump diagnostics.
5. **Studio, not marketing.** No hero illustrations, no gradient splash, no
   onboarding carousel.

---

## 3. Technology choices

| Layer | Choice | Why |
| --- | --- | --- |
| App | React 18 + TypeScript | Overlay state, page canvas, report trees |
| Bundler | Vite | Fast SPA, proxy to FastAPI |
| Styling | CSS modules + CSS variables from this spec | No component library required |
| PDF render | PDF.js | Render `source.pdf` to canvas; overlay HTML bboxes |
| Routing | React Router | `/`, `/jobs/:jobId` |
| Data | TanStack Query | Polling job status; cache document/report |
| Icons | Lucide (1.5px stroke, 16px default) | Consistent, small, quiet |
| Markdown | `react-markdown` + `remark-gfm` | Tables and lists in reconstruction |
| Formula | KaTeX, only when text looks like TeX | Optional; fall back to monospace |
| Syntax | No extra highlighter in v1 | `IBM Plex Mono` is enough for code/JSON |

Do not use a heavy admin kit (Ant Design, MUI). Build a small set of primitives
from the tokens below.

Suggested package layout:

```text
frontend/
  index.html
  package.json
  vite.config.ts
  src/
    main.tsx
    App.tsx
    styles/
      tokens.css
      reset.css
      global.css
    api/
      client.ts
      types.ts
    routes/
      JobsHome.tsx
      JobReview.tsx
    components/
      AppShell.tsx
      StatusBadge.tsx
      UploadDropzone.tsx
      PolicyPanel.tsx
      JobList.tsx
      JobHeader.tsx
      PageStrip.tsx
      PdfStage.tsx
      BboxOverlay.tsx
      Reconstruction.tsx
      ElementInspector.tsx
      ReportView.tsx
      JsonView.tsx
      AssetFigure.tsx
      Legend.tsx
    lib/
      status.ts
      colors.ts
      bbox.ts
      poll.ts
```

Dev proxy: Vite `server.proxy["/api"]` → `http://127.0.0.1:8010`.
Production: serve the built SPA from FastAPI (`/`) or a static host with the
same origin / CORS as the API.

API origin in development: `http://127.0.0.1:8010`
UI origin in development: `http://127.0.0.1:5173`

---

## 4. Design tokens

All values live as CSS custom properties on `:root` (dark) and
`[data-theme="light"]`. Components must not hard-code hex values.

### 4.1 Color — dark (default)

The chrome is a warm charcoal so a white PDF page reads as a sheet of paper.
The accent is amber (inspection / highlighter). Structure and success use teal.

```css
:root {
  /* Surfaces */
  --bg-app: #161412;
  --bg-raised: #1e1b18;
  --bg-overlay: #26221e;
  --bg-input: #1a1815;
  --bg-page: #0f0e0c;
  --bg-paper: #f6f1e8;          /* reconstructed page surface */
  --bg-dropzone: #1a1815;

  /* Hairlines */
  --border: #3a342e;
  --border-strong: #534a41;
  --border-focus: #e8a838;

  /* Text */
  --text: #f3ece3;
  --text-muted: #b5a99a;
  --text-faint: #7d7367;
  --text-invert: #161412;

  /* Accent */
  --accent: #e8a838;
  --accent-hover: #f0bc5c;
  --accent-muted: rgba(232, 168, 56, 0.16);
  --accent-text: #161412;

  /* Semantic */
  --ok: #3db88a;
  --ok-muted: rgba(61, 184, 138, 0.16);
  --warn: #e8a838;
  --warn-muted: rgba(232, 168, 56, 0.16);
  --danger: #e05c4a;
  --danger-muted: rgba(224, 92, 74, 0.16);
  --info: #6aa6d8;
  --info-muted: rgba(106, 166, 216, 0.16);
  --privacy: #c47cff;
  --privacy-muted: rgba(196, 124, 255, 0.14);
}
```

### 4.2 Color — light

```css
[data-theme="light"] {
  --bg-app: #f4efe8;
  --bg-raised: #fffdf9;
  --bg-overlay: #ffffff;
  --bg-input: #ffffff;
  --bg-page: #e7e0d6;
  --bg-paper: #fffdf9;
  --bg-dropzone: #fffdf9;

  --border: #d9d0c4;
  --border-strong: #b9ae9f;
  --border-focus: #c48914;

  --text: #1c1814;
  --text-muted: #5c5349;
  --text-faint: #8a7f72;
  --text-invert: #fffdf9;

  --accent: #c48914;
  --accent-hover: #a87410;
  --accent-muted: rgba(196, 137, 20, 0.12);
  --accent-text: #fffdf9;

  --ok: #1f8a62;
  --ok-muted: rgba(31, 138, 98, 0.12);
  --warn: #c48914;
  --warn-muted: rgba(196, 137, 20, 0.12);
  --danger: #c44738;
  --danger-muted: rgba(196, 71, 56, 0.12);
  --info: #3d7eb0;
  --info-muted: rgba(61, 126, 176, 0.12);
  --privacy: #8b4fd1;
  --privacy-muted: rgba(139, 79, 209, 0.12);
}
```

Theme toggle lives in the app shell (sun/moon). Persist `extract-theme` in
`localStorage`. Default is `dark`.

### 4.3 Element-type overlay colors

These draw on the **white PDF page**, so they must stay saturated and distinct.
Use the same hue in the reconstruction gutter and the legend.

Fill is the color at 14% opacity. Stroke is 1.5px solid. Selected stroke is
2.5px with fill at 28%.

| Element type | Token | Hex | Use |
| --- | --- | --- | --- |
| `heading` | `--el-heading` | `#4C6EF5` | indigo |
| `paragraph` | `--el-paragraph` | `#748198` | slate (quiet) |
| `list` | `--el-list` | `#22B8CF` | cyan |
| `table` | `--el-table` | `#2F9E44` | green |
| `picture` | `--el-picture` | `#F76707` | orange |
| `chart` | `--el-chart` | `#D6336C` | magenta |
| `diagram` | `--el-diagram` | `#7950F2` | violet |
| `formula` | `--el-formula` | `#E64980` | pink |
| `code` | `--el-code` | `#5C7C2A` | olive |
| `key_value` | `--el-key-value` | `#0CA678` | teal |
| `form_field` | `--el-form-field` | `#E8590C` | amber-orange |
| `header` | `--el-header` | `#868E96` | gray |
| `footer` | `--el-footer` | `#868E96` | gray |
| `footnote` | `--el-footnote` | `#A0794A` | brown |
| `page_number` | `--el-page-number` | `#ADB5BD` | light gray |
| `unknown` | `--el-unknown` | `#FA5252` | red |

Problem regions (validation failure or fallback) add a 1px dashed `--danger`
outline **outside** the type stroke. Do not replace the type color.

### 4.4 Extractor colors

Used in badges, the page-strip route chip, and inspector provenance.

| Extractor | Token | Hex |
| --- | --- | --- |
| `pymupdf` | `--ex-pymupdf` | `#4C8DDE` |
| `docling` | `--ex-docling` | `#2F9E44` |
| `gemini` | `--ex-gemini` | `#9B6DFF` |
| `groq-vision` | `--ex-groq` | `#F76707` |
| unknown / mixed | `--ex-mixed` | `--text-muted` |

Docling profiles do not get their own hue. Show the profile as muted text next
to the Docling badge: `docling · formula-code`.

### 4.5 Status colors

| Job / page status | Background | Foreground | Dot |
| --- | --- | --- | --- |
| `queued` | `--bg-overlay` | `--text-muted` | `--text-faint` |
| in progress (`validating_input` … `merging`) | `--accent-muted` | `--accent` | `--accent` (pulse) |
| `completed` | `--ok-muted` | `--ok` | `--ok` |
| `completed_with_warnings` | `--warn-muted` | `--warn` | `--warn` |
| `failed` | `--danger-muted` | `--danger` | `--danger` |

In-progress statuses share one visual treatment. Differentiate them with the
label, not a rainbow of colors.

### 4.6 Typography

Load from Google Fonts or self-host:

```text
IBM Plex Sans: 400, 500, 600
IBM Plex Mono: 400, 500
```

```css
:root {
  --font-sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;

  --fs-2xs: 10px;
  --fs-xs: 11px;
  --fs-sm: 12px;
  --fs-md: 13px;
  --fs-base: 14px;
  --fs-lg: 16px;
  --fs-xl: 20px;
  --fs-2xl: 24px;

  --lh-tight: 1.25;
  --lh-body: 1.45;
  --lh-doc: 1.55;

  --tracking-ui: 0;
  --tracking-caps: 0.06em;
}
```

Usage:

| Surface | Font | Size | Weight |
| --- | --- | --- | --- |
| App chrome, buttons, tabs | sans | 13px | 500 |
| Body copy, reconstruction paragraphs | sans | 14px | 400 |
| Section labels (uppercase) | sans | 11px | 600, `letter-spacing: 0.06em` |
| Job filename | sans | 14px | 600 |
| Job id, sha256, element id | mono | 11px | 400 |
| JSON / code / formulas | mono | 12px | 400 |
| Reconstruction `heading` | sans | 20px / 16px | 600 |
| Reconstruction `table` | sans | 12px | 400 |
| Overlay legend | sans | 11px | 500 |
| Status badge | sans | 11px | 600 |

Do not use italic in chrome. Reconstruction footnotes may be 12px muted.

### 4.7 Spacing, radius, elevation, motion

4px base grid.

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;

  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 10px;
  --radius-pill: 999px;

  --shadow-1: 0 1px 0 rgba(0, 0, 0, 0.35);
  --shadow-2: 0 8px 24px rgba(0, 0, 0, 0.35);

  --z-base: 0;
  --z-overlay: 10;     /* bbox layer */
  --z-strip: 20;
  --z-header: 30;
  --z-inspector: 40;
  --z-popover: 50;
  --z-modal: 60;
  --z-toast: 70;

  --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  --dur-fast: 120ms;
  --dur: 180ms;
}
```

Motion: only opacity and transform. The status dot on in-progress jobs pulses
(`opacity 0.4 ↔ 1`, 1.2s). Do not animate layout width during extraction.

Density is **compact**. Default control height is 32px. Icon buttons are 28×28.

### 4.8 Focus and interaction

- Focus ring: `0 0 0 2px var(--bg-app), 0 0 0 4px var(--border-focus)`
- Hover on raised rows: background `--bg-overlay`
- Disabled: opacity 0.45, `cursor: not-allowed`
- Pointer on all clickable chrome: `cursor: pointer`
- Overlay hover on the PDF: `cursor: crosshair` when no element, `pointer` on a box

---

## 5. App shell

Fixed 48px top bar. No left nav in v1. Two routes only.

```text
┌─────────────────────────────────────────────────────────────┐
│ Extract    Jobs                            ☀/☾   theme      │  48px
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                         route outlet                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Left:** wordmark `Extract` in IBM Plex Sans 16px/600, color `--text`. A 6px
amber square sits to the left of the word. Clicking it goes to `/`.

**Center-left:** text link `Jobs` (active state: amber underline 2px). On the
review route, also show a breadcrumb:

```text
Jobs  /  2309.06180v1-2.pdf
```

Filename is truncated with ellipsis at 40ch. Hover shows the full name.

**Right:** theme toggle. No user menu. No settings page in v1.

Shell background `--bg-app`. Bottom border `--border`. Do not use a drop
shadow on the shell.

---

## 6. Routes

| Path | Screen |
| --- | --- |
| `/` | Jobs home (upload + list) |
| `/jobs/:jobId` | Document review |
| `/jobs/:jobId?tab=report` | Same screen, Report tab |
| `/jobs/:jobId?tab=json` | Same screen, JSON tab |
| `/jobs/:jobId?page=3` | Review, selected page |

Unknown `jobId` → full-page error with code `JOB_NOT_FOUND` and a link home.

---

## 7. Screen: Jobs home (`/`)

Two columns on viewports ≥ 1100px. Single column below that (upload first).

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Upload                       │ Recent jobs                  │
│ dropzone + policy            │ filter + list                │
└──────────────────────────────┴──────────────────────────────┘
```

Left column max-width 520px. Right column fills remaining space. Page padding
`--space-6`. Gap `--space-6`.

### 7.1 Upload dropzone

Height 180px. Dashed border `--border-strong`, radius `--radius-lg`,
background `--bg-dropzone`.

Idle copy:

```text
Drop a PDF here
or click to choose · PDF only · max 100 MB · up to 500 pages
```

The max size and page cap must be read from config when the config endpoint
exists; until then hard-code `100 MB` and `500 pages` to match
`EXTRACTION_MAX_FILE_BYTES` and `EXTRACTION_MAX_PAGES`.

States:

| State | Visual |
| --- | --- |
| Idle | dashed border, muted icon (file), copy above |
| Drag over | solid `--accent` border, background `--accent-muted` |
| File selected | replace copy with filename, page count if known, size, and a clear (×) |
| Invalid type | `--danger` border, “Only PDF files are accepted.” |
| Too large | `--danger` border, “File exceeds the 100 MB limit.” |
| Uploading | progress bar (indeterminate) + “Uploading…” |
| Queued | “Job queued” + link to the new job |

Accept: `application/pdf` and `.pdf`. Reject folders. One file at a time.

After a successful `202`, navigate to `/jobs/:jobId` immediately. The job also
appears at the top of the list.

### 7.2 Policy panel

Directly under the dropzone. Section label `EXTRACTION OPTIONS` (caps token).

**Always visible**

| Control | Type | Default | API field | Copy |
| --- | --- | --- | --- | --- |
| Allow managed APIs | switch | on | `allow_managed_apis` | “Send pages to Gemini / Groq when needed.” |
| Visual understanding | switch | off | `visual_understanding` | “Interpret charts, graphs, and diagrams. Increases cost.” |
| Page range | two number inputs | empty = all | `page_start`, `page_end` | placeholders `From`, `To` |

When **Allow managed APIs** is on, show a quiet privacy note under the switch:

```text
Selected pages may leave this machine.
```

Use `--privacy` for the info icon, not danger. When the switch is off:

```text
Local extractors only. Scans use Docling OCR. Gemini and Groq will not run.
```

Visual understanding is disabled (and shown off) when managed APIs are off.
Tooltip: “Requires managed APIs (Groq).”

Page inputs are integers ≥ 1. Validate `from ≤ to` on the client before
submit. Empty means the full document.

Primary button under the panel:

```text
Extract
```

32px height, full width of the left column, background `--accent`, text
`--accent-text`, radius `--radius-md`. Disabled until a valid PDF is selected.
Shortcut: `⌘ Enter` / `Ctrl Enter`.

**Advanced (collapsed by default)**

Disclosure `Advanced · benchmark`. Visible only if
`EXTRACTION_BENCHMARK_ENABLED` is true (config endpoint or
`VITE_BENCHMARK_ENABLED=true` for local). Otherwise omit the disclosure
entirely — do not show a disabled tease.

| Control | Type | API field |
| --- | --- | --- |
| Force extractor | select | `force_extractor` |
| Compare extractors | switch | `compare_extractors` |

Force extractor options:

```text
(auto hybrid)          → omit field
pymupdf
docling
docling:digital-layout
docling:digital-table
docling:formula-code
docling:private-ocr
gemini
groq-vision
```

Compare mode in v1 still submits the flag but the review screen does **not**
change layout. Show a toast: “Compare flag submitted. Side-by-side view is not
in v1; use the report.”

### 7.3 Recent jobs

Header row: `RECENT JOBS` + a segmented filter:

```text
All | Running | Done | Failed
```

Search input, 32px, placeholder `Filter by filename or job id`.

Each row is 56px, clickable, navigates to `/jobs/:jobId`.

```text
┌─────────────────────────────────────────────────────────────┐
│ 2309.06180v1-2.pdf                         6m 12s   cache   │
│ 16 pages · hybrid                          completed ⚠      │
│ job-6a01305a… · 2 min ago                                   │
└─────────────────────────────────────────────────────────────┘
```

- Line 1: filename (600) · duration · `cache` chip if `cache_hit`
- Line 2: `N pages` · route summary (`hybrid` or forced extractor name) ·
  `StatusBadge`
- Line 3: truncated `job_id` in mono 11px · relative `created_at`

Running rows show a thin amber progress bar at the bottom of the row
(indeterminate). Failed rows show `error_code` instead of duration.

Empty filter: “No jobs match.”
Empty list: “No extractions yet. Drop a PDF to start.”

Sort: newest `created_at` first.

There is no job-list API today. See §16. Until it exists, persist jobs created
in this browser in `localStorage` key `extract-jobs` (array of job ids) and
hydrate each with `GET /api/v1/extractions/{job_id}`. Filename is stored
locally at upload time because the status payload currently omits it.

---

## 8. Screen: Job review (`/jobs/:jobId`)

This is 80% of the product. Three horizontal bands.

```text
┌─────────────────────────────────────────────────────────────┐
│ Job header (filename, status, stats, tabs)           56px   │
├─────┬─────────────────────────────┬─────────────────────────┤
│Strip│ Original page + overlays    │ Reconstructed document  │
│ 96px│                             │                         │
│     │                             │                         │
├─────┴─────────────────────────────┴─────────────────────────┤
│ Inspector (collapsed 40px / expanded 220px)                 │
└─────────────────────────────────────────────────────────────┘
```

On the Report and JSON tabs, the strip + split + inspector are replaced by the
tab body. The header stays.

### 8.1 Job header

Left cluster:

- Filename, 16px/600
- `StatusBadge`
- If running: stage label from §10 (`Inspecting pages…`)
- If `cache_hit`: chip `cache`

Right cluster of stat chips (hide a chip if the value is unknown):

| Chip | Source |
| --- | --- |
| `16 pp` | `page_count` |
| `6m 12s` | `duration_ms` (omit while running, or show elapsed from `created_at`) |
| `$0.023` | `document.summary.estimated_cost_usd` or `report.usage.estimated_cost_usd` |
| `528¶ 5 tbl 2 cht` | `document.summary.element_counts` for paragraph / table / chart |
| `3 failed` | `document.summary.failed_pages.length` — `--danger` if > 0 |

Tabs, 13px/500, sit under the filename on the left of the header or as a
second 36px row if the first row is full. Prefer a second row rather than
wrapping stats.

**Primary tabs** (query `?tab=`):

| Id | Label | When enabled |
| --- | --- | --- |
| `review` | Review | always (default) |
| `report` | Report | after terminal status; while running show disabled with tooltip “Available when extraction finishes” |
| `json` | JSON | same as Report |

Active tab: 2px amber underline, text `--text`. Inactive: `--text-muted`.

Header actions (icon buttons, right of stats):

| Action | Icon | Behavior |
| --- | --- | --- |
| Download document | download | `document.json` |
| Download report | file-bar-chart | `extraction-report.json` |
| Copy job id | copy | clipboard, toast “Job id copied” |

### 8.2 Page strip (Review tab)

Vertical list, 96px wide, scrollable, background `--bg-page`. Each item:

- Thumbnail 72×96 of the PDF page (PDF.js render, scale 0.2, cached)
- Page number centered under the thumb, mono 11px
- Status dot, 8px, top-right of the thumb (ok / warn / fail / running)
- Optional 3px left bar in the **primary_route** extractor color

Badges (max two, 10px caps, overlay bottom of thumb):

| Badge | When |
| --- | --- |
| `SCAN` | page in `summary.scanned_pages` or report inspection |
| `TBL` | page has `table` elements or task kind `table_structure` |
| `CHART` | page has `chart` / `diagram` elements |
| `OCR` | route includes `gemini` or Docling `private-ocr` |
| `FB` | a fallback record exists for this page |

Selected page: `--border-focus` ring on the thumb. Click selects and sets
`?page=`. Arrow `Up` / `Down` move pages. `Home` / `End` jump.

While the job is running and document.json is not ready, show page count from
the status payload as numbered placeholders (no thumbs). Pulse the current
implied stage; do not fake per-page progress the API does not provide.

### 8.3 Original page (center)

Background `--bg-page`. Center the PDF.js canvas. Fit-width by default.

Toolbar, 32px, overlay top of the stage (not a second header):

| Control | Default |
| --- | --- |
| Zoom `−` / `%` / `+` | fit width |
| Fit width / Fit page | fit width |
| Overlay | on |
| Overlay filter | All types |
| Problems only | off |

Overlay filter is a popover of checkboxes, one per element type present on
**this page**, plus `Select all` / `None`. “Problems only” shows elements that
appear in `validation.pages[].failures` for this page, or pages with fallbacks.

PDF.js renders the page to canvas. An absolutely positioned SVG/HTML layer
sits on top with the same CSS size. See §11 for bbox math.

Empty page (no elements): muted “No elements on this page.”
Failed page with retained image: if a page asset exists
(`assets/pages/page_{n}.png`), show it under the PDF (or instead, if PDF
render fails) and a danger banner “Extraction failed for this page. Source
image retained.”

### 8.4 Reconstructed document (right)

Background `--bg-paper`, text `--text-invert` in dark theme (the paper is
light in both themes). Padding 24px. Max width 640px, centered in the pane.

This pane answers “what would a downstream system see?” Render the selected
page’s elements sorted by `reading_order`.

| Type | Render |
| --- | --- |
| `heading` | `<h2>` 20px/600 if markdown starts with `# ` or `## `; else `<h3>` 16px/600 |
| `paragraph` | `<p>` 14px/400, `--lh-doc` |
| `list` | markdown → `<ul>`/`<ol>`; fallback split lines into `<ul>` |
| `table` | prefer `html` inside a scroll wrapper; else GFM markdown; else `<pre>` of `text` |
| `picture` | `<figure>` + `img` from asset URL + caption `text` |
| `chart` / `diagram` | `<figure>` + crop `img` if `asset` else type-colored placeholder + body `text`/`markdown` as caption |
| `formula` | KaTeX if `$…$` or `\(…\)`; else mono 13px |
| `code` | `<pre><code>` mono 12px, `--bg-raised` on paper via a light gray `#eee8df` |
| `key_value` | `<dl>` from markdown or `key: value` lines |
| `form_field` | label + boxed value |
| `header` / `footer` | 12px muted, separated by a hairline |
| `footnote` | 12px muted |
| `page_number` | omit from reconstruction (still in overlay) |
| `unknown` | dashed red box, 12px, show `text` |

Clicking a reconstructed block selects the same element as the overlay
(bidirectional highlight). Selected block: 2px left bar in the type color and
`--accent-muted` background.

A pane header (12px) shows `Page {n} · {count} elements` and a switch
`Reading order` (always on in v1; do not offer spatial reconstruction).

If the selected element has `metadata.duplicate_sources`, show a small chip
`merged` on that block. Inspector lists the duplicate extractors.

### 8.5 Split behavior

Default: 50 / 50 after the strip. A 6px drag handle (`col-resize`) between
center and right. Double-click the handle to reset 50/50.

View-mode segmented control in the job header, Review tab only:

```text
Split | Original | Extracted
```

- `Split` — both panes
- `Original` — hide reconstruction
- `Extracted` — hide PDF stage

Keyboard: `1` original, `2` split, `3` extracted.

### 8.6 Inspector

Bottom drawer. Collapsed: 40px bar `Select an element on the page`. Expanded:
220px (drag to 160–360). Collapse chevron on the right.

When an element is selected, three columns:

**Column A — Identity**

- Type badge (type color)
- `element_id` mono 11px, copy button
- `page` · `reading_order`
- Confidence meter: 60px bar, `--ok` if ≥ 0.85, `--warn` if 0.6–0.85,
  `--danger` if < 0.6. Threshold 0.85 matches
  `EXTRACTION_MIN_VALIDATION_CONFIDENCE`.

**Column B — Content**

- Tabs inside inspector: `Text` | `Markdown` | `HTML`
- Show whichever fields are non-null; hide empty tabs
- Asset: thumbnail 72px + open-in-new (asset URL)

**Column C — Provenance**

- Extractor badge + version + adapter version
- Profile, model, prompt version (omit nulls)
- Attempt number
- Routing reasons for the **page** (from `page.routing_reasons`), not the
  element, as a bulleted muted list
- Validation failures for this `element_id` if present

If nothing is selected, show page-level diagnostics instead:

- `primary_route`, `extraction_routes`
- `overall_confidence`
- `routing_reasons`
- page `warnings` and `errors`
- attempts table: extractor, status, duration, element_count

---

## 9. Screen: Report tab

Readable diagnostics. Not a raw dump. Max width 960px, padding `--space-6`,
scroll in the main band.

Sections, each a raised card (`--bg-raised`, radius `--radius-lg`, padding
`--space-4`), in this order:

### 9.1 Summary

Four stat tiles:

| Tile | Field |
| --- | --- |
| Status | `report.status` |
| Duration | `report.duration_ms` plus stacked bar of `report.durations` |
| Cost | `report.usage.estimated_cost_usd` · `total_tokens` |
| Cache | hit/miss · group hits/misses |

Chips for extractors used and `allow_managed_apis`. If false, privacy chip
`local only`.

### 9.2 Pipeline timing

Horizontal stacked bar from `durations`:

| Key | Label | Color |
| --- | --- | --- |
| `inspect_ms` | Inspect | `--info` |
| `plan_ms` | Plan | `--text-faint` |
| `extract_ms` | Extract | `--accent` |
| `validate_ms` | Validate | `--ok` |
| `fallback_ms` | Fallback | `--warn` |
| `merge_ms` | Merge | `--ex-docling` |

Omit missing keys. Tooltip on each segment: label + ms.

### 9.3 Inspection

From `inspection_summary`:

- Page count
- Scanned pages as page-number chips (click jumps to Review `?page=` + `tab=review`)
- PyMuPDF fast-path page chips

### 9.4 Routes

`route_counts` as a small bar chart (CSS flex bars). Below, a table of
`report.pages`:

| Column | Field |
| --- | --- |
| Page | `page` |
| Primary | `primary_route` badge |
| Routes | `extraction_routes` |
| Elements | `element_count` |
| Attempts | `attempt_count` |
| Validation | passed/fail |
| Confidence | `overall_confidence` as bar |
| Status | `status` |

Row click → Review on that page.

### 9.5 Groups

From `routing.groups`: extractor, profile, kind, pages. Compact chips.

### 9.6 Fallbacks

Table from `fallbacks`:

| Page | Reason | From | To | Status | Message |
| --- | --- | --- | --- | --- | --- |

Empty: “No fallbacks.” (positive, muted)

### 9.7 Validation

From `validation`:

- `min_confidence`
- failed page chips
- Expandable per-page failure list: `code`, `message`, `element_id` (click
  selects that element on Review)

Color hard vs soft codes:

**Hard (danger):**
`NATIVE_TEXT_CORRUPT`, `NATIVE_TEXT_MISSING`, `READING_ORDER_INVALID`,
`BBOX_OUT_OF_BOUNDS`, `BBOX_NON_POSITIVE_AREA`, `TABLE_STRUCTURE_INVALID`,
`TABLE_EMPTY`, `VISUAL_CROP_MISSING`

**Soft (warn):**
`PRINTABLE_RATIO_LOW`, `REPLACEMENT_RATIO_HIGH`, `DUPLICATE_LINES`,
`REPEATED_SYMBOLS`, `OCR_TOO_SHORT`, `EXCESSIVE_OVERLAP`,
`DUPLICATE_PARAGRAPHS`, `TABLE_MARKDOWN_INVALID`, `TABLE_HTML_INVALID`,
`TABLE_MISSING`, `FORMULA_MISSING`, `EXPECTED_FIGURE_MISSING`,
`VISUAL_BBOX_INVALID`, `VISUAL_MEANING_MISSING`

Unknown codes render as warn.

### 9.8 Usage and versions

Two-column: token/cost block; `versions` as a definition list in mono 11px.
Circuit breaker state only if not `closed` (show warn/danger). Hide the
process-wide `metrics` snapshot — that is ops, not this job.

---

## 10. Screen: JSON tab

Two sub-tabs: `document.json` | `extraction-report.json`.

- Read-only `<pre>` mono 12px, `--bg-page`, wrap off, horizontal scroll
- Search (`⌘ F` browser native is enough in v1)
- Buttons: Copy, Download
- While running: empty state “JSON is written when the job finishes.”

Pretty-print with `JSON.stringify(data, null, 2)`. Do not fetch these
endpoints until the job is in a terminal status (they 404 with
`RESULT_NOT_READY`).

---

## 11. Overlay and coordinates

Canonical bboxes are **PDF points, top-left origin**, matching PDF.js default
viewport when `rotation` is applied via the page viewport.

```text
scaleX = canvasCssWidth  / page.width
scaleY = canvasCssHeight / page.height

cssLeft   = bbox.left   * scaleX
cssTop    = bbox.top    * scaleY
cssWidth  = (bbox.right  - bbox.left)   * scaleX
cssHeight = (bbox.bottom - bbox.top)    * scaleY
```

Use `page.width` / `page.height` from `CanonicalPage`, not the PDF.js unscaled
page, if they disagree after rotation. If `page.rotation` is 90/270, prefer
PDF.js viewport transform and convert through `viewport.convertToViewportPoint`.

Hit testing: top-most element in reverse `reading_order` (later = typically
tighter). Clicking empty canvas clears selection.

Hover tooltip (12px, `--bg-overlay`, delay 80ms): `{type} · {extractor}`.

Do not draw overlays for elements with a missing bbox.

---

## 12. Status machine

Poll `GET /api/v1/extractions/{job_id}`:

| Job status | Interval |
| --- | --- |
| `queued` | 1000 ms |
| `validating_input`, `inspecting`, `planning`, `extracting`, `validating_output`, `retrying`, `merging` | 1000 ms |
| `completed`, `completed_with_warnings`, `failed` | stop |

On terminal status, fetch document and report in parallel. If document returns
`RESULT_NOT_READY`, retry twice at 500 ms then show error.

### 12.1 Stage copy (header)

| Status | Label |
| --- | --- |
| `queued` | Queued |
| `validating_input` | Validating PDF |
| `inspecting` | Inspecting pages |
| `planning` | Planning routes |
| `extracting` | Extracting |
| `validating_output` | Validating output |
| `retrying` | Retrying failed work |
| `merging` | Merging results |
| `completed` | Completed |
| `completed_with_warnings` | Completed with warnings |
| `failed` | Failed |

Badge label uses the same strings, shorter on the job list:

| Status | List badge |
| --- | --- |
| in progress | the stage label |
| `completed` | Done |
| `completed_with_warnings` | Done · warnings |
| `failed` | Failed |

### 12.2 Running Review tab

Show the PDF from the local `File` (IndexedDB) or from the source endpoint
(§16). Header stats that need the document are omitted. Inspector shows only
job status. Overlay off until `document.json` exists.

Do not invent per-page checkmarks. A single stage label is honest.

---

## 13. Empty, error, and edge states

| Situation | UI |
| --- | --- |
| Home, no jobs | Dropzone + “No extractions yet.” |
| Upload 400 | Toast + inline dropzone error using `error.message` |
| `FILE_TOO_LARGE` | “File exceeds the maximum size.” |
| `INVALID_PDF_SIGNATURE` | “This file is not a valid PDF.” |
| `QUEUE_BACKPRESSURE` 429 | “The queue is full. Retry in a moment.” |
| `BENCHMARK_NOT_ENABLED` 403 | Hide advanced controls; if somehow sent, toast the server message |
| Job not found | Centered card, link to Jobs |
| `failed` job | Review still opens the PDF; banner with `error_code` and `error_message`; Report/JSON if files exist |
| Missing asset | Broken-image placeholder, type color, “Asset not stored” |
| Huge page (500 pages) | Virtualize the page strip (react-virtuoso or equivalent). Reconstruct and overlay only the selected page |
| Cache hit | Chip in header; no special layout |

Toasts: 12px, `--bg-overlay`, 3.5s, bottom-right, `--z-toast`. One at a time.

---

## 14. Components

Build these primitives. No others are required for v1.

| Component | Notes |
| --- | --- |
| `Button` | `primary` (accent fill), `ghost` (transparent), `danger`. Height 32 / icon 28 |
| `IconButton` | 28×28, tooltip |
| `Switch` | 28×16 track, accent when on |
| `Input` / `NumberInput` | 32px, `--bg-input`, border `--border` |
| `Select` | native is acceptable in v1 |
| `Tabs` | underline style |
| `Segmented` | raised `--bg-overlay` container, active `--bg-raised` |
| `StatusBadge` | pill, 18px height |
| `Chip` | 18px height, optional color |
| `Tooltip` | 200ms delay |
| `Disclosure` | advanced policy |
| `Dropzone` | §7.1 |
| `JobList` | §7.3 |
| `JobHeader` | §8.1 |
| `PageStrip` | §8.2 |
| `PdfStage` | canvas + overlay |
| `BboxOverlay` | SVG rects |
| `Reconstruction` | element switch |
| `ElementInspector` | §8.6 |
| `Legend` | type colors, toggle visibility |
| `ReportView` | §9 |
| `JsonView` | §10 |
| `AssetFigure` | authenticated-ish img via asset URL |
| `EmptyState` | muted icon + one line |
| `Toast` | |
| `ThemeToggle` | |

Legend: horizontal list under the PDF toolbar, 8px color swatch + type name.
Clicking a swatch toggles that type in the overlay filter.

---

## 15. Keyboard and accessibility

| Key | Action |
| --- | --- |
| `⌘ Enter` | Start extract (home, file selected) |
| `1` / `2` / `3` | Original / Split / Extracted |
| `j` / `k` or arrows | Previous / next page |
| `[` / `]` | Previous / next element on the page |
| `Esc` | Clear selection; close popovers |
| `?` | Keyboard cheat sheet modal |

- All controls keyboard reachable
- Overlay rects: `role="button"`, `aria-label="{type} {reading_order}"`
- Status updates: `aria-live="polite"` on the header stage label
- Contrast: text on chips must meet 4.5:1; overlay labels are tooltips, not
  tiny text on the PDF
- Do not rely on color alone: status badges include words; failed pages also
  use the `FB` / danger dot

Target: desktop Chrome and Firefox. Safari is best-effort.

### 15.1 Breakpoints

| Width | Layout |
| --- | --- |
| ≥ 1280px | Full studio (strip + split + inspector) |
| 1100–1279px | Home becomes single column; review keeps split but inspector is a right drawer |
| 800–1099px | Review: hide reconstruction unless `Extracted` mode; strip remains |
| < 800px | Unsupported banner: “Extract is built for a desktop review workspace.” Still show job list and upload |

Do not build a native-app phone layout in v1.

---

## 16. API contract for the UI

Existing endpoints (already implemented):

```text
POST /api/v1/extractions
GET  /api/v1/extractions/{job_id}
GET  /api/v1/extractions/{job_id}/document
GET  /api/v1/extractions/{job_id}/report
GET  /api/v1/extractions/{job_id}/assets/{asset_path}
GET  /api/v1/health
```

`POST` is `multipart/form-data`:

| Field | Type | Default |
| --- | --- | --- |
| `file` | PDF | required |
| `allow_managed_apis` | `true` / `false` | `true` |
| `visual_understanding` | `true` / `false` | `false` |
| `page_start` | int | omit |
| `page_end` | int | omit |
| `force_extractor` | string | omit unless benchmark |
| `compare_extractors` | `true` / `false` | omit unless benchmark |

Create response `202`:

```json
{ "job_id": "job-…", "status": "queued" }
```

Status payload (`JobStatusResponse`) today:

```json
{
  "job_id": "job-…",
  "document_id": "sha256…",
  "status": "extracting",
  "page_count": 16,
  "sha256": "…",
  "policy": {
    "allow_managed_apis": true,
    "visual_understanding": false,
    "page_start": null,
    "page_end": null,
    "force_extractor": null,
    "compare_extractors": false
  },
  "error_code": null,
  "error_message": null,
  "duration_ms": null,
  "cache_hit": false,
  "created_at": "…",
  "updated_at": "…"
}
```

Error envelope:

```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "…",
    "details": {}
  }
}
```

Asset URLs:

```text
GET /api/v1/extractions/{job_id}/assets/assets/pictures/{file}
GET /api/v1/extractions/{job_id}/assets/assets/charts/page_{n}_r{i}.png
GET /api/v1/extractions/{job_id}/assets/assets/pages/page_{n}.png
```

`CanonicalElement.asset` is a relative path like `assets/pictures/…`. Prefix
with `/api/v1/extractions/{job_id}/assets/`.

### 16.1 Backend additions required to finish the UI

These are not in the current API. Implement them with the SPA, or the UI uses
the fallbacks noted.

| Addition | Why | Fallback if missing |
| --- | --- | --- |
| CORS for `http://127.0.0.1:5173` | Vite dev | Vite proxy; required for split origin |
| `GET /api/v1/extractions?limit=50` | Job list | `localStorage` of job ids |
| `original_filename` on status | List and header | Store filename at upload |
| `GET /api/v1/extractions/{job_id}/source` | PDF.js on reload | Cache `File` in IndexedDB (`extract-pdf:{jobId}`) |
| `GET /api/v1/ui-config` | Max bytes, max pages, benchmark flag, default managed APIs | Vite env + hard-coded 100MB / 500 pages |

Recommended list item:

```json
{
  "job_id": "job-…",
  "original_filename": "paper.pdf",
  "status": "completed_with_warnings",
  "page_count": 16,
  "duration_ms": 371721,
  "cache_hit": false,
  "created_at": "…",
  "force_extractor": null
}
```

Recommended ui-config:

```json
{
  "max_file_bytes": 104857600,
  "max_pages": 500,
  "benchmark_enabled": false,
  "allow_managed_apis_default": true
}
```

`inspection.json` is **not** a public endpoint. Derive scan/table/chart badges
from `document.summary`, `page.elements`, and `report.pages` / `report.routing`.

### 16.2 TypeScript types (canonical, minimum)

```ts
type JobStatus =
  | "queued"
  | "validating_input"
  | "inspecting"
  | "planning"
  | "extracting"
  | "validating_output"
  | "retrying"
  | "merging"
  | "completed"
  | "completed_with_warnings"
  | "failed";

type ElementType =
  | "heading"
  | "paragraph"
  | "list"
  | "table"
  | "picture"
  | "chart"
  | "diagram"
  | "formula"
  | "code"
  | "key_value"
  | "form_field"
  | "header"
  | "footer"
  | "footnote"
  | "page_number"
  | "unknown";

interface BoundingBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
  coordinate_origin: "top-left" | string;
  unit: "pdf-point" | string;
}
```

Match `app/models/canonical.py` and `app/models/jobs.py` rather than
re-documenting every field here. Optional fields must be treated as optional
in the UI (`html`, `asset`, `extractor`, confidences).

---

## 17. Copy deck

Use these strings. Do not invent friendlier paraphrases in v1.

| Location | Copy |
| --- | --- |
| Dropzone idle | Drop a PDF here |
| Dropzone hint | or click to choose · PDF only · max 100 MB · up to 500 pages |
| Primary button | Extract |
| Managed APIs on | Send pages to Gemini / Groq when needed. |
| Managed APIs note on | Selected pages may leave this machine. |
| Managed APIs off | Local extractors only. Scans use Docling OCR. Gemini and Groq will not run. |
| Visual | Interpret charts, graphs, and diagrams. Increases cost. |
| Visual disabled | Requires managed APIs (Groq). |
| Advanced | Advanced · benchmark |
| Running overlay | Extraction in progress. Overlays appear when the document is ready. |
| Warnings banner | Completed with warnings. Failed or low-confidence pages are marked in the strip. |
| Failed banner | Extraction failed. {error_code}: {error_message} |
| No overlays | No bounding boxes on this page. |
| No reconstruction | No elements to display. |
| Report empty fallbacks | No fallbacks. |
| JSON pending | JSON is written when the job finishes. |
| Unsupported width | Extract is built for a desktop review workspace. |
| Toast copied | Copied to clipboard |
| Window title running | Extracting — {filename} |
| Window title done | {filename} — Extract |

---

## 18. Local persistence

| Key | Value |
| --- | --- |
| `extract-theme` | `dark` \| `light` |
| `extract-jobs` | `string[]` job ids, newest first, cap 100 |
| `extract-job-names` | `{ [jobId]: filename }` |
| IndexedDB `extract-pdfs` | `jobId → Blob` for source PDF, cap 20 documents, LRU |

Do not store API keys in the frontend. There is no auth in v1.

---

## 19. Performance

- Render **one** PDF page at a time
- Cache PDF.js page canvases for the strip (thumb) and the stage separately
- Virtualize strip at > 40 pages
- Reconstruction and overlays bind only `pages[selected]`
- Document JSON for a 16-page paper can be tens of thousands of lines; keep it
  in memory once. JSON tab should not re-stringify on every render
- Images via asset endpoint: `loading="lazy"`
- Polling: one request in flight; no document/report fetch until terminal

---

## 20. Implementation order

Build in this sequence so each slice is demoable.

1. **Shell + tokens + theme** — empty routes, dark/light
2. **API client + types** — health check in the header as a quiet dot
3. **Upload + policy + create job** — redirect to review with running status
4. **Polling + header badges** — no PDF yet
5. **PDF.js stage from IndexedDB File** — page strip thumbs
6. **Fetch document on complete + overlays + selection**
7. **Reconstruction pane + inspector**
8. **Report tab**
9. **JSON tab + downloads**
10. **Job list hydration + localStorage**
11. **Source PDF endpoint + reload-safe review**
12. **Keyboard, legend, problems-only filter, toasts**
13. **Light theme pass and contrast audit**

Do not start compare-extractors layout, labeling, or chat.

---

## 21. Definition of done (v1)

A reviewer can:

1. Drop a PDF, leave managed APIs on, start extraction
2. Watch status move through inspecting → extracting → completed
3. See the original page with type-colored boxes
4. Click a table box and see the HTML table on the right and extractor in the
   inspector
5. Jump to a warned page from the strip
6. Open Report and see routes, fallbacks, cost, and validation codes
7. Download `document.json`
8. Reload the review URL and still see the PDF (after source endpoint or
   IndexedDB)
9. Toggle light theme without broken contrast on chips or overlays
10. Turn managed APIs off and see the local-only note; visual understanding
    disabled

If any of those fail, the UI is not done — extra chrome is not a substitute.
