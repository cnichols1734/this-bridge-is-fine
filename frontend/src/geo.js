/** Precise location. Short cache. The OS prompt is where Precise vs Approximate lives. */

export const PRECISE_GEO = {
  enableHighAccuracy: true,
  maximumAge: 4000,
  timeout: 10000,
};

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

export function getPrecisePosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      const err = new Error("location unavailable");
      err.code = 2;
      reject(err);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve(readFix(pos)),
      reject,
      PRECISE_GEO
    );
  });
}

export function watchPrecisePosition(onFix, onError) {
  if (!navigator.geolocation) {
    onError?.({ code: 2, message: "location unavailable" });
    return () => {};
  }
  const id = navigator.geolocation.watchPosition(
    (pos) => onFix(readFix(pos)),
    onError,
    PRECISE_GEO
  );
  return () => navigator.geolocation.clearWatch(id);
}

export function isPermissionDenied(err) {
  return err?.code === 1 || err?.code === err?.PERMISSION_DENIED;
}
