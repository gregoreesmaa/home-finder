// TomTom incident overlay (issue #763, harvester #672): jams,
// closures and roadworks on the Tallinn bbox from a 6-hour
// observation window.
//
// Data reads POLE AGGREGATE-WINDOW TABLES (/v1/incidents, never
// committed sidecars — the SHORT-TERM CACHE ONLY verdict gates all
// TomTom work, see docs/p4_tomtom_incidents.md section 0), local
// keyed-harvester operator cache (tomtom_incidents.json, 6 h TTL) as
// fallback. The window is the contract (issue #783: no momentary
// state — every live-descended layer names its window + vintage):
// a stale cache hides behind the freshness timestamp (route degrades
// past INCIDENTS_TTL_S, never presented as live when old — scorer
// NULLs on stale by the same rule). No network, ever.
//
// Markers only (pins spec — no score field is painted for this layer,
// by design). One marker per incident at its FIRST geometry coordinate
// (where drivers encounter it); coordless incidents never plot.
// Shared files touch this module only through marked
// `INCIDENTS-HOOK (#763)` blocks.

import type { BonusSpec, LayerDef } from "./layers";

export type IncidentsLayerId = "incidents";

export const INCIDENTS_LAYER_IDS: IncidentsLayerId[] = ["incidents"];

/** 6-hour short-term cache (parity with INCIDENTS_TTL_S, pinned). */
export const INCIDENTS_TTL_S = 6 * 3600;

/**
 * Observation window, user-visible (issue #783: each live-descended
 * layer names its window + vintage). The window is the pull cadence +
 * serve TTL in parity: pulled 6-hourly (minute 17 past every 6th
 * hour cron) served 6h.
 * Single-layer mirror of DATEX_WINDOW_ET (pinned by test).
 */
export const INCIDENTS_WINDOW_ET = "6 h aken";

/** Pole live-table dataset (pole/api.py TOMTOM-HOOK, issue #782). */
export const INCIDENTS_POLE_DATASET = "incidents";

/** Harvester cache filename (batch_tomtom_incidents.py). */
export const INCIDENTS_CACHE_FILE = "tomtom_incidents.json";

/** Default cache dir (same default as the harvester --cache-dir usage). */
export function incidentsCacheDir(env: NodeJS.ProcessEnv = process.env): string {
  return env.INCIDENTS_CACHE_DIR ?? "/tmp/hf-incidents";
}

export const INCIDENTS_DEFS: LayerDef[] = [
  {
    id: "incidents",
    paramIds: [],
    paramLabel: "P4-intsidendid",
    title: "Intsidendid (TomTom)",
    goodLabel: "roheline = aknas marsruudil ummikuid/sulgusid pole",
    badLabel:
      "punane = ummik, sulgus või teetöö lähedal (mõõtmik 6 h aknast, mitte prognoos)",
    source:
      "TomTomi intsidentide pooli vaatlusakna tabel (6 h aken, 6-tunni tõmme; aegunud peitub ajatempli taha)",
    fallbackPoints: [
      { lat: 59.4372, lon: 24.7536 }, // Kesklinn (labeled demo only)
    ],
  },
];

/** Inert placeholder required by the Record<LayerId> tables (never evaluated). */
export const INCIDENTS_DECAY: Record<IncidentsLayerId, number> = {
  incidents: 0.2,
};

/** Markers only (no score field — pinned by test). */
export const INCIDENTS_BONUS: Record<IncidentsLayerId, BonusSpec> = {
  incidents: { kind: "pins" },
};

