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
  onReady,
  onMove,
  onSelect,
  onDeselect,
}) {
  const root = useRef(null);
  const mapRef = useRef(null);
  const onMoveRef = useRef(onMove);
  const onSelectRef = useRef(onSelect);
  const onDeselectRef = useRef(onDeselect);
  const geojsonRef = useRef(geojson);
  const selectedRef = useRef(selectedId);
  const basemapRef = useRef(basemap);
  const codesRef = useRef(visibleConditions);
  onMoveRef.current = onMove;
  onSelectRef.current = onSelect;
  onDeselectRef.current = onDeselect;
  geojsonRef.current = geojson;
  selectedRef.current = selectedId;
  basemapRef.current = basemap;
  codesRef.current = visibleConditions;

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
      const feature = event.features?.[0];
      if (feature?.properties?.id) {
        event.originalEvent?.stopPropagation?.();
        onSelectRef.current(feature.properties.id);
      }
    };
    const onMapClick = (event) => {
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

  return <div ref={root} className={`map map-${basemap}`} />;
}
