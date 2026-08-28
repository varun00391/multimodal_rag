import { useQuery } from "@tanstack/react-query";
import { Copy, Download, FileBarChart } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { fetchSourceBlob, getDocument, getJob, getReport } from "../api/client";
import type { CanonicalPage, ElementType, JobStatus } from "../api/types";
import { ElementInspector } from "../components/ElementInspector";
import { JsonView } from "../components/JsonView";
import { PdfStage } from "../components/PdfStage";
import { Reconstruction } from "../components/Reconstruction";
import { ReportView } from "../components/ReportView";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { extractorColor } from "../lib/colors";
import { formatCost, formatDuration } from "../lib/format";
import { loadPdfDocument, renderPage, type PdfDocument } from "../lib/pdf";
import { loadPdf, readJobNames, savePdf } from "../lib/storage";
import { isRunning, isTerminal, stageLabel } from "../lib/status";

const ALL_TYPES = new Set<ElementType>([
  "heading",
  "paragraph",
  "list",
  "table",
  "picture",
  "chart",
  "diagram",
  "formula",
  "code",
  "key_value",
  "form_field",
  "header",
  "footer",
  "footnote",
  "page_number",
  "unknown",
]);

type Tab = "review" | "report" | "json";
type ViewMode = "split" | "original" | "extracted";

