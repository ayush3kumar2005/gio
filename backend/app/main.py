"""GIO web API."""
import csv
import io
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from . import calc, db, planner, routing


@asynccontextmanager
async def lifespan(_app):
    conn = db.connect()
    db.init(conn)  # first start loads the sample items
    conn.close()
    yield


app = FastAPI(title="Green Inventory Optimizer", lifespan=lifespan)


def get_conn():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- items

class Item(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=20)
    stock: float = Field(ge=0)
    weekly_demand: float = Field(gt=0)
    price: float = Field(gt=0)
    order_cost: float = Field(ge=0)
    weight_kg: float = Field(gt=0)
    lead_time_weeks: int = Field(ge=0, le=12)
    distance_km: float = Field(ge=0, le=10000)


def item_view(it, s):
    n = planner.item_numbers(it, s)
    return {**it, "safety_stock": round(n["safety_stock"]), "reorder_point": round(n["reorder_point"]),
            "eoq": round(n["eoq"]), "weeks_left": round(calc.weeks_of_stock(it["stock"], it["weekly_demand"]), 1),
            "status": calc.stock_status(it["stock"], n["reorder_point"], it["weekly_demand"], it["lead_time_weeks"]),
            "stock_value": round(it["stock"] * it["price"])}


@app.get("/api/items")
def list_items(conn=Depends(get_conn)):
    s = db.settings(conn)
    return [item_view(it, s) for it in db.items(conn)]


def _save(conn, item: Item, item_id=None):
    vals = [getattr(item, f) for f in db.ITEM_FIELDS]
    try:
        if item_id is None:
            conn.execute(f"INSERT INTO items ({','.join(db.ITEM_FIELDS)}) VALUES ({','.join('?' * len(vals))})", vals)
        else:
            conn.execute(f"UPDATE items SET {','.join(f + '=?' for f in db.ITEM_FIELDS)} WHERE id=?", vals + [item_id])
        conn.commit()
    except Exception:
        raise HTTPException(400, f"An item called '{item.name}' already exists.")


@app.post("/api/items")
def add_item(item: Item, conn=Depends(get_conn)):
    _save(conn, item)
    return {"ok": True}


@app.put("/api/items/{item_id}")
def edit_item(item_id: int, item: Item, conn=Depends(get_conn)):
    _save(conn, item, item_id)
    return {"ok": True}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, conn=Depends(get_conn)):
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    return {"ok": True}


@app.post("/api/items/sample")
def reset_sample(conn=Depends(get_conn)):
    db.load_sample(conn)
    return {"ok": True}


@app.get("/api/items/template.csv")
def template():
    rows = ",".join(db.ITEM_FIELDS) + "\nSteel sheets,sheets,1400,400,1950,3500,29.4,1,112\n"
    return Response(rows, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="items_template.csv"'})


@app.post("/api/items/upload")
async def upload(file: UploadFile = File(...), conn=Depends(get_conn)):
    """Replace all items with the rows of a CSV file. Nothing is changed if any row is invalid."""
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    missing = [f for f in db.ITEM_FIELDS if f not in (reader.fieldnames or [])]
    if missing:
        raise HTTPException(400, f"The file is missing these columns: {', '.join(missing)}. Download the template to see the format.")
    good, errors, names = [], [], set()
    for row_no, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values()):
            continue
        try:
            item = Item(**{f: (row[f] or "").strip() for f in db.ITEM_FIELDS})
        except ValidationError as e:
            for err in e.errors():
                errors.append(f"Row {row_no}, {err['loc'][0]}: {err['msg']}")
            continue
        if item.name.lower() in names:
            errors.append(f"Row {row_no}: '{item.name}' appears twice")
        names.add(item.name.lower())
        good.append(item)
    if errors:
        raise HTTPException(400, "Nothing was imported. Please fix: " + "; ".join(errors[:15]))
    if not good:
        raise HTTPException(400, "The file has no item rows.")
    conn.execute("DELETE FROM items")
    for it in good:
        _save(conn, it)
    conn.execute("DELETE FROM plan")
    conn.commit()
    return {"imported": len(good)}


# ---------------------------------------------------------------- settings

class Settings(BaseModel):
    plant_city: str = Field(min_length=2)
    weeks: int = Field(ge=2, le=26)
    holding_pct: float = Field(ge=0, le=100)
    demand_variation_pct: float = Field(ge=0, le=100)
    service_level_pct: float = Field(ge=50, le=99.9)
    shortage_cost_multiplier: float = Field(ge=1, le=20)
    fuel_price: float = Field(gt=0)


