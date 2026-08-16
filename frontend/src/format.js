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

export const SCORE_BANDS = [
  { min: 85, label: "Few concerns" },
  { min: 70, label: "Some concerns" },
  { min: 55, label: "Moderate concerns" },
  { min: 40, label: "Elevated concerns" },
  { min: 0, label: "Significant concerns" },
];

export function scoreBand(score) {
  if (score == null || Number.isNaN(Number(score))) return null;
  const n = Number(score);
  for (const band of SCORE_BANDS) {
    if (n >= band.min) return band.label;
  }
  return "Significant concerns";
}

export function formatBuilt(year, ageYears) {
  if (!year) return null;
  if (ageYears != null && ageYears >= 0) {
    const years = Number(ageYears) === 1 ? "1 year old" : `${ageYears} years old`;
    return `Built ${year} · ${years}`;
  }
  return `Built ${year}`;
}

export const COPY = {
  rankNote:
    "A ranking from official condition ratings and other reported factors. Not an official grade.",
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
  scoreHeading: "Bridge Score",
  scoreShort: "Score",
  scoreHigher: "Higher is better",
  scoreExplainer:
    "Calculated by this site from NBI condition ratings, restrictions, vulnerability flags, inspection timing, and traffic. Not an official safety grade.",
  scoreNote:
    "A site-generated score based on public NBI condition ratings and other reported factors. Lower scores mean the bridge stands out more in the inventory. This is not an official safety grade.",
  meaning: "What this means",
  standout: "Why it stands out",
  whyScore: "Why this score",
  facts: "Bridge facts",
  source: "Source",
  methodology: "Methodology",
  methodologyBody:
    "FHWA supplies the official inspection ratings and Good/Fair/Poor condition. This site calculates the 0–100 Bridge Score to make bridges easier to compare. The score is not an FHWA grade, engineering inspection, or safety determination. NBI data may lag newer state or local records.",
  sourceLine: "FHWA National Bridge Inventory via BTS NTAD",
  nearest: "Nearest",
  lowestScores: "Lowest scores in view",
  drive: "Drive",
  driveAction: "Start a drive",
  driveStart: "Start",
  driveEnd: "End",
  driveHere: "Your location",
  driveCenter: "Map center",
  driveDrop: "Drop points on the map",
  driveDropHint: "Tap the map to set the next point.",
  driveUse: "Use this drive",
  driveBack: "Back",
  driveClear: "Clear",
  driveLooking: "Looking up the route.",
  driveNone: "No driving route for these points.",
  driveDown: "Routing is unavailable.",
  driveBridges: "Bridges on this drive",
  driveEmpty: "No structures on this drive.",
  driveWorst: "Worst on this drive",
  driveFollow: "Follow",
  locate: "My location",
  locationDenied: "Location is off for this site. Enable it in Safari or Settings.",
  locationPreciseOff: "Precise location is unavailable.",
  driveLocating: "Finding your location.",
  approachDismiss: "Dismiss",
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

/** Which trip end a map tap should set. Never clears the other end. */
export function nextDropSlot(start, end, editing) {
  if (editing === "start" || editing === "end") return editing;
  if (!start) return "start";
  return "end";
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

const EMPTY_DRIVE_BRIDGES = [];

/**
 * Which bridges the map should paint.
 * A drive uses only `/api/drive` `bridges` (Poor is never dropped from that list).
 * Null means keep the viewport overlay.
 */
export function driveBridgesForMap({ route, bridges, tripOpen, lastBridges } = {}) {
  if (route) return Array.isArray(bridges) ? bridges : EMPTY_DRIVE_BRIDGES;
  if (tripOpen && lastBridges != null) return lastBridges;
  return null;
}

/** FeatureCollection for drive pins. Same properties the viewport overlay uses. */
export function driveBridgesGeojson(bridges) {
  const features = [];
  for (const bridge of Array.isArray(bridges) ? bridges : []) {
    if (!bridge?.id || !Number.isFinite(bridge.lng) || !Number.isFinite(bridge.lat)) {
      continue;
    }
    features.push({
      type: "Feature",
      id: bridge.id,
      geometry: {
        type: "Point",
        coordinates: [bridge.lng, bridge.lat],
      },
      properties: {
        id: bridge.id,
        condition: bridge.condition,
        lowest: bridge.lowest,
        score: bridge.score,
        status: bridge.status,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export function mapDotsCollection(viewportGeojson, driveBridges) {
  if (driveBridges != null) return driveBridgesGeojson(driveBridges);
  return viewportGeojson;
}

/** Official Poor first, then lowest public score, then lowest inspector rating. */
export function pickWorstOnDrive(bridges, n = 3) {
  const rows = Array.isArray(bridges) ? [...bridges] : [];
  rows.sort((a, b) => {
    const ap = officialCondition(a?.condition) === "P" ? 0 : 1;
    const bp = officialCondition(b?.condition) === "P" ? 0 : 1;
    if (ap !== bp) return ap - bp;
    const as = a?.score == null ? 100 : Number(a.score);
    const bs = b?.score == null ? 100 : Number(b.score);
    if (as !== bs) return as - bs;
    const al = a?.lowest == null ? 99 : Number(a.lowest);
    const bl = b?.lowest == null ? 99 : Number(b.lowest);
    return al - bl;
  });
  return rows.slice(0, n);
}

export function metersBetween(a, b) {
  return kmBetween(a, b) * 1000;
}

function toRad(deg) {
  return (deg * Math.PI) / 180;
}

export function bearingDegrees(from, to) {
  if (!from || !to) return 0;
  const y = Math.sin(toRad(to.lng - from.lng)) * Math.cos(toRad(to.lat));
  const x =
    Math.cos(toRad(from.lat)) * Math.sin(toRad(to.lat)) -
    Math.sin(toRad(from.lat)) *
      Math.cos(toRad(to.lat)) *
      Math.cos(toRad(to.lng - from.lng));
  return (Math.atan2(y, x) * 180) / Math.PI;
}

function projectT(lng, lat, a, b) {
  const [ax, ay] = a;
  const [bx, by] = b;
  const dx = bx - ax;
  const dy = by - ay;
  const den = dx * dx + dy * dy;
  if (den <= 0) return 0;
  const t = ((lng - ax) * dx + (lat - ay) * dy) / den;
  return Math.max(0, Math.min(1, t));
}

export function pointAlongRoute(lng, lat, coordinates) {
  if (!coordinates?.length) return 0;
  if (coordinates.length === 1) return 0;
  const segs = [];
  let total = 0;
  for (let i = 0; i < coordinates.length - 1; i += 1) {
    const a = coordinates[i];
    const b = coordinates[i + 1];
    const d = metersBetween(
      { lng: a[0], lat: a[1] },
      { lng: b[0], lat: b[1] }
    );
    segs.push({ d, a, b });
    total += d;
  }
  if (total <= 0) return 0;
  let best = { dist: Infinity, along: 0 };
  let walked = 0;
  for (const seg of segs) {
    const t = projectT(lng, lat, seg.a, seg.b);
    const pt = [seg.a[0] + (seg.b[0] - seg.a[0]) * t, seg.a[1] + (seg.b[1] - seg.a[1]) * t];
    const dist = metersBetween({ lng, lat }, { lng: pt[0], lat: pt[1] });
    if (dist < best.dist) best = { dist, along: walked + t * seg.d };
    walked += seg.d;
  }
  return best.along / total;
}

export function routeHeadingAt(along01, coordinates) {
  if (!coordinates || coordinates.length < 2) return 0;
  const segs = [];
  let total = 0;
  for (let i = 0; i < coordinates.length - 1; i += 1) {
    const a = coordinates[i];
    const b = coordinates[i + 1];
    const d = metersBetween(
      { lng: a[0], lat: a[1] },
      { lng: b[0], lat: b[1] }
    );
    segs.push({ d, a, b });
    total += d;
  }
  if (total <= 0) return 0;
  let target = Math.min(1, Math.max(0, along01)) * total + 12;
  if (target > total) target = total;
  let walked = 0;
  for (const seg of segs) {
    if (walked + seg.d >= target || walked + seg.d === total) {
      return bearingDegrees(
        { lng: seg.a[0], lat: seg.a[1] },
        { lng: seg.b[0], lat: seg.b[1] }
      );
    }
    walked += seg.d;
  }
  const last = segs[segs.length - 1];
  return bearingDegrees(
    { lng: last.a[0], lat: last.a[1] },
    { lng: last.b[0], lat: last.b[1] }
  );
}

export function formatManeuver(step) {
  if (!step) return "Continue";
  const name = (step.name || step.ref || "").trim();
  const type = step.type || "continue";
  const turn = {
    left: "Left",
    right: "Right",
    "sharp left": "Sharp left",
    "sharp right": "Sharp right",
    "slight left": "Slight left",
    "slight right": "Slight right",
    straight: "Continue",
    uturn: "U-turn",
  }[step.modifier] || "";
  if (type === "arrive") return "Arrive";
  if (type === "depart") return name ? `Start on ${name}` : "Start";
  if (type === "merge") return name ? `Merge onto ${name}` : "Merge";
  if (type === "on ramp") return name ? `Onto ${name}` : "On ramp";
  if (type === "off ramp") return name ? `Exit toward ${name}` : "Exit";
  if (type === "fork") return turn && name ? `${turn} fork onto ${name}` : "Fork";
  if (type === "roundabout") return name ? `Roundabout onto ${name}` : "Roundabout";
  if (type === "new name" || type === "continue") {
    return name ? `Continue on ${name}` : "Continue";
  }
  if (turn && name) return `${turn} on ${name}`;
  if (turn) return turn;
  return name || "Continue";
}

export function navBanner(steps, along01, routeM) {
  if (!steps?.length || !routeM) return null;
  const traveled = Math.min(1, Math.max(0, along01)) * routeM;
  let acc = 0;
  let index = 0;
  for (let i = 0; i < steps.length; i += 1) {
    const end = acc + (Number(steps[i].distance_m) || 0);
    if (traveled <= end + 8) {
      index = i;
      const remaining = Math.max(0, end - traveled);
      if (remaining < 35 && i < steps.length - 1) {
        return {
          text: formatManeuver(steps[i + 1]),
          distance_m: remaining,
          step: steps[i + 1],
        };
      }
      return {
        text: formatManeuver(steps[i]),
        distance_m: remaining,
        step: steps[i],
      };
    }
    acc = end;
    index = i;
  }
  const last = steps[index];
  return { text: formatManeuver(last), distance_m: 0, step: last };
}

export const APPROACH_WINDOW_M = 280;
export const APPROACH_PAST_M = 40;

export function pickApproachingBridge({
  bridges,
  worstIds,
  along,
  routeM,
  dismissedIds,
} = {}) {
  if (!bridges?.length || !routeM) return null;
  const worst = new Set(worstIds || []);
  const dismissed = dismissedIds || new Set();
  const ranked = [];
  for (const bridge of bridges) {
    if (!bridge?.id || dismissed.has(bridge.id) || bridge.along == null) continue;
    const delta = (Number(bridge.along) - along) * routeM;
    if (delta > APPROACH_WINDOW_M || delta < -APPROACH_PAST_M) continue;
    ranked.push({ bridge, delta });
  }
  ranked.sort((a, b) => {
    const ap = officialCondition(a.bridge.condition) === "P" ? 0 : 1;
    const bp = officialCondition(b.bridge.condition) === "P" ? 0 : 1;
    if (ap !== bp) return ap - bp;
    const aw = worst.has(a.bridge.id) ? 0 : 1;
    const bw = worst.has(b.bridge.id) ? 0 : 1;
    if (aw !== bw) return aw - bw;
    return a.delta - b.delta;
  });
  return ranked[0]?.bridge ?? null;
}
