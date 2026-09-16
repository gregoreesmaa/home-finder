"use client";

import { useEffect, useRef } from "react";
import { ValueHeatLayer } from "./ValueHeatLayer";
import {
  buildScoredField,
  fieldResolution,
  sampleScored,
  scoredToRgba,
  type ScoredField,
} from "../lib/distanceField";
import type { BBoxLike, BonusSpec, ParkOutline, WalkRasterDoc } from "../lib/layers";
import type { FloodArea } from "../lib/layers_flood";
import type { MaaParcelArea } from "../lib/layers_maaparcel";
import type { EelisArea } from "../lib/layers_eelis";
import type { SevesoArea } from "../lib/layers_p4_seveso";
import {
  applyFloodPolygons,
  applyMaaParcelPolygons,
  applyEelisPolygons,
  applyOutlines,
  applyPointOverlay,
  applySevesoPolygons,
  applyUsePolygons,
  clearVectorOverlays,
  type OutlineMap,
  type UseFillPolygon,
} from "../lib/outlines";
import type { OverlayPoint } from "../lib/overlays";
import { decodeRaster, rasterToRgba, sampleRaster, type DecodedRaster } from "../lib/walkRaster";
import { lutCssGradient } from "../lib/valueScale";

export interface HeatPoint {
  lon: number;
  lat: number;
  /** Weekday departures for the "trips" score; absent means unknown. */
  t?: number;
  /** Hectares for the "area" score (parks); absent means no area. */
  a?: number;
}

const ESTONIA_CENTER: [number, number] = [25.0, 58.75];

/**
 * One overlay slot, painted above the raster: flood polygons win when
 * present, then parcel fills, then eelis polygons, then seveso danger
 * fills, then point markers, then use-fills (page guarantees
 * flood-areas, maa-parcels, eelis-areas, seveso-areas, outlines and
 * points never coincide — and fills and points never coincide either),
 * otherwise park outlines; hidden clears the slot. All painters clear
 * stale layers first, so switches never stack.
 */
function paintOverlay(
  mapObj: OutlineMap,
  opts: {
    outlines?: ParkOutline[] | null;
    floodAreas?: FloodArea[] | null;

    maaParcels?: MaaParcelArea[] | null;

    eelisAreas?: EelisArea[] | null;
    sevesoAreas?: SevesoArea[] | null;
    overlayPoints?: OverlayPoint[] | null;
    usePolygons?: UseFillPolygon[] | null;
    overlayColor?: string;
    showOverlay?: boolean;
  },
): void {
  if (opts.showOverlay === false) {
    clearVectorOverlays(mapObj);
    return;
  }
  // FLOOD-HOOK (#487): floodzone choropleth fills (polygons only — no
  // score field is painted for this layer, by design).
  if (opts.floodAreas && opts.floodAreas.length > 0) {
    applyFloodPolygons(mapObj, opts.floodAreas, { color: opts.overlayColor ?? "#1e3a8a" });

    return;
  }
  // MAAPARCEL-HOOK (#491): maaparcel class fills (polygons only — no
  // score field is painted for this layer, by design).
  if (opts.maaParcels && opts.maaParcels.length > 0) {
    applyMaaParcelPolygons(mapObj, opts.maaParcels, { casing: opts.overlayColor ?? "#701a75" });

    return;
  }
  // EELIS-HOOK (#488): eelis choropleth fills (polygons only — no score
  // field is painted for these layers, by design).
  if (opts.eelisAreas && opts.eelisAreas.length > 0) {
    applyEelisPolygons(mapObj, opts.eelisAreas, { color: opts.overlayColor ?? "#1a2e05" });
    return;
  }
  // SEVESO-HOOK (#613): seveso danger-class fills (polygons only — no
  // score field is painted for this layer, by design).
  if (opts.sevesoAreas && opts.sevesoAreas.length > 0) {
    applySevesoPolygons(mapObj, opts.sevesoAreas);
    return;
  }
  if (opts.overlayPoints && opts.overlayPoints.length > 0) {
    applyPointOverlay(mapObj, opts.overlayPoints, { color: opts.overlayColor ?? "#1d4ed8" });
    return;
  }
  // PLANKTPR-HOOK (#492): designated-use fills win over the (empty)
  // unknown field; an empty harvest falls through to no outlines.
  if (opts.usePolygons && opts.usePolygons.length > 0) {
    applyUsePolygons(mapObj, opts.usePolygons);
    return;
  }
  applyOutlines(mapObj, opts.outlines);
}

