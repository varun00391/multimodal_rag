import { Copy } from "lucide-react";
import { useMemo, useState } from "react";
import { assetUrl } from "../api/client";
import type { CanonicalElement, CanonicalPage, ValidationFailure } from "../api/types";
import { ELEMENT_COLORS, extractorColor } from "../lib/colors";
import { useToast } from "./Toast";

export function ElementInspector({
  jobId,
  page,
  element,
  failures,
  expanded,
  onExpanded,
  height,
}: {
  jobId: string;
  page?: CanonicalPage;
  element: CanonicalElement | null;
  failures: ValidationFailure[];
  expanded: boolean;
  onExpanded: (value: boolean) => void;
  height: number;
}) {
  const toast = useToast();
  const availableTabs = useMemo(() => {
    const tabs: Array<"text" | "markdown" | "html"> = [];
    if (element?.text) tabs.push("text");
    if (element?.markdown) tabs.push("markdown");
    if (element?.html) tabs.push("html");
    return tabs;
  }, [element]);
  const [contentTab, setContentTab] = useState<"text" | "markdown" | "html">("text");
  const tab = availableTabs.includes(contentTab) ? contentTab : availableTabs[0];

  return (
    <div className="inspector" style={{ height: expanded ? height : 40 }}>
      <div className="inspector-bar" onClick={() => onExpanded(!expanded)}>
        <span>
          {element
            ? `${element.type} · ${element.element_id}`
            : page
              ? `Page ${page.page} diagnostics`
              : "Select an element on the page"}
        </span>
        <span>{expanded ? "▾" : "▴"}</span>
      </div>
      {expanded ? (
        <div className="inspector-body" style={{ height: height - 40 }}>
          {element ? (
            <>
              <div>
                <span className="chip" style={{ background: ELEMENT_COLORS[element.type], color: "#fff" }}>
                  {element.type}
                </span>
                <div className="mono" style={{ marginTop: 8 }}>
                  {element.element_id}
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={(event) => {
                      event.stopPropagation();
                      void navigator.clipboard.writeText(element.element_id);
                      toast("Copied to clipboard");
                    }}
                  >
                    <Copy size={12} />
                  </button>
                </div>
                <div className="field-note">
                  page {element.page} · reading order {element.reading_order}
                </div>
                <Confidence value={element.confidence} />
              </div>
              <div>
                {availableTabs.length ? (
                  <div className="segmented" style={{ marginBottom: 8 }}>
                    {availableTabs.map((item) => (
                      <button key={item} type="button" className={tab === item ? "active" : ""} onClick={() => setContentTab(item)}>
                        {item}
                      </button>
                    ))}
                  </div>
                ) : null}
                <pre className="recon-pre" style={{ maxHeight: height - 90, overflow: "auto", color: "var(--text-invert)" }}>
                  {tab === "html" ? element.html : tab === "markdown" ? element.markdown : element.text}
                </pre>
                {element.asset ? (
                  <a href={assetUrl(jobId, element.asset)} target="_blank" rel="noreferrer">
                    <img src={assetUrl(jobId, element.asset)} alt="" style={{ width: 72, marginTop: 8 }} />
                  </a>
                ) : null}
              </div>
              <div>
                <ExtractorBlock element={element} page={page} failures={failures} />
              </div>
            </>
          ) : page ? (
            <PageDiagnostics page={page} />
          ) : (
            <div className="empty">Select an element on the page</div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function Confidence({ value }: { value?: number | null }) {
  if (value == null) return null;
  const color = value >= 0.85 ? "var(--ok)" : value >= 0.6 ? "var(--warn)" : "var(--danger)";
  return (
    <div style={{ marginTop: 8 }}>
      <div className="field-note">confidence {value.toFixed(2)}</div>
      <div className="meter">
        <span style={{ width: `${Math.round(value * 100)}%`, background: color }} />
      </div>
    </div>
  );
}

function ExtractorBlock({
  element,
  page,
  failures,
}: {
  element: CanonicalElement;
  page?: CanonicalPage;
  failures: ValidationFailure[];
}) {
  const ex = element.extractor;
  return (
    <>
      <span className="chip" style={{ background: extractorColor(ex?.name), color: "#fff" }}>
        {ex?.name ?? "unknown"}
        {ex?.profile ? ` · ${ex.profile}` : ""}
      </span>
      <div className="mono" style={{ marginTop: 8 }}>
        {ex?.version ? `v${ex.version}` : null}
        {ex?.adapter_version ? ` · adapter ${ex.adapter_version}` : null}
        {ex?.model ? ` · ${ex.model}` : null}
        {ex?.prompt_version != null ? ` · prompt ${ex.prompt_version}` : null}
      </div>
      <div className="field-note">attempt {element.provenance?.attempt ?? 1}</div>
      {page?.routing_reasons?.length ? (
        <ul style={{ paddingLeft: 16, fontSize: 12, color: "var(--text-muted)" }}>
          {page.routing_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      {failures.length ? (
        <ul style={{ paddingLeft: 16, fontSize: 12, color: "var(--danger)" }}>
          {failures.map((item) => (
            <li key={`${item.code}-${item.message}`}>
              {item.code}: {item.message}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

function PageDiagnostics({ page }: { page: CanonicalPage }) {
  return (
    <div style={{ gridColumn: "1 / -1" }}>
      <div>
        primary {page.primary_route} · routes {(page.extraction_routes ?? []).join(", ")}
      </div>
      <Confidence value={page.overall_confidence} />
      <ul style={{ fontSize: 12, color: "var(--text-muted)" }}>
        {(page.routing_reasons ?? []).map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      {(page.attempts ?? []).map((attempt) => (
        <div key={`${attempt.extractor}-${attempt.attempt}`} className="field-note">
          {attempt.extractor} · {attempt.status} · {attempt.element_count ?? 0} elements
        </div>
      ))}
    </div>
  );
}
