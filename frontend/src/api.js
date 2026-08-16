export async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return response.json();
}

export function bboxString(bounds) {
  const west = bounds.getWest();
  const south = bounds.getSouth();
  const east = bounds.getEast();
  const north = bounds.getNorth();
  return `${west},${south},${east},${north}`;
}

export function fetchViewport(bounds, zoom) {
  const bbox = bboxString(bounds);
  const q = new URLSearchParams({ bbox, zoom: String(zoom) });
  return Promise.all([
    getJson(`/api/bridges?${q}`),
    getJson(`/api/bridges/list?bbox=${encodeURIComponent(bbox)}`),
    getJson(`/api/worst?bbox=${encodeURIComponent(bbox)}&limit=10`),
    getJson(`/api/stats?bbox=${encodeURIComponent(bbox)}`),
  ]).then(([geojson, list, worst, stats]) => ({
    geojson,
    list: list.bridges || [],
    worst: worst.bridges || [],
    stats,
  }));
}

export function fetchBridge(id) {
  const dash = id.indexOf("-");
  if (dash < 0) throw new Error("bad id");
  const state = id.slice(0, dash);
  const structure = encodeURIComponent(id.slice(dash + 1));
  return getJson(`/api/bridges/${state}/${structure}`);
}

export function fetchMeta() {
  return getJson("/api/meta");
}

export function fetchHealth() {
  return getJson("/api/health");
}

export function fetchDrive(start, end) {
  const params = new URLSearchParams({
    from: `${start.lng},${start.lat}`,
    to: `${end.lng},${end.lat}`,
  });
  return getJson(`/api/drive?${params}`);
}

export function searchPlaces(q, near) {
  const query = q.trim();
  if (query.length < 2) return Promise.resolve([]);
  const params = new URLSearchParams({ q: query });
  if (near?.lat != null && near?.lng != null) {
    params.set("lat", String(near.lat));
    params.set("lng", String(near.lng));
  }
  return getJson(`/api/geocode?${params}`).then((body) => body.results || []);
}
