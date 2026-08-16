import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { CONDITION_COLORS } from "./format.js";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/positron";

const SATELLITE_STYLE = {
  version: 8,
  name: "satellite",
  sources: {
    esri: {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 19,
      attribution:
        "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
    },
  },
  layers: [{ id: "esri", type: "raster", source: "esri" }],
};

const empty = { type: "FeatureCollection", features: [] };

function styleFor(basemap) {
  return basemap === "satellite" ? SATELLITE_STYLE : MAP_STYLE;
}

function dotsFilter(codes) {
  if (!codes?.length) return ["==", ["get", "condition"], "__none__"];
  return ["in", ["get", "condition"], ["literal", codes]];
}

function selectedFilter(selectedId, codes) {
  return ["all", ["==", ["get", "id"], selectedId || ""], dotsFilter(codes)];
}

function stripOverlay(map) {
  if (map.getLayer("bridges-selected")) map.removeLayer("bridges-selected");
  if (map.getLayer("bridges-dots")) map.removeLayer("bridges-dots");
  if (map.getSource("bridges")) map.removeSource("bridges");
}

function stripRoute(map) {
  if (map.getLayer("drive-ends")) map.removeLayer("drive-ends");
  if (map.getLayer("drive-line")) map.removeLayer("drive-line");
  if (map.getLayer("drive-case")) map.removeLayer("drive-case");
  if (map.getSource("drive-ends")) map.removeSource("drive-ends");
  if (map.getSource("drive")) map.removeSource("drive");
}

function routeCollection(route) {
  if (!route?.coordinates?.length) return empty;
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: route.coordinates },
      },
    ],
  };
}

function endsCollection(ends) {
  const features = [];
  if (ends?.start) {
    features.push({
      type: "Feature",
      properties: { role: "start" },
      geometry: { type: "Point", coordinates: [ends.start.lng, ends.start.lat] },
    });
  }
  if (ends?.end) {
    features.push({
      type: "Feature",
      properties: { role: "end" },
      geometry: { type: "Point", coordinates: [ends.end.lng, ends.end.lat] },
    });
  }
  return { type: "FeatureCollection", features };
}

function addRouteOverlay(map, route, ends, preview, basemap) {
  if (!map.getStyle()) return;
  try {
    stripRoute(map);
    const satellite = basemap === "satellite";
    const before = map.getLayer("bridges-dots") ? "bridges-dots" : undefined;
    map.addSource("drive", { type: "geojson", data: routeCollection(route) });
    map.addLayer(
      {
        id: "drive-case",
        type: "line",
        source: "drive",
        paint: {
          "line-color": satellite ? "#1d1d1f" : "#ffffff",
          "line-width": 7,
          "line-opacity": route ? 0.92 : 0,
        },
      },
      before
    );
    map.addLayer(
      {
        id: "drive-line",
        type: "line",
        source: "drive",
        paint: {
          "line-color": "#1d1d1f",
          "line-width": 3.25,
          "line-opacity": route ? (preview ? 0.55 : 0.92) : 0,
          ...(preview ? { "line-dasharray": [1.6, 1.4] } : {}),
        },
      },
      before
    );
    map.addSource("drive-ends", { type: "geojson", data: endsCollection(ends) });
    map.addLayer({
      id: "drive-ends",
      type: "circle",
      source: "drive-ends",
      paint: {
        "circle-radius": ["match", ["get", "role"], "end", 6.5, 5.5],
        "circle-color": ["match", ["get", "role"], "end", "#1d1d1f", "#ffffff"],
        "circle-stroke-width": 2,
        "circle-stroke-color": "#1d1d1f",
      },
    });
  } catch {
    /* style not ready */
  }
}

