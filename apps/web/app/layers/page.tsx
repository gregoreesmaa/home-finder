"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ValueHeatMap } from "../../components/ValueHeatMap";
import { ESTONIA_BBOX } from "../../lib/heatmap";
import {
  LAYERS,
  bonusSpecFor,
  fetchLayerPoints,
  fetchParkAreas,
  fetchWindow,
  radiusKmFor,
  type BBoxLike,
  type LayerDef,
  type LayerId,
  type LayerPoint,
  type LayerProvenance,
  type ParkOutline,
  type TransitDistance,
  type WalkRasterDoc,
} from "../../lib/layers";
import {
  fetchGraphOverlay,
  needsGraphOverlay,
  overlayColorFor,
  overlayLegendFor,
  selectOverlayPoints,
  type OverlayPoint,
} from "../../lib/overlays";

/** Viewport bbox rounded for fetch stability (matches server key rounding). */
function sameView(a: BBoxLike, b: BBoxLike): boolean {
  return (
    a.minlon.toFixed(2) === b.minlon.toFixed(2) &&
    a.minlat.toFixed(2) === b.minlat.toFixed(2) &&
    a.maxlon.toFixed(2) === b.maxlon.toFixed(2) &&
    a.maxlat.toFixed(2) === b.maxlat.toFixed(2)
  );
}

/** Human age for cached data ("5 min", "3 h", "2 p"). */
function ageEt(ageMs: number | null): string {
  if (ageMs === null) return "";
  const min = Math.floor(ageMs / 60000);
  if (min < 1) return "paar sekundit";
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  if (h < 48) return `${h} h`;
  return `${Math.floor(h / 24)} p`;
}

/** Deep-link camera (?c=lon,lat,z); invalid values fall back to Estonia. */
function initialCamera(): { center?: [number, number]; zoom?: number } {
  if (typeof window === "undefined") return {};
  const parts = new URLSearchParams(window.location.search).get("c")?.split(",").map(Number);
  if (!parts || parts.length !== 3 || !parts.every(Number.isFinite)) return {};
  const [lon, lat, zoom] = parts;
  if (lon < -180 || lon > 180 || lat < -90 || lat > 90 || zoom < 0 || zoom > 22) return {};
  return { center: [lon, lat], zoom };
}

/**
 * /layers — parameters3.md map layers, one at a time: green = good areas,
 * red = bad areas. v1 ships parks (p19), transit (p15) and schools
 * (p12/p123); each new parameter is one LAYERS entry in lib/layers.ts.
 */
