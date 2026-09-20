// Per-asum asking-price medians from OWN listing snapshots (issue #495).
//
// ONE layer ("asumedia"): the median €/m² asking price per Tallinn asum
// (linnaosa-subdistrict), derived ONLY from the repo's own 17-adapter
// snapshot store — no external price source, no invented medians. The
// map twin of the scorer kernel in
// services/scoring/dims_p4_own_asum.py (same MIN_N, same thin→NULL rule,
// pinned by the parity test below). This file owns ALL asumedia runtime
// data; shared files (lib/layers.ts, lib/overlays.ts, the [layer]
// route) touch it only through small marked `ASUMEDIA-HOOK (#495)`
// blocks, so sibling batches stay disjoint. This module imports
// ./layers ONLY as types: no runtime cycle.
//
// VERDICT (Group B verify-first, tallied 2026-09-14 from real repo
// content — commands in ASUMEDIA_VERDICT, re-runnable, no network):
// DATED NEGATIVE — no choropleth ships. Per-asum N is nowhere near
// sufficient AND the asum join key does not exist yet:
// * 30 parsed adapter-fixture records (15 adapters × 2, kv fixture via
//   kv_ee.parse_search_html) → 26 with price+area, 13 Tallinn-usable —
//   and ZERO carry an `asum` key (the adapter record schema has none).
// * Portal addresses sit at street+locality grain ("Sireli tee 4,
//   Haiba, Saue vald"; "Kopli tn 61, Põhja-Tallinna linnaosa,
//   Tallinn") — linnaosa at best, never a stable asum key. Free-text
//   asum mentions ("... Kalamaja, Telliskivi 49") are not an exact
//   join (statkov #485 identity-join-or-NULL precedent).
// * No Tallinn asum polygons are vendored anywhere (84 asums; no
//   admin_level=10 extract, no 84-row table) and the listings schema
//   (db/init.sql) has no asum column — so even geocoded snapshots
//   (Photon lat/lon via livability.resolve) cannot join today.
// * Bar: ASUMEDIA_MIN_N = 5 per asum (Land Board publication ≥5 per
//   settlement precedent — asking prices are noisier than closed
//   deals, so the strict bar, not the micro ≥3). 84 asums × 5 needs
//   hundreds of accumulated geocoded Tallinn snapshots; page-1 polite
//   pulls + fixtures-only commits (AGENTS.md §5) cannot supply that.
// So the measured set below is EMPTY ON PURPOSE and the layer renders
// the whole field unknown (never zero, never a fake median) until the
// reopen PR lands real per-asum N (see the checklist).
//
// HONESTY (load-bearing):
// * Titles, legends and sources say "ootel" + "hinnang" and name the
//   dated tally with its date; thin asums stay NULL with the reason
//   labeled (never fake precision — no bands are calibrated off
//   fixtures, so there is no band table here to drift).
// * paramIds stays [] (no parameters3 number claimed): the asking-
//   median leg is distinct from P4-002 closed-deal micro-comps
//   (dims_p4_maa_tehingud.py, restricted bulk → production NULL) and
//   from P4-038 bargaining margin (needs the Maa-amet gap table) —
//   painting own asking medians as either score would double-count
//   P4-001's per-listing drop in the steal sort.
// * fallbackPoints is EMPTY by decision (planktpr #492 precedent): a
//   demo point would paint a fake gradient splat on a future exact-
//   fill choropleth. The generic labels test carves this layer out
//   (see layers.test.ts).
// * NO bands, NO calibration: with zero qualifying asums any band
//   table would be fixture fiction. The reopen PR calibrates bands
//   off the real accumulated store, not off these fixtures.
// * #807 DORMANT verdict (2026-09-20): the cover kernel is the RIGHT
//   kernel (exact-fill choropleth when data lands) but the set is
//   empty, so the whole field stays unknown — dormant, not unscorable.
//   Revisit at reopen; no spec change needed then.
//
// Overlap (documented, same grain different question):
// dims_p4_maa_tehingud.py already joins per-ASUM off Maa-amet CLOSED
// deals (P4-025/044/050 legs, MIN_COMPS = 3, production NULL behind
// the restricted bulk). Those answer "closed-deal truth in this
// asum"; this layer will answer "live asking level in this asum".
// Same join SHAPE, disjoint sources — the rebalance follow-up must
// weight only one leg per question.

import type { BonusSpec, LayerDef } from "./layers";

export type AsumediaLayerId = "asumedia";

export const ASUMEDIA_LAYER_IDS: AsumediaLayerId[] = ["asumedia"];

/**
 * Minimum snapshots per asum for an honest median (Land Board
 * publications ≥5/deals-per-settlement precedent — asking prices are
 * noisier than closed deals, so the strict bar, not the micro ≥3).
 * Byte parity with MIN_N in services/scoring/dims_p4_own_asum.py
 * (pinned by the parity tests on both sides).
 */
