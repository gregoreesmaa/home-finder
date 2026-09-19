// Elektrilevi live-outage overlay (issue #729, P4-009 power slice;
// follow-up of the POSITIVE probe #689). This file owns ALL outage
// overlay runtime data; shared files (lib/layers.ts,
// lib/distanceField.ts, lib/overlays.ts, lib/server/snapshot.ts,
// lib/server/outage.ts, app/api/layers/[layer]/route.ts) touch it
// only through small marked `OUTAGE-HOOK (#729)` blocks, so sibling
// batches stay disjoint. This module imports ./layers ONLY as types:
// no runtime cycle.
//
// SOURCE VERDICT (2026-09-19, polite GETs, probe UA
// `home-finder-research/0.1`, `--max-time` 30, paced, 429 as stop,
// raw in /tmp/hf729 only — full evidence in docs/p4_outage.md §2):
// keyless `geoserver-api/GetApplicationData` -> 200, ~127 KB
// double-encoded JSON `scopes.p.{areas,dynareas,outages}` (99 areas,
// 516 outages). Field semantics PINNED from the app's own
// `geoserver-api/content/configuration.js` (deferred from the probe,
// pinned now): OUTAGE_T_PLAN="p" / OUTAGE_T_FAULT="f" /
// OUTAGE_T_UPCOMING="u"; area counters fc/fcc = active faults +
// affected customers, pc/pcc = active planned, uc/ucc = upcoming
// planned ("Aktiivseid rikkelisi katkestusi / plaanilisi /
// Tulevane plaaniline katkestus / Mõjutatud kliente").
//
// HONESTY (load-bearing): a live snapshot is thin evidence — the
// bands are capped (fault 30 / planned 55 / upcoming-only 70 /
// clean 80) and every surface says hetkeseis, never reliability. A
// quiet live map is NOT a reliable feeder (SAIDI stays unpublished
// per dims_p4_elektrilevi — that module is untouched). City grain:
// ONE Tallinn centroid point (59.4372, 24.7536) carries the Tallinn
// row inside a hard 15 km radius (whole city reads the city row,
// outside stays null/255, never a faked calm); the Harju county row
// is the documented dims fallback, never averaged in. No snapshot
// (or older than 5 min) stays null/empty — the route serves 500 and
// the client falls back to the labeled demo (ookla #489 precedent).
// The kernel is byte parity with dim_outage_now in
// services/scoring/dims_p4_outage.py — changing the scorer without
// changing outageBandForRow (or vice versa) is a drift bug, pinned
// by the parity test below.
//
// The layer shares the P4-009 paramLabel with the ookla slices BY
// DESIGN (split-slice precedent: Ookla owns throughput, outage owns
// running cuts — same param, different legs, never double-scored).
// paramIds stays [] (parameters4 namespace).

import type { BBoxLike, BonusSpec, LayerDef, LayerId, LayerPoint } from "./layers";

export type OutageLayerId = "outage";

