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
  layerParamTag,
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
// STATKOV-HOOK (#485): choropleth distance-suffix skip (see sourceNote).
import { isStatKovLayerId } from "../../lib/layers_statkov";
// MARUKOV-HOOK (#486): choropleth distance-suffix skip (see sourceNote).
import { isMaruKovLayerId } from "../../lib/layers_maru";
// FLOOD-HOOK (#487): floodzone paints KAUR zone polygons (polygons only,
// never a gradient) instead of points.
import {
  fetchFloodAreas,
  isPolygonOnlyLayer,
  type FloodArea,
} from "../../lib/layers_flood";
// OOKLA-HOOK (#489): tileband status line + suffix (see below).
import { OOKLA_QUARTER } from "../../lib/layers_p4_ookla";

// MAAPARCEL-HOOK (#491): maaparcel paints kataster parcel polygons
// (polygons only, never a gradient) instead of points.
import {
  fetchMaaParcelAreas,
  isPolygonOnlyMaaLayer,
  type MaaParcelArea,
} from "../../lib/layers_maaparcel";


// EELIS-HOOK (#488): eelis layers paint EELIS nature polygons (polygons
// only, never a gradient) instead of points.
import {
  eelisAreasForKind,
  eelisKindForLayer,
  fetchEelisAreas,
  isEelisPolygonOnlyLayer,
  type EelisArea,
} from "../../lib/layers_eelis";

