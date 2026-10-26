export async function api(path, method = "GET", body) {
  let res;
  try {
    res = await fetch(path, body instanceof FormData
      ? { method, body }
      : { method, headers: body ? { "Content-Type": "application/json" } : {}, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new Error("Cannot reach the server. Is it running?");
  }
  const data = (res.headers.get("content-type") || "").includes("json") ? await res.json() : null;
  if (!res.ok) {
    let msg = data?.detail;
    if (Array.isArray(msg)) msg = msg.map((d) => `${d.loc.at(-1).replaceAll("_", " ")}: ${d.msg}`).join("; ");
    throw new Error(msg || "Something went wrong");
  }
  return data;
}

export const num = (v, d = 0) => (v == null ? "—" : Number(v).toLocaleString("en-IN", { maximumFractionDigits: d }));
export const money = (v, cur = "₹") => (v == null ? "—" : `${v < 0 ? "−" : ""}${cur}${Math.abs(Math.round(v)).toLocaleString("en-IN")}`);
