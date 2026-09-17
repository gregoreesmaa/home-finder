// Harbour overlay (issue #627): joined sadamaregister ports + AIS
// pleasure-craft cells, NULL-empty outside.
//
// Ports: sadamaregister public-active rows (function 1/2/3 mapped
// from the app's own UI) joined to INSPIRE PortNode geometry on
// publicId — served as POINTS on the standard point path (real
// data, snapshot provenance). Cells: AIS 2024 500 m pleasure counts
// (CC BY-SA 3.0, grid as-is) painted as band FILLS under port DOTS
// via applyHarbourOverlays (one slot pass). Outside every port influence radius and
// every cell is NULL — never calm/quiet. Season data is not public,
// so no calendar claims anywhere (legend + reasons say so).
//
// Serving: the Harju keep set ships in ONE sidecar
// (harbour/harbour-areas.json) via /api/layers/harbour/areas for the
// cells; ports ride the [layer] points branch off the same sidecar.
// Scorer legs live in services/scoring/dims_p4_harbour.py (function
// bands + pleasure bands, worst/mild); the P4-023 fixture sadam row
// scores measured bands when it carries a joined function.

import type { BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type HarbourLayerId = "harbour";
export const HARBOUR_LAYER_IDS: HarbourLayerId[] = ["harbour"];

/** Publisher attribution (register: no licence stated; AIS: CC BY-SA 3.0). */
export const HARBOUR_ATTRIBUTION =
  "sadamaregister (funktsioon) + INSPIRE TN_sadam PortNode (geomeetria) + Transpordiamet AIS 2024 (CC BY-SA 3.0)";

/** AIS vintage harvested (annual TTL). */
export const HARBOUR_VINTAGE = "2024";

export const HARBOUR_DEFS: LayerDef[] = [
  {
    id: "harbour",
    paramIds: [],
    paramLabel: "P4-sadam",
    title: "Sadamad + väikelaevaliiklus (2024)",
    goodLabel:
      "läheduses sadamat/AIS-tihedust pole (mitte 'rahulik' — kaardistamata on teadmata)",
    badLabel:
      "töösadam lähedal (fn1) või tihe väikelaevaliiklus (Pleasure ≥50)",
    source: `${HARBOUR_ATTRIBUTION}: Harju sadamad (liitunud punktid) + Tallinna lahe väikelaevaruudud (hooajajaotuseta, aastakokku)`,
    // Points ARE the data for ports (served on the point path);
    // cells paint as fills. No demo points ever (empty fallback,
    // pinned by test).
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): the scorer's bands read off joined rows, never a field —
 * pinned by test.
 */
export const HARBOUR_DECAY: Record<HarbourLayerId, number> = {
  harbour: 1.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: ports live in
 * the sadamaregister API + INSPIRE join, cells in the AIS SHP; the
 * only data path is app/api/layers/harbour/areas.
 */
export const HARBOUR_TAGS: Record<HarbourLayerId, string> = {
  harbour: "sadamaregister-api + INSPIRE-join + AIS-SHP (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented decision (see header): the name resolves to an absent
 * file so windows serve honestly-empty, never a gradient. */
export const HARBOUR_RASTER_FILE: Record<HarbourLayerId, string> = {
  harbour: "harbour-walk-raster.json",
};

/** NO raster master (documented): points + fills, windows serve county. */
export const HARBOUR_NO_RASTER = true;

/** NO metro master (documented): points + fills, windows serve county. */
export const HARBOUR_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: ports score in
 * dims_p4_harbour.py, cells paint fills — pinned by test). Shape
 * mirrors the area kind so the type contract holds without inventing
 * a calibration.
 */
export const HARBOUR_BONUS: Record<HarbourLayerId, BonusSpec> = {
  harbour: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isHarbourLayerId(layer: string): layer is HarbourLayerId {
  return (HARBOUR_LAYER_IDS as string[]).includes(layer);
}

/**
 * Harbour serves REAL points (ports) plus fills (cells) — it is NOT a
 * polygons-only layer, so this is always false (kept for grep-symmetry
 * with the polygons-only hooks; pinned by test).
 */
export function isHarbourPolygonOnlyLayer(layer: string): boolean {
  void layer;
  return false;
}

/**
 * Harbour bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForHarbour(layer: string): BonusSpec | undefined {
  return (HARBOUR_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const HARBOUR_HOOK =
  "HARBOUR-HOOK (#627): harbour ports + AIS cells wired into layers/overlays/outlines/snapshot; NULL-empty outside (never calm).";

/** One joined port for points + scorer joins. */
export interface HarbourPort {
  harbour_id: string;
  name: string;
  function: number;
  function_label: string;
  address: string;
  lon: number;
  lat: number;
}

/** One AIS pleasure cell centroid for fills + scorer joins. */
export interface HarbourCell {
  lon: number;
  lat: number;
  pleasure: number;
  all: number;
}

function isFiniteNumber(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

export function isHarbourPort(v: unknown): v is HarbourPort {
  const p = v as Partial<HarbourPort>;
  return (
    typeof p?.harbour_id === "string" &&
    typeof p?.name === "string" &&
    (p.function === 1 || p.function === 2 || p.function === 3) &&
    typeof p?.function_label === "string" &&
    typeof p?.address === "string" &&
    isFiniteNumber(p?.lon) &&
    isFiniteNumber(p?.lat)
  );
}

export function isHarbourCell(v: unknown): v is HarbourCell {
  const p = v as Partial<HarbourCell>;
  return (
    isFiniteNumber(p?.lon) &&
    isFiniteNumber(p?.lat) &&
    isFiniteNumber(p?.pleasure) &&
    isFiniteNumber(p?.all)
  );
}

export interface HarbourAreas {
  ports: HarbourPort[];
  cells: HarbourCell[];
}

/**
 * Harbour sidecar for cells (ports ride the [layer] points branch).
 * Null on any failure: fills are a visual aid, never load-bearing.
 */
export async function fetchHarbourAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<HarbourAreas | null> {
  try {
    const res = await fetchImpl("/api/layers/harbour/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object") return null;
    const raw = body as { ports?: unknown[]; cells?: unknown[] };
    if (!Array.isArray(raw.ports) || !Array.isArray(raw.cells)) return null;
    return {
      ports: raw.ports.filter(isHarbourPort),
      cells: raw.cells.filter(isHarbourCell),
    };
  } catch {
    return null;
  }
}

/**
 * Ports inside a bbox for the [layer] points branch (pure; the route
 * loads the sidecar and filters per view).
 */
export function harbourPointsIn(
  ports: HarbourPort[],
  bbox: { minlon: number; minlat: number; maxlon: number; maxlat: number },
): { lat: number; lon: number }[] {
  return ports
    .filter(
      (p) =>
        p.lon >= bbox.minlon &&
        p.lon <= bbox.maxlon &&
        p.lat >= bbox.minlat &&
        p.lat <= bbox.maxlat,
    )
    .map((p) => ({ lat: p.lat, lon: p.lon }));
}

/**
 * Pleasure-cell fill colors (recreation pressure, pale → deep green).
 * Shared by the map painter (applyHarbourOverlays) and unit-tested.
 */
export const HARBOUR_CELL_FILL: Record<string, string> = {
  low: "#bbf7d0",
  mid: "#4ade80",
  high: "#15803d",
  unknown: "#d1d5db",
};

/** Fill key for one annual pleasure count (grid as-is, never scaled). */
export function harbourCellFillKey(pleasure: number): string {
  if (!Number.isFinite(pleasure) || pleasure < 1) return "unknown";
  if (pleasure >= 50) return "high";
  if (pleasure >= 10) return "mid";
  return "low";
}
