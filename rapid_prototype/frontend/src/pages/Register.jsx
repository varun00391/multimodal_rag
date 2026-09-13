import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(name, email, password);
      navigate("/app/chat");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen mesh relative">
      <div className="grain absolute inset-0" />
      <div className="relative min-h-screen grid place-items-center p-6">
        <form onSubmit={onSubmit} className="glass w-full max-w-md rounded-3xl p-8">
          <div className="flex items-center gap-3 mb-8">
            <div className="h-9 w-9 rounded-xl bg-lime text-ink grid place-items-center font-serif text-xl">N</div>
            <span className="text-sm tracking-[0.24em] uppercase text-mute">Nexus</span>
          </div>
          <h1 className="font-serif text-4xl mb-2">Create your vault</h1>
          <p className="text-sm text-mute mb-8">Start with uploads. Add Drive, Gmail, and Outlook when you are ready.</p>

          <label className="block text-xs text-mute mb-1.5">Full name</label>
          <input className="input mb-4" value={name} onChange={(e) => setName(e.target.value)} required />
          <label className="block text-xs text-mute mb-1.5">Work email</label>
          <input className="input mb-4" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <label className="block text-xs text-mute mb-1.5">Password</label>
          <input className="input mb-5" type="password" minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} required />

          {error && <p className="text-sm text-red-300 mb-4">{error}</p>}

          <button disabled={busy} className="w-full rounded-xl bg-lime text-ink font-semibold py-3 text-sm disabled:opacity-60">
            {busy ? "Creating…" : "Create account"}
          </button>
          <p className="mt-6 text-sm text-mute">
            Already have access? <Link to="/login" className="text-cream hover:text-lime">Sign in</Link>
          </p>
        </form>
      </div>
      <style>{`
        .input { width:100%; border-radius:0.75rem; background:rgba(0,0,0,.3); border:1px solid rgba(255,255,255,.08); padding:.75rem 1rem; font-size:.875rem; outline:none; }
        .input:focus { border-color: rgba(215,255,60,.6); }
      `}</style>
    </div>
  );
}
