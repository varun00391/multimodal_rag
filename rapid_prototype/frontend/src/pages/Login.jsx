import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowUpRight, FileText, Image, Mail, Video } from "lucide-react";
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
      <div className="relative grid lg:grid-cols-2 min-h-screen">
        <section className="hidden lg:flex flex-col justify-between p-12 xl:p-16">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-lime text-ink grid place-items-center font-serif text-2xl">
              N
            </div>
            <span className="text-sm tracking-[0.28em] uppercase text-mute">Nexus</span>
          </div>

          <div>
            <p className="text-lime text-xs tracking-[0.3em] uppercase mb-5">Multimodal knowledge OS</p>
            <h1 className="font-serif text-6xl xl:text-7xl leading-[0.95] max-w-xl">
              Ask every file.
              <span className="italic text-mist"> Hear every source.</span>
            </h1>
            <p className="mt-6 max-w-md text-mute text-lg">
              PDFs, images, video, mail, and drives — one retrieval layer with citations, cost, and latency you can actually see.
            </p>

            <div className="relative mt-14 h-64">
              <div className="orbit absolute left-16 top-6 h-52 w-52 rounded-full border border-white/10" />
              <Card className="float-a absolute left-0 top-8" icon={FileText} label="Q3 strategy.pdf" meta="12 pages · Drive" />
              <Card className="float-b absolute left-44 top-0" icon={Image} label="aisle-B12.jpg" meta="vision · warehouse" />
              <Card className="float-a absolute left-28 top-36" icon={Video} label="customer-call.mp4" meta="transcript ready" />
              <Card className="float-b absolute left-72 top-24" icon={Mail} label="Invoice HL-2044" meta="Gmail · due 30 Sep" />
            </div>
          </div>

          <div className="flex gap-10 text-xs text-mute">
            <span>Cited answers</span>
            <span>Connector sync</span>
            <span>Usage & cost telemetry</span>
          </div>
        </section>

        <section className="flex items-center justify-center p-6 sm:p-10">
          <form onSubmit={onSubmit} className="glass w-full max-w-md rounded-3xl p-8 shadow-glow">
            <p className="text-xs uppercase tracking-[0.25em] text-mute mb-3">Sign in</p>
            <h2 className="font-serif text-4xl mb-2">Welcome back</h2>
            <p className="text-sm text-mute mb-8">
              Use the demo workspace or your own account.
            </p>

            <label className="block text-xs text-mute mb-1.5">Email</label>
            <input
              className="w-full mb-4 rounded-xl bg-black/30 border border-line px-4 py-3 text-sm outline-none focus:border-lime/60"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
            />
            <label className="block text-xs text-mute mb-1.5">Password</label>
            <input
              className="w-full mb-5 rounded-xl bg-black/30 border border-line px-4 py-3 text-sm outline-none focus:border-lime/60"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
            />

            {error && <p className="text-sm text-red-300 mb-4">{error}</p>}

            <button
              disabled={busy}
              className="w-full rounded-xl bg-lime text-ink font-semibold py-3 text-sm hover:brightness-110 disabled:opacity-60"
            >
              {busy ? "Signing in…" : "Enter workspace"}
            </button>

            <div className="mt-5 rounded-xl border border-lime/20 bg-lime/5 px-4 py-3 text-xs text-mute">
              Demo: <span className="text-cream">demo@nexus.ai</span> / <span className="text-cream">demo1234</span>
            </div>

            <p className="mt-6 text-sm text-mute">
              New here?{" "}
              <Link to="/register" className="text-cream inline-flex items-center gap-1 hover:text-lime">
                Create an account <ArrowUpRight size={14} />
              </Link>
            </p>
          </form>
        </section>
      </div>
    </div>
  );
}

function Card({ className, icon: Icon, label, meta }) {
  return (
    <div className={`rounded-2xl border border-white/10 bg-black/40 backdrop-blur px-4 py-3 w-52 ${className}`}>
      <div className="flex items-center gap-2 text-lime mb-2">
        <Icon size={14} />
        <span className="text-[10px] uppercase tracking-wider">Source</span>
      </div>
      <div className="text-sm">{label}</div>
      <div className="text-[11px] text-mute mt-1">{meta}</div>
    </div>
  );
}