export function JobReview({ onFilename }: { onFilename: (name: string | null) => void }) {
  const { jobId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const toast = useToast();
  const tab = (params.get("tab") as Tab) || "review";
  const page = Number(params.get("page") || "1");
  const view = (params.get("view") as ViewMode) || "split";

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && isRunning(status) ? 1000 : false;
    },
    retry: false,
  });

  const ready = Boolean(jobQuery.data && isTerminal(jobQuery.data.status));
  const documentQuery = useQuery({
    queryKey: ["document", jobId],
    queryFn: () => getDocument(jobId),
    enabled: ready,
    retry: 2,
  });
  const reportQuery = useQuery({
    queryKey: ["report", jobId],
    queryFn: () => getReport(jobId),
    enabled: ready,
    retry: 2,
  });

  const [pdf, setPdf] = useState<PdfDocument | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overlayOn, setOverlayOn] = useState(true);
  const [problemsOnly, setProblemsOnly] = useState(false);
  const [enabledTypes, setEnabledTypes] = useState<Set<ElementType>>(new Set(ALL_TYPES));
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [split, setSplit] = useState(50);
  const [helpOpen, setHelpOpen] = useState(false);
  const [thumbs, setThumbs] = useState<Record<number, string>>({});

  const filename =
    jobQuery.data?.original_filename ||
    documentQuery.data?.source.filename ||
    readJobNames()[jobId] ||
    jobId;

  useEffect(() => {
    onFilename(filename);
    return () => onFilename(null);
  }, [filename, onFilename]);

  useEffect(() => {
    document.title = jobQuery.data && isRunning(jobQuery.data.status) ? `Extracting — ${filename}` : `${filename} — Extract`;
    return () => {
      document.title = "Extract — Hybrid PDF Studio";
    };
  }, [filename, jobQuery.data]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      let blob = await loadPdf(jobId);
      if (!blob) {
        blob = await fetchSourceBlob(jobId);
        await savePdf(jobId, blob);
      }
      const buffer = await blob.arrayBuffer();
      const doc = await loadPdfDocument(buffer);
      if (!cancelled) setPdf(doc);
    }
    void load().catch(() => {
      if (!cancelled) setPdf(null);
    });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const pageCount = jobQuery.data?.page_count || documentQuery.data?.page_count || pdf?.numPages || 1;
  const canonicalPage = documentQuery.data?.pages.find((item) => item.page === page);
  const selected = canonicalPage?.elements.find((el) => el.element_id === selectedId) ?? null;

  const problemIds = useMemo(() => {
    const ids = new Set<string>();
    for (const item of reportQuery.data?.validation?.pages ?? []) {
      for (const failure of item.failures) {
        if (failure.element_id) ids.add(failure.element_id);
      }
    }
    return ids;
  }, [reportQuery.data]);

  const fallbackPages = useMemo(() => new Set((reportQuery.data?.fallbacks ?? []).map((item) => item.page)), [reportQuery.data]);
  const scanned = new Set(documentQuery.data?.summary.scanned_pages ?? reportQuery.data?.inspection_summary?.scanned_pages ?? []);

  useEffect(() => {
    if (!pdf) return;
    let cancelled = false;
    const canvas = document.createElement("canvas");
    void (async () => {
      const next: Record<number, string> = {};
      const limit = Math.min(pageCount, 80);
      for (let n = 1; n <= limit; n += 1) {
        await renderPage(pdf, n, canvas, 72);
        next[n] = canvas.toDataURL("image/png");
        if (cancelled) return;
      }
      if (!cancelled) setThumbs(next);
    })();
    return () => {
      cancelled = true;
    };
  }, [pdf, pageCount]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT") return;
      if (event.key === "?") {
        setHelpOpen((v) => !v);
        return;
      }
      if (event.key === "Escape") {
        setSelectedId(null);
        setHelpOpen(false);
        return;
      }
      if (event.key === "1") setView("original");
      if (event.key === "2") setView("split");
      if (event.key === "3") setView("extracted");
      if (event.key === "j" || event.key === "ArrowDown") setPage(Math.min(pageCount, page + 1));
      if (event.key === "k" || event.key === "ArrowUp") setPage(Math.max(1, page - 1));
      if (event.key === "[") moveElement(-1);
      if (event.key === "]") moveElement(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function setTab(next: Tab) {
    const copy = new URLSearchParams(params);
    copy.set("tab", next);
    setParams(copy, { replace: true });
  }

  function setPage(next: number) {
    const copy = new URLSearchParams(params);
    copy.set("page", String(next));
    setParams(copy, { replace: true });
    setSelectedId(null);
  }

  function setView(next: ViewMode) {
    const copy = new URLSearchParams(params);
    copy.set("view", next);
    setParams(copy, { replace: true });
  }

  function moveElement(delta: number) {
    const elements = [...(canonicalPage?.elements ?? [])].sort((a, b) => a.reading_order - b.reading_order);
    if (!elements.length) return;
    const index = elements.findIndex((el) => el.element_id === selectedId);
    const next = elements[(index < 0 ? 0 : index + delta + elements.length) % elements.length];
    setSelectedId(next.element_id);
  }

  if (jobQuery.isError) {
    return (
      <div className="error-card">
        <h1>Job not found</h1>
        <p>JOB_NOT_FOUND</p>
        <Link to="/">Back to Jobs</Link>
      </div>
    );
  }

  const job = jobQuery.data;
  const summary = documentQuery.data?.summary;
  const failedCount = summary?.failed_pages?.length ?? 0;

  return (
    <div className="review">
      <header className="job-header">
        <div className="job-header-row">
          <div className="job-title">
            <h1 title={filename}>{filename}</h1>
            {job ? <StatusBadge status={job.status} /> : null}
            {job && isRunning(job.status) ? <span className="field-note">{stageLabel(job.status)}</span> : null}
            {job?.cache_hit ? <span className="chip">cache</span> : null}
          </div>
          <div className="stats">
            <span className="chip">{pageCount} pp</span>
            {job?.duration_ms != null ? <span className="chip">{formatDuration(job.duration_ms)}</span> : null}
            {summary?.estimated_cost_usd != null || reportQuery.data?.usage?.estimated_cost_usd != null ? (
              <span className="chip">{formatCost(summary?.estimated_cost_usd ?? reportQuery.data?.usage?.estimated_cost_usd)}</span>
            ) : null}
            {summary?.element_counts ? (
              <span className="chip">
                {summary.element_counts.paragraph ?? 0}¶ {summary.element_counts.table ?? 0} tbl {summary.element_counts.chart ?? 0} cht
              </span>
            ) : null}
            {failedCount > 0 ? <span className="chip" style={{ color: "var(--danger)" }}>{failedCount} failed</span> : null}
            <button
              type="button"
              className="icon-btn"
              title="Copy job id"
              onClick={() => {
                void navigator.clipboard.writeText(jobId);
                toast("Job id copied");
              }}
            >
              <Copy size={14} />
            </button>
            <button
              type="button"
              className="icon-btn"
              title="Download document"
              disabled={!documentQuery.data}
              onClick={() => download("document.json", documentQuery.data)}
            >
              <Download size={14} />
            </button>
            <button
              type="button"
              className="icon-btn"
              title="Download report"
              disabled={!reportQuery.data}
              onClick={() => download("extraction-report.json", reportQuery.data)}
            >
              <FileBarChart size={14} />
            </button>
          </div>
        </div>
        <div className="job-header-row">
          <div className="tabs">
            <button type="button" className={tab === "review" ? "active" : ""} onClick={() => setTab("review")}>
              Review
            </button>
            <button
              type="button"
              className={tab === "report" ? "active" : ""}
              disabled={!ready}
              title={ready ? undefined : "Available when extraction finishes"}
              onClick={() => setTab("report")}
            >
              Report
            </button>
            <button
              type="button"
              className={tab === "json" ? "active" : ""}
              disabled={!ready}
              title={ready ? undefined : "Available when extraction finishes"}
              onClick={() => setTab("json")}
            >
              JSON
            </button>
          </div>
          {tab === "review" ? (
            <div className="segmented">
              <button type="button" className={view === "original" ? "active" : ""} onClick={() => setView("original")}>
                Original
              </button>
              <button type="button" className={view === "split" ? "active" : ""} onClick={() => setView("split")}>
                Split
              </button>
              <button type="button" className={view === "extracted" ? "active" : ""} onClick={() => setView("extracted")}>
                Extracted
              </button>
            </div>
          ) : null}
        </div>
        {job?.status === "completed_with_warnings" ? (
          <div className="banner banner-warn">Completed with warnings. Failed or low-confidence pages are marked in the strip.</div>
        ) : null}
        {job?.status === "failed" ? (
          <div className="banner banner-danger">
            Extraction failed. {job.error_code}: {job.error_message}
          </div>
        ) : null}
        {job && isRunning(job.status) ? (
          <div className="banner banner-warn">Extraction in progress. Overlays appear when the document is ready.</div>
        ) : null}
      </header>

      {tab === "report" && reportQuery.data ? (
        <ReportView
          report={reportQuery.data}
          onOpenPage={(next) => {
            setPage(next);
            setTab("review");
          }}
        />
      ) : null}
      {tab === "json" ? (
        <JsonView documentJson={documentQuery.data ?? null} reportJson={reportQuery.data ?? null} ready={ready} />
      ) : null}

      {tab === "review" ? (
        <div className="review-body">
          <nav className="strip">
            {Array.from({ length: pageCount }, (_, index) => index + 1).map((n) => (
              <button key={n} type="button" className={`strip-item${n === page ? " selected" : ""}`} onClick={() => setPage(n)}>
                <div
                  className="thumb"
                  style={{ borderLeft: `3px solid ${extractorColor(pageMeta(documentQuery.data?.pages, n)?.primary_route)}` }}
                >
                  {thumbs[n] ? <img src={thumbs[n]} alt={`Page ${n}`} /> : null}
                  <span className={`thumb-dot ${dotClass(pageMeta(documentQuery.data?.pages, n), fallbackPages.has(n), job?.status)}`} />
                  <div className="thumb-badges">
                    {scanned.has(n) ? <span className="thumb-badge">SCAN</span> : null}
                    {hasType(pageMeta(documentQuery.data?.pages, n), "table") ? <span className="thumb-badge">TBL</span> : null}
                    {hasType(pageMeta(documentQuery.data?.pages, n), "chart") || hasType(pageMeta(documentQuery.data?.pages, n), "diagram") ? (
                      <span className="thumb-badge">CHART</span>
                    ) : null}
                    {fallbackPages.has(n) ? <span className="thumb-badge">FB</span> : null}
                  </div>
                </div>
                {n}
              </button>
            ))}
          </nav>
          <div
            className={`split ${view}`}
            style={view === "split" ? { gridTemplateColumns: `minmax(0, ${split}fr) 6px minmax(0, ${100 - split}fr)` } : undefined}
          >
            {view !== "extracted" ? (
              <PdfStage
                pdf={pdf}
                pageNumber={page}
                canonicalPage={canonicalPage}
                selectedId={selectedId}
                problemIds={problemIds}
                overlayOn={overlayOn && Boolean(documentQuery.data)}
                problemsOnly={problemsOnly}
                enabledTypes={enabledTypes}
                onSelect={setSelectedId}
                onOverlayOn={setOverlayOn}
                onProblemsOnly={setProblemsOnly}
                onToggleType={(type) => {
                  setEnabledTypes((current) => {
                    const next = new Set(current);
                    if (next.has(type)) next.delete(type);
                    else next.add(type);
                    return next;
                  });
                }}
              />
            ) : null}
            {view === "split" ? (
              <div
                className="split-handle"
                onDoubleClick={() => setSplit(50)}
                onMouseDown={(event) => {
                  const startX = event.clientX;
                  const start = split;
                  const onMove = (move: MouseEvent) => {
                    const parent = (event.target as HTMLElement).parentElement;
                    if (!parent) return;
                    const delta = ((move.clientX - startX) / parent.clientWidth) * 100;
                    setSplit(Math.min(80, Math.max(20, start + delta)));
                  };
                  const onUp = () => {
                    window.removeEventListener("mousemove", onMove);
                    window.removeEventListener("mouseup", onUp);
                  };
                  window.addEventListener("mousemove", onMove);
                  window.addEventListener("mouseup", onUp);
                }}
              />
            ) : null}
            {view !== "original" ? (
              <Reconstruction jobId={jobId} page={canonicalPage} selectedId={selectedId} onSelect={setSelectedId} />
            ) : null}
          </div>
          <ElementInspector
            jobId={jobId}
            page={canonicalPage}
            element={selected}
            failures={(reportQuery.data?.validation?.pages ?? [])
              .filter((item) => item.page === page)
              .flatMap((item) => item.failures)
              .filter((item) => !selected || item.element_id === selected.element_id)}
            expanded={inspectorOpen}
            onExpanded={setInspectorOpen}
            height={220}
          />
        </div>
      ) : null}

      {helpOpen ? (
        <div className="kbd-modal" onClick={() => setHelpOpen(false)}>
          <div className="kbd-card" onClick={(event) => event.stopPropagation()}>
            <h2>Keyboard</h2>
            <p><kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> original / split / extracted</p>
            <p><kbd>j</kbd> / <kbd>k</kbd> next / previous page</p>
            <p><kbd>[</kbd> / <kbd>]</kbd> previous / next element</p>
            <p><kbd>Esc</kbd> clear selection</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function pageMeta(pages: CanonicalPage[] | undefined, n: number): CanonicalPage | undefined {
  return pages?.find((item) => item.page === n);
}

function hasType(page: CanonicalPage | undefined, type: ElementType): boolean {
  return Boolean(page?.elements.some((el) => el.type === type));
}

function dotClass(page: CanonicalPage | undefined, fallback: boolean, status?: JobStatus): string {
  if (status && isRunning(status)) return "run";
  if (page?.errors?.length || fallback) return "fail";
  if ((page?.warnings?.length ?? 0) > 0) return "warn";
  return "";
}

function download(filename: string, data: unknown): void {
  if (!data) return;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
