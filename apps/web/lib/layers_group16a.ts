// Group 16 macro/finance-A verdicts (parameters3.md §5.16, issue #205):
// p2 property taxes, p6 mortgage rates, p7 home insurance, p8 closing
// costs, p9 down payment, p41 historical appreciation, p43 resale appeal,
// p70 home insurability, p73 special tax assessment, p77 municipal fiscal
// health, p143 assumable mortgages, p147 contractor availability,
// p148 relocation incentives, p149 market liquidity, p151 tax
// reassessment rules, p153 seller concessions, p155 mortgage portability,
// p156 first-time buyer programs, p157 rent-back feasibility,
// p159 opportunity zones, p160 title insurance costs, p185 net-metering
// laws.
//
// VERDICT: all 22 are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group16a.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 batch-B file shape) and lands + tests green on its own.
//
// WHY no layer ships (evidence: registry facts, not snapshot gaps):
// * ECB 6M Euribor / Eesti Pank MFI rates (p6), KredEx/state program
//   rules (p156), net-metering law + Elering terms (p185) are NATIONAL
//   series/rules — identical in Tallinn and rural Harjumaa. A gradient
//   map would paint the county one flat colour and must NEVER be
//   presented as an area signal.
// * Maa-amet tehingud medians, Statistikaamet HH01/KK11 aggregates,
//   EMTA land-tax tables, KOV budgets/assessments (p2/p41/p43/p73/p77/
//   p149/p151) are quarterly/annual REGISTRY tables: none is in the
//   2026-09-12 OSM snapshot, so there is nothing to calibrate a
//   gradient against. KOV-set rates (p2/p73) do vary by municipality,
//   but without the EMTA/KOV table in-snapshot any KOV-coloured map
//   would be invented data — fake precision, not a fallback.
// * Deal/contract/buyer facts (p7/p8/p9/p70/p143/p153/p155/p157/p160)
//   and market/program facts (p147/p148/p159) are per-deal,
//   per-building or per-programme truths: an area gradient would
//   reward/penalise parcels on questions it cannot resolve.
//
// G16A-HOOK (#205): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP16A_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group16a.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP16A_ALL_PARAMS = [
  2, 6, 7, 8, 9, 41, 43, 70, 73, 77, 143, 147, 148, 149, 151, 153, 155,
  156, 157, 159, 160, 185,
] as const;