function addBridgeOverlay(map, data, selectedId, basemap, codes) {
  if (!map.getStyle()) return false;
  try {
    stripOverlay(map);
    const satellite = basemap === "satellite";
    map.addSource("bridges", { type: "geojson", data: data || empty });
    map.addLayer({
      id: "bridges-dots",
      type: "circle",
      source: "bridges",
      filter: dotsFilter(codes),
      paint: {
        "circle-radius": [
          "case",
          ["in", ["get", "status"], ["literal", ["K", "P", "R", "D"]]],
          6.5,
          5.2,
        ],
        "circle-color": [
          "match",
          ["get", "condition"],
          "P",
          CONDITION_COLORS.P,
          "F",
          CONDITION_COLORS.F,
          "G",
          CONDITION_COLORS.G,
          CONDITION_COLORS.U,
        ],
        "circle-stroke-width": satellite
          ? 1.2
          : [
              "case",
              ["in", ["get", "status"], ["literal", ["K", "P", "R", "D"]]],
              1.4,
              0,
            ],
        "circle-stroke-color": satellite ? "#1d1d1f" : "#ffffff",
        "circle-opacity": 0.94,
      },
    });
    map.addLayer({
      id: "bridges-selected",
      type: "circle",
      source: "bridges",
      filter: selectedFilter(selectedId, codes),
      paint: {
        "circle-radius": 9,
        "circle-color": "transparent",
        "circle-stroke-width": 2,
        "circle-stroke-color": satellite ? "#ffffff" : "#1d1d1f",
      },
    });
    return true;
  } catch {
    return false;
  }
}

