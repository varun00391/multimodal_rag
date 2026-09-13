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
          <h1 className="font-serif text-4xl">Library</h1>
          <p className="text-sm text-mute mt-1">PDFs, images, video, sheets, and anything else you want to ask.</p>
        </div>
        <label className="rounded-xl bg-lime text-ink text-sm font-semibold px-4 py-2.5 cursor-pointer inline-flex items-center gap-2">
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
        className={`rounded-3xl border border-dashed p-10 text-center mb-8 transition ${
          drag ? "border-lime bg-lime/10" : "border-line bg-white/[0.02]"
        }`}
      >
        <p className="text-sm text-mute">Drop PDFs, images, video, audio, Word, PowerPoint, or Excel here.</p>
      </div>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Filter by filename"
        className="mb-6 w-full max-w-sm rounded-xl bg-panel border border-line px-4 py-2.5 text-sm outline-none"
      />

      {error && <p className="text-sm text-red-300 mb-4">{error}</p>}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((d) => {
          const Icon = ICONS[d.modality] || FileText;
          return (
            <article key={d.id} className="rounded-2xl border border-line p-4 bg-white/[0.02]">
              <div className="flex items-start justify-between gap-3">
                <div className="h-10 w-10 rounded-xl bg-lime/10 text-lime grid place-items-center">
                  <Icon size={18} />
                </div>
                <button
                  className="text-mute hover:text-red-300"
                  onClick={async () => {
                    await api(`/documents/${d.id}`, { method: "DELETE" });
                    load();
                  }}
                >
                  <Trash2 size={15} />
                </button>
              </div>
              <h3 className="mt-3 text-sm font-medium truncate" title={d.filename}>
                {d.filename}
              </h3>
              <p className="text-[11px] text-mute mt-1">
                {d.modality} · {d.source} · {bytes(d.size_bytes)} · {d.chunk_count} chunks
              </p>
            </article>
          );
        })}
      </div>
      {filtered.length === 0 && <p className="text-sm text-mute">No files yet. Upload or sync a connector.</p>}
    </div>
  );
}
