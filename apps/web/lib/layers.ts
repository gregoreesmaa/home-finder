// Parameter map layers (parameters3.md): one layer per mappable parameter,
// green = good areas, red = bad areas. Listing-specific groups (portals,
// finance, HOA, inspection, subjective taste) and Group 2 EHR building
// attributes (G02-HOOK #136) are deliberately omitted — they describe a
// deal, not a place.
//
// Points come from the local 2026-09-12 snapshot via our server proxy.
// Transit stop positions are OSM nodes joined to Peatus.ee GTFS weekday
// departures (trips/day); stops outside GTFS coverage get a documented
// default instead of a faked zero.

import { haversineKm } from "./poi";
// B1-HOOK(#98): batch B1 (Group 11 amenity) layers own their tables in
// layers_batch1.ts; each hook below is one spread/guard line.
import {
  B1_DECAY,
  B1_LAYERS,
  B1_TAGS,
  b1BonusSpecFor,
  isB1LayerId,
  type B1LayerId,
} from "./layers_batch1";
// G07B-HOOK(#141): batch G07B (Group 7 env-health B) tables live in
// ./layers_group07b (new file). That module imports layers only as
// types, so no runtime cycle.
import {
  G07B_DECAY_KM,
  G07B_LAYERS,
  G07B_TAGS,
  g07bBonusSpecFor,
  isG07BLayerId,
  type G07BLayerId,
} from "./layers_group07b";
// G07-HOOK(#140): batch G07 (Group 7 env-health) tables live in
// ./layers_group07 (new file). That module imports layers only as types,
// so no runtime cycle.
import {
  G07_DECAY_KM,
  G07_LAYERS,
  G07_TAGS,
  g07BonusSpecFor,
  isG07LayerId,
  type G07LayerId,
} from "./layers_group07";
// B5-HOOK(#102): batch B5 (Group 14 public-safety) tables live in
// ./layers_batch5 (new file). That module imports layers only as types,
// so no runtime cycle.
import type { Batch5LayerId } from "./layers_batch5";
import {
  BATCH5_DECAY,
  BATCH5_DEFS,
  BATCH5_TAGS,
  bonusSpecForBatch5,
} from "./layers_batch5";
// G03-HOOK(#151): batch G03 (Group 3 cadastre-A drainage proxy) tables
// live in ./layers_group03 (new file). That module imports layers only
// as types, so no runtime cycle.
import type { Group03LayerId } from "./layers_group03";
import {
  GROUP03_DECAY,
  GROUP03_LAYERS,
  GROUP03_TAGS,
  bonusSpecForGroup03,
} from "./layers_group03";
// G08A-HOOK (#167): batch G08A (Group 8 flood/climate A: p69 wildfire
// proxy; p46/p112/p117 documented no-map) tables live in
// ./layers_group08a (new file). That module imports layers only as
// types, so no runtime cycle.
import type { G08ALayerId } from "./layers_group08a";
import {
  G08A_DECAY_KM,
  G08A_LAYERS,
  G08A_TAGS,
  bonusSpecForGroup08A,
} from "./layers_group08a";
// G03D-HOOK(#154): batch G03D (Group 3 cadastre-D moorage + shoredist)
// tables live in ./layers_group03d (new file). That module imports
// layers only as types, so no runtime cycle.
import type { Group03DLayerId } from "./layers_group03d";
import {
  GROUP03D_DECAY,
  GROUP03D_LAYERS,
  GROUP03D_TAGS,
  bonusSpecForGroup03D,
} from "./layers_group03d";
// G08D-HOOK(#170): batch G08D (Group 8 flood/climate-D vernalpool)
// tables live in ./layers_group08d (new file). That module imports
// layers only as types, so no runtime cycle.
import type { G08DLayerId } from "./layers_group08d";
import {
  G08D_DECAY_KM,
  G08D_LAYERS,
  G08D_TAGS,
  g08dBonusSpecFor,
  isG08DLayerId,
} from "./layers_group08d";
// G08C-HOOK(#169): batch G08C (Group 8 flood/climate-C surgeroad +
// slidebuf) tables live in ./layers_group08c (new file). That module
// imports layers only as types, so no runtime cycle.
import type { Group08CLayerId } from "./layers_group08c";
import {
  GROUP08C_DECAY,
  GROUP08C_LAYERS,
  GROUP08C_TAGS,
  bonusSpecForGroup08C,
} from "./layers_group08c";
// G08B-HOOK(#168): batch G08B (Group 8 flood/climate-B windtunnel +
// saltspray) tables live in ./layers_group08b (new file). That module
// imports layers only as types, so no runtime cycle.
import type { Group08BLayerId } from "./layers_group08b";
import {
  GROUP08B_DECAY,
  GROUP08B_LAYERS,
  GROUP08B_TAGS,
  bonusSpecForGroup08B,
} from "./layers_group08b";
// G05B-HOOK(#162): batch G05B (Group 5 plans-B gardens + buildout)
// tables live in ./layers_group05b (new file). That module imports
// layers only as types, so no runtime cycle.
import type { Group05BLayerId } from "./layers_group05b";
import {
  GROUP05B_DECAY,
  GROUP05B_LAYERS,
  GROUP05B_TAGS,
  bonusSpecForGroup05B,
} from "./layers_group05b";
// G11D-HOOK(#135): batch G11D (Group 11 leftovers B: p346/p470/p419/p466;
// p317 is a documented no-map) tables live in ./layers_group11d (new
// file). That module imports layers only as types, so no runtime cycle.
import {
  G11D_DECAY,
  G11D_LAYERS,
  G11D_TAGS,
  g11dBonusSpecFor,
  isG11DLayerId,
  type G11DLayerId,
} from "./layers_group11d";
// G07D-HOOK(#143): batch G07D (Group 7 env-health D) tables live in
// ./layers_group07d (new file). That module imports layers only as
// types, so no runtime cycle.
import {
  G07D_DECAY_KM,
  G07D_LAYERS,
  G07D_TAGS,
  g07dBonusSpecFor,
  isG07DLayerId,
  type G07DLayerId,
} from "./layers_group07d";
// G07C-HOOK(#142): batch G07C (Group 7 env-health C: p257 vector-habitat
// proxy; p260/p316/p401/p402 documented no-map) tables live in
// ./layers_group07c (new file, no imports from here — no runtime cycle).
import {
  G07C_DECAY_KM,
  G07C_LAYERS,
  G07C_TAGS,
  g07cBonusSpec,
  isG07CLayerId,
  type G07CLayerId,
} from "./layers_group07c";
// G06B-HOOK (#139): Group 6 leftover tables live in ./layers_group06b
// (new file). That module imports layers only as types, so no cycle.
import type { Group06BLayerId } from "./layers_group06b";
import {
  GROUP06B_DECAY,
  GROUP06B_DEFS,
  GROUP06B_TAGS,
  bonusSpecForGroup06B,
  isGroup06BAvoidLayer,
} from "./layers_group06b";
// G11C-HOOK(#134): batch G11C (Group 11 leftovers A) tables live in
// ./layers_group11c (new file). That module imports layers only as types,
// so no runtime cycle.
import type { Group11CLayerId } from "./layers_group11c";
import {
  G11C_DECAY,
  G11C_DEFS,
  G11C_TAGS,
  bonusSpecForGroup11C,
} from "./layers_group11c";
// B6-HOOK(#133): batch B6 (mobility/access leftovers: p220/p270/p386)
// tables live in ./layers_batch6 (new file). That module imports layers
// only as types, so no runtime cycle.
import type { Batch6LayerId } from "./layers_batch6";
import {
  BATCH6_DECAY,
  BATCH6_DEFS,
  BATCH6_TAGS,
  bonusSpecForBatch6,
} from "./layers_batch6";
// G02B-HOOK(#137): batch G02B (Group 2 EHR batch B, p196 lift proxy)
// tables live in ./layers_group02b (new file). That module imports
// layers only as types, so no runtime cycle.
import type { Group02bLayerId } from "./layers_group02b";
import {
  G02B_DECAY,
  G02B_DEFS,
  G02B_TAGS,
  bonusSpecForGroup02b,
} from "./layers_group02b";
// G02-HOOK(#136): Group 2 EHR batch-A verdicts live in ./layers_group02
// (new file, five documented no-map verdicts). That module imports
// nothing, so no runtime cycle.
import { GROUP02_UNMAPPED_PARAMS } from "./layers_group02";
// G06-HOOK (#138): Group 6 heritage tables live in ./layers_group06
// (new file). That module imports layers only as types, so no cycle.
import type { Group06LayerId } from "./layers_group06";
import {
  GROUP06_DECAY,
  GROUP06_DEFS,
  GROUP06_TAGS,
  bonusSpecForGroup06,
} from "./layers_group06";

