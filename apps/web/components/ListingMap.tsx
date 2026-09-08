"use client";

import { useEffect, useRef } from "react";
import type { AreaHex } from "../lib/heatmap";
import { toHeatPoints } from "../lib/heatmap";

const ESTONIA_CENTER: [number, number] = [25.0, 58.75];

/**
 * MapLibre base (Carto light) + deck.gl HeatmapLayer over H3 area-scores.
 * Map libs load lazily on the client; with ?mock=1 (or when the API is
 * unreachable) the layer renders from the bundled mock hexes.
 */
export const MOCK_HEXES: AreaHex[] = [
  { h3: "mock-tallinn", score_goodness: 85, lon: 24.75, lat: 59.43 },
  { h3: "mock-tartu", score_goodness: 62, lon: 26.72, lat: 58.37 },
  { h3: "mock-parnu", score_goodness: 30, lon: 24.5, lat: 58.38 },
];

export function ListingMap({ hexes }: { hexes?: AreaHex[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = toHeatPoints(hexes ?? MOCK_HEXES);
      const [{ default: maplibregl }, { MapboxOverlay }, { HeatmapLayer }] = (await Promise.all([
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
          new HeatmapLayer({
            id: "goodness-heat",
            data,
            getPosition: (d) => [d.lon, d.lat],
            getWeight: (d) => d.weight,
            radiusPixels: 60,
          }),
        ],
      });
      map.addControl(overlay);
      return () => map.remove();
    })();
    return () => {
      cancelled = true;
    };
  }, [hexes]);

  return <div ref={ref} aria-label="Piirkondade heatmap" style={{ height: 480 }} />;
}
