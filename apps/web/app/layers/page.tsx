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
// PAASTE-HOOK (#493): bands status label is senscom-only (see base
// below) — paaste rides the generic snapshot branch. Honest-empty
// fetch handling (see effect below) needs the paaste guard.
import { isSenscomLayerId } from "../../lib/layers_p4_senscom";
import { isPaasteLayerId } from "../../lib/layers_paaste";
// EHIS-HOOK (#608): dbands status names the EHIS extract for ehis
// layers (see isDbands branch below) — sport keeps its own label.
import { isEhisLayerId } from "../../lib/layers_p4_ehis";
// MEDRE-HOOK (#609): dbands status names the medre extract for medre
// layers (see isDbands branch below) — Step-1 honest-empty included.
import { isMedreLayerId } from "../../lib/layers_p4_medre";
// OHUSEIRE-HOOK (#610): dbands status names the station inventory
// for the ohuseire layer (see isDbands branch below).
import { isOhuseireLayerId } from "../../lib/layers_p4_ohuseire";
// KLIIMA-HOOK (#611): qbands status names the Keskkonnaagentuur
// extract for kliima layers (see isQbands branch below) — tervise
// keeps its own label.
import { isKliimaLayerId } from "../../lib/layers_kliima";
// POI-HOOK (#612): dbands status names the register extract for poi
// layers (see isDbands branch below).
import { isPoiLayerId } from "../../lib/layers_p4_poi";
// SEVESO-HOOK (#613): seveso paints Päästeamet danger polygons
// (polygons only, never a gradient) instead of points.
import {
  fetchSevesoAreas,
  isSevesoPolygonOnlyLayer,
  type SevesoArea,
} from "../../lib/layers_p4_seveso";
// STATELAND-HOOK (#615): stateland paints KATRI state + auction
// polygons (polygons only, never a gradient) instead of points.
import {
  fetchStatelandAreas,
  isStatelandPolygonOnlyLayer,
  type StatelandArea,
} from "../../lib/layers_p4_stateland";
// QUARRY-HOOK (#614): quarry paints Maa-amet permit/watch polygons
// (polygons only, never a gradient) instead of points.
import {
  fetchQuarryAreas,
  isQuarryPolygonOnlyLayer,
  type QuarryArea,
} from "../../lib/layers_p4_quarry";
// DRAINAGE-HOOK (#616): drainage paints maaparandus network/invalid
// fills + outflow centerlines (polygons only, never a gradient)
// instead of points.
import {
  fetchMaaparandusAreas,
  isMaaparandusPolygonOnlyLayer,
  type MaaparandusArea,
} from "../../lib/layers_p4_maaparandus";
// SOIL-HOOK (#617): soil paints Maa-amet soil contours (polygons only,
// viewport-driven, never a gradient) instead of points.
import {
  fetchSoilAreas,
  isSoilPolygonOnlyLayer,
  type SoilArea,
} from "../../lib/layers_p4_soil";
// ETAK-HOOK (#618): etak paints ETAK wetland/water/yard contours
// (polygons only, never a gradient) instead of points — viewport-driven
// (the WFS harvest is 114 MB, so the page refetches per settled view).
import {
  fetchEtakAreas,
  isEtakPolygonOnlyLayer,
  type EtakArea,
} from "../../lib/layers_p4_etak";
// RELIEF-HOOK (#619): relief paints the DTM hypsometric character tint
// (taste-only, never a gradient/score) instead of points — fetched once
// per selection (the county grid covers every view).
import {
  fetchReliefTint,
  isReliefTasteOnlyLayer,
  type ReliefTintGrid,
} from "../../lib/layers_p4_relief";
// CANOPY-HOOK (#620): canopy paints the CHM class character tint
// (taste-only, never a gradient/score) instead of points — fetched once
// per selection (the county grid covers every view).
import {
  fetchCanopyTint,
  isCanopyTasteOnlyLayer,
  type CanopyTintGrid,
} from "../../lib/layers_p4_canopy";
// BUILDINGS-HOOK (#621): buildings paints the LoD1 height character
// tint (taste-only, never a gradient/score) instead of points —
// fetched once per selection (the county grid covers every view).
import {
  fetchBuildingsTint,
  isBuildingsTasteOnlyLayer,
  type BuildingsTintGrid,
} from "../../lib/layers_p4_buildings";
// DENSITY-HOOK (#622): density paints INSPIRE PD 1 km squares
// (taste-only, never a gradient/score) instead of points — fetched
// once per selection (the county squares cover every view).
import {
  fetchDensityAreas,
  isDensityTasteOnlyLayer,
  type DensityArea,
} from "../../lib/layers_p4_density";
// FOREST-HOOK (#624): forest paints metsamuutused detected-change
// polygons (scored warning bands, never "safe forest") instead of
// points — fetched once per selection (the county keep set covers
// every view).
import {
  fetchForestAreas,
  isForestPolygonOnlyLayer,
  type ForestArea,
} from "../../lib/layers_p4_forest";
// NOISE-HOOK (#625): noise paints myrakaart Lden/Lnight band fills
// (modelled, never measured) instead of points — fetched once per
// selection (the county keep set covers every view).
import {
  fetchNoiseAreas,
  isNoisePolygonOnlyLayer,
  type NoiseArea,
} from "../../lib/layers_p4_noise";

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
        // PAASTE-HOOK (#493): paaste is honest-empty — its fetch NEVER
        // succeeds (no sidecar by dated-negative verdict), so the
        // generic stale-while-revalidate above would keep the PREVIOUS
        // layer's points under the paaste bands kernel and paint
        // fabricated "komando coverage". Demo-empty (zero markers +
        // "DEMO-varu · 0 punkti") IS the honest state: take it even
        // when older layers already put data on screen.
        if (isPaasteLayerId(layer)) {
          setProvenance("demo");
          setAgeMs(null);
          setPointCount(0);
          setFeaturePoints([]);
          setDistance("euclidean");
          hasDataRef.current = true;
          setLoading(false);
          return;
        }
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
        // PAASTE-HOOK (#493): same honest-empty state on transport
        // error (see above) — never another layer's stale points,
        // never demo markers (fallbackPoints is [] by honesty).
        if (isPaasteLayerId(layer)) {
          setProvenance("demo");
          setAgeMs(null);
          setPointCount(0);
          setFeaturePoints([]);
          setDistance("euclidean");
          hasDataRef.current = true;
          return;
        }
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

  // SEVESO-HOOK (#613): Päästeamet danger polygons (seveso layer
  // only, fetched once per selection): the choropleth itself — inside
  // a named danger polygon vs outside/unknown. No points and no score
  // field are painted for this layer, by design (polygons only, never
  // a gradient).
  const [sevesoAreas, setSevesoAreas] = useState<SevesoArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isSevesoPolygonOnlyLayer(layer)) {
      setSevesoAreas(null);
      return;
    }
    fetchSevesoAreas().then((areas) => {
      if (!cancelled) setSevesoAreas(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // STATELAND-HOOK (#615): KATRI state + auction polygons (stateland
  // layer only, fetched once per selection): the choropleth itself —
  // inside a named state/auction parcel vs outside/unknown. No points
  // and no score field are painted for this layer, by design (polygons
  // only, never a gradient).
  const [statelandAreas, setStatelandAreas] = useState<StatelandArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isStatelandPolygonOnlyLayer(layer)) {
      setStatelandAreas(null);
      return;
    }
    fetchStatelandAreas().then((areas) => {
      if (!cancelled) setStatelandAreas(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // QUARRY-HOOK (#614): Maa-amet permit/watch polygons (quarry
  // layer only, fetched once per selection): the choropleth itself —
  // inside a named permit polygon vs outside/unknown. No points and no
  // score field are painted for this layer, by design (polygons only,
  // never a gradient).
  const [quarryAreas, setQuarryAreas] = useState<QuarryArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isQuarryPolygonOnlyLayer(layer)) {
      setQuarryAreas(null);
      return;
    }
    fetchQuarryAreas().then((areas) => {
      if (!cancelled) setQuarryAreas(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // SOIL-HOOK (#617): soil contours (soil layer only, refetched per
  // settled viewport): the choropleth itself — inside a named contour
  // vs outside/unknown. No points and no score field are painted for
  // this layer, by design (polygons only, never a gradient). The view
  // bbox is settled upstream (sameView), so pans refetch politely.
  const [soilAreas, setSoilAreas] = useState<SoilArea[] | null>(null);
  const [soilNote, setSoilNote] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isSoilPolygonOnlyLayer(layer)) {
      setSoilAreas(null);
      setSoilNote(null);
      return;
    }
    fetchSoilAreas(view).then((res) => {
      if (cancelled) return;
      setSoilAreas(res ? res.areas : null);
      setSoilNote(res ? res.note : null);
    });
    return () => {
      cancelled = true;
    };
  }, [layer, view]);

  // DRAINAGE-HOOK (#616): maaparandus network/invalid/outflow shapes
  // (drainage layer only, fetched once per selection): the choropleth
  // itself — inside a named network area vs outside/unknown. No points
  // and no score field are painted for this layer, by design (polygons
  // only, never a gradient).
  const [maaparandusAreas, setMaaparandusAreas] = useState<MaaparandusArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isMaaparandusPolygonOnlyLayer(layer)) {
      setMaaparandusAreas(null);
      return;
    }
    fetchMaaparandusAreas().then((areas) => {
      if (!cancelled) setMaaparandusAreas(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // ETAK-HOOK (#618): ETAK wetland/water/yard contours (etak layer
  // only, refetched per settled view): the choropleth itself — inside a
  // named contour vs outside/unknown. No points and no score field are
  // painted for this layer, by design (polygons only, never a
  // gradient). Viewport-driven (not once-per-selection like the other
  // polygon layers): the WFS harvest is 114 MB, so the server answers
  // per-bbox and the page refetches on pan/zoom like the points path.
  const [etakAreas, setEtakAreas] = useState<EtakArea[] | null>(null);
  const [etakNote, setEtakNote] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isEtakPolygonOnlyLayer(layer)) {
      setEtakAreas(null);
      setEtakNote(null);
      return;
    }
    fetchEtakAreas(view).then((res) => {
      if (cancelled) return;
      setEtakAreas(res ? res.areas : null);
      setEtakNote(res ? res.note : null);
    });
    return () => {
      cancelled = true;
    };
  }, [layer, view]);

  // RELIEF-HOOK (#619): DTM hypsometric tint grid (relief layer only,
  // fetched once per selection): the character tint itself — ground
  // character vs honestly-unknown (missing sidecar). No points and no
  // score field are painted for this layer, by design (taste-only,
  // never a gradient/score).
  const [reliefTint, setReliefTint] = useState<ReliefTintGrid | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isReliefTasteOnlyLayer(layer)) {
      setReliefTint(null);
      return;
    }
    fetchReliefTint().then((grid) => {
      if (!cancelled) setReliefTint(grid);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // CANOPY-HOOK (#620): CHM class tint grid (canopy layer only,
  // fetched once per selection): the character tint itself — tree
  // character vs honestly-unknown (missing sidecar). No points and no
  // score field are painted for this layer, by design (taste-only,
  // never a gradient/score).
  const [canopyTint, setCanopyTint] = useState<CanopyTintGrid | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isCanopyTasteOnlyLayer(layer)) {
      setCanopyTint(null);
      return;
    }
    fetchCanopyTint().then((grid) => {
      if (!cancelled) setCanopyTint(grid);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // BUILDINGS-HOOK (#621): LoD1 height tint grid (buildings layer
  // only, fetched once per selection): the character tint itself —
  // built character vs honestly-unknown (missing sidecar). No points
  // and no score field are painted for this layer, by design
  // (taste-only, never a gradient/score).
  const [buildingsTint, setBuildingsTint] = useState<BuildingsTintGrid | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isBuildingsTasteOnlyLayer(layer)) {
      setBuildingsTint(null);
      return;
    }
    fetchBuildingsTint().then((grid) => {
      if (!cancelled) setBuildingsTint(grid);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // DENSITY-HOOK (#622): INSPIRE PD 1 km squares (density layer only,
  // fetched once per selection): the choropleth itself — settled
  // character vs honestly-unknown (missing sidecar). No points and no
  // score field are painted for this layer, by design (taste-only,
  // never a gradient/score).
  const [densityAreas, setDensityAreas] = useState<DensityArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isDensityTasteOnlyLayer(layer)) {
      setDensityAreas(null);
      return;
    }
    fetchDensityAreas().then((areas) => {
      if (!cancelled) setDensityAreas(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // FOREST-HOOK (#624): metsamuutused detected-change polygons
  // (forest layer only, fetched once per selection): the warning
  // itself — 2024 detected change vs honestly-unknown
  // (missing sidecar). No points are painted for this layer, by
  // design (polygons only); the per-listing distance bands are the
  // scorer's job.
  const [forestAreas, setForestAreas] = useState<ForestArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isForestPolygonOnlyLayer(layer)) {
      setForestAreas(null);
      return;
    }
    fetchForestAreas().then((areas) => {
      if (!cancelled) setForestAreas(areas);
    });
    return () => {
      cancelled = true;
    };
  }, [layer]);

  // NOISE-HOOK (#625): myrakaart Lden/Lnight band polygons
  // (noise layer only, fetched once per selection): the bands
  // themselves — modelled loud vs quiet vs honestly-unknown
  // (missing sidecar). No points are painted for this layer, by
  // design (polygons only); the per-listing binding leg is the
  // scorer's job.
  const [noiseAreas, setNoiseAreas] = useState<NoiseArea[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (!isNoisePolygonOnlyLayer(layer)) {
      setNoiseAreas(null);
      return;
    }
    fetchNoiseAreas().then((areas) => {
      if (!cancelled) setNoiseAreas(areas);
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
    // SEVESO-HOOK (#613): seveso paints polygons, never point markers.
    // QUARRY-HOOK (#614): quarry paints polygons, never point markers.
    // SOIL-HOOK (#617): soil paints polygons, never point markers.
    // ETAK-HOOK (#618): etak paints polygons, never point markers.
    layer === "parks" || isPolygonOnlyLayer(layer) || isPolygonOnlyMaaLayer(layer) || isEelisPolygonOnlyLayer(layer) || isSevesoPolygonOnlyLayer(layer) || isStatelandPolygonOnlyLayer(layer) || isQuarryPolygonOnlyLayer(layer) || isMaaparandusPolygonOnlyLayer(layer) || isSoilPolygonOnlyLayer(layer) || isEtakPolygonOnlyLayer(layer) || isReliefTasteOnlyLayer(layer) || isCanopyTasteOnlyLayer(layer) || isBuildingsTasteOnlyLayer(layer) || isDensityTasteOnlyLayer(layer) || isForestPolygonOnlyLayer(layer) || isNoisePolygonOnlyLayer(layer)
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
        : isSevesoPolygonOnlyLayer(layer)
          ? (sevesoAreas?.length ?? 0)
        : isStatelandPolygonOnlyLayer(layer)
          ? (statelandAreas?.length ?? 0)
        : isQuarryPolygonOnlyLayer(layer)
          ? (quarryAreas?.length ?? 0)
        : isMaaparandusPolygonOnlyLayer(layer)
          ? (maaparandusAreas?.length ?? 0)
        : isSoilPolygonOnlyLayer(layer)
          ? (soilAreas?.length ?? 0)
        : isEtakPolygonOnlyLayer(layer)
          ? (etakAreas?.length ?? 0)
        : isReliefTasteOnlyLayer(layer)
          ? (reliefTint ? 1 : 0)
        : isCanopyTasteOnlyLayer(layer)
          ? (canopyTint ? 1 : 0)
        : isBuildingsTasteOnlyLayer(layer)
          ? (buildingsTint ? 1 : 0)
        : isDensityTasteOnlyLayer(layer)
          ? (densityAreas?.length ?? 0)
        : isForestPolygonOnlyLayer(layer)
          ? (forestAreas?.length ?? 0)
        : isNoisePolygonOnlyLayer(layer)
          ? (noiseAreas?.length ?? 0)
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
  // SPORT-HOOK (#607): dbands-layer points ride the Spordiregister +
  // ujulad sidecar, not the OSM snapshot — the status names the
  // register harvest vintage (+ its age) instead of the snapshot date.
  const isDbands = bonusSpecFor(layer).kind === "dbands";
  // FIXIT-HOOK (#623): pins-layer markers ride the annateada sidecar,
  // not the OSM snapshot — the status names the pull vintage (+ its
  // age) plus the rolling window instead of the snapshot date.
  const isPins = bonusSpecFor(layer).kind === "pins";
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
  // SEVESO-HOOK (#613): seveso status counts danger polygons, never
  // points — the layer serves zero points by design (polygons only).
  const sevesoStatus =
    sevesoAreas === null
      ? "Laadin Seveso ohualasid…"
      : `Päästeameti Seveso ohualad · ${sevesoAreas.length} polügooni (väljaspool = teadmata, mitte ohutu)`;
  // STATELAND-HOOK (#615): stateland status counts state/auction
  // parcels, never points — the layer serves zero points by design
  // (polygons only).
  const statelandStatus =
    statelandAreas === null
      ? "Laadin riigimaid…"
      : `KATRI riigimaa + oksjonid · ${statelandAreas.length} parselli (väljaspool = teadmata, mitte riigimaavaba)`;
  // QUARRY-HOOK (#614): quarry status counts permit/watch polygons,
  // never points — the layer serves zero points by design (polygons
  // only).
  const quarryStatus =
    quarryAreas === null
      ? "Laadin karjääripiirkondi…"
      : `Maa-ameti karjäärid ja uuringualad · ${quarryAreas.length} polügooni (väljaspool = teadmata, mitte kaevandusvaba)`;
  // DRAINAGE-HOOK (#616): drainage status counts network/invalid
  // shapes + outflow lines, never points — the layer serves zero
  // points by design (polygons only).
  const maaparandusStatus =
    maaparandusAreas === null
      ? "Laadin kuivendusvõrku…"
      : `Maaparandusvõrk + eesvoolud · ${maaparandusAreas.length} kujundit (väljaspool = teadmata, mitte kuiv)`;
  // SOIL-HOOK (#617): soil status counts viewport contours, never
  // points — the layer serves zero points by design (polygons only,
  // viewport-driven).
  const soilStatus =
    soilAreas === null
      ? "Laadin mullakontuure…"
      : soilNote !== null
        ? `Mullastikukaart · ${soilNote}`
        : `Mullastikukaart · ${soilAreas.length} kontuuri vaates (väljaspool = teadmata, mitte hea pinnas; linn/vesi/määramata EI MAALI)`;
  // ETAK-HOOK (#618): etak status counts viewport contours (+ the
  // server honesty note: too-wide zoom guidance or WFS outage), never
  // points — the layer serves zero points by design (polygons only).
  const etakStatus =
    etakAreas === null
      ? "Laadin ETAK kontuure…"
      : `ETAK märgala/vesi/õu · ${etakAreas.length} kontuuri vaates (väljaspool = teadmata, mitte kuiv maa)${etakNote ? ` · ${etakNote}` : ""}`;
  // RELIEF-HOOK (#619): relief status names the tint grid, never
  // points — the layer serves zero points by design (taste-only, no
  // score field anywhere).
  const reliefStatus =
    reliefTint === null
      ? "Laadin reljeefitooni…"
      : `Reljeefi toon · ${reliefTint.cols}×${reliefTint.rows} maastikuruudustik (maitse, mitte hinne — toon ERISTAB, ei hinda)`;
  // CANOPY-HOOK (#620): canopy status names the tint grid, never
  // points — the layer serves zero points by design (taste-only, no
  // score field anywhere).
  const canopyStatus =
    canopyTint === null
      ? "Laadin võrastikutooni…"
      : `Võrastiku toon · ${canopyTint.cols}×${canopyTint.rows} klassiruudustik (maitse, mitte hinne — toon ERISTAB, ei hinda)`;
  // BUILDINGS-HOOK (#621): buildings status names the tint grid, never
  // points — the layer serves zero points by design (taste-only, no
  // score field anywhere).
  const buildingsStatus =
    buildingsTint === null
      ? "Laadin hoonetooni…"
      : `Hoonete toon · ${buildingsTint.cols}×${buildingsTint.rows} kõrgusruudustik (maitse, mitte hinne — toon ERISTAB, ei hinda)`;
  // DENSITY-HOOK (#622): density status counts squares, never points
  // — the layer serves zero points by design (taste-only, no score
  // field anywhere).
  const densityStatus =
    densityAreas === null
      ? "Laadin asustusruute…"
      : `Asustuse toon · ${densityAreas.length} ruutu 1x1 km, 2024 (maitse, mitte hinne — toon ERISTAB, ei hinda)`;
  // FOREST-HOOK (#624): forest status counts changes, never points —
  // the layer serves zero points by design (polygons only); outside
  // every polygon is NULL, never safe forest.
  const forestStatus =
    forestAreas === null
      ? "Laadin võramuutisi…"
      : `Tuvastatud võramuutis · ${forestAreas.length} polügooni, 2024 lend (väljaspool = teadmata, MITTE turvaline mets)`;
  // NOISE-HOOK (#625): noise status counts bands, never points —
  // the layer serves zero points by design (polygons only); outside
  // every polygon is NULL, never quiet.
  const noiseStatus =
    noiseAreas === null
      ? "Laadin müravööndeid…"
      : `Strateegiline müra · ${noiseAreas.length} vööndit, 2022 mudel (väljaspool = teadmata, MITTE vaikne)`;
  const base =
    isPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
      ? floodStatus
      : isPolygonOnlyMaaLayer(layer) && provenance !== null && provenance !== "demo"
        ? maaStatus
      : isEelisPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? eelisStatus
      : isSevesoPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? sevesoStatus
      : isStatelandPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? statelandStatus      : isStatelandPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? statelandStatus
      : isQuarryPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? quarryStatus
      : isMaaparandusPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? maaparandusStatus
      : isSoilPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? soilStatus
      : isEtakPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? etakStatus
      : isReliefTasteOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? reliefStatus
      : isCanopyTasteOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? canopyStatus
      : isBuildingsTasteOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? buildingsStatus
      : isDensityTasteOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? densityStatus
      : isForestPolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? forestStatus
      : isNoisePolygonOnlyLayer(layer) && provenance !== null && provenance !== "demo"
        ? noiseStatus
      : provenance === null
      ? "Laadin kihi andmeid…"
      : provenance === "snapshot"
        ? pointCount > 0 || !raster
          ? isTileband
            ? `Ookla Tallinna väljavõte (${OOKLA_QUARTER}) · ${pointCount} ruutu`
            // PAASTE-HOOK (#493): the extract label is senscom-only.
            // isBands alone would mislabel paaste (the other bands layer)
            // as "sensor.community väljavõte" — paaste rides the generic
            // snapshot branch (its own fetch never succeeds: no sidecar,
            // no raster — the designed 500 → demo-empty path).
            : isBands && isSenscomLayerId(layer)
              ? `sensor.community väljavõte${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
              : isQbands
                ? isKliimaLayerId(layer)
                  ? `Keskkonnaagentuuri väljavõte (kliimanormatiiv 1991-2020, seis 2026-09-16)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
                  : `Terviseameti väljavõte (suplusvesi, seis 2026-09-14)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
              : isDbands
                ? isEhisLayerId(layer)
                  ? `EHISe väljavõte (koolihooned, seis 2026-09-16)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
                  : isMedreLayerId(layer)
                    ? `Medre väljavõte (perearstid, seis 2026-09-16)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
                    : isOhuseireLayerId(layer)
                      ? `Õhuseire väljavõte (3 jaama, seis 2026-09-16)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
                      : isPoiLayerId(layer)
                        ? `Huvipunktide väljavõte (register, seis 2026-09-16)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
                        : `Spordiregistri + ujulate väljavõte (seis 2026-09-16)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} punkti`
              : isPins
                ? `annateada väljavõte (libisev 19 päeva aken, seis 2026-09-17)${ageMs !== null ? ` (vanus ${ageEt(ageMs)})` : ""} · ${pointCount} teadet`
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
        sevesoAreas={sevesoAreas}
        statelandAreas={statelandAreas}
        quarryAreas={quarryAreas}
        maaparandusAreas={maaparandusAreas}
        soilAreas={soilAreas}
        etakAreas={etakAreas}
        reliefTint={reliefTint}
        canopyTint={canopyTint}
        buildingsTint={buildingsTint}
        densityAreas={densityAreas}
        forestAreas={forestAreas}
        noiseAreas={noiseAreas}
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
          // SEVESO-HOOK (#613): seveso paints no field at all (zero
          // points, null raster) -- same skip for the danger fills.
          // QUARRY-HOOK (#614): quarry paints no field at all (zero
          // points, null raster) -- same skip for the permit fills.
          (isStatKovLayerId(layer) || isEelisPolygonOnlyLayer(layer) ||
            isMaruKovLayerId(layer) ||
            isPolygonOnlyLayer(layer) ||
            isPolygonOnlyMaaLayer(layer) ||
            isSevesoPolygonOnlyLayer(layer) ||
            // STATELAND-HOOK (#615): stateland paints no field at all
            // (zero points, null raster) -- same skip for state fills.
            isStatelandPolygonOnlyLayer(layer) ||
            isQuarryPolygonOnlyLayer(layer) ||
            // DRAINAGE-HOOK (#616): drainage paints no field at all
            // (zero points, null raster) -- same skip for network fills.
            isMaaparandusPolygonOnlyLayer(layer) ||
            // SOIL-HOOK (#617): soil paints no field at all (zero
            // points, null raster) -- same skip for the contour fills.
            isSoilPolygonOnlyLayer(layer) ||
            // ETAK-HOOK (#618): etak paints no field at all (zero
            // points, null raster) -- same skip for contour fills.
            isEtakPolygonOnlyLayer(layer) ||
            // RELIEF-HOOK (#619): relief paints no field at all (zero
            // points, null raster) -- same skip for the taste tint.
            isReliefTasteOnlyLayer(layer) ||
            // CANOPY-HOOK (#620): canopy paints no field at all (zero
            // points, null raster) -- same skip for the taste tint.
            isCanopyTasteOnlyLayer(layer) ||
            // BUILDINGS-HOOK (#621): buildings paints no field at all
            // (zero points, null raster) -- same skip for the taste
            // tint.
            isBuildingsTasteOnlyLayer(layer) ||
            // DENSITY-HOOK (#622): density paints no field at all
            // (zero points, null raster) -- same skip for the square
            // fills.
            isDensityTasteOnlyLayer(layer) ||
            // FOREST-HOOK (#624): forest paints no field at all
            // (zero points, null raster) -- same skip for the change
            // fills.
            isForestPolygonOnlyLayer(layer) ||
            // NOISE-HOOK (#625): noise paints no field at all
            // (zero points, null raster) -- same skip for the band
            // fills.
            isNoisePolygonOnlyLayer(layer) ||
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
                    : bonusSpecFor(layer).kind === "pins"
                      ? " · teated, mitte hinnang (kaebuste tihedus, mitte elukvaliteet)"
                    : " · euclidiline varu (kõndimisvõrk puudub)"
              : "")
        }
        onViewChange={(b) => setView((prev) => (sameView(prev, b) ? prev : b))}
      />
    </main>
  );
}
