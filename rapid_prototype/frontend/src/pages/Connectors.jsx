import { useEffect, useState } from "react";
import { RefreshCw, Unplug } from "lucide-react";
import { api } from "../api/client";

const ACCENTS = {
  gdrive: "from-sky-400/20 to-transparent",
  gmail: "from-rose-400/20 to-transparent",
  outlook: "from-indigo-400/20 to-transparent",
  onedrive: "from-blue-400/20 to-transparent",
  dropbox: "from-cyan-400/20 to-transparent",
  slack: "from-fuchsia-400/20 to-transparent",
  notion: "from-stone-300/20 to-transparent",
  sharepoint: "from-teal-400/20 to-transparent",
};

export default function Connectors() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setRows(await api("/connectors"));
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function act(provider, path) {
    setBusy(provider + path);
    setError("");
    try {
      await api(`/connectors/${provider}${path}`, { method: "POST", body: {} });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="font-serif text-4xl">Connectors</h1>
      <p className="text-sm text-mute mt-2 max-w-2xl">
        Pull knowledge from mail, drives, chat, and wikis. This prototype simulates OAuth and syncs realistic sample corpora you can query immediately.
      </p>
      {error && <p className="text-sm text-red-300 mt-4">{error}</p>}

      <div className="grid md:grid-cols-2 gap-4 mt-8">
        {rows.map((c) => {
          const connected = c.status === "connected";
          return (
            <article key={c.provider} className="relative overflow-hidden rounded-3xl border border-line p-5 bg-panel">
              <div className={`absolute inset-0 bg-gradient-to-br ${ACCENTS[c.provider] || "from-lime/10 to-transparent"}`} />
              <div className="relative">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold">{c.name}</h2>
                    <p className="text-sm text-mute mt-1">{c.description}</p>
                  </div>
                  <span
                    className={`text-[11px] uppercase tracking-wide px-2 py-1 rounded-full border ${
                      connected ? "border-lime/40 text-lime" : "border-line text-mute"
                    }`}
                  >
                    {c.status}
                  </span>
                </div>
                {connected && (
                  <p className="text-xs text-mute mt-4">
                    {c.account_email} · {c.items_synced} items
                    {c.last_synced_at ? ` · synced ${new Date(c.last_synced_at).toLocaleString()}` : ""}
                  </p>
                )}
                <div className="mt-5 flex flex-wrap gap-2">
                  {!connected ? (
                    <button
                      disabled={!!busy}
                      onClick={() => act(c.provider, "/connect")}
                      className="rounded-xl bg-lime text-ink text-sm font-semibold px-3 py-2"
                    >
                      {busy === c.provider + "/connect" ? "Connecting…" : "Connect"}
                    </button>
                  ) : (
                    <>
                      <button
                        disabled={!!busy}
                        onClick={() => act(c.provider, "/sync")}
                        className="rounded-xl bg-lime text-ink text-sm font-semibold px-3 py-2 inline-flex items-center gap-1.5"
                      >
                        <RefreshCw size={14} /> {busy === c.provider + "/sync" ? "Syncing…" : "Sync now"}
                      </button>
                      <button
                        disabled={!!busy}
                        onClick={() => act(c.provider, "/disconnect")}
                        className="rounded-xl border border-line text-sm px-3 py-2 inline-flex items-center gap-1.5"
                      >
                        <Unplug size={14} /> Disconnect
                      </button>
                    </>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