export default function LayersPage() {
  const [camera] = useState(initialCamera);
  const [layer, setLayer] = useState<LayerId>("parks");
  // Data follows the visible map area: zooming in refetches complete local
  // points instead of stretching the capped country-wide set. The server
  // cache (rounded-bbox keys, 24 h TTL) keeps this polite.
  const [view, setView] = useState<BBoxLike>(ESTONIA_BBOX);
  const [featurePoints, setFeaturePoints] = useState<LayerPoint[] | null>(null);
  const [raster, setRaster] = useState<WalkRasterDoc | null>(null);
  const [distance, setDistance] = useState<TransitDistance>("euclidean");
  const [provenance, setProvenance] = useState<LayerProvenance | null>(null);
  const [ageMs, setAgeMs] = useState<number | null>(null);
  const [pointCount, setPointCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const hasDataRef = useRef(false);
  const requestRef = useRef(0);
  const def = LAYERS.find((l) => l.id === layer) as LayerDef;

  useEffect(() => {
    let cancelled = false;
    // Stale-while-revalidate: keep showing the previous field while the
    // new view loads, so pans never flash an empty map. Sequenced: a slow
    // earlier response can never clobber a newer one, and server-side demo
    // points never replace real data already on screen.
    const id = ++requestRef.current;
    const fresh = () => !cancelled && id === requestRef.current;
    setLoading(true);
    setRefreshFailed(false);
    // Score window (8x raster) rides alongside the points; whichever is
    // fresh wins the render, failures fall back to the points splat.
    fetchWindow(layer, view).then((doc) => {
      if (!fresh()) return;
      setRaster(doc);
    });
    fetchLayerPoints(layer, view)
      .then((res) => {
        if (!fresh()) return;
        if (res.provenance === "demo" && hasDataRef.current) {
          setRefreshFailed(true);
        } else {
          setProvenance(res.provenance);
          setAgeMs(res.ageMs);
          setPointCount(res.points.length);
          setFeaturePoints(res.points);
          setDistance(res.distance);
          hasDataRef.current = true;
        }
        setLoading(false);
      })
      .catch(() => {
        if (!fresh()) return;
        setLoading(false);
        if (!hasDataRef.current) {
          setProvenance("demo");
          setFeaturePoints([]);
        } else {
          setRefreshFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [layer, view]);

  // A new layer starts without the previous layer's window.
  useEffect(() => {
    setRaster(null);
  }, [layer]);

  // Park boundaries (parks layer only): fetched once per selection, a
  // visual aid so scored-inside vs surroundings reads at a glance.
  const [outlines, setOutlines] = useState<ParkOutline[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (layer !== "parks") {
      setOutlines(null);
      return;
    }
    fetchParkAreas().then((areas) => {
      if (!cancelled) setOutlines(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // Density layers (walkability/pedinfra/cycling) have no snapshot
  // points: their overlay is a viewport-capped foot-graph sample that
  // refetches with the view, same cadence as the points path. Point
  // layers reuse featurePoints directly (no extra fetch).
  const [graphPoints, setGraphPoints] = useState<OverlayPoint[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!needsGraphOverlay(layer)) {
      setGraphPoints(null);
      return;
    }
    fetchGraphOverlay(layer, view).then((pts) => {
      if (!cancelled) setGraphPoints(pts);
    });
    return () => {
      cancelled = true;
    };
  }, [layer, view]);

  // Per-layer overlay toggle (all visible by default; undefined = on).
  const [overlayOn, setOverlayOn] = useState<Partial<Record<LayerId, boolean>>>({});
  const showOverlay = overlayOn[layer] !== false;
  const pointOverlay: OverlayPoint[] | null =
    layer === "parks"
      ? null
      : needsGraphOverlay(layer)
        ? graphPoints
        : selectOverlayPoints(featurePoints ?? [], layer);
  const overlayCount =
    layer === "parks" ? (outlines?.length ?? 0) : (pointOverlay?.length ?? 0);

  const base =
    provenance === null
      ? "Laadin kihi andmeid…"
      : provenance === "snapshot"
        ? pointCount > 0 || !raster
          ? `Kohalik hetktõmmis (2026-09-12) · ${pointCount} punkti`
          : "Kohalik hetktõmmis (2026-09-12) · rasterkiht"
        : provenance === "empty"
          ? "Selle piirkonna kohta hetktõmmises andmed puuduvad"
          : provenance === "live"
            ? `LIVE: Overpass serveri kaudu · ${pointCount} punkti`
            : provenance === "cache"
              ? `Vahemälust (vanus ${ageEt(ageMs)}) · ${pointCount} punkti`
              : provenance === "stale"
                ? `Aegunud vahemälu — upstream maas (vanus ${ageEt(ageMs)}) · ${pointCount} punkti`
                : `DEMO-varu (live ebaõnnestus) · ${pointCount} punkti`;
  const status =
    (loading && provenance !== null ? `${base} · uuendan…` : base) +
    (refreshFailed ? " · uuendamine ebaõnnestus" : "");

  return (
    <main>
      <p>
        <Link href="/">← Tagasi nimekirja</Link>
      </p>
      <h1>Parameetrikaardid</h1>
      <p>
        Iga kiht värvib piirkonnad: roheline = hea, punane = halb. Andmed
        pärinevad kohalikust 2026-09-12 hetktõmmisest (Harjumaa); väljaspool
        selle katvust andmeid ei kuvata.
      </p>
      <div role="group" aria-label="Parameetrikiht">
        {LAYERS.map((l) => (
          <button
            key={l.id}
            type="button"
            aria-pressed={layer === l.id}
            onClick={() => setLayer(l.id)}
          >
            {l.title} (p{l.paramIds.join(", p")})
          </button>
        ))}
      </div>
      <p aria-live="polite">{status}</p>
      <label style={{ display: "block", margin: "8px 0" }}>
        <input
          type="checkbox"
          checked={showOverlay}
          onChange={(e) => setOverlayOn((prev) => ({ ...prev, [layer]: e.target.checked }))}
        />{" "}
        Näita alusandmeid ({overlayCount})
      </label>
      <ValueHeatMap
        points={featurePoints ?? []}
        radiusKm={radiusKmFor(layer)}
        bonus={bonusSpecFor(layer)}
        raster={raster}
        outlines={outlines}
        overlayPoints={pointOverlay}
        overlayColor={overlayColorFor(layer)}
        overlayLegend={overlayLegendFor(layer)}
        showOverlay={showOverlay}
        title={def.title}
        goodLabel={def.goodLabel}
        badLabel={def.badLabel}
        initialCenter={camera.center}
        initialZoom={camera.zoom}
        sourceNote={
          `Allikas: ${def.source}` +
          (distance === "euclidean" && provenance === "snapshot"
            ? " · euclidiline varu (kõndimisvõrk puudub)"
            : "")
        }
        onViewChange={(b) => setView((prev) => (sameView(prev, b) ? prev : b))}
      />
    </main>
  );
}
