import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import MapView from "./MapView.jsx";
import Detail, { RankNote } from "./Detail.jsx";
import SearchBox from "./SearchBox.jsx";
import TripBar from "./TripBar.jsx";
import Sheet, { detentHeight } from "./Sheet.jsx";
import { fetchBridge, fetchDrive, fetchHealth, fetchMeta, fetchViewport } from "./api.js";
import {
  getPrecisePosition,
  isApproximateError,
  isPermissionDenied,
  isPreciseFix,
  waitForPreciseFix,
  watchPrecisePosition,
} from "./geo.js";
import { ApproachCard, DriveButton, LocateButton, NavBanner, WorstOnDrive } from "./NavOverlay.jsx";
import {
  CHICAGO,
  CONDITION_FILTERS,
  COPY,
  conditionClass,
  conditionVisible,
  driveBridgesForMap,
  formatAdt,
  formatCrossings,
  formatDriveDistance,
  formatDriveTime,
  formatEta,
  mapDotsCollection,
  navBanner,
  nextDropSlot,
  officialCondition,
  pickApproachingBridge,
  pickWorstOnDrive,
  pointAlongRoute,
  readConditionFilter,
  readPermalink,
  routeHeadingAt,
  viewIsAway,
  writeConditionFilter,
  writePermalink,
} from "./format.js";

function Row({ bridge, selected, onSelect, showScore, trip }) {
  const cond = officialCondition(bridge.condition);
  const condLabel = bridge.condition_label || "Unknown";
  return (
    <button
      type="button"
      className={`row${selected ? " is-on" : ""}${cond === "P" ? " is-poor" : ""}`}
      aria-current={selected ? "true" : undefined}
      onClick={() => onSelect(bridge.id)}
    >
      <span className={conditionClass(bridge)} />
      <span className="row-body">
        <div className="row-title">
          {bridge.facility_carried || "Unnamed structure"}
        </div>
        <div className="row-meta">
          <span className={`cond cond-${cond}`}>{condLabel}</span>
          {trip && bridge.score != null ? ` · ${bridge.score}` : ""}
          {trip ? ` · ${formatAdt(bridge.adt, bridge.adt_suspect)}` : ""}
          {!trip && bridge.distance_km != null ? ` · ${bridge.distance_km} km` : ""}
          {!trip && bridge.year_built ? ` · ${bridge.year_built}` : ""}
        </div>
        {!trip && bridge.headline ? <div className="row-head">{bridge.headline}</div> : null}
      </span>
      {showScore && bridge.score != null ? (
        <span
          className="row-score"
          aria-label={`${COPY.scoreHeading} ${bridge.score} of 100. ${COPY.rankNote}`}
        >
          <span className="row-score-n">{bridge.score}</span>
          <span className="row-score-word">{COPY.scoreHeading}</span>
        </span>
      ) : null}
    </button>
  );
}

function TripFacts({ route, summary }) {
  const bridges = summary?.bridges ?? 0;
  const poor = summary?.poor ?? 0;
  return (
    <p className="pulse-copy">
      {formatEta(route.duration_s)}
      {` · ${formatDriveDistance(route.distance_m)}`}
      {` · ${bridges.toLocaleString()} ${bridges === 1 ? "bridge" : "bridges"}`}
      {poor > 0 ? (
        <>
          {" · "}
          <span className="cond cond-P">{poor} Poor</span>
        </>
      ) : (
        " · No Poor"
      )}
    </p>
  );
}

function TripPulse({
  payload,
  confirmed,
  onConfirm,
  onOpen,
  worst,
  selectedId,
  onSelect,
}) {
  if (!payload?.route) return null;
  const { route, summary } = payload;
  return (
    <div className="sheet-pulse sheet-drag trip-pulse" onClick={onOpen}>
      <div className="pulse-label">{COPY.drive}</div>
      <div className="pulse-number">{formatDriveTime(route.duration_s)}</div>
      <TripFacts route={route} summary={summary} />
      {!confirmed ? (
        <button
          type="button"
          className="trip-use"
          onClick={(event) => {
            event.stopPropagation();
            onConfirm();
          }}
        >
          {COPY.driveUse}
        </button>
      ) : null}
      <WorstOnDrive
        bridges={worst}
        selectedId={selectedId}
        onSelect={onSelect}
      />
    </div>
  );
}