/**
 * Single-layer value heatmap: MapLibre base + per-pixel exact shader field.
 * Hover reads the exact interpolated value under the cursor; areas without
 * data stay unpainted and read as "no data", never as zero.
 */
export function ValueHeatMap({
  points,
  radiusKm,
  bonus,
  raster,
  outlines,
  floodAreas,

  maaParcels,

  eelisAreas,
  sevesoAreas,
  overlayPoints,
  usePolygons,
  overlayColor,
  overlayLegend,
  showOverlay,
  title,
  goodLabel,
  badLabel,
  sourceNote,
  initialCenter,
  initialZoom,
  onViewChange,
}: {
  points: HeatPoint[];
  radiusKm: number;
  bonus: BonusSpec;
  /** Pre-scored county walk raster (transit); splat path when null. */
  raster?: WalkRasterDoc | null;
  /** Park polygon outlines (parks layer only); boundary overlay. */
  outlines?: ParkOutline[] | null;
  /** KAUR flood-zone fills (floodzone layer only); choropleth overlay. */
  floodAreas?: FloodArea[] | null;

  /** Kataster parcel fills (maaparcel layer only); class choropleth. */
  maaParcels?: MaaParcelArea[] | null;

  /** EELIS nature fills (eelis layers only); choropleth overlay. */
  eelisAreas?: EelisArea[] | null;
  /** Seveso danger fills (seveso layer only); danger-class choropleth. */
  sevesoAreas?: SevesoArea[] | null;
  /** Point markers drawn ABOVE the raster (all layers but parks). */
  overlayPoints?: OverlayPoint[] | null;
  /** Designated-use fills drawn ABOVE the field (planktpr only). */
  usePolygons?: UseFillPolygon[] | null;
  overlayColor?: string;
  /** Legend line explaining the markers + their weights (Estonian). */
  overlayLegend?: string | null;
  /** Per-layer overlay toggle from the page. */
  showOverlay?: boolean;
  title: string;
  goodLabel: string;
  badLabel: string;
  sourceNote: string;
  /** Deep-link camera (?c=lon,lat,z); defaults to the Estonia overview. */
  initialCenter?: [number, number];
  initialZoom?: number;
  /** Current view bbox (unpadded) on every settled move, for refetching. */
  onViewChange?: (bbox: BBoxLike) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const layerRef = useRef<ValueHeatLayer | null>(null);
  const gridRef = useRef<ScoredField | null>(null);
  const rasterRef = useRef<DecodedRaster | null>(null);
  const decodedRef = useRef<{ doc: WalkRasterDoc; raster: DecodedRaster | null } | null>(null);
  const refreshRef = useRef<(() => void) | null>(null);
  const mapRef = useRef<OutlineMap | null>(null);
  const dataRef = useRef({
    points,
    radiusKm,
    bonus,
    raster,
    outlines,
    floodAreas,

    maaParcels,

    eelisAreas,
    sevesoAreas,
    overlayPoints,
    usePolygons,
    overlayColor,
    showOverlay,
  });
  dataRef.current = {
    points,
    radiusKm,
    bonus,
    raster,
    outlines,
    floodAreas,

    maaParcels,

    eelisAreas,
    sevesoAreas,
    overlayPoints,
    usePolygons,
    overlayColor,
    showOverlay,
  };
  const viewCbRef = useRef(onViewChange);
  viewCbRef.current = onViewChange;
  // Mount-time camera only: later prop changes must not yank the camera.
  const initCenterRef = useRef(initialCenter);
  const initZoomRef = useRef(initialZoom);

  useEffect(() => {
    let cancelled = false;
    let map: { remove: () => void } | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;
    (async () => {
      const maplibregl = (await import("maplibre-gl")) as typeof import("maplibre-gl");
      if (cancelled || !ref.current) return;
      const mapObj = new maplibregl.Map({
        container: ref.current,
        style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        center: initCenterRef.current ?? ESTONIA_CENTER,
        zoom: initZoomRef.current ?? 7,
      });
      const layer = new ValueHeatLayer("value-heat");
      layerRef.current = layer;

      const refresh = () => {
        if (cancelled) return;
        const b = mapObj.getBounds();
        // Pad so edge kernels never clip; recompute only when the view moves.
        const padLon = (b.getEast() - b.getWest()) * 0.15;
        const padLat = (b.getNorth() - b.getSouth()) * 0.15;
        const box = {
          minlon: b.getWest() - padLon,
          minlat: b.getSouth() - padLat,
          maxlon: b.getEast() + padLon,
          maxlat: b.getNorth() + padLat,
        } as const;
        const { points: pts, radiusKm: rKm, bonus: spec, raster: doc } = dataRef.current;
        // Walk-raster path: one county texture for every view (pan/zoom are
        // free on the GPU); decoded once per doc identity.
        if (doc) {
          let cached = decodedRef.current;
          if (!cached || cached.doc !== doc) {
            cached = { doc, raster: decodeRaster(doc) };
            decodedRef.current = cached;
          }
          rasterRef.current = cached.raster;
          gridRef.current = null;
          if (!cached.raster) {
            layer.setField(null, 0, 0, [0, 0, 0, 0]);
            return;
          }
          const b = cached.raster.bbox;
          layer.setField(rasterToRgba(cached.raster), cached.raster.cols, cached.raster.rows, [
            b.minlon,
            b.minlat,
            b.maxlon,
            b.maxlat,
          ]);
          return;
        }
        rasterRef.current = null;
        const valid = pts.filter((c) => Number.isFinite(c.lon) && Number.isFinite(c.lat));
        if (valid.length === 0) {
          gridRef.current = null;
          layer.setField(null, 0, 0, [0, 0, 0, 0]);
          return;
        }
        // FIXIT-HOOK (#623): pins layers render markers ONLY (the
        // field stays unknown everywhere by decision — pins measure
        // reporting activity, not place quality). Clearing the field
        // keeps the map clean: an all-NaN grid would otherwise paint
        // the viewport score-0 red. Markers still ride paintOverlay.
        if (spec.kind === "pins") {
          gridRef.current = null;
          layer.setField(null, 0, 0, [0, 0, 0, 0]);
          return;
        }
        const res = fieldResolution(box, rKm);
        const grid = buildScoredField(valid, box, res.cols, res.rows, rKm, spec);
        gridRef.current = grid;
        layer.setField(scoredToRgba(grid), res.cols, res.rows, [
          box.minlon,
          box.minlat,
          box.maxlon,
          box.maxlat,
        ]);
      };
      refreshRef.current = refresh;

      mapObj.on("load", () => {
        if (cancelled) return;
        // Heat under roads and labels: full-opacity color stays exact while
        // street names remain readable for the house-hunting use case.
        const styleLayers = mapObj.getStyle()?.layers;
        const beforeId = styleLayers?.find((l) => l.type === "line" || l.type === "symbol")?.id;
        try {
          if (beforeId) mapObj.addLayer(layer as unknown as maplibregl.CustomLayerInterface, beforeId);
          else mapObj.addLayer(layer as unknown as maplibregl.CustomLayerInterface);
        } catch {
          mapObj.addLayer(layer as unknown as maplibregl.CustomLayerInterface);
        }
        mapRef.current = mapObj as unknown as OutlineMap;
        refresh();
        paintOverlay(mapRef.current, dataRef.current);
      });
      const schedule = () => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(refresh, 150);
        const c = mapObj.getCenter();
        ref.current?.setAttribute(
          "data-camera",
          `${c.lng.toFixed(3)},${c.lat.toFixed(3)},${mapObj.getZoom().toFixed(2)}`,
        );
        // Report the settled view upward so the page refetches points for
        // the visible area (complete local data instead of a capped set).
        const vb = mapObj.getBounds();
        viewCbRef.current?.({
          minlon: vb.getWest(),
          minlat: vb.getSouth(),
          maxlon: vb.getEast(),
          maxlat: vb.getNorth(),
        });
      };
      mapObj.on("moveend", schedule);
      mapObj.on("zoomend", schedule);

      mapObj.getCanvas().addEventListener("mousemove", (e: MouseEvent) => {
        const tip = tipRef.current;
        if (!tip) return;
        const rect = mapObj.getCanvas().getBoundingClientRect();
        const ll = mapObj.unproject([e.clientX - rect.left, e.clientY - rect.top]);
        const hit = rasterRef.current
          ? sampleRaster(rasterRef.current, ll.lng, ll.lat)
          : gridRef.current && sampleScored(gridRef.current, ll.lng, ll.lat);
        if (!hit) {
          tip.style.display = "none";
          return;
        }
        tip.style.display = "block";
        tip.style.left = `${e.clientX - rect.left + 12}px`;
        tip.style.top = `${e.clientY - rect.top + 12}px`;
        tip.textContent = `Headus ${Math.round(hit.value)}/100`;
      });
      mapObj.getCanvas().addEventListener("mouseleave", () => {
        if (tipRef.current) tipRef.current.style.display = "none";
      });

      map = { remove: () => mapObj.remove() };
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      layerRef.current = null;
      gridRef.current = null;
      mapRef.current = null;
      map?.remove();
    };
  }, []);

  // New layer data repaints the field without touching the camera.
  useEffect(() => {
    refreshRef.current?.();
  }, [points, radiusKm, bonus, raster]);

  // Overlay rides the map lifecycle: paint once loaded, clear on switch.
  useEffect(() => {
    if (mapRef.current) {
      // FLOOD-HOOK (#487): floodAreas join the painted slot.
      // MAAPARCEL-HOOK (#491): maaParcels join the painted slot.
      // EELIS-HOOK (#488): eelisAreas join the painted slot.
      // PLANKTPR-HOOK (#492): usePolygons join the painted slot.
      // SEVESO-HOOK (#613): sevesoAreas join the painted slot.
      paintOverlay(mapRef.current, { outlines, floodAreas, maaParcels, eelisAreas, sevesoAreas, overlayPoints, usePolygons, overlayColor, showOverlay });
    }
  }, [outlines, floodAreas, maaParcels, eelisAreas, sevesoAreas, overlayPoints, usePolygons, overlayColor, showOverlay]);

  return (
    <section aria-label={title}>
      <div
        ref={ref}
        data-testid="value-heat-map"
        style={{ position: "relative", width: "100%", height: 480 }}
      >
        <div
          ref={tipRef}
          role="status"
          style={{
            display: "none",
            position: "absolute",
            pointerEvents: "none",
            background: "rgba(20, 20, 20, 0.85)",
            color: "#fff",
            padding: "2px 8px",
            borderRadius: 4,
            fontSize: 12,
            zIndex: 1,
          }}
        />
      </div>
      <div
        role="img"
        aria-label={`Legend: ${goodLabel}; ${badLabel}`}
        style={{
          height: 12,
          background: lutCssGradient(),
          marginTop: 8,
        }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
        <span>{badLabel} · 0</span>
        <span>{goodLabel} · 100</span>
      </div>
      {showOverlay !== false && overlayLegend ? (
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, marginTop: 4 }}>
          <span
            aria-hidden="true"
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: overlayColor ?? "#1d4ed8",
              border: "2px solid #ffffff",
              boxShadow: "0 0 0 1px rgba(0,0,0,0.35)",
              flexShrink: 0,
            }}
          />
          <span>{overlayLegend}</span>
        </div>
      ) : null}
      <div style={{ fontSize: 12, opacity: 0.75 }}>Punane katab ka alasid, kus andmed puuduvad.</div>
      <p>
        <small>{sourceNote}</small>
      </p>
    </section>
  );
}