export function bonusSpecForIncidents(layer: string): BonusSpec | undefined {
  return (INCIDENTS_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * Overpass QL fragment. Operator-cache serving never queries live
 * (route comment); documents the source tags for rebuilds.
 * overpassQueryFor("incidents") is never called in production (senscom
 * #484 precedent).
 */
export const INCIDENTS_TAGS: Record<IncidentsLayerId, string> = {
  incidents: 'n["highway"];',
};

/**
 * Raster master filename. NOT BUILT by documented markers-only
 * decision: the name resolves to an absent file (honestly-empty
 * downstream, never a gradient).
 */
export const INCIDENTS_RASTER_FILE: Record<IncidentsLayerId, string> = {
  incidents: "incidents-walk-raster.json",
};

/** NO metro master (documented): markers-only, windows serve county. */
export const INCIDENTS_NO_METRO = true;

export function isIncidentsLayerId(layer: string): layer is IncidentsLayerId {
  return layer === "incidents";
}

export interface IncidentPoint {
  lon: number;
  lat: number;
  /** Delay magnitude 0-4 (marker sizing); null when unmeasured. */
  magnitude: number | null;
}

/**
 * Cached incidentDetails body -> map points. One marker per incident
 * at its FIRST finite geometry coordinate (lon-first GeoJSON order);
 * coordless incidents never plot; magnitude outside 0-4 reads null
 * (unknown, never clamped into a color).
 */
export function incidentPointsForCache(body: unknown): IncidentPoint[] {
  if (typeof body !== "object" || body === null) return [];
  const incidents = (body as { incidents?: unknown }).incidents;
  if (!Array.isArray(incidents)) return [];
  const out: IncidentPoint[] = [];
  for (const inc of incidents) {
    if (typeof inc !== "object" || inc === null) continue;
    const rec = inc as {
      properties?: { magnitudeOfDelay?: unknown };
      geometry?: { coordinates?: unknown };
    };
    const coords = rec.geometry?.coordinates;
    let first: { lon: number; lat: number } | null = null;
    if (Array.isArray(coords)) {
      for (const c of coords) {
        if (!Array.isArray(c) || c.length < 2) continue;
        if (typeof c[0] === "boolean" || typeof c[1] === "boolean") continue;
        const lon = Number(c[0]);
        const lat = Number(c[1]);
        if (Number.isFinite(lon) && Number.isFinite(lat)) {
          first = { lon, lat };
          break;
        }
      }
    }
    if (!first) continue;
    const mag = Number(rec.properties?.magnitudeOfDelay);
    out.push({
      ...first,
      magnitude:
        Number.isInteger(mag) && mag >= 0 && mag <= 4 ? mag : null,
    });
  }
  return out;
}

/**
 * Pole live-table body ({ incidents: [{ magnitude, points }] },
 * dims_tomtom_incidents.build_table shape served from
 * built/tomtom-incidents/table.json) -> map points. One marker per
 * row at its FIRST finite [lat, lon] pair (dims points are
 * lat-first, unlike the GeoJSON lon-first raw cache shape);
 * coordless rows never plot; magnitude outside 0-4 reads null
 * (unknown, never clamped into a color). Junk bodies read empty.
 */
export function incidentPointsForPoleTable(body: unknown): IncidentPoint[] {
  if (typeof body !== "object" || body === null) return [];
  const incidents = (body as { incidents?: unknown }).incidents;
  if (!Array.isArray(incidents)) return [];
  const out: IncidentPoint[] = [];
  for (const inc of incidents) {
    if (typeof inc !== "object" || inc === null) continue;
    const rec = inc as { magnitude?: unknown; points?: unknown };
    let first: { lon: number; lat: number } | null = null;
    if (Array.isArray(rec.points)) {
      for (const c of rec.points) {
        if (!Array.isArray(c) || c.length < 2) continue;
        if (typeof c[0] === "boolean" || typeof c[1] === "boolean") continue;
        const lat = Number(c[0]);
        const lon = Number(c[1]);
        if (Number.isFinite(lon) && Number.isFinite(lat)) {
          first = { lon, lat };
          break;
        }
      }
    }
    if (!first) continue;
    const mag = Number(rec.magnitude);
    out.push({
      ...first,
      magnitude:
        Number.isInteger(mag) && mag >= 0 && mag <= 4 ? mag : null,
    });
  }
  return out;
}

/**
 * Windowed status line for /layers (issue #783: window + vintage on
 * the surface, never momentary state). `age` is the preformatted
 * vintage ("3 h", null when unknown) — formatting lives with the
 * page's ageEt, this helper owns the window wording only.
 */
export function incidentsStatusLine(
  pointCount: number,
  age: string | null,
): string {
  const vintage = age !== null ? `; vanus ${age}` : "";
  return `Intsidendid (TomTomi ${INCIDENTS_WINDOW_ET}${vintage}) · ${pointCount} punkti`;
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const INCIDENTS_HOOK =
  "INCIDENTS-HOOK (#763): incidents overlay wired into layers/overlays/snapshot; operator 6h cache only, stale hides behind the timestamp. WINDOWED-HOOK (#783): names the 6 h observation window + vintage, never momentary state.";
