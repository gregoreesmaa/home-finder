// Temporal class of every map layer (issue #801: no realtime layers).
//
// Rule: no layer may show realtime/momentary state. Everything on the
// map is one of:
//
//   "aggregate"    (A) Pre-pulled aggregate computed over an observation
//                      window (noise maps, outage 28-day reliability,
//                      DATEX windowed levels, TomTom sheds). The window
//                      + vintage is named on the layer.
//   "static"       (B) Relatively static info that barely moves (parks,
//                      grocery stores, OSM snapshot extracts, registers).
//   "pole-realtime" (C) Realtime at the source, lawful ONLY aggregated
//                      via the pole server over time, with the
//                      observation log append-only (retention = forever).
//                      The browser NEVER fetches a live source directly:
//                      browser data paths are same-origin `/api/*` plus
//                      the first-party scoring backend only (pinned by
//                      layer_temporal.test.ts).
//
// First concrete class-C consumer (criterion 4, named — no follow-up
// issue needed): bus locations -> congestion estimate, i.e. the
// delay-* corridor bands (issue #629): Tallinna GPS bus tracks
// aggregated per corridor-hour on the pole into typical-speed
// factors. Window + metric live in CLASS_C_SOURCES below.
//
// Judgment calls (documented for the reviewer):
// - senscom/ohuseire are B, not C: the map paints witness/station
//   LOCATIONS from dated extracts ("never live (no network in the map
//   path)"), never live readings. If readings ever reach the map they
//   must arrive as a C pole aggregation.
// - transit/gtfsstops/busmesh are B, not A/C: GTFS STATIC carries
//   schedules, never occupancy or reliability (busmesh header); the
//   map shows schedule-derived frequency/transfer richness from a
//   vintaged snapshot (TLT GTFS 2026-09-11), not observations.
// - gbfs is C (not B) although honest-empty: bike-share availability
//   is realtime at the source, so its only lawful future is a pole
//   time-aggregation. Wiring it as static pins would bless live data.
// - harbour is A (not C): the AIS half is ANNUAL 2024 counts
//   (HARBOUR_VINTAGE), a pre-pulled aggregate, not live positions.
//
// This module imports ./layers ONLY as types: no runtime cycle
// (layers.ts never imports here).

import type { LayerId } from "./layers";

export type LayerTemporalClass = "aggregate" | "static" | "pole-realtime";

/** Class A: pre-pulled aggregates (window + vintage named per layer). */
export const AGGREGATE_LAYER_IDS: LayerId[] = [
  "datex-restrictions",
  "datex-srti",
  "datex-weather",
  "datex-counters",
  "datex-cameras",
  "datex-truckpark",
  "shed-15-peak",
  "shed-15-offpeak",
  "shed-30-peak",
  "shed-30-offpeak",
  "incidents",
  "outage",
  "noise",
  "harbour",
  "ookla_fixed",
  "ookla_mobile",
  "kliima_frost",
  "kliima_wet",
  "kovmigr",
  "kovehit",
  "kovfisc",
  "kovkasv",
  "kovkaive",
  "kovedas",
  "kovkiirus",
  "asumedia",
  "tervise",
  "accblack",
  "fixit",
  "viirs",
];

/** Class C: pole-aggregated realtime (browser-direct live fetch banned). */
export const POLE_REALTIME_LAYER_IDS: LayerId[] = [
  "delay-morning",
  "delay-midday",
  "delay-evening",
  "delay-offpeak",
  "delay-worst",
  "gbfs",
];