export type LayerId =
  | "parks"
  | "transit"
  | "schools"
  | "walkability"
  | "pedinfra"
  | "cycling"
  | "grocery"
  | "healthcare"
  | B1LayerId // B1-HOOK(#98)
  // G07B-HOOK (#141): Group 7 env-health B ids (defined in ./layers_group07b).
  | G07BLayerId
  // G07D-HOOK (#143): Group 7 env-health D ids (defined in ./layers_group07d).
  | G07DLayerId
  // G07C-HOOK(#142): Group 7 env-health C id (defined in ./layers_group07c).
  | G07CLayerId
  // G07-HOOK (#140): Group 7 env-health ids (defined in ./layers_group07).
  | G07LayerId
  // B5-HOOK (#102): Group 14 public-safety ids (defined in ./layers_batch5).
  | Batch5LayerId
  // G11D-HOOK (#135): Group 11 leftover-B ids (./layers_group11d).
  | G11DLayerId
  // G06B-HOOK (#139): Group 6 leftover ids (defined in ./layers_group06b).
  | Group06BLayerId
  // G11C-HOOK (#134): Group 11 leftover-A ids (./layers_group11c).
  | Group11CLayerId
  // B6-HOOK (#133): mobility/access leftover ids (./layers_batch6).
  | Batch6LayerId
  // G06-HOOK (#138): Group 6 heritage id (defined in ./layers_group06).
  | Group06LayerId
  // G02B-HOOK (#137): Group 2 batch-B lift-proxy id (./layers_group02b).
  | Group02bLayerId
  // G03-HOOK (#151): Group 3 cadastre-A drainage id (./layers_group03).
  | Group03LayerId
  // G03D-HOOK (#154): Group 3 cadastre-D ids (./layers_group03d).
  | Group03DLayerId
  // G08A-HOOK (#167): Group 8 flood/climate A id (./layers_group08a).
  | G08ALayerId
  // G08D-HOOK (#170): Group 8 flood/climate-D id (./layers_group08d).
  | G08DLayerId
  // G08C-HOOK (#169): Group 8 flood/climate-C ids (./layers_group08c).
  | Group08CLayerId
  // G08B-HOOK (#168): Group 8 flood/climate-B ids (./layers_group08b).
  | Group08BLayerId
  // G05B-HOOK (#162): Group 5 plans-B ids (./layers_group05b).
  | Group05BLayerId;

