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
  formatDriveDistance,
  formatDriveTime,
  formatEta,
  nextDropSlot,
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
  assert.equal(COPY.driveBack, "Back");
  assert.equal(COPY.driveNone, "No driving route for these points.");
  assert.equal(COPY.driveDown, "Routing is unavailable.");
  assert.doesNotMatch(COPY.drive, /!/);
});

test("drop points fill the next empty end and do not imply a wipe", () => {
  assert.equal(nextDropSlot(null, null, null), "start");
  assert.equal(nextDropSlot({ label: "A" }, null, null), "end");
  assert.equal(nextDropSlot({ label: "A" }, { label: "B" }, null), "end");
  assert.equal(nextDropSlot({ label: "A" }, { label: "B" }, "start"), "start");
  assert.equal(nextDropSlot(null, { label: "B" }, "end"), "end");
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
