import { NextResponse } from "next/server";
import { LAYERS, tileForView, type BBoxLike, type LayerPoint } from "../../../../lib/layers";
import { isSenscomLayerId } from "../../../../lib/layers_p4_senscom";
// TERVISE-HOOK (#494): committed bathing-water points (see below).
import {
  TERVISE_POINTS,
  TERVISE_VINTAGE,
  isTerviseLayerId,
  tervisePointsIn,
} from "../../../../lib/layers_tervise";
// FLOOD-HOOK (#487): polygons-only branch guard (see below).
import { isFloodLayerId } from "../../../../lib/layers_flood";
// VIIRS-HOOK (#719): committed brightness cells (see below).
import {
  VIIRS_CELLS,
  VIIRS_VINTAGE,
  isViirsLayerId,
  viirsPointsIn,
} from "../../../../lib/layers_p4_viirs";
// OOKLA-HOOK (#489): ookla tile points come from the Ookla Tallinn
// extract (never the OSM snapshot, never live).
import { isOoklaLayerId } from "../../../../lib/layers_p4_ookla";
// ACCBLACK-HOOK (#490): accblack serves honestly-empty (never 500/demo).
import { isAccBlackLayerId } from "../../../../lib/layers_accblack";
// ASUMEDIA-HOOK (#495): asumedia serves honestly-empty (never 500/demo).
import { isAsumediaLayerId } from "../../../../lib/layers_asumedia";
// MAAPARCEL-HOOK (#491): polygons-only branch guard (see below).
import { isMaaParcelLayerId } from "../../../../lib/layers_maaparcel";

// EELIS-HOOK (#488): polygons-only branch guard (see below).
import { isEelisLayerId } from "../../../../lib/layers_eelis";
// SEVESO-HOOK (#613): polygons-only branch guard (see below).
import { isSevesoLayerId } from "../../../../lib/layers_p4_seveso";
// DELAY-HOOK (#629): polygons-only branch guard (see below).
import { isDelayLayerId } from "../../../../lib/layers_p4_delay";
// STATELAND-HOOK (#615): polygons-only branch guard (see below).
import { isStatelandLayerId } from "../../../../lib/layers_p4_stateland";
// QUARRY-HOOK (#614): polygons-only branch guard (see below).
import { isQuarryLayerId } from "../../../../lib/layers_p4_quarry";
// DRAINAGE-HOOK (#616): polygons-only branch guard (see below).
import { isMaaparandusLayerId } from "../../../../lib/layers_p4_maaparandus";
// SOIL-HOOK (#617): polygons-only branch guard (see below).
import { isSoilLayerId } from "../../../../lib/layers_p4_soil";
// ETAK-HOOK (#618): polygons-only branch guard (see below).
import { isEtakLayerId } from "../../../../lib/layers_p4_etak";
// RELIEF-HOOK (#619): taste-only branch guard (see below).
import { isReliefLayerId } from "../../../../lib/layers_p4_relief";
// CANOPY-HOOK (#620): taste-only branch guard (see below).
import { isCanopyLayerId } from "../../../../lib/layers_p4_canopy";
// BUILDINGS-HOOK (#621): taste-only branch guard (see below).
import { isBuildingsLayerId } from "../../../../lib/layers_p4_buildings";
// DENSITY-HOOK (#622): taste-only branch guard (see below).
import { isDensityLayerId } from "../../../../lib/layers_p4_density";
// FOREST-HOOK (#624): polygons-only branch guard (see below).
import { isForestLayerId } from "../../../../lib/layers_p4_forest";
// NOISE-HOOK (#625): polygons-only branch guard (see below).
import { isNoiseLayerId } from "../../../../lib/layers_p4_noise";
import { isKpoLayerId } from "../../../../lib/layers_p4_kpo";
// HARBOUR-HOOK (#627): port points branch (see below) + vintage.
import {
  HARBOUR_VINTAGE,
  harbourPointsIn,
  isHarbourLayerId,
} from "../../../../lib/layers_p4_harbour";