export const OUTAGE_LAYER_IDS: OutageLayerId[] = ["outage"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const OUTAGE_PARAM_LABEL = "P4-009";

/**
 * Dated source this layer rests on (see header + docs/p4_outage.md
 * §2). The harvester (scripts/build/batch_outage.py) refills the
 * sidecar every 5 min; the band function mirrors dim_outage_now.
 */
export const OUTAGE_PROBE = {
  date: "2026-09-19",
  liveVerified: true,
  sidecarCommitted: false,
} as const;

/** City-grain join point: Tallinn centroid (repo convention). */
export const OUTAGE_TALLINN = { lat: 59.4372, lon: 24.7536 } as const;

/**
 * Hard join radius in metres — city grain (centre to city edge is
 * ~10 km; 15 km keeps the whole city on the city row without
 * inventing coverage past it).
 */
export const OUTAGE_RADIUS_M = 15000;

/** Freshness ceiling in seconds (== OUTAGE_TTL_S in dims_p4_outage.py). */
export const OUTAGE_TTL_S = 300;

/**
 * Pole dataset serving the same sidecar shape (pole/api.py DATASETS
 * key, issue #775): the route reads the live table first (DATEX #763
 * precedent) and falls back to the operator local sidecar.
 */
export const OUTAGE_POLE_DATASET = "outage";

/** Capped hetkeseis bands (parity with dim_outage_now). */
export const OUTAGE_BANDS = { fault: 30, planned: 55, upcoming: 70, clean: 80 } as const;

/** LayerPoint.tags keys carrying one area row's live counters. */
export const OUTAGE_TAG_FC = "fc";
export const OUTAGE_TAG_FCC = "fcc";
export const OUTAGE_TAG_PC = "pc";
export const OUTAGE_TAG_PCC = "pcc";
export const OUTAGE_TAG_UC = "uc";
export const OUTAGE_TAG_UCC = "ucc";

export const OUTAGE_LAYERS: LayerDef[] = [
  {
    id: "outage",
    paramIds: [],
    paramLabel: OUTAGE_PARAM_LABEL,
    title: "Elektrikatkestused (hetkeseis, hinnang)",
    goodLabel:
      "roheline = rikkekaardil aktiivseid katkestusi pole (hetkeseis-hinnang, lagi 80 — vaikne kaart ei ole töökindluse tõend)",
    badLabel:
      "punane = aktiivne rikkeline VÕI plaaniline katkestus Tallinnas (hetkeseis) VÕI seis teadmata (EI OLE värsket väljavõtet)",
    source:
      "Elektrilevi rikkekaart (keyless GetApplicationData, 5-min väljavõte; Tallinna rida: fc/fcc aktiivsed rikked, pc/pcc plaanilised, uc/ucc tulevased — hetkeseis, MITTE fiidri ajalugu SAIDI; ajalugu avaldamata, lähemalt docs/p4_outage.md)",
    // EMPTY BY HONESTY (load-bearing): no committed snapshot exists
    // (live data goes stale in minutes) — the route serves the fresh
    // sidecar when the operator pull is in TTL, else 500 → demo.
    // Never hand-place a calm point here.
    fallbackPoints: [],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — running cuts
 * are not OSM data; inventing plumbing would be dishonest, paaste
 * #493 precedent). overpassQueryFor("outage") is never called in
 * production; the string only satisfies the registry shape.
 */
export const OUTAGE_TAGS: Record<OutageLayerId, string> = {
  outage:
    "Elektrilevi rikkekaart GetApplicationData (keyless elav JSON, 5-min väljavõte; serveeritakse operaatori/pooluse vahemälust, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see OUTAGE_NO_RASTER). */
export const OUTAGE_RASTER_FILE: Record<OutageLayerId, string> = {
  outage: "outage-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat quality kernel IS
 * the field (tervise #494 precedent). A county stamp of one city
 * point would add build machinery without meaning. The window route
 * serves 500 for this layer and the client falls back to the splat
 * (designed path).
 */
export const OUTAGE_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the name resolves
 * absent so windows fall back to county cleanly (harno #687
 * precedent).
 */
export const OUTAGE_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 15 km join radius: the
 * scale story is the city-grain window, same as the kernel).
 */
export const OUTAGE_DECAY: Record<OutageLayerId, number> = {
  outage: 15.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isOutageLayerId(layer: LayerId): layer is OutageLayerId {
  return (OUTAGE_LAYER_IDS as string[]).includes(layer);
}

/** Quality-band spec for the outage layer (called from the bonusSpecFor hook). */
export function outageBonusSpecFor(layer: OutageLayerId): BonusSpec {
  void layer;
  return { kind: "qbands", radiusM: OUTAGE_RADIUS_M };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function outageHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface OutagePoint {
  lat: number;
  lon: number;
  /** Capped hetkeseis band (absent = quality NULL, never a faked calm). */
  q?: number;
  tags?: Record<string, string>;
}

function numTag(tags: Record<string, string> | undefined, key: string): number | null {
  if (!tags) return null;
  const raw = tags[key];
  if (typeof raw !== "string") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

/** One counter off a served point, null when unmeasured. */
export function outageCountOf(
  tags: Record<string, string> | undefined,
  key: string,
): number | null {
  return numTag(tags, key);
}

/**
 * Capped hetkeseis band off one area row's counters — byte parity
 * with dim_outage_now in services/scoring/dims_p4_outage.py (fault
 * 30 / planned 55 / upcoming-only 70 / clean 80; missing counts
 * never zero-fill into calm). Null when the row carries no
 * scoreable class (unknown, never zero).
 */
export function outageBandForRow(row: {
  fc?: number | null;
  fcc?: number | null;
  pc?: number | null;
  pcc?: number | null;
  uc?: number | null;
  ucc?: number | null;
}): number | null {
  const { fc, fcc, pc, pcc, uc, ucc } = row;
  if ((typeof fc === "number" && fc > 0) || (typeof fcc === "number" && fcc > 0))
    return OUTAGE_BANDS.fault;
  if ((typeof pc === "number" && pc > 0) || (typeof pcc === "number" && pcc > 0))
    return OUTAGE_BANDS.planned;
  if ((typeof uc === "number" && uc > 0) || (typeof ucc === "number" && ucc > 0))
    return OUTAGE_BANDS.upcoming;
  const all = [fc, fcc, pc, pcc, uc, ucc];
  if (all.every((v) => v === 0)) return OUTAGE_BANDS.clean;
  return null;
}

/**
 * Nearest outage point within the hard city radius, nearest first
 * (pure). No averaging, no smoothing — mirrors the qbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function outageNearby(
  lat: number,
  lon: number,
  points: OutagePoint[],
  radiusM: number = OUTAGE_RADIUS_M,
): { point: OutagePoint; distM: number }[] {
  const out: { point: OutagePoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = outageHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Hetkeseis hinnang at one address: the NEAREST point's band, null
 * where no point covers the address or the nearest point's quality
 * is NULL (unknown, never zero, never a faked calm).
 */
export function outageBandAt(
  lat: number,
  lon: number,
  points: OutagePoint[],
  radiusM: number = OUTAGE_RADIUS_M,
): number | null {
  const near = outageNearby(lat, lon, points, radiusM);
  if (near.length === 0) return null;
  const q = near[0].point.q;
  return typeof q === "number" && Number.isFinite(q) ? q : null;
}

/** Extract points clipped to the view bbox (same inBBox contract as senscom). */
export function outagePointsIn(points: OutagePoint[], bbox: BBoxLike): LayerPoint[] {
  return points.filter(
    (p) =>
      p.lon >= bbox.minlon && p.lon <= bbox.maxlon && p.lat >= bbox.minlat && p.lat <= bbox.maxlat,
  );
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const OUTAGE_HOOK =
  "OUTAGE-HOOK (#729): outage wired into layers/overlays/snapshot/route/server; P4-009 power leg, city-grain hetkeseis (never reliability).";