export default function MapView({
  center,
  zoom,
  geojson,
  selectedId,
  basemap = "map",
  visibleConditions = ["G", "F", "P"],
  route = null,
  routePreview = false,
  tripEnds = null,
  pickMode = false,
  follow = null,
  followOn = false,
  userFix = null,
  onReady,
  onMove,
  onSelect,
  onDeselect,
  onPickPoint,
  onFollowBreak,
}) {
  const root = useRef(null);
  const mapRef = useRef(null);
  const onMoveRef = useRef(onMove);
  const onSelectRef = useRef(onSelect);
  const onDeselectRef = useRef(onDeselect);
  const onPickPointRef = useRef(onPickPoint);
  const geojsonRef = useRef(geojson);
  const selectedRef = useRef(selectedId);
  const basemapRef = useRef(basemap);
  const codesRef = useRef(visibleConditions);
  const routeRef = useRef(route);
  const previewRef = useRef(routePreview);
  const endsRef = useRef(tripEnds);
  const pickRef = useRef(pickMode);
  const followOnRef = useRef(followOn);
  const onFollowBreakRef = useRef(onFollowBreak);
  const puckRef = useRef(null);
  onMoveRef.current = onMove;
  onSelectRef.current = onSelect;
  onDeselectRef.current = onDeselect;
  onPickPointRef.current = onPickPoint;
  onFollowBreakRef.current = onFollowBreak;
  geojsonRef.current = geojson;
  selectedRef.current = selectedId;
  basemapRef.current = basemap;
  codesRef.current = visibleConditions;
  routeRef.current = route;
  previewRef.current = routePreview;
  endsRef.current = tripEnds;
  pickRef.current = pickMode;
  followOnRef.current = followOn;

  useEffect(() => {
    if (!root.current || mapRef.current) return undefined;
    const map = new maplibregl.Map({
      container: root.current,
      style: styleFor(basemap),
      center: [center.lng, center.lat],
      zoom,
      attributionControl: false,
      pitchWithRotate: false,
      dragRotate: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      "bottom-right"
    );

    const onDotClick = (event) => {
      if (pickRef.current) return;
      const feature = event.features?.[0];
      if (feature?.properties?.id) {
        event.originalEvent?.stopPropagation?.();
        onSelectRef.current(feature.properties.id);
      }
    };
    const onMapClick = (event) => {
      if (pickRef.current) {
        onPickPointRef.current?.({
          lng: event.lngLat.lng,
          lat: event.lngLat.lat,
        });
        return;
      }
      const hits = map.getLayer("bridges-dots")
        ? map.queryRenderedFeatures(event.point, { layers: ["bridges-dots"] })
        : [];
      if (!hits.length) {
        onDeselectRef.current?.();
      }
    };
    const bindOverlayEvents = () => {
      map.off("click", "bridges-dots", onDotClick);
      map.on("click", "bridges-dots", onDotClick);
      map.off("mouseenter", "bridges-dots");
      map.off("mouseleave", "bridges-dots");
      map.on("mouseenter", "bridges-dots", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "bridges-dots", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    const installOverlay = () => {
      const ok = addBridgeOverlay(
        map,
        geojsonRef.current,
        selectedRef.current,
        basemapRef.current,
        codesRef.current
      );
      if (ok) {
        addRouteOverlay(
          map,
          routeRef.current,
          endsRef.current,
          previewRef.current,
          basemapRef.current
        );
        bindOverlayEvents();
        return;
      }
      map.once("idle", installOverlay);
    };

    map.on("load", () => {
      installOverlay();
      let timer;
      const emit = () => onMoveRef.current(map);
      map.on("moveend", () => {
        clearTimeout(timer);
        timer = setTimeout(emit, 220);
      });
      map.on("click", onMapClick);
      map.on("dragstart", () => {
        if (followOnRef.current) onFollowBreakRef.current?.();
      });
      onReady(map);
      emit();
    });
    map.on("style.load", installOverlay);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const didInit = useRef(false);
  useEffect(() => {
    if (!didInit.current) {
      didInit.current = true;
      return;
    }
    const map = mapRef.current;
    if (!map) return;
    map.setStyle(styleFor(basemap), { diff: false });
  }, [basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getSource("bridges") || !geojson) return;
    map.getSource("bridges").setData(geojson);
  }, [geojson]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("bridges-dots")) return;
    map.setFilter("bridges-dots", dotsFilter(visibleConditions));
    if (map.getLayer("bridges-selected")) {
      map.setFilter(
        "bridges-selected",
        selectedFilter(selectedId, visibleConditions)
      );
    }
  }, [selectedId, visibleConditions]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getStyle()) return;
    if (map.getSource("drive") && map.getSource("drive-ends")) {
      map.getSource("drive").setData(routeCollection(route));
      map.getSource("drive-ends").setData(endsCollection(tripEnds));
      if (map.getLayer("drive-line")) {
        map.setPaintProperty(
          "drive-line",
          "line-opacity",
          route ? (routePreview ? 0.55 : 0.92) : 0
        );
        map.setPaintProperty(
          "drive-line",
          "line-dasharray",
          routePreview ? [1.6, 1.4] : [1, 0]
        );
      }
      if (map.getLayer("drive-case")) {
        map.setPaintProperty("drive-case", "line-opacity", route ? 0.92 : 0);
      }
      return;
    }
    addRouteOverlay(map, route, tripEnds, routePreview, basemap);
  }, [route, routePreview, tripEnds, basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    if (!userFix) {
      puckRef.current?.remove();
      puckRef.current = null;
      return undefined;
    }
    const heading = Number.isFinite(userFix.heading) ? userFix.heading : 0;
    if (!puckRef.current) {
      const el = document.createElement("div");
      el.className = "user-puck";
      el.setAttribute("aria-hidden", "true");
      puckRef.current = new maplibregl.Marker({
        element: el,
        rotationAlignment: "map",
        pitchAlignment: "viewport",
      })
        .setLngLat([userFix.lng, userFix.lat])
        .setRotation(heading)
        .addTo(map);
    } else {
      puckRef.current.setLngLat([userFix.lng, userFix.lat]);
      puckRef.current.setRotation(heading);
    }
    return undefined;
  }, [userFix]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (!followOn || !follow) {
      if (map.getPitch() > 0.5 || Math.abs(map.getBearing()) > 0.5) {
        map.easeTo({ pitch: 0, bearing: 0, duration: 220 });
      }
      return;
    }
    map.easeTo({
      center: [follow.lng, follow.lat],
      zoom: Math.max(map.getZoom(), 15.4),
      bearing: Number.isFinite(follow.heading) ? follow.heading : map.getBearing(),
      pitch: 48,
      duration: 260,
      easing: (t) => 1 - (1 - t) * (1 - t),
      essential: true,
    });
  }, [follow, followOn]);

  return (
    <div
      ref={root}
      className={`map map-${basemap}${pickMode ? " is-pick" : ""}${followOn ? " is-nav" : ""}`}
    />
  );
}