export const ASUMEDIA_MIN_N = 5;

/** Tallinn asum count (linnaosa-subdistricts; join target on reopen). */
export const ASUMEDIA_TALLINN_ASUMS = 84;

/**
 * Dated verify-first tally this negative rests on (re-tally command —
 * hermetic, no network — from the repo root):
 *   python3 /tmp/hf495_tally.py  (throwaway; see issue #495 for output)
 * which parses every adapter fixture with that adapter's own
 * parse_search entry point. A re-tally that changes these counts
 * forces an intentional edit here (drift-pinned by test).
 */
export const ASUMEDIA_VERDICT = {
  date: "2026-09-14",
  fixtureRecords: 30,
  fixtureUsable: 26,
  fixtureWithAsumKey: 0,
  fixtureTallinnUsable: 13,
  asumsAtMinN: 0,
} as const;

const TALLY =
  `oma snapshotite loendus ${ASUMEDIA_VERDICT.date}: ` +
  `${ASUMEDIA_VERDICT.fixtureRecords} adapteri-fixture kirjet, ` +
  `${ASUMEDIA_VERDICT.fixtureUsable} hinna+pinnaga, ` +
  `${ASUMEDIA_VERDICT.fixtureTallinnUsable} Tallinnas — ` +
  `${ASUMEDIA_VERDICT.fixtureWithAsumKey} asumivõtmega, ` +
  `${ASUMEDIA_VERDICT.asumsAtMinN}/${ASUMEDIA_TALLINN_ASUMS} asumi ` +
  `MIN_N=${ASUMEDIA_MIN_N} täis`;

export const ASUMEDIA_DEFS: LayerDef[] = [
  {
    id: "asumedia",
    paramIds: [],
    title: "Asumite küsi-mediaanid oma snapshotitest (ootel — hinnang)",
    goodLabel:
      "roheline = asumi küsi-mediaan madal (praegu: ükski asum MIN_N-i täis pole, kogu väli teadmata)",
    badLabel:
      "punane = asumi küsi-mediaan kõrge VÕI andmed puuduvad (praegu: alati teadmata — EI OLE)",
    source:
      `Oma 17 adapteri snapshotid (P4-002/038-kõrvalne küsitaseme jalg, ` +
      `mitte sulgunud tehingud): ${TALLY}. Adapterikirjetel asumivõtit ` +
      `pole (tänav+linnaosa-täpsus) ja Tallinna 84 asumi polügoone repos ` +
      `pole — täpsust ei võltsita, õhukese N-iga asumeid EI FEIGITA. ` +
      `Korduskontroll: geokodeeritud snapshotite kogum + asumiliide`,
    // EMPTY by decision (see header): no honest demo medians exist —
    // the client renders the empty field, never faked fills.
    fallbackPoints: [],
  },
];

/**
 * Empty-state status line for the /layers page (issue #786). The
 * route serves provenance "empty" for asumedia, and the page's
 * generic empty copy ("Selle piirkonna kohta väljavõttes andmed
 * puuduvad") cannot distinguish "pending by design" from "no
 * viewport coverage" — so this names the dated tally + the reopen
 * path instead. Built from ASUMEDIA_VERDICT / ASUMEDIA_MIN_N /
 * ASUMEDIA_TALLINN_ASUMS so the counts cannot drift from the pinned
 * tally (drift-pinned by test).
 */
export function asumediaEmptyStatus(): string {
  return (
    `Ootel-hinnang (${ASUMEDIA_VERDICT.date} loendus: ` +
    `${ASUMEDIA_VERDICT.fixtureRecords} kirjet, ` +
    `${ASUMEDIA_VERDICT.fixtureWithAsumKey} asumivõtmega, ` +
    `${ASUMEDIA_VERDICT.asumsAtMinN}/${ASUMEDIA_TALLINN_ASUMS} asumi ` +
    `MIN_N=${ASUMEDIA_MIN_N} täis) — taasavab: geokodeeritud ` +
    `snapshotid + Tallinna ${ASUMEDIA_TALLINN_ASUMS} asumi polügoonid; ` +
    `õhukese N-iga asumeid EI FEIGITA`
  );
}

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the future join
 * is geocoded snapshot coords × vendored asum polygons (neither
 * vendored today), never a live Overpass query — overpassQueryFor
 * ("asumedia") is never called in production (senscom precedent).
 */