// PLANKTPR-HOOK (#492): designated-use polygon fills (see usePolygons).
import {
  fetchPlanktprAreas,
  isPlanktprLayerId,
  planktprColorForUse,
  planktprFold,
  planktprIsTallinn,
  PLANKTPR_DECREE_STAGE,
} from "../../lib/layers_planktpr";
import type { UseFillPolygon } from "../../lib/outlines";

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
        // Points belong to exactly one layer (PLANKTPR-HOOK #492: the
        // previous layer's points reset on switch below, so accepting
        // here can never leak stale dots under a new layer's legend —
        // the old suppress-demo branch did exactly that for empty
        // layers). A demo that follows real data still raises the
        // refresh-failed flag; the status names it.
        setProvenance(res.provenance);
        setAgeMs(res.ageMs);
        setPointCount(res.points.length);
        setFeaturePoints(res.points);
        setDistance(res.distance);
        if (res.provenance === "demo" && hasDataRef.current) {
          setRefreshFailed(true);
        }
        hasDataRef.current = true;
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

  // A new layer starts without the previous layer's data: window,
  // points, provenance and counts all belong to exactly one layer, so
  // stale dots/status must never render under a new layer's legend
  // (PLANKTPR-HOOK #492 — exposed by the polygons-only layer, whose
  // empty point set otherwise inherits the previous layer's markers).
  // Same-view pans keep stale-while-revalidate (this runs on layer
  // switches only, like the raster reset before it).
  useEffect(() => {
    setRaster(null);
    setFeaturePoints(null);
    setProvenance(null);
    setAgeMs(null);
    setPointCount(0);
  }, [layer]);

  // EELIS-HOOK (#488): EELIS nature polygons (eelis layers only,
  // fetched once per selection): the choropleth itself — inside a named
  // polygon vs outside/unknown. No points and no score field are painted
  // for these layers, by design (polygons only, never a gradient).
  const [eelisAreas, setEelisAreas] = useState<EelisArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isEelisPolygonOnlyLayer(layer)) {
      setEelisAreas(null);
      return;
    }
    fetchEelisAreas().then((areas) => {
      if (!cancelled) setEelisAreas(areas);
    });
    return () => {
      cancelled = true;
    };
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

  // FLOOD-HOOK (#487): KAUR zone polygons (floodzone layer only, fetched
  // once per selection): the choropleth itself — inside a named polygon
  // vs outside/unknown. No points and no score field are painted for
  // this layer, by design (polygons only, never a gradient).
  const [floodAreas, setFloodAreas] = useState<FloodArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isPolygonOnlyLayer(layer)) {
      setFloodAreas(null);
      return;
    }
    fetchFloodAreas().then((areas) => {
      if (!cancelled) setFloodAreas(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // MAAPARCEL-HOOK (#491): kataster parcel polygons (maaparcel layer
  // only, fetched once per selection): the choropleth itself — registered
  // parcel fabric by omandivorm class vs outside/unknown. No points and
  // no score field are painted for this layer, by design (polygons only,
  // never a gradient).
  const [maaAreas, setMaaAreas] = useState<MaaParcelArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isPolygonOnlyMaaLayer(layer)) {
      setMaaAreas(null);
      return;
    }
    fetchMaaParcelAreas().then((areas) => {
      if (!cancelled) setMaaAreas(areas);

    });
    return () => {
      cancelled = true;
    };
  }, [layer]);
  // PLANKTPR-HOOK (#492): designated-use fills (planktpr layer only):
  // fetched once per selection; only scored rows draw (kehtestatud +
  // Tallinn + recognised use — unscored rows never paint, so the fills
  // and planktprScoreAt agree by construction). Empty harvest draws
  // nothing (the dated NULL).
  const [usePolygons, setUsePolygons] = useState<UseFillPolygon[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isPlanktprLayerId(layer)) {
      setUsePolygons(null);
      return;
    }
    fetchPlanktprAreas().then((areas) => {
      if (cancelled) return;
      if (!areas) {
        setUsePolygons(null);
        return;
      }
      const fills: UseFillPolygon[] = [];
      for (const a of areas) {
        if (!planktprIsTallinn(a.kov)) continue;
        if (planktprFold(a.stage) !== PLANKTPR_DECREE_STAGE) continue;
        const color = planktprColorForUse(a.use);
        if (!color) continue;
        fills.push({ rings: a.rings, color });
      }
      setUsePolygons(fills);
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
  // EELIS-HOOK (#488): this layer's polygons (the shared sidecar carries
  // all three kinds; each layer paints only its own).
  const eelisKind = eelisKindForLayer(layer);
  const eelisOverlay: EelisArea[] | null =
    eelisKind === null ? null : eelisAreasForKind(eelisAreas, eelisKind);
  const pointOverlay: OverlayPoint[] | null =
    // FLOOD-HOOK (#487): floodzone paints polygons, never point markers.
    // MAAPARCEL-HOOK (#491): maaparcel paints polygons, never point markers.
    // EELIS-HOOK (#488): eelis layers paint polygons, never point markers.
    layer === "parks" || isPolygonOnlyLayer(layer) || isPolygonOnlyMaaLayer(layer) || isEelisPolygonOnlyLayer(layer)
      ? null
      : needsGraphOverlay(layer)
        ? graphPoints
        : selectOverlayPoints(featurePoints ?? [], layer);
  // PLANKTPR-HOOK (#492): the toggle counts scored fills, not points.
  const overlayCount = isPolygonOnlyLayer(layer)
    ? (floodAreas?.length ?? 0)
    : isPolygonOnlyMaaLayer(layer)
      ? (maaAreas?.length ?? 0)
      : isEelisPolygonOnlyLayer(layer)
        ? (eelisOverlay?.length ?? 0)
        : isPlanktprLayerId(layer)
          ? (usePolygons?.length ?? 0)
    : layer === "parks"
      ? (outlines?.length ?? 0)
      : (pointOverlay?.length ?? 0);

  // P4-031-HOOK (#484): bands-layer points ride the sensor.community
  // extract, not the OSM snapshot — the status names the extract (+ its
  // age) instead of the snapshot date.
  const isBands = bonusSpecFor(layer).kind === "bands";
  // TERVISE-HOOK (#494): qbands-layer points ride the committed
  // Terviseamet extract, not the OSM snapshot — the status names the
  // extract vintage (+ its age) instead of the snapshot date.
  const isQbands = bonusSpecFor(layer).kind === "qbands";
  // FLOOD-HOOK (#487): floodzone status counts polygons, never points —
  // the layer serves zero points by design (polygons only).
  const floodStatus =
    floodAreas === null
      ? "Laadin KAUR tsoone…"
      : `KAUR üleujutusohuga alad · ${floodAreas.length} tsooni (väljaspool = teadmata, mitte kuiv)`;
  // MAAPARCEL-HOOK (#491): maaparcel status counts parcels, never
  // points — the layer serves zero points by design (polygons only). The
  // KKIS touch tally rides along (coarse puute-liide, never deed depth).
  const maaTouched = maaAreas?.filter((p) => (p.kkis ?? 0) > 0).length ?? 0;
  const maaStatus =
    maaAreas === null
      ? "Laadin katastritunnuseid…"
      : `Maa-amet kataster · ${maaAreas.length} tunnust proovialas (${maaTouched} KKIS-puudega; väljaspool = teadmata, mitte tühi)`;
  // OOKLA-HOOK (#489): tileband-layer points ride the Ookla Tallinn
  // extract, not the OSM snapshot — the status names the extract (+
  // its quarter) instead of the snapshot date.
  const isTileband = bonusSpecFor(layer).kind === "tileband";
  // EELIS-HOOK (#488): eelis status counts polygons, never points — the
  // layers serve zero points by design (polygons only).
  const eelisStatus =
    eelisAreas === null || eelisKind === null
      ? "Laadin EELIS tsoone…"
      : `EELIS ${eelisKind === "kaitse" ? "kaitsealad" : eelisKind === "niit" ? "niiduelupaigad" : "raiealad"} · ${eelisOverlay?.length ?? 0} polügooni (väljaspool = teadmata, mitte puhas)`;
  const base =
    isPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
      ? floodStatus
      : isPolygonOnlyMaaLayer(layer) && provenance !== null && provenance !== "demo"
        ? maaStatus
      : isEelisPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? eelisStatus
      : provenance === null
      ? "Laadin kihi andmeid…"
      : provenance === "snapshot"
        ? pointCount > 0 || !raster
          ? isTileband
            ? `Ookla Tallinna väljavõte (${OOKLA_QUARTER}) · ${pointCount} ruutu`
            : isBands
              ? `sensor.community väljavõte${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
              : isQbands
                ? `Terviseameti väljavõte (suplusvesi, seis 2026-09-14)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
              : `Kohalik hetktõmmis (2026-09-12) · ${pointCount} punkti`
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
  // PLANKTPR-HOOK (#492): the DEMO base already names the failed
  // refresh, so the suffix would repeat it — it rides only on real
  // (non-demo) provenances.
  const status =
    (loading && provenance !== null ? `${base} · uuendan…` : base) +
    (refreshFailed && provenance !== "demo" ? " · uuendamine ebaõnnestus" : "");

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
            {l.title}
            {/* OSMDAILY-HOOK (#482) + P4-031-HOOK (#484): P4 layers carry
                an empty paramIds (parameters4 namespace — see
                layers_osmdaily.ts); layerParamTag returns "" for them
                (and "(P4-031)" for paramLabel slices like senscom), so
                skip the trailing space when the tag is empty instead of
                rendering "(p)" on all six osmdaily buttons. */}
            {/* STATKOV-HOOK (#485): P4 layers carry an empty paramIds
                (parameters4 namespace -- see layers_statkov.ts), so
                layerParamTag returns "" for them too -- no suffix. */}
            {layerParamTag(l) === "" ? "" : ` ${layerParamTag(l)}`}
            {/* P4OSM-HOOK (#480): blockwalk + darkness carry empty
                paramIds too -- the generic empty-tag skip covers them. */}
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
        floodAreas={floodAreas}

        maaParcels={maaAreas}


        eelisAreas={eelisOverlay}
        overlayPoints={pointOverlay}
        usePolygons={usePolygons}
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
          // STATKOV-HOOK (#485): choropleth fields are exact KOV fills,
          // not distances -- skip the otsekaugus/varu suffix for them.
          // MARUKOV-HOOK (#486): same skip for the MARU KOV fills.
          // FLOOD-HOOK (#487): floodzone paints no field at all (zero
          // points, null raster) -- "varu" would claim a fallback splat
          // exists. Skip the suffix for polygon-only layers too.
          // MAAPARCEL-HOOK (#491): maaparcel paints no field at all (zero
          // points, null raster) -- same skip for the kataster fills.
          // EELIS-HOOK (#488): eelis layers paint no field at all (zero
          // points, null raster) -- same skip for the nature fills.
          // PLANKTPR-HOOK (#492): use-fills are exact parcel joins too.
          (isStatKovLayerId(layer) || isEelisPolygonOnlyLayer(layer) ||
            isMaruKovLayerId(layer) ||
            isPolygonOnlyLayer(layer) ||
            isPolygonOnlyMaaLayer(layer) ||
            isPlanktprLayerId(layer)
            ? ""
            : distance === "euclidean" && provenance === "snapshot"
              ? raster
                // B10C-HOOK (#230): Euclidean-BUILT masters (mobile + the
                // GENV/G03-style proxy fields) are direct distance, not a
                // fallback — "varu" would claim the foot graph was missing.
                ? " · otsekaugus (sirge joon, mitte kõndimisaeg)"
                // P4-031-HOOK (#484): the senscom band kernel counts in a
                // hard Euclidean radius by design (DIY witnesses, no walk
                // graph involved) — "varu" would claim a walk version exists.
                // OOKLA-HOOK (#489): the tileband kernel joins the nearest
                // tile in a hard Euclidean radius by design (quarterly
                // tile centroids, no walk graph involved).
                : isTileband
                  ? " · lähiruut kõvas raadiuses (Ookla kvartaliruudud, mitte kõnnivõrk)"
                  : bonusSpecFor(layer).kind === "bands"
                    ? " · otsekaugus kõvas raadiuses (DIY-tunnistajad, mitte kõnnivõrk)"
                    : bonusSpecFor(layer).kind === "qbands"
                      ? " · otsekaugus kõvas raadiuses (lähim seirepunkt, mitte kõnnivõrk)"
                    : " · euclidiline varu (kõndimisvõrk puudub)"
              : "")
        }
        onViewChange={(b) => setView((prev) => (sameView(prev, b) ? prev : b))}
      />
    </main>
  );
}
