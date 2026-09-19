// Trivial & silly amenity bundle (issue #711). Twelve micro-layers from
// the OSM extract already held — zero new pulls. This file owns ALL
// silly runtime data; shared files (lib/layers.ts, lib/overlays.ts,
// lib/server/snapshot.ts) touch it only through small marked
// `SILLY-HOOK (#711)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// PROBE (2026-09-19, local held extract
// /private/tmp/estonia-260914.osm.pbf, osmium tags-filter + export, no
// network; Tallinn bbox lon 24.45-25.0 / lat 59.35-59.5):
//   amenity=place_of_worship 97, marketplace 27, fountain 88,
//   drinking_water 74, toilets 205, public_bookcase 18;
//   leisure=playground 1874, dog_park 89, sauna 34, pitch 1571,
//   sports_centre 144, fitness_station 319, swimming_area 19;
//   sport=disc_golf 6, swimming 53, skateboard 53;
//   landuse=harbour 5, landfill 4, cemetery 30;
//   emergency=defibrillator 11.
// Every shipped checkbox below is non-empty in Tallinn (counts locked in
// SILLY_PROBE, pinned by test). fallbackPoints are REAL mapped points
// from that probe (never invented): 2-3 central-Tallinn points per
// layer so one map shot carries several at once.
//
// DROPPED (one-line reasons, full verdicts in docs/p4_silly.md):
// * targad pingid — OSM-s pole nutipinkide märgendit (tavalisi
//   amenity=bench pinke on Tallinnas 14 555, aga "tarkust" ei kaardistata).
// * SUve häirikute komposiit (kajakad + sääsed + öömüra + STR) —
//   sääskedel ja STR-il pole kaardistatud allikat, osaline komposiit
//   täisnime all oleks feik-täpsus.
//
// HONESTY (load-bearing): markers-only `pins` layers (fixit #623
// precedent) — dots mark MAPPED objects (hinnang), never quality, never
// completeness (AED: 11 punkti on hõre kaardistus, mitte hõre tegelikkus).
// talisuplus shows mapped swim spots (leisure=swimming_area +
// sport=swimming): dedicated winter-swimming tagging does not exist in
// OSM, so the title/source carry the talvehooldus-teadmata caveat.
// tänavasport is informal street sport ONLY (välijõusaalid + rula +
// discgolf) — register halls/pools live in layers_p4_sport.ts (#607)
// and are never re-listed here.
//
// NAMESPACE (p4osm #480 precedent): paramIds stays EMPTY (P4 numbers are
// not parameters3 ids — the layers.md audit locks 1..500). The linkage
// lives in paramLabel ("P4-…" short tags) + titles + sources.

import type { BBoxLike, BonusSpec, LayerDef, LayerId } from "./layers";

export type SillyLayerId =
  | "kirikukellad"
  | "kajakad"
  | "manguvaljakud"
  | "koertepargid"
  | "saunad"
  | "talisuplus"
  | "tanavasport"
  | "vesi"
  | "wc"
  | "aed"
  | "raamatukapid"
  | "kalmistu";

export const SILLY_LAYER_IDS: SillyLayerId[] = [
  "kirikukellad",
  "kajakad",
  "manguvaljakud",
  "koertepargid",
  "saunad",
  "talisuplus",
  "tanavasport",
  "vesi",
  "wc",
  "aed",
  "raamatukapid",
  "kalmistu",
];

/**
 * Held-extract Tallinn counts per layer (see header probe). Pinned by
 * test so the "non-empty in Tallinn" verdict cannot silently rot.
 */
/**
 * Held-extract vintage the servable pins sidecar is built from
 * (estonia-260914.osm.pbf, scripts/build/batch_silly.py — nodes
 * only, issue #774 option A). Pinned by test.
 */
export const SILLY_VINTAGE = "2026-09-14";

/** Servable sidecar point (lat/lon/slice only, sport #607 precedent). */
export interface SillyPoint {
  lat: number;
  lon: number;
  slice: SillyLayerId;
}

