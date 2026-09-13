// Group 4 title/legal verdicts (parameters3.md §5.4, issue #204):
// p76 mineral/water/timber rights, p80 deed covenants (non-HOA),
// p139 property stigma, p144 title cleanliness, p229 mineral right
// severances, p242 stigmatized property laws, p248 existing lease
// encumbrances, p271 view preservation covenants, p274 air rights,
// p276 adverse possession risks, p279 morals clauses in deeds,
// p361 trust/LLC transferability, p362 probate/estate sale delays,
// p364 ground lease realities, p367 squatter/holdover laws,
// p369 co-op board approval, p428 title cloud resolution.
//
// VERDICT: all seventeen are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group04.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3-B file shape, #152) and lands + tests green on its own.
//
// WHY no layer ships (evidence, verified 2026-09-13 against the local
// Harjumaa PBF ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf — no
// network; see GROUP04_EVIDENCE):
// * Every param in this batch is a per-parcel legal/registry fact whose
//   primary source is e-Kinnistusraamat (RIK X-Road / commercial portal,
//   Tier 2 PAID registry — parameters3.md §5.4): it is NOT in the OSM
//   snapshot by construction, same precedent as p71 servitudes and p75
//   boundary clarity (#151, both no-map NULL dims). An area gradient
//   cannot resolve a parcel's title question — it would reward/penalise
//   homes on a legal fact it cannot see.
// * The snapshot carries ZERO deed/lien/mortgage/lease/covenant keys
//   county-wide (osmium tags-count, 2627 distinct keys scanned): there
//   is literally no tag family to calibrate any of the 17 against.
// * The only owner-ish keys are 13 owner=* + 1 ownership=* against
//   7710 institutional operator=* (schools, utilities, transit): owner
//   tags mark managed facilities, never parcel title — a gradient from
//   "near an operator-tagged object" would red-pen homes on a deed
//   question it cannot resolve, so all 17 stay NULL per-listing dims
//   with a kinnistusraamat/notary buyer check — ära feigi.
// * p139/p242 (stigma) are per-parcel history + statute facts: no
//   incident archive is in the snapshot, and a crime-proximity gradient
//   would brand whole streets on unproven history. p362 (probate
//   delays) needs Ametlikud Teadaanded notices, likewise not in the
//   snapshot. p248/p361/p364 (lease/trust/ground-lease) need the
//   registry extract + e-Äriregister pledge check, never area geometry.
//
// G04-HOOK (#204): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP04_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group04.py.
//
// Param-name note: §5.4 truncates several names in the table ("Mineral,
// water, and timber r", "Trust and LLC transferabi", ...); full names
// below are reconstructed from the DB column names in the same table
// rows (e.g. p76_mineral_water_and_timber_r -> "... rights").

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP04_ALL_PARAMS = [
  76, 80, 139, 144, 229, 242, 248, 271, 274, 276, 279, 361, 362, 364, 367,
  369, 428,
] as const;

