"""Basic inventory and transport formulas used across GIO."""
import math
from statistics import NormalDist

DIESEL_CO2_KG_PER_LITRE = 2.69   # US EPA: 10,180 g CO2 per US gallon of diesel (10.18 / 3.785)
RAIL_CO2_KG_PER_TONNE_KM = 0.028  # typical published freight-train average (estimate)
RAIL_COST_PER_TONNE_KM = 1.6      # rough estimate, change in code if you have a quote

# Two generic road vehicles. Fuel use and running cost are typical values (estimates).
VEHICLES = {
    "small_truck": {"label": "Small truck", "capacity_kg": 3000, "litres_per_100km": 12, "cost_per_km": 8},
    "large_truck": {"label": "Large truck", "capacity_kg": 20000, "litres_per_100km": 30, "cost_per_km": 15},
}


# ---------- inventory ----------

def eoq(weekly_demand, order_cost, price, holding_pct, weeks_per_year=52):
    """Economic Order Quantity = sqrt(2 x yearly demand x order cost / yearly holding cost per unit)."""
    yearly_demand = weekly_demand * weeks_per_year
    holding_per_unit = price * holding_pct / 100
    if holding_per_unit <= 0 or yearly_demand <= 0:
        return 0.0
    return math.sqrt(2 * yearly_demand * order_cost / holding_per_unit)


def safety_stock(weekly_demand, variation_pct, lead_time_weeks, service_level_pct):
    """Safety stock = z x (weekly demand x variation%) x sqrt(lead time + 1 week review)."""
    z = NormalDist().inv_cdf(service_level_pct / 100)
    sigma = weekly_demand * variation_pct / 100
    return z * sigma * math.sqrt(lead_time_weeks + 1)


def reorder_point(weekly_demand, lead_time_weeks, ss):
    """Order again when stock falls to: demand during (lead time + 1 week) + safety stock."""
    return weekly_demand * (lead_time_weeks + 1) + ss


def weeks_of_stock(stock, weekly_demand):
    return stock / weekly_demand if weekly_demand > 0 else None


def stock_status(stock, rop, weekly_demand, lead_time_weeks):
    if stock < weekly_demand * lead_time_weeks:
        return "urgent"      # will run out before a new order can arrive
    if stock <= rop:
        return "order soon"
    return "ok"


# ---------- transport ----------

def trip(vehicle_key, distance_km, fuel_price):
    """Fuel, CO2 and cost of ONE trip of a vehicle."""
    v = VEHICLES[vehicle_key]
    litres = distance_km * v["litres_per_100km"] / 100
    return {
        "litres": litres,
        "co2_kg": litres * DIESEL_CO2_KG_PER_LITRE,
        "cost": litres * fuel_price + distance_km * v["cost_per_km"],
    }


def cheapest_trucks(weight_kg, distance_km, fuel_price):
    """Cheapest mix of small and large trucks that can carry weight_kg."""
    if weight_kg <= 0:
        return {"small": 0, "large": 0, "cost": 0.0, "co2_kg": 0.0, "litres": 0.0}
    s, l = trip("small_truck", distance_km, fuel_price), trip("large_truck", distance_km, fuel_price)
    best = None
    for large in range(0, math.ceil(weight_kg / 20000) + 1):
        rest = max(0.0, weight_kg - large * 20000)
        small = math.ceil(rest / 3000 - 1e-9)
        cost = small * s["cost"] + large * l["cost"]
        if best is None or cost < best["cost"] - 1e-9:
            best = {"small": small, "large": large, "cost": cost,
                    "co2_kg": small * s["co2_kg"] + large * l["co2_kg"],
                    "litres": small * s["litres"] + large * l["litres"]}
    return best


def delivery_options(weight_kg, distance_km, fuel_price):
    """Compare small trucks, large trucks and train for one shipment."""
    out = []
    for key in ("small_truck", "large_truck"):
        v = VEHICLES[key]
        n = max(1, math.ceil(weight_kg / v["capacity_kg"] - 1e-9))
        t = trip(key, distance_km, fuel_price)
        out.append({"option": v["label"], "vehicles": n, "litres": round(n * t["litres"], 1),
                    "co2_kg": round(n * t["co2_kg"], 1), "cost": round(n * t["cost"]), "estimate": False})
    tkm = weight_kg / 1000 * distance_km
    out.append({"option": "Train", "vehicles": None, "litres": None,
                "co2_kg": round(tkm * RAIL_CO2_KG_PER_TONNE_KM, 1), "cost": round(tkm * RAIL_COST_PER_TONNE_KM),
                "estimate": True})
    return out