export const SILLY_PROBE = {
  date: "2026-09-19",
  kirikukellad: 97,
  kajakad: 36,
  manguvaljakud: 1874,
  koertepargid: 89,
  saunad: 34,
  talisuplus: 72,
  tanavasport: 378,
  vesi: 162,
  wc: 205,
  aed: 11,
  raamatukapid: 18,
  kalmistu: 30,
} as const;

const SNAP = "kohalik hetktõmmis 2026-09-12 (OSM, hinnang, mitte loendus)";

export const SILLY_LAYERS: LayerDef[] = [
  {
    id: "kirikukellad",
    paramIds: [],
    paramLabel: "P4-kellad",
    title: "Kirikukellad (pühapäevamüra, hinnang)",
    goodLabel: "lilla täpp = kaardistatud kirik lähedal (kellamüra-hinnang)",
    badLabel: "tühi kaart = kirikut lähedal pole (teadmata, mitte vaikne)",
    source: `${SNAP} (amenity=place_of_worship, Tallinnas 97; kellade helitugevust ega heliaegu snapshots pole — kauguse-hinnang, kohapeal kuulata)`,
    fallbackPoints: [
      { lat: 59.43763, lon: 24.71339 }, // Toompea (kaardistatud kirik)
      { lat: 59.44664, lon: 24.7393 }, // Kalamaja (kaardistatud kirik)
    ],
  },
  {
    id: "kajakad",
    paramIds: [],
    paramLabel: "P4-kajakad",
    title: "Kajakad (sadam/turg/prügila, hinnang)",
    goodLabel: "roheline täpp = kajakate meelispaik lähedal (hinnang — prügikast kinni)",
    badLabel: "tühi kaart = sadamat/turgu/prügilat lähedal pole (teadmata)",
    source: `${SNAP} (landuse=harbour 5 + amenity=marketplace 27 + landuse=landfill 4; kajakaid endid ei kaardistata — toidupaiga-hinnang)`,
    fallbackPoints: [
      { lat: 59.44848, lon: 24.75213 }, // Vanasadam (kaardistatud sadam)
      { lat: 59.44093, lon: 24.73317 }, // Keskturg (kaardistatud turg)
      { lat: 59.43046, lon: 24.78311 }, // Pärnamäe prügila (kaardistatud)
    ],
  },
  {
    id: "manguvaljakud",
    paramIds: [],
    paramLabel: "P4-mäng",
    title: "Mänguväljakud (päevakära, hinnang)",
    goodLabel: "roosa täpp = mänguväljak lähedal (lapsed + päevakära-hinnang)",
    badLabel: "tühi kaart = mänguväljakut lähedal pole (teadmata)",
    source: `${SNAP} (leisure=playground, Tallinnas 1874; kellaaegu ega müra snapshots pole — läheduse-hinnang)`,
    fallbackPoints: [
      { lat: 59.44618, lon: 24.69656 }, // Pelgulinn (kaardistatud väljak)
      { lat: 59.45249, lon: 24.71353 }, // Kalamaja (kaardistatud väljak)
    ],
  },
  {
    id: "koertepargid",
    paramIds: [],
    paramLabel: "P4-koerad",
    title: "Koertepargid (hinnang)",
    goodLabel: "sinine täpp = koertepark lähedal (haukumis-hinnang)",
    badLabel: "tühi kaart = koerteparki lähedal pole (teadmata)",
    source: `${SNAP} (leisure=dog_park, Tallinnas 89; lahtiolekut ega koormust snapshots pole — läheduse-hinnang)`,
    fallbackPoints: [
      { lat: 59.36937, lon: 24.74753 }, // Männiku (kaardistatud koertepark)
      { lat: 59.36959, lon: 24.74366 }, // Männiku 2 (kaardistatud koertepark)
    ],
  },
  {
    id: "saunad",
    paramIds: [],
    paramLabel: "P4-saun",
    title: "Avalikud saunad (hinnang)",
    goodLabel: "roosa täpp = avalik saun lähedal (leili-hinnang)",
    badLabel: "tühi kaart = sauna lähedal pole (teadmata)",
    source: `${SNAP} (leisure=sauna, Tallinnas 34; hindu ega aegu snapshots pole — läheduse-hinnang)`,
    fallbackPoints: [
      { lat: 59.4363, lon: 24.76696 }, // Kadriorg (kaardistatud saun)
      { lat: 59.44385, lon: 24.7377 }, // Kesklinn (kaardistatud saun)
    ],
  },
  {
    id: "talisuplus",
    paramIds: [],
    paramLabel: "P4-suplus",
    title: "Talisupluskohad (kaardistatud supluskohad, talvehooldus teadmata)",
    goodLabel: "helesinine täpp = supluskoht lähedal (talvine auk teadmata — küsi kohapeal)",
    badLabel: "tühi kaart = supluskohta lähedal pole (teadmata)",
    source: `${SNAP} (leisure=swimming_area 19 + sport=swimming 53; talisupluse eraldi märgendit OSM-is pole — supluskoha-hinnang, auguhooldus teadmata)`,
    fallbackPoints: [
      { lat: 59.43103, lon: 24.9348 }, // Pirita (kaardistatud suplusala)
      { lat: 59.43366, lon: 24.74702 }, // Kesklinn (kaardistatud ujumine)
    ],
  },
  {
    id: "tanavasport",
    paramIds: [],
    paramLabel: "P4-tänavasport",
    title: "Tänavasport (välijõusaalid/rula/discgolf, hinnang)",
    goodLabel: "heleroheline täpp = välijõusaal/rula/discgolf lähedal (hinnang)",
    badLabel: "tühi kaart = tänavasporti lähedal pole (teadmata)",
    source: `${SNAP} (leisure=fitness_station 319 + sport=skateboard 53 + sport=disc_golf 6; registri saalid/basseinid on layers_p4_sport kihis, siin ainult tänavavorm — läheduse-hinnang)`,
    fallbackPoints: [
      { lat: 59.42306, lon: 24.72949 }, // Kristiine (kaardistatud välijõusaal)
      { lat: 59.41898, lon: 24.74142 }, // Tondi (kaardistatud rula)
      { lat: 59.3802, lon: 24.74727 }, // Nõmme (kaardistatud discgolf)
    ],
  },
  {
    id: "vesi",
    paramIds: [],
    paramLabel: "P4-vesi",
    title: "Suvevesi (purskkaevud/joogivesi, hinnang)",
    goodLabel: "türkiissinine täpp = purskkaev/joogivesi lähedal (jahutus-hinnang)",
    badLabel: "tühi kaart = vett lähedal pole (teadmata)",
    source: `${SNAP} (amenity=fountain 88 + amenity=drinking_water 74; töökorda ega veekvaliteeti snapshots pole — läheduse-hinnang)`,
    fallbackPoints: [
      { lat: 59.43913, lon: 24.75285 }, // Vanalinn (kaardistatud purskkaev)
      { lat: 59.43653, lon: 24.75231 }, // Vanalinn (kaardistatud joogivesi)
    ],
  },
  {
    id: "wc",
    paramIds: [],
    paramLabel: "P4-WC",
    title: "Avalikud WC-d (hinnang)",
    goodLabel: "virsikitäpp = avalik WC lähedal (hädahinnang)",
    badLabel: "tühi kaart = WC-d lähedal pole (teadmata)",
    source: `${SNAP} (amenity=toilets, Tallinnas 205; avatust ega tasulisust snapshots pole — läheduse-hinnang)`,
    fallbackPoints: [
      { lat: 59.43536, lon: 24.73981 }, // Kesklinn (kaardistatud WC)
      { lat: 59.41832, lon: 24.66256 }, // Mustamäe (kaardistatud WC)
    ],
  },
  {
    id: "aed",
    paramIds: [],
    paramLabel: "P4-AED",
    title: "AED defibrillaatorid (hõre kaardistus, hinnang)",
    goodLabel: "punane täpp = defibrillaator lähedal (hinnang — kaardistus hõre)",
    badLabel: "tühi kaart = defibrillaatorit lähedal pole (TEADMATA — 11 punkti on kaardistus, mitte tegelikkus)",
    source: `${SNAP} (emergency=defibrillator, Tallinnas AINULT 11 — hõre kaardistus, mitte hõre tegelikkus; töökorra snapshots pole — läheduse-hinnang, hädaolukorras helista 112)`,
    fallbackPoints: [
      { lat: 59.43901, lon: 24.75633 }, // Kesklinn (kaardistatud AED)
      { lat: 59.40151, lon: 24.69749 }, // Nõmme (kaardistatud AED)
    ],
  },
  {
    id: "raamatukapid",
    paramIds: [],
    paramLabel: "P4-raamat",
    title: "Raamatukapid (hinnang)",
    goodLabel: "lilla täpp = avalik raamatukapp lähedal (lugemis-hinnang)",
    badLabel: "tühi kaart = raamatukappi lähedal pole (teadmata)",
    source: `${SNAP} (amenity=public_bookcase, Tallinnas 18; valikut ega seisu snapshots pole — läheduse-hinnang)`,
    fallbackPoints: [
      { lat: 59.43796, lon: 24.77973 }, // Kadriorg (kaardistatud raamatukapp)
      { lat: 59.44443, lon: 24.72859 }, // Pelgulinn (kaardistatud raamatukapp)
    ],
  },
  {
    id: "kalmistu",
    paramIds: [],
    paramLabel: "P4-kalmistu",
    title: "Kalmistu-vaikus (roheline vaikus, hinnang)",
    goodLabel: "hall täpp = kalmistu lähedal (roheline vaikus-hinnang)",
    badLabel: "tühi kaart = kalmistut lähedal pole (teadmata)",
    source: `${SNAP} (landuse=cemetery, Tallinnas 30; vaikus on hinnang, mitte mõõdetud dB — kohapeal kuulata)`,
    fallbackPoints: [
      { lat: 59.42183, lon: 24.7659 }, // Siselinna (kaardistatud kalmistu)
      { lat: 59.42409, lon: 24.76198 }, // Siselinna 2 (kaardistatud kalmistu)
    ],
  },
];

