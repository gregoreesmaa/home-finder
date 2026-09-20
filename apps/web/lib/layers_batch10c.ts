// Group 10 batch-C utility layers (parameters3.md §5.10, issue #121).
//
// One layer per mappable Group 10C parameter, Harjumaa scope, local
// 2026-09-12 snapshot ONLY. Scores are absolute 0..100; unknown stays 255
// (renders red). This file owns ALL Batch-10C runtime data; shared files
// (lib/layers.ts, lib/server/snapshot.ts) touch it only through small
// marked `B10C-HOOK (#121)` blocks, so the sibling batches stay disjoint.
//
// HONESTY (load-bearing): the KKIS/TTJA registries and KOV ÜVK master
// plans are NOT in the snapshot, so every layer below is an honestly-
// labeled OSM-derived PROXY. Titles, legends and sources say
// "kaardistatud" (mapped) and "hinnang"/"proksi" (estimate/proxy) —
// never measured broadband coverage, tap-water source, collection
// service, or signal field strength. p51's registry type is BOOLEAN
// (connected/not); the registry is absent, so the proxy is a 0-100
// score, never a fake boolean.
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf ...
//   man_made=mast: 219 uses (~199 with tower:type=communication =
//     confirmed telecom); man_made=communications_tower: 4;
//     man_made=tower: 276 (mostly church/clock/observation, excluded
//     without tower:type=communication — sibling p52 owns generic masts).
//   man_made=antenna: 44; communication:television=yes: 6;
//     communication:radio=yes: 1 (sparse: OTA absence is a soft floor).
//   man_made=water_well: 29; natural=spring: 40;
//     amenity=drinking_water: 88 (~157 mapped public water points).
//   amenity=waste_disposal: 709; amenity=recycling: 1034 (dense);
//     amenity=waste_basket: 6347 (street litter bins — furniture, not
//     collection service — deliberately excluded).
//
// Calibration (judgment calls, documented for the reviewer): both layers
// are unweighted count kernels, area-kind saturating scores
// (100·S/(S+half)), mirroring the grocery/healthcare/B5 path. Water is
// sparse (~154 mapped points), so half 1 lets a lone public tap read
// mid-ramp. Waste uses the hydrant half (6) at comparable urban density.
// Measured Tallinn-window medians/max (known cells, 2026-09-12 build):
// water 37/88, waste 23/84 — streets discriminate instead of blobbing.
// Sigmas equal the Euclidean fallback decay (DECAY_KM hook) and the
// raster contract (matchesContract). Halves live in one dict below and
// in scripts/build/batch_b10c_utility.py LAYER_DEFAULTS (kept in sync
// by test).
//
// SCOPE (cut after buyer review): p51/p262/p265 shipped as mast-
// proximity map layers first and were removed — masts cannot show
// fiber/mobile coverage. p51 RETURNS here as FIBER on real TTJA
// netikaart coverage (~160k reported ≥1000 Mbit/s addresses, half 50 /
// sigma 0.3; Tallinn-window med/max 44/87 — the city saturates green,
// which is the truth). p262/p265 stay cut (redundancy incomprehensible,
// OTA unmappable — see dims_group10c.py). Their scorer dims still serve
// per-listing scoring.

import type { BonusSpec, LayerDef } from "./layers";

export type Batch10CLayerId = "water" | "waste" | "fiber" | "mobile";

export const BATCH10C_LAYER_IDS: Batch10CLayerId[] = ["water", "waste", "fiber", "mobile"];

/** parameters3.md number per Batch-10C layer. */
export const BATCH10C_PARAMS: Record<Batch10CLayerId, number> = {
  water: 53,
  waste: 54,
  fiber: 51,
  mobile: 51,
};

