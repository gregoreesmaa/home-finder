// Päästeamet fire-station (komando) point overlay (issue #493, Group B
// verify-first; P4-012 station half from services/scoring/dims_p4_paaste.py).
// This file owns ALL paaste runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/server/snapshot.ts) touch it only through small
// marked `PAASTE-HOOK (#493)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// FEED VERDICT (2026-09-13, four polite single GETs, probe UA
// `home-finder-p4-paaste-probe/1.0`, `--max-time 20`, no retries; full
// evidence in docs/p4_paaste.md §6): station locations are NOT open as
// a machine feed —
//   * `avaandmed.eesti.ee/datasets?ih=paasteamet` 301s to the new
//     Teabevärav (`andmed.eesti.ee`), which serves a JS app shell
//     (HTTP 200, 75 kB, zero server-rendered dataset records);
//   * `rescue.ee/et/kontaktid` + `/pohja_paastekeskus` are OPEN human
//     HTML org trees (HTTP 200, ~132 kB): komando names + STREET
//     ADDRESSES (e.g. "Erika tn 3, Tallinn"), ZERO coordinates, zero
//     map embeds, zero geojson.
// Addresses are not points: hand-geocoding them would invent stations,
// so this layer ships an HONEST-EMPTY point set (no derived-paaste.json
// sidecar, no builder) and every surface says EI OLE + the buyer-side
// check (rescue.ee kontaktid + Tark Tee + kohapeal).
//
// HONESTY (load-bearing): response-time gradients are NOT mappable —
// the module holds NO komando coordinates and computes NO routed time
// (dims_p4_paaste.py P4-012 shape: caller-supplied rescue_station POIs,
// straight-line penalty past 5 km only). The map kernel below is the
// coverage twin of that leg: ≥1 komando within 5 km reads 60 ("kaetud,
// hinnang"), nothing in radius reads NaN/unknown (never zero). Extra
// stations do NOT stack — response comes from the nearest komando, and
// proximity is coverage, never safety truth (cap 60, never 100). The
// bands are PROVISIONAL (unobservable today: zero points → all-NaN,
// pinned by test) pending a real feed + the joint WEIGHTS rebalancing
// (per-batch rebalancing stays one joint change).
//
// OVERLAY-ONLY (documented): no walk raster / metro master is built —
// the named files resolve absent so the layer degrades through the
// designed path (API 500 → honestly-labeled demo with ZERO markers,
// never invented ones). `bands` kind skips the /window fetch by the
// generic senscom short-circuit (no console litter).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type PaasteLayerId = "paaste";

