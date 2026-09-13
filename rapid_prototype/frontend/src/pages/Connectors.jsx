import { useEffect, useState } from "react";
import { RefreshCw, Unplug } from "lucide-react";
import { api } from "../api/client";

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
      <p className="kicker mb-2">Integrations</p>
      <h1 className="font-serif text-4xl tracking-tight">Connectors</h1>
      <p className="text-sm text-mute mt-2 max-w-xl font-light">
        Pull knowledge from mail, drives, chat, and wikis. This prototype simulates OAuth and syncs a sample corpus you can query immediately.
      </p>
      {error && <p className="text-sm text-rose-700 mt-4">{error}</p>}

      <div className="grid md:grid-cols-2 gap-3 mt-8">
        {rows.map((c) => {
          const connected = c.status === "connected";
          return (
            <article key={c.provider} className="card p-6">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-[17px] font-medium tracking-tight">{c.name}</h2>
                  <p className="text-sm text-mute mt-1.5 font-light leading-relaxed">{c.description}</p>
                </div>
                <span
                  className={`text-[10px] uppercase tracking-[0.14em] px-2.5 py-1 rounded-full ${
                    connected ? "bg-mist/10 text-mist" : "bg-ink text-mute"
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
                    className="btn-primary"
                  >
                    {busy === c.provider + "/connect" ? "Connecting…" : "Connect"}
                  </button>
                ) : (
                  <>
                    <button
                      disabled={!!busy}
                      onClick={() => act(c.provider, "/sync")}
                      className="btn-primary"
                    >
                      <RefreshCw size={14} /> {busy === c.provider + "/sync" ? "Syncing…" : "Sync now"}
                    </button>
                    <button
                      disabled={!!busy}
                      onClick={() => act(c.provider, "/disconnect")}
                      className="btn-ghost"
                    >
                      <Unplug size={14} /> Disconnect
                    </button>
                  </>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
