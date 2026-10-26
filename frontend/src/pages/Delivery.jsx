import { useEffect, useMemo, useState } from "react";
import { api, money, num } from "../api";
import MapView from "../components/MapView";
import { Note, useLoad } from "../components/bits";

export default function Delivery() {
  const settings = useLoad("/api/settings");
  const [f, setF] = useState({ from: "Mumbai", to: "", weight: "5000" });
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => { if (settings.data && !f.to) setF((x) => ({ ...x, to: settings.data.plant_city })); }, [settings.data]); // eslint-disable-line

  const go = async (e) => {
    e.preventDefault();
    if (!(Number(f.weight) > 0)) { setErr("Enter a weight above 0 kg."); return; }
    setBusy(true); setErr(null);
    try { setRes(await api("/api/delivery", "POST", { from_place: f.from, to_place: f.to, weight_kg: Number(f.weight) })); }
    catch (e2) { setErr(e2.message); setRes(null); } finally { setBusy(false); }
  };

  const points = useMemo(() => res ? [{ ...res.from, label: res.from.name, kind: "supplier" }, { ...res.to, label: res.to.name, kind: "plant" }] : [], [res]);
  const lines = useMemo(() => res ? [{ coords: res.geometry, label: `${num(res.distance_km)} km` }] : [], [res]);

  return (
    <div className="space-y-6">
      <div><h1>Delivery & CO₂</h1><p className="mt-1 text-ink-600">Find the road distance between two places and compare the cost and CO₂ of sending a load by small truck, large truck or train.</p></div>

      <form onSubmit={go} className="card grid gap-4 sm:grid-cols-4 sm:items-end">
        <div><label className="label" htmlFor="from">From</label><input id="from" className="input" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} required /></div>
        <div><label className="label" htmlFor="to">To</label><input id="to" className="input" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} required /></div>
        <div><label className="label" htmlFor="w">Weight (kg)</label><input id="w" type="number" min="1" className="input" value={f.weight} onChange={(e) => setF({ ...f, weight: e.target.value })} required /></div>
        <button className="btn" disabled={busy}>{busy ? "Finding route…" : "Compare"}</button>
      </form>
      {err && <Note kind="error">{err}</Note>}

      {res && (
        <>
          <Note kind="ok">Road distance <b>{num(res.distance_km, 1)} km</b>, about <b>{num(res.hours, 1)} hours</b> of driving. Greenest: <b>{res.greenest}</b>. Cheapest: <b>{res.cheapest}</b>.</Note>
          <div className="grid gap-4 sm:grid-cols-3">
            {res.options.map((o) => (
              <div key={o.option} className={`card ${o.option === res.greenest ? "border-brand-600 ring-1 ring-brand-600" : ""}`}>
                <div className="flex items-center justify-between">
                  <h2>{o.option === "Train" ? "🚆" : "🚚"} {o.option}</h2>
                  {o.option === res.greenest && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">Greenest</span>}
                </div>
                <dl className="mt-3 space-y-1 text-sm">
                  <div className="flex justify-between"><dt className="text-ink-500">CO₂</dt><dd className="font-semibold">{num(o.co2_kg)} kg</dd></div>
                  <div className="flex justify-between"><dt className="text-ink-500">Cost</dt><dd className="font-semibold">{money(o.cost)}</dd></div>
                  {o.vehicles != null && <div className="flex justify-between"><dt className="text-ink-500">Trucks</dt><dd>{o.vehicles}</dd></div>}
                  {o.litres != null && <div className="flex justify-between"><dt className="text-ink-500">Diesel</dt><dd>{num(o.litres)} L</dd></div>}
                </dl>
                {o.estimate && <p className="mt-2 text-xs text-ink-500">Rough estimate using average train figures and the road distance. Only possible if a rail link exists.</p>}
              </div>
            ))}
          </div>
          <div className="card"><MapView points={points} lines={lines} height={360} /></div>
          <div className="card text-sm text-ink-600">
            <h2 className="mb-2 text-base">How this is calculated</h2>
            <ul className="list-disc space-y-1 pl-5">
              <li>Route and distance from OpenStreetMap (OSRM). Driving time is for a car with no traffic, so trucks will take longer.</li>
              <li>Small truck: up to 3 t, about 12 L diesel per 100 km. Large truck: up to 20 t, about 30 L per 100 km (typical values).</li>
              <li>CO₂ = litres of diesel × 2.69 kg (US EPA figure). Train ≈ 0.028 kg CO₂ per tonne per km (typical average).</li>
              <li>Cost = diesel used × diesel price + a running cost per km (driver, maintenance).</li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
