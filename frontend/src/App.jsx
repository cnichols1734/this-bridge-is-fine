import { useCallback, useEffect, useRef, useState } from "react";
import MapView from "./MapView.jsx";
import Detail, { RankNote } from "./Detail.jsx";
import SearchBox from "./SearchBox.jsx";
import Sheet, { detentHeight } from "./Sheet.jsx";
import { fetchBridge, fetchHealth, fetchMeta, fetchViewport } from "./api.js";
import {
  CHICAGO,
  CONDITION_FILTERS,
  COPY,
  conditionClass,
  conditionVisible,
  formatCrossings,
  officialCondition,
  readConditionFilter,
  readPermalink,
  viewIsAway,
  writeConditionFilter,
  writePermalink,
} from "./format.js";

function Row({ bridge, selected, onSelect, showScore }) {
  const cond = officialCondition(bridge.condition);
  const condLabel = bridge.condition_label || "Unknown";
  return (
    <button
      type="button"
      className={`row${selected ? " is-on" : ""}`}
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
          {bridge.distance_km != null ? ` · ${bridge.distance_km} km` : ""}
          {bridge.year_built ? ` · ${bridge.year_built}` : ""}
        </div>
        {bridge.headline ? <div className="row-head">{bridge.headline}</div> : null}
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
  const [sheet, setSheet] = useState("peek");
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
  const mapRef = useRef(null);

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
      rememberView(map);
      try {
        const data = await fetchViewport(map.getBounds(), map.getZoom());
        setGeojson(data.geojson);
        setList(data.list);
        setWorst(data.worst);
        setStats(data.stats);
        setHint(data.geojson.hint || null);
        setError(null);
      } catch (err) {
        setError(err.message);
      }
    },
    [rememberView]
  );

  const padMap = useCallback((detent, bridge) => {
    const map = mapRef.current;
    if (!map) return;
    const mobile = window.matchMedia("(max-width: 900px)").matches;
    const bottom = mobile ? detentHeight(detent) + 12 : 40;
    const camera = {
      padding: { top: mobile ? 88 : 24, bottom, left: 12, right: 12 },
      duration: 420,
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
      const preview =
        list.find((bridge) => bridge.id === id) ||
        worst.find((bridge) => bridge.id === id);
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
    [padMap, list, worst]
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

  const locate = useCallback(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const next = { lng: pos.coords.longitude, lat: pos.coords.latitude };
        setUserLocation(next);
        flyHome(next);
      },
      () => {},
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, [flyHome]);

  const goToPlace = useCallback(
    (hit) => {
      const map = mapRef.current;
      if (!map) return;
      map.easeTo({
        center: [hit.lng, hit.lat],
        zoom: 11.2,
        duration: 800,
      });
    },
    []
  );

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
    if (!permalink.id) return;
    fetchBridge(permalink.id).then(setDetail).catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") closeDetail();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeDetail]);

  const onReady = (map) => {
    mapRef.current = map;
    if (!permalink.lat && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const next = { lng: pos.coords.longitude, lat: pos.coords.latitude };
          setUserLocation(next);
          map.easeTo({
            center: [next.lng, next.lat],
            zoom: 11.2,
            duration: 800,
          });
        },
        () => {},
        { enableHighAccuracy: true, timeout: 6000 }
      );
    } else if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation({
            lng: pos.coords.longitude,
            lat: pos.coords.latitude,
          });
        },
        () => {},
        { enableHighAccuracy: true, timeout: 6000 }
      );
    }
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

  return (
    <div className={`app sheet-${sheet}${detail ? " has-place" : ""}`}>
      <aside className="col col-left">
        <header className="brand">
          <div className="wordmark">This Bridge Is Fine</div>
          <p className="tag">{COPY.tagline}</p>
          <SearchBox onPick={goToPlace} near={userLocation || center} />
          <button className="locate" type="button" onClick={locate}>
            Use my location
          </button>
        </header>
        {error ? <div className="error">{error}</div> : null}
        {hint ? <div className="hint">{hint}</div> : null}
        <div className="section-head">
          <div className="section-label">{COPY.nearest}</div>
        </div>
        <div className="list">
          {list.length === 0 && !hint ? (
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
          geojson={geojson}
          selectedId={selectedId}
          onReady={onReady}
          onMove={loadViewport}
          onSelect={select}
          onDeselect={closeDetail}
          basemap={basemap}
          visibleConditions={visibleConditions}
        />
        <div className="map-search">
          <div className="map-brand">This Bridge Is Fine</div>
          <SearchBox onPick={goToPlace} near={userLocation || center} />
        </div>
        {away && userLocation ? (
          <button
            type="button"
            className="recenter"
            aria-label="Recenter on my location"
            onClick={() => flyHome(userLocation)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="3.2" />
              <path d="M12 3v3.2M12 17.8V21M3 12h3.2M17.8 12H21" />
              <circle cx="12" cy="12" r="7.2" fill="none" />
            </svg>
          </button>
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
        <div className="pulse">
          <div className="pulse-label">{COPY.pulseLabel}</div>
          <div className="pulse-number">{pulseNumber}</div>
          <p className="pulse-copy">{pulseCopy}</p>
        </div>
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
      </aside>

      <Sheet
        detent={sheet}
        onDetent={(next) => {
          setSheet(next);
          padMap(next, detail);
        }}
        onDismiss={detail ? closeDetail : undefined}
      >
        {detail ? (
          <>
            <Detail bridge={detail} onClose={closeDetail} />
            <p className="sheet-legal">{COPY.poorDefinition}</p>
          </>
        ) : (
          <>
            <div className="sheet-pulse sheet-drag" onClick={() => setSheet("half")}>
              <div className="pulse-label">{COPY.pulseLabel}</div>
              <div className="pulse-number">{pulseNumber}</div>
              <p className="pulse-copy">{pulseCopy}</p>
            </div>
            {sheet !== "peek" ? (
              <div className="section-head">
                <div className="section-label">{COPY.lowestScores}</div>
                <RankNote />
              </div>
            ) : null}
            <div className="list">
              {shownWorst.length === 0 ? (
                <div className="empty">{COPY.emptyWorst}</div>
              ) : (
                (sheet === "peek" ? shownWorst.slice(0, 2) : shownWorst).map((bridge) => (
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
