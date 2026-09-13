// OSM daily-life overlay (issue #482): six honest OSM-derived PROXY map
// layers for the P4 grocery/culture/evening-place/doorstep/fringe set:
// P4-027 grocery, P4-032 activity density, P4-044 herd (culture
// taste-match), P4-045 third places, P4-049 taxi/guest doorstep,
// P4-061 last-shop fringe watch. Scorer dims live in
// services/scoring/dims_p4_osm.py (issues #280/#354); this file is the
// map side those dims never had.
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100 count kernels (score = 100*S/(S+half), area-kind like
// grocery/healthcare/B1/B10C); unknown stays 255 (renders red). This
// file owns ALL OSMDAILY runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts, app/layers/page.tsx) touch
// it only through small marked `OSMDAILY-HOOK (#482)` blocks, so the
// sibling batches stay disjoint. This module imports ./layers ONLY as
// types (BonusSpec, LayerDef): no runtime cycle (layers.ts imports
// values from here).
//
// HONESTY (load-bearing): these are MAPPED-feature counts, never
// measured commerce or registry data. Titles, legends and sources say
// "hinnang" (estimate) and "kaardistatud" (mapped); lastshop says
// "hoiatus" (warning): a red fringe cell is absence-of-mapped-shops,
// never a measured closure. Scorer-side caps (never 100 on presence:
// P4-027 <=85, P4-032 <=75, P4-044 <=75, P4-045 <=85, P4-049 <=80,
// P4-061 <=85; absences 40/40/55/45/55/35-warning) live in the dims,
// not on this map: the map shows 0..100 density, so it runs HOTTER
// than the scorer in dense clusters and REDDER than the scorer's
// absence floor in sparse zones — by construction, stated here so the
// reviewer sees the gap. Evening hours (opening_hours), delivery
// windows (Barbora/Selver), ride/delivery coverage (Wolt/Bolt),
// closure calendars and GTFS diffs are NOT in the snapshot: unknown
// hours are stated unknown, never closed.
//
// NAMESPACE (judgment call, AGENTS.md 7.5): paramIds stays EMPTY. P4
// numbers (P4-027 etc.) live in the parameters4 namespace, while
// paramIds feeds the parameters3 audit (docs/layers.md: every number
// 1..500 has exactly one verdict — e.g. 44 is korterstock, 61 is
// industprox). Claiming bare 27/32/44/45/49/61 would corrupt that
// audit. The P4 linkage lives in OSMDAILY_P4 + the titles instead
// (pinned by test), and app/layers/page.tsx skips the "(p…)" suffix
// for empty paramIds (zero behaviour change for existing layers).
//
// Tag verification (2026-09-13, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
//     'nwr/shop=supermarket,convenience,greengrocer,general,bakery' \
//     'nwr/craft=bakery,confectionery' \
//     'nwr/amenity=pharmacy,atm,bank,cafe,bar,pub,restaurant,library' \
//     'nwr/leisure=sauna' 'nwr/tourism=gallery,museum,arts_centre' \
//     'nwr/entrance' -o /tmp/hf-482-daily.pbf --overwrite
//   osmium export /tmp/hf-482-daily.pbf -o /tmp/hf-482-daily.geojson
// Tagged-object counts (-R: untagged member nodes of matched ways
// excluded — raw tags-filter counts run 2-5x higher on way-mapped tags
// and are reported in docs/p4_osm.md, NOT here):
//   daily shops 483; bakery 61 + craft 7; pharmacy 204; money 258
//   (atm 224 + bank ~39); thirdplace amenities 1308; sauna 35;
//   culture 153 (museum 107 + gallery 46); entrances 4973 (pure nodes:
//   main 705 + yes 1124 + staircase 2782 + home 122 + service 112 +
//   shop 56 + secondary 14 + the rest emergency/exit/garage, which the
//   scorer does NOT consume).
// Derived (deduped ~20 m centroids, 2026-09-13 build): dailyshop 477
// (283 Tallinn window), activity 1840 (1362), herd 149 (105),
// thirdplace 1211 (969), taxidoor 4085 (3469), lastshop 840 (545).
//
// Calibration (judgment calls, documented for the reviewer): all six
// are area-kind count kernels (Gaussian sigma below, score
// 100*S/(S+half)). Sigmas mirror the scorer radii where map-readable
// (activity 0.4 = 400 m, taxidoor 0.3 = 300 m); herd keeps the full
// 1.0 km grid tier, the rest use 0.5. Halves locked from a 2026-09-13
// probe (Viru / Mustamae / Nomme / rural S, same sigma):
//   dailyshop 8 (18.4/9.2/3.6/0 -> 70/53/31/unknown),
//   activity 12 (277/22/3.8/0 -> 96/65/24/unknown; tames old-town),
//   herd 3 (70.5/0.4/0.3/0 -> 96/12/9/unknown; sparse by nature),
//   thirdplace 12 (291/17.5/1.6/0 -> 96/59/12/unknown),
//   taxidoor 30 (37.8/237.9/2.7/0 -> 56/89/8/unknown; panel stairwells
//     saturate — the proxy reads stairwell density, honestly stated),
//   lastshop 12 (55/22/4.8/0 -> 82/65/29/unknown).
// Rasters are follow-up (none built): the route serves these layers
// from derived-*.json via the honest Euclidean fallback until then.

import type { BonusSpec, LayerDef } from "./layers";

export type OsmdailyLayerId =
  | "dailyshop"
  | "activity"
  | "herd"
  | "thirdplace"
  | "taxidoor"
  | "lastshop";

export const OSMDAILY_LAYER_IDS: OsmdailyLayerId[] = [
  "dailyshop",
  "activity",
  "herd",
  "thirdplace",
  "taxidoor",
  "lastshop",
];

/** parameters4 number per OSM-daily layer (traceability, NOT paramIds). */
export const OSMDAILY_P4: Record<OsmdailyLayerId, string> = {
  dailyshop: "P4-027",
  activity: "P4-032",
  herd: "P4-044",
  thirdplace: "P4-045",
  taxidoor: "P4-049",
  lastshop: "P4-061",
};

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const OSMDAILY_DEFS: LayerDef[] = [
  {
    id: "dailyshop",
    paramIds: [],
    title: "Igapäevapoed (P4-027 proksi, hinnang)",
    goodLabel: "roheline = toidupood lähedal (kaardistatud, hinnang)",
    badLabel: "punane = kaardistatud pood kaugel või teadmata (hinnang)",
    source:
      `${SNAP} (kaardistatud 483 toidupoodi: supermarket/kauplus/köögivili/universaal — PROKSI-hinnang läheduse järgi; lahtiolekuajad, tarneaknad ja Wolt/Bolt katvus snapshots puuduvad — see EI OLE tarnegarantii)`,
    fallbackPoints: [
      { lat: 59.4373, lon: 24.7513 }, // Viru (poodide keskus)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (kaardistatud poodidest kaugel)
    ],
  },
  {
    id: "activity",
    paramIds: [],
    title: "Õhtune kasutus (P4-032 proksi, hinnang)",
    goodLabel: "roheline = õhtuse kasutusega kohti tihedalt (hinnang)",
    badLabel: "punane = kasutuskohti hõredalt või teadmata (hinnang)",
    source:
      `${SNAP} (kaardistatud 1840 õhtuse kasutusega kohta 400 m raadius: kohvikud, söögikohad, poed, kultuur — KASUTUS-hinnang, mitte turvalisus; PPA/Päästeamet teadlikult kasutamata — tihedus ei ole ohutus)`,
    fallbackPoints: [
      { lat: 59.4366, lon: 24.7547 }, // Vanalinn (tihe kasutus)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hõre kasutus)
    ],
  },
  {
    id: "herd",
    paramIds: [],
    title: "Kultuuriseltskond (P4-044 proksi, hinnang)",
    goodLabel: "roheline = galerii/muuseum lähedal (maitse-hinnang)",
    badLabel: "punane = kaardistatud kultuuri lähedal pole (hinnang)",
    source:
      `${SNAP} (kaardistatud 153 galeriid/muuseumi/kunstikeskust — hõre, aga päris; MAITSE-hinnang, mitte väärtushinnang; REL2021 ametite ruudustikku snapshots pole; tihedus ei ole gentrifikatsiooni tõestus)`,
    fallbackPoints: [
      { lat: 59.4366, lon: 24.7547 }, // Vanalinn (kultuuritihe)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (kaardistatud kultuurist kaugel)
    ],
  },
  {
    id: "thirdplace",
    paramIds: [],
    title: "Kolmandad kohad (P4-045 proksi, hinnang)",
    goodLabel: "roheline = kohvik/saun/raamatukogu lähedal (hinnang)",
    badLabel: "punane = kolmandaid kohti lähedal pole (hinnang)",
    source:
      `${SNAP} (kaardistatud 1308 kohvikut/baari/pub/söögikohta/raamatukogu + 35 sauna — KUULUVUS-hinnang; õhtused lahtiolekuajad snapshots puuduvad — teadmata, mitte suletud)`,
    fallbackPoints: [
      { lat: 59.4369, lon: 24.7526 }, // Vanalinn (kolmandaid kohti tihedalt)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hõredalt)
    ],
  },
  {
    id: "taxidoor",
    paramIds: [],
    title: "Sissepääsud (P4-049 proksi, hinnang)",
    goodLabel: "roheline = sissepääs kaardistatud lähedal (nõrk hea-märk, hinnang)",
    badLabel: "punane = sissepääsu lähedal kaardistamata (hinnang)",
    source:
      `${SNAP} (kaardistatud 4973 sissepääsu, sh 2782 trepikoja ust — paneelrajoonide trepikojad küllastavad; LEITAVUSE-hinnang (nõrk hea-märk), mitte külalisparkimise garantii — parkimisreegleid snapshots pole)`,
    fallbackPoints: [
      { lat: 59.4362, lon: 24.7546 }, // Vanalinn (sissepääsud tihedalt)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hõredalt kaardistatud)
    ],
  },
  {
    id: "lastshop",
    paramIds: [],
    title: "Viimase poe hoiatus (P4-061 proksi, hinnang)",
    goodLabel: "roheline = pood/apteek/sularaha lähedal (hinnang)",
    badLabel: "punane = HOIATUS: kaardistatud poodi/apteeki/sularaha 1,5 km raadiuses pole",
    source:
      `${SNAP} (kaardistatud 840 poodi/apteeki/pangaautomaati — ÄÄREALA elujõu-hoiatus: punane on kaardistuslünga hoiatus (35), mitte mõõdetud sulgemine; sulgemiskalendrit ja GTFS diffi snapshots pole)`,
    fallbackPoints: [
      { lat: 59.4363, lon: 24.7546 }, // Vanalinn (teenused lähedal)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hoiatustsoon)
    ],
  },
];

/**
 * Overpass QL fragments per OSM-daily layer (document the source tags;
 * the app serves the frozen snapshot, never live Overpass). n/ shape:
 * the shared overpassQueryFor() rewrites n[ to nwr/ (PR #118).
 */
export const OSMDAILY_TAGS: Record<OsmdailyLayerId, string> = {
  dailyshop: 'n["shop"~"supermarket|convenience|greengrocer|general"];',
  activity:
    'n["amenity"~"cafe|bar|pub|restaurant|library"];n["leisure"="sauna"];' +
    'n["shop"~"supermarket|convenience|greengrocer|general|bakery"];' +
    'n["craft"~"bakery|confectionery"];n["tourism"~"gallery|museum|arts_centre"];',
  herd: 'n["tourism"~"gallery|museum|arts_centre"];',
  thirdplace: 'n["amenity"~"cafe|bar|pub|restaurant|library"];n["leisure"="sauna"];',
  taxidoor: 'n["entrance"~"main|yes|home|shop|service|secondary|staircase"];',
  lastshop:
    'n["shop"~"supermarket|convenience|greengrocer|general"];' +
    'n["amenity"~"pharmacy|atm|bank"];',
};

/** Influence radii in km (== walk-kernel sigma == Euclidean fallback decay). */
export const OSMDAILY_DECAY: Record<OsmdailyLayerId, number> = {
  dailyshop: 0.5,
  activity: 0.4,
  herd: 1.0,
  thirdplace: 0.5,
  taxidoor: 0.3,
  lastshop: 0.5,
};

/**
 * Saturation midpoints, locked 2026-09-13 from the probe in the module
 * header (unweighted count kernels, grocery/B1 shape 100*S/(S+half)).
 */
export const OSMDAILY_BONUS: Record<OsmdailyLayerId, BonusSpec> = {
  dailyshop: { kind: "area", half: 8 },
  activity: { kind: "area", half: 12 },
  herd: { kind: "area", half: 3 },
  thirdplace: { kind: "area", half: 12 },
  taxidoor: { kind: "area", half: 30 },
  lastshop: { kind: "area", half: 12 },
};

/**
 * OSM-daily bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for all other layers (their switch/hooks handle them).
 */
export function bonusSpecForOsmdaily(layer: string): BonusSpec | undefined {
  return (OSMDAILY_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master filenames next to the base masters (follow-up builds). */
export const OSMDAILY_RASTER_FILE: Record<OsmdailyLayerId, string> = {
  dailyshop: "dailyshop-walk-raster.json",
  activity: "activity-walk-raster.json",
  herd: "herd-walk-raster.json",
  thirdplace: "thirdplace-walk-raster.json",
  taxidoor: "taxidoor-walk-raster.json",
  lastshop: "lastshop-walk-raster.json",
};

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const OSMDAILY_HOOK =
  "OSMDAILY-HOOK (#482): dailyshop/activity/herd/thirdplace/taxidoor/lastshop wired into layers/overlays/snapshot; P4 linkage in OSMDAILY_P4, paramIds stays empty (parameters4 namespace).";
