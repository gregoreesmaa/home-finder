// Commute-shed isochrone overlays (issue #670, wired by #763): TomTom
// Reachable Range polygons (15/30 min, peak/off-peak) around the 5 job hubs.

import type { BonusSpec, LayerDef } from "./layers";
//
// HONESTY (load-bearing): sheds are a WEEKLY keyed measurement served
// from the pole aggregate-window table (ToS 11.4 — never a committed
// sidecar), so every def carries the 7-day window + vintage
// ("7-päeva aken, nädalatõmme; mõõtmik, mitte reaalajas", issue
// #783). Rush sheds are the binding constraint; off-peak sheds are
// reference only. Empty rings paint slate "mõõtmata" (never dropped,
// never shrunk to a dot).
//
// SCOPE (judgment call, for the reviewer): WIRED by #763 — the live
// keyed cache exists (the harvester's git-ignored operator cache dir,
// served same-origin through /api/layers/sheds/areas, never committed).
// Shared files touch this module only through marked `SHED-HOOK (#763)`
// blocks. The per-listing leg is the scorer's job
// (services/scoring/dims_tomtom_isochrones.py).

/** Shed polygon layer ids: 15/30 min x peak/off-peak. */
export type ShedLayerId =
  | "shed-15-peak"
  | "shed-15-offpeak"
  | "shed-30-peak"
  | "shed-30-offpeak";

export const SHED_LAYER_IDS: ShedLayerId[] = [
  "shed-15-peak",
  "shed-15-offpeak",
  "shed-30-peak",
  "shed-30-offpeak",
];

/** Budget + band behind each layer id. */
export const SHED_LAYER_SPEC: Record<
  ShedLayerId,
  { budgetS: 900 | 1800; band: "rush" | "offpeak" }
> = {
  "shed-15-peak": { budgetS: 900, band: "rush" },
  "shed-15-offpeak": { budgetS: 900, band: "offpeak" },
  "shed-30-peak": { budgetS: 1800, band: "rush" },
  "shed-30-offpeak": { budgetS: 1800, band: "offpeak" },
};

export function isShedLayerId(v: unknown): v is ShedLayerId {
  return (
    typeof v === "string" &&
    (SHED_LAYER_IDS as string[]).includes(v)
  );
}

/** One hub shed polygon (ring = [lat, lon] pairs). */
export interface ShedPolygon {
  hub: string;
  budgetS: number;
  band: string;
  ring: Array<[number, number]>;
}

export function isShedPolygon(v: unknown): v is ShedPolygon {
  if (typeof v !== "object" || v === null) return false;
  const p = v as Record<string, unknown>;
  return (
    typeof p.hub === "string" &&
    typeof p.budgetS === "number" &&
    typeof p.band === "string" &&
    Array.isArray(p.ring) &&
    p.ring.every(
      (pt) =>
        Array.isArray(pt) &&
        pt.length === 2 &&
        pt.every((n) => typeof n === "number" && Number.isFinite(n)),
    )
  );
}

/** Fill colors per layer (peak = stronger, off-peak = washed). */
export const SHED_FILL: Record<ShedLayerId, string> = {
  "shed-15-peak": "#16a34a",
  "shed-15-offpeak": "#86efac",
  "shed-30-peak": "#2563eb",
  "shed-30-offpeak": "#bfdbfe",
};

/** Unmeasured paint (slate, never dropped, never green). */
export const SHED_UNMEASURED_FILL = "#94a3b8";

export const SHED_ATTRIBUTION =
  "TomTom Reachable Range (pooli vaatlusakna tabel — 7-päeva aken, nädalatõmme; mõõtmik, mitte reaalajas)";

/**
 * Observation window, user-visible (issue #783: each live-descended
 * layer names its window + vintage). The window is the pull cadence +
 * serve TTL in parity: pulled weekly (Sun 20:05 cron) served 7d
 * (SHED_TTL_S in lib/server/sheds.ts — pinned mirror). All four shed
 * layers share the one window (single-window mirror of
 * DATEX_WINDOW_ET, pinned by test).
 */
