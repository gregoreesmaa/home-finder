// TEHIK medre primary-care dots overlay (issue #609, Step 1; P4-011 GP
// half from services/scoring/dims_p4_medre.py). This file owns ALL
// medre runtime data; shared files (lib/layers.ts, lib/overlays.ts,
// lib/server/snapshot.ts, app/api/layers/[layer]/route.ts,
// app/layers/page.tsx) touch it only through small marked `MEDRE-HOOK
// (#609)` blocks, so sibling batches stay disjoint. This module
// imports ./layers ONLY as types: no runtime cycle.
//
// FEED VERDICT (2026-09-16, polite one-off round, custom UA
// `home-finder-research/0.1`, single GETs, no retries; aggregates only,
// raw bodies never committed — full evidence in docs/p4_medre.md):
// medre nimistud bulk (HTTP 200, ~3.6 MB, DAILY): 782 <nimistu> rows,
// 870 <koht> reception addresses with <adr_id> ADS refs (378 Harju),
// ZERO with coordinates. medre companies bulk (HTTP 200, ~14.5 MB,
// DAILY): 1571 <asutus> rows (759 Harju/Tallinn), 537 Üldarstiabi
// tegevuskoht rows with plain-text addresses, ZERO with coordinates.
// Harvest scripts/build/batch_medre.py (monthly TTL, paced, 429 =
// stop) stores the register tallies + linkage report in the snapshot
// sidecar (medre/medre-points.json) with points [] and linkage_rate 0
// — no ADS adr_id->AKS join adapter is owned anywhere in the repo, so
// the caller-joined set is EMPTY (Step 2 replaces it and bumps the
// rate; the loader and kernel already serve whatever the sidecar
// carries).
//
// HONESTY (load-bearing, paaste #493 precedent): addresses are not
// points — hand-geocoding them would invent clinics, so this layer
// ships an HONEST-EMPTY point set (no derived-medre.json sidecar
// points, no builder-invented coords) and every surface says EI OLE +
// the buyer-side check (Tervisekassa per-GP lookup + kohapeal).
// Response quality is NOT mappable either — the bulk has no
// open/closed, capacity, or patient-count column anywhere (grep over
// the full 3.6 MB), so the status leg stays NULL (dims precedent) and
// proximity is coverage, never care quality (cap 80, never 100 — the
// scorer's own ceiling). The map kernel below is the coverage twin of
// that leg: ≥1 joined point within 2 km reads the scorer band table
// (<=500 m -> 80, <=1 km -> 65, <=2 km -> 50); nothing in radius reads
// NaN/unknown (never zero). DORMANT today (zero joined points →
// all-NaN, pinned by test) pending the Step-2 ADS join + the joint
// WEIGHTS rebalancing (per-batch rebalancing stays one joint change).
//
// OVERLAY-ONLY (documented): no walk raster / metro master is built —
// the named files resolve absent so the layer degrades through the
// designed path (API honestly-empty → map "no data", never invented
// markers). `dbands` kind skips the /window fetch by the generic
// short-circuit (no console litter).
//
// Share-alike scope (reviewable): CC BY-NC-SA 3.0 on both bulks —
// attribution + share-alike + non-commercial scope ride the legend +
// docs/p4_medre.md. GP names never leave the sidecar (tallies only,
// no per-doctor rows — reasons never name a doctor, dims precedent).
// Eriarstiabi/Oendusabi legs stay OUT (primary-care scope only).
//
// Overlap (documented): P4-011 is shared with the EHIS school slices
// (#608) — same buyer param, distinct slices (gp/clinic vs
// school/kindergarten/hobby), distinct dim keys, no double-score of
// one signal (DEDICATED_SPLIT discipline, #612 precedent).
//
// The layers carry NO parameters3.md id: P4-011 is a parameters4 buyer
// param (ehis #608 / sport #607 precedent). paramIds stays [] and
// paramLabel carries the slice ("P4-011") for the layer buttons.

import type { BBoxLike, BonusSpec, LayerDef, LayerId } from "./layers";

export type MedreLayerId = "medre_gp" | "medre_clinic";

export const MEDRE_LAYER_IDS: MedreLayerId[] = ["medre_gp", "medre_clinic"];

