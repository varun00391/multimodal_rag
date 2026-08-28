import { useEffect, useMemo, useRef, useState } from "react";
import type { CanonicalElement, CanonicalPage, ElementType } from "../api/types";
import { bboxToCss } from "../lib/bbox";
import { ELEMENT_COLORS, typeFill } from "../lib/colors";
import { renderPage, type PdfDocument } from "../lib/pdf";

const TYPES: ElementType[] = [
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
];

export function PdfStage({
  pdf,
  pageNumber,
  canonicalPage,
  selectedId,
  problemIds,
  overlayOn,
  problemsOnly,
  enabledTypes,
  onSelect,
  onOverlayOn,
  onProblemsOnly,
  onToggleType,
}: {
  pdf: PdfDocument | null;
  pageNumber: number;
  canonicalPage?: CanonicalPage;
  selectedId: string | null;
  problemIds: Set<string>;
  overlayOn: boolean;
  problemsOnly: boolean;
  enabledTypes: Set<ElementType>;
  onSelect: (id: string | null) => void;
  onOverlayOn: (value: boolean) => void;
  onProblemsOnly: (value: boolean) => void;
  onToggleType: (type: ElementType) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [fit, setFit] = useState<"width" | "page">("width");
  const [zoom, setZoom] = useState(1);
  const [filterOpen, setFilterOpen] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current?.parentElement;
    if (!pdf || !canvas || !wrap) return;
    const available = Math.max(320, wrap.clientWidth - 32);
    const target = fit === "width" ? available * zoom : Math.min(available, 720) * zoom;
    let cancelled = false;
    void renderPage(pdf, pageNumber, canvas, target).then((result) => {
      if (!cancelled) setSize({ width: result.cssWidth, height: result.cssHeight });
    });
    return () => {
      cancelled = true;
    };
  }, [pdf, pageNumber, fit, zoom]);

  const boxes = useMemo(() => {
    if (!canonicalPage || !overlayOn || size.width === 0) return [];
    return [...canonicalPage.elements]
      .filter((el) => el.bbox)
      .filter((el) => enabledTypes.has(el.type))
      .filter((el) => !problemsOnly || problemIds.has(el.element_id));
  }, [canonicalPage, overlayOn, enabledTypes, problemsOnly, problemIds, size.width]);

  const presentTypes = useMemo(() => {
    const found = new Set((canonicalPage?.elements ?? []).map((el) => el.type));
    return TYPES.filter((type) => found.has(type));
  }, [canonicalPage]);

  return (
    <div className="stage">
      <div className="stage-toolbar">
        <button type="button" className="icon-btn" onClick={() => setZoom((z) => Math.max(0.4, z - 0.1))}>
          −
        </button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" className="icon-btn" onClick={() => setZoom((z) => Math.min(3, z + 0.1))}>
          +
        </button>
        <div className="segmented">
          <button type="button" className={fit === "width" ? "active" : ""} onClick={() => setFit("width")}>
            Fit width
          </button>
          <button type="button" className={fit === "page" ? "active" : ""} onClick={() => setFit("page")}>
            Fit page
          </button>
        </div>
        <span>Overlay</span>
        <button
          type="button"
          className={`switch${overlayOn ? " on" : ""}`}
          role="switch"
          aria-checked={overlayOn}
          onClick={() => onOverlayOn(!overlayOn)}
        />
        <span>Problems only</span>
        <button
          type="button"
          className={`switch${problemsOnly ? " on" : ""}`}
          role="switch"
          aria-checked={problemsOnly}
          onClick={() => onProblemsOnly(!problemsOnly)}
        />
        <button type="button" className="btn btn-ghost" style={{ height: 24, fontSize: 11 }} onClick={() => setFilterOpen((v) => !v)}>
          Overlay filter
        </button>
        {filterOpen ? (
          <div className="popover">
            {presentTypes.map((type) => (
              <label key={type} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, marginBottom: 4 }}>
                <input type="checkbox" checked={enabledTypes.has(type)} onChange={() => onToggleType(type)} />
                {type}
              </label>
            ))}
          </div>
        ) : null}
      </div>
      <div className="legend" style={{ padding: "0 12px 8px" }}>
        {presentTypes.map((type) => (
          <button key={type} type="button" onClick={() => onToggleType(type)} style={{ opacity: enabledTypes.has(type) ? 1 : 0.35 }}>
            <span className="swatch" style={{ background: ELEMENT_COLORS[type] }} />
            {type}
          </button>
        ))}
      </div>
      <div ref={wrapRef} className="stage-canvas-wrap" onClick={() => onSelect(null)}>
        {pdf ? <canvas ref={canvasRef} /> : <div className="empty">Loading PDF…</div>}
        {boxes.map((el) => (
          <BboxRect
            key={el.element_id}
            element={el}
            page={canonicalPage!}
            css={size}
            selected={el.element_id === selectedId}
            problem={problemIds.has(el.element_id)}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}

function BboxRect({
  element,
  page,
  css,
  selected,
  problem,
  onSelect,
}: {
  element: CanonicalElement;
  page: CanonicalPage;
  css: { width: number; height: number };
  selected: boolean;
  problem: boolean;
  onSelect: (id: string | null) => void;
}) {
  if (!element.bbox) return null;
  const box = bboxToCss(element.bbox, page.width, page.height, css.width, css.height);
  return (
    <div
      className="bbox"
      role="button"
      aria-label={`${element.type} ${element.reading_order}`}
      title={`${element.type} · ${element.extractor?.name ?? "unknown"}`}
      style={{
        left: box.left,
        top: box.top,
        width: box.width,
        height: box.height,
        background: typeFill(element.type, selected),
        border: `${selected ? 2.5 : 1.5}px solid ${ELEMENT_COLORS[element.type]}`,
        outline: problem ? "1px dashed var(--danger)" : undefined,
        outlineOffset: 2,
        zIndex: selected ? 2 : 1,
      }}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(element.element_id);
      }}
    />
  );
}