export interface BBoxLike {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

export interface LayerPoint {
  lat: number;
  lon: number;
  /** Allowlisted OSM tags (variety/mode scoring); absent when unknown. */
  tags?: Record<string, string>;
  /** Weekday departures for transit trips scoring; absent means unknown. */
  t?: number;
  /** Hectares for the "area" score (parks); absent means no area. */
  a?: number;
}

/** Tag keys worth caching (small, bounded); names/addresses never leave. */
// B5-HOOK (#102): "emergency" keeps emergency=fire_hydrant tags (p315).
const TAG_ALLOWLIST = ["amenity", "leisure", "railway", "public_transport", "highway", "emergency",
  // G07C-HOOK(#142): vector-habitat points carry natural/landuse tags (p257).
  "natural", "landuse"];

/** Pick allowlisted string tags, or undefined when there are none. */
export function pickFeatureTags(tags: unknown): Record<string, string> | undefined {
  if (typeof tags !== "object" || tags === null) return undefined;
  const out: Record<string, string> = {};
  for (const k of TAG_ALLOWLIST) {
    const v = (tags as Record<string, unknown>)[k];
    if (typeof v === "string" && v.length > 0) out[k] = v;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

export interface LayerDef {
  id: LayerId;
  /** parameters3.md parameter numbers this layer implements. */
  paramIds: number[];
  title: string;
  /** Legend text: what green means. */
  goodLabel: string;
  /** Legend text: what red means. */
  badLabel: string;
  /** Provenance shown next to the map. */
  source: string;
  /** Honestly-labeled demo points used only when live fetch fails. */
  fallbackPoints: LayerPoint[];
}

export interface LayerHex {
  h3: string;
  score_goodness: number;
  lon: number;
  lat: number;
}

/**
 * Distance (km) at which goodness decays to ~37%. Deliberately steep:
 * hubs must beat suburbs (a lone stop 200 m out reads amber, not green).
 * Shared by scoring and the map field — changing these retunes both.
 */
const DECAY_KM: Record<LayerId, number> = {
  // Calibrated 2026-09-12 from Tallinn score histograms (absolute 0..100):
  // each layer's median sits mid-ramp so streets discriminate instead of
  // blobbing. Transit and parks use walk-graph kernels, narrower because
  // true walks run longer than Euclidean crow-flies distance (and narrow
  // kernels keep big-park adjacency from averaging into background green).
  parks: 0.25,
  transit: 0.2,
  schools: 0.8,
  walkability: 0.2,
  pedinfra: 0.25,
  cycling: 0.3,
  grocery: 0.3,
  healthcare: 0.8,
  ...B1_DECAY, // B1-HOOK(#98)
  // G07B-HOOK (#141): env-health B radii (see layers_group07b.ts G07B_DECAY_KM).
  ...G07B_DECAY_KM,
  // G07D-HOOK (#143): env-health D radii (see layers_group07d.ts G07D_DECAY_KM).
  ...G07D_DECAY_KM,
  // G07C-HOOK(#142): env-health C radius (see layers_group07c.ts G07C_DECAY_KM).
  ...G07C_DECAY_KM,
  // G07-HOOK (#140): env-health radii (see layers_group07.ts G07_DECAY_KM).
  ...G07_DECAY_KM,
  // B5-HOOK (#102): Group 14 radii (see layers_batch5.ts BATCH5_DECAY).
  ...BATCH5_DECAY,
  // G11D-HOOK (#135): leftover-B radii (see layers_group11d.ts G11D_DECAY).
  ...G11D_DECAY,
  // G06B-HOOK (#139): Group 6 leftover radii (see layers_group06b.ts GROUP06B_DECAY).
  ...GROUP06B_DECAY,
  // G11C-HOOK (#134): Group 11 leftover-A radii (layers_group11c.ts G11C_DECAY).
  ...G11C_DECAY,
  // B6-HOOK (#133): mobility/access radii (see layers_batch6.ts BATCH6_DECAY).
  ...BATCH6_DECAY,
  // G06-HOOK (#138): Group 6 radius (see layers_group06.ts GROUP06_DECAY).
  ...GROUP06_DECAY,
  // G02B-HOOK (#137): lift-proxy radius (see layers_group02b.ts G02B_DECAY).
  ...G02B_DECAY,
  // G03-HOOK (#151): drainage radius (see layers_group03.ts GROUP03_DECAY).
  ...GROUP03_DECAY,
  // G03D-HOOK (#154): moorage + shoredist radii (see layers_group03d.ts GROUP03D_DECAY).
  ...GROUP03D_DECAY,
  // G08A-HOOK (#167): wildfire radius (see layers_group08a.ts G08A_DECAY_KM).
  ...G08A_DECAY_KM,
  // G08D-HOOK (#170): vernalpool radius (see layers_group08d.ts G08D_DECAY_KM).
  ...G08D_DECAY_KM,
  // G08C-HOOK (#169): surgeroad + slidebuf radii (see layers_group08c.ts GROUP08C_DECAY).
  ...GROUP08C_DECAY,
  // G08B-HOOK (#168): windtunnel + saltspray radii (see layers_group08b.ts GROUP08B_DECAY).
  ...GROUP08B_DECAY,
  // G05B-HOOK (#162): gardens + buildout radii (see layers_group05b.ts GROUP05B_DECAY).
  ...GROUP05B_DECAY,
};

/** Meaningful influence radius in km: drives scoring decay and the map field. */
export function radiusKmFor(layer: LayerId): number {
  return DECAY_KM[layer];
}

export const LAYERS: LayerDef[] = [
  {
    id: "parks",
    paramIds: [19],
    title: "Pargid ja rohealad",
    goodLabel: "roheline = lühike jalutuskäik rohealale",
    badLabel: "punane = pikk jalutuskäik rohealadeni",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + haljasalad)",
    fallbackPoints: [
      { lat: 59.4386, lon: 24.7912 }, // Kadriorg
      { lat: 59.4318, lon: 24.7383 }, // Hirvepark
      { lat: 58.3785, lon: 26.7158 }, // Tartu Toomemägi
    ],
  },
  {
    id: "transit",
    paramIds: [15],
    title: "Ühistransport",
    goodLabel: "roheline = lühike jalutuskäik sagedase ühenduseni",
    badLabel: "punane = pikk jalutuskäik või harv ühendus",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + GTFS väljumised)",
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam
      { lat: 59.4278, lon: 24.7611 }, // Viru
      { lat: 58.378, lon: 26.729 }, // Tartu kesklinn
    ],
  },
  {
    id: "schools",
    paramIds: [12, 123],
    title: "Koolid ja lasteaiad",
    goodLabel: "roheline = lühike jalutuskäik kooli/lasteaiani",
    badLabel: "punane = pikk jalutuskäik või koole pole",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + amenity)",
    fallbackPoints: [
      { lat: 59.4326, lon: 24.7396 }, // Tallinna kesklinn
      { lat: 59.4211, lon: 24.7153 }, // Kristiine
      { lat: 58.3717, lon: 26.7219 }, // Tartu Karlova
    ],
  },
  {
    id: "walkability",
    paramIds: [14],
    title: "Jalutatavus",
    goodLabel: "roheline = tihe, hästi ühendatud tänavavõrk",
    badLabel: "punane = hõre võrk, pikad kõrvalteed",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafiku ristmike tihedus)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam
    ],
  },
  {
    id: "pedinfra",
    paramIds: [84],
    title: "Kõnniteed",
    goodLabel: "roheline = tihe kõnniteedevõrk",
    badLabel: "punane = kõnniteed puuduvad",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik, kõnniteede km)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn
      { lat: 59.412, lon: 24.655 }, // Õismäe
    ],
  },
  {
    id: "cycling",
    paramIds: [102],
    title: "Rattateed",
    goodLabel: "roheline = tihe rattateedevõrk",
    badLabel: "punane = rattateed puuduvad",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik, rattateede km)",
    fallbackPoints: [
      { lat: 59.4437, lon: 24.7307 }, // Telliskivi
      { lat: 59.44, lon: 24.82 }, // Lasnamäe
    ],
  },
  {
    id: "grocery",
    paramIds: [103],
    title: "Toidupoed",
    goodLabel: "roheline = pood jalutuskäigu kaugusel",
    badLabel: "punane = poed kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + shop)",
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Viru
      { lat: 59.44, lon: 24.82 }, // Lasnamäe
    ],
  },
  {
    id: "healthcare",
    paramIds: [20],
    title: "Tervishoid",
    goodLabel: "roheline = apteek/arst jalutuskäigu kaugusel",
    badLabel: "punane = arstiabi kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + amenity)",
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Viru
      { lat: 59.412, lon: 24.655 }, // Õismäe
    ],
  },
  ...B1_LAYERS, // B1-HOOK(#98): Group 11 amenity layers (p86/87/89/108/313)
  // G07B-HOOK (#141): env-health B defs (p189/p202/p227) from ./layers_group07b.
  ...G07B_LAYERS,
  // G07D-HOOK (#143): env-health D defs (p409/p450) from ./layers_group07d.
  ...G07D_LAYERS,
  // G07C-HOOK(#142): env-health C def (p257) from ./layers_group07c.
  ...G07C_LAYERS,
  // G07-HOOK (#140): env-health defs (p61/p62) from ./layers_group07.
  ...G07_LAYERS,
  // B5-HOOK (#102): Group 14 defs (p13/p78/p315/p335/p467) from ./layers_batch5.
  ...BATCH5_DEFS,
  // G11D-HOOK (#135): leftover-B defs (p346/p470/p419/p466) from ./layers_group11d.
  ...G11D_LAYERS,
  // G06B-HOOK (#139): Group 6 leftover defs (p352/p353/p356) from ./layers_group06b.
  ...GROUP06B_DEFS,
  // G11C-HOOK (#134): Group 11 leftover-A defs (p88/p101/p124/p169/p190).
  ...G11C_DEFS,
  // B6-HOOK (#133): mobility/access defs (p220/p270/p386) from ./layers_batch6.
  ...BATCH6_DEFS,
  // G06-HOOK (#138): Group 6 def (p72) from ./layers_group06.
  ...GROUP06_DEFS,
  // G02B-HOOK (#137): lift-proxy def (p196) from ./layers_group02b.
  ...G02B_DEFS,
  // G03-HOOK (#151): drainage def (p50) from ./layers_group03.
  ...GROUP03_LAYERS,
  // G03D-HOOK (#154): moorage (p332) + shoredist (p340) defs from ./layers_group03d.
  ...GROUP03D_LAYERS,
  // G08A-HOOK (#167): wildfire def (p69) from ./layers_group08a.
  ...G08A_LAYERS,
  // G08D-HOOK (#170): vernalpool def (p447) from ./layers_group08d.
  ...G08D_LAYERS,
  // G08C-HOOK (#169): surgeroad (p334) + slidebuf (p336) defs from ./layers_group08c.
  ...GROUP08C_LAYERS,
  // G08B-HOOK (#168): windtunnel (p255) + saltspray (p333) defs from ./layers_group08b.
  ...GROUP08B_LAYERS,
  // G05B-HOOK (#162): gardens (p106) + buildout (p146) defs from ./layers_group05b.
  ...GROUP05B_LAYERS,
];

