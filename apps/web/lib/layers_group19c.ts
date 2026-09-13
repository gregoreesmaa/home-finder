// Group 19 on-site-inspection-C verdicts (parameters3.md §5.19, issue #210):
// p309 microbial/musty scent perception, p310 natural ventilation draft
// pattern, p321 make-up air unit integration, p322 ductwork zoning
// dampers, p323 attic ventilation balance, p324 condensate line routing,
// p325 main shutoff valve accessibility, p326 combustion appliance
// backdraft, p327 sump pump backup redundancy, p328 thermostatic
// expansion valve, p329 vapor barrier integrity in crawlspace, p330
// sewer backflow preventer presence, p341 grocery unloading ergonomics,
// p344 emergency egress from bedroom, p345 stroller/cart navigability,
// p348 furniture delivery clearance, p357 knob-and-tube wiring presence,
// p358 coal chute and oil tank remnants, p373 hurricane strap
// retrofitting, p374 backup generator fuel supply, p375 potable water
// storage tanks, p376 wildfire smoke air-scrubbing, p379 tornado
// wind-load ratings, p391 lawn equipment access, p392 sprinkler system
// winterizing, p393 pool equipment noise, p396 snow storage space,
// p399 outdoor hose bib placement, p406 allergen circulation, p407
// black mold vulnerability, p414 perimeter breach points, p415 safe
// room potential, p416 driveway choke points.
//
// VERDICT: all 33 are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group19c.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 19 batch-A file shape, layers_group19a.ts, issue #208) and lands
// + tests green on its own.
//
// WHY no layer ships (by construction, Group 19 is Tier 4 on-site
// forensic walkthrough & mechanical diagnostics — Primary Ingestion
// Source: Certified Building Engineer Audit EVS 932:2017, Alternate:
// buyer DIY walkthrough toolkit with GFCI tester / laser meter /
// Protimeter moisture meter):
// * Every one of these 33 facts needs physical presence, a meter, or a
//   hand-test in the room: nose (musty scent), smoke-pencil drafts,
//   attic/crawlspace entry, opening the shutoff hatch, CO worst-case
//   test, tape-measured egress windows, laser-measured clearances,
//   listening to the pool pump on site. A neighbourhood-area gradient
//   cannot resolve a per-unit forensic fact — painting one would be
//   fake precision.
// * The OSM snapshot has zero honest area signal for any of them:
//   shell tags describe the building shell, never the mechanical room
//   (dampers, expansion valves, backflow flaps), the legacy wiring in
//   the attic, or the buried oil tank in the yard. Deriving scores from
//   shell tags would reward/penalise listings on facts the tags cannot
//   see.
// * So every dim returns NULL with an inspector/buyer-check reason in
//   Estonian (EI OLE hinnangut) — the buyer or certified inspector
//   fills the fact during the physical walkthrough, never the map.
//
// G19C-HOOK (#210): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP19C_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group19c.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP19C_ALL_PARAMS = [
  309, 310, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 341, 344,
  345, 348, 357, 358, 373, 374, 375, 376, 379, 391, 392, 393, 396, 399,
  406, 407, 414, 415, 416,
] as const;