import {
  intersectsCoverage,
  loadAccblackPoints,
  loadEhisPoints,
  loadLayerRaster,
  loadFixitPoints,
  loadHarbourAreas,
  loadMedrePoints,
  loadOhuseirePoints,
  loadPoiPoints,
  loadSnapshotPoints,
  loadSportPoints,
  SNAPSHOT_AS_OF_MS,
  snapshotDir,
  SnapshotUnavailable,
} from "../../../../lib/server/snapshot";
import {
  isSportLayerId,
  SPORT_VINTAGE,
  sportPointsIn,
  sportSliceFor,
} from "../../../../lib/layers_p4_sport";
// EHIS-HOOK (#608): measured-school sidecar points (see below).
import {
  EHIS_VINTAGE,
  ehisPointsIn,
  ehisSliceFor,
  isEhisLayerId,
} from "../../../../lib/layers_p4_ehis";
// MEDRE-HOOK (#609): primary-care sidecar points (see below).
import {
  isMedreLayerId,
  MEDRE_VINTAGE,
  medrePointsIn,
  medreSliceFor,
} from "../../../../lib/layers_p4_medre";
// OHUSEIRE-HOOK (#610): official air-station sidecar points (see below).
import {
  isOhuseireLayerId,
  ohuseirePointsIn,
  OHUSEIRE_VINTAGE,
} from "../../../../lib/layers_p4_ohuseire";
// KLIIMA-HOOK (#611): harvested climate-normals cells (see below).
import {
  KLIIMA_CELLS,
  KLIIMA_VINTAGE,
  isKliimaLayerId,
  kliimaPointsIn,
  kliimaSliceFor,
} from "../../../../lib/layers_kliima";
// POI-HOOK (#612): long-tail sidecar points (see below).
import {
  isPoiLayerId,
  POI_VINTAGE,
  poiPointsIn,
  poiSliceFor,
} from "../../../../lib/layers_p4_poi";
// FIXIT-HOOK (#623): report-pin sidecar points (see below).
import {
  FIXIT_VINTAGE,
  FIXIT_WINDOW_DAYS,
  fixitPointsIn,
  isFixitLayerId,
} from "../../../../lib/layers_p4_fixit";
import { loadSenscomSnapshot, senscomPointsIn } from "../../../../lib/server/senscom";
import { loadOoklaSnapshot, ooklaPointsIn } from "../../../../lib/server/ookla";

export const dynamic = "force-dynamic";

function parseBBox(url: URL): BBoxLike | null {
  const nums = ["minlon", "minlat", "maxlon", "maxlat"].map((k) =>
    Number(url.searchParams.get(k)),
  );
  if (!nums.every(Number.isFinite)) return null;
  const [minlon, minlat, maxlon, maxlat] = nums;
  if (minlon >= maxlon || minlat >= maxlat) return null;
  return { minlon, minlat, maxlon, maxlat };
}

/**
 * GET /api/layers/<parks|transit|schools>?minlon&minlat&maxlon&maxlat
 * -> { points, provenance: snapshot|empty, ageMs }
 *
 * Served exclusively from the local 2026-09-12 snapshot — no upstream
 * requests, so map pans can never throttle a source service. Tiles outside
 * snapshot coverage resolve to honestly-empty (the map renders those as
 * "no data", never as zero). A broken snapshot is a 500, which the client
 * maps to labeled demo points. The generic fileCache/overpass modules stay
 * for future parameters beyond snapshot coverage; this route does not use
 * them.
 */
