import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, money, num } from "../api";
import { Loading, Note, Stat, useLoad } from "../components/bits";

const MODES = [
  ["cheapest", "💰 Cheapest", "Lowest total cost: buying, ordering, storage and transport."],
  ["greenest", "🌱 Greenest", "Fewest truck emissions while meeting the same demand. May cost a little more."],
];

function Review({ plan, onDone }) {
  const [name, setName] = useState("");
  const [err, setErr] = useState(null);
  if (plan.reviewed_by) return <Note kind="ok">✔ Checked by {plan.reviewed_by} on {plan.reviewed_at}.</Note>;
  const submit = async (e) => {
    e.preventDefault();
    try { await api("/api/plan/review", "POST", { name }); onDone(); } catch (e2) { setErr(e2.message); }
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <div><label className="label" htmlFor="rev">Your name</label><input id="rev" className="input w-56" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Store manager" /></div>
      <button className="btn" disabled={name.trim().length < 2}>I have checked this plan</button>
      {err && <p className="w-full text-sm text-red-700">{err}</p>}
    </form>
  );
}

export default function Plan() {
  const saved = useLoad("/api/plan");
  const [plan, setPlan] = useState(null);
  const [mode, setMode] = useState("cheapest");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [itemId, setItemId] = useState(null);

  useEffect(() => { if (saved.data) { setPlan(saved.data); setMode(saved.data.mode); } }, [saved.data]);

  const create = async () => {
    setBusy(true); setErr(null);
    try { setPlan(await api("/api/plan", "POST", { mode })); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  };
  const refresh = async () => setPlan(await api("/api/plan"));

  const names = plan?.item_names || {};
  const chartItem = itemId ?? plan?.plan.items[0]?.item_id;
  const stockChart = useMemo(() => {
    if (!plan) return [];
    const p = plan.plan.items.find((x) => x.item_id === chartItem);
    const b = plan.simple_rule.items.find((x) => x.item_id === chartItem);
    return (p?.weekly || []).map((w, i) => ({ week: `W${w.week}`, plan: w.stock, rule: b?.weekly[i]?.stock, safety: p.safety_stock }));
  }, [plan, chartItem]);

  if (saved.loading) return <Loading />;
  const p = plan?.plan.totals, b = plan?.simple_rule.totals;

  return (
    <div className="space-y-6">
      <div><h1>Order Plan</h1><p className="mt-1 text-ink-600">Pick what matters most and GIO will plan your orders for the next weeks.</p></div>

      <div className="card">
        <div className="grid gap-3 sm:grid-cols-2">
          {MODES.map(([k, title, text]) => (
            <label key={k} className={`cursor-pointer rounded-lg border p-4 ${mode === k ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600" : "border-ink-200 hover:border-ink-400"}`}>
              <input type="radio" name="mode" className="sr-only" checked={mode === k} onChange={() => setMode(k)} />
              <p className="font-semibold">{title}</p><p className="mt-1 text-sm text-ink-600">{text}</p>
            </label>
          ))}
        </div>
        <button className="btn mt-4" onClick={create} disabled={busy}>
          {busy && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
          {busy ? "Working it out… (up to 20 s)" : plan ? "Make a new plan" : "Create plan"}
        </button>
        {err && <Note kind="error" className="mt-3">{err}</Note>}
      </div>

      {plan && (
        <>
          {plan.note && <Note>{plan.note}</Note>}
          {plan.summary.warnings.map((w, i) => <Note key={i} kind="warn">{w}</Note>)}
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Total cost" value={money(p.total_cost)} sub={`${money(Math.abs(b.total_cost - p.total_cost))} ${b.total_cost >= p.total_cost ? "less" : "more"} than the simple rule`} good={b.total_cost >= p.total_cost} />
            <Stat label="Truck CO₂" value={`${num(p.co2_kg)} kg`} sub={`${num(Math.abs(b.co2_kg - p.co2_kg))} kg ${b.co2_kg >= p.co2_kg ? "less" : "more"} than the simple rule`} good={b.co2_kg >= p.co2_kg} />
            <Stat label="Trucks needed" value={p.small_trucks + p.large_trucks} sub={`${p.small_trucks} small + ${p.large_trucks} large (simple rule: ${b.small_trucks + b.large_trucks})`} good={p.small_trucks + p.large_trucks <= b.small_trucks + b.large_trucks} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="card">
              <h2>Orders to place</h2>
              <div className="mt-3 max-h-96 overflow-auto">
                <table className="tbl">
                  <thead><tr><th>Week</th><th>Item</th><th className="num">Quantity</th><th>Trucks</th></tr></thead>
                  <tbody>{plan.plan.orders.map((o, i) => (
                    <tr key={i}><td>{o.week}</td><td>{names[o.item_id]}</td><td className="num">{num(o.qty)}</td>
                      <td className="text-sm">{[o.large && `${o.large} large`, o.small && `${o.small} small`].filter(Boolean).join(" + ")}</td></tr>))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="card">
              <h2>Plan vs simple rule</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={[
                  { name: "Transport (₹)", Plan: p.transport, Rule: b.transport },
                  { name: "Storage (₹)", Plan: p.storage, Rule: b.storage },
                  { name: "Ordering (₹)", Plan: p.ordering, Rule: b.ordering },
                ]} margin={{ left: 10, top: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={(v) => num(v)} tick={{ fontSize: 11 }} width={70} />
                  <Tooltip formatter={(v) => money(v)} />
                  <Legend />
                  <Bar dataKey="Rule" name="Simple rule" fill="#94a3b8" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Plan" name="This plan" fill="#047857" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-xs text-ink-500">Simple rule = order the EOQ amount whenever stock drops to the reorder level. Purchase cost is almost the same in both, so it is not shown.</p>
            </div>
          </div>

          <div className="card">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2>Stock over the coming weeks</h2>
              <select className="input w-56" value={chartItem} onChange={(e) => setItemId(Number(e.target.value))} aria-label="Item">
                {plan.plan.items.map((x) => <option key={x.item_id} value={x.item_id}>{x.name}</option>)}
              </select>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={stockChart} margin={{ top: 10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" />
                <YAxis tickFormatter={(v) => num(v)} width={60} />
                <Tooltip formatter={(v) => num(v)} />
                <Legend />
                <Line dataKey="plan" name="This plan" stroke="#047857" strokeWidth={2.5} dot={false} />
                <Line dataKey="rule" name="Simple rule" stroke="#94a3b8" strokeWidth={2} dot={false} />
                <Line dataKey="safety" name="Safety stock" stroke="#d97706" strokeDasharray="5 5" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card space-y-4">
            <h2>Check & download</h2>
            <p className="text-sm text-ink-600">GIO does not place orders. A person should check the plan (quantities, supplier availability) before ordering.</p>
            <Review plan={plan} onDone={refresh} />
            <a className="btn-light" href="/api/plan.csv">Download plan (CSV)</a>
          </div>
        </>
      )}
    </div>
  );
}
