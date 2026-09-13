import { useEffect, useState } from "react";
import { FileImage, FileSpreadsheet, FileText, Film, Music, Trash2, Upload } from "lucide-react";
import { api } from "../api/client";

const ICONS = {
  pdf: FileText,
  text: FileText,
  docx: FileText,
  pptx: FileText,
  spreadsheet: FileSpreadsheet,
  image: FileImage,
  video: Film,
  audio: Music,
};

function bytes(n) {
  if (n > 1_000_000) return `${(n / 1_000_000).toFixed(1)} MB`;
  if (n > 1000) return `${(n / 1000).toFixed(1)} KB`;
  return `${n} B`;
}

export default function Library() {
  const [docs, setDocs] = useState([]);
  const [q, setQ] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setDocs(await api("/documents"));
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function upload(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    try {
      await api("/documents/upload", { method: "POST", body: form, isForm: true });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const filtered = docs.filter((d) => d.filename.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <p className="kicker mb-2">Corpus</p>
          <h1 className="font-serif text-4xl tracking-tight">Library</h1>
          <p className="text-sm text-mute mt-2 font-light">PDFs, images, video, sheets, and anything else you want to ask.</p>
        </div>
        <label className="btn-primary cursor-pointer">
          <Upload size={15} /> {busy ? "Indexing…" : "Add files"}
          <input type="file" multiple className="hidden" onChange={(e) => upload(e.target.files)} />
        </label>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          upload(e.dataTransfer.files);
        }}
        className={`rounded-[24px] border border-dashed p-12 text-center mb-8 transition ${
          drag ? "border-mist bg-mist/5" : "border-line bg-ink/60"
        }`}
      >
        <p className="text-sm text-mute">Drop PDFs, images, video, audio, Word, PowerPoint, or Excel here.</p>
      </div>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Filter by filename"
        className="field mb-6 max-w-sm"
      />

      {error && <p className="text-sm text-rose-700 mb-4">{error}</p>}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((d) => {
          const Icon = ICONS[d.modality] || FileText;
          return (
            <article key={d.id} className="card p-4 hover:shadow-lift transition">
              <div className="flex items-start justify-between gap-3">
                <div className="h-10 w-10 rounded-2xl bg-ink text-cream grid place-items-center">
                  <Icon size={18} strokeWidth={1.7} />
                </div>
                <button
                  className="text-mute hover:text-rose-700"
                  onClick={async () => {
                    await api(`/documents/${d.id}`, { method: "DELETE" });
                    load();
                  }}
                >
                  <Trash2 size={15} />
                </button>
              </div>
              <h3 className="mt-4 text-sm font-medium truncate" title={d.filename}>
                {d.filename}
              </h3>
              <p className="text-[11px] text-mute mt-1.5">
                <span className="text-mist">{d.modality}</span>
                <span> · {d.source} · {bytes(d.size_bytes)} · {d.chunk_count} chunks</span>
              </p>
            </article>
          );
        })}
      </div>
      {filtered.length === 0 && <p className="text-sm text-mute">No files yet. Upload or sync a connector.</p>}
    </div>
  );
}
