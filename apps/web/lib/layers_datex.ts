// TarkTee DATEX overlays (issue #763, harvesters #681–#686): road
// restrictions, SRTI, weather stations, counters, cameras, truck parks.
//
// Data reads POLE AGGREGATE-WINDOW TABLES (/v1/datex-*, never committed
// sidecars — the SHORT-TERM CACHE ONLY verdict gates all DATEX work,
// see docs/datex_restrictions.md section 0). The window is the
// contract (issue #783: no momentary state — every live-descended layer
// names its window + vintage): the route enforces per-feed TTLs against
// X-Pole-Built-At and degrades past them (labeled demo for point
// layers, honestly-empty for the geometry-less feeds). Pulls stay
// pole-only (server-side fetchPoleTable; never browser-direct).
//
// GEOMETRY HONESTY (load-bearing): only feeds whose rows carry
// measured lat/lon plot points (weather/counters/cameras/truckpark).
// restrictions + srti rows have NO coordinates by format — those layers
// register honestly-empty (accblack #490 precedent): the route still
// reads the pole table (liveness-gated: pole down reads demo, pole up
// reads empty+snapshot), but no point is ever placed without geometry.
// Cameras are URL-only: image binaries never touch the map (points
// carry no image_url).
//
// Markers only (pins spec — no score field is painted for these
// layers, by design). Shared files touch this module only through
// marked `DATEX-HOOK (#763)` blocks.
// #807 NO-SCORE DECISION (2026-09-20): restrictions/srti have NO
// geometry by format (cannot join spatially — accblack precedent);
// weather/counters/cameras/truckpark DO plot, but station proximity
// measures measurement availability, not place goodness (a counter
// marks a counted road, a camera a watched junction — scoring
// near-a-sensor as good/bad would fake a quality gradient). Specs
// stay `pins` for all six feeds.

import type { BonusSpec, LayerDef } from "./layers";

export type DatexLayerId =
  | "datex-restrictions"
  | "datex-srti"
  | "datex-weather"
  | "datex-counters"
  | "datex-cameras"
  | "datex-truckpark";

export const DATEX_LAYER_IDS: DatexLayerId[] = [
  "datex-restrictions",
  "datex-srti",
  "datex-weather",
  "datex-counters",
  "datex-cameras",
  "datex-truckpark",
];

/** Pole dataset name per layer (pole/api.py DATASETS keys). */
export const DATEX_POLE_DATASET: Record<DatexLayerId, string> = {
  "datex-restrictions": "datex-restrictions",
  "datex-srti": "datex-srti",
  "datex-weather": "datex-weather",
  "datex-counters": "datex-counters",
  "datex-cameras": "datex-cameras",
  "datex-truckpark": "datex-truckpark",
};

/**
 * Freshness TTL per layer, seconds (parity with the harvesters —
 * pinned in test): restrictions 24h, srti 6h, weather/counters/
 * cameras 1h, truckpark 30d. A pole table older than this is stale
 * data, never served (outage #729 rule).
 */
export const DATEX_TTL_S: Record<DatexLayerId, number> = {
  "datex-restrictions": 24 * 3600,
  "datex-srti": 6 * 3600,
  "datex-weather": 1 * 3600,
  "datex-counters": 1 * 3600,
  "datex-cameras": 1 * 3600,
  "datex-truckpark": 30 * 24 * 3600,
};

/**
 * Observation window per feed, user-visible (issue #783: each
 * live-descended layer names its window + vintage). The window is the
 * pull cadence + serve TTL in parity: restrictions pulled daily (04:17
 * cron) served 24h; srti pulled every 6h served 6h; weather/counters/
 * cameras pulled hourly served 1h; truckpark pulled monthly (3rd 05:23
 * cron) served 30d. Keys mirror DATEX_TTL_S (pinned by test).
 */
export const DATEX_WINDOW_ET: Record<DatexLayerId, string> = {
  "datex-restrictions": "24 h aken, öine tõmme",
  "datex-srti": "6 h aken",
  "datex-weather": "1 h aken, tunni tõmme",
  "datex-counters": "1 h aken, tunni tõmme",
  "datex-cameras": "1 h aken, tunni tõmme",
  "datex-truckpark": "30-päeva aken, kuutõmme",
};

