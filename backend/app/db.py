"""SQLite storage: items, a few settings and the latest plan."""
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("GIO_DB", Path(__file__).resolve().parent.parent / "gio.db"))

DEFAULT_SETTINGS = {
    "currency_symbol": "₹",
    "plant_city": "Chakan, Pune",
    "weeks": 8,                       # planning horizon
    "holding_pct": 20,                # yearly storage cost as % of item price
    "demand_variation_pct": 20,       # how much weekly demand usually varies
    "service_level_pct": 95,          # chance of not running out during lead time
    "shortage_cost_multiplier": 3,    # running out of 1 unit costs 3x its price (lost production)
    "fuel_price": 90,                 # diesel price per litre
    "time_limit_s": 20,
    "osrm_url": "https://router.project-osrm.org",
    "nominatim_url": "https://nominatim.openstreetmap.org",
}

ITEM_FIELDS = ["name", "unit", "stock", "weekly_demand", "price", "order_cost", "weight_kg", "lead_time_weeks", "distance_km"]

SAMPLE_ITEMS = [
    # name, unit, stock, weekly demand, price, order cost, kg per unit, lead time (weeks), supplier distance (km)
    ("Steel sheets", "sheets", 1400, 400, 1950, 3500, 29.4, 1, 112),
    ("Aluminium rods", "rods", 520, 120, 2300, 3000, 8.2, 2, 638),
    ("Plastic granules", "bags", 150, 80, 2800, 1500, 25, 1, 16),
    ("Ball bearings", "pieces", 14000, 3000, 82, 2500, 0.13, 2, 1100),
    ("Paint", "boxes", 50, 25, 6400, 1200, 20, 1, 16),
    ("Cardboard boxes", "bundles", 260, 60, 900, 800, 10, 1, 16),
]


def connect():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, unit TEXT NOT NULL,
      stock REAL NOT NULL, weekly_demand REAL NOT NULL, price REAL NOT NULL, order_cost REAL NOT NULL,
      weight_kg REAL NOT NULL, lead_time_weeks INTEGER NOT NULL, distance_km REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS plan (id INTEGER PRIMARY KEY CHECK (id = 1), created_at TEXT, result TEXT,
      reviewed_by TEXT, reviewed_at TEXT);
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    if conn.execute("SELECT value FROM meta WHERE key='initialised'").fetchone() is None:
        load_sample(conn)
        conn.execute("INSERT INTO meta VALUES ('initialised', '1')")
    conn.commit()


def load_sample(conn):
    conn.execute("DELETE FROM items")
    conn.execute("DELETE FROM plan")
    conn.executemany(f"INSERT INTO items ({','.join(ITEM_FIELDS)}) VALUES ({','.join('?' * len(ITEM_FIELDS))})", SAMPLE_ITEMS)
    conn.commit()


def items(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM items ORDER BY id")]


def settings(conn):
    s = dict(DEFAULT_SETTINGS)
    for r in conn.execute("SELECT key, value FROM settings"):
        if r["key"] in s:
            s[r["key"]] = json.loads(r["value"])
    return s


def save_settings(conn, values):
    for k, v in values.items():
        if k in DEFAULT_SETTINGS:
            conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, json.dumps(v)))
    conn.commit()
