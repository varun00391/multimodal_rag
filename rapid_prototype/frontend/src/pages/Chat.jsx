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
    <div className="h-screen flex">
      <aside className="w-64 border-r border-line p-4 hidden xl:flex flex-col">
        <button
          onClick={() => {
            setActiveId(null);
            setMessages([]);
          }}
          className="mb-4 flex items-center justify-center gap-2 rounded-xl bg-lime text-ink text-sm font-semibold py-2"
        >
          <Plus size={15} /> New question
        </button>
        <div className="text-[11px] uppercase tracking-wider text-mute mb-2">History</div>
        <div className="overflow-y-auto space-y-1 flex-1">
          {convos.map((c) => (
            <div key={c.id} className="group flex items-center gap-1">
              <button
                onClick={() => openConvo(c.id)}
                className={`flex-1 text-left text-sm px-3 py-2 rounded-lg truncate ${
                  activeId === c.id ? "bg-white/10" : "hover:bg-white/5 text-mute"
                }`}
              >
                {c.title}
              </button>
              <button
                className="opacity-0 group-hover:opacity-100 p-1 text-mute hover:text-red-300"
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
        <header className="border-b border-line px-6 py-4 flex flex-wrap items-center gap-3">
          <div>
            <h1 className="font-serif text-2xl">Ask Nexus</h1>
            <p className="text-xs text-mute">Grounded answers from your files and connectors</p>
          </div>
          <div className="ml-auto flex gap-2">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="bg-panel border border-line rounded-lg text-xs px-3 py-2"
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
              className="bg-panel border border-line rounded-lg text-xs px-3 py-2"
            >
              {FILTERS.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>
        </header>

        <div ref={scroller} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {messages.length === 0 && (
            <Empty
              onPick={(s) => {
                setInput(s);
              }}
            />
          )}
          {messages.map((m, i) => (
            <div key={i} className={`max-w-3xl ${m.role === "user" ? "ml-auto" : ""}`}>
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                  m.role === "user" ? "bg-lime text-ink" : "bg-white/5 border border-line"
                }`}
              >
                {m.content}
              </div>
              {m.role === "assistant" && (
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-mute">
                  <span>{m.model}</span>
                  <span>{m.latency_ms} ms</span>
                  <span>{(m.tokens_in || 0) + (m.tokens_out || 0)} tokens</span>
                  <span>${Number(m.cost_usd || 0).toFixed(5)}</span>
                </div>
              )}
              {m.sources?.length > 0 && (
                <div className="mt-3 grid sm:grid-cols-2 gap-2">
                  {m.sources.slice(0, 4).map((s, idx) => (
                    <div key={idx} className="rounded-xl border border-line p-3 text-xs">
                      <div className="text-lime mb-1">
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
          {error && <p className="text-sm text-red-300">{error}</p>}
        </div>

        <form onSubmit={send} className="p-4 border-t border-line">
          <div className="max-w-3xl mx-auto flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a PDF, screenshot, call recording, or email…"
              className="flex-1 rounded-2xl bg-panel border border-line px-4 py-3 text-sm outline-none focus:border-lime/50"
            />
            <button className="rounded-2xl bg-lime text-ink px-4 grid place-items-center">
              <Send size={16} />
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
    <div className="max-w-2xl mx-auto text-center pt-16">
      <div className="mx-auto h-12 w-12 rounded-2xl bg-lime/15 text-lime grid place-items-center mb-4">
        <Sparkles size={20} />
      </div>
      <h2 className="font-serif text-4xl">A single question across every modality.</h2>
      <p className="text-mute mt-3 text-sm">
        Retrieval runs over uploads and synced connectors, then returns an answer with file-level citations.
      </p>
      <div className="mt-8 grid gap-2">
        {samples.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            className="rounded-xl border border-line px-4 py-3 text-sm text-left text-mute hover:border-lime/40 hover:text-cream"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
