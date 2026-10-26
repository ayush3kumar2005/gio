"""Order planning.

* simple_rule_plan(): what most small factories do today - order the EOQ whenever stock
  drops to the reorder point (used as the comparison baseline).
* optimal_plan(): a Mixed-Integer Linear Program (PuLP + CBC) that decides how much to
  order each week and how many small/large trucks to use, at the lowest total cost.
  Eco mode adds a CO2 limit.
Both plans are scored by the same evaluate() function so the comparison is fair.
"""
import math

import pulp

from . import calc


class PlanError(Exception):
    pass


def item_numbers(item, s):
    """Derived numbers for one item: holding cost per week, safety stock, reorder point, EOQ."""
    ss = calc.safety_stock(item["weekly_demand"], s["demand_variation_pct"], item["lead_time_weeks"], s["service_level_pct"])
    return {
        "holding_per_week": item["price"] * s["holding_pct"] / 100 / 52,
        "shortage_cost": item["price"] * s["shortage_cost_multiplier"],
        "safety_stock": ss,
        "reorder_point": calc.reorder_point(item["weekly_demand"], item["lead_time_weeks"], ss),
        "eoq": calc.eoq(item["weekly_demand"], item["order_cost"], item["price"], s["holding_pct"]),
    }


# ---------------------------------------------------------------- scoring

def evaluate(items, orders, s):
    """Simulate week by week. orders: [{item_id, week, qty, small, large}] (small/large = trucks)."""
    T = s["weeks"]
    by_item = {it["id"]: [] for it in items}
    for o in orders:
        by_item[o["item_id"]].append(o)
    totals = dict(purchase=0.0, ordering=0.0, storage=0.0, transport=0.0, missed=0.0, leftover_value=0.0,
                  co2_kg=0.0, litres=0.0, small_trucks=0, large_trucks=0, missed_units=0.0, demand_units=0.0)
    per_item = []
    for it in items:
        n = item_numbers(it, s)
        arrivals = [0.0] * (T + 2)
        for o in by_item[it["id"]]:
            arrive = o["week"] + it["lead_time_weeks"]
            if arrive <= T:
                arrivals[arrive] += o["qty"]
            t = calc.trip("small_truck", it["distance_km"], s["fuel_price"]), calc.trip("large_truck", it["distance_km"], s["fuel_price"])
            totals["purchase"] += o["qty"] * it["price"]
            totals["ordering"] += it["order_cost"]
            totals["transport"] += o["small"] * t[0]["cost"] + o["large"] * t[1]["cost"]
            totals["co2_kg"] += o["small"] * t[0]["co2_kg"] + o["large"] * t[1]["co2_kg"]
            totals["litres"] += o["small"] * t[0]["litres"] + o["large"] * t[1]["litres"]
            totals["small_trucks"] += o["small"]
            totals["large_trucks"] += o["large"]
        stock, weekly, missed = it["stock"], [], 0.0
        for w in range(1, T + 1):
            stock += arrivals[w]
            used = min(stock, it["weekly_demand"])
            short = it["weekly_demand"] - used
            stock -= used
            missed += short
            totals["storage"] += stock * n["holding_per_week"]
            totals["missed"] += short * n["shortage_cost"]
            weekly.append({"week": w, "stock": round(stock, 1), "arrives": round(arrivals[w], 1), "short": round(short, 1)})
        totals["leftover_value"] += stock * it["price"]
        totals["missed_units"] += missed
        totals["demand_units"] += it["weekly_demand"] * T
        per_item.append({"item_id": it["id"], "name": it["name"], "unit": it["unit"], "weekly": weekly,
                         "missed_units": round(missed, 1), "end_stock": round(stock, 1),
                         "safety_stock": round(n["safety_stock"], 1)})
    totals["total_cost"] = (totals["purchase"] + totals["ordering"] + totals["storage"] + totals["transport"]
                            + totals["missed"] - totals["leftover_value"])
    totals["service_pct"] = 100 * (1 - totals["missed_units"] / totals["demand_units"]) if totals["demand_units"] else 100.0
    return {"totals": {k: round(v, 2) if isinstance(v, float) else v for k, v in totals.items()},
            "items": per_item,
            "orders": sorted(orders, key=lambda o: (o["week"], o["item_id"]))}


# ---------------------------------------------------------------- baseline

