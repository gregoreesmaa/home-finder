// Group 19 on-site inspection B verdicts (parameters3.md §5.19, issue #209):
// p210 sewer line intrusion, p212 smart home cybersecurity,
// p217 integrated battery backup, p218 hardwired network
// infrastructure, p219 smart irrigation efficiency, p232 staircase
// ergonomics, p233 customized countertop height, p235 heavy-duty
// ceiling joists, p236 threshold flushness, p237 visual alarm
// pre-wiring, p238 allergen-trapping architecture, p240
// colorblind-friendly finishes, p261 wiring conduit availability,
// p263 biometric security readiness, p264 EV charging scale,
// p266 automated shading potential, p267 home automation lock-in,
// p269 backup water cisterns, p284 heavy home gym capacity,
// p291 flat roof drainage, p292 cantilevered structural stress,
// p293 radiant heat repairability, p294 below-grade window wells,
// p295 custom glazing costs, p296 exposed architectural steel,
// p297 vaulted ceiling energy waste, p298 adaptive reuse quirks,
// p299 salvaged material delicacy, p302 thermal bridge sensation,
// p303 acoustic resonance between floors, p304 echo and room reverb,
// p306 plumbing water hammer, p307 HVAC register whistle, p308
// subtle tilt and floor slope.
//
// VERDICT: all 34 are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group19b.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3-B file shape, #152) and lands + tests green on its own.
//
// WHY no layer ships (evidence, verified 2026-09-13 against the local
// snapshot ~/hf-data/2026-09-12/osm/ — no network; see
// GROUP19B_EVIDENCE):
// * §5.19's own protocol says the source is a certified building
//   engineer audit (EVS 932:2017) + a buyer DIY walkthrough toolkit
//   (GFCI tester, laser meter, Protimeter moisture meter) + EHR
//   concealed-work records (kaetud tööde aktid) + hydrostatic tests.
//   NONE of these feeds is in the snapshot pipeline (OSM PBF +
//   Maa-amet WFS + derived area rasters): a filename sweep of the
//   snapshot dir finds zero audit/inspect/NDT/walkthrough/interior/
//   forensic feeds (only false positive: "windtunnel" matching "ndt").
// * The most mappable-looking proxies fail the honesty test and are
//   explicitly rejected: 341 amenity=charging_station objects
//   county-wide are an area amenity that says NOTHING about THIS
//   property's panel kW (p264 stays NULL); 4501 man_made=pipeline
//   objects are network geometry that says NOTHING about root
//   intrusion in the property's own lateral — only a pipe camera does
//   (p210 stays NULL); the `sewer` key has ZERO objects county-wide.
// * Every one of the 34 is a per-property forensic/sensory fact that
//   needs physical presence or a meter: pipe camera (p210), firmware/
//   network audit on site (p212), inverter/battery nameplate (p217),
//   cable runs and jacks (p218, p261), controller zones (p219), laser
//   tape (p232, p233), attic/engineer review (p235, p284, p292),
//   level and straightedge (p236, p308), low-voltage panel (p237),
//   materials walkthrough (p238, p299), the buyer's own eyes on site
//   (p240), lock/door compatibility (p263), panel amps/phases (p264),
//   shading wiring (p266), hub protocols (p267), tanks/pump (p269),
//   roof falls and outlets in rain (p291), manifold + concealed-work
//   records (p293), well drains and covers (p294), supplier quote
//   (p295), corrosion/fireproofing sight check (p296), heating bills
//   and volume (p297), rebuild history + EHR (p298), thermal camera
//   (p302), listening in a quiet/loaded house (p303, p304, p306,
//   p307). A cell-average gradient cannot tell a buyer where THEIR
//   property falls — inventing one would be fake precision, so each
//   dim stays NULL with an inspector-check reason.
//
// G19B-HOOK (#209): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP19B_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group19b.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP19B_ALL_PARAMS = [
  210, 212, 217, 218, 219, 232, 233, 235, 236, 237, 238, 240, 261, 263,
  264, 266, 267, 269, 284, 291, 292, 293, 294, 295, 296, 297, 298, 299,
  302, 303, 304, 306, 307, 308,
] as const;

