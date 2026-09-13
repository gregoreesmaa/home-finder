// Group 17 HOA-C verdict (parameters3.md §5.17, issue #207):
// p3 HOA fees (igakuine KÜ haldustasu).
//
// VERDICT: documented NO-MAP (OTA PR #131 precedent — per-document
// facts ship as scorer NULLs, never gradients) with the scorer dim in
// services/scoring/dims_group17c.py. This file owns the verdict
// registry; it is self-contained on purpose (mirrors the Group 3-B
// file shape) and lands + tests green on its own.
//
// WHY no layer ships (evidence): the monthly HOA fee is a per-KÜ EUR
// fact — the KÜ eelarve line / juhatuse tasumäär, filed in the
// e-Äriregister annual report. Zero fee keys exist anywhere in the
// local 2026-09-12 snapshot, so there is nothing to calibrate a
// gradient against; a neighbours-average map would attribute another
// building's fee to the buyer's flat (fake precision). It stays a
// per-listing NULL dim with an Äriregister-check reason — ära feigi.
//
// Sibling context (disjoint ownership, no overlap): G17A (#177) owns
// p60/p187/p311/p312/p347, G17B (#178) owns p463/p464/p465/p469,
// G17-rest (#196) owns p4/p49/p142/p145/p152/p167/p245/p246/p247/
// p278/p368/p427. p3 is owned only here.
//
// G17C-HOOK (#207): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP17C_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group17c.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP17C_ALL_PARAMS = [3] as const;

export type Group17CParam = (typeof GROUP17C_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP17C_SHIPPED_PARAMS: readonly Group17CParam[] = [];

export interface Group17CVerdict {
  /** parameters3.md parameter number. */
  param: Group17CParam;
  /** Scorer dim in services/scoring/dims_group17c.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP17C_NO_MAP: Group17CVerdict[] = [
  {
    param: 3,
    dim: "dim_hoa_fees",
    nearestMap: "puudub — asenduskaarti pole",
    reason:
      "Igakuine KÜ haldustasu on KÜ-põhine euro-fakt (KÜ eelarve / " +
      "juhatuse tasumäär e-Äriregistri majandusaasta aruandes): tasu " +
      "võtmeid snapshots pole (EI OLE hinnangut) — naabermajade " +
      "keskmine gradient omistaks ostjale võõra maja tasu. Dim jääb " +
      "NULLiks Äriregistri-kontrolli põhjusega — ära feigi.",
  },
];

/**
 * Snapshot evidence backing the verdict: zero HOA-fee keys anywhere
 * in the local 2026-09-12 snapshot (a per-KÜ document fact has no
 * area signal to calibrate — verified by the absence of fee/cost
 * keys in the extract, same precedent as the G17-rest EUR facts,
 * #196).
 */
export const GROUP17C_EVIDENCE = {
  feeKeysInSnapshot: 0,
} as const;

/**
 * OSM tags evaluated for the param and rejected for a gradient map
 * (documents the absence for the record; the per-listing dim runs
 * offline on KÜ documents — the app serves the frozen snapshot,
 * never live Overpass).
 */
export const GROUP17C_CONSIDERED_TAGS: Record<Group17CParam, string> = {
  3: "(puudub — e-Äriregister KÜ majandusaasta aruanded / juhatuse tasumäärad, snapshots pole)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP17C_HOOK =
  "G17C-HOOK (#207): no shared-file wiring — no layers ship, verdicts + dims only.";
