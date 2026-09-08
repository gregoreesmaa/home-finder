"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  MOCK_HEXES,
  legendBuckets,
  nearestHeatPoint,
  popupText,
  resolveHexes,
  toHeatPoints,
  type AreaHex,
  type HeatPoint,
} from "../lib/heatmap";

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
 */
export function ListingMap({
  hexes,
  initialMode = "heatmap",
}: {
  hexes?: AreaHex[];
  initialMode?: Mode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>(initialMode);
  const [remote, setRemote] = useState<AreaHex[] | null>(null);
  const [selected, setSelected] = useState<HeatPoint | null>(null);

  // Fetch live scores unless the caller passes hexes explicitly.
  useEffect(() => {
    if (hexes) return;
    if (
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).has("mock")
    ) {
      setRemote(MOCK_HEXES);
      return;
    }
    let cancelled = false;
    fetch(`${SCORING_URL}/area-scores`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((json: unknown) => {
        if (!cancelled) setRemote(resolveHexes(json, MOCK_HEXES));
      })
      .catch(() => {
        if (!cancelled) setRemote(MOCK_HEXES);
      });
    return () => {
      cancelled = true;
    };
  }, [hexes]);

  const points = useMemo(
    () => toHeatPoints(hexes ?? remote ?? MOCK_HEXES),
    [hexes, remote],
  );
  const legend = useMemo(() => legendBuckets(), []);

  useEffect(() => {
    let cancelled = false;
    let cleanup = () => {};
    (async () => {
      const [
        { default: maplibregl },
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
      // Click popup works in both modes: select the nearest hex cell.
      const onClick = (e: { lngLat: { lng: number; lat: number } }) => {
        setSelected(nearestHeatPoint(points, e.lngLat.lng, e.lngLat.lat));
      };
      map.on("click", onClick);
      cleanup = () => {
        map.off("click", onClick);
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