def simple_rule_plan(items, s):
    """Order EOQ (at least one week of demand) when stock + incoming <= reorder point; cheapest trucks."""
    T, orders = s["weeks"], []
    for it in items:
        n = item_numbers(it, s)
        q = max(math.ceil(n["eoq"]), math.ceil(it["weekly_demand"]))
        stock, incoming = it["stock"], {}
        for w in range(1, T + 1):
            on_order = sum(v for k, v in incoming.items() if k >= w)
            if stock + on_order <= n["reorder_point"] and w + it["lead_time_weeks"] <= T:
                trucks = calc.cheapest_trucks(q * it["weight_kg"], it["distance_km"], s["fuel_price"])
                orders.append({"item_id": it["id"], "week": w, "qty": float(q), "small": trucks["small"], "large": trucks["large"]})
                incoming[w + it["lead_time_weeks"]] = incoming.get(w + it["lead_time_weeks"], 0) + q
            stock += incoming.get(w, 0)
            stock -= min(stock, it["weekly_demand"])
    return evaluate(items, orders, s)


# ---------------------------------------------------------------- MILP

def _build(items, s, objective="cost", co2_limit=None, max_missed_units=None):
    """Objective note: every unit bought is either used or left in stock at the end, and leftover stock
    is counted at its price. So (purchase cost - leftover value) = constant - price x missed units, and
    the model only needs ordering + storage + transport + (shortage cost - price) x missed units."""
    T = s["weeks"]
    m = pulp.LpProblem("order_plan", pulp.LpMinimize)
    cost_terms, co2_terms, missed_terms = [], [], []
    v = {}
    for it in items:
        i, n, L = it["id"], item_numbers(it, s), it["lead_time_weeks"]
        small, large = calc.trip("small_truck", it["distance_km"], s["fuel_price"]), calc.trip("large_truck", it["distance_km"], s["fuel_price"])
        I_prev = it["stock"]
        for t in range(1, T + 1):
            if t + L <= T:  # an order placed in week t arrives in week t + L
                most_useful = it["weekly_demand"] * (T - t - L + 1) + n["safety_stock"] + 1
                x = v[("x", i, t)] = pulp.LpVariable(f"x_{i}_{t}", lowBound=0)          # quantity ordered
                y = v[("y", i, t)] = pulp.LpVariable(f"y_{i}_{t}", cat="Binary")         # order placed?
                ns = v[("s", i, t)] = pulp.LpVariable(f"s_{i}_{t}", lowBound=0, cat="Integer")  # small trucks
                nl = v[("l", i, t)] = pulp.LpVariable(f"l_{i}_{t}", lowBound=0, cat="Integer")  # large trucks
                m += x <= most_useful * y
                m += it["weight_kg"] * x <= 3000 * ns + 20000 * nl          # trucks must carry the order
                cost_terms += [it["order_cost"] * y, small["cost"] * ns, large["cost"] * nl]
                co2_terms += [small["co2_kg"] * ns, large["co2_kg"] * nl]
            I = v[("I", i, t)] = pulp.LpVariable(f"I_{i}_{t}", lowBound=0)              # stock at end of week
            U = v[("U", i, t)] = pulp.LpVariable(f"U_{i}_{t}", lowBound=0, upBound=it["weekly_demand"])  # missed demand
            arrive = v.get(("x", i, t - L), 0)
            m += I == I_prev + arrive - it["weekly_demand"] + U                  # stock balance
            cost_terms += [n["holding_per_week"] * I, (n["shortage_cost"] - it["price"]) * U]
            missed_terms.append(U)
            if t > L:  # keep safety stock once a new order could have arrived (soft: small penalty if below)
                g = pulp.LpVariable(f"g_{i}_{t}", lowBound=0)
                m += I + g >= n["safety_stock"]
                cost_terms.append((2 * n["holding_per_week"] + (it["price"] if t == T else 0)) * g)
            I_prev = I
    if co2_limit is not None:
        m += pulp.lpSum(co2_terms) <= co2_limit
    if max_missed_units is not None:
        m += pulp.lpSum(missed_terms) <= max_missed_units
    if objective == "co2":  # greenest: CO2 matters far more than money (1 kg CO2 weighs like 1,000 in cost)
        m += 1000 * pulp.lpSum(co2_terms) + pulp.lpSum(cost_terms)
    else:
        m += pulp.lpSum(cost_terms)
    return m, v