export type Group16AParam = (typeof GROUP16A_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP16A_SHIPPED_PARAMS: readonly Group16AParam[] = [];

export interface Group16AVerdict {
  /** parameters3.md parameter number. */
  param: Group16AParam;
  /** Scorer dim in services/scoring/dims_group16a.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP16A_NO_MAP: Group16AVerdict[] = [
  {
    param: 2,
    dim: "dim_property_taxes",
    nearestMap: "puudub — maamaksu kihti snapshots pole",
    reason:
      "Maamaksu määrad (EMTA/KOV tabel, EI OLE hinnangut snapshots): " +
      "KOV-kehtestatud määrad muutuvad aastas korra ja puuduvad OSM " +
      "hetktõmmisest — gradient oleks väljamõeldis. Per-listing dim " +
      "jääb NULLiks KOV-tabeli kontrolli põhjusega.",
  },
  {
    param: 6,
    dim: "dim_mortgage_rates",
    nearestMap: "puudub — Euribor on üleriigiline, mitte kaardisignaal",
    reason:
      "6M Euribor (ECB) + Eesti Pank MFI on üleriigiline seeria (EI OLE " +
      "kohahinnangut): intress on Tallinnas ja maal sama, nii et " +
      "kaardigradient valetaks. Dim jääb NULLiks panga pakkumuse " +
      "kontrolli põhjusega — ära feigi.",
  },
  {
    param: 7,
    dim: "dim_home_insurance",
    nearestMap: "puudub — kindlustuspakkumust ei kaardistata",
    reason:
      "Kodukindlustuse hind on hoone-põhine pakkumus (EI OLE hinnangut " +
      "snapshots): kindlustusseltside tariife hetktõmmises pole. Dim " +
      "jääb NULLiks võrdluspakkumuse kontrolli põhjusega.",
  },
  {
    param: 8,
    dim: "dim_closing_costs",
    nearestMap: "puudub — tehingukulud on tehingu-, mitte koha-fakt",
    reason:
      "Notari/tasu/kulud sõltuvad tehinguhinnast ja -vormist (EI OLE " +
      "hinnangut snapshots): asukohagradient ei lahenda tehingu " +
      "matemaatikat. Dim jääb NULLiks notarikulu kalkulaatori " +
      "põhjusega.",
  },
  {
    param: 9,
    dim: "dim_down_payment",
    nearestMap: "puudub — sissemakse on ostja/panga-, mitte koha-fakt",
    reason:
      "Sissemakse nõue on panga poliitika + ostja profiil (EI OLE " +
      "hinnangut snapshots): ükski OSM tunnus ei kanna ausat " +
      "gradienti. Dim jääb NULLiks pangatingimuste kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 41,
    dim: "dim_historical_appreciation",
    nearestMap: "puudub — tehingustatistikat snapshots pole",
    reason:
      "Ajalugu (Maa-amet tehingud / Statistikaamet HH01) on kvartali " +
      "registritabel (EI OLE hinnangut snapshots): OSM " +
      "hetktõmmisest ei saa tuletada hinnakasvu. Dim jääb NULLiks " +
      "registri väljavõtte kontrolli põhjusega.",
  },
  {
    param: 43,
    dim: "dim_resale_appeal",
    nearestMap: "puudub — järelturu atraktiivsus on koondhinnang",
    reason:
      "Edasimüügi atraktiivsus on mitme registri koondotsus (EI OLE " +
      "ühest hinnangut snapshots): ükski OSM kiht ei mõõda nõudlust. " +
      "Dim jääb NULLiks maakleri võrdlustehingute (comp) kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 70,
    dim: "dim_home_insurability",
    nearestMap: "puudub — kindlustatavus on hoone-põhine otsus",
    reason:
      "Kindlustatavus on seltsi riskiotsus hoone kohta (EI OLE " +
      "hinnangut snapshots): kaardigradient lubaks katet, mida pole. " +
      "Dim jääb NULLiks kindlustusseltsi eelkinnituse kontrolli " +
      "põhjusega.",
  },
  {
    param: 73,
    dim: "dim_special_tax_assessment",
    nearestMap: "puudub — erimaksustamise tabelit snapshots pole",
    reason:
      "Erimaksustamine (KOV eriotsused/tasud) on registritabel (EI OLE " +
      "hinnangut snapshots): OSM-ist tuletatud gradient oleks " +
      "väljamõeldis. Dim jääb NULLiks KOV-maksuinfo kontrolli " +
      "põhjusega.",
  },
  {
    param: 77,
    dim: "dim_municipal_fiscal_health",
    nearestMap: "puudub — KOV eelarvet snapshots pole",
    reason:
      "KOV fiskaaltervis (eelarve/maksuvõlad, EMTA avaandmed) on " +
      "aastane registrifakt (EI OLE hinnangut snapshots): OSM " +
      "geomeetria ei mõõda eelarvet. Dim jääb NULLiks KOV " +
      "majandusaasta aruande kontrolli põhjusega.",
  },
  {
    param: 143,
    dim: "dim_assumable_mortgages",
    nearestMap: "puudub — laenulepingu tingimus, mitte koha-fakt",
    reason:
      "Laenu ülevõetavus on konkreetse lepingutingimus (EI OLE " +
      "hinnangut snapshots): Eesti fikseeritud laenud üldjuhul üle ei " +
      "lähe. Dim jääb NULLiks müüja panga kinnituse kontrolli " +
      "põhjusega — ära feigi.",
  },
  {
    param: 147,
    dim: "dim_contractor_availability",
    nearestMap: "puudub — töövõtjate saadavus pole registrifakt",
    reason:
      "Ehitajate saadavus on turu hetkeseis (EI OLE hinnangut " +
      "snapshots): Äriregister loetleb firmasid, mitte vabu " +
      "brigaade. Dim jääb NULLiks hinnapäringute kontrolli " +
      "põhjusega.",
  },
  {
    param: 148,
    dim: "dim_relocation_incentives",
    nearestMap: "puudub — kolimistoetuste keskregistrit pole",
    reason:
      "Kolimistoetused (KOV/tööandja programmid) on programmipõhised " +
      "(EI OLE hinnangut snapshots): ühtset kaardistatavat tabelit " +
      "pole. Dim jääb NULLiks KOV-toetuste kontrolli põhjusega.",
  },
  {
    param: 149,
    dim: "dim_market_liquidity",
    nearestMap: "puudub — tehingumahtusid snapshots pole",
    reason:
      "Turulikviidsus (Maa-amet tehingute arv/KK11) on kvartali " +
      "registriagregaat (EI OLE hinnangut snapshots): OSM punktid ei " +
      "mõõda tehingukiirust. Dim jääb NULLiks registri väljavõtte " +
      "kontrolli põhjusega.",
  },
  {
    param: 151,
    dim: "dim_tax_reassessment",
    nearestMap: "puudub — ümberhindluse reeglid on seadus+KOV tabel",
    reason:
      "Maamaksu ümberhindluse reeglid (seadus + KOV rakendus) on " +
      "õigusfakt (EI OLE hinnangut snapshots): gradient ei asenda " +
      "õigusteksti. Dim jääb NULLiks EMTA/KOV-info kontrolli " +
      "põhjusega.",
  },
  {
    param: 153,
    dim: "dim_seller_concessions",
    nearestMap: "puudub — müüja järeleandmised on läbirääkimine",
    reason:
      "Müüja järeleandmised sünnivad läbirääkimisel (EI OLE hinnangut " +
      "snapshots): ükski kaardikiht ei tea müüja motivatsiooni. Dim " +
      "jääb NULLiks pakkumisstrateegia kontrolli põhjusega.",
  },
  {
    param: 155,
    dim: "dim_mortgage_portability",
    nearestMap: "puudub — laenu kaasaskantavus on lepingutingimus",
    reason:
      "Laenu portatiivsus on konkreetse panga lepingutingimus (EI OLE " +
      "hinnangut snapshots): koha-gradient valetaks panga poliitikat. " +
      "Dim jääb NULLiks laenulepingu kontrolli põhjusega.",
  },
  {
    param: 156,
    dim: "dim_first_time_buyer",
    nearestMap: "puudub — KredEx/riigi programmid on üleriigilised",
    reason:
      "Esmakordse ostja programmid (KredEx/riik) on üleriigilised " +
      "reeglid (EI OLE kohahinnangut): toetus ei sõltu kaardipunktist. " +
      "Dim jääb NULLiks programmi tingimuste kontrolli põhjusega.",
  },
  {
    param: 157,
    dim: "dim_rent_back",
    nearestMap: "puudub — tagasiüür on tehingutingimus",
    reason:
      "Tagasiüüri võimalus on müüja/ostja kokkulepe (EI OLE hinnangut " +
      "snapshots): kaardil pole poolt, kellega kokku leppida. Dim " +
      "jääb NULLiks tehingustruktuuri kontrolli põhjusega.",
  },
  {
    param: 159,
    dim: "dim_opportunity_zones",
    nearestMap: "puudub — soodustsoonide kihti snapshots pole",
    reason:
      "Soodustsoonid (USA-kontseptsiooni vaste; KOV planeeringuala on " +
      "krundi-põhine) on registri-/planeeringufakt (EI OLE hinnangut " +
      "snapshots): OSM-ist tuletatud tsoon oleks väljamõeldis. Dim " +
      "jääb NULLiks planeeringuinfo kontrolli põhjusega.",
  },
  {
    param: 160,
    dim: "dim_title_insurance",
    nearestMap: "puudub — omandikindlustus on tehingukulu",
    reason:
      "Omandikindlustus/kinnistuskulud (notar + kinnistusraamat) on " +
      "tehingu-fakt (EI OLE hinnangut snapshots): USA-toode Eestis " +
      "praktiliselt puudub. Dim jääb NULLiks notari/kinnistusraamatu " +
      "kulukalkulaatori põhjusega.",
  },
  {
    param: 185,
    dim: "dim_net_metering",
    nearestMap: "puudub — võrgueeskiri on üleriigiline",
    reason:
      "Netoarvestus (seadus + Eleringi/võrguettevõtja tingimused) on " +
      "üleriigiline reegel (EI OLE kohahinnangut): tariif ei muutu " +
      "kaardil liikudes. Dim jääb NULLiks võrguettevõtja tingimuste " +
      "kontrolli põhjusega.",
  },
];

/**
 * Registry reality backing the verdicts (no snapshot probe applies —
 * these sources are quarterly/annual tables or national series, never
 * OSM geometry; documented here so the no-map call stays reviewable):
 * Maa-amet tehingud (notariaalsed tehingud), Statistikaamet HH01/KK11,
 * ECB Euribor 6M (üleriigiline), Eesti Pank MFI, EMTA maamaks, KOV
 * eelarved/otsused, KredEx programmid, Eleringi tingimused.
 */
export const GROUP16A_EVIDENCE = {
  snapshotHasRegistryTable: false,
  euriborIsNational: true,
  sources: [
    "Maa-amet tehingud",
    "Statistikaamet HH01/KK11",
    "ECB Euribor 6M",
    "Eesti Pank MFI",
    "EMTA maamaks",
    "KOV eelarved/otsused",
    "KredEx",
    "Elering",
  ],
} as const;

/**
 * OSM tags evaluated per param: NONE can honestly proxy a macro,
 * registry or deal fact (a mortgage rate has no OSM tag), so every
 * entry documents the missing registry instead of a tag filter.
 */
export const GROUP16A_CONSIDERED_TAGS: Record<Group16AParam, string> = {
  2: "(puudub — EMTA/KOV maamaksu tabel, snapshots pole)",
  6: "(puudub — ECB Euribor/Eesti Pank MFI üleriigiline seeria)",
  7: "(puudub — kindlustusseltside tariifid, snapshots pole)",
  8: "(puudub — notari/tehingukulud, tehingu-fakt)",
  9: "(puudub — pankade sissemakse-poliitika, snapshots pole)",
  41: "(puudub — Maa-amet tehingud / Statistikaamet HH01)",
  43: "(puudub — registrite koondotsus, mitte OSM tunnus)",
  70: "(puudub — seltsi riskiotsus hoone kohta)",
  73: "(puudub — KOV erimaksustamise tabel, snapshots pole)",
  77: "(puudub — KOV eelarve / EMTA maksuvõlad)",
  143: "(puudub — laenulepingu tingimus, snapshots pole)",
  147: "(puudub — brigaadide saadavus pole registrifakt)",
  148: "(puudub — KOV/tööandja programmide info)",
  149: "(puudub — Maa-amet tehingumahud / KK11)",
  151: "(puudub — seadus + KOV rakendustabel)",
  153: "(puudub — läbirääkimise tulemus, mitte OSM tunnus)",
  155: "(puudub — panga lepingutingimus, snapshots pole)",
  156: "(puudub — KredEx/riigi üleriigilised reeglid)",
  157: "(puudub — tehingustruktuuri kokkulepe)",
  159: "(puudub — soodustsoonide/planeeringute register)",
  160: "(puudub — notari/kinnistusraamatu kulud)",
  185: "(puudub — seadus + Eleringi üleriigilised tingimused)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP16A_HOOK =
  "G16A-HOOK (#205): no shared-file wiring — no layers ship, verdicts + dims only.";