export type Group04Param = (typeof GROUP04_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP04_SHIPPED_PARAMS: readonly Group04Param[] = [];

export interface Group04Verdict {
  /** parameters3.md parameter number. */
  param: Group04Param;
  /** Scorer dim in services/scoring/dims_group04.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP04_NO_MAP: Group04Verdict[] = [
  {
    param: 76,
    dim: "dim_mineral_timber_rights",
    nearestMap: "puudub — maavaraõiguste kaarti snapshots pole",
    reason:
      "Maavara-, vee- ja puiduõigused on krundi-põhine registrifakt " +
      "(hinnang, p71 servituudi pretsedent #151): e-Kinnistusraamatu " +
      "väljavõtet snapshots pole (EI OLE hinnangut) ja OSM-is pole ühtki " +
      "deed/lien/mortgage-märgendit. Dim jääb NULLiks " +
      "kinnistusraamatu/notari kontrolli põhjusega — ära feigi.",
  },
  {
    param: 80,
    dim: "dim_deed_covenants",
    nearestMap: "puudub — kitsenduste kaarti snapshots pole",
    reason:
      "Kinnistusraamatu kitsendused (mitte-ühistu) on krundi-põhine " +
      "juriidiline fakt (hinnang, p71 pretsedent #151): covenant-märgendeid " +
      "snapshots pole (EI OLE hinnangut), KKIS kitsendusi OSM-is pole. " +
      "Dim jääb NULLiks kinnistusraamatu väljavõtte kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 139,
    dim: "dim_property_stigma",
    nearestMap: "puudub — stigma ajalugu on krundi-, mitte piirkonnafakt",
    reason:
      "Kinnisvara stigma (surm/kuritegu/kuulsus) on krundi-põhine " +
      "ajaloofakt (hinnang): juhtumi-arhiivi snapshots pole (EI OLE " +
      "hinnangut) ja kuriteo-läheduse gradient brändiks terve tänava " +
      "tõestamata ajalooga. Dim jääb NULLiks müüja/notari " +
      "avaldamis-kontrolli põhjusega — ära feigi.",
  },
  {
    param: 144,
    dim: "dim_title_cleanliness",
    nearestMap: "puudub — omandi puhtuse kaarti snapshots pole",
    reason:
      "Omandi puhtus (koormatised, vaidlused, pandiõigused) on " +
      "krundi-põhine registrifakt (hinnang, p71 pretsedent #151): " +
      "e-Kinnistusraamatu päringut snapshots pole (EI OLE hinnangut). " +
      "Dim jääb NULLiks notari õigusauditi kontrolli põhjusega — " +
      "ära feigi.",
  },
  {
    param: 229,
    dim: "dim_mineral_severance",
    nearestMap: "puudub — maavara eraldamiste kaarti snapshots pole",
    reason:
      "Maavaraõiguste eraldamine krundist on krundi-põhine registrifakt " +
      "(hinnang, p71 pretsedent #151): eraldamis-märgendeid snapshots " +
      "pole (EI OLE hinnangut). Dim jääb NULLiks kinnistusraamatu " +
      "väljavõtte kontrolli põhjusega — ära feigi.",
  },
  {
    param: 242,
    dim: "dim_stigma_laws",
    nearestMap: "puudub — stigma-seadused on statuut, mitte kaardikiht",
    reason:
      "Stigmatiseeritud kinnisvara avaldamiskohustus on krundi-põhine " +
      "õigusfakt (hinnang): statuudi sisu snapshots pole (EI OLE " +
      "hinnangut) ja piirkonna-gradient ei lahenda ühegi krundi " +
      "avaldamisküsimust. Dim jääb NULLiks notari/õigusnõu kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 248,
    dim: "dim_lease_encumbrance",
    nearestMap: "puudub — üürikoormatiste kaarti snapshots pole",
    reason:
      "Kehtivad üüri-/rendikoormatised on krundi-põhine registrifakt " +
      "(hinnang, p71 pretsedent #151): lease-märgendeid snapshots pole " +
      "(EI OLE hinnangut). Dim jääb NULLiks kinnistusraamatu väljavõtte " +
      "ja üürilepingu kontrolli põhjusega — ära feigi.",
  },
  {
    param: 271,
    dim: "dim_view_covenant",
    nearestMap: "puudub — vaate-kitsendused on leping, mitte kõrgusmudel",
    reason:
      "Vaate säilitamise kitsendus on krundi-põhine lepingufakt " +
      "(hinnang, p71 pretsedent #151): kitsenduse teksti snapshots pole " +
      "(EI OLE hinnangut) — kõrgusmudel näitab, mis täna paistab, mitte " +
      "mis on keelatud ehitada. Dim jääb NULLiks kinnistusraamatu " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 274,
    dim: "dim_air_rights",
    nearestMap: "puudub — õhuõiguste kaarti snapshots pole",
    reason:
      "Õhuõigused (ehitusõigus krundi kohal) on krundi-põhine " +
      "registrifakt (hinnang, p71 pretsedent #151): õhuõiguse-märgendeid " +
      "snapshots pole (EI OLE hinnangut). Dim jääb NULLiks " +
      "kinnistusraamatu/planeeringu kontrolli põhjusega — ära feigi.",
  },
  {
    param: 276,
    dim: "dim_adverse_possession",
    nearestMap: "puudub — igamisriski kaarti snapshots pole",
    reason:
      "Igamisega (adverse possession) omandamise risk on krundi-põhine " +
      "õigusfakt (hinnang): kasutusajaloo tõendeid snapshots pole (EI " +
      "OLE hinnangut). Dim jääb NULLiks kinnistusraamatu ja " +
      "piiri-mõõdistuse kontrolli põhjusega — ära feigi.",
  },
  {
    param: 279,
    dim: "dim_morals_clause",
    nearestMap: "puudub — moraaliklauslid on lepingutekst, mitte kaardikiht",
    reason:
      "Kinnistusraamatu moraaliklauslid on krundi-põhine lepingufakt " +
      "(hinnang): klausli teksti snapshots pole (EI OLE hinnangut). " +
      "Dim jääb NULLiks kinnistusraamatu väljavõtte kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 361,
    dim: "dim_trust_llc_transfer",
    nearestMap: "puudub — usaldus/ühingu-siirde kaarti snapshots pole",
    reason:
      "Usaldusfondi/osaühingu kaudu siirdatavus on krundi-põhine " +
      "õigusfakt (hinnang): omandistruktuuri snapshots pole (EI OLE " +
      "hinnangut). Dim jääb NULLiks notari ja e-Äriregistri kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 362,
    dim: "dim_probate_delay",
    nearestMap: "puudub — pärimismenetluste kaarti snapshots pole",
    reason:
      "Pärimis-/pärandmüügi viivitus on krundi-põhine menetlusfakt " +
      "(hinnang): Ametlike Teadaannete pärimisteateid snapshots pole " +
      "(EI OLE hinnangut). Dim jääb NULLiks Ametlike Teadaannete ja " +
      "notari kontrolli põhjusega — ära feigi.",
  },
  {
    param: 364,
    dim: "dim_ground_lease",
    nearestMap: "puudub — hoonestusõiguse kaarti snapshots pole",
    reason:
      "Hoonestusõiguse/maakasutuse rendi tingimused on krundi-põhine " +
      "registrifakt (hinnang, p71 pretsedent #151): rendilepingu sisu " +
      "snapshots pole (EI OLE hinnangut). Dim jääb NULLiks " +
      "kinnistusraamatu väljavõtte kontrolli põhjusega — ära feigi.",
  },
  {
    param: 367,
    dim: "dim_squatter_holdover",
    nearestMap: "puudub — asustamisvaidluste kaarti snapshots pole",
    reason:
      "Ebaseadusliku asustuse/üürniku-jäämise risk on krundi-põhine " +
      "õigusfakt (hinnang): asustusajalugu snapshots pole (EI OLE " +
      "hinnangut). Dim jääb NULLiks kinnistusraamatu ja kohapealse " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 369,
    dim: "dim_coop_approval",
    nearestMap: "puudub — ühistu-nõusolek on maja-, mitte piirkonnafakt",
    reason:
      "Ühistu juhatuse heakskiit (co-op board) on maja-põhine fakt " +
      "(hinnang): ühistu põhikirja snapshots pole (EI OLE hinnangut). " +
      "Dim jääb NULLiks ühistu/müüja kontrolli põhjusega — ära feigi.",
  },
  {
    param: 428,
    dim: "dim_title_cloud",
    nearestMap: "puudub — omandi-vaidluste kaarti snapshots pole",
    reason:
      "Omandi hägususe (title cloud) lahendatavus on krundi-põhine " +
      "registrifakt (hinnang, p71 pretsedent #151): kohtu-/vaidlusandmeid " +
      "snapshots pole (EI OLE hinnangut). Dim jääb NULLiks notari " +
      "õigusauditi kontrolli põhjusega — ära feigi.",
  },
];

/**
 * Snapshot counts backing the verdicts (osmium tags-count on
 * harjumaa-260911.osm.pbf, 2026-09-13 — no network; key-only
 * nwr/<key> filters select objects carrying that key):
 * deed/lien/mortgage/lease/covenant keys: 0 county-wide (2627 distinct
 * keys scanned) — no tag family exists to calibrate any of the 17.
 * owner 13 + ownership 1 vs institutional operator 7710: the only
 * owner-ish tags mark managed facilities, never parcel title.
 * board:title 146 (signage) + protection_title 41 (heritage) are
 * unrelated name/title strings, not ownership facts.
 */
export const GROUP04_EVIDENCE = {
  deedKeys: 0,
  lienKeys: 0,
  mortgageKeys: 0,
  leaseKeys: 0,
  covenantKeys: 0,
  ownerKeys: 13,
  ownershipKeys: 1,
  operatorKeys: 7710,
} as const;

/**
 * OSM tags evaluated per param and rejected for a gradient map
 * (documents the source tags for the record; the NULL dims need no
 * fetch — the app serves the frozen snapshot, never live Overpass).
 */
export const GROUP04_CONSIDERED_TAGS: Record<Group04Param, string> = {
  76: 'nwr["owner"];nwr["ownership"]; (13 + 1 — asutuste märgendid, registrifakt snapshots pole)',
  80: '(puudub — covenant-märgendeid snapshots pole, KKIS kitsendusi OSM-is pole)',
  139: "(puudub — juhtumi-arhiiv snapshots pole, lähedus-gradient brändiks tänava)",
  144: 'nwr["owner"];nwr["ownership"]; (13 + 1 — omandi puhtust ei kodeeri, e-Kinnistusraamat snapshots pole)',
  229: "(puudub — maavara-eraldamise märgendeid snapshots pole)",
  242: "(puudub — statuut, mitte kaardikiht; kaardisignaali snapshots pole)",
  248: "(puudub — lease-märgendeid snapshots pole)",
  271: "(puudub — kitsenduse tekst snapshots pole; kõrgusmudel ei asenda lepingut)",
  274: "(puudub — õhuõiguse märgendeid snapshots pole)",
  276: "(puudub — kasutusajaloo tõendid snapshots pole)",
  279: "(puudub — klausli tekst snapshots pole)",
  361: "(puudub — omandistruktuur snapshots pole, e-Äriregister OSM-is pole)",
  362: "(puudub — Ametlikud Teadaanded snapshots pole)",
  364: "(puudub — rendilepingu sisu snapshots pole)",
  367: "(puudub — asustusajalugu snapshots pole)",
  369: "(puudub — ühistu põhikiri snapshots pole)",
  428: 'nwr["owner"];nwr["ownership"]; (13 + 1 — vaidlusi ei kodeeri, kohtuandmed snapshots pole)',
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP04_HOOK =
  "G04-HOOK (#204): no shared-file wiring — no layers ship, verdicts + dims only.";