def optimal_plan(items, s, objective="cost", co2_limit=None, max_missed_units=None):
    m, v = _build(items, s, objective, co2_limit, max_missed_units)
    m.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=s["time_limit_s"], gapRel=0.001))
    if pulp.LpStatus[m.status] != "Optimal":
        return None, pulp.LpStatus[m.status]
    orders = []
    for (kind, i, t), var in v.items():
        if kind == "x" and var.value() and var.value() > 0.5:
            orders.append({"item_id": i, "week": t, "qty": float(math.floor(var.value() + 1e-6)),
                           "small": int(round(v[("s", i, t)].value())), "large": int(round(v[("l", i, t)].value()))})
    proven = getattr(m, "sol_status", 1) == 1
    return evaluate(items, orders, s), "optimal" if proven else "good (time limit reached)"


# ---------------------------------------------------------------- the whole thing

def make_plan(items, s, mode="cheapest"):
    """mode 'cheapest': lowest total cost.
    mode 'greenest': lowest truck CO2 while meeting as much demand as the cheapest plan,
    then the lowest cost among those plans."""
    if not items:
        raise PlanError("Add at least one item first.")
    baseline = simple_rule_plan(items, s)
    cheapest, status = optimal_plan(items, s)
    if cheapest is None:
        raise PlanError(f"The optimiser could not find a plan (status: {status}).")
    plan, note = cheapest, None
    if mode == "greenest":
        missed = cheapest["totals"]["missed_units"] + 0.01
        green, status = optimal_plan(items, s, objective="co2", max_missed_units=missed)
        if green is None:
            note = "A greener plan could not be found in time, so the lowest-cost plan is shown."
        else:
            plan = green
            extra = green["totals"]["total_cost"] - cheapest["totals"]["total_cost"]
            saved = cheapest["totals"]["co2_kg"] - green["totals"]["co2_kg"]
            note = (f"Greenest plan: {saved:,.0f} kg less truck CO₂ than the cheapest plan, "
                    f"for {fmt_money(max(extra, 0), s)} extra cost.")
    plan["solver_status"] = status
    return {"mode": mode, "plan": plan, "simple_rule": baseline, "note": note,
            "summary": summary(items, plan, baseline, s)}


def fmt_money(x, s):
    return f"{s['currency_symbol']}{x:,.0f}"


def summary(items, plan, baseline, s):
    """Plain-language to-do list."""
    names = {it["id"]: it for it in items}
    todo = []
    for o in plan["orders"]:
        it = names[o["item_id"]]
        trucks = " + ".join(x for x in [f"{o['large']} large truck{'s' * (o['large'] > 1)}" if o["large"] else "",
                                        f"{o['small']} small truck{'s' * (o['small'] > 1)}" if o["small"] else ""] if x)
        todo.append({"week": o["week"], "item": it["name"],
                     "text": f"{it['name']}: order {o['qty']:,.0f} {it['unit']} (arrives week {o['week'] + it['lead_time_weeks']}, {trucks or 'no truck needed'})"})
    p, b = plan["totals"], baseline["totals"]
    headline = []
    saved = b["total_cost"] - p["total_cost"]
    headline.append(f"This plan costs {fmt_money(abs(saved), s)} {'less' if saved >= 0 else 'more'} than the simple reorder rule.")
    dco2 = b["co2_kg"] - p["co2_kg"]
    headline.append(f"Truck CO₂ is {abs(dco2):,.0f} kg {'lower' if dco2 >= 0 else 'higher'} ({p['co2_kg']:,.0f} kg vs {b['co2_kg']:,.0f} kg).")
    trucks_p, trucks_b = p["small_trucks"] + p["large_trucks"], b["small_trucks"] + b["large_trucks"]
    headline.append(f"Trucks needed: {trucks_p} instead of {trucks_b}.")
    headline.append(f"Demand met: {p['service_pct']:.1f}% (simple rule: {b['service_pct']:.1f}%).")
    warnings = [f"{x['name']}: {x['missed_units']:,.0f} {names[x['item_id']]['unit']} of demand cannot be met in time — "
                f"current stock is too low for the lead time. Consider an urgent order." for x in plan["items"] if x["missed_units"] > 0.5]
    return {"headline": headline, "todo": todo, "warnings": warnings}
