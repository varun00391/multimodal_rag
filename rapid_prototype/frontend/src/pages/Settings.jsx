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
      <p className="kicker mb-2">Workspace</p>
      <h1 className="font-serif text-4xl tracking-tight mb-2">Settings</h1>
      <p className="text-sm text-mute mb-8 font-light">Defaults for generation. Leave the key empty to use extractive RAG.</p>
      <form onSubmit={save} className="card p-6 space-y-5">
        <div>
          <label className="text-[11px] text-mute">Display name</label>
          <input className="field mt-1.5" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="text-[11px] text-mute">Default model</label>
          <select className="field mt-1.5" value={model} onChange={(e) => setModel(e.target.value)}>
            <option>gpt-4o-mini</option>
            <option>gpt-4o</option>
            <option>claude-3.5-sonnet</option>
            <option>gemini-2.0-flash</option>
            <option>nexus-extractive</option>
          </select>
        </div>
        <div>
          <label className="text-[11px] text-mute">OpenAI API key (optional)</label>
          <input
            className="field mt-1.5"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-…"
          />
          <p className="text-[11px] text-mute mt-2 font-light">
            Stored on this user record for the prototype. Without a key, Nexus still retrieves and answers extractively.
          </p>
        </div>
        <button disabled={busy} className="btn-primary">
          {busy ? "Saving…" : "Save settings"}
        </button>
        {msg && <p className="text-sm text-mute">{msg}</p>}
      </form>
    </div>
  );
}
