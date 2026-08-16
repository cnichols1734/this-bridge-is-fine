import assert from "node:assert/strict";
import test from "node:test";
import {
  CONDITION_COLORS,
  CONDITION_WORDS,
  COPY,
  RANK_NOTE,
  RATING_NOTE,
  conditionClass,
  conditionVisible,
  driveBridgesForMap,
  driveBridgesGeojson,
  formatDriveDistance,
  formatDriveTime,
  formatEta,
  formatManeuver,
  mapDotsCollection,
  navBanner,
  nextDropSlot,
  pickApproachingBridge,
  pickWorstOnDrive,
  pointAlongRoute,
  officialCondition,
  ratingBand,
  ratingClass,
  ratingIsPoor,
  ratingWord,
} from "./format.js";

const FORBIDDEN = [
  "Looks fine",
  "Worth a look",
  "Serious shape",
  "Bad shape",
  "Yours first",
  "about to fall",
  "Run the ingest",
];

test("Good / 7 is not Poor-red", () => {
  assert.equal(ratingBand(7), "Good");
  assert.equal(ratingWord(7), "Good");
  assert.equal(ratingIsPoor(7), false);
  assert.equal(ratingClass(7), "rating");
  assert.doesNotMatch(ratingClass(7), /is-poor|is-low/);
});

test("Very good / 8 and Excellent / 9 stay off the Poor-red bar", () => {
  for (const n of [8, 9]) {
    assert.equal(ratingBand(n), "Good");
    assert.equal(ratingIsPoor(n), false);
    assert.equal(ratingClass(n), "rating");
  }
});

test("Poor / 4 and below use Poor-red", () => {
  for (const n of [4, 3, 2, 1, 0]) {
    assert.equal(ratingBand(n), "Poor");
    assert.equal(ratingIsPoor(n), true);
    assert.equal(ratingClass(n), "rating is-poor");
  }
});

test("Fair ratings are not Poor-red", () => {
  for (const n of [5, 6]) {
    assert.equal(ratingBand(n), "Fair");
    assert.equal(ratingIsPoor(n), false);
    assert.equal(ratingClass(n), "rating");
  }
});

test("unknown rating is not Good and is not Poor-red", () => {
  assert.equal(ratingBand(null), "Unknown");
  assert.equal(ratingBand(undefined), "Unknown");
  assert.equal(ratingWord(null), "Unknown");
  assert.equal(ratingIsPoor(null), false);
  assert.equal(ratingClass(null), "rating");
  assert.equal(officialCondition(null), "U");
  assert.equal(officialCondition(""), "U");
  assert.equal(officialCondition("G"), "G");
});

test("prefers the API condition word when present", () => {
  assert.equal(ratingWord(8, "Very good"), "Very good");
  assert.equal(ratingWord(3, "Serious"), "Serious");
  assert.equal(ratingWord(1, "Imminent failure"), "Imminent failure");
  assert.equal(ratingWord(7), CONDITION_WORDS[7]);
});

test("unknown official condition is not treated as Good", () => {
  assert.equal(conditionVisible({ condition: null }, ["G"]), true);
  assert.equal(conditionVisible({ condition: "G" }, ["F", "P"]), false);
  assert.equal(conditionVisible({ condition: "P" }, ["P"]), true);
  assert.equal(conditionClass({ condition: null, status: "A" }), "dot U");
  assert.equal(conditionClass({ condition: "G", status: "A" }), "dot G");
  assert.doesNotMatch(conditionClass({ condition: null }), /\bG\b/);
});

test("official G/F/P dots use the original Good green and Fair gold", () => {
  assert.equal(CONDITION_COLORS.P, "#b42318");
  assert.equal(CONDITION_COLORS.G, "#5c7a52");
  assert.equal(CONDITION_COLORS.F, "#c4a84a");
  assert.equal(CONDITION_COLORS.U, "#c7c7cc");
});