const DATEX_ET: Record<
  DatexLayerId,
  { title: string; label: string; good: string; bad: string; source: string }
> = {
  "datex-restrictions": {
    title: "Teepiirangud (DATEX)",
    label: "P4-piirangud",
    good: "roheline = piiranguid aknas pole (olukorrad geomeetriata)",
    bad: "punane = piiranguolukord akna tabelis (asukohta pole)",
    source:
      "TarkTee DATEX piiranguvoog pooli vaatlusakna tabelist (24 h aken, öine tõmme; olukorra-ID + liik, kaardigeomeetriat voos pole — asukohata)",
  },
  "datex-srti": {
    title: "Ohuteated (DATEX SRTI)",
    label: "P4-ohuteated",
    good: "roheline = ohuteateid aknas pole (olukorrad geomeetriata)",
    bad: "punane = ohuteateolukord akna tabelis (asukohta pole)",
    source:
      "TarkTee DATEX SRTI pooli vaatlusakna tabelist (6 h aken; olukorra-ID + liik, kaardigeomeetriat voos pole — asukohata)",
  },
  "datex-weather": {
    title: "Teeilmajaamad (DATEX)",
    label: "P4-teeilm",
    good: "roheline = ilmajaam lähedal (mõõtmik 1 h aknast, mitte prognoos)",
    bad: "punane = jaamu lähedal pole (teadmata)",
    source:
      "TarkTee DATEX ilmajaamade pooli vaatlusakna tabel (1 h aken, tunni tõmme; mõõtjaamad)",
  },
  "datex-counters": {
    title: "Liiklusloendurid (DATEX)",
    label: "P4-loendurid",
    good: "roheline = loendur lähedal (mõõtmik 1 h aknast, mitte hinnang)",
    bad: "punane = loendureid lähedal pole (teadmata)",
    source:
      "TarkTee DATEX loendurite pooli vaatlusakna tabel (1 h aken, tunni tõmme; voog/kiirus)",
  },
  "datex-cameras": {
    title: "Liikluskaamerad (DATEX)",
    label: "P4-kaamerad",
    good: "roheline = kaamera lähedal (ainult asukoht, pilti kaardil pole)",
    bad: "punane = kaameraid lähedal pole (teadmata)",
    source:
      "TarkTee DATEX kaamerate pooli vaatlusakna tabel (1 h aken, tunni tõmme; asukoht + URL pooli tabelis; binaare kaardile ei tooda kunagi)",
  },
  "datex-truckpark": {
    title: "Veoautoparklad (DATEX)",
    label: "P4-veoautoparklad",
    good: "roheline = parkla lähedal (asukoht + kohad, 30-päeva aknast)",
    bad: "punane = parklaid lähedal pole (teadmata)",
    source:
      "TarkTee DATEX veoautoparklate pooli vaatlusakna tabel (30-päeva aken, kuutõmme; asukoht + kohad)",
  },
};

export const DATEX_DEFS: LayerDef[] = DATEX_LAYER_IDS.map((id) => ({
  id,
  paramIds: [],
  paramLabel: DATEX_ET[id].label,
  title: DATEX_ET[id].title,
  goodLabel: DATEX_ET[id].good,
  badLabel: DATEX_ET[id].bad,
  source: DATEX_ET[id].source,
  fallbackPoints: [
    { lat: 59.4372, lon: 24.7536 }, // Kesklinn (labeled demo only)
  ],
}));

/** Inert placeholders required by the Record<LayerId> tables (never evaluated). */
export const DATEX_DECAY: Record<DatexLayerId, number> = {
  "datex-restrictions": 0.2,
  "datex-srti": 0.2,
  "datex-weather": 0.2,
  "datex-counters": 0.2,
  "datex-cameras": 0.2,
  "datex-truckpark": 0.2,
};

/** Markers only (no score field — pinned by test). */
export const DATEX_BONUS: Record<DatexLayerId, BonusSpec> = {
  "datex-restrictions": { kind: "pins" },
  "datex-srti": { kind: "pins" },
  "datex-weather": { kind: "pins" },
  "datex-counters": { kind: "pins" },
  "datex-cameras": { kind: "pins" },
  "datex-truckpark": { kind: "pins" },
};

