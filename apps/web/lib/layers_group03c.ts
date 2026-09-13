// Group 3 cadastre-C verdicts (parameters3.md §5.3, issue #153):
// p254 protected wetlands proximity, p256 natural springs/high water,
// p258 soil pH/composition, p273 unregistered easements, p277 riparian
// constraints.
//
// VERDICT: all five are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group03c.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 batch-B file shape, layers_group03b.ts, issue #152) and lands
// + tests green on its own.
//
// WHY no layer ships (evidence, verified 2026-09-12 against the local
// Harjumaa PBF ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf — no
// network; see GROUP03C_EVIDENCE):
// * p254: mapped wetlands (1264 tagged features) already feed TWO
//   shipped gradients — p50 drainage (#151, quiet halfM 300 over sea +
//   open water + wetlands + waterways) and wildcorr (#143, encounter
//   halfM 500 over wood + wetland + reserves). A third gradient over
//   wetland+reserve distance would re-skin siblings while claiming a
//   "protected" meaning the snapshot cannot resolve: per-wetland
//   protection status is an EELIS/kaitseala register fact, not an OSM
//   attribute, and proximity valence is genuinely two-sided (building
//   restriction vs nature amenity — a map needs a good/bad direction).
//   Per-listing dim reports the raw metres (the param's own REAL unit).
// * p256: 43 spring objects (35 points) + 30 well objects (28 points)
//   county-wide are too sparse for a Tallinn gradient (flat red, not
//   info — same verdict as p183, #152); the area question is covered
//   by B10C water (p53, mapped wells/springs) and p50 drainage.
//   Per-listing dim scores the nearest spring/well only (disjoint from
//   p183, which also counts wetlands).
// * p258: needs the soil DB (ESDAC/SoilGrids pH, texture, organic
//   matter): derived-soil.geojson holds 53 features of barrier/gate
//   junk with zero soil attributes (verified) — same verdict as p68
//   (#151) and p251 (#152). Nothing to calibrate against.
// * p273: UNREGISTERED easements are unmappable by definition —
//   stronger than p71 (#151 no-map): not even KKIS can show what was
//   never registered. Any spatial proxy would be fiction. Scorer dim
//   stays NULL with a disclosure/audit reason.
// * p277: riparian constraints are per-parcel legal facts (same
//   precedent as p228 water rights, #152 no-map): a water-proximity
//   gradient would reward/penalise parcels on a legal question it
//   cannot resolve, and either direction poaches a sibling (p50
//   drainage / p338 amenity / rejected p228). Per-listing dim flags
//   the nearest flowing-water-or-shore constraint check (disjoint
//   from p228, which scores flowing water only — the Water Act
//   ehituskeelu/kaitsevöönd also binds the sea shore).
//
// G03C-HOOK (#153): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP03C_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group03c.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP03C_ALL_PARAMS = [254, 256, 258, 273, 277] as const;

