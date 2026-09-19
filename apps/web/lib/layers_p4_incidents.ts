// TomTom daily incident overlay (issue #763, harvester #672): today's
// jams, closures and roadworks on the Tallinn bbox.
//
// Data reads the keyed harvester's git-ignored operator cache
// (tomtom_incidents.json, 6 h TTL — SHORT-TERM CACHE ONLY verdict,
// docs/p4_tomtom_incidents.md section 0; no committed sidecars, no
// stored tables). The freshness timestamp is the contract: a stale
// cache hides behind it (route degrades past INCIDENTS_TTL_S, never
// presented as live when old — scorer NULLs on stale by the same
// rule). No network, ever.
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
    goodLabel: "roheline = marsruudil täna ummikuid/sulgusid pole",
    badLabel: "punane = ummik, sulgus või teetöö lähedal (mõõtmik, mitte prognoos)",
    source:
      "TomTomi intsidentide võtmega nädalasisene mõõtmik operaatori 6 h puhvrist (hetkeseis, mitte reaalajas; aegunud peitub ajatempli taha)",
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

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const INCIDENTS_HOOK =
  "INCIDENTS-HOOK (#763): incidents overlay wired into layers/overlays/snapshot; operator 6h cache only, stale hides behind the timestamp.";