// G02-HOOK (#136): Group 2 EHR batch-A params (p21/p30/p33/p35/p48) are
// deliberately NOT layers -- building attributes, not place fields
// (per-param verdicts in ./layers_group02). Locked by test: none of
// these ids may appear in any layer's paramIds.
/** parameters3.md ids with documented no-map verdicts (Group 2 EHR, #136). */
export const UNMAPPED_PARAMS: readonly number[] = GROUP02_UNMAPPED_PARAMS;

const TAGS: Record<LayerId, string> = {
  parks: 'n["leisure"~"park|garden|playground"];n["landuse"="recreation_ground"];',
  transit: 'n["public_transport"~"stop_position|platform"];n["railway"~"tram_stop|station"];n["highway"="bus_stop"];',
  schools: 'n["amenity"~"school|kindergarten|university|college"];',
  // Density layers (walkability/pedinfra/cycling) have no point features;
  // queries below document the source tags for future use.
  walkability: 'w["highway"~"residential|living_street|tertiary|secondary"];',
  pedinfra: 'w["highway"~"footway|path|pedestrian|steps"];',
  cycling: 'w["highway"="cycleway"];w["cycleway"~"lane|track"];',
  grocery: 'n["shop"~"supermarket|convenience|greengrocer|grocery|marketplace"];',
  healthcare: 'n["amenity"~"pharmacy|doctors|dentist"];',
  ...B1_TAGS, // B1-HOOK(#98)
  // G07B-HOOK (#141): env-health B queries (see layers_group07b.ts G07B_TAGS).
  ...G07B_TAGS,
  // G07D-HOOK (#143): env-health D queries (see layers_group07d.ts G07D_TAGS).
  ...G07D_TAGS,
  // G07C-HOOK(#142): env-health C query (see layers_group07c.ts G07C_TAGS).
  ...G07C_TAGS,
  // G07-HOOK (#140): env-health queries (see layers_group07.ts G07_TAGS).
  ...G07_TAGS,
  // B5-HOOK (#102): Group 14 queries (see layers_batch5.ts BATCH5_TAGS).
  ...BATCH5_TAGS,
  // G11D-HOOK (#135): leftover-B queries (see layers_group11d.ts G11D_TAGS).
  ...G11D_TAGS,
  // G06B-HOOK (#139): Group 6 leftover queries (see layers_group06b.ts GROUP06B_TAGS).
  ...GROUP06B_TAGS,
  // G11C-HOOK (#134): Group 11 leftover-A queries (layers_group11c.ts G11C_TAGS).
  ...G11C_TAGS,
  // B6-HOOK (#133): mobility/access queries (see layers_batch6.ts BATCH6_TAGS).
  ...BATCH6_TAGS,
  // G06-HOOK (#138): Group 6 query (see layers_group06.ts GROUP06_TAGS).
  ...GROUP06_TAGS,
  // G02B-HOOK (#137): lift-proxy query (see layers_group02b.ts G02B_TAGS).
  ...G02B_TAGS,
  // G03-HOOK (#151): drainage query (see layers_group03.ts GROUP03_TAGS).
  ...GROUP03_TAGS,
  // G03D-HOOK (#154): moorage + shoredist queries (see layers_group03d.ts GROUP03D_TAGS).
  ...GROUP03D_TAGS,
  // G08A-HOOK (#167): wildfire query (see layers_group08a.ts G08A_TAGS).
  ...G08A_TAGS,
  // G08D-HOOK (#170): vernalpool query (see layers_group08d.ts G08D_TAGS).
  ...G08D_TAGS,
  // G08C-HOOK (#169): surgeroad + slidebuf queries (see layers_group08c.ts GROUP08C_TAGS).
  ...GROUP08C_TAGS,
  // G08B-HOOK (#168): windtunnel + saltspray queries (see layers_group08b.ts GROUP08B_TAGS).
  ...GROUP08B_TAGS,
  // G05B-HOOK (#162): gardens + buildout queries (see layers_group05b.ts GROUP05B_TAGS).
  ...GROUP05B_TAGS,
};