export type Group03CParam = (typeof GROUP03C_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP03C_SHIPPED_PARAMS: readonly Group03CParam[] = [];

export interface Group03CVerdict {
  /** parameters3.md parameter number. */
  param: Group03CParam;
  /** Scorer dim in services/scoring/dims_group03c.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP03C_NO_MAP: Group03CVerdict[] = [
  {
    param: 254,
    dim: "dim_wetland_proximity",
    nearestMap: "p50 drenaažiproksi (#151) + wildcorr elupaik (#143) — mõlemad loevad märgalu",
    reason:
      "Kaitsealune märgala on registri-fakt (hinnang): kaitse staatus " +
      "märgala kohta EELIS/kaitseala registrist snapshots pole ja kolmas " +
      "märgala-gradient dubleeriks p50 drenaaži + wildcorri. Per-listing " +
      "dim teatab kauguse meetrites (parameetri enda ühik) koos " +
      "kaitsepiirangu kontrollivajadusega.",
  },
  {
    param: 256,
    dim: "dim_springs",
    nearestMap: "B10C vesi (p53): kaardistatud kaevud/allikad; p50 drenaaž (#151)",
    reason:
      "Allikaid/kaevusid on terves maakonnas ~70 objekti (hinnang): " +
      "Tallinna gradient värviks ühtlaselt punaseks (tühi info, mitte " +
      "kaart), täis-hüdro kiht dubleeriks p50 drenaaži. Per-listing dim " +
      "hindab lähimat kaardistatud allikat/kaevu (märgaladeta — need " +
      "loeb p183).",
  },
  {
    param: 258,
    dim: "dim_soil_ph",
    nearestMap: "puudub — mullastiku kihti snapshots pole",
    reason:
      "Mulla pH/lõimise andmebaasi (ESDAC/SoilGrids) snapshots pole " +
      "(EI OLE hinnangut): derived-soil.geojson 53 objekti on " +
      "tõkkepuu/värava müra ilma ühegi mulla-atribuudita. Dim jääb " +
      "NULLiks KOV-tabeli/pinnaseuuringu kontrolli põhjusega — ära feigi.",
  },
  {
    param: 273,
    dim: "dim_unregistered_easements",
    nearestMap: "puudub — registreerimata koormatist ei näita ükski register",
    reason:
      "Registreerimata servituut on määratluse poolest kaardistamatu " +
      "(EI OLE hinnangut): seda ei näita ei KKIS ega kinnistusraamat, " +
      "iga ruumiline proksi oleks väljamõeldis. Dim jääb NULLiks " +
      "müüja-avalduse/õigusauditi kontrolli põhjusega — ära feigi.",
  },
  {
    param: 277,
    dim: "dim_riparian_constraints",
    nearestMap: "p338 veekogude lähedus (#116, ameniteet) — MITTE piirangud",
    reason:
      "Kaldapiirang (ehituskeelu-/kaitsevöönd/kallasrada) on " +
      "krundi-põhine juriidiline fakt (hinnang, p228 pretsedent #152): " +
      "vee-läheduse gradient premeeriks/karistaks krunte küsimuses, " +
      "mida ta ei lahenda. Per-listing dim märgib lähima vooluvee/ranna " +
      "piirangu-kontrolli (mererand kaasa arvatud — erinevalt p228-st).",
  },
];

/**
 * Snapshot counts backing the verdicts (osmium tags-filter nwr/ +
 * export on harjumaa-260911.osm.pbf, 2026-09-12; tagged-feature counts
 * with geometry split — closed-way twins and untagged relation members
 * counted separately so the numbers re-derive; replay with
 * scripts/build/batch_g03c_cadastre.py --stat).
 */
export const GROUP03C_EVIDENCE = {
  springsTagged: 43,
  springsPoints: 35,
  wellsTagged: 30,
  wellsPoints: 28,
  wetlandsTagged: 1264,
  wetlandsPoly: 667,
  wetlandsLine: 637,
  reservesLeisureTagged: 137,
  reservesLeisurePoly: 32,
  protectedAreaTagged: 167,
  protectedAreaPoly: 51,
  soilFileFeatures: 53,
  soilFileSoilAttrs: 0,
} as const;

/**
 * OSM tags evaluated per param and rejected for a gradient map
 * (documents the source tags for the record; the per-listing dims use
 * the same tags offline — the app serves the frozen snapshot, never
 * live Overpass).
 */
export const GROUP03C_CONSIDERED_TAGS: Record<Group03CParam, string> = {
  254: 'nwr["natural"="wetland"];nwr["leisure"="nature_reserve"];nwr["boundary"="protected_area"];',
  256: 'nwr["natural"="spring"];nwr["man_made"="water_well"];',
  258: "(puudub — ESDAC/SoilGrids, snapshots pole)",
  273: "(puudub — registreerimata koormatis on määratluse poolest kaardistamatu)",
  277: 'nwr["waterway"~"river|stream|canal|ditch|drain"];nwr["natural"="coastline"];',
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP03C_HOOK =
  "G03C-HOOK (#153): no shared-file wiring — no layers ship, verdicts + dims only.";