export function bonusSpecForDatex(layer: string): BonusSpec | undefined {
  return (DATEX_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * Overpass QL fragment. Pole-only serving never queries live (route
 * comment); documents the source tags for rebuilds.
 * overpassQueryFor("datex-*") is never called in production (senscom
 * #484 precedent).
 */
export const DATEX_TAGS: Record<DatexLayerId, string> = {
  "datex-restrictions": 'n["highway"];',
  "datex-srti": 'n["highway"];',
  "datex-weather": 'n["man_made"="monitoring_station"];',
  "datex-counters": 'n["highway"="traffic_signals"];',
  "datex-cameras": 'n["man_made"="surveillance"];',
  "datex-truckpark": 'n["amenity"="parking"];',
};

/**
 * Raster master filename. NOT BUILT by documented markers-only
 * decision: the name resolves to an absent file (honestly-empty
 * downstream, never a gradient).
 */
export const DATEX_RASTER_FILE: Record<DatexLayerId, string> = {
  "datex-restrictions": "datex-restrictions-walk-raster.json",
  "datex-srti": "datex-srti-walk-raster.json",
  "datex-weather": "datex-weather-walk-raster.json",
  "datex-counters": "datex-counters-walk-raster.json",
  "datex-cameras": "datex-cameras-walk-raster.json",
  "datex-truckpark": "datex-truckpark-walk-raster.json",
};

/** NO metro master (documented): markers-only, windows serve county. */
export const DATEX_NO_METRO = true;

export function isDatexLayerId(layer: string): layer is DatexLayerId {
  return (DATEX_LAYER_IDS as string[]).includes(layer);
}

/** Feeds whose rows carry measured lat/lon (the plottable four). */
export function isDatexGeoLayer(layer: DatexLayerId): boolean {
  return (
    layer === "datex-weather" ||
    layer === "datex-counters" ||
    layer === "datex-cameras" ||
    layer === "datex-truckpark"
  );
}

function isFiniteNum(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

export interface DatexPoint {
  lon: number;
  lat: number;
}

/**
 * Pole table -> map points for the geo feeds. Only rows with measured
 * finite lat/lon plot (unlocated rows skipped, never zero-filled);
 * cameras plot position only (no image_url on the wire, ever).
 * restrictions/srti always read [] (no geometry by format).
 */
export function datexPointsForLayer(
  table: unknown,
  layer: DatexLayerId,
): DatexPoint[] {
  if (!isDatexGeoLayer(layer)) return [];
  if (typeof table !== "object" || table === null) return [];
  const rows = (table as { rows?: unknown }).rows;
  if (!Array.isArray(rows)) return [];
  const out: DatexPoint[] = [];
  for (const row of rows) {
    if (typeof row !== "object" || row === null) continue;
    const rec = row as Record<string, unknown>;
    const lat = rec.lat;
    const lon = rec.lon;
    if (!isFiniteNum(lat) || !isFiniteNum(lon)) continue;
    out.push({ lon, lat });
  }
  return out;
}

/** Short noun per feed for the /layers status line (freshness display). */
export function datexStatusNoun(layer: DatexLayerId): string {
  switch (layer) {
    case "datex-restrictions":
      return "piirangud";
    case "datex-srti":
      return "ohuteated";
    case "datex-weather":
      return "teeilmajaamad";
    case "datex-counters":
      return "loendurid";
    case "datex-cameras":
      return "kaamerad";
    case "datex-truckpark":
      return "veoautoparklad";
  }
}

/**
 * Windowed status line for /layers (issue #783: window + vintage on
 * the surface, never momentary state). `age` is the preformatted
 * vintage ("3 h", null when unknown) — formatting lives with the
 * page's ageEt, this helper owns the window wording only.
 */
export function datexStatusLine(
  layer: DatexLayerId,
  pointCount: number,
  age: string | null,
): string {
  const vintage = age !== null ? `; vanus ${age}` : "";
  const tail =
    pointCount > 0 ? `${pointCount} punkti` : "olukorrad geomeetriata";
  return `TarkTee DATEX ${datexStatusNoun(layer)} (${DATEX_WINDOW_ET[layer]}${vintage}) · ${tail}`;
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const DATEX_HOOK =
  "DATEX-HOOK (#763): datex overlays wired into layers/overlays/snapshot; pole live tables only, restrictions/srti honestly-empty, cameras URL-only. WINDOWED-HOOK (#783): every feed names its observation window + vintage, never momentary state.";