export const SHED_WINDOW_ET = "7-päeva aken, nädalatõmme";

/** Layer descriptors (standalone: not part of the shared LayerId union). */
export interface ShedDef {
  id: ShedLayerId;
  title: string;
  goodLabel: string;
  badLabel: string;
  source: string;
  hubCount: number;
}

function estBand(band: "rush" | "offpeak"): string {
  return band === "rush" ? "tipptund" : "tipuväline";
}

export const SHED_DEFS: ShedDef[] = SHED_LAYER_IDS.map((id) => {
  const spec = SHED_LAYER_SPEC[id];
  const mins = spec.budgetS / 60;
  return {
    id,
    title: `${mins} min tööulatus (${estBand(spec.band)})`,
    goodLabel: `hubi ulatuses — ${mins} min autosõit tööle (${estBand(spec.band)}, mõõtmik)`,
    badLabel: "ulatust väljas — pikk autosõit või mõõtmata (tõmmet pole)",
    source: `${SHED_ATTRIBUTION}: 5 tööhubi polügooni (${mins} min, ${estBand(spec.band)})`,
    hubCount: 5,
  };
});

export const SHED_HOOK =
  "SHED-HOOK (#763) WINDOWED-HOOK (#783): shed hub fills name the 7-day observation window + vintage, never momentary state.";

/**
 * Windowed status line for /layers (issue #783: window + vintage on
 * the surface, never momentary state). `age` is the preformatted
 * vintage ("3 pv", null when unknown) — formatting lives with the
 * page's ageEt, this helper owns the window wording only.
 */
export function shedStatusLine(
  areaCount: number,
  age: string | null,
): string {
  const vintage = age !== null ? `; vanus ${age}` : "";
  return `TomTomi tööulatus (5 hubi, ${SHED_WINDOW_ET}${vintage}) · ${areaCount} polügooni`;
}

/**
 * Registry defs (polygons-only, flood #487 precedent): no score field
 * is painted for these layers — the map paints hub fills only, and
 * outside every polygon stays unknown. fallbackPoints is EMPTY (demo
 * points would paint a fake gradient splat); paramIds stays [] with
 * the P4-sõiduulatus slice label (scorer leg
 * dim_jobs_within_30min, never a parameters3 number).
 */
export const SHED_LAYER_DEFS: LayerDef[] = SHED_DEFS.map((d) => ({
  id: d.id,
  paramIds: [],
  paramLabel: "P4-sõiduulatus",
  title: d.title,
  goodLabel: d.goodLabel,
  badLabel: d.badLabel,
  source: `${d.source} (Tallinna aken)`,
  fallbackPoints: [],
}));

/** Inert placeholders required by the Record<LayerId> tables (never evaluated). */
export const SHED_DECAY: Record<ShedLayerId, number> = {
  "shed-15-peak": 0.2,
  "shed-15-offpeak": 0.2,
  "shed-30-peak": 0.2,
  "shed-30-offpeak": 0.2,
};

/**
 * Inside-shed scores by drive-time budget (issue #807 judgment: a
 * 15-minute hub reach reads 80, a 30-minute reach 70 — congestion is
 * baked into the polygon SHAPE, so peak/offpeak share the score).
 * Outside every hub polygon stays unknown (unmeasured slate, never a
 * long-drive penalty — the cache may simply lack that hub).
 */
export const SHED_BUDGET_SCORE: Record<number, number> = {
  900: 80,
  1800: 70,
};

/**
 * Membership-zone specs (issue #807): hub polygons carry the verdict
 * (see zones807.ts). Still polygons-only (zero fallback points).
 */
export const SHED_BONUS: Record<ShedLayerId, BonusSpec> = {
  "shed-15-peak": { kind: "zones" },
  "shed-15-offpeak": { kind: "zones" },
  "shed-30-peak": { kind: "zones" },
  "shed-30-offpeak": { kind: "zones" },
};

