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

const COLORS = ["#6D5EF7", "#111110", "#A39BFF", "#73726C", "#C9C6BF"];

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

  if (error) return <div className="p-8 text-rose-700">{error}</div>;
  if (!data) return <div className="p-8 text-mute">Loading telemetry…</div>;

  const k = data.kpis;
  const tooltip = { background: "#fff", border: "1px solid rgba(17,17,16,0.08)", borderRadius: 16, fontSize: 12 };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <p className="kicker mb-2">Telemetry</p>
        <h1 className="font-serif text-4xl tracking-tight">Usage</h1>
        <p className="text-sm text-mute mt-2 font-light">Questions, tokens, latency, spend, and model mix for this workspace.</p>
      </div>

      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <Kpi label="Questions asked" value={k.questions.toLocaleString()} />
        <Kpi label="Tokens used" value={k.tokens.toLocaleString()} hint={`${k.tokens_in.toLocaleString()} in · ${k.tokens_out.toLocaleString()} out`} />
        <Kpi label="Avg latency" value={`${k.avg_latency_ms} ms`} />
        <Kpi label="Total cost" value={money(k.total_cost_usd)} hint={`${k.documents} files · ${k.conversations} threads`} />
      </div>

      <div className="grid lg:grid-cols-5 gap-3">
        <section className="lg:col-span-3 card p-5">
          <h2 className="text-sm font-medium mb-4">Queries over 28 days</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.usage_series}>
                <defs>
                  <linearGradient id="q" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6D5EF7" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#6D5EF7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(17,17,16,0.06)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#73726C", fontSize: 11 }} tickFormatter={(d) => d.slice(5)} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#73726C", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltip} />
                <Area type="monotone" dataKey="queries" stroke="#6D5EF7" strokeWidth={2} fill="url(#q)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="lg:col-span-2 card p-5">
          <h2 className="text-sm font-medium mb-4">Model distribution</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data.model_distribution} dataKey="queries" nameKey="model" innerRadius={56} outerRadius={86} paddingAngle={4} stroke="none">
                  {data.model_distribution.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltip} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <section className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-line text-sm font-medium">How much each model is used</div>
        <table className="w-full text-sm">
          <thead className="text-mute text-[11px] uppercase tracking-[0.14em]">
            <tr>
              <th className="text-left px-5 py-3 font-medium">Model</th>
              <th className="text-right px-5 py-3 font-medium">Queries</th>
              <th className="text-right px-5 py-3 font-medium">Tokens</th>
              <th className="text-right px-5 py-3 font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {data.model_distribution.map((m) => (
              <tr key={m.model} className="border-t border-line">
                <td className="px-5 py-3">{m.model}</td>
                <td className="px-5 py-3 text-right tabular">{m.queries}</td>
                <td className="px-5 py-3 text-right tabular">{m.tokens.toLocaleString()}</td>
                <td className="px-5 py-3 text-right tabular">{money(m.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="grid lg:grid-cols-2 gap-3">
        <section className="card p-5">
          <h2 className="text-sm font-medium mb-4">Recent questions</h2>
          <ul className="space-y-4">
            {data.recent_questions.map((q) => (
              <li key={q.id} className="text-sm border-b border-line last:border-0 pb-4 last:pb-0">
                <div>{q.question}</div>
                <div className="text-[11px] text-mute mt-1">
                  {q.title} · {q.created_at ? new Date(q.created_at).toLocaleString() : ""}
                </div>
              </li>
            ))}
            {data.recent_questions.length === 0 && <li className="text-sm text-mute">No questions yet.</li>}
          </ul>
        </section>
        <section className="card p-5">
          <h2 className="text-sm font-medium mb-4">Library mix</h2>
          <ul className="space-y-3">
            {data.modality_breakdown.map((m) => (
              <li key={m.modality} className="flex justify-between text-sm">
                <span className="capitalize">{m.modality}</span>
                <span className="text-mute tabular">{m.count}</span>
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
    <div className="card p-5">
      <div className="kicker">{label}</div>
      <div className="font-serif text-[2rem] mt-3 tracking-tight tabular">{value}</div>
      {hint && <div className="text-[11px] text-mute mt-2">{hint}</div>}
    </div>
  );
}
