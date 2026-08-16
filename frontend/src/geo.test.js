import assert from "node:assert/strict";
import test from "node:test";
import {
  COARSE_ACCURACY_M,
  PRECISE_ACCURACY_M,
  PRECISE_GEO,
  getPrecisePosition,
  isCoarseFix,
  isPreciseFix,
  shouldAcceptFix,
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
    watchPosition(success, error, opts) {
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

test("Start a drive requests a fresh fix, not a 4s cache", () => {
  assert.equal(PRECISE_GEO.enableHighAccuracy, true);
  assert.equal(PRECISE_GEO.maximumAge, 0);
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
  assert.equal(geo.opts.maximumAge, 0);
  assert.equal(geo.opts.enableHighAccuracy, true);
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
      watchPosition(success) {
        success(coords({ accuracy: 420 }));
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
