"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ESTONIA_BBOX,
  HEAT_SOURCE_ET,
  MOCK_HEXES,
  buildViewportGrid,
  heatmapLayerProps,
  hexRadiusForZoom,
  hexesFromGeoJSON,
  legendBuckets,
  listingsToPoints,
  mergeHeatData,
  nearestHeatPoint,
  pickHeatInput,
  popupText,
  resolutionForZoom,
  toHeatPoints,
  type AreaHex,
  type BBox,
  type HeatPoint,
  type HeatSource,
} from "../lib/heatmap";
import type { MockListing } from "../lib/mockListings";
import type { MapboxOverlay } from "@deck.gl/mapbox";
import type {
  HeatmapLayer,
  HexagonLayer,
} from "@deck.gl/aggregation-layers";

export { MOCK_HEXES };

const ESTONIA_CENTER: [number, number] = [25.0, 58.75];
const SCORING_URL =
  process.env.NEXT_PUBLIC_SCORING_URL ?? "http://localhost:8000";

type Mode = "heatmap" | "hex";

type DeckKinds = {
  HeatmapLayer: typeof HeatmapLayer;
  HexagonLayer: typeof HexagonLayer;
};

/**
 * Red -> amber -> green ramp, shared by both layers and the legend (#72).
 * The low end is faint: fringe pixels between sparse cells must not read
 * as solid "bad" — only real low-goodness cores render solid red.
 */
const GOODNESS_COLORS: [number, number, number, number][] = [
  [220, 60, 50, 30],
  [220, 60, 50, 170],
  [230, 170, 40, 190],
  [46, 160, 67, 190],
];

/**
 * Build the deck.gl layer for the current mode over a continuous gap-free
 * surface (#72): sparse 0.25-degree cells are resampled onto a full-viewport
 * IDW grid (finer steps when zoomed in), so every visible pixel maps to a
 * colored cell instead of isolated blobs. MEAN aggregation so overlapping
 * cells average instead of piling up, threshold 0 so fringe pixels stay
 * colored, and the red->green ramp for goodness.
 */
function makeHeatLayers(
  deck: DeckKinds,
  mode: Mode,
  points: HeatPoint[],
  zoom: number,
  bbox: BBox,
  surfaceParam?: HeatPoint[],
): (HeatmapLayer | HexagonLayer)[] {
  const surface = surfaceParam ?? buildViewportGrid(points, bbox, zoom);
  const data = surface.length > 0 ? surface : points;
  if (mode === "hex") {
    return [
      new deck.HexagonLayer({
        id: "goodness-hex",
        data,
        getPosition: (d: HeatPoint) => [d.lon, d.lat],
        getColorWeight: (d: HeatPoint) => d.weight * 100,
        getColorValue: (cell: HeatPoint[]) =>
          cell.reduce((s, p) => s + p.weight * 100, 0) / cell.length,
        colorRange: GOODNESS_COLORS,
        radius: hexRadiusForZoom(zoom),
        coverage: 1,
        extruded: false,
        pickable: true,
        autoHighlight: true,
      }),
    ];
  }
  const hp = heatmapLayerProps(zoom);
  return [
    new deck.HeatmapLayer({
      id: "goodness-heat",
      data,
      getPosition: (d: HeatPoint) => [d.lon, d.lat],
      getWeight: (d: HeatPoint) => d.weight,
      aggregation: hp.aggregation,
      radiusPixels: hp.radiusPixels,
      intensity: hp.intensity,
      threshold: hp.threshold,
      colorRange: GOODNESS_COLORS,
    }),
  ];
}

/**
 * MapLibre base (Carto light) + deck.gl layer over H3 area-scores:
 * HeatmapLayer (continuous regional goodness overlay) or HexagonLayer
 * (cluster toggle) with legend + click popup.
 *
 * Data: GET /area-scores (GeoJSON). With ?mock=1, when no `hexes` prop is
 * given and the API is unreachable, the bundled mock hexes are used.
 *
 * The map instance is created once (#71): data/mode changes only swap the
 * deck.gl layers via overlay.setProps, so panning never snaps the camera
 * back to the Estonia default. The container's data-camera attribute
 * (lng,lat,zoom) exposes the viewport for tests.
 *
 * Note: deck.gl 9.4 logs "luma.gl: Binding weightsTexture not set" on the
 * WebGL path. It is a known benign upstream warning (visgl/deck.gl#10483
 * notes it on their own unchanged baseline) — the heatmap still paints.
 */
