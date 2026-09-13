import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("demo@nexus.ai");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      navigate("/app/chat");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen mesh relative overflow-hidden">
      <div className="grain absolute inset-0" />
      <div className="relative grid lg:grid-cols-[1.15fr_0.85fr] min-h-screen">
        <section className="hidden lg:flex flex-col justify-between p-12 xl:px-20 xl:py-14">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-cream text-ink grid place-items-center font-serif text-xl italic">
              N
            </div>
            <span className="kicker">Nexus</span>
          </div>

          <div>
            <p className="kicker mb-6">Multimodal knowledge OS</p>
            <h1 className="font-serif text-[4.6rem] xl:text-[5.4rem] leading-[0.92] tracking-[-0.04em] max-w-xl">
              Ask every file.
              <br />
              <span className="italic text-mist">Hear every source.</span>
            </h1>
            <p className="mt-7 max-w-md text-mute text-[17px] leading-relaxed font-light">
              Retrieval across PDFs, images, video, mail, and drives — with citations, latency, and cost you can actually see.
            </p>

            <dl className="mt-14 grid grid-cols-3 gap-6 max-w-lg">
              {[
                ["01", "Ingest", "Any modality"],
                ["02", "Retrieve", "Cited answers"],
                ["03", "Measure", "Tokens & cost"],
              ].map(([n, t, d]) => (
                <div key={n} className="border-t border-line pt-4">
                  <div className="text-[11px] text-mist tabular mb-2">{n}</div>
                  <div className="text-sm font-medium">{t}</div>
                  <div className="text-xs text-mute mt-1">{d}</div>
                </div>
              ))}
            </dl>
          </div>

          <p className="text-xs text-mute">Private workspace · Simulated connectors · Extractive or LLM</p>
        </section>

        <section className="flex items-center justify-center p-6 sm:p-10">
          <form onSubmit={onSubmit} className="glass w-full max-w-[420px] rounded-[28px] p-8 sm:p-10">
            <p className="kicker mb-3">Sign in</p>
            <h2 className="font-serif text-[2.6rem] leading-none tracking-tight mb-3">Welcome back</h2>
            <p className="text-sm text-mute mb-8 font-light">Continue to your knowledge workspace.</p>

            <label className="block text-[11px] text-mute mb-1.5">Email</label>
            <input className="field mb-4" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
            <label className="block text-[11px] text-mute mb-1.5">Password</label>
            <input className="field mb-5" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />

            {error && <p className="text-sm text-rose-700 mb-4">{error}</p>}

            <button disabled={busy} className="btn-primary w-full py-3.5">
              {busy ? "Signing in…" : "Enter workspace"}
            </button>

            <div className="mt-5 rounded-2xl bg-ink px-4 py-3 text-xs text-mute">
              Demo <span className="text-cream">demo@nexus.ai</span>
              <span className="mx-2 text-mute">·</span>
              <span className="text-cream">demo1234</span>
            </div>

            <p className="mt-6 text-sm text-mute">
              New here?{" "}
              <Link to="/register" className="text-cream inline-flex items-center gap-1 hover:text-mist">
                Create an account <ArrowUpRight size={14} />
              </Link>
            </p>
          </form>
        </section>
      </div>
    </div>
  );
}