/** Buyer-param slice these overlays visualize (NOT a parameters3 id). */
export const MEDRE_PARAM_LABEL = "P4-011";

/**
 * Dated harvest these layers rest on (see header). The Python builder
 * (scripts/build/batch_medre.py) and the 2026-09-16 live pulls agree:
 * 782 nimistu / 870 kohad (378 Harju); 1571 asutus (759 Harju) / 537
 * Üldarstiabi kohad; linkage_rate 0 (zero coord-carrying rows exist).
 */
export const MEDRE_PROBE = {
  date: "2026-09-16",
  nimistu: 782,
  harjuKohad: 378,
  asutus: 1571,
  uldarstiabiKohad: 537,
  linkageRate: 0,
} as const;

/** Vintage label stamped on the sidecar build (monthly harvest, 30 d TTL). */
export const MEDRE_VINTAGE = "2026-09-16";

/**
 * Proximity bands in metres — the scorer PROX_BANDS (km) restated:
 * changing services/scoring/dims_p4_medre.py without changing this
 * (or vice versa) is a drift bug, pinned by test on both sides.
 * DORMANT until Step 2 joins points (all-NaN today, pinned by test).
 */
export const MEDRE_EDGES_M: ReadonlyArray<readonly [number, number]> = [
  [500, 80],
  [1000, 65],
  [2000, 50],
];

/**
 * Hard join radius in metres — the outer band edge. Everything renders
 * unknown by honesty until the ADS join lands.
 */
export const MEDRE_RADIUS_M = 2000;

/** Slice tag carried by sidecar points (lat/lon/slice only on the wire). */
export type MedreSlice = "gp" | "clinic";

export interface MedrePoint {
  lat: number;
  lon: number;
  slice: MedreSlice;
}

