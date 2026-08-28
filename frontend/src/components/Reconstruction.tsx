import katex from "katex";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { assetUrl } from "../api/client";
import type { CanonicalElement, CanonicalPage } from "../api/types";
import { ELEMENT_COLORS } from "../lib/colors";
import { looksLikeTex } from "../lib/format";

export function Reconstruction({
  jobId,
  page,
  selectedId,
  onSelect,
}: {
  jobId: string;
  page?: CanonicalPage;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (!page) {
    return (
      <div className="recon">
        <div className="empty" style={{ padding: 24 }}>
          No elements to display.
        </div>
      </div>
    );
  }
  const elements = [...page.elements].sort((a, b) => a.reading_order - b.reading_order);
  return (
    <div className="recon">
      <div className="recon-page">
        <div className="recon-head">
          Page {page.page} · {elements.length} elements
        </div>
        {elements.length === 0 ? <div className="recon-muted">No elements to display.</div> : null}
        {elements.map((el) => (
          <div
            key={el.element_id}
            className={`recon-block${el.element_id === selectedId ? " selected" : ""}`}
            style={{ borderLeftColor: el.element_id === selectedId ? ELEMENT_COLORS[el.type] : undefined }}
            onClick={() => onSelect(el.element_id)}
          >
            <ElementView jobId={jobId} element={el} />
          </div>
        ))}
      </div>
    </div>
  );
}

function ElementView({ jobId, element }: { jobId: string; element: CanonicalElement }) {
  const merged = Array.isArray(element.metadata?.duplicate_sources);
  const chip = merged ? <span className="chip">merged</span> : null;
  switch (element.type) {
    case "heading": {
      const md = element.markdown ?? "";
      if (md.startsWith("# ") || md.startsWith("## ")) {
        return (
          <h2>
            {element.text} {chip}
          </h2>
        );
      }
      return (
        <h3>
          {element.text} {chip}
        </h3>
      );
    }
    case "paragraph":
      return <p>{element.text}</p>;
    case "list":
      return element.markdown ? <Markdown text={element.markdown} /> : <ul>{(element.text ?? "").split("\n").map((line, i) => <li key={i}>{line}</li>)}</ul>;
    case "table":
      if (element.html) {
        return <div className="table-wrap" dangerouslySetInnerHTML={{ __html: element.html }} />;
      }
      if (element.markdown) return <div className="table-wrap"><Markdown text={element.markdown} /></div>;
      return <pre className="recon-pre">{element.text}</pre>;
    case "picture":
    case "chart":
    case "diagram":
      return (
        <figure>
          {element.asset ? <img src={assetUrl(jobId, element.asset)} alt={element.text ?? element.type} /> : null}
          <figcaption className="recon-muted">
            {element.text} {chip}
          </figcaption>
        </figure>
      );
    case "formula":
      if (element.text && looksLikeTex(element.text)) {
        return <div dangerouslySetInnerHTML={{ __html: katex.renderToString(element.text.replace(/^\$|\$$/g, ""), { throwOnError: false }) }} />;
      }
      return <code>{element.text}</code>;
    case "code":
      return <pre className="recon-pre">{element.text}</pre>;
    case "key_value":
      return element.markdown ? <Markdown text={element.markdown} /> : <p>{element.text}</p>;
    case "form_field":
      return <p>{element.text}</p>;
    case "header":
    case "footer":
    case "footnote":
      return <p className="recon-muted">{element.text}</p>;
    case "page_number":
      return null;
    default:
      return <div className="recon-unknown">{element.text}</div>;
  }
}

function Markdown({ text }: { text: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>;
}
