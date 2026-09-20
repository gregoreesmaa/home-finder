// KPO restriction-zone overlay (issue #626): joined WFS zones, NULL-empty outside.
//
// Restriction zones (piiranguvööndid: ehituskeeld vs conditioned) from the
// KMA kmakitsendused WFS (CC-BY 4.0 default, 18 families), harvested into
// known-parcel windows (never the whole county — elekter alone matches
// ~479k features; see scripts/build/batch_kpo.py). Bands score per parcel
// in services/scoring/dims_p4_kitsendus.py (ban 20-35, conditioned
// 50-65, worst/min wins; unknown types stay NULL). The overlay paints the
// ZONE polygons so restricted vs free reads at a glance; outside every
// polygon is NULL — never "clean title" (zones are not title truth; the
// legend + every reason name the kinnistusraamat/notar check).
//
// Serving: the parcel-window keep set ships in ONE sidecar
// (kpo/kpo-areas.json) via /api/layers/kpo/areas — fetched once per
// selection, painted as band fills (see applyKpoPolygons in
// ./outlines), polygons-only precedent (noise #625, forest #624).

import type { BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type KpoLayerId = "kpo";
export const KPO_LAYER_IDS: KpoLayerId[] = ["kpo"];

/** Publisher attribution (CC-BY 4.0 default, MKM source). */
export const KPO_ATTRIBUTION =
  "Maa- ja Ruumiamet kmakitsendused WFS (CC-BY 4.0, allikas MKM)";

/** Vintage of the zone harvest (annual TTL). */
export const KPO_VINTAGE = "2026-09";

/** The 18 harvested zone families (kma_avalik_*). */
export const KPO_FAMILIES = [
  "asjaoigus",
  "elekter",
  "gaas",
  "geodeesia",
  "kaugkyte",
  "kemikaal",
  "looduskaitse",
  "maaparandus",
  "muinsuskaitse",
  "planeering",
  "reostusoht",
  "ressurss",
  "riigikaitse",
  "side",
  "sundvaldus",
  "transport",
  "veekogu",
  "veevarustus",
] as const;

export const KPO_DEFS: LayerDef[] = [
  {
    id: "kpo",
    paramIds: [],
    paramLabel: "P4-kitsendus",
    title: "KPO piiranguvööndid (2026-09)",
    goodLabel:
      "vööndis tsooni pole (mitte 'puhas omand' — kaardistamata on teadmata, tsoonid pole omandiõigus)",
    badLabel:
      "punane = ehituskeeld (20-35) või tingimuslik vöönd (50-65) — kontrolli kinnistusraamatust ja notarilt",
    source:
      `${KPO_ATTRIBUTION}: teadaolevate kruntide akende tsoonipolügoonid (18 peret; väljaspool aknaid andmeid pole)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygons-only layers out of its fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): kpo serves zero points and builds no raster; the scorer's
 * bands read off the sidecar polygons, never a field — pinned by test.
 */
export const KPO_DECAY: Record<KpoLayerId, number> = {
  kpo: 1.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: zones live in
 * the KMA kmakitsendused WFS harvest, and polygon-only serving never
 * queries anything else. The only data path is
 * app/api/layers/kpo/areas.
 */
export const KPO_TAGS: Record<KpoLayerId, string> = {
  kpo: "kmakitsendused-WFS parcel-window keep (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const KPO_RASTER_FILE: Record<KpoLayerId, string> = {
  kpo: "kpo-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const KPO_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const KPO_NO_METRO = true;

/**
/**
 * Zone-type -> band score (issue #807) — mirrors _band_for_zone in
 * services/scoring/dims_p4_kitsendus.py (ban words first, then the
 * conditioned set; heritage zones condition whatever the wording;
 * unknown types stay NULL, never a guess).
 */
export function kpoScoreForZone(voond: string, family = ""): number | null {
  const raw = (voond || "").toLowerCase();
  const banWords: Array<[string, number]> = [
    ["ehituskeeld", 20],
    ["ehituskeeluvöönd", 20],
    ["tagasilöök", 35],
  ];
  for (const [word, score] of banWords) {
    if (raw.includes(word)) return score;
  }
  const conditionedWords: Array<[string, number]> = [
    ["tingimuslik", 50],
    ["kooskõlastus", 50],
    ["teavitus", 65],
    ["kaitsevöönd", 50],
    ["asjaõigus", 50],
  ];
  for (const [word, score] of conditionedWords) {
    if (raw.includes(word)) return score;
  }
  if ((family || "").toLowerCase() === "muinsuskaitse") return 50;
  return null;
}

/**
 * Bonus spec. Membership zones (issue #807): zones carry the verdict
 * — inside reads kpoScoreForZone (see zones807.ts), outside stays
 * unknown (unmapped is unmeasured, never clean title). Zero points,
 * null raster (still polygons-only). The live scorer legs are
 * services/scoring/dims_p4_kitsendus.py.
 */
export const KPO_BONUS: Record<KpoLayerId, BonusSpec> = {
  kpo: { kind: "zones" },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isKpoLayerId(layer: string): layer is KpoLayerId {
  return (KPO_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygons-only layers: no points, no raster — the sidecar polygons
 * carry the data (scored, unlike taste-only tints). The /layers page
 * branches on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isKpoPolygonOnlyLayer(layer: string): boolean {
  return isKpoLayerId(layer);
}

/**
 * Kpo bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForKpo(layer: string): BonusSpec | undefined {
  return (KPO_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const KPO_HOOK =
  "KPO-HOOK (#626): kpo zones wired into layers/overlays/outlines/snapshot; ban/conditioned fills, NULL-empty outside (never clean title).";

/**
 * One KPO zone polygon for the map sidecar. Rings are GeoJSON
 * [lon, lat] (exterior only, LCC-projected); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box; family is the
 * kma_avalik_* name; voond is the zone-type value (drives the fill).
 */
export interface KpoArea {
  family: string;
  nimi: string;
  voond: string;
  reegel: string;
  b: [number, number, number, number];
  r: number[][][];
}

export function isKpoArea(v: unknown): v is KpoArea {
  const p = v as Partial<KpoArea>;
  return (
    typeof p?.family === "string" &&
    (KPO_FAMILIES as readonly string[]).includes(p.family) &&
    typeof p?.nimi === "string" &&
    typeof p?.voond === "string" &&
    typeof p?.reegel === "string" &&
    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    Array.isArray(p?.r) &&
    p.r.length > 0 &&
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
 * Kpo polygons for painting band fills on the kpo layer.
 * Null on any failure: fills are a visual aid, never load-bearing —
 * the scorer reads the same sidecar independently.
 */
export async function fetchKpoAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<KpoArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/kpo/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    const areas = (body as { areas: unknown[] }).areas.filter(isKpoArea).map((p) => {
      const o = p as KpoArea;
      return {
        family: o.family,
        nimi: o.nimi,
        voond: o.voond,
        reegel: o.reegel,
        b: o.b,
        r: o.r,
      };
    });
    return areas;
  } catch {
    return null;
  }
}

/**
 * Zone fill colors by band (ban red, conditioned amber, unknown gray —
 * the overlay grades restriction, per docs/layers.md; the scorer's
 * worst/min wins, never the map). Shared by the map painter
 * (applyKpoPolygons) and unit-tested here.
 */
export const KPO_BAND_FILL: Record<string, string> = {
  ban: "#dc2626",
  conditioned: "#f59e0b",
  unknown: "#d1d5db",
};

/** Fill key for one zone (mirrors the scorer band table: ban words
 * first, then the conditioned set incl. "kaitsevöönd" + "asjaõigus";
 * heritage zones condition whatever the wording, Muinsuskaitseamet
 * approval, #626 acceptance). Unknown types stay gray, never dropped. */
export function kpoFillKey(voond: string, family = ""): string {
  const raw = (voond || "").toLowerCase();
  if (
    raw.includes("ehituskeeld") ||
    raw.includes("ehituskeeluvöönd") ||
    raw.includes("tagasilöök")
  )
    return "ban";
  if (
    raw.includes("tingimuslik") ||
    raw.includes("kooskõlastus") ||
    raw.includes("teavitus") ||
    raw.includes("kaitsevöönd") ||
    raw.includes("asjaõigus")
  )
    return "conditioned";
  if (family.toLowerCase() === "muinsuskaitse") return "conditioned";
  return "unknown";
}
