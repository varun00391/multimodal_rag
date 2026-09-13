import { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext.jsx";

export default function Settings() {
  const { user, refresh } = useAuth();
  const settings = user?.settings || {};
  const [name, setName] = useState(user?.name || "");
  const [model, setModel] = useState(settings.default_model || "gpt-4o-mini");
  const [apiKey, setApiKey] = useState(settings.openai_api_key || "");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      await api("/auth/me", {
        method: "PATCH",
        body: { settings: { name, default_model: model, openai_api_key: apiKey } },
      });
      await refresh();
      setMsg("Saved.");
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-8 max-w-xl">
      <h1 className="font-serif text-4xl mb-2">Settings</h1>
      <p className="text-sm text-mute mb-8">Workspace defaults for generation. Leave the key empty to use extractive RAG.</p>
      <form onSubmit={save} className="space-y-5">
        <div>
          <label className="text-xs text-mute">Display name</label>
          <input className="mt-1 w-full rounded-xl bg-panel border border-line px-4 py-3 text-sm" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="text-xs text-mute">Default model</label>
          <select className="mt-1 w-full rounded-xl bg-panel border border-line px-4 py-3 text-sm" value={model} onChange={(e) => setModel(e.target.value)}>
            <option>gpt-4o-mini</option>
            <option>gpt-4o</option>
            <option>claude-3.5-sonnet</option>
            <option>gemini-2.0-flash</option>
            <option>nexus-extractive</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-mute">OpenAI API key (optional)</label>
          <input
            className="mt-1 w-full rounded-xl bg-panel border border-line px-4 py-3 text-sm"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-…"
          />
          <p className="text-[11px] text-mute mt-2">
            Stored on this user record for the prototype. Without a key, Nexus still retrieves and answers extractively.
          </p>
        </div>
        <button disabled={busy} className="rounded-xl bg-lime text-ink font-semibold px-4 py-2.5 text-sm">
          {busy ? "Saving…" : "Save settings"}
        </button>
        {msg && <p className="text-sm text-mute">{msg}</p>}
      </form>
    </div>
  );
}