export type Group19BParam = (typeof GROUP19B_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP19B_SHIPPED_PARAMS: readonly Group19BParam[] = [];

export interface Group19BVerdict {
  /** parameters3.md parameter number. */
  param: Group19BParam;
  /** Scorer dim in services/scoring/dims_group19b.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP19B_NO_MAP: Group19BVerdict[] = [
  {
    param: 210,
    dim: "dim_sewer_intrusion",
    nearestMap:
      "puudub — 4501 pipeline-joont on võrgu geomeetria, MITTE haru seisund",
    reason:
      "Kanalisatsioonitorustiku läbikasv selgub ainult torukaameraga " +
      "(hinnang): 4501 kaardistatud pipeline-objekti kirjeldavad võrgu " +
      "geomeetriat, mitte SINU haru juurte seisu, ja `sewer`-võtmel on " +
      "terves maakonnas NULL objekti. Dim jääb NULLiks kaamerauuringu + " +
      "kaetud tööde aktide kontrolli põhjusega (EI OLE kaamera-hinnangut, " +
      "ära feigi).",
  },
  {
    param: 212,
    dim: "dim_smart_cybersecurity",
    nearestMap: "puudub — seadmete püsivara kihti snapshots pole",
    reason:
      "Nutikodu küberturve (vaikimisi paroolid, püsivara vanus, avatud " +
      "pordid) selgub ainult kohapealse võrgu-auditiga (hinnang): " +
      "hetktõmmises pole ühegi seadme turva-hinnangut. Dim jääb NULLiks " +
      "inspektori kontrollnimekirja põhjusega (EI OLE turva-hinnangut, " +
      "ära feigi).",
  },
  {
    param: 217,
    dim: "dim_battery_backup",
    nearestMap: "puudub — paigaldise võimsuskihti snapshots pole",
    reason:
      "Akuvarutoite maht selgub ainult inverteri/akude nimesiltidelt ja " +
      "paigaldusaktist (hinnang): hetktõmmises pole elektripaigaldise " +
      "mahuhinnangut. Dim jääb NULLiks paigaldusakti kontrolli põhjusega " +
      "(EI OLE mahu-hinnangut, ära feigi).",
  },
  {
    param: 218,
    dim: "dim_hardwired_network",
    nearestMap: "puudub — sisevõrgu kaablikihti snapshots pole",
    reason:
      "Kaabelvõrgu (Ethernet) olemasolu ja läbilase selguvad ainult " +
      "kaabliteede/pistikute ülevaatusega kohapeal (hinnang): hetktõmmises " +
      "pole sisevõrgu hinnangut. Dim jääb NULLiks kohapealse ülevaatuse " +
      "põhjusega (EI OLE läbilaske-hinnangut, ära feigi).",
  },
  {
    param: 219,
    dim: "dim_smart_irrigation",
    nearestMap: "puudub — kastmissüsteemi kihti snapshots pole",
    reason:
      "Nutikastmise tõhusus selgub ainult kontrolleri/tsoonide ülevaatusega " +
      "kohapeal (hinnang): hetktõmmises pole kastmissüsteemi hinnangut. " +
      "Dim jääb NULLiks kohapealse ülevaatuse põhjusega (EI OLE tõhususe " +
      "hinnangut, ära feigi).",
  },
  {
    param: 232,
    dim: "dim_staircase_ergonomics",
    nearestMap: "puudub — trepi mõõdukihti snapshots pole",
    reason:
      "Trepi ergonoomika (astme kõrgus/sügavus, käsipuu) selgub ainult " +
      "lasermõõtjaga kohapeal (hinnang): hetktõmmises pole trepi mõõtude " +
      "hinnangut. Dim jääb NULLiks kohapealse mõõtmise põhjusega (EI OLE " +
      "sammu-hinnangut, ära feigi).",
  },
  {
    param: 233,
    dim: "dim_countertop_height",
    nearestMap: "puudub — köögimõõtude kihti snapshots pole",
    reason:
      "Töötasapinna kõrguse sobivus selgub ainult mõõdulindiga kohapeal " +
      "(hinnang): hetktõmmises pole köögimõõtude hinnangut. Dim jääb " +
      "NULLiks ostja-mõõtmise põhjusega (EI OLE kõrguse hinnangut, ära " +
      "feigi).",
  },
  {
    param: 235,
    dim: "dim_ceiling_joists",
    nearestMap: "puudub — konstruktsiooni kihti snapshots pole",
    reason:
      "Laetalade kandevõime (raske valgusti/voodi/pööningukoormus) selgub " +
      "ainult pööningu ülevaatuse või inseneri-auditiga (hinnang): " +
      "hetktõmmises pole konstruktsiooni hinnangut. Dim jääb NULLiks " +
      "inspektori kontrolli põhjusega (EI OLE kandevõime hinnangut, ära " +
      "feigi).",
  },
  {
    param: 236,
    dim: "dim_threshold_flushness",
    nearestMap: "puudub — viimistluse kihti snapshots pole",
    reason:
      "Lävepakkude tasasus (komistamis-/ligipääsurisk) selgub ainult " +
      "nivelliiri/mõõdulindiga kohapeal (hinnang): hetktõmmises pole " +
      "viimistluse hinnangut. Dim jääb NULLiks kohapealse ülevaatuse " +
      "põhjusega (EI OLE tasasuse hinnangut, ära feigi).",
  },
  {
    param: 237,
    dim: "dim_visual_alarm",
    nearestMap: "puudub — nõrkvoolu kaablikihti snapshots pole",
    reason:
      "Visuaalalarmide (vilkurite) eeljuhtmestus selgub ainult kilbi ja " +
      "kaablite ülevaatusega kohapeal (hinnang): hetktõmmises pole " +
      "nõrkvoolu valmiduse hinnangut. Dim jääb NULLiks elektriku kontrolli " +
      "põhjusega (EI OLE valmiduse hinnangut, ära feigi).",
  },
  {
    param: 238,
    dim: "dim_allergen_arch",
    nearestMap: "puudub — siseõhuallika kihti snapshots pole",
    reason:
      "Allergeene kinni pidav arhitektuur (vaibad, kardinad, ventilatsiooni " +
      "lahendus) selgub ainult materjalide ülevaatusega kohapeal (hinnang): " +
      "hetktõmmises pole siseõhuallika hinnangut. Dim jääb NULLiks " +
      "kohapealse ülevaatuse põhjusega (EI OLE allergeeni-hinnangut, ära " +
      "feigi).",
  },
  {
    param: 240,
    dim: "dim_colorblind_finishes",
    nearestMap: "puudub — maitse-eelistust ei kaardistata",
    reason:
      "Värvipimedatele sobivad viimistlused on ostja enda silmade küsimus " +
      "(hinnang): hetktõmmises pole viimistlusvaliku hinnangut ega saagi " +
      "olla. Dim jääb NULLiks kohapealse külastuse põhjusega (EI OLE " +
      "sobivuse hinnangut, ära feigi).",
  },
  {
    param: 261,
    dim: "dim_wiring_conduit",
    nearestMap: "puudub — paigaldise läbitavuskihti snapshots pole",
    reason:
      "Kaablitorude (kõride) olemasolu ja läbitavus selguvad ainult kilbi " +
      "ja avade kaudu kohapeal (hinnang): hetktõmmises pole paigaldise " +
      "hinnangut. Dim jääb NULLiks elektriku kontrolli põhjusega (EI OLE " +
      "läbitavuse hinnangut, ära feigi).",
  },
  {
    param: 263,
    dim: "dim_biometric_security",
    nearestMap: "puudub — lukustuse ühilduvuskihti snapshots pole",
    reason:
      "Biomeetrilise turva (sõrmejäljelukk) valmidus selgub ainult ukse ja " +
      "luku ühilduvuse kontrolliga kohapeal (hinnang): hetktõmmises pole " +
      "lukustuse hinnangut. Dim jääb NULLiks kohapealse ülevaatuse " +
      "põhjusega (EI OLE valmiduse hinnangut, ära feigi).",
  },
  {
    param: 264,
    dim: "dim_ev_scale",
    nearestMap:
      "341 amenity=charging_station on piirkonna mugavus, MITTE kilbi kW",
    reason:
      "EV-laadimise võimsus (amprid/faasid) selgub ainult kilbist ja " +
      "liitumislepingust (hinnang): 341 kaardistatud laadijat kirjeldavad " +
      "piirkonna mugavust, mitte SINU parkimiskoha kilbi võimsust. Dim " +
      "jääb NULLiks elektriku + liitumislepingu kontrolli põhjusega (EI " +
      "OLE kW-hinnangut, ära feigi).",
  },
  {
    param: 266,
    dim: "dim_automated_shading",
    nearestMap: "puudub — varjustuse juhtmestikukihti snapshots pole",
    reason:
      "Automaatvarjustuse (mootorite) potentsiaal selgub ainult aknaajamite " +
      "juhtmestiku ülevaatusega kohapeal (hinnang): hetktõmmises pole " +
      "varjustuse hinnangut. Dim jääb NULLiks kohapealse ülevaatuse " +
      "põhjusega (EI OLE potentsiaali hinnangut, ära feigi).",
  },
  {
    param: 267,
    dim: "dim_automation_lockin",
    nearestMap: "puudub — ökosüsteemi kihti snapshots pole",
    reason:
      "Nutikodu tootjalukustus (suletud protokollid/hub) selgub ainult " +
      "seadmete jaoturi ülevaatusega kohapeal (hinnang): hetktõmmises pole " +
      "ökosüsteemi hinnangut. Dim jääb NULLiks inspektori kontrollnimekirja " +
      "põhjusega (EI OLE lukustuse hinnangut, ära feigi).",
  },
  {
    param: 269,
    dim: "dim_backup_cisterns",
    nearestMap: "puudub — veevaru mahutikihti snapshots pole",
    reason:
      "Varuveemahutite (tsisternide) olemasolu ja maht selguvad ainult " +
      "mahutite/pumba ülevaatusega kohapeal (hinnang): hetktõmmises pole " +
      "veevaru hinnangut. Dim jääb NULLiks kohapealse ülevaatuse põhjusega " +
      "(EI OLE mahu-hinnangut, ära feigi).",
  },
  {
    param: 284,
    dim: "dim_home_gym",
    nearestMap: "puudub — põranda koormuskihti snapshots pole",
    reason:
      "Raske kodujõusaali (masinad, raskused) kandevõime selgub ainult " +
      "inseneri koormus-hinnanguga (hinnang): hetktõmmises pole põranda " +
      "kandevõime hinnangut. Dim jääb NULLiks inseneri-auditi põhjusega " +
      "(EI OLE koormuse hinnangut, ära feigi).",
  },
  {
    param: 291,
    dim: "dim_flatroof_drainage",
    nearestMap: "puudub — katusevee äravoolukihti snapshots pole",
    reason:
      "Lamekatuse drenaaž (kalded, neelud, lombid) selgub ainult katuse " +
      "ülevaatuse või vihmase ilmaga külastusega (hinnang): hetktõmmises " +
      "pole katusevee hinnangut. Dim jääb NULLiks katuse-ülevaatuse " +
      "põhjusega (EI OLE äravoolu-hinnangut, ära feigi).",
  },
  {
    param: 292,
    dim: "dim_cantilever_stress",
    nearestMap: "puudub — staatika kihti snapshots pole",
    reason:
      "Konsoolse (väljulatuva) konstruktsiooni pingeseisund selgub ainult " +
      "inseneri staatika-auditiga (hinnang): hetktõmmises pole staatika " +
      "hinnangut. Dim jääb NULLiks inseneri-auditi põhjusega (EI OLE " +
      "kandevõime hinnangut, ära feigi).",
  },
  {
    param: 293,
    dim: "dim_radiant_repair",
    nearestMap: "puudub — küttesüsteemi remondikihti snapshots pole",
    reason:
      "Põrandakütte remonditavus (kollektor, kontuurid, ligipääs) selgub " +
      "ainult jaotuskollektori ülevaatuse ja kaetud tööde aktidega " +
      "(hinnang): hetktõmmises pole küttesüsteemi hinnangut. Dim jääb " +
      "NULLiks aktide + torumehe kontrolli põhjusega (EI OLE " +
      "remondi-hinnangut, ära feigi).",
  },
  {
    param: 294,
    dim: "dim_window_wells",
    nearestMap: "puudub — aknakaevude kihti snapshots pole",
    reason:
      "Soklikorruse aknakaevude (valguskaevude) drenaaž ja katted selguvad " +
      "ainult ülevaatusega kohapeal (hinnang): hetktõmmises pole kaevude " +
      "hinnangut. Dim jääb NULLiks kohapealse ülevaatuse põhjusega (EI OLE " +
      "äravoolu-hinnangut, ära feigi).",
  },
  {
    param: 295,
    dim: "dim_glazing_costs",
    nearestMap: "puudub — hinnakalkulatsiooni kihti snapshots pole",
    reason:
      "Eritellimus-klaaside (erimõõdud, kolmekordsed) maksumus selgub " +
      "ainult klaasifirma pakkumisega (hinnang): hetktõmmises pole " +
      "hinnakalkulatsiooni. Dim jääb NULLiks pakkumise küsimise põhjusega " +
      "(EI OLE kulu-hinnangut, ära feigi).",
  },
  {
    param: 296,
    dim: "dim_exposed_steel",
    nearestMap: "puudub — terase seisukorra kihti snapshots pole",
    reason:
      "Paljandatud arhitektuurse terase (korrosioon, tulekaitse) seisukord " +
      "selgub ainult visuaalse ülevaatusega kohapeal (hinnang): hetktõmmises " +
      "pole terase hinnangut. Dim jääb NULLiks inspektori kontrolli " +
      "põhjusega (EI OLE seisundi-hinnangut, ära feigi).",
  },
  {
    param: 297,
    dim: "dim_vaulted_ceiling",
    nearestMap: "puudub — ruumimahu kulu-kihti snapshots pole",
    reason:
      "Kõrge (kelp-)lae energiakulu selgub ainult kütteloogika ja arvete " +
      "ülevaatusega (hinnang): hetktõmmises pole ruumimahu kulu-hinnangut. " +
      "Dim jääb NULLiks arvete + inspektori kontrolli põhjusega (EI OLE " +
      "kulu-hinnangut, ära feigi).",
  },
  {
    param: 298,
    dim: "dim_adaptive_reuse",
    nearestMap: "puudub — ümberehitusloo kihti snapshots pole",
    reason:
      "Taaskasutatud (ümber ehitatud) hoone eripärad selguvad ainult " +
      "ümberehituse ajaloo ja EHR-i uurimisega (hinnang): hetktõmmises pole " +
      "ajaloo hinnangut. Dim jääb NULLiks dokumendi-uurimise põhjusega " +
      "(EI OLE eripärade hinnangut, ära feigi).",
  },
  {
    param: 299,
    dim: "dim_salvaged_material",
    nearestMap: "puudub — materjali kulumiskihti snapshots pole",
    reason:
      "Taaskasutatud materjalide (vana puit, tellis) õrnus ja kulumine " +
      "selguvad ainult visuaalse ülevaatusega kohapeal (hinnang): " +
      "hetktõmmises pole materjali seisundi hinnangut. Dim jääb NULLiks " +
      "kohapealse ülevaatuse põhjusega (EI OLE vastupidavuse hinnangut, " +
      "ära feigi).",
  },
  {
    param: 302,
    dim: "dim_thermal_bridge",
    nearestMap: "puudub — soojusleke termopildikihti snapshots pole",
    reason:
      "Külmasildade (soojuslekete) tunnetus selgub ainult termokaameraga " +
      "kütteperioodil (hinnang): hetktõmmises pole soojusleke hinnangut. " +
      "Dim jääb NULLiks termopildi-uuringu põhjusega (EI OLE " +
      "termopildi-hinnangut, ära feigi).",
  },
  {
    param: 303,
    dim: "dim_acoustic_resonance",
    nearestMap: "puudub — akustika mõõtmiskihti snapshots pole",
    reason:
      "Korrustevaheline heliresonants (sammud, bass) selgub ainult " +
      "kuulamisega kohapeal vaikses majas (hinnang): hetktõmmises pole " +
      "akustika mõõtmist. Dim jääb NULLiks kohapealse kuulamise põhjusega " +
      "(EI OLE heli-hinnangut, ära feigi).",
  },
  {
    param: 304,
    dim: "dim_echo_reverb",
    nearestMap: "puudub — järelkõla mõõtmiskihti snapshots pole",
    reason:
      "Kaja ja ruumi järelkõla selguvad ainult kuulamisega kohapeal, " +
      "soovitavalt tühjas ruumis (hinnang): hetktõmmises pole akustika " +
      "mõõtmist. Dim jääb NULLiks kohapealse kuulamise põhjusega (EI OLE " +
      "järelkõla hinnangut, ära feigi).",
  },
  {
    param: 306,
    dim: "dim_water_hammer",
    nearestMap: "puudub — torustiku heli-kihti snapshots pole",
    reason:
      "Torustiku veelöögid (kolin kraanide sulgemisel) selguvad ainult " +
      "kuulamisega kohapeal (hinnang): hetktõmmises pole torustiku " +
      "heli-hinnangut. Dim jääb NULLiks torumehe kontrolli põhjusega (EI " +
      "OLE löögi-hinnangut, ära feigi).",
  },
  {
    param: 307,
    dim: "dim_register_whistle",
    nearestMap: "puudub — ventilatsioonimüra kihti snapshots pole",
    reason:
      "Ventilatsioonirestide vilin täiskoormusel selgub ainult kuulates " +
      "HVAC-i täisvõimsusel kohapeal (hinnang): hetktõmmises pole " +
      "müramõõtmist. Dim jääb NULLiks kohapealse kuulamise põhjusega (EI " +
      "OLE mürataseme hinnangut, ära feigi).",
  },
  {
    param: 308,
    dim: "dim_floor_slope",
    nearestMap: "puudub — tasasuse mõõtmiskihti snapshots pole",
    reason:
      "Põranda peen kalle ja viltusus (vajumine) selguvad ainult " +
      "nivelliiri/pika latiga kohapeal (hinnang): hetktõmmises pole " +
      "tasasuse mõõtmist. Dim jääb NULLiks kohapealse mõõtmise põhjusega " +
      "(EI OLE kalde-hinnangut, ära feigi).",
  },
];

/**
 * Snapshot counts backing the verdicts (verified 2026-09-13, no
 * network — osmium tags-filter nwr/ + export on
 * harjumaa-260911.osm.pbf, plus a filename sweep of the snapshot dir):
 * charging_station objects (area amenity, not per-property kW —
 * rejected proxy for p264); man_made=pipeline objects (network
 * geometry, not lateral condition — rejected proxy for p210); `sewer`
 * key objects (zero: no OSM sewer-condition signal at all); audit /
 * inspect / NDT / walkthrough / interior / forensic feeds in the
 * snapshot inventory (zero: Tier-4 walkthrough has no snapshot feed
 * by construction — the lone "ndt" filename hit is "windtunnel").
 */
export const GROUP19B_EVIDENCE = {
  chargingStations: 341,
  pipelineObjects: 4501,
  sewerKeyObjects: 0,
  auditFeeds: 0,
} as const;

/**
 * OSM tags evaluated per param and rejected for a gradient map
 * (documents the source tags for the record; the NULL dims need no
 * fetch — the app serves the frozen snapshot, never live Overpass).
 * Every entry ends in absence-by-construction: per-property NDT /
 * camera / listening facts have no mappable OSM key.
 */
export const GROUP19B_CONSIDERED_TAGS: Record<Group19BParam, string> = {
  210: 'nwr/man_made=pipeline (4501 objekti — võrgu geomeetria, MITTE haru seisund); nwr/sewer (0 objekti — nullisignaal); kaameraleid puudub (kohapealne fakt)',
  212: "(puudub — püsivara/võrgu-audit on kohapealne fakt, OSM-is pindmine signaal puudub)",
  217: "(puudub — aku/inverteri nimesilt on kohapealne fakt, OSM-is pindmine signaal puudub)",
  218: "(puudub — sisevõrgu kaablitee on kohapealne fakt, OSM-is pindmine signaal puudub)",
  219: "(puudub — kastmiskontroller on kohapealne fakt, OSM-is pindmine signaal puudub)",
  232: "(puudub — trepi mõõdud on kohapealne fakt, OSM-is pindmine signaal puudub)",
  233: "(puudub — köögimõõdud on kohapealne fakt, OSM-is pindmine signaal puudub)",
  235: "(puudub — laetalade kandevõime on inseneri-fakt, OSM-is pindmine signaal puudub)",
  236: "(puudub — lävepakkude tasasus on kohapealne fakt, OSM-is pindmine signaal puudub)",
  237: "(puudub — nõrkvoolu juhtmestus on kohapealne fakt, OSM-is pindmine signaal puudub)",
  238: "(puudub — sisematerjalid on kohapealne fakt, OSM-is pindmine signaal puudub)",
  240: "(puudub — maitse-eelistus pole kaardistatav, OSM-is pindmine signaal puudub)",
  261: "(puudub — kaablitorude läbitavus on kohapealne fakt, OSM-is pindmine signaal puudub)",
  263: "(puudub — luku ühilduvus on kohapealne fakt, OSM-is pindmine signaal puudub)",
  264: 'nwr/amenity=charging_station (341 objekti — piirkonna mugavus, MITTE kilbi kW); paneeli võimsus puudub (kohapealne fakt)',
  266: "(puudub — varjustuse juhtmestik on kohapealne fakt, OSM-is pindmine signaal puudub)",
  267: "(puudub — seadmete ökosüsteem on kohapealne fakt, OSM-is pindmine signaal puudub)",
  269: "(puudub — veemahutid on kohapealne fakt, OSM-is pindmine signaal puudub)",
  284: "(puudub — põranda koormustaluvus on inseneri-fakt, OSM-is pindmine signaal puudub)",
  291: "(puudub — katuse kalded/neelud on kohapealne fakt, OSM-is pindmine signaal puudub)",
  292: "(puudub — konsooli staatika on inseneri-fakt, OSM-is pindmine signaal puudub)",
  293: "(puudub — küttesüsteemi kontuurid on varjatud fakt + aktid, OSM-is pindmine signaal puudub)",
  294: "(puudub — aknakaevude drenaaž on kohapealne fakt, OSM-is pindmine signaal puudub)",
  295: "(puudub — klaasipakkumine on tarnija-fakt, OSM-is pindmine signaal puudub)",
  296: "(puudub — terase korrosioon on visuaalne fakt, OSM-is pindmine signaal puudub)",
  297: "(puudub — ruumimahu küttekulu on arvete-fakt, OSM-is pindmine signaal puudub)",
  298: "(puudub — ümberehituslugu on dokumendi-fakt, OSM-is pindmine signaal puudub)",
  299: "(puudub — materjali kulumine on visuaalne fakt, OSM-is pindmine signaal puudub)",
  302: "(puudub — soojusleke vajab termokaamerat, OSM-is pindmine signaal puudub)",
  303: "(puudub — heliresonants vajab kuulamist, OSM-is pindmine signaal puudub)",
  304: "(puudub — järelkõla vajab kuulamist, OSM-is pindmine signaal puudub)",
  306: "(puudub — veelöögid vajavad kuulamist, OSM-is pindmine signaal puudub)",
  307: "(puudub — restide vilin vajab kuulamist täiskoormusel, OSM-is pindmine signaal puudub)",
  308: "(puudub — põranda kalle vajab nivelliiri, OSM-is pindmine signaal puudub)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP19B_HOOK =
  "G19B-HOOK (#209): no shared-file wiring — no layers ship, verdicts + dims only.";
