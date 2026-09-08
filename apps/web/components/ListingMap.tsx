"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  HEAT_SOURCE_ET,
  MOCK_HEXES,
  hexesFromGeoJSON,
  legendBuckets,
  listingsToPoints,
  nearestHeatPoint,
  pickHeatInput,
  popupText,
  toHeatPoints,
  type AreaHex,
  type HeatPoint,
  type HeatSource,
} from "../lib/heatmap";
import type { MockListing } from "../lib/mockListings";

export { MOCK_HEXES };

const ESTONIA_CENTER: [number, number] = [25.0, 58.75];
const SCORING_URL =
  process.env.NEXT_PUBLIC_SCORING_URL ?? "http://localhost:8000";

type Mode = "heatmap" | "hex";

/**
 * MapLibre base (Carto light) + deck.gl layer over H3 area-scores:
 * HeatmapLayer (density, weight = livability goodness) or HexagonLayer
 * (cluster toggle) with legend + click popup.
 *
 * Data: GET /area-scores (GeoJSON). With ?mock=1, when no `hexes` prop is
 * given and the API is unreachable, the bundled mock hexes are used.
 *
 * Note: deck.gl 9.4 logs "luma.gl: Binding weightsTexture not set" on the
 * WebGL path. It is a known benign upstream warning (visgl/deck.gl#10483
 * notes it on their own unchanged baseline) — the heatmap still paints.
 */
export function ListingMap({
  hexes,
  listings,
  initialMode = "heatmap",
}: {
  hexes?: AreaHex[];
  listings?: MockListing[];
  initialMode?: Mode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<{ getBounds: () => { getWest: () => number; getSouth: () => number; getEast: () => number; getNorth: () => number } } | null>(null);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [remote, setRemote] = useState<AreaHex[] | null>(null);
  const [liveCells, setLiveCells] = useState(false);
  const [source, setSource] = useState<HeatSource>("mock");
  const [selected, setSelected] = useState<HeatPoint | null>(null);

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

  // Fetch live cells (B3: bbox-aware on move, debounced), unless the caller
  // passes hexes explicitly or ?mock=1 forces the bundled fallback.
  // The loader lives in a ref so the map-init effect can call it on moveend.
  const loadRef = useRef<(bbox?: string) => void>(() => {});
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
    loadRef.current = (bbox?: string) => {
      const url = bbox
        ? `${SCORING_URL}/heatmap-cells?bbox=${bbox}`
        : `${SCORING_URL}/area-scores`;
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

  const points = useMemo(() => toHeatPoints(hexes ?? picked), [hexes, picked]);
  const legend = useMemo(() => legendBuckets(), []);

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
      const map = new maplibregl.Map({
        container: ref.current,
        style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        center: ESTONIA_CENTER,
        zoom: 7,
      });
      const overlay = new MapboxOverlay({
        interleaved: true,
        layers: [
          mode === "hex"
            ? new HexagonLayer({
                id: "goodness-hex",
                data: points,
                getPosition: (d: HeatPoint) => [d.lon, d.lat],
                getColorWeight: (d: HeatPoint) => d.weight * 100,
                getColorValue: (cell: HeatPoint[]) =>
                  cell.reduce((s, p) => s + p.weight * 100, 0) / cell.length,
                colorRange: [
                  [220, 60, 50],
                  [230, 170, 40],
                  [46, 160, 67],
                ],
                radius: 15000,
                coverage: 0.9,
                extruded: false,
                pickable: true,
                autoHighlight: true,
              })
            : new HeatmapLayer({
                id: "goodness-heat",
                data: points,
                getPosition: (d: HeatPoint) => [d.lon, d.lat],
                getWeight: (d: HeatPoint) => d.weight,
                radiusPixels: 60,
              }),
        ],
      });
      map.addControl(overlay);
      mapRef.current = map;
      // Click popup works in both modes: select the nearest hex cell.
      const onClick = (e: { lngLat: { lng: number; lat: number } }) => {
        setSelected(nearestHeatPoint(points, e.lngLat.lng, e.lngLat.lat));
      };
      map.on("click", onClick);
      // B3: reload cells for the new viewport (debounced in the loader path).
      let moveTimer: ReturnType<typeof setTimeout> | null = null;
      const onMove = () => {
        if (moveTimer) clearTimeout(moveTimer);
        moveTimer = setTimeout(() => {
          const b = map.getBounds();
          loadRef.current(
            `${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}`,
          );
        }, 600);
      };
      map.on("moveend", onMove);
      cleanup = () => {
        if (moveTimer) clearTimeout(moveTimer);
        map.off("click", onClick);
        map.off("moveend", onMove);
        mapRef.current = null;
        map.remove();
      };
    })();
    return () => {
      cancelled = true;
      cleanup();
    };
  }, [points, mode]);

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