export const ASUMEDIA_TAGS: Record<AsumediaLayerId, string> = {
  asumedia:
    "Oma snapshotite store (17 adapterit, päevane korje, fixtures only): " +
    "asumivõti puudub — taasavamise liide on geokodeeritud koordinaadid × " +
    "Tallinna 84 asumi polügoonid (mõlemad hetkel OOTEL, serveeritakse " +
    "külgfailist, mitte elusalt)",
};

/**
 * Fallback kernel width in km (== wire sigma). The fills themselves
 * will be exact joins with no kernel; this only sizes the Euclidean
 * fallback if points ever appear (mobile/"cover" precedent). INERT
 * today (empty set — pinned by test).
 */
export const ASUMEDIA_DECAY: Record<AsumediaLayerId, number> = {
  asumedia: 0.5,
};

/**
 * Self-scaling cover spec (mobile precedent): future per-asum medians
 * carry their own value (no half); sigma is the Euclidean fallback
 * kernel width. Contract-checked against the wire (half null, sigma
 * 0.5) by loadLayerRaster. INERT today (empty set, no raster).
 */
export const ASUMEDIA_BONUS: Record<AsumediaLayerId, BonusSpec> = {
  asumedia: { kind: "cover", sigma: 0.5 },
};

/** One per-asum median row (the reopen PR fills this from the store). */
export interface AsumediaRow {
  /** Asum name as joined (exact key — free-text guesses never join). */
  asum: string;
  /** Median €/m² asking price over the grouped snapshots. */
  medianEurM2: number;
  /** Snapshots grouped into this median (must reach ASUMEDIA_MIN_N). */
  n: number;
}

/**
 * Measured per-asum medians (EMPTY ON PURPOSE — see the verdict
 * above: 0/84 asums reach MIN_N=5). The reopen PR fills this from the
 * accumulated snapshot store via dims_p4_own_asum.py; until then the
 * route serves [] with provenance "empty".
 */
export const ASUMEDIA_MEASURED: AsumediaRow[] = [];

/**
 * Median €/m² over one asum's grouped snapshot values. Null when the
 * group is empty or holds no finite positive value — an empty group
 * is unknown, never zero. The MIN_N gate lives with the caller (the
 * Python kernel applies it per asum; the map only paints gated rows).
 */
export function asumediaMedianEurM2(values: number[]): number | null {
  const xs = values.filter((v) => typeof v === "number" && Number.isFinite(v) && v > 0);
  if (xs.length === 0) return null;
  const sorted = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * Gate one asum's median behind ASUMEDIA_MIN_N: (median, n) when the
 * group is thick enough, (null, n) when thin — thin stays NULL with
 * its n labeled, never a faked median.
 */
export function asumediaGatedMedian(
  values: number[],
): { median: number | null; n: number } {
  const xs = values.filter((v) => typeof v === "number" && Number.isFinite(v) && v > 0);
  if (xs.length < ASUMEDIA_MIN_N) return { median: null, n: xs.length };
  return { median: asumediaMedianEurM2(xs), n: xs.length };
}

/** Raster master filename (intentionally never built — see below). */
export const ASUMEDIA_RASTER_FILE: Record<AsumediaLayerId, string> = {
  asumedia: "asumedia-walk-raster.json",
};

/**
 * NO raster master (documented): with zero qualifying asums there is
 * no field to bake — a no-data raster would be fake precision. The
 * window route serves 500 for this layer and the client falls back to
 * the empty field (designed path, planktpr #492 precedent). NO metro
 * master either (county-only windows, G05C/G17A precedent).
 */
export const ASUMEDIA_NO_RASTER = true;
export const ASUMEDIA_NO_METRO = true;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isAsumediaLayerId(layer: string): layer is AsumediaLayerId {
  return (ASUMEDIA_LAYER_IDS as string[]).includes(layer);
}

/**
 * Asumedia bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForAsumedia(layer: string): BonusSpec | undefined {
  return (ASUMEDIA_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * Reopen checklist (judgment calls, reviewable): real per-asum N from
 * the accumulated store (≥MIN_N in ≥1 asum) + vendored 84-asum
 * polygons + geocoded snapshot coords; calibrate bands off the REAL
 * store (never these fixtures); wire the sidecar + fills; flip this
 * verdict with a fresh tally date. A single deal never sets a
 * "median" (tehingud MIN_COMPS precedent).
 */
export const ASUMEDIA_REOPEN =
  "Taasavamise latt (#495): kogunenud geokodeeritud snapshotid " +
  "(≥MIN_N samas asumis) + 84 asumi polügoonid + päris-store'ilt " +
  "kalibreeritud bändid; seni tühi teadlikult.";

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const ASUMEDIA_HOOK =
  "ASUMEDIA-HOOK (#495): asumedia wired into layers/overlays/snapshot/route; own-snapshot asking medians, dated negative 2026-09-14 (0/84 asums at MIN_N=5), empty-on-purpose.";
