/** Fresh GPS. No cached cell/wifi reading. Precise vs Approximate is an OS grant. */

export const PRECISE_GEO = {
  enableHighAccuracy: true,
  maximumAge: 0,
  timeout: 12000,
};

/** Tens of meters. A first callback of a few hundred meters is typical cell/wifi. */
export const PRECISE_ACCURACY_M = 80;

/** Cell/wifi and iOS Approximate are typically at least this. */
export const COARSE_ACCURACY_M = 100;

export const PRECISE_WAIT_MS = 8000;

export function readFix(pos) {
  return {
    lng: pos.coords.longitude,
    lat: pos.coords.latitude,
    accuracy: pos.coords.accuracy,
    heading: Number.isFinite(pos.coords.heading) ? pos.coords.heading : null,
    speed: Number.isFinite(pos.coords.speed) ? pos.coords.speed : null,
    at: Date.now(),
  };
}

export function isPreciseFix(fix) {
  return Number.isFinite(fix?.accuracy) && fix.accuracy > 0 && fix.accuracy <= PRECISE_ACCURACY_M;
}

export function isCoarseFix(fix) {
  return Number.isFinite(fix?.accuracy) && fix.accuracy >= COARSE_ACCURACY_M;
}

/** Keep a GPS fix. Do not replace it with a later cell/wifi reading. */
export function shouldAcceptFix(next, prev) {
  if (!next) return false;
  if (!prev) return true;
  if (isPreciseFix(next)) return true;
  if (isPreciseFix(prev) && isCoarseFix(next)) return false;
  if (Number.isFinite(next.accuracy) && Number.isFinite(prev.accuracy)) {
    return next.accuracy < prev.accuracy;
  }
  return true;
}

function geoHost(geolocation) {
  if (geolocation) return geolocation;
  if (typeof navigator !== "undefined") return navigator.geolocation;
  return null;
}

function unavailableError() {
  const err = new Error("location unavailable");
  err.code = 2;
  return err;
}

/**
 * Use the first reading immediately (often cell/wifi), keep watching,
 * and snap when GPS locks. Reject only when there is no fix at all.
 */
export function waitForPreciseFix({
  geolocation,
  watchMs = PRECISE_WAIT_MS,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
  onFix,
} = {}) {
  return new Promise((resolve, reject) => {
    const geo = geoHost(geolocation);
    if (!geo?.watchPosition) {
      reject(unavailableError());
      return;
    }
    let best = null;
    let settled = false;
    let timer = 0;
    let stop = () => {};

    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimer(timer);
      stop();
      resolve(result);
    };

    const fail = (err) => {
      if (settled) return;
      settled = true;
      clearTimer(timer);
      stop();
      reject(err);
    };

    const id = geo.watchPosition(
      (pos) => {
        const fix = readFix(pos);
        if (!shouldAcceptFix(fix, best)) return;
        best = fix;
        onFix?.(fix);
        if (isPreciseFix(best)) {
          finish({ fix: best, precise: true, approximate: false });
        }
      },
      (err) => {
        if (isPermissionDenied(err)) fail(err);
      },
      PRECISE_GEO
    );
    stop = () => geo.clearWatch(id);

    timer = setTimer(() => {
      if (best) {
        finish({
          fix: best,
          precise: isPreciseFix(best),
          approximate: !isPreciseFix(best),
        });
        return;
      }
      const err = new Error("location timeout");
      err.code = 3;
      fail(err);
    }, watchMs);
  });
}

export function getPrecisePosition(options) {
  return waitForPreciseFix(options).then((result) => result.fix);
}

export function watchPrecisePosition(onFix, onError, options = {}) {
  const geo = geoHost(options.geolocation);
  if (!geo?.watchPosition) {
    onError?.(unavailableError());
    return () => {};
  }
  let last = null;
  const id = geo.watchPosition(
    (pos) => {
      const fix = readFix(pos);
      if (!shouldAcceptFix(fix, last)) return;
      last = fix;
      onFix(fix);
    },
    onError,
    PRECISE_GEO
  );
  return () => geo.clearWatch(id);
}

export function isPermissionDenied(err) {
  return err?.code === 1 || err?.code === err?.PERMISSION_DENIED;
}
