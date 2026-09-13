// Group 19 on-site-inspection-A verdicts (parameters3.md §5.19, issue #208):
// p10 renovation budget, p31 structural integrity, p38 HVAC systems,
// p55 EV charging readiness, p57 plumbing pipe materials, p58 electrical
// service capacity, p59 water pressure and heating, p91 ceiling height and
// volume, p95 interior acoustic insulation, p96 ventilation and air
// exchange, p97 basement usability, p111 hurricane/typhoon readiness,
// p114 severe winter resilience, p115 seismic retrofitting, p116
// tornado/storm shelter, p120 off-grid capabilities, p150 moving truck
// accessibility, p171 foundation type, p172 insulation materials, p173
// interior door quality, p174 floor joist engineering, p175 cabinet box
// construction, p176 window frame materials, p177 roofing material
// lifespan, p178 exterior cladding maintenance, p179 proprietary smart
// home lock-in, p197 whole-home purification, p199 advanced physical
// security, p203 problematic plumbing materials, p205 synthetic stucco
// (EIFS), p206 chimney flue integrity, p207 retaining wall condition,
// p208 unpermitted hidden splices, p209 mold remediation history.
//
// VERDICT: all 34 are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group19a.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 batch-B file shape, layers_group03b.ts, issue #152) and lands
// + tests green on its own.
//
// WHY no layer ships (by construction, Group 19 is Tier 4 on-site
// forensic walkthrough & mechanical diagnostics — Primary Ingestion
// Source: Certified Building Engineer Audit EVS 932:2017, Alternate:
// buyer DIY walkthrough toolkit with GFCI tester / laser meter /
// Protimeter moisture meter):
// * Every one of these 34 facts needs physical presence or a meter in
//   the room: structural cracks, pipe materials, flue cameras, moisture
//   sondes, pressure gauges, laser measures, hidden splices behind
//   panels. A neighbourhood-area gradient cannot resolve a per-unit
//   forensic fact — painting one would be fake precision.
// * The OSM snapshot has zero honest area signal for any of them:
//   building:levels / roof:shape tags describe the shell, never the
//   forensic interior (pipe alloy, joist engineering, mold history,
//   EHR concealed-work records). Deriving scores from shell tags would
//   reward/penalise listings on facts the tags cannot see.
// * So every dim returns NULL with an inspector/buyer-check reason in
//   Estonian (EI OLE hinnangut) — the buyer or certified inspector
//   fills the fact during the physical walkthrough, never the map.
//
// G19A-HOOK (#208): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP19A_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group19a.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP19A_ALL_PARAMS = [
  10, 31, 38, 55, 57, 58, 59, 91, 95, 96, 97, 111, 114, 115, 116, 120,
  150, 171, 172, 173, 174, 175, 176, 177, 178, 179, 197, 199, 203, 205,
  206, 207, 208, 209,
] as const;

