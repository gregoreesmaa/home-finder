// Group 1 listing-portal verdicts, batch A (parameters3.md §5.1, issue #202):
// p1 purchase price, p5 utility costs, p22 bedrooms, p23 bathrooms,
// p24 floor plan flow, p25 kitchen, p26 workspace, p27 storage,
// p28 parking/garage, p32 move-in readiness, p36 finishes,
// p37 outdoor living, p39 smart home, p92 primary suite,
// p93 laundry, p94 mudroom, p99 flex space, p109 gear storage,
// p110 outdoor kitchen, p119 backup heating.
//
// VERDICT: all twenty are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group01a.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 batch-B file shape) and lands + tests green on its own.
//
// WHY no layer ships (evidence: parameters3.md §5.1 Group 1 is Tier 1
// scraped/ingested syndication — KV.ee, City24, Kinnisvara24, broker
// KVXML feeds, broker-NLP extraction):
// * Every param in this batch describes ONE listing — its price, its
//   floorplan, its kitchen — never the area around it. The OSM
//   snapshot carries no area signal that discriminates per-listing
//   facts, so any gradient would paint buyer-relevant differences
//   (this flat's garage vs that flat's none) flat — a useless map.
// * p28 parking is the closest call: OSM maps parking lots, but area
//   parking density says nothing about whether THIS listing includes
//   a garage or reserved spot — a proxy would mislead, so it stays a
//   per-listing dim with a kuulutus-check reason.
// * p1/p5 stay mapless even though Maa-amet transaction data exists in
//   principle: it is not in the snapshot, and past area sales are not
//   this listing's asking price or utility bill.
// * All twenty dims return NULL with an Estonian buyer-check reason
//   (hinnang + EI OLE): the buyer checks the kuulutus, the
//   korruseplaan, the photos, or the broker — never the map.
//
// G01A-HOOK (#202): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP01A_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group01a.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP01A_ALL_PARAMS = [
  1, 5, 22, 23, 24, 25, 26, 27, 28, 32, 36, 37, 39, 92, 93, 94, 99, 109,
  110, 119,
] as const;

