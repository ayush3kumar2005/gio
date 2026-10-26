import { useEffect, useState } from "react";
import { api, money, num } from "../api";
import { Loading, Note, Status, useLoad } from "../components/bits";

const FIELDS = [
  ["name", "Item name", "text", "e.g. Steel sheets"],
  ["unit", "Unit", "text", "e.g. sheets, kg, boxes"],
  ["stock", "Current stock", "number", ""],
  ["weekly_demand", "Used per week", "number", ""],
  ["price", "Price per unit (₹)", "number", ""],
  ["order_cost", "Cost of placing one order (₹)", "number", "paperwork, handling"],
  ["weight_kg", "Weight of one unit (kg)", "number", ""],
  ["lead_time_weeks", "Delivery time (weeks)", "number", ""],
  ["distance_km", "Supplier distance (km)", "number", "use Delivery & CO₂ page to find it"],
];
const EMPTY = Object.fromEntries(FIELDS.map(([k]) => [k, ""]));

function ItemForm({ initial, onDone, onCancel }) {
  const [f, setF] = useState(initial || EMPTY);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const save = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    const body = Object.fromEntries(FIELDS.map(([k, , type]) => [k, type === "number" ? (f[k] === "" ? null : Number(f[k])) : f[k]]));
    try { await api(initial?.id ? `/api/items/${initial.id}` : "/api/items", initial?.id ? "PUT" : "POST", body); onDone(); }
    catch (e2) { setErr(e2.message); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={save} className="card">
      <h2>{initial?.id ? `Edit ${initial.name}` : "Add an item"}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {FIELDS.map(([k, label, type, hint]) => (
          <div key={k}>
            <label className="label" htmlFor={k}>{label}</label>
            <input id={k} required type={type} step="any" min={type === "number" ? 0 : undefined} className="input" placeholder={hint}
              value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
          </div>
        ))}
      </div>
      {err && <Note kind="error" className="mt-4">{err}</Note>}
      <div className="mt-4 flex gap-2">
        <button className="btn" disabled={busy}>{busy ? "Saving…" : "Save item"}</button>
        <button type="button" className="btn-light" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function SettingsBox() {
  const { data, loading } = useLoad("/api/settings");
  const [s, setS] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => { if (data) setS(data); }, [data]);
  if (loading || !s) return null;
  const fields = [
    ["plant_city", "Factory location", "text"], ["weeks", "Plan ahead (weeks)", "number"],
    ["fuel_price", "Diesel price (₹/litre)", "number"], ["holding_pct", "Storage cost (% of price per year)", "number"],
    ["demand_variation_pct", "Demand varies by about (%)", "number"], ["service_level_pct", "Avoid running out (% confidence)", "number"],
  ];
  const save = async (e) => {
    e.preventDefault();
    try {
      await api("/api/settings", "PUT", Object.fromEntries(Object.keys(s).map((k) => [k, typeof data[k] === "number" ? Number(s[k]) : s[k]])));
      setMsg(["ok", "Saved. Create a new plan to use the new settings."]);
    } catch (e2) { setMsg(["error", e2.message]); }
  };
  return (
    <details className="card">
      <summary className="cursor-pointer font-semibold">Settings</summary>
      <form onSubmit={save} className="mt-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map(([k, label, type]) => (
            <div key={k}><label className="label" htmlFor={`s-${k}`}>{label}</label>
              <input id={`s-${k}`} type={type} step="any" className="input" value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })} /></div>
          ))}
        </div>
        {msg && <Note kind={msg[0]} className="mt-4">{msg[1]}</Note>}
        <button className="btn mt-4">Save settings</button>
      </form>
    </details>
  );
}

export default function Items() {
  const { data, error, loading, reload } = useLoad("/api/items");
  const [editing, setEditing] = useState(null);
  const [msg, setMsg] = useState(null);

  const upload = async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    if (!window.confirm("Replace all items with the items in this file?")) return;
    const form = new FormData();
    form.append("file", file);
    try { const r = await api("/api/items/upload", "POST", form); setMsg(["ok", `Imported ${r.imported} items.`]); reload(); }
    catch (e2) { setMsg(["error", e2.message]); }
  };
  const remove = async (it) => {
    if (!window.confirm(`Delete ${it.name}?`)) return;
    await api(`/api/items/${it.id}`, "DELETE"); reload();
  };
  const sample = async () => {
    if (!window.confirm("Replace all items with the example items?")) return;
    await api("/api/items/sample", "POST"); setMsg(["ok", "Example items loaded."]); reload();
  };

  if (loading && !data) return <Loading />;
  if (error) return <Note kind="error">{error}</Note>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1>My Items</h1><p className="mt-1 text-ink-600">The raw materials you buy. Add them one by one or upload a CSV file.</p></div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" onClick={() => setEditing({})}>+ Add item</button>
          <label className="btn-light cursor-pointer">Upload CSV<input type="file" accept=".csv" className="sr-only" onChange={upload} /></label>
          <a className="btn-light" href="/api/items/template.csv">CSV template</a>
          <button className="btn-light" onClick={sample}>Load example items</button>
        </div>
      </div>
      {msg && <Note kind={msg[0]}>{msg[1]}</Note>}
      {editing && <ItemForm initial={editing.id ? editing : null} onCancel={() => setEditing(null)} onDone={() => { setEditing(null); reload(); }} />}

      <div className="card overflow-x-auto p-0">
        <table className="tbl">
          <thead><tr>
            <th>Item</th><th className="num">Stock</th><th className="num">Used / week</th><th className="num">Price</th><th className="num">Delivery</th>
            <th className="num">Distance</th><th className="num">Best order size (EOQ)</th><th className="num">Safety stock</th><th>Status</th><th />
          </tr></thead>
          <tbody>
            {data.map((it) => (
              <tr key={it.id}>
                <td className="font-medium">{it.name}</td><td className="num">{num(it.stock)} {it.unit}</td><td className="num">{num(it.weekly_demand)}</td>
                <td className="num">{money(it.price)}</td><td className="num">{it.lead_time_weeks} wk</td><td className="num">{num(it.distance_km)} km</td>
                <td className="num">{num(it.eoq)}</td><td className="num">{num(it.safety_stock)}</td><td><Status value={it.status} /></td>
                <td className="whitespace-nowrap text-sm"><button className="text-brand-700 underline" onClick={() => setEditing(it)}>Edit</button>{" "}
                  <button className="ml-2 text-red-700 underline" onClick={() => remove(it)}>Delete</button></td>
              </tr>
            ))}
            {!data.length && <tr><td colSpan={10} className="py-10 text-center text-ink-500">No items yet. Add one or load the example items.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="card text-sm text-ink-600">
        <h2 className="mb-2 text-base">How the numbers are worked out</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li><b>Best order size (EOQ)</b> = √(2 × yearly use × order cost ÷ yearly storage cost per unit). It balances ordering often against holding stock.</li>
          <li><b>Safety stock</b> = extra stock kept in case demand is higher than usual (based on the settings below).</li>
          <li><b>Order now</b> = stock will run out before a new delivery can arrive. <b>Order soon</b> = stock is at or below the reorder level.</li>
        </ul>
      </div>
      <SettingsBox />
    </div>
  );
}
