import { useEffect, useRef, useState } from "react";
import { Plus, Send, Sparkles, Trash2 } from "lucide-react";
import { api } from "../api/client";

const FILTERS = [
  { id: "all", label: "All sources" },
  { id: "upload", label: "Uploads" },
  { id: "gdrive", label: "Drive" },
  { id: "gmail", label: "Gmail" },
  { id: "outlook", label: "Outlook" },
  { id: "slack", label: "Slack" },
  { id: "notion", label: "Notion" },
];

export default function Chat() {
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("gpt-4o-mini");
  const [source, setSource] = useState("all");
  const [convos, setConvos] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const scroller = useRef(null);

  async function loadConvos() {
    const rows = await api("/conversations");
    setConvos(rows);
  }

  async function openConvo(id) {
    setActiveId(id);
    const data = await api(`/conversations/${id}`);
    setMessages(data.messages || []);
  }

  useEffect(() => {
    api("/models").then((d) => setModels(d.models || []));
    loadConvos().catch(() => {});
  }, []);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(e) {
    e.preventDefault();
    if (!input.trim() || busy) return;
    const text = input.trim();
    setInput("");
    setBusy(true);
    setError("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    try {
      const res = await api("/chat", {
        method: "POST",
        body: { message: text, conversation_id: activeId, model, source_filter: source },
      });
      setActiveId(res.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          model: res.model,
          latency_ms: res.latency_ms,
          tokens_in: res.tokens_in,
          tokens_out: res.tokens_out,
          cost_usd: res.cost_usd,
        },
      ]);
      loadConvos();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-[calc(100vh-1.5rem)] flex">
      <aside className="w-64 border-r border-line p-4 hidden xl:flex flex-col bg-panel/40">
        <button
          onClick={() => {
            setActiveId(null);
            setMessages([]);
          }}
          className="btn-primary mb-5 w-full"
        >
          <Plus size={15} /> New question
        </button>
        <div className="kicker mb-3 px-1">History</div>
        <div className="overflow-y-auto space-y-0.5 flex-1">
          {convos.map((c) => (
            <div key={c.id} className="group flex items-center gap-1">
              <button
                onClick={() => openConvo(c.id)}
                className={`flex-1 text-left text-[13px] px-3 py-2 rounded-full truncate ${
                  activeId === c.id ? "bg-ink text-cream" : "hover:bg-ink text-mute"
                }`}
              >
                {c.title}
              </button>
              <button
                className="opacity-0 group-hover:opacity-100 p-1 text-mute hover:text-rose-700"
                onClick={async () => {
                  await api(`/conversations/${c.id}`, { method: "DELETE" });
                  if (activeId === c.id) {
                    setActiveId(null);
                    setMessages([]);
                  }
                  loadConvos();
                }}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      <section className="flex-1 flex flex-col min-w-0">
        <header className="px-7 py-5 flex flex-wrap items-center gap-3">
          <div>
            <p className="kicker mb-1">Workspace</p>
            <h1 className="font-serif text-[1.85rem] tracking-tight leading-none">Ask Nexus</h1>
          </div>
          <div className="ml-auto flex gap-2">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="bg-ink border border-line rounded-full text-xs px-3 py-2"
            >
              {(models.length ? models : [model]).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="bg-ink border border-line rounded-full text-xs px-3 py-2"
            >
              {FILTERS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
        </header>

        <div ref={scroller} className="flex-1 overflow-y-auto px-7 py-2 space-y-5">
          {messages.length === 0 && <Empty onPick={setInput} />}
          {messages.map((m, i) => (
            <div key={i} className={`max-w-3xl ${m.role === "user" ? "ml-auto" : ""}`}>
              <div
                className={`px-4 py-3 text-[14.5px] leading-relaxed whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-cream text-ink rounded-[22px] rounded-br-md"
                    : "bg-ink border border-line rounded-[22px] rounded-bl-md"
                }`}
              >
                {m.content}
              </div>
              {m.role === "assistant" && (
                <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-mute tabular">
                  <span>{m.model}</span>
                  <span>{m.latency_ms} ms</span>
                  <span>{(m.tokens_in || 0) + (m.tokens_out || 0)} tokens</span>
                  <span>${Number(m.cost_usd || 0).toFixed(5)}</span>
                </div>
              )}
              {m.sources?.length > 0 && (
                <div className="mt-3 grid sm:grid-cols-2 gap-2">
                  {m.sources.slice(0, 4).map((s, idx) => (
                    <div key={idx} className="rounded-2xl border border-line bg-panel p-3 text-xs">
                      <div className="text-mist mb-1 font-medium">
                        {s.filename} · {s.modality}
                      </div>
                      <div className="text-mute line-clamp-3">{s.excerpt}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {busy && <p className="text-sm text-mute">Retrieving and composing…</p>}
          {error && <p className="text-sm text-rose-700">{error}</p>}
        </div>

        <form onSubmit={send} className="p-5">
          <div className="max-w-3xl mx-auto flex gap-2 items-end bg-ink border border-line rounded-[22px] p-2 pl-4">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a PDF, screenshot, call recording, or email…"
              className="flex-1 bg-transparent py-2.5 text-sm outline-none"
            />
            <button className="h-10 w-10 rounded-full bg-cream text-ink grid place-items-center shrink-0">
              <Send size={15} />
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function Empty({ onPick }) {
  const samples = [
    "What did the customer ask about in the call recording?",
    "Summarize the Q3 product strategy.",
    "What is our refund policy?",
  ];
  return (
    <div className="max-w-2xl mx-auto text-center pt-12 pb-8">
      <div className="mx-auto h-12 w-12 rounded-full bg-mist/10 text-mist grid place-items-center mb-5">
        <Sparkles size={18} />
      </div>
      <h2 className="font-serif text-[2.15rem] leading-[1.08] tracking-tight">One question. Every modality.</h2>
      <p className="text-mute mt-4 text-sm font-light max-w-md mx-auto">
        Retrieval runs over uploads and synced connectors, then returns an answer with file-level citations.
      </p>
      <div className="mt-8 grid gap-2">
        {samples.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="rounded-full border border-line bg-panel px-5 py-3 text-sm text-left text-mute hover:border-mist/40 hover:text-cream"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