/** Overpass QL for the layer inside the bbox (south,west,north,east). */
export function overpassQueryFor(layer: LayerId, bbox: BBoxLike): string {
  const bb = `${bbox.minlat},${bbox.minlon},${bbox.maxlat},${bbox.maxlon}`;
  const body = TAGS[layer].replaceAll("n[", `nwr[`);
  return `[out:json][timeout:25];(${body.replaceAll("];", `](${bb});`)});out center 2000;`;
}

interface OverpassElement {
  type?: unknown;
  lat?: unknown;
  lon?: unknown;
  center?: { lat?: unknown; lon?: unknown };
  tags?: unknown;
}

/** Nodes and way/relation centers become points; coordless junk is skipped. */
export function parseOverpassElements(payload: unknown): LayerPoint[] {
  const elements = (payload as { elements?: unknown })?.elements;
  if (!Array.isArray(elements)) return [];
  const out: LayerPoint[] = [];
  for (const e of elements as OverpassElement[]) {
    const lat = e?.lat ?? e?.center?.lat;
    const lon = e?.lon ?? e?.center?.lon;
    if (typeof lat !== "number" || typeof lon !== "number") continue;
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    const tags = pickFeatureTags(e?.tags);
    out.push(tags ? { lat, lon, tags } : { lat, lon });
  }
  return out;
}

/** Transit mode from stop tags; null when unrecognized (counts as a stop, not a mode). */
export function stopMode(tags: Record<string, string> | undefined): string | null {
  if (!tags) return null;
  if (tags.railway === "tram_stop") return "tram";
  if (tags.railway === "station" || tags.railway === "stop") return "train";
  if (tags.public_transport === "station") return "train";
  if (
    tags.highway === "bus_stop" ||
    tags.public_transport === "platform" ||
    tags.public_transport === "stop_position"
  ) {
    return "bus";
  }
  return null;
}

/**
 * Score spec per layer. The "area" kind is total nearby area, saturating:
 * score = 100·S/(S+half), linear in area (two 10-ha parks equal one
 * 20-ha park) with distance falloff from the kernel. "trips" is the same
 * shape over nearby weekday departures (two 500-trip stops equal one
 * 1000-trip stop) plus a multi-mode kicker; "variety" is a base+bonus
 * agglomeration for schools.
 */
export interface AreaSpec {
  kind: "area";
  /** Hectares scoring 50 next to the feature (saturation midpoint). */
  half: number;
}

export interface TripsSpec {
  kind: "trips";
  /** Departures scoring 50 next to the stop (saturation midpoint). */
  half: number;
  /** Flat bonus when distinct modes mix nearby. */
  modeBonus: number;
  /** Distinct modes nearby that earn the bonus. */
  minModes: number;
}

/**
 * Inverse proximity ("avoid") spec: score FALLS with nearness.
 * score = 100·(1−2^(−d/half)), d = walk/Euclidean km to the nearest
 * feature: 0 on top of a feature, 50 at `half` km, →100 far away.
 * Only G06B woodfire (p356 fire-spread attention) uses it: green = far
 * from mapped wooden houses. Null (no feature in range) stays null —
 * the raster/window path renders it red as honestly-unknown, same as
 * every other layer.
 */
export interface AvoidSpec {
  kind: "avoid";
  /** Walk-km from the nearest feature scoring 50 (woodfire: 0.21). */
  half: number;
}

export type BonusSpec =
  | AreaSpec
  | TripsSpec
  | { kind: "variety"; key: string; values: string[]; per: number; cap: number }
  // B6-HOOK (#133) + G07-HOOK (#140) + G03-HOOK (#151): nearest-source
  // calmness/cleanliness/drainage goodness (0 on the source, 50 at halfM).
  // G07B-HOOK (#141): nearest-source cleanliness (0 on the source, 50 at
  // halfM). Same kind the G07-A batch (#140) adds — identical semantics,
  // shared on purpose; if #140 lands first this union member dedupes on
  // rebase.
  // G11D-HOOK (#135): nearest-source calmness for inverted badness
  // layers (trailprivacy): 0 on the source, 50 at halfM (GENV designed
  // this kind but never wired it; G11D is the first wired use).
  // G07D-HOOK (#143): nearest-source cleanliness (0 on the source, 50 at
  // halfM). Same kind the G07-A/B batches (#140/#141) add — identical
  // semantics, shared on purpose; dedupes on rebase.
  | AvoidSpec
  | { kind: "variety"; key: string; values: string[]; per: number; cap: number }
  // B6-HOOK (#133) + G07-HOOK (#140): nearest-source calmness/cleanliness
  // (0 on the source, 50 at halfM).
  | { kind: "quiet"; halfM: number };

