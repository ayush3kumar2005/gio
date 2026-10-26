import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/** points: [{lat, lon, label, kind}], lines: [{coords: [[lon,lat],...], color, weight, dashed, label}] */
export default function MapView({ points = [], lines = [], height = 360 }) {
  const el = useRef(null);
  const map = useRef(null);
  const layer = useRef(null);

  useEffect(() => {
    map.current = L.map(el.current, { scrollWheelZoom: false }).setView([20.5, 78.9], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map.current);
    layer.current = L.layerGroup().addTo(map.current);
    return () => map.current.remove();
  }, []);

  useEffect(() => {
    const g = layer.current;
    g.clearLayers();
    const bounds = [];
    lines.forEach((ln) => {
      if (!ln.coords?.length) return;
      const ll = ln.coords.map(([lon, lat]) => [lat, lon]);
      L.polyline(ll, { color: ln.color || "#047857", weight: ln.weight || 4, opacity: 0.85, dashArray: ln.dashed ? "6 8" : null })
        .bindTooltip(ln.label || "").addTo(g);
      bounds.push(...ll);
    });
    points.forEach((p) => {
      if (p.lat == null || p.lon == null) return;
      const color = p.kind === "plant" ? "#047857" : p.kind === "supplier" ? "#2563eb" : "#d97706";
      L.circleMarker([p.lat, p.lon], { radius: p.kind === "plant" ? 9 : 7, color: "#fff", weight: 2, fillColor: color, fillOpacity: 1 })
        .bindTooltip(p.label || "").addTo(g);
      bounds.push([p.lat, p.lon]);
    });
    if (bounds.length) map.current.fitBounds(bounds, { padding: [30, 30], maxZoom: 11 });
  }, [points, lines]);

  return <div ref={el} style={{ height }} className="w-full rounded-lg border border-ink-200" role="img" aria-label="Map of locations and routes" />;
}
