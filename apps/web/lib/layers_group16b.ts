// Group 16 macro/finance-B verdicts (parameters3.md §5.16, issue #206):
// p241 attractive-nuisance liability, p243 flood-insurance caps,
// p249 transferable solar leases, p250 conservation tax credits,
// p318 unfunded municipal pension liability, p363 1031-exchange
// eligibility, p366 tax abatement expirations, p370 flip/transfer tax,
// p421 appraisal gap risk, p422 supplemental tax bills, p423 special
// assessment districts, p424 PMI cancellation threshold, p425
// energy-efficient mortgage, p426 capital gains exclusions, p430
// escrow buffer requirements, p444 summer tourist influx, p481 street
// price ceiling, p482 corporate ownership density, p483 shadow
// inventory, p484 absorption rate, p486 land-to-improvement ratio,
// p487 demographic transition.
//
// VERDICT: all twenty-two are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group16b.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 file shape, #152) and lands + tests green on its own.
//
// WHY no layer ships (evidence, reviewed 2026-09-13 against the
// parameters3.md §5.16 spec + the 2026-09-12 snapshot contract):
// * Every param in this batch is a deal-, parcel- or registry-level
//   fact, a market-WIDE series, or a foreign-jurisdiction concept with
//   no Estonian equivalent — none of them varies across the map in a
//   way the frozen OSM snapshot can honestly discriminate:
//   - Per-deal / per-parcel / per-borrower facts (p241 liability
//     exposure, p249/p250/p425/p426 contract & tax-credit terms,
//     p363/p366/p370/p422/p424/p430 closing & loan terms, p421
//     appraisal gap, p481 street ceiling vs the subject listing):
//     these attach to the transaction or the property, not to an area.
//   - Registry / policy facts (p243 flood-insurance caps need the
//     insurer tariff tables, p318 KOV pension books, p423 the
//     erihoonestusõiguse/eritasude register): zero snapshot signal
//     exists by construction.
//   - Market-WIDE series (p482/p483/p484/p486/p487 Maa-amet tehingud
//     aggregates, Statistikaamet HH01/KK11, ECB Euribor): one value for
//     the whole market. Painting a city-wide constant as a gradient
//     would be fake precision — a flat colour is not a map.
//   - Foreign-jurisdiction concepts (p363 US 1031 exchange, p424 US
//     PMI, p425 US EEM, p426 US capital-gains exclusion, p370 US
//     flip-tax): no Estonian register holds them; the honest verdict
//     is NULL with a notary/bank check, not a proxy.
//   - p444 summer tourist influx is a seasonal market-wide pulse
//     (Statistikaamet majutusstatistika), not a place-varying signal
//     the snapshot can calibrate — and a static gradient would punish
//     Old-Town-adjacent homes for a June–August effect.
// * Painting any of these from OSM amenity density would re-skin a
//   sibling layer while answering a question the tags cannot resolve
//   (same precedent as p71 easements / p228 riparian rights, #151 /
//   #152 no-map): so every dim stays per-listing NULL.
//
// G16B-HOOK (#206): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP16B_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group16b.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP16B_ALL_PARAMS = [
  241, 243, 249, 250, 318, 363, 366, 370, 421, 422, 423, 424, 425, 426,
  430, 444, 481, 482, 483, 484, 486, 487,
] as const;