export function bonusSpecFor(layer: LayerId): BonusSpec {
  // B1-HOOK(#98): batch B1 specs live in layers_batch1.ts.
  if (isB1LayerId(layer)) return b1BonusSpecFor(layer);
  // G07B-HOOK(#141): env-health B specs live in layers_group07b.ts.
  if (isG07BLayerId(layer)) return g07bBonusSpecFor(layer);
  // G08D-HOOK(#170): flood/climate-D specs live in layers_group08d.ts.
  if (isG08DLayerId(layer)) return g08dBonusSpecFor(layer);
  // G07D-HOOK(#143): env-health D specs live in layers_group07d.ts.
  if (isG07DLayerId(layer)) return g07dBonusSpecFor(layer);
  // G07C-HOOK(#142): env-health C specs live in layers_group07c.ts.
  if (isG07CLayerId(layer)) return g07cBonusSpec(layer);
  // G07-HOOK(#140): env-health specs live in layers_group07.ts.
  if (isG07LayerId(layer)) return g07BonusSpecFor(layer);
  switch (layer) {
    case "parks":
      // Area-proportional: total nearby hectares, saturating (half = 15).
      // Calibrated on the walk-graph raster (Tallinn median mid-ramp;
      // the old half = 3 saturated the whole city once true polygon
      // hectares were summed). Drives the Euclidean fallback; the walk
      // raster has it baked in and is contract-checked (loadLayerRaster).
      return { kind: "area", half: 15 };
    case "transit":
      // Trips-proportional: total nearby weekday departures, saturating
      // (half = 1500). Calibrated on the walk-graph raster: Tallinn median
      // mid-ramp with Balti jaam at 100 and Raekoja plats at ~40. This spec
      // drives the Euclidean fallback; the walk raster has it baked in and
      // is contract-checked against these numbers (see loadTransitDistance).
      return { kind: "trips", half: 1500, modeBonus: 10, minModes: 2 };
    case "walkability":
      // Junction density from the foot graph (p14, half = 300 junctions).
      // Histogram-locked: Tallinn median mid-ramp (city grids are dense).
      return { kind: "area", half: 300 };
    case "pedinfra":
      // Dedicated footway km nearby (p84, half = 12 km).
      return { kind: "area", half: 12 };
    case "cycling":
      // Cycleway km nearby (p102, half = 3 km).
      return { kind: "area", half: 3 };
    case "grocery":
      // Nearby everyday food stores, unweighted counts (p103, half = 6).
      return { kind: "area", half: 6 };
    case "healthcare":
      // Nearby pharmacies/doctors/dentists, unweighted (p20, half = 20).
      return { kind: "area", half: 20 };
    case "schools":
      return {
        kind: "variety",
        key: "amenity",
        values: ["school", "kindergarten", "university", "college"],
        per: 12,
        cap: 36,
      };
  }
  // B5-HOOK (#102): Group 14 specs live in ./layers_batch5.
  const b5 = bonusSpecForBatch5(layer);
  if (b5) return b5;
  // G11D-HOOK (#135): leftover-B specs live in ./layers_group11d.
  if (isG11DLayerId(layer)) return g11dBonusSpecFor(layer);
  // G06B-HOOK (#139): Group 6 leftover specs live in ./layers_group06b.
  const g06b = bonusSpecForGroup06B(layer);
  if (g06b) return g06b;
  // G11C-HOOK (#134): Group 11 leftover-A specs live in ./layers_group11c.
  const g11c = bonusSpecForGroup11C(layer);
  if (g11c) return g11c;
  // B6-HOOK (#133): mobility/access specs live in ./layers_batch6.
  const b6 = bonusSpecForBatch6(layer);
  if (b6) return b6;
  // G06-HOOK (#138): Group 6 spec lives in ./layers_group06.
  const g06 = bonusSpecForGroup06(layer);
  if (g06) return g06;
  // G02B-HOOK (#137): lift-proxy spec lives in ./layers_group02b.
  const g02b = bonusSpecForGroup02b(layer);
  if (g02b) return g02b;
  // G03-HOOK (#151): drainage spec lives in ./layers_group03.
  const g03 = bonusSpecForGroup03(layer);
  if (g03) return g03;
  // G03D-HOOK (#154): moorage + shoredist specs live in ./layers_group03d.
  const g03d = bonusSpecForGroup03D(layer);
  if (g03d) return g03d;
  // G08A-HOOK (#167): wildfire spec lives in ./layers_group08a.
  const g08a = bonusSpecForGroup08A(layer);
  if (g08a) return g08a;
  // G08C-HOOK (#169): surgeroad + slidebuf specs live in ./layers_group08c.
  const g08c = bonusSpecForGroup08C(layer);
  if (g08c) return g08c;
  // G08B-HOOK (#168): windtunnel + saltspray specs live in ./layers_group08b.
  const g08b = bonusSpecForGroup08B(layer);
  if (g08b) return g08b;
  // G05B-HOOK (#162): gardens + buildout specs live in ./layers_group05b.
  const g05b = bonusSpecForGroup05B(layer);
  if (g05b) return g05b;
  throw new Error(`unknown layer: ${layer}`);
}

/**
 * Goodness 0..100 by nearest-feature distance (exponential decay).
 * Null when there are no features — the caller must show "no data",
 * never a faked zero.
 */
