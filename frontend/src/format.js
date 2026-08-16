export function formatAdt(value, suspect) {
  if (!value) return "No traffic count";
  const n = Number(value);
  const text =
    n >= 10000 ? `${Math.round(n / 1000)}k / day` : `${n.toLocaleString()} / day`;
  return suspect ? `${text} (reported)` : text;
}

export function formatDriveTime(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.round(total / 60);
  if (minutes < 1) return "Under 1 min";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (rest === 0) return hours === 1 ? "1 hr" : `${hours} hr`;
  return `${hours} hr ${rest} min`;
}

export function formatDriveDistance(meters) {
  const miles = Number(meters || 0) / 1609.344;
  if (miles < 0.1) return `${Math.max(1, Math.round(Number(meters || 0) / 0.3048))} ft`;
  if (miles < 10) return `${miles.toFixed(1)} mi`;
  return `${Math.round(miles).toLocaleString()} mi`;
}

export function formatEta(seconds, now = new Date()) {
  const eta = new Date(now.getTime() + Math.max(0, Number(seconds) || 0) * 1000);
  return eta.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
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

/** Official NBI 0–9 words. Same table the API sends as ratings[k].word. */
export const CONDITION_WORDS = {
  9: "Excellent",
  8: "Very good",
  7: "Good",
  6: "Satisfactory",
  5: "Fair",
  4: "Poor",
  3: "Serious",
  2: "Critical",
  1: "Imminent failure",
  0: "Failed",
};

/**
 * Official G/F/P on the map. Christopher chose the original Good green
 * and Fair gold. Poor remains the one red accent for ratings ≤4.
 */
export const CONDITION_COLORS = {
  P: "#b42318",
  F: "#c4a84a",
  G: "#5c7a52",
  U: "#c7c7cc",
};

export const COPY = {
  rankNote:
    "A ranking from the worst inspector rating and daily traffic. Not an official grade.",
  ratingNote: "Inspector ratings, 0 to 9. Higher is better.",
  zoomHint: "No structures in this view.",
  emptyFilter: "No structures in view for the selected conditions.",
  emptyWorst: "No low scores in this view.",
  inventoryEmpty: "Inventory is not loaded.",
  inventoryDown: "Inventory is unavailable.",
  pulseLabel: "Daily crossings on Poor",
  pulseMove: "Move the map. The count is for this view.",
  poorDefinition: "Poor means a major component scored 4 or below.",
  tagline: "The National Bridge Inventory, starting with the one under you.",
  scoreMeta: "/ 100 · higher is better",
  scoreHeading: "Score",
  nearest: "Nearest",
  lowestScores: "Lowest scores in view",
  drive: "Drive",
  driveStart: "Start",
  driveEnd: "End",
  driveHere: "Your location",
  driveCenter: "Map center",
  driveDrop: "Drop points on the map",
  driveDropHint: "Tap the start, then the end.",
  driveUse: "Use this drive",
  driveClear: "Clear",
  driveLooking: "Looking up the route.",
  driveNone: "No driving route for these points.",
  driveDown: "Routing is unavailable.",
  driveBridges: "Bridges on this drive",
  driveEmpty: "No structures on this drive.",
};

export const RANK_NOTE = COPY.rankNote;
export const RATING_NOTE = COPY.ratingNote;

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

export function officialCondition(code) {
  if (code === "G" || code === "F" || code === "P") return code;
  return "U";
}

export function conditionVisible(bridge, codes) {
  const code = officialCondition(bridge?.condition);
  if (code === "U") return true;
  return codes.includes(code);
}

export function conditionClass(bridge) {
  const restricted = ["K", "P", "R", "D"].includes(bridge.status);
  const code = officialCondition(bridge.condition);
  return `dot ${code}${restricted ? " restricted" : ""}`;
}

/** Official NBI band for a 0–9 inspector rating. Null is not Good. */
export function ratingBand(value) {
  if (value == null || Number.isNaN(Number(value))) return "Unknown";
  const n = Number(value);
  if (n <= 4) return "Poor";
  if (n <= 6) return "Fair";
  return "Good";
}

export function ratingWord(value, apiWord) {
  if (apiWord) return apiWord;
  if (value == null || Number.isNaN(Number(value))) return "Unknown";
  return CONDITION_WORDS[Number(value)] || "Unknown";
}

export function ratingIsPoor(value) {
  return value != null && !Number.isNaN(Number(value)) && Number(value) <= 4;
}

/** Component bar class. Poor-red only when the rating itself is Poor. */
export function ratingClass(value) {
  return ratingIsPoor(value) ? "rating is-poor" : "rating";
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
