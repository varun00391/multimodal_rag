import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";

const COLORS = ["#d7ff3c", "#9bb7ff", "#ff8c5a", "#5eead4", "#f5d0fe"];

function money(n) {
  return `$${Number(n || 0).toFixed(4)}`;
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="p-8 text-red-300">{error}</div>;
  if (!data) return <div className="p-8 text-mute">Loading telemetry…</div>;

  const k = data.kpis;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="font-serif text-4xl">Usage</h1>
        <p className="text-sm text-mute mt-1">Questions, tokens, latency, spend, and model mix for this workspace.</p>
      </div>

      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Kpi label="Questions asked" value={k.questions.toLocaleString()} />
        <Kpi label="Tokens used" value={k.tokens.toLocaleString()} hint={`${k.tokens_in.toLocaleString()} in · ${k.tokens_out.toLocaleString()} out`} />
        <Kpi label="Avg latency" value={`${k.avg_latency_ms} ms`} />
        <Kpi label="Total cost" value={money(k.total_cost_usd)} hint={`${k.documents} files · ${k.conversations} threads`} />
      </div>

      <div className="grid lg:grid-cols-5 gap-4">
        <section className="lg:col-span-3 rounded-3xl border border-line p-5 bg-white/[0.02]">
          <h2 className="text-sm font-medium mb-4">Queries over 28 days</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.usage_series}>
                <defs>
                  <linearGradient id="q" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#d7ff3c" stopOpacity={0.7} />
                    <stop offset="100%" stopColor="#d7ff3c" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#8b93a7", fontSize: 11 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fill: "#8b93a7", fontSize: 11 }} />
                <Tooltip contentStyle={{ background: "#10131a", border: "1px solid rgba(255,255,255,0.08)" }} />
                <Area type="monotone" dataKey="queries" stroke="#d7ff3c" fill="url(#q)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="lg:col-span-2 rounded-3xl border border-line p-5 bg-white/[0.02]">
          <h2 className="text-sm font-medium mb-4">Model distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data.model_distribution} dataKey="queries" nameKey="model" innerRadius={52} outerRadius={84} paddingAngle={3}>
                  {data.model_distribution.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: "#10131a", border: "1px solid rgba(255,255,255,0.08)" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <section className="rounded-3xl border border-line overflow-hidden">
        <div className="px-5 py-4 border-b border-line text-sm font-medium">How much each model is used</div>
        <table className="w-full text-sm">
          <thead className="text-mute text-xs uppercase tracking-wider">
            <tr>
              <th className="text-left px-5 py-3">Model</th>
              <th className="text-right px-5 py-3">Queries</th>
              <th className="text-right px-5 py-3">Tokens</th>
              <th className="text-right px-5 py-3">Cost</th>
            </tr>
          </thead>
          <tbody>
            {data.model_distribution.map((m) => (
              <tr key={m.model} className="border-t border-line">
                <td className="px-5 py-3">{m.model}</td>
                <td className="px-5 py-3 text-right">{m.queries}</td>
                <td className="px-5 py-3 text-right">{m.tokens.toLocaleString()}</td>
                <td className="px-5 py-3 text-right">{money(m.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="grid lg:grid-cols-2 gap-4">
        <section className="rounded-3xl border border-line p-5">
          <h2 className="text-sm font-medium mb-4">Recent questions</h2>
          <ul className="space-y-3">
            {data.recent_questions.map((q) => (
              <li key={q.id} className="text-sm">
                <div>{q.question}</div>
                <div className="text-[11px] text-mute mt-1">
                  {q.title} · {q.created_at ? new Date(q.created_at).toLocaleString() : ""}
                </div>
              </li>
            ))}
            {data.recent_questions.length === 0 && <li className="text-sm text-mute">No questions yet.</li>}
          </ul>
        </section>
        <section className="rounded-3xl border border-line p-5">
          <h2 className="text-sm font-medium mb-4">Library mix</h2>
          <ul className="space-y-3">
            {data.modality_breakdown.map((m) => (
              <li key={m.modality} className="flex justify-between text-sm">
                <span className="capitalize">{m.modality}</span>
                <span className="text-mute">{m.count}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

function Kpi({ label, value, hint }) {
  return (
    <div className="rounded-3xl border border-line p-5 bg-white/[0.02]">
      <div className="text-xs uppercase tracking-wider text-mute">{label}</div>
      <div className="font-serif text-3xl mt-2">{value}</div>
      {hint && <div className="text-[11px] text-mute mt-2">{hint}</div>}
    </div>
  );
}
