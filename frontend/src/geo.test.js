import assert from "node:assert/strict";
import test from "node:test";
import {
  COARSE_ACCURACY_M,
  FIRST_GEO,
  PRECISE_ACCURACY_M,
  PRECISE_GEO,
  getPrecisePosition,
  isCoarseFix,
  isPreciseFix,
  shouldAcceptFix,
  startPreciseWatch,
  waitForPreciseFix,
  watchPrecisePosition,
} from "./geo.js";

function coords({ lat = 29.76, lng = -95.37, accuracy = 15, heading = null, speed = null } = {}) {
  return {
    coords: {
      latitude: lat,
      longitude: lng,
      accuracy,
      heading,
      speed,
    },
    timestamp: Date.now(),
  };
}

function mockGeo() {
  let cb = null;
  const geo = {
    opts: null,
    firstOpts: null,
    currentCalls: 0,
    watchCalls: 0,
    getCurrentPosition(success, error, opts) {
      geo.currentCalls += 1;
      geo.firstOpts = opts;
      cb = { success, error };
    },
    watchPosition(success, error, opts) {
      geo.watchCalls += 1;
      geo.opts = opts;
      cb = { success, error };
      return 1;
    },
    clearWatch() {
      cb = null;
    },
    push(fix) {
      cb?.success(coords(fix));
    },
    fail(err) {
      cb?.error(err);
    },
  };
  return geo;
}

test("the watch asks for a new GPS lock; the first read may be cached", () => {
  assert.equal(PRECISE_GEO.enableHighAccuracy, true);
  assert.equal(PRECISE_GEO.maximumAge, 0);
  assert.ok(PRECISE_GEO.timeout >= 20000);
  assert.equal(FIRST_GEO.enableHighAccuracy, true);
  assert.ok(FIRST_GEO.maximumAge >= 15000);
});

test("startPreciseWatch calls geolocation in this turn, not after a then", () => {
  const geo = mockGeo();
  let returned = false;
  startPreciseWatch(() => {}, undefined, { geolocation: geo });
  returned = true;
  assert.equal(geo.currentCalls, 1);
  assert.equal(geo.watchCalls, 1);
  assert.equal(returned, true);
  assert.equal(geo.firstOpts.maximumAge, FIRST_GEO.maximumAge);
  assert.equal(geo.opts.maximumAge, 0);
});

test("hundreds of meters is coarse; tens of meters is GPS", () => {
  assert.equal(isCoarseFix({ accuracy: 400 }), true);
  assert.equal(isPreciseFix({ accuracy: 400 }), false);
  assert.equal(isPreciseFix({ accuracy: 18 }), true);
  assert.equal(isCoarseFix({ accuracy: 18 }), false);
  assert.ok(COARSE_ACCURACY_M >= 100);
  assert.ok(PRECISE_ACCURACY_M <= 80);
});

test("a GPS fix is not replaced by a later cell reading", () => {
  const gps = { lat: 29.76, lng: -95.37, accuracy: 15 };
  const cell = { lat: 29.764, lng: -95.374, accuracy: 400 };
  assert.equal(shouldAcceptFix(cell, gps), false);
  assert.equal(shouldAcceptFix(gps, cell), true);
});

test("uses a coarse reading immediately, then snaps to GPS", async () => {
  const geo = mockGeo();
  const seen = [];
  const pending = waitForPreciseFix({
    geolocation: geo,
    watchMs: 5000,
    setTimer: () => 1,
    clearTimer: () => {},
    onFix: (fix) => seen.push(fix.accuracy),
  });
  geo.push({ lat: 29.76, lng: -95.37, accuracy: 400 });
  assert.deepEqual(seen, [400]);
  geo.push({ lat: 29.761, lng: -95.371, accuracy: 16 });
  const result = await pending;
  assert.deepEqual(seen, [400, 16]);
  assert.equal(result.precise, true);
  assert.equal(result.fix.accuracy, 16);
});

test("a coarse-only timeout is still a usable fix, not a failure", async () => {
  const geo = mockGeo();
  let expire;
  const seen = [];
  const pending = waitForPreciseFix({
    geolocation: geo,
    watchMs: 8000,
    setTimer: (fn) => {
      expire = fn;
      return 1;
    },
    clearTimer: () => {},
    onFix: (fix) => seen.push(fix.accuracy),
  });
  geo.push({ lat: 29.76, lng: -95.37, accuracy: 420 });
  expire();
  const result = await pending;
  assert.deepEqual(seen, [420]);
  assert.equal(result.precise, false);
  assert.equal(result.fix.accuracy, 420);
  const fix = await getPrecisePosition({
    geolocation: {
      getCurrentPosition(success) {
        success(coords({ accuracy: 420 }));
      },
      watchPosition() {
        return 1;
      },
      clearWatch() {},
    },
    setTimer: (fn) => {
      fn();
      return 1;
    },
    clearTimer: () => {},
  });
  assert.equal(fix.accuracy, 420);
});

test("watch emits coarse, then GPS, and ignores a later cell reading", () => {
  const geo = mockGeo();
  const seen = [];
  watchPrecisePosition((fix) => seen.push(fix.accuracy), undefined, { geolocation: geo });
  geo.push({ accuracy: 380 });
  assert.deepEqual(seen, [380]);
  geo.push({ accuracy: 20 });
  assert.deepEqual(seen, [380, 20]);
  geo.push({ accuracy: 450 });
  assert.deepEqual(seen, [380, 20]);
});
