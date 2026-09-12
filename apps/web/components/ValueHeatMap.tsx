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
import { applyOutlines, type OutlineMap } from "../lib/outlines";
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
  const dataRef = useRef({ points, radiusKm, bonus, raster, outlines });
  dataRef.current = { points, radiusKm, bonus, raster, outlines };
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
        applyOutlines(mapRef.current, dataRef.current.outlines);
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

  // Outlines ride the map lifecycle: paint once loaded, clear on switch.
  useEffect(() => {
    if (mapRef.current) applyOutlines(mapRef.current, outlines);
  }, [outlines]);

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
      <div style={{ fontSize: 12, opacity: 0.75 }}>Punane katab ka alasid, kus andmed puuduvad.</div>
      <p>
        <small>{sourceNote}</small>
      </p>
    </section>
  );
}
