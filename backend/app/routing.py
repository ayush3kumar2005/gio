"""Road distance between two places using free OpenStreetMap services:
Nominatim (place name -> coordinates) and OSRM (shortest road route)."""
import httpx

HEADERS = {"User-Agent": "GreenInventoryOptimizer/1.0 (student project)"}


class RoutingError(Exception):
    pass


def find_place(base_url, name):
    try:
        r = httpx.get(f"{base_url}/search", params={"q": name, "format": "json", "limit": 1}, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        raise RoutingError("Could not reach the map service. Check your internet connection.")
    if not data:
        raise RoutingError(f"Place not found: '{name}'. Try adding the state or country.")
    return {"name": data[0]["display_name"], "lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}


def parse_route(payload):
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError("No road route found between these places.")
    r = payload["routes"][0]
    return {"distance_km": round(r["distance"] / 1000, 1), "hours": round(r["duration"] / 3600, 1),
            "geometry": r["geometry"]["coordinates"]}


def road_route(base_url, a, b):
    url = f"{base_url}/route/v1/driving/{a['lon']},{a['lat']};{b['lon']},{b['lat']}"
    try:
        r = httpx.get(url, params={"overview": "simplified", "geometries": "geojson"}, headers=HEADERS, timeout=20)
        payload = r.json()
    except (httpx.HTTPError, ValueError):
        raise RoutingError("Could not reach the routing service. Check your internet connection.")
    return parse_route(payload)