/**
 * Overpass QL fragments per silly layer (runnable — silly layers ARE
 * OSM data; the app serves the frozen snapshot, never live Overpass).
 */
export const SILLY_TAGS: Record<SillyLayerId, string> = {
  kirikukellad: 'n["amenity"="place_of_worship"];',
  kajakad:
    'n["landuse"="harbour"];n["amenity"="marketplace"];n["landuse"="landfill"];',
  manguvaljakud: 'n["leisure"="playground"];',
  koertepargid: 'n["leisure"="dog_park"];',
  saunad: 'n["leisure"="sauna"];',
  talisuplus: 'n["leisure"="swimming_area"];n["sport"="swimming"];',
  tanavasport:
    'n["leisure"="fitness_station"];n["sport"="skateboard"];n["sport"="disc_golf"];',
  vesi: 'n["amenity"="fountain"];n["amenity"="drinking_water"];',
  wc: 'n["amenity"="toilets"];',
  aed: 'n["emergency"="defibrillator"];',
  raamatukapid: 'n["amenity"="public_bookcase"];',
  kalmistu: 'n["landuse"="cemetery"];',
};

/** Influence radii in km (doorstep window story, fixit #623 precedent). */
export const SILLY_DECAY: Record<SillyLayerId, number> = {
  kirikukellad: 0.5,
  kajakad: 0.5,
  manguvaljakud: 0.5,
  koertepargid: 0.5,
  saunad: 0.5,
  talisuplus: 0.5,
  tanavasport: 0.5,
  vesi: 0.5,
  wc: 0.5,
  aed: 0.5,
  raamatukapid: 0.5,
  kalmistu: 0.5,
};