@app.get("/api/settings")
def get_settings(conn=Depends(get_conn)):
    return db.settings(conn)


@app.put("/api/settings")
def put_settings(body: Settings, conn=Depends(get_conn)):
    db.save_settings(conn, body.model_dump())
    return db.settings(conn)


# ---------------------------------------------------------------- plan

class PlanRequest(BaseModel):
    mode: str = Field(pattern="^(cheapest|greenest)$")


def latest(conn):
    r = conn.execute("SELECT * FROM plan WHERE id=1").fetchone()
    if not r:
        return None
    return {**json.loads(r["result"]), "created_at": r["created_at"], "reviewed_by": r["reviewed_by"], "reviewed_at": r["reviewed_at"]}


@app.post("/api/plan")
def create_plan(body: PlanRequest, conn=Depends(get_conn)):
    s = db.settings(conn)
    items = db.items(conn)
    try:
        result = planner.make_plan(items, s, body.mode)
    except planner.PlanError as e:
        raise HTTPException(400, str(e))
    result["item_names"] = {it["id"]: it["name"] for it in items}
    conn.execute("INSERT OR REPLACE INTO plan (id, created_at, result) VALUES (1, ?, ?)", (now(), json.dumps(result)))
    conn.commit()
    return latest(conn)


@app.get("/api/plan")
def get_plan(conn=Depends(get_conn)):
    return latest(conn)


class Review(BaseModel):
    name: str = Field(min_length=2, max_length=60)


@app.post("/api/plan/review")
def review(body: Review, conn=Depends(get_conn)):
    if not latest(conn):
        raise HTTPException(400, "Create a plan first.")
    conn.execute("UPDATE plan SET reviewed_by=?, reviewed_at=? WHERE id=1", (body.name.strip(), now()))
    conn.commit()
    return latest(conn)


@app.get("/api/plan.csv")
def plan_csv(conn=Depends(get_conn)):
    p = latest(conn)
    if not p:
        raise HTTPException(404, "No plan yet.")
    out = io.StringIO()
    w = csv.writer(out)
    status = f"Checked by {p['reviewed_by']} on {p['reviewed_at']}" if p["reviewed_by"] else "NOT CHECKED YET - do not place orders"
    w.writerow(["Status", status])
    w.writerow([])
    w.writerow(["Order in week", "Item", "Quantity", "Small trucks", "Large trucks"])
    names = {int(k): v for k, v in p["item_names"].items()}
    for o in p["plan"]["orders"]:
        w.writerow([o["week"], names.get(o["item_id"], o["item_id"]), o["qty"], o["small"], o["large"]])
    w.writerow([])
    t = p["plan"]["totals"]
    for k in ("total_cost", "transport", "co2_kg", "service_pct"):
        w.writerow([k, t[k]])
    return Response(out.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="order_plan.csv"'})


# ---------------------------------------------------------------- dashboard

@app.get("/api/dashboard")
def dashboard(conn=Depends(get_conn)):
    s = db.settings(conn)
    rows = [item_view(it, s) for it in db.items(conn)]
    return {"items": rows, "plan": latest(conn), "currency": s["currency_symbol"],
            "stock_value": sum(r["stock_value"] for r in rows),
            "urgent": [r["name"] for r in rows if r["status"] == "urgent"],
            "order_soon": [r["name"] for r in rows if r["status"] == "order soon"]}


# ---------------------------------------------------------------- delivery calculator

class DeliveryRequest(BaseModel):
    from_place: str = Field(min_length=2)
    to_place: str = Field(min_length=2)
    weight_kg: float = Field(gt=0, le=500000)


@app.post("/api/delivery")
def delivery(body: DeliveryRequest, conn=Depends(get_conn)):
    s = db.settings(conn)
    try:
        a = routing.find_place(s["nominatim_url"], body.from_place)
        b = routing.find_place(s["nominatim_url"], body.to_place)
        route = routing.road_route(s["osrm_url"], a, b)
    except routing.RoutingError as e:
        raise HTTPException(400, str(e))
    options = calc.delivery_options(body.weight_kg, route["distance_km"], s["fuel_price"])
    greenest = min(options, key=lambda o: o["co2_kg"])["option"]
    cheapest = min(options, key=lambda o: o["cost"])["option"]
    return {"from": a, "to": b, **route, "options": options, "greenest": greenest, "cheapest": cheapest}


# ---------------------------------------------------------------- website

DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def site(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