function fitRoute(map, geometry, detent, roomy) {
  const coords = geometry?.coordinates;
  if (!map || !coords?.length) return;
  const west = Math.min(...coords.map((pair) => pair[0]));
  const east = Math.max(...coords.map((pair) => pair[0]));
  const south = Math.min(...coords.map((pair) => pair[1]));
  const north = Math.max(...coords.map((pair) => pair[1]));
  const mobile = window.matchMedia("(max-width: 900px)").matches;
  const bottom = mobile ? detentHeight(detent, roomy) + 12 : 48;
  map.fitBounds(
    [
      [west, south],
      [east, north],
    ],
    {
      padding: { top: mobile ? 132 : 56, bottom, left: 36, right: 36 },
      duration: 700,
      maxZoom: 13,
    }
  );
}

export default function App() {
  const permalink = readPermalink();
  const [center] = useState(() => ({
    lng: permalink.lng ?? CHICAGO.lng,
    lat: permalink.lat ?? CHICAGO.lat,
  }));
  const [zoom] = useState(permalink.z ?? CHICAGO.zoom);
  const [geojson, setGeojson] = useState(null);
  const [list, setList] = useState([]);
  const [worst, setWorst] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedId, setSelectedId] = useState(permalink.id);
  const [detail, setDetail] = useState(null);
  const [hint, setHint] = useState(null);
  const [error, setError] = useState(null);
  const [stale, setStale] = useState(null);
  const [sheet, setSheet] = useState(() => (permalink.id ? "full" : "peek"));
  const [meta, setMeta] = useState(null);
  const [userLocation, setUserLocation] = useState(null);
  const [away, setAway] = useState(false);
  const [basemap, setBasemap] = useState(() => {
    try {
      return localStorage.getItem("tbif-basemap") === "satellite"
        ? "satellite"
        : "map";
    } catch {
      return "map";
    }
  });
  const [visibleConditions, setVisibleConditions] = useState(readConditionFilter);
  const [tripOpen, setTripOpen] = useState(false);
  const [tripStart, setTripStart] = useState(null);
  const [tripEnd, setTripEnd] = useState(null);
  const [tripDraft, setTripDraft] = useState(null);
  const [trip, setTrip] = useState(null);
  const [tripBusy, setTripBusy] = useState(false);
  const [fixingStart, setFixingStart] = useState(false);
  const [tripError, setTripError] = useState(null);
  const [dropMode, setDropMode] = useState(false);
  const [dropEditing, setDropEditing] = useState(null);
  const [lastPlace, setLastPlace] = useState(null);
  const [navigating, setNavigating] = useState(false);
  const [followOn, setFollowOn] = useState(false);
  const [navFix, setNavFix] = useState(null);
  const [navNote, setNavNote] = useState(null);
  const [dismissedApproach, setDismissedApproach] = useState(() => new Set());
  const mapRef = useRef(null);
  const tripKey = useRef("");
  const typeaheadOpen = useRef(false);
  const typeaheadCount = useRef(0);
  const lastDriveBridges = useRef(null);
  const drivePinsOn = useRef(false);
  const wasDrivePinsOn = useRef(false);
  const navigatingRef = useRef(false);
  const lastFixAt = useRef(0);
  const fixGen = useRef(0);

  const toggleCondition = useCallback((code) => {
    setVisibleConditions((current) => {
      const on = current.includes(code);
      if (on && current.length === 1) return current;
      const next = on ? current.filter((item) => item !== code) : [...current, code];
      writeConditionFilter(next);
      return next;
    });
  }, []);

  const chooseBasemap = useCallback((next) => {
    setBasemap(next);
    try {
      localStorage.setItem("tbif-basemap", next);
    } catch {
      /* ignore */
    }
  }, []);

  const rememberView = useCallback(
    (map) => {
      const here = map.getCenter();
      const z = map.getZoom();
      writePermalink({
        lat: here.lat,
        lng: here.lng,
        z,
        id: selectedId,
      });
      setAway(viewIsAway(userLocation, { lat: here.lat, lng: here.lng }, z));
    },
    [selectedId, userLocation]
  );

  const loadViewport = useCallback(
    async (map) => {
      if (navigatingRef.current) return;
      rememberView(map);
      if (drivePinsOn.current) return;
      try {
        const data = await fetchViewport(map.getBounds(), map.getZoom());
        if (drivePinsOn.current) return;
        setGeojson(data.geojson);
        setList(data.list);
        setWorst(data.worst);
        setStats(data.stats);
        setHint(data.geojson.hint || null);
        setError(null);
      } catch (err) {
        if (drivePinsOn.current) return;
        setError(err.message);
      }
    },
    [rememberView]
  );

  const padMap = useCallback((detent, bridge, roomy = false) => {
    const map = mapRef.current;
    if (!map) return;
    const mobile = window.matchMedia("(max-width: 900px)").matches;
    const bottom = mobile ? detentHeight(detent, roomy) + 12 : 40;
    const camera = {
      padding: { top: mobile ? 88 : 24, bottom, left: 12, right: 12 },
      duration: 200,
    };
    if (bridge) camera.center = [bridge.lng, bridge.lat];
    map.easeTo(camera);
  }, []);

  const closeDetail = useCallback(() => {
    setSelectedId(null);
    setDetail(null);
    setSheet("peek");
    const map = mapRef.current;
    if (map) {
      writePermalink({
        lat: map.getCenter().lat,
        lng: map.getCenter().lng,
        z: map.getZoom(),
        id: null,
      });
      padMap("peek");
    }
  }, [padMap]);

  const select = useCallback(
    async (id) => {
      setSelectedId(id);
      setSheet("half");
      if (navigatingRef.current) setFollowOn(false);
      const preview =
        list.find((bridge) => bridge.id === id) ||
        worst.find((bridge) => bridge.id === id) ||
        trip?.bridges?.find((bridge) => bridge.id === id) ||
        tripDraft?.bridges?.find((bridge) => bridge.id === id) ||
        trip?.worst?.find((bridge) => bridge.id === id) ||
        tripDraft?.worst?.find((bridge) => bridge.id === id);
      if (preview) setDetail(preview);
      const map = mapRef.current;
      if (map) {
        writePermalink({
          lat: map.getCenter().lat,
          lng: map.getCenter().lng,
          z: map.getZoom(),
          id,
        });
      }
      try {
        const bridge = await fetchBridge(id);
        setDetail(bridge);
        padMap("half", bridge);
      } catch (err) {
        setError(err.message);
      }
    },
    [padMap, list, worst, trip, tripDraft]
  );

  const flyHome = useCallback((coords) => {
    const map = mapRef.current;
    if (!map || !coords) return;
    map.easeTo({
      center: [coords.lng, coords.lat],
      zoom: 11.2,
      duration: 700,
    });
    setAway(false);
  }, []);

  const applyFix = useCallback((fix) => {
    if (!fix || !isPreciseFix(fix)) return null;
    lastFixAt.current = fix.at || Date.now();
    setUserLocation(fix);
    return fix;
  }, []);

  const locationNote = useCallback((err) => {
    if (isPermissionDenied(err)) return COPY.locationDenied;
    if (isApproximateError(err)) return COPY.locationApproximate;
    return COPY.locationPreciseOff;
  }, []);

  const refreshPrecise = useCallback(
    (force = false) => {
      if (!force && Date.now() - lastFixAt.current < 8000 && userLocation && isPreciseFix(userLocation)) {
        return Promise.resolve(userLocation);
      }
      return getPrecisePosition()
        .then((fix) => {
          setNavNote(null);
          return applyFix(fix);
        })
        .catch((err) => {
          setNavNote(locationNote(err));
          return null;
        });
    },
    [applyFix, locationNote, userLocation]
  );

  const mapCenterStart = useCallback(() => {
    const map = mapRef.current;
    if (map) {
      const here = map.getCenter();
      return { lng: here.lng, lat: here.lat, label: COPY.driveCenter };
    }
    return { ...center, label: COPY.driveCenter };
  }, [center]);

  const locate = useCallback(() => {
    refreshPrecise(true).then((fix) => {
      if (fix) flyHome(fix);
    });
  }, [flyHome, refreshPrecise]);

  const goToPlace = useCallback((hit) => {
    setLastPlace(hit);
    if (tripOpen) {
      setTripEnd({ lng: hit.lng, lat: hit.lat, label: hit.label });
      setTrip(null);
      setTripDraft(null);
      return;
    }
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({
      center: [hit.lng, hit.lat],
      zoom: 11.2,
      duration: 800,
    });
  }, [tripOpen]);

  const clearTrip = useCallback(() => {
    fixGen.current += 1;
    tripKey.current = "";
    navigatingRef.current = false;
    setNavigating(false);
    setFollowOn(false);
    setNavFix(null);
    setNavNote(null);
    setDismissedApproach(new Set());
    setTripOpen(false);
    setTripStart(null);
    setTripEnd(null);
    setTripDraft(null);
    setTrip(null);
    setTripBusy(false);
    setFixingStart(false);
    setTripError(null);
    setDropMode(false);
    setDropEditing(null);
    setSheet("peek");
  }, []);

  const openDrive = useCallback(() => {
    const gen = ++fixGen.current;
    setTripStart(null);
    if (lastPlace) {
      setTripEnd({
        lng: lastPlace.lng,
        lat: lastPlace.lat,
        label: lastPlace.label,
      });
    }
    setTrip(null);
    setTripDraft(null);
    setTripError(null);
    setNavNote(null);
    setDropMode(false);
    setDropEditing(null);
    setTripOpen(true);
    setFixingStart(true);
    setSheet("peek");
    waitForPreciseFix()
      .then((result) => {
        if (gen !== fixGen.current) return;
        setFixingStart(false);
        if (result.precise) {
          setNavNote(null);
          applyFix(result.fix);
          setTripStart({ ...result.fix, label: COPY.driveHere });
          return;
        }
        setNavNote(COPY.locationApproximate);
        setTripStart(mapCenterStart());
      })
      .catch((err) => {
        if (gen !== fixGen.current) return;
        setFixingStart(false);
        setNavNote(locationNote(err));
        setTripStart(mapCenterStart());
      });
  }, [applyFix, lastPlace, locationNote, mapCenterStart]);

  const confirmTrip = useCallback(() => {
    if (!tripDraft) return;
    setTrip(tripDraft);
    setDropMode(false);
    setSheet("peek");
    setDismissedApproach(new Set());
    navigatingRef.current = true;
    setNavigating(true);
    waitForPreciseFix()
      .then((result) => {
        if (result.precise) {
          setNavNote(null);
          applyFix(result.fix);
          setNavFix(result.fix);
          setFollowOn(true);
          return;
        }
        setNavNote(COPY.locationApproximate);
        setFollowOn(false);
      })
      .catch((err) => {
        setNavNote(locationNote(err));
        setFollowOn(false);
      });
  }, [applyFix, locationNote, tripDraft]);

  const pickTripPoint = useCallback((point) => {
    const labeled = {
      lng: point.lng,
      lat: point.lat,
      label: `${point.lat.toFixed(4)}, ${point.lng.toFixed(4)}`,
    };
    const slot = nextDropSlot(tripStart, tripEnd, dropEditing);
    tripKey.current = "";
    setTrip(null);
    setTripDraft(null);
    if (slot === "start") {
      setTripStart(labeled);
      if (tripEnd) setDropMode(false);
      return;
    }
    setTripEnd(labeled);
    setDropMode(false);
    navigatingRef.current = false;
    setNavigating(false);
    setFollowOn(false);
  }, [tripStart, tripEnd, dropEditing]);

  useEffect(() => {
    fetchMeta().then(setMeta).catch(() => {});
    fetchHealth()
      .then((health) => {
        if (health.ingest_status === "empty") {
          setStale(COPY.inventoryEmpty);
        }
      })
      .catch(() => setStale(COPY.inventoryDown));
  }, []);

  useEffect(() => {
    if (!permalink.id) return undefined;
    let cancelled = false;
    fetchBridge(permalink.id)
      .then((bridge) => {
        if (cancelled) return;
        setDetail(bridge);
        padMap("full", bridge);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [padMap]);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key !== "Escape") return;
      if (typeaheadOpen.current) return;
      if (selectedId) {
        closeDetail();
        return;
      }
      if (tripOpen) clearTrip();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeDetail, selectedId, tripOpen, clearTrip]);

  useEffect(() => {
    if (!tripOpen || !tripStart || !tripEnd) return undefined;
    const key = `${tripStart.lng.toFixed(5)},${tripStart.lat.toFixed(5)}|${tripEnd.lng.toFixed(5)},${tripEnd.lat.toFixed(5)}`;
    if (tripKey.current === key) return undefined;
    tripKey.current = key;
    let cancelled = false;
    setTripBusy(true);
    setTripError(null);
    setTripDraft(null);
    setTrip(null);
    navigatingRef.current = false;
    setNavigating(false);
    setFollowOn(false);
    fetchDrive(tripStart, tripEnd)
      .then((payload) => {
        if (cancelled) return;
        setTripDraft(payload);
        setTripBusy(false);
        fitRoute(mapRef.current, payload.route?.geometry, "peek", true);
      })
      .catch((err) => {
        if (cancelled) return;
        setTripBusy(false);
        setTripDraft(null);
        const message = err.message || COPY.driveDown;
        setTripError(
          /no driving route/i.test(message) ? COPY.driveNone : COPY.driveDown
        );
      });
    return () => {
      cancelled = true;
    };
  }, [tripOpen, tripStart, tripEnd]);

  useEffect(() => {
    if (!navigating) return undefined;
    const stop = watchPrecisePosition(
      (fix) => {
        applyFix(fix);
        setNavFix(fix);
      },
      (err) => {
        setNavNote(locationNote(err));
      }
    );
    return stop;
  }, [navigating, applyFix, locationNote]);

  const onReady = (map) => {
    mapRef.current = map;
    if (permalink.id) padMap("full");
    refreshPrecise(true).then((fix) => {
      if (!fix || permalink.lat) return;
      map.easeTo({
        center: [fix.lng, fix.lat],
        zoom: 11.2,
        duration: 800,
      });
    });
  };

  useEffect(() => {
    if (detail && !conditionVisible(detail, visibleConditions)) {
      closeDetail();
    }
  }, [visibleConditions, detail, closeDetail]);

  const shownList = list.filter((bridge) =>
    conditionVisible(bridge, visibleConditions)
  );
  const shownWorst = worst.filter((bridge) =>
    conditionVisible(bridge, visibleConditions)
  );

  const pulseNumber = stats ? formatCrossings(stats.daily_crossings_on_poor) : "—";
  const pulseCopy = stats
    ? `${stats.poor.toLocaleString()} Poor of ${stats.total.toLocaleString()} in view. ${COPY.poorDefinition}`
    : COPY.pulseMove;
  const tripPayload = trip || tripDraft;
  const routeOnMap = Boolean(tripPayload?.route);
  const tripList = routeOnMap ? tripPayload.bridges || [] : [];
  const tripWorst = tripPayload
    ? tripPayload.worst || pickWorstOnDrive(tripPayload.bridges, 3)
    : [];
  const routeCoords = trip?.route?.geometry?.coordinates;
  const routeM = trip?.route?.distance_m || 0;
  const along = navFix && routeCoords
    ? pointAlongRoute(navFix.lng, navFix.lat, routeCoords)
    : 0;
  const followHeading =
    navFix && Number.isFinite(navFix.heading) && (navFix.speed || 0) > 1
      ? navFix.heading
      : routeCoords
        ? routeHeadingAt(along, routeCoords)
        : navFix?.heading;
  const banner = navigating
    ? navBanner(trip?.route?.steps, along, routeM)
    : null;
  const approach = navigating
    ? pickApproachingBridge({
        bridges: trip?.bridges,
        worstIds: tripWorst.map((bridge) => bridge.id),
        along,
        routeM,
        dismissedIds: dismissedApproach,
      })
    : null;
  const followCamera =
    followOn && navFix
      ? { lng: navFix.lng, lat: navFix.lat, heading: followHeading }
      : null;
  if (!tripOpen) {
    lastDriveBridges.current = null;
  } else if (tripPayload?.route) {
    lastDriveBridges.current = tripPayload.bridges || [];
  }
  const driveBridges = driveBridgesForMap({
    route: tripPayload?.route,
    bridges: tripPayload?.bridges,
    tripOpen,
    lastBridges: lastDriveBridges.current,
  });
  drivePinsOn.current = driveBridges != null;
  const mapGeojson = useMemo(
    () => mapDotsCollection(geojson, driveBridges),
    [geojson, tripPayload, tripOpen]
  );

  useEffect(() => {
    const on = drivePinsOn.current;
    if (wasDrivePinsOn.current && !on && mapRef.current) {
      loadViewport(mapRef.current);
    }
    wasDrivePinsOn.current = on;
  }, [tripOpen, tripPayload, loadViewport]);

  const roomySheet = Boolean(tripOpen && (tripPayload || tripError) && !detail);
  const searchNear = userLocation && isPreciseFix(userLocation) ? userLocation : center;
  const preciseHere =
    (navFix && isPreciseFix(navFix) ? navFix : null) ||
    (userLocation && isPreciseFix(userLocation) ? userLocation : null);

  const tripComposer = tripOpen ? (
    <TripBar
      start={tripStart}
      end={tripEnd}
      near={searchNear}
      dropping={dropMode}
      busy={tripBusy}
      locating={fixingStart}
      note={navNote}
      error={tripError}
      onFocusStart={() => {
        setDropEditing("start");
        refreshPrecise();
      }}
      onFocusEnd={() => {
        setDropEditing("end");
        refreshPrecise();
      }}
      onOpenChange={(open) => {
        typeaheadCount.current += open ? 1 : -1;
        if (typeaheadCount.current < 0) typeaheadCount.current = 0;
        typeaheadOpen.current = typeaheadCount.current > 0;
      }}
      onPickStart={(point) => {
        setTripStart(point);
        tripKey.current = "";
        setTrip(null);
        setTripDraft(null);
        navigatingRef.current = false;
        setNavigating(false);
        setFollowOn(false);
      }}
      onPickEnd={(point) => {
        setTripEnd(point);
        tripKey.current = "";
        setTrip(null);
        setTripDraft(null);
        navigatingRef.current = false;
        setNavigating(false);
        setFollowOn(false);
      }}
      onDrop={() => setDropMode((on) => !on)}
      onBack={clearTrip}
      onClear={clearTrip}
    />
  ) : null;

  return (
    <div
      className={`app sheet-${sheet}${detail ? " has-place" : ""}${tripOpen ? " has-trip" : ""}${navigating ? " has-nav" : ""}`}
    >
      <aside className="col col-left">
        <header className="brand">
          <div className="wordmark">This Bridge Is Fine</div>
          <p className="tag">{COPY.tagline}</p>
          {tripOpen ? (
            tripComposer
          ) : (
            <>
              <SearchBox
                onPick={goToPlace}
                near={searchNear}
                onFocus={() => refreshPrecise()}
              />
              <div className="brand-actions">
                <LocateButton labeled onClick={locate} />
                <DriveButton onClick={openDrive} />
              </div>
            </>
          )}
        </header>
        {error ? <div className="error">{error}</div> : null}
        {tripError ? <div className="error">{tripError}</div> : null}
        {hint && !tripOpen ? <div className="hint">{hint}</div> : null}
        {trip && tripPayload ? (
          <TripPulse
            payload={tripPayload}
            confirmed
            onOpen={() => {}}
            worst={tripWorst}
            selectedId={selectedId}
            onSelect={select}
          />
        ) : tripDraft ? (
          <TripPulse
            payload={tripDraft}
            confirmed={false}
            onConfirm={confirmTrip}
            onOpen={() => {}}
            worst={tripWorst}
            selectedId={selectedId}
            onSelect={select}
          />
        ) : null}
        <div className="section-head">
          <div className="section-label">
            {routeOnMap ? COPY.driveBridges : COPY.nearest}
          </div>
        </div>
        <div className="list">
          {routeOnMap ? (
            tripList.length === 0 ? (
              <div className="empty">{COPY.driveEmpty}</div>
            ) : (
              tripList.map((bridge) => (
                <Row
                  key={bridge.id}
                  bridge={bridge}
                  selected={bridge.id === selectedId}
                  onSelect={select}
                  trip
                />
              ))
            )
          ) : list.length === 0 && !hint ? (
            <div className="empty">{COPY.zoomHint}</div>
          ) : list.length === 0 ? null : shownList.length === 0 ? (
            <div className="empty">{COPY.emptyFilter}</div>
          ) : (
            shownList.map((bridge) => (
              <Row
                key={bridge.id}
                bridge={bridge}
                selected={bridge.id === selectedId}
                onSelect={select}
              />
            ))
          )}
        </div>
      </aside>

      <main className="col col-map">
        <MapView
          center={center}
          zoom={zoom}
          geojson={mapGeojson}
          selectedId={selectedId}
          onReady={onReady}
          onMove={loadViewport}
          onSelect={select}
          onDeselect={closeDetail}
          basemap={basemap}
          visibleConditions={visibleConditions}
          route={tripPayload?.route?.geometry || null}
          routePreview={Boolean(tripDraft && !trip)}
          tripEnds={navigating ? null : tripOpen ? { start: tripStart, end: tripEnd } : null}
          pickMode={dropMode}
          onPickPoint={pickTripPoint}
          follow={followCamera}
          followOn={followOn}
          userFix={
            (tripOpen || navigating) && preciseHere
              ? { ...preciseHere, heading: navigating ? followHeading : preciseHere.heading }
              : null
          }
          onFollowBreak={() => setFollowOn(false)}
        />
        <div className="map-search">
          {navigating ? (
            <NavBanner banner={banner} note={navNote} onExit={clearTrip} />
          ) : (
            <>
              <div className="map-brand-row">
                <div className="map-brand">This Bridge Is Fine</div>
                {tripOpen ? null : <DriveButton className="map-drive" onClick={openDrive} />}
              </div>
              {tripOpen ? (
                tripComposer
              ) : (
                <SearchBox
                  onPick={goToPlace}
                  near={searchNear}
                  onFocus={() => refreshPrecise()}
                />
              )}
            </>
          )}
        </div>
        {navigating && approach ? (
          <ApproachCard
            bridge={approach}
            onOpen={select}
            onDismiss={() =>
              setDismissedApproach((current) => new Set([...current, approach.id]))
            }
          />
        ) : null}
        {!navigating || !followOn ? (
          <LocateButton
            className="recenter"
            follow={navigating}
            onClick={() => {
              if (navigating) {
                refreshPrecise(true).then((fix) => {
                  if (fix) setNavFix(fix);
                  setFollowOn(true);
                });
                return;
              }
              locate();
            }}
          />
        ) : null}
        {detail && selectedId ? (
          <div className="map-popup" role="dialog" aria-label="Bridge file">
            <Detail bridge={detail} onClose={closeDetail} />
          </div>
        ) : null}
        <div className="map-dock">
          <div className="basemap" role="group" aria-label="Map type">
            <button
              type="button"
              className={basemap === "map" ? "is-on" : ""}
              aria-pressed={basemap === "map"}
              onClick={() => chooseBasemap("map")}
            >
              Map
            </button>
            <button
              type="button"
              className={basemap === "satellite" ? "is-on" : ""}
              aria-pressed={basemap === "satellite"}
              onClick={() => chooseBasemap("satellite")}
            >
              Satellite
            </button>
          </div>
          <div className="legend" role="group" aria-label="Filter by condition">
            {CONDITION_FILTERS.map((item) => {
              const on = visibleConditions.includes(item.code);
              return (
                <button
                  key={item.code}
                  type="button"
                  className={`${item.code}${on ? " is-on" : ""}`}
                  aria-pressed={on}
                  title={on ? `Hide ${item.label}` : `Show ${item.label}`}
                  onClick={() => toggleCondition(item.code)}
                >
                  <i />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
        {stale ? <div className="banner">{stale}</div> : null}
      </main>

      <aside className="col col-right">
        {trip && tripPayload ? (
          <TripPulse
            payload={tripPayload}
            confirmed
            onOpen={() => {}}
            worst={tripWorst}
            selectedId={selectedId}
            onSelect={select}
          />
        ) : tripDraft ? (
          <TripPulse
            payload={tripDraft}
            confirmed={false}
            onConfirm={confirmTrip}
            onOpen={() => {}}
            worst={tripWorst}
            selectedId={selectedId}
            onSelect={select}
          />
        ) : (
          <div className="pulse">
            <div className="pulse-label">{COPY.pulseLabel}</div>
            <div className="pulse-number">{pulseNumber}</div>
            <p className="pulse-copy">{pulseCopy}</p>
          </div>
        )}
        <div className="section-head">
          <div className="section-label">
            {routeOnMap ? COPY.driveBridges : COPY.lowestScores}
          </div>
          {routeOnMap ? null : <RankNote />}
        </div>
        <div className="list">
          {routeOnMap ? (
            tripList.length === 0 ? (
              <div className="empty">{COPY.driveEmpty}</div>
            ) : (
              tripList.map((bridge) => (
                <Row
                  key={bridge.id}
                  bridge={bridge}
                  selected={bridge.id === selectedId}
                  onSelect={select}
                  trip
                  showScore
                />
              ))
            )
          ) : shownWorst.length === 0 ? (
            <div className="empty">{COPY.emptyWorst}</div>
          ) : (
            shownWorst.map((bridge) => (
              <Row
                key={bridge.id}
                bridge={bridge}
                selected={bridge.id === selectedId}
                onSelect={select}
                showScore
              />
            ))
          )}
        </div>
      </aside>

      <Sheet
        detent={sheet}
        roomy={roomySheet}
        onDetent={(next) => {
          setSheet(next);
          padMap(next, detail, roomySheet);
        }}
        onDismiss={detail ? closeDetail : tripOpen ? clearTrip : undefined}
      >
        {detail ? (
          <>
            <Detail bridge={detail} onClose={closeDetail} />
            <p className="sheet-legal">{COPY.poorDefinition}</p>
          </>
        ) : tripPayload ? (
          <>
            <TripPulse
              payload={tripPayload}
              confirmed={Boolean(trip)}
              onConfirm={confirmTrip}
              onOpen={() => setSheet("half")}
              worst={tripWorst}
              selectedId={selectedId}
              onSelect={select}
            />
            {sheet !== "peek" && routeOnMap ? (
              <>
                <div className="section-head">
                  <div className="section-label">{COPY.driveBridges}</div>
                </div>
                <div className="list">
                  {tripList.length === 0 ? (
                    <div className="empty">{COPY.driveEmpty}</div>
                  ) : (
                    tripList.map((bridge) => (
                      <Row
                        key={bridge.id}
                        bridge={bridge}
                        selected={bridge.id === selectedId}
                        onSelect={select}
                        trip
                      />
                    ))
                  )}
                </div>
              </>
            ) : null}
          </>
        ) : tripOpen && (tripError || tripBusy || fixingStart) ? (
          <div className="sheet-pulse sheet-drag trip-pulse trip-status">
            <div className="pulse-label">{COPY.drive}</div>
            <p className={`pulse-copy${tripError ? " trip-error" : ""}`}>
              {tripError || (fixingStart ? COPY.driveLocating : COPY.driveLooking)}
            </p>
          </div>
        ) : (
          <>
            <div className="sheet-pulse sheet-drag" onClick={() => setSheet("half")}>
              <div className="pulse-label">{COPY.pulseLabel}</div>
              <div className="pulse-number">{pulseNumber}</div>
              <p className="pulse-copy">{pulseCopy}</p>
            </div>
            {sheet !== "peek" ? (
              <>
                <div className="section-head">
                  <div className="section-label">{COPY.lowestScores}</div>
                  <RankNote />
                </div>
                <div className="list">
                  {shownWorst.length === 0 ? (
                    <div className="empty">{COPY.emptyWorst}</div>
                  ) : (
                    shownWorst.map((bridge) => (
                      <Row
                        key={bridge.id}
                        bridge={bridge}
                        selected={bridge.id === selectedId}
                        onSelect={select}
                        showScore
                      />
                    ))
                  )}
                </div>
              </>
            ) : null}
          </>
        )}
      </Sheet>

      <footer className="disclaimer">
        FHWA National Bridge Inventory via BTS NTAD
        {meta?.snapshot ? ` · snapshot ${meta.snapshot}` : ""}. Poor means a major
        component scored 4 or below. Inspections are typically every 24 months. Not a
        closure notice. Map ©{" "}
        <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>{" "}
        contributors
        {basemap === "satellite"
          ? ". Satellite © Esri, Maxar, Earthstar Geographics."
          : "."}
      </footer>
    </div>
  );
}