/** Raster master filenames (intentionally never built — SILLY_NO_RASTER). */
export const SILLY_RASTER_FILE: Record<SillyLayerId, string> = {
  kirikukellad: "silly-kirikukellad-pins-raster.json",
  kajakad: "silly-kajakad-pins-raster.json",
  manguvaljakud: "silly-manguvaljakud-pins-raster.json",
  koertepargid: "silly-koertepargid-pins-raster.json",
  saunad: "silly-saunad-pins-raster.json",
  talisuplus: "silly-talisuplus-pins-raster.json",
  tanavasport: "silly-tanavasport-pins-raster.json",
  vesi: "silly-vesi-pins-raster.json",
  wc: "silly-wc-pins-raster.json",
  aed: "silly-aed-pins-raster.json",
  raamatukapid: "silly-raamatukapid-pins-raster.json",
  kalmistu: "silly-kalmistu-pins-raster.json",
};

/**
 * NO raster masters (documented): markers-only layers have no field to
 * stamp (fixit #623 precedent). Absent files degrade windows to null.
 */
export const SILLY_NO_RASTER = true;

/** Metro master prefixes (intentionally never built — SILLY_NO_METRO). */
export const SILLY_METRO_PREFIX: Record<SillyLayerId, string> = {
  kirikukellad: "silly-kirikukellad-metro",
  kajakad: "silly-kajakad-metro",
  manguvaljakud: "silly-manguvaljakud-metro",
  koertepargid: "silly-koertepargid-metro",
  saunad: "silly-saunad-metro",
  talisuplus: "silly-talisuplus-metro",
  tanavasport: "silly-tanavasport-metro",
  vesi: "silly-vesi-metro",
  wc: "silly-wc-metro",
  aed: "silly-aed-metro",
  raamatukapid: "silly-raamatukapid-metro",
  kalmistu: "silly-kalmistu-metro",
};

