import { Link } from "react-router-dom";
import { money, num } from "../api";
import { Loading, Note, Stat, Status, useLoad } from "../components/bits";

export default function Home() {
  const { data, error, loading } = useLoad("/api/dashboard");
  if (loading) return <Loading />;
  if (error) return <Note kind="error">{error}</Note>;
  const cur = data.currency;
  const plan = data.plan;
  const thisWeek = plan?.summary.todo.filter((t) => t.week === 1) || [];
  const later = plan?.summary.todo.filter((t) => t.week > 1) || [];

  return (
    <div className="space-y-6">
      <div>
        <h1>What should I do?</h1>
        <p className="mt-1 text-ink-600">A quick summary of your stock and the orders to place.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Items tracked" value={data.items.length} sub={`Stock worth ${money(data.stock_value, cur)}`} />
        <Stat label="Need ordering now" value={data.urgent.length} sub={data.urgent.join(", ") || "None"} good={data.urgent.length === 0} />
        <Stat label="Order soon" value={data.order_soon.length} sub={data.order_soon.join(", ") || "None"} />
      </div>

      {!plan ? (
        <div className="card text-center">
          <h2>No order plan yet</h2>
          <p className="mx-auto mt-1 max-w-md text-ink-600">GIO will work out when to order each item, how much, and which trucks to use — at the lowest cost.</p>
          <Link to="/plan" className="btn mt-4">Create my order plan</Link>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="card">
            <h2>To do this week</h2>
            {thisWeek.length ? (
              <ul className="mt-3 space-y-2">{thisWeek.map((t, i) => <li key={i} className="flex gap-2"><span className="text-brand-700">✔</span>{t.text}</li>)}</ul>
            ) : <p className="mt-2 text-ink-600">Nothing to order this week. 🎉</p>}
            {plan.summary.warnings.map((w, i) => <Note key={i} kind="warn" className="mt-3">{w}</Note>)}
            {later.length > 0 && (
              <>
                <h3 className="mt-5 text-sm font-semibold text-ink-700">Coming up</h3>
                <ul className="mt-2 space-y-1 text-sm text-ink-600">{later.slice(0, 6).map((t, i) => <li key={i}><b>Week {t.week}:</b> {t.text}</li>)}</ul>
                {later.length > 6 && <Link to="/plan" className="mt-2 inline-block text-sm text-brand-700 underline">See all {later.length} orders</Link>}
              </>
            )}
          </div>
          <div className="card">
            <h2>Why this plan is better</h2>
            <ul className="mt-3 space-y-2">{plan.summary.headline.map((h, i) => <li key={i} className="flex gap-2"><span className="text-brand-700">•</span>{h}</li>)}</ul>
            <p className="mt-4 text-sm text-ink-500">Compared with the usual rule “order a fixed amount (EOQ) when stock gets low”. Plan made {plan.created_at}.</p>
            <p className="mt-2 text-sm">{plan.reviewed_by ? <span className="text-emerald-700">✔ Checked by {plan.reviewed_by}</span> : <span className="text-amber-800">Not checked yet — <Link to="/plan" className="underline">review it</Link> before ordering.</span>}</p>
          </div>
        </div>
      )}

      <div className="card overflow-x-auto p-0">
        <div className="flex items-center justify-between p-5 pb-3"><h2>Stock levels</h2><Link to="/items" className="text-sm text-brand-700 underline">Edit items</Link></div>
        <table className="tbl">
          <thead><tr><th>Item</th><th className="num">In stock</th><th className="num">Lasts</th><th className="num">Reorder at</th><th>Status</th></tr></thead>
          <tbody>{data.items.map((it) => (
            <tr key={it.id}><td className="font-medium">{it.name}</td><td className="num">{num(it.stock)} {it.unit}</td>
              <td className="num">{num(it.weeks_left, 1)} weeks</td><td className="num">{num(it.reorder_point)}</td><td><Status value={it.status} /></td></tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