export type Group01AParam = (typeof GROUP01A_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP01A_SHIPPED_PARAMS: readonly Group01AParam[] = [];

export interface Group01AVerdict {
  /** parameters3.md parameter number. */
  param: Group01AParam;
  /** Scorer dim in services/scoring/dims_group01a.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP01A_NO_MAP: Group01AVerdict[] = [
  {
    param: 1,
    dim: "dim_purchase_price",
    nearestMap: "puudub — tehinguandmed (Maa-amet) pole snapshotis",
    reason:
      "Ostuhind on kuulutuse-fakt, millele snapshotis piirkonna-signaali " +
      "pole (EI OLE hinnangut): võrdle kuulutuse hinda Maa-ameti " +
      "tehinguandmete ja maakleri KOV-tabeliga, ära feigi.",
  },
  {
    param: 5,
    dim: "dim_utility_costs",
    nearestMap: "puudub — KÜ eelarved pole snapshotis",
    reason:
      "Kõrvalkulud on kuulutuse-fakt (KÜ eelarve / kommunaalide väljavõte), " +
      "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): " +
      "küsi maaklerilt viimase 12 kuu arveid, ära feigi.",
  },
  {
    param: 22,
    dim: "dim_bedrooms",
    nearestMap: "puudub — korruseplaanid pole snapshotis",
    reason:
      "Magamistubade arv on korruseplaani fakt, millele snapshotis " +
      "piirkonna-signaali pole (EI OLE hinnangut): loe tubade arv " +
      "kuulutuse plaanilt, mitte naabruskonna kaardilt, ära feigi.",
  },
  {
    param: 23,
    dim: "dim_bathrooms",
    nearestMap: "puudub — korruseplaanid pole snapshotis",
    reason:
      "Vannitubade arv on korruseplaani fakt, millele snapshotis " +
      "piirkonna-signaali pole (EI OLE hinnangut): kontrolli " +
      "sanitaarruumide arvu kuulutuse plaanilt ja fotodelt, ära feigi.",
  },
  {
    param: 24,
    dim: "dim_floor_plan_flow",
    nearestMap: "puudub — plaanilahendusi kaart ei hinda",
    reason:
      "Plaanilahenduse voolavus on maakleri-NLP kuulutuse-põhine hinne, " +
      "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): " +
      "hinda läbikäidavust kohapeal plaaniga käes, ära feigi.",
  },
  {
    param: 25,
    dim: "dim_kitchen",
    nearestMap: "puudub — köökide sisu kaart ei näita",
    reason:
      "Köögi funktsionaalsus on kuulutuse-põhine hinne (seadmed, " +
      "tööpinnad, paigutus), millele snapshotis piirkonna-signaali pole " +
      "(EI OLE hinnangut): kontrolli fotodelt ja kohapeal, ära feigi.",
  },
  {
    param: 26,
    dim: "dim_workspace",
    nearestMap: "puudub — tubade kasutus kaart ei näita",
    reason:
      "Eraldi tööruumi olemasolu on kuulutuse-fakt, millele snapshotis " +
      "piirkonna-signaali pole (EI OLE hinnangut): otsi plaanilt " +
      "suletavat kabinetti/kontorinurka, ära feigi.",
  },
  {
    param: 27,
    dim: "dim_storage",
    nearestMap: "puudub — panipaigad pole snapshotis",
    reason:
      "Hoiuruumi maht (panipaik, garderoob, sahver) on kuulutuse-fakt, " +
      "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): " +
      "küsi panipaiga m2 kuulutusest, ära feigi.",
  },
  {
    param: 28,
    dim: "dim_parking",
    nearestMap: "puudub — parklate kaart ei tõlgi SELLE kuulutuse kohta",
    reason:
      "Parkimine/garaaž on kuulutuse-fakt (koha number, hind ja " +
      "omandivorm), millele snapshotis ausat piirkonna-signaali pole " +
      "(EI OLE hinnangut): kaardistatud parklad ei tõlgi, kas SELLES " +
      "kuulutuses on koht, ära feigi.",
  },
  {
    param: 32,
    dim: "dim_move_in_readiness",
    nearestMap: "puudub — seisukorda kaart ei hinda",
    reason:
      "Sissekolimise valmidus on kuulutuse-põhine seisukorra hinne, " +
      "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): " +
      "hinda remondivajadust fotode ja kohapealse ülevaatusega, ära feigi.",
  },
  {
    param: 36,
    dim: "dim_finishes",
    nearestMap: "puudub — materjale kaart ei näita",
    reason:
      "Viimistluse kvaliteet on foto/külastuse fakt, millele snapshotis " +
      "piirkonna-signaali pole (EI OLE hinnangut): hinda materjale " +
      "fotodelt ja kohapeal, ära feigi.",
  },
  {
    param: 37,
    dim: "dim_outdoor_living",
    nearestMap: "puudub — rõdude/terrasseside omand kaart ei näita",
    reason:
      "Õue-eluruum (rõdu, terrass, aed) on kuulutuse-fakt, millele " +
      "snapshotis piirkonna-signaali pole (EI OLE hinnangut): kontrolli " +
      "pinna m2 ja orientatsiooni kuulutusest, ära feigi.",
  },
  {
    param: 39,
    dim: "dim_smart_home",
    nearestMap: "puudub — seadmeid kaart ei näita",
    reason:
      "Nutikodu funktsioonid on kuulutuse-fakt, millele snapshotis " +
      "piirkonna-signaali pole (EI OLE hinnangut): küsi seadmete " +
      "nimekirja ja juhtimisplatvormi maaklerilt, ära feigi.",
  },
  {
    param: 92,
    dim: "dim_primary_suite",
    nearestMap: "puudub — korruseplaanid pole snapshotis",
    reason:
      "Magamistoa eraldatus (oma vannituba/garderoob) on korruseplaani " +
      "fakt, millele snapshotis piirkonna-signaali pole (EI OLE " +
      "hinnangut): loe plaanilt privaatsust, ära feigi.",
  },
  {
    param: 93,
    dim: "dim_laundry",
    nearestMap: "puudub — korruseplaanid pole snapshotis",
    reason:
      "Pesuruumi paigutus on korruseplaani fakt, millele snapshotis " +
      "piirkonna-signaali pole (EI OLE hinnangut): otsi plaanilt " +
      "eraldi pesuruumi või -nurka, ära feigi.",
  },
  {
    param: 94,
    dim: "dim_mudroom",
    nearestMap: "puudub — korruseplaanid pole snapshotis",
    reason:
      "Esiku/porandaruumi üleminek on korruseplaani fakt, millele " +
      "snapshotis piirkonna-signaali pole (EI OLE hinnangut): hinda " +
      "esiku suurust ja porandavahet plaanilt, ära feigi.",
  },
  {
    param: 99,
    dim: "dim_flex_space",
    nearestMap: "puudub — abihoonete kasutus kaart ei näita",
    reason:
      "Paindlik lisa-pind (kõrvalhooned, abihooned) on kuulutuse-fakt, " +
      "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): " +
      "kontrolli abihoonete registriandmeid ja kuulutuse loetelu, " +
      "ära feigi.",
  },
  {
    param: 109,
    dim: "dim_gear_storage",
    nearestMap: "puudub — garaažide mõõdud pole snapshotis",
    reason:
      "Rasketehnika hoiustamise võimalus on kuulutuse-fakt, millele " +
      "snapshotis piirkonna-signaali pole (EI OLE hinnangut): küsi " +
      "garaaži kõrgust, uste laiust ja kandevõimet, ära feigi.",
  },
  {
    param: 110,
    dim: "dim_outdoor_kitchen",
    nearestMap: "puudub — õue kommunikatsioone kaart ei näita",
    reason:
      "Väliköögi potentsiaal on kuulutuse-fakt (õue suurus, vesi, elekter), " +
      "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): " +
      "kontrolli kommunikatsioonide olemasolu õuealal, ära feigi.",
  },
  {
    param: 119,
    dim: "dim_backup_heating",
    nearestMap: "puudub — küttesüsteemid pole snapshotis",
    reason:
      "Varukütte allikad (ahi, kamin, generaator) on kuulutuse-fakt, " +
      "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): " +
      "küsi küttesüsteemide nimekirja ja hoolduslugu, ära feigi.",
  },
];

/**
 * Structural facts backing the verdicts (no snapshot area signal exists
 * for per-listing facts by construction — Group 1 is Tier 1
 * scraped/ingested syndication per parameters3.md §5.1, not geospatial):
 * groupTotal 40 Group 1 params, batchOwns 20 here, snapshotSignals 0.
 */
export const GROUP01A_EVIDENCE = {
  groupTotal: 40,
  batchOwns: 20,
  snapshotSignals: 0,
} as const;

/**
 * OSM tags evaluated per param: none — per-listing facts have no honest
 * snapshot query (documents the absence for the record; the NULL dims
 * need no live-path wiring — the app serves the frozen snapshot, never
 * live Overpass).
 */
export const GROUP01A_CONSIDERED_TAGS: Record<Group01AParam, string> = {
  1: "(puudub — ostuhind on kuulutuse-fakt, snapshotis pole)",
  5: "(puudub — kõrvalkulud on kuulutuse-fakt, snapshotis pole)",
  22: "(puudub — tubade arv on plaani-fakt, snapshotis pole)",
  23: "(puudub — tubade arv on plaani-fakt, snapshotis pole)",
  24: "(puudub — plaanihinne on kuulutuse-fakt, snapshotis pole)",
  25: "(puudub — köögihinne on kuulutuse-fakt, snapshotis pole)",
  26: "(puudub — tööruum on kuulutuse-fakt, snapshotis pole)",
  27: "(puudub — hoiuruum on kuulutuse-fakt, snapshotis pole)",
  28: "(puudub — p28 lähim-kaalutlus tagasi lükatud: ala parklad ei tõlgi kuulutuse kohta)",
  32: "(puudub — seisukorrahinne on kuulutuse-fakt, snapshotis pole)",
  36: "(puudub — viimistlus on foto-fakt, snapshotis pole)",
  37: "(puudub — õue-eluruum on kuulutuse-fakt, snapshotis pole)",
  39: "(puudub — nutiseadmed on kuulutuse-fakt, snapshotis pole)",
  92: "(puudub — eraldatus on plaani-fakt, snapshotis pole)",
  93: "(puudub — paigutus on plaani-fakt, snapshotis pole)",
  94: "(puudub — esik on plaani-fakt, snapshotis pole)",
  99: "(puudub — lisapind on kuulutuse-fakt, snapshotis pole)",
  109: "(puudub — hoiutingimus on kuulutuse-fakt, snapshotis pole)",
  110: "(puudub — väliköök on kuulutuse-fakt, snapshotis pole)",
  119: "(puudub — küttesüsteem on kuulutuse-fakt, snapshotis pole)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP01A_HOOK =
  "G01A-HOOK (#202): no shared-file wiring — no layers ship, verdicts + dims only.";