export type Group16BParam = (typeof GROUP16B_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP16B_SHIPPED_PARAMS: readonly Group16BParam[] = [];

export interface Group16BVerdict {
  /** parameters3.md parameter number. */
  param: Group16BParam;
  /** Scorer dim in services/scoring/dims_group16b.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP16B_NO_MAP: Group16BVerdict[] = [
  {
    param: 241,
    dim: "dim_nuisance_liability",
    nearestMap: "puudub — vastutusrisk on krundi-põhine õigusfakt",
    reason:
      "Atraktiivse ohuallika vastutus on krundi-põhine õiguslik hinnang " +
      "(EI OLE kaardikihina mõõdetav): bassein/mänguväljak OSM-is ei " +
      "lahenda hoolsuskohustuse küsimust. Dim jääb NULLiks koos " +
      "notari/kindlustuse kontrolli põhjusega — ära feigi.",
  },
  {
    param: 243,
    dim: "dim_flood_insurance_caps",
    nearestMap: "puudub — kindlustustariifi kihti snapshots pole",
    reason:
      "Üleujutuskindlustuse limiidid on kindlustusseltsi tariifi hinnang " +
      "(EI OLE snapshots registrit): tariifitabeleid OSM-is pole ja " +
      "limiit sõltub lepingust, mitte asukohast. Dim jääb NULLiks koos " +
      "kindlustuspakkumise kontrolli põhjusega — ära feigi.",
  },
  {
    param: 249,
    dim: "dim_solar_lease_transfer",
    nearestMap: "puudub — päikesepargi rendileping on tehingu-fakt",
    reason:
      "Päikesepaneelide rendilepingu ülekantavus on tehingu-põhine " +
      "lepingufakt (hinnang, EI OLE kaardisignaal): ülekantavust ei saa " +
      "asukohast tuletada. Dim jääb NULLiks koos müügilepingu " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 250,
    dim: "dim_conservation_credits",
    nearestMap: "puudub — looduskaitse maksusoodustus on registrifakt",
    reason:
      "Looduskaitse maksusoodustused eeldavad Keskkonnaameti/EMTA " +
      "registrikannet (hinnang): snapshots vastavat registrit EI OLE. " +
      "Dim jääb NULLiks koos maksuameti kontrolli põhjusega — ära feigi.",
  },
  {
    param: 318,
    dim: "dim_pension_liability",
    nearestMap: "puudub — KOV pensionikohustuste raamatut snapshots pole",
    reason:
      "KOV rahastamata pensionikohustus on omavalitsuse raamatupidamise " +
      "hinnang (EI OLE snapshots registrit): see ei varieeru kvartalite " +
      "lõikes kaardil. Dim jääb NULLiks koos KOV eelarve kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 363,
    dim: "dim_exchange_eligibility",
    nearestMap: "puudub — USA 1031-vahetusel Eesti vastet pole",
    reason:
      "1031-vahetuse kõlblikkus on USA maksukontseptsioon, millele Eesti " +
      "registrites vastet EI OLE (hinnang puudub): asukohaproksi " +
      "joonistamine oleks feik. Dim jääb NULLiks koos maksunõustaja " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 366,
    dim: "dim_abatement_expiry",
    nearestMap: "puudub — maksuvabastuse lõpp on tehingu-fakt",
    reason:
      "Maksuvabastuse lõpptähtaeg on konkreetse kinnistu/tehingu " +
      "lepingufakt (hinnang, EI OLE kaardisignaal): aegumist ei saa " +
      "naabruskonnast tuletada. Dim jääb NULLiks koos notari/müüja " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 370,
    dim: "dim_transfer_fees",
    nearestMap: "puudub — võõrandamistasu on tehingu-fakt",
    reason:
      "Flip-maks/võõrandamistasu on tehingu-põhine kulu (hinnang, EI OLE " +
      "kaardisignaal): Eesti registrites USA-tüüpi flip-maksu vastet " +
      "pole. Dim jääb NULLiks koos notaritariifi kontrolli põhjusega " +
      "— ära feigi.",
  },
  {
    param: 421,
    dim: "dim_appraisal_gap",
    nearestMap: "puudub — hindamisakt on tehingu-fakt",
    reason:
      "Hindamisakti lõhe (ostuhind vs panga hindamine) tekib alles " +
      "konkreetses tehingus (hinnang, EI OLE kaardisignaal): seda ei saa " +
      "asukohast ette ennustada. Dim jääb NULLiks koos pangahindamise " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 422,
    dim: "dim_supplemental_tax",
    nearestMap: "puudub — lisamaksuarve on tehingu-fakt",
    reason:
      "Lisamaksuarve (ümberhindlusest tulenev) on konkreetse tehingu " +
      "maksufakt (hinnang, EI OLE kaardisignaal): EMTA/kov arveid " +
      "snapshots pole. Dim jääb NULLiks koos maksuameti kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 423,
    dim: "dim_assessment_district",
    nearestMap: "puudub — eritasude registrit snapshots pole",
    reason:
      "Erihindamispiirkonna tasud eeldavad KOV eritasude registrikannet " +
      "(hinnang): snapshots vastavat registrit EI OLE. Dim jääb " +
      "NULLiks koos KOV-tabeli kontrolli põhjusega — ära feigi.",
  },
  {
    param: 424,
    dim: "dim_pmi_threshold",
    nearestMap: "puudub — USA PMI-l Eesti vastet pole",
    reason:
      "PMI (USA eralaenukindlustuse) lõpetamise lävi on USA laenutoote " +
      "lepingutingimus, millele Eesti registrites vastet EI OLE " +
      "(hinnang puudub). Dim jääb NULLiks koos pangalaenutingimuste " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 425,
    dim: "dim_eem_loan",
    nearestMap: "puudub — USA EEM-laenul Eesti vastet pole",
    reason:
      "Energiasäästlik hüpoteek (USA EEM) on USA laenutoode, millele " +
      "Eesti registrites vastet EI OLE (hinnang puudub): asukohaproksi " +
      "oleks feik. Dim jääb NULLiks koos panga rohe-laenu kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 426,
    dim: "dim_capital_gains",
    nearestMap: "puudub — USA capital-gains vabastusel Eesti vastet pole",
    reason:
      "Kapitalikasumi vabastus (USA §121 loogika) on USA maksureegel, " +
      "millele Eesti tulumaksuseaduses samaväärset EI OLE (hinnang " +
      "puudub). Dim jääb NULLiks koos maksunõustaja kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 430,
    dim: "dim_escrow_buffer",
    nearestMap: "puudub — deponeerimisreserv on laenulepingu fakt",
    reason:
      "Deponeerimisreservi (escrow buffer) nõue on konkreetse " +
      "laenulepingu tingimus (hinnang, EI OLE kaardisignaal): Eesti " +
      "notari-deposiidis USA-tüüpi reservireeglit pole. Dim jääb " +
      "NULLiks koos pangatingimuste kontrolli põhjusega — ära feigi.",
  },
  {
    param: 444,
    dim: "dim_tourist_influx",
    nearestMap: "puudub — turismihooaeg on turu-ülene pulss, mitte koht",
    reason:
      "Suvine turistide juurdevool on hooajaline turu-ülene hinnang " +
      "(Statistikaameti majutusstatistika, EI OLE koha-signaal): " +
      "staatiline gradient karistaks vanalinna-lähedasi kodusid " +
      "juuni–augusti efekti eest. Dim jääb NULLiks — ära feigi.",
  },
  {
    param: 481,
    dim: "dim_price_ceiling",
    nearestMap: "puudub — tänava lagi selgub tehingu-võrdluses",
    reason:
      "Tänava hinnalagi on võrdlustehingute (Maa-ameti tehingute " +
      "andmebaasi) hinnang konkreetse kuulutuse suhtes, EI OLE " +
      "asukoha-gradient: lagi ilma tehinguteta on feik. Dim jääb " +
      "NULLiks koos maakleri võrdlustehingute kontrolli põhjusega " +
      "— ära feigi.",
  },
  {
    param: 482,
    dim: "dim_corporate_density",
    nearestMap: "puudub — omanike struktuur on registrifakt",
    reason:
      "Juriidiliste isikute omanike osakaal eeldab kinnistusraamatu/ " +
      "tehingute registri aggregaati (hinnang): snapshots vastavat " +
      "registrit EI OLE ja turu-ülene konstant ei joonistu " +
      "gradientina. Dim jääb NULLiks — ära feigi.",
  },
  {
    param: 483,
    dim: "dim_shadow_inventory",
    nearestMap: "puudub — varjatud pakkumine on turu-ülene hinnang",
    reason:
      "Varjatud pakkumine (müümata, aga varjus olev maht) on turu-ülene " +
      "hinnang (EI OLE koha-signaal): ühte turu konstanti ei saa ausalt " +
      "kaardigradiendiks lahutada. Dim jääb NULLiks — ära feigi.",
  },
  {
    param: 484,
    dim: "dim_absorption_rate",
    nearestMap: "puudub — neeldumiskiirus on turu-ülene seeria",
    reason:
      "Neeldumiskiirus (Maa-amet/Statistikaameti tehingute aggregaat) " +
      "on turu-ülene seeria (hinnang, EI OLE koha-signaal): linna-ülene " +
      "number ei diskrimineeri kvartaleid. Dim jääb NULLiks — ära feigi.",
  },
  {
    param: 486,
    dim: "dim_land_improvement_ratio",
    nearestMap: "puudub — maa/hoone suhe on hindamisakti fakt",
    reason:
      "Maa-parenduste suhe selgub konkreetse hindamisakti/tehingu " +
      "hinnangust (EI OLE kaardisignaal): katastriüksuse suhet ei saa " +
      "naabruskonnast tuletada. Dim jääb NULLiks koos hindamisakti " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 487,
    dim: "dim_demographic_transition",
    nearestMap: "puudub — demograafiline nihe on turu-ülene seeria",
    reason:
      "Demograafiline üleminek (Statistikaameti rahvastikustatistika) " +
      "on aeglane turu-ülene seeria (hinnang, EI OLE koha-signaal): " +
      "aastane linna-taseme number ei kanna kvartali-gradienti. Dim " +
      "jääb NULLiks — ära feigi.",
  },
];

/**
 * OSM tags evaluated per param and rejected for a gradient map
 * (documents the source question for the record; the per-listing dims
 * return NULL — the app serves the frozen snapshot, never live
 * Overpass — and market-wide series are never painted as area signal).
 */
export const GROUP16B_CONSIDERED_TAGS: Record<Group16BParam, string> = {
  241: "(puudub — vastutusrisk on õigusfakt, OSM-proksi EI OLE)",
  249: "(puudub — rendileping on tehingufakt, OSM-proksi EI OLE)",
  250: "(puudub — Keskkonnaamet/EMTA register, snapshots pole)",
  243: "(puudub — kindlustustariifid, snapshots pole)",
  318: "(puudub — KOV raamatupidamine, snapshots pole)",
  363: "(puudub — USA maksukontseptsioon, Eesti vastet pole)",
  366: "(puudub — tehingu lepingutähtaeg, OSM-proksi EI OLE)",
  370: "(puudub — tehingukulu, OSM-proksi EI OLE)",
  421: "(puudub — tehingu hindamislõhe, OSM-proksi EI OLE)",
  422: "(puudub — EMTA/KOV maksuarve, snapshots pole)",
  423: "(puudub — KOV eritasude register, snapshots pole)",
  424: "(puudub — USA laenutoode, Eesti vastet pole)",
  425: "(puudub — USA laenutoode, Eesti vastet pole)",
  426: "(puudub — USA maksureegel, Eesti vastet pole)",
  430: "(puudub — laenulepingu tingimus, OSM-proksi EI OLE)",
  444: "(puudub — hooajaline turu-ülene pulss, OSM-proksi EI OLE)",
  481: "(puudub — Maa-ameti tehingute võrdlus, tehingu-hinnang)",
  482: "(puudub — kinnistusraamatu agregaat, snapshots pole)",
  483: "(puudub — turu-ülene hinnang, OSM-proksi EI OLE)",
  484: "(puudub — turu-ülene seeria, OSM-proksi EI OLE)",
  486: "(puudub — hindamisakti fakt, OSM-proksi EI OLE)",
  487: "(puudub — turu-ülene rahvastikuseeria, OSM-proksi EI OLE)",
};

/**
 * Registry reality backing the verdicts (no snapshot table exists for
 * any of these 22: deal/contract facts live with the notary, bank or
 * insurer; aggregates live in Maa-amet/Statistikaamet/EMTA tables
 * outside the frozen OSM snapshot; market-wide series are one value
 * for the whole market and must never be painted as an area signal).
 */
export const GROUP16B_EVIDENCE = {
  snapshotHasRegistryTable: false,
  marketWideIsNotAreaSignal: true,
  sources: [
    "Maa-amet tehingud",
    "Statistikaamet HH01/KK11",
    "Statistikaamet majutusstatistika",
    "Statistikaamet rahvastikustatistika",
    "EMTA maksuregistrid",
    "KOV eritasud/eelarved",
    "kinnistusraamatu agregaat",
    "panga hindamisaktid",
    "notari tehingufaktid",
  ],
} as const;

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP16B_HOOK =
  "G16B-HOOK (#206): no shared-file wiring — no layers ship, verdicts + dims only.";