export const PAASTE_LAYER_IDS: PaasteLayerId[] = ["paaste"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const PAASTE_PARAM_LABEL = "P4-012";

/**
 * Station coverage radius in metres — parity with STATION_FAR_KM in
 * services/scoring/dims_p4_paaste.py (the scorer's only station
 * distance: straight-line penalty past 5 km). Changing the scorer
 * without changing this (or vice versa) is a drift bug.
 */
export const PAASTE_FAR_M = 5000;

/**
 * Coverage band: ≥1 komando in radius reads 60 ("kaetud, hinnang").
 * Flat by honesty — extra stations do not stack coverage — and capped
 * far below 100 (proximity is not safety). PROVISIONAL until a station
 * feed exists (see header); dormant today (zero points → all-NaN).
 */
export const PAASTE_BANDS = { one: 60, twoThree: 60, fourPlus: 60 } as const;

export const PAASTE_LAYERS: LayerDef[] = [
  {
    id: "paaste",
    paramIds: [],
    paramLabel: PAASTE_PARAM_LABEL,
    title: "Päästekomandod (hinnang)",
    goodLabel:
      "roheline = päästekomando 5 km raadiuses (kaetud, hinnang — lähedus, mitte sõiduaeg)",
    badLabel:
      "punane = komando 5 km raadiuses puudu või asukohad teadmata (EI OLE masinloetavat voogu)",
    source:
      "Päästeameti kontaktipuu (inimloetav HTML, 2026-09-13: nimed + tänava-aadressid, koordinaate pole; Teabevärav andmekirjeid serveripoolselt pole) — EI OLE masinloetavat komandode asukoha-voogu; lähima komando kauguse hinnang selgub rescue.ee kontaktidest ja kohapeal, sõiduaeg Tark Tee kaardilt (marsruudi-aeg mõõtmata)",
    // EMPTY BY HONESTY (load-bearing): no verified komando coordinates
    // exist, so the demo fallback plots ZERO markers. Never add a
    // hand-geocoded address here — addresses are not points.
    fallbackPoints: [],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — Päästeamet data is
 * not OSM data; inventing amenity=fire_station plumbing would be
 * dishonest, docs/p4_paaste.md §1). overpassQueryFor("paaste") is never
 * called in production; the string only satisfies the registry shape.
 */
export const PAASTE_TAGS: Record<PaasteLayerId, string> = {
  paaste:
    "Päästeameti kontaktipuu (rescue.ee/et/kontaktid, inimloetav HTML — nimed + aadressid, koordinaate pole; serveeritakse väljavõtte vahemälu-komandode loendist, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see header). */
export const PAASTE_RASTER_FILE: Record<PaasteLayerId, string> = {
  paaste: "paaste-walk-raster.json",
};

/**
 * NO metro master (documented): overlay-only, like the senscom bands
 * layer — the window route is skipped by the generic bands
 * short-circuit and empty windows serve county everywhere.
 */
export const PAASTE_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 5 km coverage radius: the
 * scorer's station threshold, same scale story as the bands radius).
 * Dormant today (zero points → goodnessAt null everywhere).
 */
export const PAASTE_DECAY: Record<PaasteLayerId, number> = {
  paaste: 5.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isPaasteLayerId(layer: LayerId): layer is PaasteLayerId {
  return (PAASTE_LAYER_IDS as string[]).includes(layer);
}

/**
 * Honest-empty status line (issue #785). Paaste ships ZERO points BY
 * DECISION (addresses are not points — no machine feed, header
 * verdict) and always renders through the demo fallback — so the
 * generic "live ebaõnnestus" (live failed) label reads as breakage.
 * This names the dated verdict instead: EI OLE + source +
 * buyer-side check, never a count claim beyond the served points,
 * never a failure. Pure (pinned by test, silly #774 precedent).
 */
export function paasteDemoStatus(pointCount: number): string {
  return (
    "EI OLE masinloetavat komando-voogu (Päästeamet, 2026-09-13: nimed " +
    `+ aadressid, koordinaate pole) · ${pointCount} punkti — lähim ` +
    "komando selgub rescue.ee kontaktidest"
  );
}

/** Band spec for the paaste layer (called from the bonusSpecFor hook). */
export function paasteBonusSpecFor(layer: PaasteLayerId): BonusSpec {
  void layer;
  return {
    kind: "bands",
    radiusM: PAASTE_FAR_M,
    one: PAASTE_BANDS.one,
    twoThree: PAASTE_BANDS.twoThree,
    fourPlus: PAASTE_BANDS.fourPlus,
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function paasteHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface PaastePoint {
  lat: number;
  lon: number;
}

/**
 * Band for a komando count — flat 60 by honesty (see PAASTE_BANDS).
 * Null when no komando covers the address: unknown, never zero.
 */
export function paasteBandForCount(n: number): number | null {
  if (!Number.isFinite(n) || n <= 0) return null;
  return PAASTE_BANDS.one;
}

/**
 * Komandos within the hard coverage radius, nearest first (pure). No
 * averaging, no smoothing — mirrors the scorer's straight-line komando
 * leg (same hard cutoff, same order).
 */
export function paasteNearby(
  lat: number,
  lon: number,
  points: PaastePoint[],
  radiusM: number = PAASTE_FAR_M,
): { point: PaastePoint; distM: number }[] {
  const out: { point: PaastePoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = paasteHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Coverage hinnang 60 at one address, null where no komando covers it
 * (the scorer reads the same gap as NULL with hinnang + EI OLE +
 * buyer-side check — never a faked score).
 */
export function paasteCoveredAt(
  lat: number,
  lon: number,
  points: PaastePoint[],
  radiusM: number = PAASTE_FAR_M,
): number | null {
  return paasteBandForCount(paasteNearby(lat, lon, points, radiusM).length);
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const PAASTE_HOOK =
  "PAASTE-HOOK (#493): paaste wired into layers/overlays/snapshot; P4-012 station half, honest-empty (no machine feed, never invented stations).";