export async function GET(
  request: Request,
  { params }: { params: { layer: string } },
): Promise<NextResponse> {
  const def = LAYERS.find((l) => l.id === params.layer);
  if (!def) {
    return NextResponse.json({ error: "unknown layer" }, { status: 404 });
  }
  const bbox = parseBBox(new URL(request.url));
  if (!bbox) {
    return NextResponse.json({ error: "bad bbox" }, { status: 400 });
  }
  const tile = tileForView(bbox);
  if (!intersectsCoverage(tile)) {
    return NextResponse.json({ points: [], provenance: "empty", ageMs: null });
  }
  // P4-031-HOOK (#484): senscom points come from the sensor.community
  // Tallinn extract (never the OSM snapshot, never live). A missing or
  // corrupt extract is a 500 (client shows labeled demo); a valid
  // extract with no sensors in view is honestly-empty (the map renders
  // those as "no data", never as zero).
  if (isSenscomLayerId(def.id)) {
    const snap = await loadSenscomSnapshot();
    if (!snap) {
      return NextResponse.json({ error: "no senscom snapshot data" }, { status: 500 });
    }
    const points = senscomPointsIn(snap, bbox);
    const age = snap.fetched ? Date.parse(snap.fetched) : NaN;
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Number.isFinite(age) ? Date.now() - age : null,
    });
  }
  // TERVISE-HOOK (#494): tervise points come from the committed
  // projected extract (TERVISE_POINTS in lib/layers_tervise.ts, built
  // offline by scripts/build/batch_tervise.py — never the OSM snapshot,
  // never live). Provenance "snapshot" (local static data); the status
  // line names the Terviseamet vintage instead of the OSM snapshot date
  // (see app/layers/page.tsx). An empty view bbox is honestly-empty.
  if (isTerviseLayerId(def.id)) {
    const points = tervisePointsIn(TERVISE_POINTS, bbox);
    // Vintage midnight parses in SERVER-LOCAL time (no Z suffix): the
    // vintage is a local calendar date (harvest 2026-09-14 00:04 EEST),
    // and a UTC-midnight parse goes negative before 03:00 UTC.
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${TERVISE_VINTAGE}T00:00:00`),
    });
  }
  // VIIRS-HOOK (#719): viirs cells come from the committed sampled
  // extract (VIIRS_CELLS in lib/layers_p4_viirs.ts, built offline by
  // scripts/build/batch_viirs.py from the keyless GIBS harvest —
  // never live). Provenance "snapshot" (local static data); the
  // status line names the 2016 composite vintage instead of the OSM
  // snapshot date (see app/layers/page.tsx). An empty view bbox is
  // honestly-empty.
  if (isViirsLayerId(def.id)) {
    const points = viirsPointsIn(VIIRS_CELLS, bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${VIIRS_VINTAGE}-01-01T00:00:00`),
    });
  }
  // FLOOD-HOOK (#487): floodzone is polygons-only (zero points, zero
  // raster — the /floodzone/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or a
  // raster here would 500 a healthy layer into labeled demo points (a
  // fake gradient), and demo fallback points are refused by the layer
  // def (empty fallbackPoints, pinned by test).
  if (isFloodLayerId(def.id)) {

    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // EELIS-HOOK (#488): eelis layers are polygons-only (zero points,
  // zero raster — the /eelis/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or a
  // raster here would 500 a healthy layer into labeled demo points (a
  // fake gradient), and demo fallback points are refused by the layer
  // defs (empty fallbackPoints, pinned by test).
  if (isEelisLayerId(def.id)) {

    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // MAAPARCEL-HOOK (#491): maaparcel is polygons-only (zero points,
  // zero raster — the /maaparcel/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or a
  // raster here would 500 a healthy layer into labeled demo points (a
  // fake gradient), and demo fallback points are refused by the layer
  // def (empty fallbackPoints, pinned by test).
  if (isMaaParcelLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // SEVESO-HOOK (#613): seveso is polygons-only (zero points, zero
  // raster — the /seveso/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isSevesoLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // DELAY-HOOK (#629): delay is polygons-only (zero points, zero
  // raster — the /delay/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer defs (empty fallbackPoints, pinned by test).
  if (isDelayLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // STATELAND-HOOK (#615): stateland is polygons-only (zero points,
  // zero raster — the /stateland/areas sidecar carries the data).
  // Answer honestly-empty points on snapshot provenance: requiring
  // points or a raster here would 500 a healthy layer into labeled
  // demo points (a fake gradient), and demo fallback points are
  // refused by the layer def (empty fallbackPoints, pinned by test).
  if (isStatelandLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }  if (isStatelandLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // SOIL-HOOK (#617): soil is polygons-only (zero points, zero raster
  // — the /soil/areas viewport proxy carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isSoilLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // QUARRY-HOOK (#614): quarry is polygons-only (zero points, zero
  // raster — the /quarry/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isQuarryLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // DRAINAGE-HOOK (#616): drainage is polygons-only (zero points, zero
  // raster — the /maaparandus/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isMaaparandusLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // ETAK-HOOK (#618): etak is polygons-only (zero points, zero raster
  // — the /etak/areas viewport proxy carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isEtakLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // RELIEF-HOOK (#619): relief is taste-only (zero points, zero raster
  // — the /relief/areas tint grid carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isReliefLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // CANOPY-HOOK (#620): canopy is taste-only (zero points, zero raster
  // — the /canopy/areas tint grid carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isCanopyLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // BUILDINGS-HOOK (#621): buildings is taste-only (zero points, zero
  // raster — the /buildings/areas tint grid carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isBuildingsLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // DENSITY-HOOK (#622): density is taste-only (zero points, zero
  // raster — the /density/areas squares carry the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or
  // a raster here would 500 a healthy layer into labeled demo points
  // (a fake gradient), and demo fallback points are refused by the
  // layer def (empty fallbackPoints, pinned by test).
  if (isDensityLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // FOREST-HOOK (#624): forest is polygons-only (zero points, zero
  // raster — the /forest/areas sidecar carries the data; the live
  // scorer leg is dims_p4_forestchange.py). Answer honestly-empty
  // points on snapshot provenance: requiring points or a raster here
  // would 500 a healthy layer into labeled demo points (a fake
  // gradient), and demo fallback points are refused by the layer def
  // (empty fallbackPoints, pinned by test).
  if (isForestLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // HARBOUR-HOOK (#627): harbour port points come from the snapshot
  // sidecar (harbour/harbour-areas.json, built offline by
  // scripts/build/batch_harbour.py — never live). A missing sidecar
  // stays honestly-empty. Vintage rides HARBOUR_VINTAGE (AIS 2024).
  if (isHarbourLayerId(def.id)) {
    const { ports } = await loadHarbourAreas(snapshotDir());
    const points = harbourPointsIn(ports, bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${HARBOUR_VINTAGE}-01-01T00:00:00`),
    });
  }
  // NOISE-HOOK (#625): noise is polygons-only (zero points, zero
  // raster — the /noise/areas sidecar carries the data; the live
  // scorer leg is dims_p4_noisemap.py). Answer honestly-empty
  // points on snapshot provenance: requiring points or a raster here
  // would 500 a healthy layer into labeled demo points (a fake
  // gradient), and demo fallback points are refused by the layer def
  // (empty fallbackPoints, pinned by test).
  // KPO-HOOK (#626): kpo is polygons-only (zero points, zero
  // raster — the /kpo/areas sidecar carries the data; the live
  // scorer legs are dims_p4_kitsendus.py). Answer honestly-empty
  // points on snapshot provenance: requiring points or a raster here
  // would 500 a healthy layer into labeled demo points (a fake
  // gradient), and demo fallback points are refused by the layer def
  // (empty fallbackPoints, pinned by test).
  if (isKpoLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  if (isNoiseLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // OOKLA-HOOK (#489): ookla points come from the Ookla Tallinn
  // extract (never the OSM snapshot, never live). A missing or
  // corrupt extract is a 500 (client shows labeled demo); a valid
  // extract with no tiles in view is honestly-empty. The extract
  // carries no fetch date (quarter label lives in OOKLA_QUARTER), so
  // ageMs stays null.
  if (isOoklaLayerId(def.id)) {
    const snap = await loadOoklaSnapshot();
    if (!snap) {
      return NextResponse.json({ error: "no ookla snapshot data" }, { status: 500 });
    }
    const points = ooklaPointsIn(snap, def.id === "ookla_fixed" ? "fixed" : "mobile", bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: null,
    });
  }
  // ACCBLACK-HOOK (#490, reopen #522): projected blackspot points come
  // from the snapshot sidecar (accblack/accblack-points.json, built
  // offline by projecting the Transpordiamet CSV with the ported
  // L-EST97 transform — never live). A missing sidecar stays
  // honestly-empty: the map renders "no data", never a faked zero.
  if (isAccBlackLayerId(def.id)) {
    const all = await loadAccblackPoints(snapshotDir());
    const points: LayerPoint[] = all
      .filter(
        (p) =>
          p.lon >= bbox.minlon && p.lon <= bbox.maxlon &&
          p.lat >= bbox.minlat && p.lat <= bbox.maxlat,
      )
      .map((p) => ({ lat: p.lat, lon: p.lon }));
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: null,
    });
  }
  // ASUMEDIA-HOOK (#495): the measured per-asum set is empty on purpose
  // (dated negative 2026-09-14 — 0/84 asums reach MIN_N=5, see
  // lib/layers_asumedia.ts). Serve honestly-empty: the map renders
  // "no data", never a faked median and never labeled demo. A layer
  // with neither points nor raster would otherwise be a 500 here.
  if (isAsumediaLayerId(def.id)) {
    return NextResponse.json({ points: [], provenance: "empty", ageMs: null });
  }
  // SPORT-HOOK (#607): sport-slice points come from the snapshot
  // sidecar (sport/sport-points.json, built offline by
  // scripts/build/batch_sport.py — never the OSM snapshot, never
  // live). A missing sidecar stays honestly-empty: the map renders
  // "no data", never a faked zero. Vintage rides SPORT_VINTAGE (the
  // register harvest date), not the OSM snapshot date.
  if (isSportLayerId(def.id)) {
    const all = await loadSportPoints(snapshotDir());
    const points: LayerPoint[] = sportPointsIn(all, sportSliceFor(def.id), bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${SPORT_VINTAGE}T00:00:00`),
    });
  }
  // EHIS-HOOK (#608): measured-school points come from the snapshot
  // sidecar (ehis/ehis-points.json, built offline by
  // scripts/build/batch_ehis.py — never the OSM snapshot, never
  // live). A missing sidecar stays honestly-empty. Vintage rides
  // EHIS_VINTAGE (the register harvest date), not the OSM snapshot
  // date. The OSM `schools` layer is untouched (separate tuning).
  if (isEhisLayerId(def.id)) {
    const all = await loadEhisPoints(snapshotDir());
    const points: LayerPoint[] = ehisPointsIn(all, ehisSliceFor(def.id), bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${EHIS_VINTAGE}T00:00:00`),
    });
  }
  // MEDRE-HOOK (#609): primary-care points come from the snapshot
  // sidecar (medre/medre-points.json, built offline by
  // scripts/build/batch_medre.py — never the OSM snapshot, never
  // live). Step 1 ships register tallies with points [] (no ADS join
  // owned) so this stays honestly-empty: the map renders "no data",
  // never a faked clinic. Vintage rides MEDRE_VINTAGE.
  if (isMedreLayerId(def.id)) {
    const all = await loadMedrePoints(snapshotDir());
    const points: LayerPoint[] = medrePointsIn(all, medreSliceFor(def.id), bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${MEDRE_VINTAGE}T00:00:00`),
    });
  }
  // OHUSEIRE-HOOK (#610): official air-station points come from the
  // snapshot sidecar (ohuseire/ohuseire-points.json, built offline by
  // scripts/build/batch_ohuseire.py — never the OSM snapshot, never
  // live). A missing sidecar stays honestly-empty. Vintage rides
  // OHUSEIRE_VINTAGE. DIY senscom stations stay untouched.
  if (isOhuseireLayerId(def.id)) {
    const all = await loadOhuseirePoints(snapshotDir());
    const points: LayerPoint[] = ohuseirePointsIn(all, bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${OHUSEIRE_VINTAGE}T00:00:00`),
    });
  }
  // KLIIMA-HOOK (#611): climate-normals cells come from the committed
  // harvest (KLIIMA_CELLS in lib/layers_kliima.ts, built offline by
  // scripts/build/batch_kliima.py — never the OSM snapshot, never
  // live). Per-slice band stamps ride q; unranked cells ride WITHOUT
  // q (plotted for location, never scored — the qbands kernel renders
  // nearest-q-absent as unknown, byte parity with the scorer's EI OLE
  // on the same gap). Vintage rides KLIIMA_VINTAGE (annual harvest).
  if (isKliimaLayerId(def.id)) {
    const points: LayerPoint[] = kliimaPointsIn(
      KLIIMA_CELLS, kliimaSliceFor(def.id), bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${KLIIMA_VINTAGE}T00:00:00`),
    });
  }
  // POI-HOOK (#612): long-tail points come from the snapshot sidecar
  // (poi/poi-points.json, built offline by scripts/build/batch_poi.py
  // — never the OSM snapshot, never live). A missing sidecar stays
  // honestly-empty. Vintage rides POI_VINTAGE (monthly harvest).
  if (isPoiLayerId(def.id)) {
    const all = await loadPoiPoints(snapshotDir());
    const points: LayerPoint[] = poiPointsIn(all, poiSliceFor(def.id), bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${POI_VINTAGE}T00:00:00`),
    });
  }
  // FIXIT-HOOK (#623): report pins come from the snapshot sidecar
  // (fixit/fixit-points.json, built offline by
  // scripts/build/batch_fixit.py — never the OSM snapshot, never
  // live). Expiry is enforced HERE at serve time: pins older than
  // the rolling window never render as current, so a stale sidecar
  // degrades to honestly-empty. Vintage rides FIXIT_VINTAGE (daily
  // harvest).
  if (isFixitLayerId(def.id)) {
    const all = await loadFixitPoints(snapshotDir());
    const points: LayerPoint[] = fixitPointsIn(all, bbox, Date.now(),
                                               FIXIT_WINDOW_DAYS);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${FIXIT_VINTAGE}T00:00:00`),
    });
  }
  try {
    // Density layers (walkability/pedinfra/cycling) have no points file:
    // their raster is the data. A layer with neither points nor raster is
    // a 500 (client shows labeled demo), exactly as before.
    let points: LayerPoint[] = [];
    try {
      points = await loadSnapshotPoints(def.id, tile);
    } catch (err) {
      if (!(err instanceof SnapshotUnavailable)) throw err;
    }
    // Per-view score windows ride the dedicated /window endpoint; this
    // payload stays small (points are the Euclidean fallback only).
    // Distance still reports whether a walk raster exists for the layer.
    const { raster, distance } = await loadLayerRaster(def.id);
    if (points.length === 0 && !raster) {
      return NextResponse.json({ error: `no ${def.id} snapshot data` }, { status: 500 });
    }
    return NextResponse.json({
      points,
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  } catch (err) {
    if (err instanceof SnapshotUnavailable) {
      return NextResponse.json({ error: err.message }, { status: 500 });
    }
    throw err;
  }
}