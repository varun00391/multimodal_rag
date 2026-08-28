import { HARD_FAILURE_CODES } from "../lib/status";
import type { ExtractionReport } from "../api/types";
import { extractorColor } from "../lib/colors";
import { formatCost, formatDuration } from "../lib/format";

const DURATION_COLORS: Record<string, string> = {
  inspect_ms: "var(--info)",
  plan_ms: "var(--text-faint)",
  extract_ms: "var(--accent)",
  validate_ms: "var(--ok)",
  fallback_ms: "var(--warn)",
  merge_ms: "var(--ex-docling)",
};

const DURATION_LABELS: Record<string, string> = {
  inspect_ms: "Inspect",
  plan_ms: "Plan",
  extract_ms: "Extract",
  validate_ms: "Validate",
  fallback_ms: "Fallback",
  merge_ms: "Merge",
};

export function ReportView({
  report,
  onOpenPage,
}: {
  report: ExtractionReport;
  onOpenPage: (page: number) => void;
}) {
  const durations = report.durations ?? {};
  const timed = Object.entries(durations).filter(([key, value]) => key !== "total_ms" && typeof value === "number" && value > 0);
  const total = timed.reduce((sum, [, value]) => sum + value, 0) || 1;

  return (
    <div className="report">
      <div className="report-inner">
        <div className="stat-grid">
          <div className="card">
            <div className="section-label">Status</div>
            <div>{report.status}</div>
          </div>
          <div className="card">
            <div className="section-label">Duration</div>
            <div>{formatDuration(report.duration_ms)}</div>
          </div>
          <div className="card">
            <div className="section-label">Cost</div>
            <div>
              {formatCost(report.usage?.estimated_cost_usd)} · {report.usage?.total_tokens ?? 0} tok
            </div>
          </div>
          <div className="card">
            <div className="section-label">Cache</div>
            <div>
              {report.cache?.hit ? "hit" : "miss"} · {report.cache?.group_hits ?? 0}/{report.cache?.group_misses ?? 0}
            </div>
          </div>
        </div>

        <div className="card">
          {(report.extractors ?? []).map((name) => (
            <span key={name} className="chip" style={{ marginRight: 6, background: extractorColor(name), color: "#fff" }}>
              {name}
            </span>
          ))}
          {report.allow_managed_apis === false ? <span className="chip">local only</span> : null}
          <div className="stack-bar" style={{ marginTop: 12 }}>
            {timed.map(([key, value]) => (
              <div
                key={key}
                title={`${DURATION_LABELS[key] ?? key}: ${formatDuration(value)}`}
                style={{ width: `${(value / total) * 100}%`, background: DURATION_COLORS[key] ?? "var(--text-faint)" }}
              />
            ))}
          </div>
        </div>

        <div className="card">
          <div className="section-label">Inspection</div>
          <div className="field-note">{report.inspection_summary?.page_count ?? 0} pages</div>
          <ChipList label="Scanned" pages={report.inspection_summary?.scanned_pages ?? []} onOpenPage={onOpenPage} />
          <ChipList label="PyMuPDF fast path" pages={report.inspection_summary?.pymupdf_fast_path_pages ?? []} onOpenPage={onOpenPage} />
        </div>

        <div className="card">
          <div className="section-label">Routes</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Page</th>
                <th>Primary</th>
                <th>Routes</th>
                <th>Elements</th>
                <th>Validation</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(report.pages ?? []).map((row) => (
                <tr key={row.page} onClick={() => onOpenPage(row.page)}>
                  <td>{row.page}</td>
                  <td>{row.primary_route}</td>
                  <td>{(row.extraction_routes ?? []).join(", ")}</td>
                  <td>{row.element_count}</td>
                  <td>{row.validation_passed === false ? "fail" : "pass"}</td>
                  <td>{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="section-label">Groups</div>
          {(report.routing?.groups ?? []).map((group) => (
            <div key={group.group_id} className="field-note">
              {group.extractor}
              {group.profile ? ` · ${group.profile}` : ""} · {group.kind} · pages {(group.pages ?? []).join(", ")}
            </div>
          ))}
        </div>

        <div className="card">
          <div className="section-label">Fallbacks</div>
          {(report.fallbacks ?? []).length === 0 ? <div className="field-note">No fallbacks.</div> : null}
          {(report.fallbacks ?? []).map((item, index) => (
            <div key={`${item.page}-${index}`} className="field-note">
              p{item.page} · {item.reason_code} · {item.from_extractor} → {item.to_extractor} · {item.status}
            </div>
          ))}
        </div>

        <div className="card">
          <div className="section-label">Validation</div>
          <div className="field-note">min confidence {report.validation?.min_confidence ?? "—"}</div>
          {(report.validation?.pages ?? []).flatMap((page) =>
            page.failures.map((failure) => (
              <div
                key={`${page.page}-${failure.code}-${failure.element_id}`}
                className="field-note"
                style={{ color: HARD_FAILURE_CODES.has(failure.code) ? "var(--danger)" : "var(--warn)", cursor: "pointer" }}
                onClick={() => onOpenPage(page.page)}
              >
                p{page.page} · {failure.code}: {failure.message}
              </div>
            )),
          )}
        </div>

        <div className="card">
          <div className="section-label">Versions</div>
          {Object.entries(report.versions ?? {}).map(([key, value]) => (
            <div key={key} className="mono">
              {key}: {value}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChipList({ label, pages, onOpenPage }: { label: string; pages: number[]; onOpenPage: (page: number) => void }) {
  if (!pages.length) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <span className="field-note">{label}: </span>
      {pages.map((page) => (
        <button key={page} type="button" className="chip" style={{ marginRight: 4 }} onClick={() => onOpenPage(page)}>
          {page}
        </button>
      ))}
    </div>
  );
}
