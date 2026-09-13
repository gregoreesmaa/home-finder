// GTFS stop overlay (issue #483): peatus/Elron/TLT stops as points.
//
// One layer, Harjumaa scope, local 2026-09-12 snapshot ONLY. The point
// set is MEASURED-ONLY: 1120 TLT-city GTFS stops (bus/tram/troll) from
// the snapshot vintage gtfs/tallinn-gtfs-2026-09-11.zip with scheduled
// Wednesday departures in `t`, plus 112 mapped Elron rail stations from
// the snapshot OSM extract (position + real railway tags, never `t`).
// Regional peatus stops outside the city vintage are NOT plotted
// (beyond-vintage is unknown, never faked); peatus.ee live stays closed
// and Elron publishes no machine timetable (dated negatives 2026-09-13,
// see services/scoring/dims_p4_peatus.py + dims_p4_elron.py).
//
// HONESTY (load-bearing): GTFS static carries SCHEDULES, never
// occupancy — marker size is scheduled Wednesday departures and the
// legend says so; evening ridership (P4-032 Elron/TLT slices) stays NULL
// with EI OLE reasons in the scorer dims, never painted from departures.
// One vintage stop (Sinilille 00902-2) has no trips at all: plotted
// without `t` (unknown service, never a faked zero).
//
// OVERLAY-ONLY (documented divergence, reviewed in #483): no walk
// raster and no metro master are built — the layer rides the Euclidean
// fallback splat with the trips spec (same scheduled-departures
// semantics and half as the transit layer, whose point set instead uses
// OSM nodes + default-100 fills; this set has no fills, so beyond-
// vintage reads honestly unknown). Calibration (builder printout,
// scripts/build/batch_gtfs_stops.py): wed deps/stop median 138 / p10 42
// / max 974 — the group-12 anchor, re-measured on the same vintage;
// half 1500 reads Balti jaam 57 / Raekoja plats 70 / Oismae 42 /
// Viimsi 6 / rural unknown: streets discriminate instead of blobbing.
// The multi-mode kicker (+10, 2 modes) fires only via Elron rail tags —
// GTFS points are classless BY HONESTY (no invented OSM tags), so the
// field is effectively pure scheduled-service density.
//
// This file owns ALL gtfsstops runtime data; shared files
// (lib/layers.ts, lib/overlays.ts, lib/server/snapshot.ts) touch it
// only through small marked `GTFS-HOOK (#483)` blocks.

import type { BonusSpec, LayerDef } from "./layers";

export type GtfsstopsLayerId = "gtfsstops";

export const GTFSSTOPS_LAYER_IDS: GtfsstopsLayerId[] = ["gtfsstops"];

/**
 * parameters3.md number per gtfsstops layer. p15 is SHARED with the
 * transit layer (same parameter, measured-only point set vs default-
 * filled set — the fiber/mobile p51 precedent in layers_batch10c.ts).
 */
export const GTFSSTOPS_PARAMS: Record<GtfsstopsLayerId, number> = {
  gtfsstops: 15,
};

export const GTFSSTOPS_DEFS: LayerDef[] = [
  {
    id: "gtfsstops",
    paramIds: [15],
    title: "GTFS peatused",
    goodLabel: "roheline = sagedane sõiduplaaniline ühendus lähedal",
    badLabel: "punane = ühendus harv või vintsist väljas (teadmata)",
    source:
      "TLT GTFS-vints 2026-09-11 (buss/tramm/troll: 1120 peatust, sõiduplaan, mitte täituvus) + kaardistatud Elroni jaamad OSM-ist (112, ainult asukoht; peatus.ee otseallikas suletud, Elroni masin-sõiduplaani pole)",
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam (GTFS + Elron)
      { lat: 59.4236, lon: 24.7972 }, // Ülemiste (Elron, kaardistatud)
    ],
  },
];

/** Influence radius in km (== Euclidean fallback sigma, transit parity). */
export const GTFSSTOPS_DECAY: Record<GtfsstopsLayerId, number> = {
  gtfsstops: 0.2,
};

/**
 * Overpass QL fragment for the layer inside the bbox. Snapshot-only
 * serving never queries live; documents the source tags for rebuilds.
 */
export const GTFSSTOPS_TAGS: Record<GtfsstopsLayerId, string> = {
  gtfsstops:
    'n["highway"="bus_stop"];n["public_transport"~"platform|stop_position|station"];n["railway"~"station|halt|stop|tram_stop"];',
};

/**
 * Raster master filename next to the base masters. NOT BUILT by
 * documented overlay-only decision (see header): the name resolves to
 * an absent file so the layer rides the Euclidean fallback splat with
 * the trips spec below, honestly labeled "euclidiline varu".
 */
export const GTFSSTOPS_RASTER_FILE: Record<GtfsstopsLayerId, string> = {
  gtfsstops: "gtfsstops-walk-raster.json",
};

/** NO metro master (documented): overlay-only, windows serve county. */
export const GTFSSTOPS_NO_METRO = true;

/**
 * Bonus spec: scheduled Wednesday departures, saturating
 * (100·S/(S+1500)) + multi-mode kicker (transit parity — same vintage,
 * same semantics; the kicker fires only via Elron rail tags, GTFS
 * points are classless by honesty, see header).
 */
export const GTFSSTOPS_BONUS: Record<GtfsstopsLayerId, BonusSpec> = {
  gtfsstops: { kind: "trips", half: 1500, modeBonus: 10, minModes: 2 },
};

/**
 * Batch-GTFS bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for all other layers (their switch/hooks handle them).
 */
export function bonusSpecForGtfsstops(layer: string): BonusSpec | undefined {
  return (GTFSSTOPS_BONUS as Record<string, BonusSpec>)[layer];
}

/** Type guard for the bonusSpecFor()/goodnessAt() hooks in ./layers. */
export function isGtfsstopsLayerId(layer: string): layer is GtfsstopsLayerId {
  return layer === "gtfsstops";
}