/** Class B: relatively static info (registers, snapshots, extracts). */
export const STATIC_LAYER_IDS: LayerId[] = [
  "parks",
  "transit",
  "schools",
  "walkability",
  "pedinfra",
  "cycling",
  "grocery",
  "healthcare",
  "pets",
  "community",
  "culture",
  "nightlife",
  "libraries",
  "brownsoil",
  "oiltank",
  "agriland",
  "agrifield",
  "wildcorr",
  "vectorhabitat",
  "industprox",
  "odorsrc",
  "safety",
  "emergency",
  "hydrants",
  "evac",
  "dispatch",
  "mailbox",
  "postal",
  "alley",
  "trailprivacy",
  "plaster",
  "antiques",
  "woodfire",
  "schoolbus",
  "recspecial",
  "medspecial",
  "worship",
  "forage",
  "droneclear",
  "droneviab",
  "rentbleed",
  "heritage",
  "liftproxy",
  "drainage",
  "moorage",
  "shoredist",
  "wildfire",
  "vernalpool",
  "surgeroad",
  "slidebuf",
  "windtunnel",
  "saltspray",
  "gardens",
  "buildout",
  "strsat",
  "ehitus",
  "korterstock",
  "commbleed",
  "windsolar",
  "viewshed",
  "equestrian",
  "upcycle",
  "skyview",
  "dayopen",
  "glassglare",
  "fishbowl",
  "mossrisk",
  "daylight",
  "compost",
  "gritbin",
  "leafdrop",
  "lawncare",
  "privroad",
  "water",
  "waste",
  "fiber",
  "mobile",
  "dailyshop",
  "activity",
  "herd",
  "thirdplace",
  "taxidoor",
  "lastshop",
  "gtfsstops",
  "busmesh",
  "busmesh-sat",
  "busmesh-sun",
  "roadsafety",
  "senscom",
  "parking",
  "floodzone",
  "blockwalk",
  "darkness",
  "maaparcel",
  "eeliskaitse",
  "eelisniit",
  "eelisraie",
  "planktpr",
  "paaste",
  "skis",
  "harno",
  "sport_hall",
  "sport_field",
  "sport_pool",
  "ehis_school",
  "ehis_kindergarten",
  "ehis_hobby",
  "medre_gp",
  "medre_clinic",
  "ohuseire",
  "poi_library",
  "poi_post",
  "poi_pharmacy",
  "seveso",
  "stateland",
  "quarry",
  "maaparandus",
  "soil",
  "etak",
  "relief",
  "canopy",
  "buildings",
  "density",
  "forest",
  "kpo",
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

/** Temporal class per layer id (built from the three pinned lists). */
export const LAYER_TEMPORAL: Record<LayerId, LayerTemporalClass> = {
  ...(Object.fromEntries(
    AGGREGATE_LAYER_IDS.map((id) => [id, "aggregate"]),
  ) as Record<LayerId, LayerTemporalClass>),
  ...(Object.fromEntries(
    STATIC_LAYER_IDS.map((id) => [id, "static"]),
  ) as Record<LayerId, LayerTemporalClass>),
  ...(Object.fromEntries(
    POLE_REALTIME_LAYER_IDS.map((id) => [id, "pole-realtime"]),
  ) as Record<LayerId, LayerTemporalClass>),
};

/**
 * Class-A window/vintage note per layer (user-visible wording lives on
 * the layer defs + WINDOW_* constants — DATEX_WINDOW_ET,
 * SHED_WINDOW_ET, INCIDENTS_WINDOW_ET, OUTAGE_WINDOW_ET — this record
 * is the audit trail pointing at them).
 */
export const AGGREGATE_WINDOW_NOTE: Partial<Record<LayerId, string>> = {
  "datex-restrictions": "pole aggregate-window table /v1/datex-restrictions (DATEX_WINDOW_ET per-feed window)",
  "datex-srti": "pole aggregate-window table /v1/datex-srti (DATEX_WINDOW_ET per-feed window)",
  "datex-weather": "pole aggregate-window table /v1/datex-weather (DATEX_WINDOW_ET per-feed window)",
  "datex-counters": "pole aggregate-window table /v1/datex-counters (DATEX_WINDOW_ET per-feed window)",
  "datex-cameras": "pole aggregate-window table /v1/datex-cameras (DATEX_WINDOW_ET per-feed window)",
  "datex-truckpark": "pole aggregate-window table /v1/datex-truckpark (DATEX_WINDOW_ET per-feed window)",
  "shed-15-peak": "7-day window, weekly pull (SHED_WINDOW_ET)",
  "shed-15-offpeak": "7-day window, weekly pull (SHED_WINDOW_ET)",
  "shed-30-peak": "7-day window, weekly pull (SHED_WINDOW_ET)",
  "shed-30-offpeak": "7-day window, weekly pull (SHED_WINDOW_ET)",
  "incidents": "6 h window, operator cache (INCIDENTS_WINDOW_ET)",
  "outage": "5-min pull, 28-day observed-reliability window (OUTAGE_WINDOW_ET + OUTAGE_RELIABILITY_WINDOW_DAYS; log append-only per #801)",
  "noise": "myrakaart Lden/Lnight statutory bands (multi-year strategic map)",
  "harbour": "AIS 2024 annual pleasure counts + sadamaregister snapshot (HARBOUR_VINTAGE 2024)",
  "ookla_fixed": "Ookla quarterly tiles (quarter vintage on the tile)",
  "ookla_mobile": "Ookla quarterly tiles (quarter vintage on the tile)",
  "kliima_frost": "Keskkonnaagentuur 1991-2020 climate normals",
  "kliima_wet": "Keskkonnaagentuur 1991-2020 climate normals",
  "kovmigr": "Statamet RVR02 2025 net migration (annual)",
  "kovehit": "Statamet EH44U 2025 completions (annual)",
  "kovfisc": "Statamet RR300 2025 operating margin (annual)",
  "kovkasv": "MARU YoY appreciation (quarterly)",
  "kovkaive": "MARU quarterly deal count (quarterly)",
  "kovedas": "MARU resale composite (quarterly)",
  "kovkiirus": "MARU deal-velocity QoQ (quarterly)",
  "asumedia": "own-listing-snapshot per-asum medians (snapshot vintage)",
  "tervise": "Terviseamet yearly XML, 2025-2026 season samples to quality bands",
  "accblack": "multi-year accident blackspot window (300 m, BLACKSPOT_WINDOW_M)",
  "fixit": "rolling ~19-day report-pin window (annateada endpoint)",
  "viirs": "VIIRS night-lights composite (vintage 2016 stamped)",
};

export interface PoleRealtimeSource {
  /** Observation window the map aggregates (never momentary). */
  window: string;
  /** Metric computed over the window. */
  metric: string;
  /** Pole harvest feeding it (live source named honestly). */
  source: string;
  /** Consumer status: live vs unwired. */
  status: string;
}

/**
 * Class-C sources: FIRST consumer is delay-* = bus locations ->
 * congestion estimate (issue #801 proposal, already shipped as #629:
 * Tallinna GPS bus tracks aggregated per corridor-hour into
 * typical-speed factors; the map says "tavaline, mitte reaalajas").
 * gbfs is the unwired slot: realtime at the source, honest-empty
 * until a verified feed arrives, lawful only via pole aggregation.
 */
export const CLASS_C_SOURCES: Partial<Record<LayerId, PoleRealtimeSource>> = {
  "delay-morning": {
    window: "corridor-hour band: hommikune tipp 7-9",
    metric: "typical-speed factor (free/typical; bands <=1.1/1.3/1.6; n>=20 probes per corridor-hour else mõõtmata)",
    source: "Tallinna GPS bus tracks (keyless gps.txt pole pulls) + TLT GTFS shapes",
    status: "live consumer (bus locations -> congestion estimate)",
  },
  "delay-midday": {
    window: "corridor-hour band: keskpäev 10-15",
    metric: "typical-speed factor (free/typical; bands <=1.1/1.3/1.6; n>=20 probes per corridor-hour else mõõtmata)",
    source: "Tallinna GPS bus tracks (keyless gps.txt pole pulls) + TLT GTFS shapes",
    status: "live consumer (bus locations -> congestion estimate)",
  },
  "delay-evening": {
    window: "corridor-hour band: õhtune tipp 16-18",
    metric: "typical-speed factor (free/typical; bands <=1.1/1.3/1.6; n>=20 probes per corridor-hour else mõõtmata)",
    source: "Tallinna GPS bus tracks (keyless gps.txt pole pulls) + TLT GTFS shapes",
    status: "live consumer (bus locations -> congestion estimate)",
  },
  "delay-offpeak": {
    window: "corridor-hour band: muu (free-flow anchor, factor 1.0 where measured)",
    metric: "off-peak median speed per corridor (free-flow baseline; n>=20 else mõõtmata)",
    source: "Tallinna GPS bus tracks (keyless gps.txt pole pulls) + TLT GTFS shapes",
    status: "live consumer (bus locations -> congestion estimate)",
  },
  "delay-worst": {
    window: "max over the three peak bands per corridor (offpeak excluded)",
    metric: "worst peak typical-speed factor per corridor",
    source: "Tallinna GPS bus tracks (keyless gps.txt pole pulls) + TLT GTFS shapes",
    status: "live consumer (bus locations -> congestion estimate)",
  },
  gbfs: {
    window: "none yet (unwired)",
    metric: "station availability may only arrive as a pole time-aggregation",
    source: "no verified keyless GBFS feed for Tallinn/Tartu (verdict 2026-09-19)",
    status: "unwired, honest-empty (EI OLE on every surface)",
  },
};