export const MEDRE_LAYERS: LayerDef[] = [
  {
    id: "medre_gp",
    paramIds: [],
    paramLabel: MEDRE_PARAM_LABEL,
    title: "Perearstid (nimistu, hinnang)",
    goodLabel:
      "roheline = perearsti vastuvõtukoht 2 km raadiuses (hinnang — lähedus, mitte kvaliteet)",
    badLabel:
      "punane = vastuvõtukoht 2 km raadiuses puudu või asukohad teadmata (EI OLE masinloetavat koordinaadivoogu)",
    source:
      "TEHIK medre perearstide nimistud (masinloetav XML, 2026-09-16: 782 nimistut, 378 Harju vastuvõtukohta ADS-aadressiviidetega, koordinaate EI OLE; CC BY-NC-SA 3.0) — EI OLE liitmist ADS-koordinaatidega, asukohad Tervisekassa perearstiotsingust ja kohapeal, järjekorrad/avatud-olek mõõtmata",
    // EMPTY BY HONESTY (load-bearing): zero joined points exist, so
    // the demo fallback plots ZERO markers. Never add a demo point
    // here — it would paint a fake clinic (paaste #493 precedent).
    fallbackPoints: [],
  },
  {
    id: "medre_clinic",
    paramIds: [],
    paramLabel: MEDRE_PARAM_LABEL,
    title: "Perearstikeskused (kliinik, hinnang)",
    goodLabel:
      "roheline = üldarstiabi tegevuskoht 2 km raadiuses (hinnang — lähedus, mitte kvaliteet)",
    badLabel:
      "punane = tegevuskoht 2 km raadiuses puudu või asukohad teadmata (EI OLE masinloetavat koordinaadivoogu)",
    source:
      "TEHIK medre tervishoiuteenuse osutajad (masinloetav XML, 2026-09-16: 1571 asutust, 537 üldarstiabi tegevuskohta tekstiaadressidega, koordinaate EI OLE; CC BY-NC-SA 3.0) — EI OLE liitmist koordinaatidega, eriarstiabi/hambaravi väljas (esmane tase ainult)",
    // EMPTY BY HONESTY (load-bearing): see medre_gp above.
    fallbackPoints: [],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — register data is
 * not OSM data; inventing amenity=doctors plumbing would be
 * dishonest, paaste #493 precedent). overpassQueryFor("medre_*") is
 * never called in production; the string only satisfies the registry
 * shape.
 */
export const MEDRE_TAGS: Record<MedreLayerId, string> = {
  medre_gp:
    "TEHIK medre päritolu märkus (nimistu vastuvõtukohad ADS-viidetega, liitmine ootel), mitte Overpass-päring.",
  medre_clinic:
    "TEHIK medre päritolu märkus (üldarstiabi tegevuskohad tekstiaadressidega, liitmine ootel), mitte Overpass-päring.",
};

/** Raster master filenames (intentionally never built — see MEDRE_NO_RASTER). */
export const MEDRE_RASTER_FILE: Record<MedreLayerId, string> = {
  medre_gp: "medre-gp-walk-raster.json",
  medre_clinic: "medre-clinic-walk-raster.json",
};

/**
 * NO raster master (documented): with zero joined points there is no
 * field to bake — a no-data raster would be fake precision. Step 2
 * keeps the points-splat distance kernel (sport #607 dbands
 * precedent); the window route serves 500 and the client falls back
 * to the splat.
 */
export const MEDRE_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the window route is
 * skipped by the generic dbands short-circuit and empty windows serve
 * county everywhere (sport #607 precedent).
 */
export const MEDRE_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 2 km join radius, dormant
 * until Step 2 — see header calibration note).
 */
export const MEDRE_DECAY: Record<MedreLayerId, number> = {
  medre_gp: 2.0,
  medre_clinic: 2.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isMedreLayerId(layer: LayerId): layer is MedreLayerId {
  return (MEDRE_LAYER_IDS as readonly string[]).includes(layer);
}

/**
 * Distance-band spec for the medre layers (called from the
 * bonusSpecFor hook). Reuses the sport #607 dbands kernel — same band
 * table as the scorer, no new spec kind. DORMANT until Step 2 joins
 * points (zero witnesses → all-NaN, pinned by test).
 */
export function medreBonusSpecFor(_layer: MedreLayerId): BonusSpec {
  void _layer;
  return {
    kind: "dbands",
    radiusM: MEDRE_RADIUS_M,
    edges: MEDRE_EDGES_M.map(([m, b]) => [m, b] as [number, number]),
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function medreHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/**
 * Band for a distance in metres under the scorer table (pure) — the map
 * twin of dims_p4_medre._band_score with km restated as m. Beyond the
 * outer edge reads null (never zero).
 */
export function medreBandAt(distM: number): number | null {
  for (const [edgeM, band] of MEDRE_EDGES_M) {
    if (distM <= edgeM) return band;
  }
  return null;
}

/** Slice tag for a medre layer id (pure). */
export function medreSliceFor(layer: MedreLayerId): MedreSlice {
  return layer.replace("medre_", "") as MedreSlice;
}

/**
 * Nearest joined point within the hard radius, nearest first (pure).
 * DORMANT: the caller-joined set is empty until the Step-2 ADS join,
 * so this returns [] on live data (pinned by test) — never a faked
 * neighbor. Mirrors the dbands kernel in distanceField.ts (same hard
 * cutoff, same nearest rule) for when Step 2 lands.
 */
export function medreNearby(
  lat: number,
  lon: number,
  points: MedrePoint[],
  slice: MedreSlice,
  radiusM: number = MEDRE_RADIUS_M,
): { point: MedrePoint; distM: number }[] {
  const out: { point: MedrePoint; distM: number }[] = [];
  for (const p of points) {
    if (p.slice !== slice) continue;
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = medreHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Points of one slice inside a bbox (pure) — the route serves these
 * from the snapshot sidecar (never the OSM snapshot, never live).
 * Empty until Step 2 (honestly-empty, never demo).
 */
export function medrePointsIn(
  points: MedrePoint[],
  slice: MedreSlice,
  bbox: BBoxLike,
): { lat: number; lon: number }[] {
  return points
    .filter(
      (p) =>
        p.slice === slice &&
        p.lon >= bbox.minlon &&
        p.lon <= bbox.maxlon &&
        p.lat >= bbox.minlat &&
        p.lat <= bbox.maxlat,
    )
    .map((p) => ({ lat: p.lat, lon: p.lon }));
}
