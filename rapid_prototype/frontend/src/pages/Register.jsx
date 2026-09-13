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
        <form onSubmit={onSubmit} className="glass w-full max-w-[420px] rounded-[28px] p-8 sm:p-10">
          <div className="flex items-center gap-3 mb-8">
            <div className="h-9 w-9 rounded-xl bg-cream text-ink grid place-items-center font-serif text-lg italic">N</div>
            <span className="kicker">Nexus</span>
          </div>
          <h1 className="font-serif text-[2.6rem] leading-none tracking-tight mb-3">Create your vault</h1>
          <p className="text-sm text-mute mb-8 font-light">Start with uploads. Connect Drive, Gmail, and Outlook when you are ready.</p>

          <label className="block text-[11px] text-mute mb-1.5">Full name</label>
          <input className="field mb-4" value={name} onChange={(e) => setName(e.target.value)} required />
          <label className="block text-[11px] text-mute mb-1.5">Work email</label>
          <input className="field mb-4" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <label className="block text-[11px] text-mute mb-1.5">Password</label>
          <input className="field mb-5" type="password" minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} required />

          {error && <p className="text-sm text-rose-700 mb-4">{error}</p>}

          <button disabled={busy} className="btn-primary w-full py-3.5">
            {busy ? "Creating…" : "Create account"}
          </button>
          <p className="mt-6 text-sm text-mute">
            Already have access? <Link to="/login" className="text-cream hover:text-mist">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