export function ListingMap({
  hexes,
  listings,
  selectedId,
  initialMode = "heatmap",
  onPickLocation,
}: {
  hexes?: AreaHex[];
  listings?: MockListing[];
  selectedId?: string | null;
  initialMode?: Mode;
  /** When set, map clicks report coordinates instead of opening popups (#74). */
  onPickLocation?: (lon: number, lat: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ getBounds: () => { getWest: () => number; getSouth: () => number; getEast: () => number; getNorth: () => number } } | null>(null);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [remote, setRemote] = useState<AreaHex[] | null>(null);
  const [liveCells, setLiveCells] = useState(false);
  const [source, setSource] = useState<HeatSource>("mock");
  const [selected, setSelected] = useState<HeatPoint | null>(null);
  // Viewport drives the continuous surface: zoom picks the grid granularity
  // (coarse out, fine in) and bbox bounds the full-viewport resampling.
  const [zoom, setZoom] = useState(7);
  const [bbox, setBbox] = useState<BBox>(ESTONIA_BBOX);

  const listingPoints = useMemo(() => listingsToPoints(listings ?? []), [listings]);

  // Pick heat input (B1): live DB cells win, else bin geocoded listings,
  // else the bundled mock. Runs on every cell/listings change.
  const [picked, setPicked] = useState<AreaHex[]>(MOCK_HEXES);
  useEffect(() => {
    if (hexes) {
      setPicked(hexes);
      setSource("cells");
      return;
    }
    if (remote === null) {
      setPicked(MOCK_HEXES);
      setSource("mock");
      return;
    }
    const p = pickHeatInput(remote, liveCells, listingPoints, MOCK_HEXES);
    setPicked(p.hexes);
    setSource(p.source);
  }, [hexes, remote, liveCells, listingPoints]);

  // Fetch live cells (B3: bbox-aware on move, debounced; resolution-aware
  // on zoom so the API serves coarse cells out and finer subcells in),
  // unless the caller passes hexes explicitly or ?mock=1 forces the
  // bundled fallback. The loader lives in a ref so the map-init effect
  // can call it on moveend.
  const loadRef = useRef<(bboxParam?: string, zoomParam?: number) => void>(() => {});
  useEffect(() => {
    if (hexes) return;
    if (
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).has("mock")
    ) {
      setRemote([]);
      setLiveCells(false);
      return;
    }
    let cancelled = false;
    loadRef.current = (bboxParam?: string, zoomParam?: number) => {
      const resolution = resolutionForZoom(zoomParam ?? 7);
      const url = bboxParam
        ? `${SCORING_URL}/heatmap-cells?bbox=${bboxParam}&resolution=${resolution}`
        : `${SCORING_URL}/area-scores?resolution=${resolution}`;
      fetch(url)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((json: unknown) => {
          if (cancelled) return;
          const obj = json as { features?: unknown; live?: unknown };
          setRemote(hexesFromGeoJSON(obj));
          setLiveCells(obj?.live === true);
        })
        .catch(() => {
          if (cancelled) return;
          setRemote([]);
          setLiveCells(false);
        });
    };
    loadRef.current();
    return () => {
      cancelled = true;
    };
  }, [hexes]);

  // Involve all available data: combine cells, listings, and neighborhood benchmarks
  const combinedPoints = useMemo(
    () => mergeHeatData(hexes ?? picked, listingPoints),
    [hexes, picked, listingPoints],
  );
  const points = useMemo(() => toHeatPoints(combinedPoints), [combinedPoints]);

  const [localRange, setLocalRange] = useState<{ min: number; max: number } | null>(null);
  const legend = useMemo(() => {
    if (localRange && localRange.max > localRange.min) {
      return legendBuckets(localRange.min, localRange.max);
    }
    return legendBuckets();
  }, [localRange]);

  // D3: a ?selected=<id> (from "Näita kaardil") opens the nearest cell popup.
  useEffect(() => {
    if (!selectedId || !listings) {
      if (!selectedId) setSelected(null);
      return;
    }
    const target = listings.find((l) => l.id === selectedId);
    if (!target || typeof target.lon !== "number" || typeof target.lat !== "number") return;
    setSelected(nearestHeatPoint(points, target.lon, target.lat));
  }, [selectedId, listings, points]);

  // Latest points for the click handler + layer swaps without re-init.
  const pointsRef = useRef<HeatPoint[]>([]);
  const deckRef = useRef<DeckKinds | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const pickRef = useRef(onPickLocation);
  pickRef.current = onPickLocation;

  // Data/mode/viewport changes swap layers in place; the camera is never
  // touched. Zoom/bbox only resample the surface, never re-create the map.
  useEffect(() => {
    pointsRef.current = points;
    if (deckRef.current && overlayRef.current) {
      const surface = buildViewportGrid(points, bbox, zoom);
      if (
        surface.length > 0 &&
        surface[0].localMin !== undefined &&
        surface[0].localMax !== undefined
      ) {
        setLocalRange({ min: surface[0].localMin, max: surface[0].localMax });
      }
      overlayRef.current.setProps({
        layers: makeHeatLayers(deckRef.current, mode, points, zoom, bbox, surface),
      });
    }
  }, [points, mode, zoom, bbox]);

  useEffect(() => {
    let cancelled = false;
    let cleanup = () => {};
    (async () => {
      const [
        maplibregl,
        { MapboxOverlay },
        { HeatmapLayer, HexagonLayer },
      ] = (await Promise.all([
        import("maplibre-gl"),
        import("@deck.gl/mapbox"),
        import("@deck.gl/aggregation-layers"),
      ])) as never as [
        typeof import("maplibre-gl"),
        typeof import("@deck.gl/mapbox"),
        typeof import("@deck.gl/aggregation-layers"),
      ];
      if (cancelled || !ref.current) return;
      deckRef.current = { HeatmapLayer, HexagonLayer };
      const map = new maplibregl.Map({
        container: ref.current,
        style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        center: ESTONIA_CENTER,
        zoom: 7,
      });
      const overlay = new MapboxOverlay({
        interleaved: true,
        layers: makeHeatLayers(
          deckRef.current,
          initialMode,
          pointsRef.current,
          7,
          ESTONIA_BBOX,
        ),
      });
      map.addControl(overlay);
      mapRef.current = map;
      overlayRef.current = overlay;
      const stampCamera = () => {
        const c = map.getCenter();
        ref.current?.setAttribute(
          "data-camera",
          `${c.lng.toFixed(3)},${c.lat.toFixed(3)},${map.getZoom().toFixed(2)}`,
        );
      };
      stampCamera(); // present even before the style finishes loading
      // Click popup works in both modes: select the nearest hex cell.
      // In pick mode the click reports coordinates instead (#74 POIs).
      const onClick = (e: { lngLat: { lng: number; lat: number } }) => {
        if (pickRef.current) {
          pickRef.current(e.lngLat.lng, e.lngLat.lat);
          return;
        }
        setSelected(nearestHeatPoint(pointsRef.current, e.lngLat.lng, e.lngLat.lat));
      };
      map.on("click", onClick);
      // B3: reload cells for the new viewport (debounced in the loader path)
      // and resample the continuous surface for the new zoom/bbox.
      let moveTimer: ReturnType<typeof setTimeout> | null = null;
      const onMove = () => {
        stampCamera();
        const b = map.getBounds();
        const bb: BBox = {
          minlon: b.getWest(),
          minlat: b.getSouth(),
          maxlon: b.getEast(),
          maxlat: b.getNorth(),
        };
        setZoom(map.getZoom());
        setBbox(bb);
        if (moveTimer) clearTimeout(moveTimer);
        moveTimer = setTimeout(() => {
          loadRef.current(
            `${bb.minlon},${bb.minlat},${bb.maxlon},${bb.maxlat}`,
            map.getZoom(),
          );
        }, 600);
      };
      map.on("moveend", onMove);
      map.on("load", stampCamera);
      cleanup = () => {
        if (moveTimer) clearTimeout(moveTimer);
        map.off("click", onClick);
        map.off("moveend", onMove);
        map.off("load", stampCamera);
        mapRef.current = null;
        overlayRef.current = null;
        map.remove();
      };
    })();
    return () => {
      cancelled = true;
      cleanup();
    };
    // Mount-once (#71): points/mode flow through pointsRef + setProps above.
  }, []);

  return (
    <section aria-label="Piirkondade heatmap">
      <div role="group" aria-label="Kihi vaade">
        <button
          type="button"
          aria-pressed={mode === "heatmap"}
          onClick={() => setMode("heatmap")}
        >
          Heatmap
        </button>
        <button
          type="button"
          aria-pressed={mode === "hex"}
          onClick={() => setMode("hex")}
        >
          Hex
        </button>
      </div>
      <p aria-live="polite">
        Andmeallikas: {HEAT_SOURCE_ET[source]} ·{" "}
        {liveCells && source === "cells" ? "reaalajas" : "demo-andmed"}
      </p>
      <div
        ref={ref}
        role="application"
        aria-label="Eesti piirkondade kaart"
        style={{ height: 480 }}
      />
      <ul aria-label="Legend: roheline hea, kollane keskmine, punane halb">
        {legend.map((b) => (
          <li key={b.level}>
            <span
              aria-hidden="true"
              style={{
                display: "inline-block",
                width: 12,
                height: 12,
                background: b.css,
              }}
            />{" "}
            {b.label}
          </li>
        ))}
      </ul>
      {selected && (
        <div role="dialog" aria-label="Piirkonna info">
          <p>{popupText(selected)}</p>
          <button type="button" onClick={() => setSelected(null)}>
            Sulge
          </button>
        </div>
      )}
    </section>
  );
}