export function goodnessAt(
  lat: number,
  lon: number,
  points: LayerPoint[],
  layer: LayerId = "parks",
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = haversineKm(lat, lon, p.lat, p.lon);
    if (d < best) best = d;
  }
  // G06B-HOOK (#139): inverse ("avoid") layers score 100·(1−2^(−d/half)):
  // 0 on top of a feature, 50 at half km, →100 far away. Mirrors the
  // walk-raster stamp (batch_g06b_heritage.py) and the buildScoredField
  // branch, so the Euclidean fallback agrees with the raster about
  // direction (near wood = low fire-safety score).
  if (isGroup06BAvoidLayer(layer)) {
    const half = (bonusSpecFor(layer) as AvoidSpec).half;
    return Math.round(100 * (1 - Math.pow(2, -best / half)));
  }
  return Math.round(100 * Math.exp(-best / DECAY_KM[layer]));
}

export const OVERPASS_URL = "https://overpass-api.de/api/interpreter";

/** Where the map points came from (shown next to the map). */
export type LayerProvenance = "live" | "cache" | "stale" | "snapshot" | "empty" | "demo";

/**
 * Pre-scored transit walk-access grid (see scripts/build-walk-raster.py):
 * uint8 base64 scores 0..100 over the snapshot bbox, 255 = unknown.
 * Scores are FINAL (saturation + mode kicker baked); the client renders
 * and bilinear-samples but never recomputes.
 */
export interface WalkRasterDoc {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  /** Wire key is snake_case (Python builder), like minlon/minlat. */
  step_m: number;
  /** Saturation midpoint (area/trips kinds); null for variety (schools). */
  half: number | null;
  sigma: number;
  /** Variety ladder (schools); 0 for area/trips kinds. */
  per: number;
  cap: number;
  unknown: number;
  dtype: string;
  data: string;
}

/** How transit distances were measured for this response. */
export type TransitDistance = "walk" | "euclidean";

export interface LayerFetchResult {
  points: LayerPoint[];
  /** False => points are labeled demo fallback, not live data. */
  live: boolean;
  provenance: LayerProvenance;
  /** ms since the upstream fetch; null for demo fallback. */
  ageMs: number | null;
  /** Walk raster for transit; null for other layers or when degraded. */
  raster: WalkRasterDoc | null;
  distance: TransitDistance;
}

/** Validate a raster doc shape; the payload itself is decoded client-side. */
export function cleanRaster(p: unknown): WalkRasterDoc | null {
  if (typeof p !== "object" || p === null) return null;
  const d = p as Record<string, unknown>;
  const { cols, rows, bbox, half, sigma, per, cap, unknown, dtype, data } = d;
  // Wire key is step_m (Python builder); the interface mirrors the wire.
  const step_m = d.step_m;
  if (!Number.isInteger(cols) || !Number.isInteger(rows)) return null;
  const c = cols as number;
  const r = rows as number;
  if (c <= 0 || r <= 0 || c * r > 50_000_000) return null;
  if (typeof bbox !== "object" || bbox === null) return null;
  const b = bbox as Record<string, unknown>;
  for (const k of ["minlon", "minlat", "maxlon", "maxlat"]) {
    if (typeof b[k] !== "number" || !Number.isFinite(b[k])) return null;
  }
  const bb = bbox as BBoxLike;
  if (bb.minlon >= bb.maxlon || bb.minlat >= bb.maxlat) return null;
  for (const n of [step_m, sigma, unknown, per, cap]) {
    if (typeof n !== "number" || !Number.isFinite(n)) return null;
  }
  if (half !== null && (typeof half !== "number" || !Number.isFinite(half))) return null;
  if (dtype !== "uint8" || unknown !== 255) return null;
  if (typeof data !== "string" || data.length === 0) return null;
  return {
    cols: c,
    rows: r,
    bbox: bb,
    step_m: step_m as number,
    half: half as number | null,
    sigma: sigma as number,
    per: per as number,
    cap: cap as number,
    unknown: 255,
    dtype: "uint8",
    data,
  };
}

type FetchImpl = (
  input: string,
) => Promise<{ ok: boolean; json: () => Promise<unknown> }>;

/**
 * Stable cache key for a layer+bbox: bbox rounded to ~1 km so float noise
 * and tiny pans share entries. Generic scheme — future parameters reuse it
 * as `<source>-v1:<id>:<rounded bbox>`.
 */
/**
 * Snap a view bbox outward to a coarse tile grid so nearby views share one
 * cache entry (and one upstream request): panning inside a tile refetches
 * nothing, and tile queries stay small enough to dodge result caps.
 */
export function snapBBoxForCache(bbox: BBoxLike, step = 1): BBoxLike {
  return {
    minlon: Math.floor(bbox.minlon / step) * step,
    minlat: Math.floor(bbox.minlat / step) * step,
    maxlon: Math.ceil(bbox.maxlon / step) * step,
    maxlat: Math.ceil(bbox.maxlat / step) * step,
  };
}

/**
 * View bbox -> upstream query tile: zoomed views snap to shared 1° tiles
 * (small queries, shared cache); large stable views (country default)
 * pass through exact so their existing cache entries keep hitting and
 * are never inflated into heavier queries.
 */
/**
 * Per-view score window for a raster layer (8x metro cells composited
 * server-side). Grid targets ~12 m cells, clamped to 64..512 per side,
 * with a 20% margin covering the heatmap's 15% edge padding. Null on any
 * failure: the caller falls back to the points splat.
 */
export async function fetchWindow(
  layer: LayerId,
  view: BBoxLike,
  fetchImpl: typeof fetch = fetch,
): Promise<WalkRasterDoc | null> {
  try {
    const spanM = (view.maxlon - view.minlon) * 57300;
    const latM = (view.maxlat - view.minlat) * 110570;
    const cols = Math.min(512, Math.max(64, Math.round(spanM / 12)));
    const rows = Math.min(512, Math.max(64, Math.round(latM / 12)));
    const padLon = (view.maxlon - view.minlon) * 0.2;
    const padLat = (view.maxlat - view.minlat) * 0.2;
    const q = new URLSearchParams({
      minlon: String(view.minlon - padLon),
      minlat: String(view.minlat - padLat),
      maxlon: String(view.maxlon + padLon),
      maxlat: String(view.maxlat + padLat),
      cols: String(cols),
      rows: String(rows),
    });
    const res = await fetchImpl(`/api/layers/${layer}/window?${q}`);
    if (!res.ok) return null;
    return cleanRaster(await res.json());
  } catch {
    return null;
  }
}