test("user-facing strings stay dry and civic", () => {
  const blob = [RANK_NOTE, RATING_NOTE, ...Object.values(COPY)].join("\n");
  for (const phrase of FORBIDDEN) {
    assert.ok(!blob.includes(phrase), phrase);
  }
  assert.doesNotMatch(blob, /\bsafe\b/i);
  assert.doesNotMatch(blob, /★/);
  assert.match(COPY.poorDefinition, /scored 4 or below/);
  assert.match(COPY.rankNote, /Not an official grade/);
  assert.equal(COPY.driveUse, "Use this drive");
  assert.equal(COPY.driveAction, "Start a drive");
  assert.equal(COPY.driveBack, "Back");
  assert.equal(COPY.driveWorst, "Worst on this drive");
  assert.equal(COPY.driveNone, "No driving route for these points.");
  assert.equal(COPY.driveDown, "Routing is unavailable.");
  assert.equal(COPY.locationDenied, "Location is off. Using the map center.");
  assert.equal(COPY.locationApproximate, "Location is approximate. Using the map center.");
  assert.equal(COPY.driveLocating, "Finding your location.");
  assert.equal(COPY.locate, "My location");
  assert.doesNotMatch(COPY.drive, /!/);
  assert.doesNotMatch(COPY.driveAction, /!/);
});

test("drop points fill the next empty end and do not imply a wipe", () => {
  assert.equal(nextDropSlot(null, null, null), "start");
  assert.equal(nextDropSlot({ label: "A" }, null, null), "end");
  assert.equal(nextDropSlot({ label: "A" }, { label: "B" }, null), "end");
  assert.equal(nextDropSlot({ label: "A" }, { label: "B" }, "start"), "start");
  assert.equal(nextDropSlot(null, { label: "B" }, "end"), "end");
});

test("drive overlay uses only the drive list, including every Poor", () => {
  const viewport = {
    type: "FeatureCollection",
    features: [
      { properties: { id: "48-HOUSTON" } },
      { properties: { id: "48-GALVESTON" } },
    ],
  };
  const drive = [
    {
      id: "48-POOR-1",
      lng: -95.37,
      lat: 29.76,
      condition: "P",
      lowest: 4,
      score: 22,
      status: "A",
    },
    {
      id: "48-POOR-2",
      lng: -95.4,
      lat: 29.8,
      condition: "P",
      lowest: 3,
      score: 18,
      status: "A",
    },
    {
      id: "48-GOOD",
      lng: -95.35,
      lat: 29.72,
      condition: "G",
      lowest: 7,
      score: 80,
      status: "A",
    },
  ];

  assert.equal(driveBridgesForMap({ tripOpen: false }), null);
  assert.equal(mapDotsCollection(viewport, null), viewport);

  const listed = driveBridgesForMap({
    route: { type: "LineString", coordinates: [[-95.3, 29.7], [-94.8, 29.3]] },
    bridges: drive,
  });
  assert.deepEqual(
    listed.map((bridge) => bridge.id),
    ["48-POOR-1", "48-POOR-2", "48-GOOD"]
  );
  const overlay = mapDotsCollection(viewport, listed);
  assert.deepEqual(
    overlay.features.map((feature) => feature.properties.id),
    ["48-POOR-1", "48-POOR-2", "48-GOOD"]
  );
  assert.equal(overlay.features[0].properties.condition, "P");
  assert.equal(overlay.features[2].properties.condition, "G");
  assert.ok(!overlay.features.some((feature) => feature.properties.id === "48-HOUSTON"));
});

test("empty drive list does not fall back to the viewport spray", () => {
  const viewport = {
    type: "FeatureCollection",
    features: [{ properties: { id: "17-CITY" } }],
  };
  const listed = driveBridgesForMap({
    route: { type: "LineString", coordinates: [[-87.6, 41.8], [-87.7, 42.0]] },
    bridges: [],
  });
  assert.deepEqual(listed, []);
  assert.deepEqual(mapDotsCollection(viewport, listed), {
    type: "FeatureCollection",
    features: [],
  });
});

test("leaving Drive returns the viewport collection", () => {
  const viewport = { type: "FeatureCollection", features: [{ properties: { id: "17-A" } }] };
  const last = [{ id: "17-DRIVE", lng: -87.6, lat: 41.8, condition: "P" }];
  assert.deepEqual(
    driveBridgesForMap({
      tripOpen: true,
      lastBridges: last,
    }),
    last
  );
  assert.equal(
    driveBridgesForMap({
      tripOpen: false,
      lastBridges: last,
    }),
    null
  );
  assert.equal(mapDotsCollection(viewport, null), viewport);
});

