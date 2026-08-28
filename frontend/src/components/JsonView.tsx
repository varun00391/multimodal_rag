import { useMemo, useState } from "react";
import { useToast } from "./Toast";

export function JsonView({
  documentJson,
  reportJson,
  ready,
}: {
  documentJson: unknown | null;
  reportJson: unknown | null;
  ready: boolean;
}) {
  const [tab, setTab] = useState<"document" | "report">("document");
  const toast = useToast();
  const text = useMemo(() => {
    const payload = tab === "document" ? documentJson : reportJson;
    return payload ? JSON.stringify(payload, null, 2) : "";
  }, [tab, documentJson, reportJson]);

  if (!ready) {
    return <div className="empty" style={{ padding: 24 }}>JSON is written when the job finishes.</div>;
  }

  return (
    <div className="json-view">
      <div className="jobs-toolbar">
        <div className="tabs" style={{ padding: 0 }}>
          <button type="button" className={tab === "document" ? "active" : ""} onClick={() => setTab("document")}>
            document.json
          </button>
          <button type="button" className={tab === "report" ? "active" : ""} onClick={() => setTab("report")}>
            extraction-report.json
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              void navigator.clipboard.writeText(text);
              toast("Copied to clipboard");
            }}
          >
            Copy
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => downloadJson(tab === "document" ? "document.json" : "extraction-report.json", text)}
          >
            Download
          </button>
        </div>
      </div>
      <pre className="json-pre">{text}</pre>
    </div>
  );
}

function downloadJson(filename: string, text: string): void {
  const blob = new Blob([text], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
