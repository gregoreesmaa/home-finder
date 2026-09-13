// Group 3 cadastre-E verdicts (parameters3.md §5.3, issue #155):
// p397 perimeter fence ownership, p400 yard drainage/swales.
//
// VERDICT: both are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group03e.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3-B file shape, #152) and lands + tests green on its own.
//
// WHY no layer ships (evidence, verified 2026-09-12 against the local
// Harjumaa PBF ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf — no
// network; see GROUP03E_EVIDENCE):
// * p397 asks WHO owns the boundary fence (buyer / neighbour / shared)
//   — a bilateral per-parcel legal fact, same precedent as p71
//   easements and p75 boundary clarity (#151, both no-map). The
//   snapshot carries ZERO ownership=* and ZERO owner=* tags on any of
//   its 36384 barrier objects; the only owner-ish signal is operator=*
//   on 364 institutional compound fences (198 Tallinna Haridusamet
//   school yards, ~90 Elering/Elektrilevi substations). A gradient from
//   "near a school/substation fence" would red-pen homes on a fence-
//   ownership question it cannot resolve — unfair and misleading, so it
//   stays a NULL per-listing dim with a seller/kinnistusraamat check.
// * p400 (yard swales, grading, French drains, sump routing) is a
//   per-parcel micro-drainage fact: the works themselves are
//   unobservable at area scale (mostly underground/private) and the
//   only area signal — 8973 mapped waterway=ditch/drain lines, 2663 in
//   the Tallinn bbox — is ALREADY consumed by the p50 drainage proxy
//   (#151) with the opposite polarity (near water = wet hint = red). A
//   second gradient from the same tags either re-skins p50 (same
//   polarity, strict tag subset) or contradicts it parcel-by-parcel
//   (flipped polarity: near-ditch = "managed" = green while p50 reads
//   the same ditch red). Neither is defensible, and the direction
//   cannot be calibrated without the Maa-amet LiDAR DEM / EELIS flow
//   grids (not in the snapshot). Area wetness context stays on the p50
//   layer; the yard question stays a NULL per-listing dim with an
//   on-site/ÜVK check.
//
// G03E-HOOK (#155): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP03E_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group03e.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP03E_ALL_PARAMS = [397, 400] as const;

export type Group03EParam = (typeof GROUP03E_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP03E_SHIPPED_PARAMS: readonly Group03EParam[] = [];

export interface Group03EVerdict {
  /** parameters3.md parameter number. */
  param: Group03EParam;
  /** Scorer dim in services/scoring/dims_group03e.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP03E_NO_MAP: Group03EVerdict[] = [
  {
    param: 397,
    dim: "dim_fence_ownership",
    nearestMap: "puudub — omandiõiguse kaarti snapshots pole",
    reason:
      "Piirdeaia omand (ostja/naaber/ühine) on krundi-põhine juriidiline " +
      "fakt (hinnang, p71 servituudi ja p75 piiride pretsedent #151): " +
      "hetktõmmise 11308 aia seas pole ühtki ownership/owner-märgendit, " +
      "364 operator-märgendit kuuluvad koolide/alajaamade piirdeaedadele " +
      "ega vasta elamukrundi küsimusele. Dim jääb NULLiks " +
      "müüja/kinnistusraamatu kontrolli põhjusega — ära feigi.",
  },
  {
    param: 400,
    dim: "dim_yard_drainage",
    nearestMap: "p50 drenaažiproksi (#151): piirkonna märguskontekst, MITTE hoovi kuivendus",
    reason:
      "Hoovi kraavid, kalded ja sademevee ärajuhtimine on krundi-põhine " +
      "mikro-fakt (hinnang): ainsat pindmist signaali (8973 kraavi/kuivendit, " +
      "sh 2663 Tallinnas) tarbib juba p50 drenaažiproksi vastupidise " +
      "polaarsusega, nii et teine gradient kas dubleeriks või räägiks p50-le " +
      "samade joonte pealt vastu. Suunda ei saa kalibreerida ilma Maa-ameti " +
      "reljeefimudelita. Dim jääb NULLiks kohapealse/ÜVK kontrolli " +
      "põhjusega — ära feigi.",
  },
];

/**
 * Snapshot counts backing the verdicts (osmium tags-filter + export on
 * harjumaa-260911.osm.pbf, 2026-09-12, nwr/ filters — space-separated
 * expressions are OR'd, a single quoted "a b" string matches nothing):
 * barriers 36384 (fence 11308), ownership/owner keys 0, operator keys
 * 364 (institutional compounds); ditch 7657 + drain 1316 tagged lines
 * (2663 in the Tallinn bbox 24.55,59.35,24.95,59.50).
 */
export const GROUP03E_EVIDENCE = {
  barriers: 36384,
  fences: 11308,
  ownershipTags: 0,
  ownerTags: 0,
  operatorTags: 364,
  ditch: 7657,
  drain: 1316,
  ditchDrainTallinn: 2663,
} as const;

/**
 * OSM tags evaluated per param and rejected for a gradient map
 * (documents the source tags for the record; the NULL dims need no
 * fetch — the app serves the frozen snapshot, never live Overpass).
 */
export const GROUP03E_CONSIDERED_TAGS: Record<Group03EParam, string> = {
  397: 'nwr["barrier"~"fence|wall|hedge|retaining_wall"]; (ownership=* keys: 0)',
  400: 'nwr["waterway"~"ditch|drain"]; (already consumed by p50 #151, opposite polarity)',
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP03E_HOOK =
  "G03E-HOOK (#155): no shared-file wiring — no layers ship, verdicts + dims only.";
