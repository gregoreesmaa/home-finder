// Group 3 cadastre-B verdicts (parameters3.md §5.3, issue #152):
// p183 water table depth, p184 geothermal suitability, p201 septic leach
// field, p228 water rights, p251 soil percolation rate.
//
// VERDICT: all five are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group03b.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 15 file shape) and lands + tests green on its own.
//
// WHY no layer ships (evidence, verified 2026-09-12 against the local
// Harjumaa PBF ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf — no
// network; see GROUP03B_EVIDENCE):
// * Every honestly-mappable area signal for these five params is already
//   shipped by a sibling: p50 drainage (#151, quiet halfM 300 over
//   sea + open water + wetlands + waterways) covers "far from water =
//   dry" for p183; B10C water (p53, area half 1 over drinking_water /
//   water_well / spring) covers mapped wells/springs; p338 weedwater
//   (#116, shore halfM 600 over natural=water) covers water amenity.
// * p183 from the remaining distinct signal (28 water_well + 35 spring
//   points county-wide) would paint Tallinn flat red (no data) — a
//   useless map; from all-hydro it would re-skin p50 drainage. Either
//   way it misleads or duplicates, so it stays a per-listing dim.
// * p184 needs bedrock depth / heat flow / conductivity (Maa-amet
//   subsurface grids): zero snapshot signal exists by construction.
// * p201 needs sewer-network absence + soil percolation (ÜVK/KOV data):
//   neither is in the snapshot; it is per-parcel either way.
// * p228 riparian rights are per-parcel legal facts (same precedent as
//   p71 easements, #151 no-map): a water-proximity gradient would
//   reward/penalise parcels on a legal question it cannot resolve, and
//   either direction poaches a sibling (p277 constraints / p338 amenity).
// * p251 needs the soil DB (ESDAC/SoilGrids): derived-soil.geojson holds
//   53 features of barrier/gate junk with zero soil attributes
//   (verified) — there is nothing to calibrate against.
//
// G03B-HOOK (#152): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP03B_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group03b.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP03B_ALL_PARAMS = [183, 184, 201, 228, 251] as const;

export type Group03BParam = (typeof GROUP03B_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP03B_SHIPPED_PARAMS: readonly Group03BParam[] = [];

export interface Group03BVerdict {
  /** parameters3.md parameter number. */
  param: Group03BParam;
  /** Scorer dim in services/scoring/dims_group03b.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP03B_NO_MAP: Group03BVerdict[] = [
  {
    param: 183,
    dim: "dim_water_table",
    nearestMap: "p50 drenaažiproksi (#151): veest kaugel = kuiv eeldus",
    reason:
      "Mõõdetud veetaset snapshots pole (hinnang): 28 kaevu + 35 allikat " +
      "terves maakonnas ei kanna Tallinna gradienti (punane tühjus, mitte " +
      "info); täis-hüdro kiht dubleeriks p50 drenaaži. Per-listing " +
      "dim hindab lähimat kaardistatud kõrge-veetaseme tunnust.",
  },
  {
    param: 184,
    dim: "dim_geothermal",
    nearestMap: "puudub — asenduskaarti pole",
    reason:
      "Aluspõhja/soojusvoo registriandmeid snapshots pole (EI OLE " +
      "hinnangut): puuraugu sobivus on puurkoha-fakt, millele OSM-is " +
      "ausat pindmist signaali pole. Dim jääb NULLiks koos " +
      "ostja-kontrolli põhjusega — ära feigi.",
  },
  {
    param: 201,
    dim: "dim_septic",
    nearestMap: "puudub — ÜVK/kanalisatsiooni kihti snapshots pole",
    reason:
      "Imbväljaku sobivus eeldab kanalisatsiooni puudumist + pinnase " +
      "läbilaskvust (hinnang): kumbagi registrit snapshots pole ja " +
      "otsus on krundi-põhine. Per-listing dim hindab kaugust lähimast " +
      "kaardistatud kaitsmist vajavast objektist (kaev/allikas/märgala).",
  },
  {
    param: 228,
    dim: "dim_water_rights",
    nearestMap: "p338 veekogude lähedus (#116, ameniteet) — MITTE õigused",
    reason:
      "Kallasõigus on krundi-põhine juriidiline fakt (hinnang, p71 " +
      "servituudi pretsedent #151): vee-läheduse gradient premeeriks/ " +
      "karistaks krunte küsimuses, mida ta ei lahenda. Per-listing dim " +
      "märgib lähima kaardistatud vooluvee kontrollivajaduse.",
  },
  {
    param: 251,
    dim: "dim_soil_percolation",
    nearestMap: "puudub — mullastiku kihti snapshots pole",
    reason:
      "Mullastiku andmebaasi (ESDAC/SoilGrids) snapshots pole (EI OLE " +
      "hinnangut): derived-soil.geojson 53 objekti on tõkkepuu/värava " +
      "müra ilma ühegi mulla-atribuudita. Dim jääb NULLiks KOV-tabeli " +
      "kontrolli põhjusega — ära feigi.",
  },
];

/**
 * Snapshot counts backing the verdicts (osmium tags-filter +
 * tags-count on harjumaa-260911.osm.pbf, 2026-09-12, nwr/ filters —
 * node-only would drop way-mapped wetlands, PR #118):
 * wells 28 man_made=water_well points, springs 35 natural=spring
 * points (+4 lines), wetlands 606 natural=wetland polygons + 548
 * lines, soil-file 53 junk features with zero soil attributes.
 */
export const GROUP03B_EVIDENCE = {
  wells: 28,
  springs: 35,
  wetlandsPoly: 606,
  wetlandsLine: 548,
  soilFileFeatures: 53,
  soilFileSoilAttrs: 0,
} as const;

/**
 * OSM tags evaluated per param and rejected for a gradient map
 * (documents the source tags for the record; the per-listing dims use
 * the same tags offline — the app serves the frozen snapshot, never
 * live Overpass).
 */
export const GROUP03B_CONSIDERED_TAGS: Record<Group03BParam, string> = {
  183: 'nwr["man_made"="water_well"];nwr["natural"="spring"];nwr["natural"="wetland"];',
  184: "(puudub — Maa-amet subsurface grids, snapshots pole)",
  201: 'nwr["man_made"="water_well"];nwr["natural"="spring"];nwr["natural"="wetland"];',
  228: 'nwr["waterway"~"river|stream|canal|ditch|drain"];',
  251: "(puudub — ESDAC/SoilGrids, snapshots pole)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP03B_HOOK =
  "G03B-HOOK (#152): no shared-file wiring — no layers ship, verdicts + dims only.";