export type Group19AParam = (typeof GROUP19A_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP19A_SHIPPED_PARAMS: readonly Group19AParam[] = [];

export interface Group19AVerdict {
  /** parameters3.md parameter number. */
  param: Group19AParam;
  /** Scorer dim in services/scoring/dims_group19a.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

/** No honest area proxy exists for any G19A param — every entry says so. */
const NO_MAP = "puudub — asenduskaarti pole";

export const GROUP19A_NO_MAP: Group19AVerdict[] = [
  {
    param: 10,
    dim: "dim_renovation_budget",
    nearestMap: NO_MAP,
    reason:
      "Remondieelarve sünnib kohapeal: mahtude mõõtmine + töövõtja " +
      "pakkumised (EI OLE hinnangut — ala-gradient kulusid ei ennusta). " +
      "Vajab ostja eelarve-kalkulatsiooni inseneri akti põhjal.",
  },
  {
    param: 31,
    dim: "dim_structural_integrity",
    nearestMap: NO_MAP,
    reason:
      "Kandekonstruktsiooni seisukorda (praod, vajumised, niiskus) näeb " +
      "ainult kohapeal — kaardikihist seda ei loe (EI OLE hinnangut). " +
      "Vajab sertifitseeritud ehitusinseneri auditit (EVS 932:2017).",
  },
  {
    param: 38,
    dim: "dim_hvac_systems",
    nearestMap: NO_MAP,
    reason:
      "Kütte/ventilatsiooni/jahutuse seisukord on seadme- ja torustiku-fakt " +
      "(EI OLE hinnangut — hooneväline kaart katelt ei mõõda). Vajab " +
      "kohapealset inseneri diagnostikat + hooldusraamatut.",
  },
  {
    param: 55,
    dim: "dim_ev_charging_readiness",
    nearestMap: NO_MAP,
    reason:
      "EV-laadimise valmidus on maja elektrikilbi ja liitumisvõimsuse fakt " +
      "(EI OLE hinnangut). Vajab elektriku kohapealset kontrolli " +
      "(peakaitsme suurus, vaba võimsus, kaabeldus).",
  },
  {
    param: 57,
    dim: "dim_plumbing_pipe_materials",
    nearestMap: NO_MAP,
    reason:
      "Torude materjal (vask/teras/plast) selgub ainult torustikku nähes " +
      "või aktidest (EI OLE hinnangut). Vajab kohapealset torumehe " +
      "kontrolli + kaetud tööde akte (EHR).",
  },
  {
    param: 58,
    dim: "dim_electrical_service_capacity",
    nearestMap: NO_MAP,
    reason:
      "Elektripaigaldise võimsus on kilbi- ja liitumis-fakt (EI OLE " +
      "hinnangut). Vajab elektriku mõõtmist + võrguettevõtja " +
      "liitumisandmeid.",
  },
  {
    param: 59,
    dim: "dim_water_pressure_heating",
    nearestMap: NO_MAP,
    reason:
      "Veerõhk ja sooja vee tootmine mõõdetakse kraani juures " +
      "manomeetri/termomeetriga (EI OLE hinnangut). Vajab ostja " +
      "DIY-kontrolli kohapeal.",
  },
  {
    param: 91,
    dim: "dim_ceiling_height_volume",
    nearestMap: NO_MAP,
    reason:
      "Lae kõrgus ja ruumimaht mõõdetakse laser-mõõtjaga toas (EI OLE " +
      "hinnangut — kaart lakke ei näe). Vajab ostja kohapealset mõõtmist.",
  },
  {
    param: 95,
    dim: "dim_interior_acoustic_insulation",
    nearestMap: NO_MAP,
    reason:
      "Siseruumide heliisolatsiooni kuuleb ja mõõdab ainult kohapeal " +
      "(EI OLE hinnangut). Vajab külastust eri kellaaegadel + müra päevikut.",
  },
  {
    param: 96,
    dim: "dim_ventilation_air_exchange",
    nearestMap: NO_MAP,
    reason:
      "Õhuvahetuse toimivust näitab CO2/niiskuse mõõtmine ruumis (EI OLE " +
      "hinnangut). Vajab kohapealset mõõtmist + ventilatsiooni hooldusakte.",
  },
  {
    param: 97,
    dim: "dim_basement_usability",
    nearestMap: NO_MAP,
    reason:
      "Keldri kasutatavust (niiskus, kõrgus, ligipääs) hinnatakse ainult " +
      "keldris seistes (EI OLE hinnangut). Vajab inseneri niiskusemõõtmist " +
      "(Protimeter).",
  },
  {
    param: 111,
    dim: "dim_hurricane_readiness",
    nearestMap: NO_MAP,
    reason:
      "Tormikinnitus on katuse/fassaadi kinnituste fakt (EI OLE hinnangut " +
      "— orkaanikaarti Eesti kohta ei joonista). Vajab inseneri kohapealset " +
      "kinnituste kontrolli.",
  },
  {
    param: 114,
    dim: "dim_severe_winter_resilience",
    nearestMap: NO_MAP,
    reason:
      "Talvekindlus (külmasillad, torude külmumisrisk, varuküte) on " +
      "hoone-fakt (EI OLE hinnangut). Vajab inseneri talveauditit + " +
      "küttekulude ajalugu.",
  },
  {
    param: 115,
    dim: "dim_seismic_retrofitting",
    nearestMap: NO_MAP,
    reason:
      "Seismiline tugevdamine on erandlik konstruktsiooni-fakt, mis selgub " +
      "ainult projektist (EI OLE hinnangut). Vajab projektdokumentatsiooni " +
      "+ inseneri hinnangut.",
  },
  {
    param: 116,
    dim: "dim_storm_shelter",
    nearestMap: NO_MAP,
    reason:
      "Varjumisruumi olemasolu ja kasutatavus (kelder/varjend) selgub " +
      "plaanilt ja kohapeal (EI OLE hinnangut). Vajab ostja kontrolli " +
      "kohapeal.",
  },
  {
    param: 120,
    dim: "dim_off_grid_capabilities",
    nearestMap: NO_MAP,
    reason:
      "Autonoomsus (kaev, septik, generaator, akud) on krundi seadmete " +
      "fakt (EI OLE hinnangut). Vajab seadmete inventuuri kohapeal + akte.",
  },
  {
    param: 150,
    dim: "dim_moving_truck_access",
    nearestMap: NO_MAP,
    reason:
      "Kolimisveoki ligipääs (pöörderaadius, kõrguspiirang, parkimine) " +
      "selgub hoovi üle vaadates (EI OLE hinnangut — tänavakaart veoki " +
      "ära ei mahuta). Vajab ostja kohapealset kontrolli.",
  },
  {
    param: 171,
    dim: "dim_foundation_type",
    nearestMap: NO_MAP,
    reason:
      "Vundamendi tüüp ja seisukord on kaetud konstruktsiooni fakt (EI OLE " +
      "hinnangut). Vajab ehitusprojekti + inseneri sondeerimist.",
  },
  {
    param: 172,
    dim: "dim_insulation_materials",
    nearestMap: NO_MAP,
    reason:
      "Soojustuse materjal ja paksus on seina-fakt (EI OLE hinnangut). " +
      "Vajab projekti/akte või puurproovi inseneri tellimusel.",
  },
  {
    param: 173,
    dim: "dim_interior_door_quality",
    nearestMap: NO_MAP,
    reason:
      "Siseuste kvaliteeti (hinged, lengid, heli) katsub ostja käega " +
      "kohapeal (EI OLE hinnangut). Vajab DIY-ülevaatust.",
  },
  {
    param: 174,
    dim: "dim_floor_joist_engineering",
    nearestMap: NO_MAP,
    reason:
      "Vahelae talade lahendus on kaetud konstruktsiooni fakt (EI OLE " +
      "hinnangut). Vajab projekti + inseneri avamist/sondeerimist.",
  },
  {
    param: 175,
    dim: "dim_cabinet_construction",
    nearestMap: NO_MAP,
    reason:
      "Köögikappide korpuse kvaliteeti näeb uksi avades ja sahtleid " +
      "katsetades (EI OLE hinnangut). Vajab ostja kohapealset kontrolli.",
  },
  {
    param: 176,
    dim: "dim_window_frame_materials",
    nearestMap: NO_MAP,
    reason:
      "Aknaraamide materjal ja seisukord on kohapeal nähtav fakt (EI OLE " +
      "hinnangut). Vajab DIY-ülevaatust + energiamärgist.",
  },
  {
    param: 177,
    dim: "dim_roofing_lifespan",
    nearestMap: NO_MAP,
    reason:
      "Katusekatte järelejäänud eluiga hindab katusemeister katusel seistes " +
      "(EI OLE hinnangut — ülaltvaade katuse vanust ei ütle). Vajab katuse " +
      "auditit + paigaldusakte.",
  },
  {
    param: 178,
    dim: "dim_exterior_cladding",
    nearestMap: NO_MAP,
    reason:
      "Fassaadikatte hooldusvajaduse näeb fassaadi üle vaadates (EI OLE " +
      "hinnangut). Vajab kohapealset inseneri/maalri hinnangut.",
  },
  {
    param: 179,
    dim: "dim_smart_home_lockin",
    nearestMap: NO_MAP,
    reason:
      "Nutikodu lukustus konkreetsesse tootjasse selgub seadmeid ja " +
      "lepinguid lugedes (EI OLE hinnangut). Vajab ostja kontrolli: kas " +
      "süsteem töötab ilma tellimuseta.",
  },
  {
    param: 197,
    dim: "dim_whole_home_purification",
    nearestMap: NO_MAP,
    reason:
      "Kogu maja vee/õhu puhastusseadmete olemasolu on seadme-fakt (EI OLE " +
      "hinnangut). Vajab kohapealset inventuuri + hooldusakte.",
  },
  {
    param: 199,
    dim: "dim_physical_security",
    nearestMap: NO_MAP,
    reason:
      "Füüsilise turvalisuse tase (uksed, lukud, võred) selgub kohapeal " +
      "(EI OLE hinnangut). Vajab ostja/inseneri ülevaatust.",
  },
  {
    param: 203,
    dim: "dim_problematic_plumbing",
    nearestMap: NO_MAP,
    reason:
      "Probleemsed torumaterjalid (plii, tsink-teras) tuvastab torumees " +
      "kohapeal (EI OLE hinnangut). Vajab torustiku auditit + veeproovi.",
  },
  {
    param: 205,
    dim: "dim_synthetic_stucco",
    nearestMap: NO_MAP,
    reason:
      "EIFS-fassaadi niiskusrisk mõõdetakse sondiga seina tagant (EI OLE " +
      "hinnangut). Vajab inseneri niiskussondeerimist.",
  },
  {
    param: 206,
    dim: "dim_chimney_flue",
    nearestMap: NO_MAP,
    reason:
      "Korsta lõõri terviklikkust näitab ainult kaamerauuring (EI OLE " +
      "hinnangut). Vajab korstnapühkija/inseneri kaamerakontrolli + akti.",
  },
  {
    param: 207,
    dim: "dim_retaining_wall",
    nearestMap: NO_MAP,
    reason:
      "Tugimüüri seisukord (kalle, drenaaž, praod) hinnatakse müüri ees " +
      "seistes (EI OLE hinnangut). Vajab inseneri kohapealset kontrolli.",
  },
  {
    param: 208,
    dim: "dim_hidden_splices",
    nearestMap: NO_MAP,
    reason:
      "Loata varjatud elektriühendused leitakse kilpi ja karpe avades " +
      "(EI OLE hinnangut). Vajab elektriku auditit + EHR kaetud tööde akte.",
  },
  {
    param: 209,
    dim: "dim_mold_history",
    nearestMap: NO_MAP,
    reason:
      "Hallituse ajalugu (lõhn, plekid, niiskuslugu) selgub kohapeal + " +
      "dokumentidest (EI OLE hinnangut). Vajab Protimeter-mõõtmist + " +
      "müüja/remondiakte.",
  },
];

/**
 * OSM tags evaluated per param and rejected for a gradient map.
 * Group 19 is Tier-4 on-site forensic by construction: shell tags
 * (building:levels, roof:shape) describe the building shell, never the
 * forensic interior — so every entry documents the ABSENT source, and
 * the per-listing dims stay NULL until the walkthrough fills them.
 */
export const GROUP19A_CONSIDERED_TAGS: Record<Group19AParam, string> = {
  10: "(puudub — remondimahud kohapealsest mõõtmisest, snapshots pole)",
  31: "(puudub — konstruktsiooni-audit EVS 932:2017, snapshots pole)",
  38: "(puudub — HVAC diagnostika inseneri poolt, snapshots pole)",
  55: "(puudub — elektrikilbi/liitumise fakt, snapshots pole)",
  57: "(puudub — torustiku materjal kohapealt/aktidest, snapshots pole)",
  58: "(puudub — elektriku mõõtmine + liitumisandmed, snapshots pole)",
  59: "(puudub — veerõhu mõõtmine kraani juures, snapshots pole)",
  91: "(puudub — laser-mõõtmine ruumis, snapshots pole)",
  95: "(puudub — heliisolatsiooni kuulamine/mõõtmine, snapshots pole)",
  96: "(puudub — CO2/niiskuse mõõtmine ruumis, snapshots pole)",
  97: "(puudub — keldri niiskusemõõtmine Protimeteriga, snapshots pole)",
  111: "(puudub — kinnituste kontroll katusel/fassaadil, snapshots pole)",
  114: "(puudub — talveaudit + küttekulude ajalugu, snapshots pole)",
  115: "(puudub — projektdokumentatsioon + insener, snapshots pole)",
  116: "(puudub — keldri/varjendi kasutatavus kohapealt, snapshots pole)",
  120: "(puudub — seadmete inventuur krundil, snapshots pole)",
  150: "(puudub — hoovi pöörderaadiuse kontroll, snapshots pole)",
  171: "(puudub — vundamendi projekt + sondeerimine, snapshots pole)",
  172: "(puudub — seina puurproov/projekt, snapshots pole)",
  173: "(puudub — uste DIY-ülevaatus kohapeal, snapshots pole)",
  174: "(puudub — vahelae projekt + avamine, snapshots pole)",
  175: "(puudub — kappide avamine/katsetamine, snapshots pole)",
  176: "(puudub — akende ülevaatus + energiamärgis, snapshots pole)",
  177: "(puudub — katuse audit katusel, snapshots pole)",
  178: "(puudub — fassaadi ülevaatus kohapeal, snapshots pole)",
  179: "(puudub — seadmete/lepingute lugemine, snapshots pole)",
  197: "(puudub — puhastusseadmete inventuur, snapshots pole)",
  199: "(puudub — uste/lukkude ülevaatus, snapshots pole)",
  203: "(puudub — torustiku audit + veeproov, snapshots pole)",
  205: "(puudub — EIFS niiskussondeerimine, snapshots pole)",
  206: "(puudub — lõõri kaamerauuring + akt, snapshots pole)",
  207: "(puudub — tugimüüri kontroll kohapeal, snapshots pole)",
  208: "(puudub — elektriku audit + EHR aktid, snapshots pole)",
  209: "(puudub — Protimeter + remondiaktid, snapshots pole)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP19A_HOOK =
  "G19A-HOOK (#208): no shared-file wiring — no layers ship, verdicts + dims only.";
