import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, createExtraction, getUiConfig, listJobs } from "../api/client";
import { FORCE_EXTRACTORS } from "../api/types";
import type { JobListItem } from "../api/types";
import { formatBytes, formatDuration, relativeTime, truncateId } from "../lib/format";
import { rememberJob, savePdf } from "../lib/storage";
import { isRunning } from "../lib/status";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";

type Filter = "all" | "running" | "done" | "failed";

export function JobsHome() {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const configQuery = useQuery({ queryKey: ["ui-config"], queryFn: getUiConfig });
  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: () => listJobs(50),
    refetchInterval: (query) => {
      const rows = query.state.data ?? [];
      return rows.some((job) => isRunning(job.status)) ? 2000 : 8000;
    },
  });

  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allowManaged, setAllowManaged] = useState<boolean | null>(null);
  const [visual, setVisual] = useState(false);
  const [pageStart, setPageStart] = useState("");
  const [pageEnd, setPageEnd] = useState("");
  const [forceExtractor, setForceExtractor] = useState("");
  const [compare, setCompare] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");

  const config = configQuery.data;
  const maxBytes = config?.max_file_bytes ?? 104_857_600;
  const maxPages = config?.max_pages ?? 500;
  const benchmark = config?.benchmark_enabled ?? false;
  const managed = allowManaged ?? config?.allow_managed_apis_default ?? true;

  const applyFile = useCallback(
    (next: File | null) => {
      setError(null);
      if (!next) {
        setFile(null);
        return;
      }
      const typeOk = next.type === "application/pdf" || next.name.toLowerCase().endsWith(".pdf");
      if (!typeOk) {
        setFile(null);
        setError("Only PDF files are accepted.");
        return;
      }
      if (next.size > maxBytes) {
        setFile(null);
        setError(`File exceeds the ${formatBytes(maxBytes)} limit.`);
        return;
      }
      setFile(next);
    },
    [maxBytes],
  );

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Select a PDF first.");
      const start = pageStart.trim() ? Number(pageStart) : undefined;
      const end = pageEnd.trim() ? Number(pageEnd) : undefined;
      if (start != null && end != null && start > end) {
        throw new Error("page_start must be less than or equal to page_end.");
      }
      const form = new FormData();
      form.append("file", file);
      form.append("allow_managed_apis", managed ? "true" : "false");
      form.append("visual_understanding", managed && visual ? "true" : "false");
      if (start != null && Number.isFinite(start)) form.append("page_start", String(start));
      if (end != null && Number.isFinite(end)) form.append("page_end", String(end));
      if (benchmark && forceExtractor) form.append("force_extractor", forceExtractor);
      if (benchmark && compare) form.append("compare_extractors", "true");
      return createExtraction(form);
    },
    onSuccess: async (created) => {
      if (file) {
        rememberJob(created.job_id, file.name);
        await savePdf(created.job_id, file);
      }
      if (compare) {
        toast("Compare flag submitted. Side-by-side view is not in v1; use the report.");
      }
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/jobs/${created.job_id}`);
    },
    onError: (err: unknown) => {
      const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Upload failed.";
      setError(message);
      toast(message);
    },
  });

  const jobs = useMemo(() => {
    const rows = jobsQuery.data ?? [];
    return rows.filter((job) => matchesFilter(job, filter, search));
  }, [jobsQuery.data, filter, search]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && file && !mutation.isPending) {
        mutation.mutate();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [file, mutation]);

  return (
    <div className="home">
      <section>
        <div
          className={`dropzone${dragOver ? " active" : ""}${error ? " error" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            applyFile(event.dataTransfer.files[0] ?? null);
          }}
          onClick={() => document.getElementById("pdf-input")?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              document.getElementById("pdf-input")?.click();
            }
          }}
          role="button"
          tabIndex={0}
        >
          <FileText size={28} />
          {file ? (
            <>
              <div className="dropzone-title">{file.name}</div>
              <div className="dropzone-hint">{formatBytes(file.size)}</div>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  applyFile(null);
                }}
              >
                Clear
              </button>
            </>
          ) : (
            <>
              <div className="dropzone-title">Drop a PDF here</div>
              <div className="dropzone-hint">
                or click to choose · PDF only · max {formatBytes(maxBytes)} · up to {maxPages} pages
              </div>
            </>
          )}
          <input
            id="pdf-input"
            type="file"
            accept="application/pdf,.pdf"
            hidden
            onChange={(event) => applyFile(event.target.files?.[0] ?? null)}
          />
        </div>
        {error ? <div className="field-note" style={{ color: "var(--danger)", marginTop: 8 }}>{error}</div> : null}

        <div className="policy">
          <div className="section-label">Extraction options</div>
          <div className="field">
            <div className="field-row">
              <div>
                <div className="field-copy">Allow managed APIs</div>
                <div className="field-note">Send pages to Gemini / Groq when needed.</div>
                <div className={`field-note${managed ? " privacy" : ""}`}>
                  {managed
                    ? "Selected pages may leave this machine."
                    : "Local extractors only. Scans use Docling OCR. Gemini and Groq will not run."}
                </div>
              </div>
              <button
                type="button"
                className={`switch${managed ? " on" : ""}`}
                role="switch"
                aria-checked={managed}
                onClick={() => {
                  if (managed) setVisual(false);
                  setAllowManaged(!managed);
                }}
              />
            </div>
          </div>
          <div className="field">
            <div className="field-row">
              <div>
                <div className="field-copy">Visual understanding</div>
                <div className="field-note">
                  {managed
                    ? "Interpret charts, graphs, and diagrams. Increases cost."
                    : "Requires managed APIs (Groq)."}
                </div>
              </div>
              <button
                type="button"
                className={`switch${visual && managed ? " on" : ""}`}
                role="switch"
                aria-checked={visual && managed}
                disabled={!managed}
                onClick={() => setVisual((value) => !value)}
              />
            </div>
          </div>
          <div className="field">
            <div className="field-copy">Page range</div>
            <div className="page-range">
              <input className="input" inputMode="numeric" placeholder="From" value={pageStart} onChange={(e) => setPageStart(e.target.value)} />
              <input className="input" inputMode="numeric" placeholder="To" value={pageEnd} onChange={(e) => setPageEnd(e.target.value)} />
            </div>
          </div>
          {benchmark ? (
            <div>
              <button type="button" className="disclosure" onClick={() => setAdvancedOpen((v) => !v)}>
                Advanced · benchmark {advancedOpen ? "▾" : "▸"}
              </button>
              {advancedOpen ? (
                <>
                  <div className="field">
                    <div className="field-copy">Force extractor</div>
                    <select className="select" value={forceExtractor} onChange={(e) => setForceExtractor(e.target.value)}>
                      {FORCE_EXTRACTORS.map((item) => (
                        <option key={item || "auto"} value={item}>
                          {item || "(auto hybrid)"}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="field-row">
                    <div className="field-copy">Compare extractors</div>
                    <button type="button" className={`switch${compare ? " on" : ""}`} role="switch" aria-checked={compare} onClick={() => setCompare((v) => !v)} />
                  </div>
                </>
              ) : null}
            </div>
          ) : null}
          <button
            className="btn btn-primary btn-block"
            type="button"
            disabled={!file || mutation.isPending}
            onClick={() => mutation.mutate()}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") mutation.mutate();
            }}
          >
            {mutation.isPending ? "Uploading…" : "Extract"}
          </button>
        </div>
      </section>

      <section>
        <div className="jobs-toolbar">
          <div className="section-label" style={{ margin: 0 }}>
            Recent jobs
          </div>
          <div className="segmented">
            {(["all", "running", "done", "failed"] as Filter[]).map((item) => (
              <button key={item} type="button" className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>
                {item[0].toUpperCase() + item.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <input className="input" placeholder="Filter by filename or job id" value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginBottom: 12 }} />
        {jobsQuery.isLoading ? <div className="empty">Loading jobs…</div> : null}
        {!jobsQuery.isLoading && jobs.length === 0 ? (
          <div className="empty">{search || filter !== "all" ? "No jobs match." : "No extractions yet. Drop a PDF to start."}</div>
        ) : null}
        {jobs.map((job) => (
          <Link key={job.job_id} to={`/jobs/${job.job_id}`} className="job-row">
            <div className="job-row-top">
              <span>{job.original_filename || "Untitled PDF"}</span>
              <span>
                {formatDuration(job.duration_ms)} {job.cache_hit ? <span className="chip">cache</span> : null}
              </span>
            </div>
            <div className="job-row-mid">
              <span>
                {job.page_count} pages · {job.force_extractor || "hybrid"}
              </span>
              <StatusBadge status={job.status} compact />
            </div>
            <div className="job-row-bot">
              <span className="job-id">{truncateId(job.job_id)}</span>
              <span>{job.status === "failed" ? job.job_id : relativeTime(job.created_at)}</span>
            </div>
            {isRunning(job.status) ? <div className="progress-bar" /> : null}
          </Link>
        ))}
      </section>
    </div>
  );
}

function matchesFilter(job: JobListItem, filter: Filter, search: string): boolean {
  const q = search.trim().toLowerCase();
  if (q) {
    const hay = `${job.original_filename ?? ""} ${job.job_id}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  if (filter === "running") return isRunning(job.status);
  if (filter === "failed") return job.status === "failed";
  if (filter === "done") return job.status === "completed" || job.status === "completed_with_warnings";
  return true;
}