/**
 * NO metro masters (documented): overlay-only pins (paaste #493
 * precedent) — absent files fall back to county cleanly.
 */
export const SILLY_NO_METRO = true;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isSillyLayerId(layer: LayerId): layer is SillyLayerId {
  return (SILLY_LAYER_IDS as string[]).includes(layer);
}

/** Marker-only spec for silly layers (called from the bonusSpecFor hook). */
export function sillyBonusSpecFor(layer: SillyLayerId): BonusSpec {
  void layer;
  return { kind: "pins" };
}

/** Points within the hard doorstep radius, nearest first (pure). */
export function sillyNearby(
  lat: number,
  lon: number,
  points: { lat: number; lon: number }[],
  radiusM = 500,
): { lat: number; lon: number; distM: number }[] {
  const out: { lat: number; lon: number; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM =
      Math.hypot((p.lon - lon) * 57.29, (p.lat - lat) * 110.57) * 1000;
    if (distM <= radiusM) out.push({ lat: p.lat, lon: p.lon, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * BBox filter for demo/serve points (pure, fixit fixitPointsIn
 * shape). The optional slice serves one layer from the shared
 * sidecar (sport sportPointsIn shape); omitted keeps every slice
 * (demo fallback path). Wire shape stays lat/lon only.
 */
export function sillyPointsIn(
  points: ({ lat: number; lon: number } & { slice?: string })[],
  bbox: BBoxLike,
  slice?: string,
): { lat: number; lon: number }[] {
  return points
    .filter(
      (p) =>
        Number.isFinite(p.lat) &&
        Number.isFinite(p.lon) &&
        (slice === undefined || p.slice === slice) &&
        p.lon >= bbox.minlon &&
        p.lon <= bbox.maxlon &&
        p.lat >= bbox.minlat &&
        p.lat <= bbox.maxlat,
    )
    .map((p) => ({ lat: p.lat, lon: p.lon }));
}

/**
 * Snapshot status line for served silly points (issue #774 option
 * A): names the open-mapping extract + vintage, never a count claim
 * beyond the served points, never a failure. Pure (pinned by test).
 */
export function sillySnapshotStatus(pointCount: number): string {
  return `OSM väljavõte (Eesti ${SILLY_VINTAGE}, hinnang) · ${pointCount} punkti`;
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const SILLY_HOOK =
  "SILLY-HOOK (#711): silly bundle wired into layers/overlays/snapshot; twelve markers-only pins layers from the held OSM extract, zero new pulls.";

/**
 * Demo-by-design status line (issue #774). Silly layers have no
 * points sidecar BY DECISION (docs/p4_silly.md) and always render
 * through the demo fallback — so the generic "live ebaõnnestus"
 * (live failed) label reads as breakage. This names the state
 * honestly instead: mapped sample points, never a count, never a
 * failure. Pure (pinned by test).
 */
export function sillyDemoStatus(pointCount: number): string {
  return `DEMO-näidis (näidispunktid, mitte loendus) · ${pointCount} punkti`;
}