/** One park polygon (prefilter box, hectares, outer rings). */
export interface ParkOutline {
  b: [number, number, number, number];
  a: number;
  r: number[][][];
}

function isOutline(v: unknown): v is ParkOutline {
  const p = v as Partial<ParkOutline>;
  return (
    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    typeof p?.a === "number" &&
    Number.isFinite(p.a) &&
    Array.isArray(p?.r) &&
    p.r.every(
      (ring) =>
        Array.isArray(ring) &&
        ring.length >= 3 &&
        ring.every(
          (pt) =>
            Array.isArray(pt) &&
            pt.length === 2 &&
            pt.every((n) => typeof n === "number" && Number.isFinite(n)),
        ),
    )
  );
}

/**
 * Park polygon outlines for drawing boundaries on the parks layer.
 * Null on any failure: outlines are a visual aid, never load-bearing.
 */
export async function fetchParkAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<ParkOutline[] | null> {
  try {
    const res = await fetchImpl("/api/layers/parks/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isOutline).map((p) => {
      const o = p as ParkOutline;
      return { b: o.b, a: o.a, r: o.r };
    });
  } catch {
    return null;
  }
}

export function tileForView(bbox: BBoxLike): BBoxLike {
  if (bbox.maxlon - bbox.minlon >= 2 || bbox.maxlat - bbox.minlat >= 2) {
    return bbox;
  }
  return snapBBoxForCache(bbox);
}

export function layerCacheKey(layer: LayerId, bbox: BBoxLike): string {
  const r = (n: number) => n.toFixed(2);
  return `overpass-v1:${layer}:${r(bbox.minlon)},${r(bbox.minlat)},${r(bbox.maxlon)},${r(bbox.maxlat)}`;
}

function cleanTags(p: unknown): Record<string, string> | undefined {
  const tags = (p as Partial<LayerPoint>)?.tags;
  if (typeof tags !== "object" || tags === null || Array.isArray(tags)) return undefined;
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(tags)) {
    if (typeof v === "string") out[k] = v;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

function isPoint(p: unknown): p is LayerPoint {
  const q = p as Partial<LayerPoint>;
  return (
    typeof q?.lat === "number" &&
    typeof q?.lon === "number" &&
    Number.isFinite(q.lat) &&
    Number.isFinite(q.lon)
  );
}

/** Validate one point-like value; shared by the proxy client and the snapshot loader. */
export function cleanTrips(p: unknown): number | undefined {
  const t = (p as Partial<LayerPoint>)?.t;
  if (typeof t !== "number" || !Number.isFinite(t) || t < 0) return undefined;
  return t;
}

function cleanArea(p: unknown): number | undefined {
  const a = (p as Partial<LayerPoint>)?.a;
  if (typeof a !== "number" || !Number.isFinite(a) || a < 0) return undefined;
  return a;
}

export function toPoint(p: unknown): LayerPoint | null {
  if (!isPoint(p)) return null;
  const tags = cleanTags(p);
  const t = cleanTrips(p);
  const a = cleanArea(p);
  const pt: LayerPoint = { lat: p.lat as number, lon: p.lon as number };
  if (tags) pt.tags = tags;
  if (t !== undefined) pt.t = t;
  if (a !== undefined) pt.a = a;
  return pt;
}

/**
 * Layer points via our server proxy (`/api/layers`), which serves the local
 * 2026-09-12 snapshot. Any proxy failure resolves to honestly-labeled
 * demo fallback points — transport errors are never presented as data.
 */
export async function fetchLayerPoints(
  layer: LayerId,
  bbox: BBoxLike,
  fetchImpl: FetchImpl = fetch as unknown as FetchImpl,
): Promise<LayerFetchResult> {
  const fallback = LAYERS.find((l) => l.id === layer)?.fallbackPoints ?? [];
  const toDemo = (): LayerFetchResult => ({
    points: fallback,
    live: false,
    provenance: "demo",
    ageMs: null,
    raster: null,
    distance: "euclidean",
  });
  try {
    const q = new URLSearchParams({
      minlon: String(bbox.minlon),
      minlat: String(bbox.minlat),
      maxlon: String(bbox.maxlon),
      maxlat: String(bbox.maxlat),
    });
    const res = await fetchImpl(`/api/layers/${layer}?${q.toString()}`);
    if (!res.ok) return toDemo();
    const body = (await res.json()) as {
      points?: unknown;
      provenance?: unknown;
      ageMs?: unknown;
      raster?: unknown;
      distance?: unknown;
    };
    if (!Array.isArray(body?.points)) return toDemo();
    const points: LayerPoint[] = [];
    for (const p of body.points) {
      const clean = toPoint(p);
      if (clean) points.push(clean);
    }
    if (body.provenance === "demo") return toDemo();
    if (
      body.provenance !== "live" &&
      body.provenance !== "cache" &&
      body.provenance !== "stale" &&
      body.provenance !== "snapshot" &&
      body.provenance !== "empty"
    ) {
      return toDemo();
    }
    const raster = cleanRaster(body.raster);
    return {
      points,
      live: true,
      provenance: body.provenance,
      ageMs: typeof body.ageMs === "number" ? body.ageMs : null,
      raster,
      distance: raster && body.distance === "walk" ? "walk" : "euclidean",
    };
  } catch {
    return toDemo();
  }
}

/** Sampled goodness grid for the map; [] when there is nothing to score. */
export function layerHexes(
  layer: LayerId,
  points: LayerPoint[],
  bbox: BBoxLike,
  step = 0.1,
): LayerHex[] {
  if (points.length === 0) return [];
  const out: LayerHex[] = [];
  for (let iy = 0, lat = bbox.minlat + step / 2; lat < bbox.maxlat; iy++, lat += step) {
    for (let ix = 0, lon = bbox.minlon + step / 2; lon < bbox.maxlon; ix++, lon += step) {
      const score = goodnessAt(lat, lon, points, layer);
      if (score === null) continue;
      out.push({ h3: `${layer}-${ix}:${iy}`, score_goodness: score, lon, lat });
    }
  }
  return out;
}