export const BATCH10C_DEFS: LayerDef[] = [
  {
    id: "water",
    paramIds: [53],
    title: "Avalikud veepunktid",
    goodLabel: "roheline = avalik veepunkt (kraan/kaev/allikas) lähedal",
    badLabel: "punane = avalikku veepunkti lähedal pole",
    source:
      "kohalik väljavõte 2026-09-12 (OSM drinking_water/water_well/spring; Tallinna ühisveevärk kaardil pole — kiht näitab avalikke punkte, nt matkajale ja koerajalutajale)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn
      { lat: 59.2, lon: 24.5 }, // Maapiirkond
    ],
  },
  {
    id: "waste",
    paramIds: [54],
    title: "Taarapunktid ja jäätmejaamad",
    goodLabel: "roheline = taara- või jäätmepunkt lähedal",
    badLabel: "punane = viimispunkti lähedal pole",
    source:
      "kohalik väljavõte 2026-09-12 (OSM waste_disposal/recycling; korraldatud prügivedu kaardil pole — kiht näitab viimispunkte; tänavaprügikastid välja arvatud)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn
      { lat: 59.44, lon: 24.82 }, // Lasnamäe
    ],
  },
  {
    id: "fiber",
    paramIds: [51],
    title: "Fiiber (≥1000 Mbit/s teatatud katvus)",
    goodLabel: "roheline = fiiber-katvusega aadress lähedal",
    badLabel: "punane = teatatud katvus puudub",
    source:
      "TTJA netikaart 2026-09-12 (operaatorite teatatud ≥1000 Mbit/s kaabliühendused, ~160 tuhat aadressi; mitteteatamine loeb punaseks — see on teatatud katvus, mitte mõõdetud kiirus)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe katvus)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hõre katvus)
    ],
  },
  {
    id: "mobile",
    paramIds: [51],
    title: "Mobiililevi (mõõdetud leviala)",
    goodLabel: "roheline = mõõdetud levialas (tugevaim kärg)",
    badLabel: "punane = väljaspool mõõdetud leviala",
    source:
      "OpenCellID 2026-09-12 (CC-BY-SA; ~4,2 tuhat hulgimõõdetud LTE-levijalajälge ulatusega; täpid on mõõtmiskohad, mitte mastid — Telia alakaetud)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe mõõtmine)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hõre mõõtmine)
    ],
  },
];

/** Influence radii in km (== walk-kernel sigma == Euclidean fallback decay). */
export const BATCH10C_DECAY: Record<Batch10CLayerId, number> = {
  water: 0.5,
  waste: 0.3,
  fiber: 0.3,
  mobile: 1.0,
};

/**
 * Overpass QL fragments for the layer inside the bbox. Snapshot-only
 * serving never queries live; these document the source tags. The
 * telecom subset (tower:type=communication) is filtered at build time —
 * Overpass cannot express that split in one fragment, so the internet /
 * redundancy fragments over-select and the builder keeps confirmed use.
 */
export const BATCH10C_TAGS: Record<Batch10CLayerId, string> = {
  water: 'nwr["man_made"="water_well"];nwr["natural"="spring"];nwr["amenity"="drinking_water"];',
  waste: 'nwr["amenity"~"waste_disposal|recycling"];',
  // Fiber comes from TTJA netikaart (WFS overlay points), not OSM — this
  // fragment documents the tier query for rebuilds, never a live fetch.
  fiber: 'wfs:kaabliyhendused_1000 (TTJA netikaart, operaatorite teatatud);',
  // Mobile comes from the OpenCellID export (CSV overlay points), not
  // OSM — fragment documents the filter for rebuilds, never a live fetch.
  mobile: 'ocid:mcc=248,radio=LTE (OpenCellID, hulgimõõdetud);',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const BATCH10C_RASTER_FILE: Record<Batch10CLayerId, string> = {
  water: "water-walk-raster.json",
  waste: "waste-walk-raster.json",
  fiber: "fiber-walk-raster.json",
  mobile: "mobile-walk-raster.json",
};

/**
 * Bonus specs (the single source of halves — no separate HALVES dict).
 * Mobile is measured-coverage discs (cover-kind, self-scaling, no half:
 * the measured ranges ARE the calibration).
 */
export const BATCH10C_BONUS: Record<Batch10CLayerId, BonusSpec> = {
  water: { kind: "area", half: 1 },
  waste: { kind: "area", half: 6 },
  fiber: { kind: "area", half: 50 },
  mobile: { kind: "cover", sigma: 1.0 },
};

/**
 * Batch-10C bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for all other layers (their switch/hooks handle them).
 */
export function bonusSpecForBatch10C(layer: string): BonusSpec | undefined {
  return (BATCH10C_BONUS as Record<string, BonusSpec>)[layer];
}
