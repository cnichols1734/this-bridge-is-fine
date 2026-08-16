export function formatAdt(value, suspect) {
  if (!value) return "No traffic count";
  const n = Number(value);
  const text =
    n >= 10000 ? `${Math.round(n / 1000)}k / day` : `${n.toLocaleString()} / day`;
  return suspect ? `${text} (reported)` : text;
}

export function formatCrossings(value) {
  const n = Number(value || 0);
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  return n.toLocaleString();
}

export function formatInspect(iso) {
  if (!iso) return "Unknown";
  const [year, month] = iso.split("-");
  const names = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  return `${names[Number(month) - 1] || month} ${year}`;
}

export function readPermalink() {
  const params = new URLSearchParams(window.location.search);
  const lat = Number(params.get("lat"));
  const lng = Number(params.get("lng"));
  const z = Number(params.get("z"));
  const id = params.get("id");
  return {
    lat: Number.isFinite(lat) ? lat : null,
    lng: Number.isFinite(lng) ? lng : null,
    z: Number.isFinite(z) ? z : null,
    id,
  };
}

export function writePermalink({ lat, lng, z, id }) {
  const params = new URLSearchParams();
  if (lat != null) params.set("lat", lat.toFixed(5));
  if (lng != null) params.set("lng", lng.toFixed(5));
  if (z != null) params.set("z", z.toFixed(2));
  if (id) params.set("id", id);
  const next = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState(null, "", next);
}

export const CHICAGO = { lng: -87.6298, lat: 41.8781, zoom: 11.2 };

export const CONDITION_FILTERS = [
  { code: "G", label: "Good" },
  { code: "F", label: "Fair" },
  { code: "P", label: "Poor" },
];

export const ALL_CONDITIONS = CONDITION_FILTERS.map((item) => item.code);

export function readConditionFilter() {
  try {
    const raw = localStorage.getItem("tbif-conditions");
    if (!raw) return [...ALL_CONDITIONS];
    const next = raw.split(",").filter((code) => ALL_CONDITIONS.includes(code));
    return next.length ? next : [...ALL_CONDITIONS];
  } catch {
    return [...ALL_CONDITIONS];
  }
}

export function writeConditionFilter(codes) {
  try {
    localStorage.setItem("tbif-conditions", codes.join(","));
  } catch {
    /* ignore */
  }
}

export function conditionVisible(bridge, codes) {
  return codes.includes(bridge.condition || "G");
}

export const RANK_NOTE =
  "Our own score, not an official grade. It drops when the bridge's worst part is in bad shape and a lot of people cross it.";

export const RATING_NOTE = "Inspector ratings, 0 to 9. Higher is better, same as our score.";

export function scoreBand(score) {
  if (score == null) return null;
  if (score >= 76) return { word: "Looks fine", short: "Fine", tone: "G" };
  if (score >= 51) return { word: "Worth a look", short: "Watch", tone: "F" };
  if (score >= 26) return { word: "Bad shape", short: "Bad", tone: "P" };
  return { word: "Serious shape", short: "Serious", tone: "P" };
}

export function ratingBand(value) {
  if (value == null) return "";
  if (value <= 4) return "Poor";
  if (value <= 6) return "Fair";
  return "Good";
}

export function kmBetween(a, b) {
  if (!a || !b) return Infinity;
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const sin =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(sin)));
}

export function viewIsAway(user, center, zoom, homeZoom = CHICAGO.zoom) {
  if (!user || !center) return false;
  return kmBetween(user, center) > 1.2 || Math.abs((zoom ?? homeZoom) - homeZoom) > 0.8;
}