export function bonusSpecForSheds(layer: string): BonusSpec | undefined {
  return (SHED_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * Overpass QL fragment. Snapshot-only serving never queries live (route
 * comment); documents the hub stop tags for rebuilds.
 * overpassQueryFor("shed-*") is never called in production (senscom
 * #484 precedent).
 */
export const SHED_TAGS: Record<ShedLayerId, string> = {
  "shed-15-peak": 'n["highway"="bus_stop"];',
  "shed-15-offpeak": 'n["highway"="bus_stop"];',
  "shed-30-peak": 'n["highway"="bus_stop"];',
  "shed-30-offpeak": 'n["highway"="bus_stop"];',
};

/**
 * Raster master filename. NOT BUILT by documented polygons-only
 * decision: the name resolves to an absent file (honestly-empty
 * downstream, never a gradient).
 */
export const SHED_RASTER_FILE: Record<ShedLayerId, string> = {
  "shed-15-peak": "shed-15-peak-walk-raster.json",
  "shed-15-offpeak": "shed-15-offpeak-walk-raster.json",
  "shed-30-peak": "shed-30-peak-walk-raster.json",
  "shed-30-offpeak": "shed-30-offpeak-walk-raster.json",
};

/** NO metro master (documented): polygons-only, windows serve county. */
export const SHED_NO_METRO = true;

/** One hub shed polygon for map fills (ring = [lat, lon] pairs). */
export interface ShedArea {
  hub: string;
  ring: Array<[number, number]>;
}

function isShedArea(v: unknown): v is ShedArea {
  if (typeof v !== "object" || v === null) return false;
  const p = v as Record<string, unknown>;
  return (
    typeof p.hub === "string" &&
    Array.isArray(p.ring) &&
    p.ring.length >= 3 &&
    p.ring.every(
      (pt) =>
        Array.isArray(pt) &&
        pt.length === 2 &&
        pt.every((n) => typeof n === "number" && Number.isFinite(n)),
    )
  );
}

/**
 * Hub shed polygons for painting fills on one shed layer. Null on any
 * failure: fills are a visual aid — a missing/stale operator cache
 * draws nothing (honestly-empty, never demo polygons).
 */
export async function fetchShedAreas(
  layer: ShedLayerId,
  fetchImpl: typeof fetch = fetch,
): Promise<ShedArea[] | null> {
  try {
    const res = await fetchImpl(
      `/api/layers/sheds/areas?layer=${encodeURIComponent(layer)}`,
    );
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (
      !body ||
      typeof body !== "object" ||
      !Array.isArray((body as { areas: unknown }).areas)
    ) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isShedArea).map((p) => {
      const o = p as ShedArea;
      return { hub: o.hub, ring: o.ring };
    });
  } catch {
    return null;
  }
}

/**
 * Shed polygons for one layer from a snapshot table
 * ({ polygons: [{ hub, budgetS, band, ring }] }).
 * Unknown shapes are skipped, never faked.
 */
export function shedPolygonsForLayer(
  snapshot: unknown,
  layer: ShedLayerId,
): ShedPolygon[] {
  const spec = SHED_LAYER_SPEC[layer];
  if (
    typeof snapshot !== "object" ||
    snapshot === null ||
    !Array.isArray((snapshot as { polygons?: unknown }).polygons)
  ) {
    return [];
  }
  const polys = (snapshot as { polygons: unknown[] }).polygons;
  return polys.filter(
    (p): p is ShedPolygon =>
      isShedPolygon(p) &&
      p.budgetS === spec.budgetS &&
      p.band === spec.band &&
      p.ring.length >= 3,
  );
}

/**
 * Ray-casting point-in-ring over a shed polygon (scorer parity with
 * point_in_ring in dims_tomtom_isochrones.py).
 */
export function shedCoversPoint(
  poly: ShedPolygon,
  lat: number,
  lon: number,
): boolean {
  const ring = poly.ring;
  if (ring.length < 3) return false;
  let inside = false;
  let j = ring.length - 1;
  for (let i = 0; i < ring.length; i++) {
    const [yi, xi] = ring[i];
    const [yj, xj] = ring[j];
    if (yi > lat !== yj > lat) {
      const xcross = ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
      if (lon < xcross) inside = !inside;
    }
    j = i;
  }
  return inside;
}
