// Bus-mesh transfer nodes (issue #769, probe #764 verdict POSITIIVNE):
// granular sõlmed where GTFS static route shapes cross, snapped to stops.
//
// Three window layers (each from its OWN services — Wednesday is the
// commuter peak, Saturday/Sunday independently derived, never copied):
// busmesh (E-R workdays), busmesh-sat, busmesh-sun. One point per snapped
// stop {lon, lat, t = route count}; classless BY HONESTY (no invented OSM
// tags, gtfsstops #483 precedent), so the client multi-mode kicker stays
// off (modeBonus 0).
//
// HONESTY (load-bearing): GTFS static carries SCHEDULES, never occupancy
// or reliability — marker size is the route count at the stop and the
// legend says so. 252 Wednesday clusters have no stop within 100 m and
// are NOT plotted (geometry, not usable transfers — diagnostic count in
// the builder printout). 199 off-node stops read honestly unknown
// ("üksikteenus") instead of borrowing a neighbour. Vintage-capped:
// TLT GTFS-vints 2026-09-11; re-verify counts with a new vintage
// (scripts/build/batch_busmesh_nodes.py).
//
// OVERLAY-ONLY (gtfsstops #483 precedent): no walk raster and no metro
// master are built — the layers ride the Euclidean fallback splat with
// the transfer spec (route-count semantics, half 5; calibration in the
// builder printout: Balti jaam 83 / Raekoja plats 96 / Õismäe 70 /
// Viimsi 4 / rural unknown — hubs discriminate instead of blobbing).
//
// This file owns ALL busmesh runtime data; shared files
// (lib/layers.ts, lib/overlays.ts, lib/server/snapshot.ts) touch it
// only through small marked `BUSMESH-HOOK (#769)` blocks.

import type { BonusSpec, LayerDef } from "./layers";

export type BusmeshLayerId = "busmesh" | "busmesh-sat" | "busmesh-sun";

export const BUSMESH_LAYER_IDS: BusmeshLayerId[] = [
  "busmesh",
  "busmesh-sat",
  "busmesh-sun",
];

/**
 * parameters3.md number per busmesh layer. p15 is SHARED with transit +
 * gtfsstops (same parameter, third leg — the fiber/mobile p51
 * precedent): transit bakes default-filled departure density, gtfsstops
 * measured-only departure density, busmesh transfer richness. Same
 * parameter, different legs, never double-scored.
 */
export const BUSMESH_PARAMS: Record<BusmeshLayerId, number> = {
  busmesh: 15,
  "busmesh-sat": 15,
  "busmesh-sun": 15,
};

const WINDOW_ET: Record<BusmeshLayerId, string> = {
  busmesh: "tööpäev (E–R)",
  "busmesh-sat": "laupäev",
  "busmesh-sun": "pühapäev",
};

const WINDOW_N: Record<BusmeshLayerId, number> = {
  busmesh: 437,
  "busmesh-sat": 426,
  "busmesh-sun": 423,
};

export const BUSMESH_DEFS: LayerDef[] = BUSMESH_LAYER_IDS.map((id) => ({
  id,
  paramIds: [15],
  title: `Ümberistumissõlmed (${WINDOW_ET[id]})`,
  goodLabel: "roheline = palju marsruute ühes peatuses (hea ümberistumine)",
  badLabel: "punane = üksikteenus või vintsist väljas (teadmata)",
  source:
    `TLT GTFS-vints 2026-09-11: ${WINDOW_N[id]} peatusega sõlme (${WINDOW_ET[id]} teenus; sõiduplaan, mitte täituvus ega töökindlus; peatusteta 100 m geomeetria plotimata)`,
  fallbackPoints: [
    { lat: 59.4405, lon: 24.7369 }, // Balti jaam (30 liini tipphub)
    { lat: 59.4372, lon: 24.7536 }, // Raekoja plats (keskuse sõlm)
  ],
}));

/** Influence radius in km (== Euclidean fallback sigma, gtfsstops parity). */
export const BUSMESH_DECAY: Record<BusmeshLayerId, number> = {
  busmesh: 0.2,
  "busmesh-sat": 0.2,
  "busmesh-sun": 0.2,
};

/**
 * Overpass QL fragment for the layer inside the bbox. Snapshot-only
 * serving never queries live (route comment); documents the source tags
 * for rebuilds. overpassQueryFor("busmesh*") is never called in
 * production (senscom #484 precedent).
 */
export const BUSMESH_TAGS: Record<BusmeshLayerId, string> = {
  busmesh:
    'n["highway"="bus_stop"];n["public_transport"~"platform|stop_position|station"];',
  "busmesh-sat":
    'n["highway"="bus_stop"];n["public_transport"~"platform|stop_position|station"];',
  "busmesh-sun":
    'n["highway"="bus_stop"];n["public_transport"~"platform|stop_position|station"];',
};

/**
 * Raster master filename next to the base masters. NOT BUILT by
 * documented overlay-only decision (see header): the name resolves to
 * an absent file so the layers ride the Euclidean fallback splat with
 * the transfer spec below, honestly labeled "euclidiline varu".
 */
export const BUSMESH_RASTER_FILE: Record<BusmeshLayerId, string> = {
  busmesh: "busmesh-walk-raster.json",
  "busmesh-sat": "busmesh-sat-walk-raster.json",
  "busmesh-sun": "busmesh-sun-walk-raster.json",
};

/** NO metro master (documented): overlay-only, windows serve county. */
export const BUSMESH_NO_METRO = true;

/**
 * Bonus spec: transfer richness — route count at the stop, saturating
 * (100·n/(n+5)): 2 routes -> ~29, 5 -> 50, 10 -> ~67, 30 -> ~86
 * (pinned by test_dims_p4_busmesh.py node_score anchors). modeBonus 0:
 * points are classless by honesty, so the multi-mode kicker never fires.
 */
export const BUSMESH_BONUS: Record<BusmeshLayerId, BonusSpec> = {
  busmesh: { kind: "trips", half: 5, modeBonus: 0, minModes: 2 },
  "busmesh-sat": { kind: "trips", half: 5, modeBonus: 0, minModes: 2 },
  "busmesh-sun": { kind: "trips", half: 5, modeBonus: 0, minModes: 2 },
};

/**
 * Batch-busmesh bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for all other layers (their switch/hooks handle them).
 */
export function bonusSpecForBusmesh(layer: string): BonusSpec | undefined {
  return (BUSMESH_BONUS as Record<string, BonusSpec>)[layer];
}

/** Type guard for the bonusSpecFor()/goodnessAt() hooks in ./layers. */
export function isBusmeshLayerId(layer: string): layer is BusmeshLayerId {
  return (
    layer === "busmesh" || layer === "busmesh-sat" || layer === "busmesh-sun"
  );
}
