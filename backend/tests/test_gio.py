import math
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["GIO_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import calc, db, planner, routing  # noqa: E402

S = {**db.DEFAULT_SETTINGS, "weeks": 6, "time_limit_s": 20}


def item(**kw):
    base = dict(id=1, name="Steel", unit="pcs", stock=0, weekly_demand=100, price=100, order_cost=500,
                weight_kg=10, lead_time_weeks=1, distance_km=100)
    return {**base, **kw}


# ---------------- inventory formulas

def test_eoq():
    # yearly demand 5200, order cost 500, holding 20% of 100 = 20 -> sqrt(2*5200*500/20) = 509.9
    assert calc.eoq(100, 500, 100, 20) == pytest.approx(509.9, abs=0.1)
    assert calc.eoq(100, 500, 0, 20) == 0


def test_safety_stock_and_reorder_point():
    ss = calc.safety_stock(100, 20, 1, 95)       # 1.645 * 20 * sqrt(2)
    assert ss == pytest.approx(1.6449 * 20 * math.sqrt(2), rel=1e-3)
    assert calc.reorder_point(100, 1, ss) == pytest.approx(200 + ss)


def test_stock_status():
    assert calc.stock_status(50, 250, 100, 1) == "urgent"
    assert calc.stock_status(200, 250, 100, 1) == "order soon"
    assert calc.stock_status(400, 250, 100, 1) == "ok"


# ---------------- transport

def test_trip_fuel_co2_cost():
    t = calc.trip("large_truck", 200, 90)
    assert t["litres"] == pytest.approx(60)                 # 200 km x 30 L/100km
    assert t["co2_kg"] == pytest.approx(60 * 2.69)          # 161.4 kg
    assert t["cost"] == pytest.approx(60 * 90 + 200 * 15)


def test_cheapest_trucks_carry_the_load():
    for w in (0, 500, 3000, 3001, 19000, 45000):
        r = calc.cheapest_trucks(w, 100, 90)
        assert r["small"] * 3000 + r["large"] * 20000 >= w
    r = calc.cheapest_trucks(2500, 100, 90)
    assert r["small"] == 1 and r["large"] == 0


def test_delivery_options():
    opts = {o["option"]: o for o in calc.delivery_options(10000, 500, 90)}
    assert opts["Small truck"]["vehicles"] == 4 and opts["Large truck"]["vehicles"] == 1
    assert opts["Train"]["co2_kg"] == pytest.approx(10 * 500 * 0.028)
    assert opts["Train"]["co2_kg"] < opts["Large truck"]["co2_kg"] < opts["Small truck"]["co2_kg"]


def test_parse_route():
    r = routing.parse_route({"code": "Ok", "routes": [{"distance": 112000, "duration": 5400, "geometry": {"coordinates": [[1, 2]]}}]})
    assert r["distance_km"] == 112.0 and r["hours"] == 1.5
    with pytest.raises(routing.RoutingError):
        routing.parse_route({"code": "NoRoute"})


# ---------------- planner

def test_plan_meets_demand_and_respects_lead_time():
    it = item(stock=250)
    r, status = planner.optimal_plan([it], S)
    assert status == "optimal"
    for o in r["orders"]:
        assert o["week"] + 1 <= S["weeks"]                                    # arrives inside the horizon
        assert o["small"] * 3000 + o["large"] * 20000 >= o["qty"] * 10        # trucks can carry it
    assert r["totals"]["missed_units"] == 0


def test_unavoidable_shortage_is_reported():
    it = item(stock=0, lead_time_weeks=2)   # nothing can arrive before week 3
    r = planner.make_plan([it], S)
    assert r["plan"]["totals"]["missed_units"] == pytest.approx(200)
    assert r["summary"]["warnings"]


def test_optimal_is_not_worse_than_simple_rule():
    items = [item(stock=300), item(id=2, name="Paint", stock=40, weekly_demand=20, price=5000, weight_kg=20, distance_km=600)]
    r = planner.make_plan(items, S)
    assert r["plan"]["totals"]["total_cost"] <= r["simple_rule"]["totals"]["total_cost"] + 1
    assert r["summary"]["todo"] and r["summary"]["headline"]


def test_greenest_has_no_more_co2_than_cheapest():
    items = [item(stock=300, distance_km=800), item(id=2, name="Bolts", stock=500, weekly_demand=400, price=5, weight_kg=1, distance_km=800)]
    cheap = planner.make_plan(items, S, "cheapest")
    green = planner.make_plan(items, S, "greenest")
    assert green["plan"]["totals"]["co2_kg"] <= cheap["plan"]["totals"]["co2_kg"] + 0.01
    assert green["plan"]["totals"]["missed_units"] <= cheap["plan"]["totals"]["missed_units"] + 0.01


def test_no_items():
    with pytest.raises(planner.PlanError):
        planner.make_plan([], S)


# ---------------- website API

@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_items_crud_and_validation(client):
    assert len(client.get("/api/items").json()) == 6                     # sample loaded on first start
    bad = client.post("/api/items", json=item(name="X", weekly_demand=0))
    assert bad.status_code == 422
    new = {k: v for k, v in item(name="Copper wire").items() if k != "id"}
    assert client.post("/api/items", json=new).status_code == 200
    assert client.post("/api/items", json=new).status_code == 400        # duplicate name
    row = next(i for i in client.get("/api/items").json() if i["name"] == "Copper wire")
    assert row["status"] == "urgent" and row["eoq"] > 0
    assert client.delete(f"/api/items/{row['id']}").status_code == 200


def test_csv_upload(client):
    bad = "name,unit,stock\nA,pcs,1\n"
    r = client.post("/api/items/upload", files={"file": ("a.csv", bad, "text/csv")})
    assert r.status_code == 400 and "missing" in r.json()["detail"]
    rows = ",".join(db.ITEM_FIELDS) + "\nWire,m,10,5,2,10,1,1,20\nTape,rolls,-1,5,2,10,1,1,20\n"
    r = client.post("/api/items/upload", files={"file": ("a.csv", rows, "text/csv")})
    assert r.status_code == 400 and "Row 3" in r.json()["detail"]
    assert len(client.get("/api/items").json()) == 6                     # nothing changed
    client.post("/api/items/sample")


def test_plan_review_and_download(client):
    p = client.post("/api/plan", json={"mode": "cheapest"}).json()
    assert p["plan"]["orders"] and p["reviewed_by"] is None
    assert b"NOT CHECKED YET" in client.get("/api/plan.csv").content
    assert client.post("/api/plan/review", json={"name": "A"}).status_code == 422
    client.post("/api/plan/review", json={"name": "Priya (stores)"})
    assert b"Checked by Priya" in client.get("/api/plan.csv").content