export type Group19CParam = (typeof GROUP19C_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP19C_SHIPPED_PARAMS: readonly Group19CParam[] = [];

export interface Group19CVerdict {
  /** parameters3.md parameter number. */
  param: Group19CParam;
  /** Scorer dim in services/scoring/dims_group19c.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

/** No honest area proxy exists for any G19C param — every entry says so. */
const NO_MAP = "puudub — asenduskaarti pole";

export const GROUP19C_NO_MAP: Group19CVerdict[] = [
  {
    param: 309,
    dim: "dim_microbial_musty_scent",
    nearestMap: NO_MAP,
    reason:
      "Hallituse/kopituse lõhna tunneb ainult nina kohapeal (EI OLE " +
      "hinnangut — kaart ei haista). Vajab ostja nuusutuskäiku + " +
      "Protimeter-niiskusmõõtmist ja remondiakte.",
  },
  {
    param: 310,
    dim: "dim_natural_ventilation_draft",
    nearestMap: NO_MAP,
    reason:
      "Loomuliku tuulutuse tõmbemustri näitab suitsupliiats/küünal toas " +
      "(EI OLE hinnangut). Vajab ostja DIY-tõmbekontrolli eri tuulega.",
  },
  {
    param: 321,
    dim: "dim_makeup_air_unit",
    nearestMap: NO_MAP,
    reason:
      "Järelõhu seadme olemasolu ja ühendus selgub tehnoruumis (EI OLE " +
      "hinnangut). Vajab inseneri kohapealset inventuuri + hooldusakte.",
  },
  {
    param: 322,
    dim: "dim_ductwork_zoning",
    nearestMap: NO_MAP,
    reason:
      "Õhukanalite tsooniklapid on pööningu/lae-tagune fakt (EI OLE " +
      "hinnangut). Vajab kanalite avamist ja klappide katsetamist " +
      "kohapeal.",
  },
  {
    param: 323,
    dim: "dim_attic_ventilation",
    nearestMap: NO_MAP,
    reason:
      "Pööningu tuulutuse tasakaalu (sisse/äravool) näeb pööningul seistes " +
      "(EI OLE hinnangut). Vajab inseneri kontrolli + niiskusjälgede " +
      "lugemist.",
  },
  {
    param: 324,
    dim: "dim_condensate_routing",
    nearestMap: NO_MAP,
    reason:
      "Kondensaaditoru kulg ja äravool aetakse jälgi kohapeal (EI OLE " +
      "hinnangut). Vajab toru jälitamist seadmest äravooluni + ummistuse " +
      "kontrolli.",
  },
  {
    param: 325,
    dim: "dim_shutoff_valve_access",
    nearestMap: NO_MAP,
    reason:
      "Peakraani leitavus ja keeratavus selgub ainult kätt proovides " +
      "(EI OLE hinnangut). Vajab ostja kohapealset ligipääsu-katset.",
  },
  {
    param: 326,
    dim: "dim_combustion_backdraft",
    nearestMap: NO_MAP,
    reason:
      "Põlemisseadme tagasivoolu (vingugaasi risk) mõõdab ainult CO-mõõtja " +
      "halvima alarõhu stsenaariumiga (EI OLE hinnangut). Vajab " +
      "sertifitseeritud põlemisohutuse testi.",
  },
  {
    param: 327,
    dim: "dim_sump_pump_backup",
    nearestMap: NO_MAP,
    reason:
      "Kuivenduspumba varutoide (aku + tagavarapump) katsetatakse kaevu " +
      "juures (EI OLE hinnangut). Vajab kohapealset käivitustesti + " +
      "hooldusakte.",
  },
  {
    param: 328,
    dim: "dim_expansion_valve",
    nearestMap: NO_MAP,
    reason:
      "Paisumisventiili olemasolu ja töö loetakse välisseadme nimesildilt " +
      "ja tehnikult (EI OLE hinnangut). Vajab külmatehniku kohapealset " +
      "kontrolli.",
  },
  {
    param: 329,
    dim: "dim_vapor_barrier",
    nearestMap: NO_MAP,
    reason:
      "Roomiku aurutõkke terviklikkuse näeb roomikusse ronides (EI OLE " +
      "hinnangut). Vajab inseneri roomiku-ülevaatust + niiskusmõõtmist.",
  },
  {
    param: 330,
    dim: "dim_sewer_backflow",
    nearestMap: NO_MAP,
    reason:
      "Kanalisatsiooni tagasivooluklapi olemasolu selgub luuki avades " +
      "(EI OLE hinnangut). Vajab torumehe kohapealset kontrolli + " +
      "paigaldusakti.",
  },
  {
    param: 341,
    dim: "dim_grocery_unloading",
    nearestMap: NO_MAP,
    reason:
      "Poekottidega mahalaadimise mugavus (parkimine, trepid, uksed) " +
      "kõnnitakse läbi kottidega (EI OLE hinnangut). Vajab ostja " +
      "kohapealset teekonna-proovi.",
  },
  {
    param: 344,
    dim: "dim_emergency_egress",
    nearestMap: NO_MAP,
    reason:
      "Magamistoa avariiväljapääsu (akna ava, lengi kõrgus) mõõdetakse " +
      "mõõdulindiga (EI OLE hinnangut — põrandaplaan avanevust ei näita). " +
      "Vajab tuleohutusnõuete kontrolli kohapeal.",
  },
  {
    param: 345,
    dim: "dim_stroller_navigation",
    nearestMap: NO_MAP,
    reason:
      "Lapsevankri/ostukäru läbitavus (lift, lävepakud, koridorid) " +
      "katsetatakse vankriga (EI OLE hinnangut). Vajab ostja kohapealset " +
      "läbisõitu.",
  },
  {
    param: 348,
    dim: "dim_furniture_clearance",
    nearestMap: NO_MAP,
    reason:
      "Mööbli sissetoomise vabad mõõdud (uksed, trepikoda, nurgad) " +
      "mõõdetakse laseriga (EI OLE hinnangut). Vajab ostja kohapealset " +
      "mõõtmist.",
  },
  {
    param: 357,
    dim: "dim_knob_tube_wiring",
    nearestMap: NO_MAP,
    reason:
      "Portselanisolaator-juhtmestiku (knob-and-tube) leiab ainult " +
      "pööningut/keldrit valgustades (EI OLE hinnangut — hoone vanus " +
      "olemasolu ei tõesta). Vajab elektriku auditit.",
  },
  {
    param: 358,
    dim: "dim_coal_chute_oil_tank",
    nearestMap: NO_MAP,
    reason:
      "Söeluugi ja õlimahuti jäänused (sh maetud mahuti pinnasereostus) " +
      "selguvad keldrist/hoovist ja registritest (EI OLE hinnangut). " +
      "Vajab keskkonna-kontrolli + EHR akte.",
  },
  {
    param: 373,
    dim: "dim_hurricane_straps",
    nearestMap: NO_MAP,
    reason:
      "Tormiklambrite (sarikakinnituste) olemasolu näeb pööningul " +
      "sarikajala juurest (EI OLE hinnangut). Vajab inseneri kohapealset " +
      "kinnituste kontrolli.",
  },
  {
    param: 374,
    dim: "dim_generator_fuel",
    nearestMap: NO_MAP,
    reason:
      "Varugeneraatori kütusevaru (paak, varu, toide) inventeeritakse " +
      "kohapeal (EI OLE hinnangut). Vajab seadmete ülevaatust + " +
      "käivitustesti.",
  },
  {
    param: 375,
    dim: "dim_water_storage_tanks",
    nearestMap: NO_MAP,
    reason:
      "Joogivee varumahutite olemasolu ja puhtus selgub mahuteid nähes " +
      "(EI OLE hinnangut). Vajab kohapealset inventuuri + veeproovi.",
  },
  {
    param: 376,
    dim: "dim_smoke_air_scrubbing",
    nearestMap: NO_MAP,
    reason:
      "Suitsuaja õhupuhastusvõime (filtrid, ventilatsioon) on seadme-fakt " +
      "(EI OLE hinnangut). Vajab filtrite kontrolli + hooldusakte " +
      "kohapeal.",
  },
  {
    param: 379,
    dim: "dim_tornado_wind_load",
    nearestMap: NO_MAP,
    reason:
      "Tuulekoormuse reiting on hoone dokumentide fakt, mitte piirkonna " +
      "ilm (EI OLE hinnangut). Vajab projektdokumentatsiooni + inseneri " +
      "hinnangut.",
  },
  {
    param: 391,
    dim: "dim_lawn_equipment_access",
    nearestMap: NO_MAP,
    reason:
      "Murutööriistade ligipääs (väravad, kuur, kallakud) mõõdetakse hoovis " +
      "(EI OLE hinnangut). Vajab ostja kohapealset kontrolli.",
  },
  {
    param: 392,
    dim: "dim_sprinkler_winterizing",
    nearestMap: NO_MAP,
    reason:
      "Kastmissüsteemi talvekindlus (tühjendusventiilid, puhumisaktid) " +
      "selgub klapikambrit nähes (EI OLE hinnangut). Vajab hooldaja " +
      "akte + sügishoolduse kontrolli.",
  },
  {
    param: 393,
    dim: "dim_pool_equipment_noise",
    nearestMap: NO_MAP,
    reason:
      "Basseiniseadmete müra (pump, soojuspump) kuuleb ainult seadme " +
      "töötades krundil (EI OLE hinnangut — liiklusmüra simulatsioon " +
      "pumpa ei kuule). Vajab kohapealset kuulamist + dBA-mõõtmist.",
  },
  {
    param: 396,
    dim: "dim_snow_storage",
    nearestMap: NO_MAP,
    reason:
      "Lume ladustamisruum hoovis selgub plaani ja talvise ülevaatuse " +
      "põhjal (EI OLE hinnangut). Vajab ostja kohapealset hinnangut " +
      "lumetõrje-teekonnale.",
  },
  {
    param: 399,
    dim: "dim_hose_bib_placement",
    nearestMap: NO_MAP,
    reason:
      "Õuekraanide asukohad ja surve loetakse kraane avades (EI OLE " +
      "hinnangut). Vajab ostja DIY-kontrolli + surveproovi kohapeal.",
  },
  {
    param: 406,
    dim: "dim_allergen_circulation",
    nearestMap: NO_MAP,
    reason:
      "Allergeenide ringlus (filtrid, kanalipuhastus, niiskus) on " +
      "ventilatsiooni-fakt (EI OLE hinnangut). Vajab filtrite kontrolli " +
      "+ kanalite hooldusakte.",
  },
  {
    param: 407,
    dim: "dim_black_mold_vulnerability",
    nearestMap: NO_MAP,
    reason:
      "Musthallituse haavatavuse (niiskusajalugu, külmasillad, " +
      "ventilatsioon) näitab mõõtmine + ajalugu (EI OLE hinnangut). " +
      "Vajab Protimeter-mõõtmist + müüja/remondiakte.",
  },
  {
    param: 414,
    dim: "dim_perimeter_breach",
    nearestMap: NO_MAP,
    reason:
      "Perimeetri nõrgad kohad (aiad, hekid, pimedad nurgad) kõnnitakse " +
      "krunt läbi (EI OLE hinnangut). Vajab ostja kohapealset " +
      "turvaülevaatust.",
  },
  {
    param: 415,
    dim: "dim_safe_room_potential",
    nearestMap: NO_MAP,
    reason:
      "Varjuruumi potentsiaal (akendeta sisetuba, seinad, uks) selgub " +
      "tubasid hinnates (EI OLE hinnangut). Vajab ostja/inseneri " +
      "kohapealset valikut.",
  },
  {
    param: 416,
    dim: "dim_driveway_choke",
    nearestMap: NO_MAP,
    reason:
      "Sissesõidutee kitsaskohad (värav, raadius, kalle) sõidetakse läbi " +
      "autoga (EI OLE hinnangut — teekaart hoovi kitsust ei mõõda). " +
      "Vajab ostja kohapealset proovisõitu.",
  },
];

/**
 * OSM tags evaluated per param and rejected for a gradient map.
 * Group 19 is Tier-4 on-site forensic by construction: shell tags
 * (building:levels, roof:shape) describe the building shell, never the
 * forensic interior or the mechanical room — so every entry documents
 * the ABSENT source, and the per-listing dims stay NULL until the
 * walkthrough fills them.
 */
export const GROUP19C_CONSIDERED_TAGS: Record<Group19CParam, string> = {
  309: "(puudub — lõhna nuusutamine kohapeal, snapshots pole)",
  310: "(puudub — tõmbemustri suitsupliiats-test, snapshots pole)",
  321: "(puudub — järelõhu seadme inventuur tehnoruumis, snapshots pole)",
  322: "(puudub — kanalite tsooniklappide katsetamine, snapshots pole)",
  323: "(puudub — pööningu tuulutuse kontroll, snapshots pole)",
  324: "(puudub — kondensaaditoru jälitamine, snapshots pole)",
  325: "(puudub — peakraani kätt-proovimine, snapshots pole)",
  326: "(puudub — CO tagasivoolu mõõtmine, snapshots pole)",
  327: "(puudub — kuivenduspumba käivitustest, snapshots pole)",
  328: "(puudub — paisumisventiili tehniku kontroll, snapshots pole)",
  329: "(puudub — roomiku aurutõkke ülevaatus, snapshots pole)",
  330: "(puudub — tagasivooluklapi luugi avamine, snapshots pole)",
  341: "(puudub — poekottide teekonna-proov, snapshots pole)",
  344: "(puudub — avariakna mõõdulindi-mõõtmine, snapshots pole)",
  345: "(puudub — vankriga läbisõit, snapshots pole)",
  348: "(puudub — vabade mõõtude laser-mõõtmine, snapshots pole)",
  357: "(puudub — pööningu/keldri elektriku audit, snapshots pole)",
  358: "(puudub — mahutijäänuste keskkonna-kontroll + EHR, snapshots pole)",
  373: "(puudub — sarikakinnituste kontroll pööningul, snapshots pole)",
  374: "(puudub — generaatori inventuur + käivitustest, snapshots pole)",
  375: "(puudub — veemahutite inventuur + veeproov, snapshots pole)",
  376: "(puudub — filtrite kontroll + hooldusaktid, snapshots pole)",
  379: "(puudub — tuulekoormuse projektdokumendid, snapshots pole)",
  391: "(puudub — hoovi väravate/kuuri mõõtmine, snapshots pole)",
  392: "(puudub — kastmissüsteemi puhumisaktid, snapshots pole)",
  393: "(puudub — pumba kuulamine + dBA-mõõtmine, snapshots pole)",
  396: "(puudub — hoovi lumeplaani ülevaatus, snapshots pole)",
  399: "(puudub — õuekraanide avamine + surveproov, snapshots pole)",
  406: "(puudub — filtrite/kanalite hooldusaktid, snapshots pole)",
  407: "(puudub — Protimeter + niiskusajalugu, snapshots pole)",
  414: "(puudub — krundi läbikõndimise turvaülevaatus, snapshots pole)",
  415: "(puudub — sisetubade varjuruumi-valik, snapshots pole)",
  416: "(puudub — sissesõidutee proovisõit autoga, snapshots pole)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP19C_HOOK =
  "G19C-HOOK (#210): no shared-file wiring — no layers ship, verdicts + dims only.";