test("drive geojson keeps official condition codes for existing colors", () => {
  const geojson = driveBridgesGeojson([
    { id: "1-P", lng: -87.6, lat: 41.8, condition: "P", status: "A" },
    { id: "1-F", lng: -87.61, lat: 41.81, condition: "F", status: "A" },
    { id: "1-G", lng: -87.62, lat: 41.82, condition: "G", status: "A" },
    { id: "1-BAD", lng: null, lat: 41.8, condition: "P" },
  ]);
  assert.deepEqual(
    geojson.features.map((feature) => feature.properties.condition),
    ["P", "F", "G"]
  );
  assert.equal(CONDITION_COLORS[geojson.features[0].properties.condition], "#b42318");
  assert.equal(CONDITION_COLORS[geojson.features[1].properties.condition], "#c4a84a");
  assert.equal(CONDITION_COLORS[geojson.features[2].properties.condition], "#5c7a52");
});

test("top three worst prefer Poor then lowest score", () => {
  const worst = pickWorstOnDrive(
    [
      { id: "g-ok", condition: "G", score: 90, lowest: 8 },
      { id: "f-mid", condition: "F", score: 60, lowest: 5 },
      { id: "p-quiet", condition: "P", score: 80, lowest: 4 },
      { id: "p-bad", condition: "P", score: 30, lowest: 3 },
      { id: "g-busy", condition: "G", score: 10, lowest: 7 },
    ],
    3
  );
  assert.deepEqual(
    worst.map((bridge) => bridge.id),
    ["p-bad", "p-quiet", "g-busy"]
  );
});

test("maneuver copy stays civic", () => {
  assert.equal(
    formatManeuver({ type: "turn", modifier: "right", name: "Lake Shore Drive" }),
    "Right on Lake Shore Drive"
  );
  assert.equal(formatManeuver({ type: "merge", name: "I 90" }), "Merge onto I 90");
  assert.equal(formatManeuver({ type: "arrive" }), "Arrive");
  assert.doesNotMatch(formatManeuver({ type: "turn", modifier: "left", name: "Main" }), /!/);
});

test("nav banner uses the upcoming turn when the current step is almost done", () => {
  const steps = [
    { type: "continue", name: "Main Street", distance_m: 100 },
    { type: "turn", modifier: "left", name: "Oak", distance_m: 400 },
  ];
  const banner = navBanner(steps, 0.92, 100);
  assert.equal(banner.text, "Left on Oak");
  assert.ok(banner.distance_m < 35);
});

test("along-route progress is 0 at the start and 1 at the end", () => {
  const line = [
    [-87.63, 41.88],
    [-87.63, 41.89],
  ];
  assert.ok(pointAlongRoute(-87.63, 41.88, line) < 0.05);
  assert.ok(pointAlongRoute(-87.63, 41.89, line) > 0.95);
});

test("approaching callout prefers Poor and ignores dismissed", () => {
  const bridges = [
    { id: "g", condition: "G", along: 0.25, score: 80 },
    { id: "p", condition: "P", along: 0.22, score: 40 },
    { id: "f", condition: "F", along: 0.21, score: 50 },
  ];
  const hit = pickApproachingBridge({
    bridges,
    worstIds: ["p"],
    along: 0.18,
    routeM: 2000,
  });
  assert.equal(hit.id, "p");
  const skipped = pickApproachingBridge({
    bridges,
    worstIds: ["p"],
    along: 0.18,
    routeM: 2000,
    dismissedIds: new Set(["p"]),
  });
  assert.equal(skipped.id, "f");
  const past = pickApproachingBridge({
    bridges,
    along: 0.4,
    routeM: 2000,
  });
  assert.equal(past, null);
});

test("drive time, distance, and ETA stay precise", () => {
  assert.equal(formatDriveTime(20), "Under 1 min");
  assert.equal(formatDriveTime(12 * 60), "12 min");
  assert.equal(formatDriveTime(72 * 60), "1 hr 12 min");
  assert.equal(formatDriveTime(120 * 60), "2 hr");
  assert.equal(formatDriveDistance(80), "262 ft");
  assert.equal(formatDriveDistance(8851), "5.5 mi");
  assert.equal(formatDriveDistance(22116.6), "14 mi");
  assert.equal(formatDriveDistance(238000), "148 mi");
  assert.match(
    formatEta(90 * 60, new Date("2026-08-16T15:00:00")),
    /4:30/
  );
});
