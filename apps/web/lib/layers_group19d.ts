// Group 19 on-site inspection-D verdicts (parameters3.md §5.19, issue #211):
// p417/p418, p431-p440, p451-p460, p472-p475, p477/p478,
// p492, p494, p496-p498 (33 params).
//
// VERDICT: all 33 are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group19d.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 batch-B file shape) and lands + tests green on its own.
//
// WHY no layer ships (Tier 4 on-site forensic walkthrough & mechanical
// diagnostics — certified building engineer audit EVS 932:2017, buyer
// DIY walkthrough toolkit with GFCI tester / laser meter / Protimeter
// moisture meter, EHR concealed-work records): every param in this
// batch is a per-property physical-presence fact — a thing an
// inspector or the buyer must touch, measure, open, walk on, or test
// with a meter in THAT unit. Map geometry carries no honest area
// signal for any of them:
// * p417 lock fit needs the door leaf measured (thickness, backset);
//   p439 grounding needs a GFCI/plug tester in each socket; p473
//   exterior sockets need a walk around the house.
// * p418 motion-light coverage needs a dark-hours visit; p460 paint
//   finish needs daylight viewing; p457 subfloor squeak needs walking
//   the floor; p453/p452/p433/p454 need a tape measure or laser meter
//   in the rooms and on the stairs; p451 needs measuring + a test
//   drive through the gate/garage.
// * p472 downspout discharge needs a rain visit (nearest shipped map
//   context is p50 drainage #151 — water-near-foundation hinnang,
//   MITTE the discharge fact itself); p477 patio fall needs a level;
//   p474 driveway wear needs a surface survey; p440 eaves rot needs
//   touch/prod from a ladder; p432 roofline risk needs a roof survey;
//   p436 skylight seals need frame + interior-ceiling inspection.
// * p431 tensioned-slab cables need drawings/EHR + an engineer
//   (drilling blind breaks cables); p438 spray foam hides rafters and
//   leak marks from any remote read; p455 exhaust routing needs
//   cabinets/ducts opened; p458 fan-box rating needs an electrician
//   opening the box; p459 bath ventilation needs a moisture/pull
//   check; p475 heater leak risk needs the plant room; p456 blind
//   fixing needs openings + wall material checked; p434 pocket-door
//   track wear needs operating the door; p437 radiator footprint needs
//   rooms measured; p435 sunken-room conversion needs a visit + permit.
// * p492 urine saturation hides under carpet (Protimeter + UV lamp);
//   p494 draft inversions need a heating-season smoke test +
//   chimney-sweep/engineer report; p496 under-deck rot needs boards
//   lifted; p497 galv-pipe internal corrosion looks sound from outside
//   (pressure/camera test); p498 hearth separation needs a structural
//   engineer.
// A gradient painted from any of these would be fake precision, so
// every scorer dim stays NULL with an inspector/buyer-check reason.
//
// G19D-HOOK (#211): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP19D_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group19d.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP19D_ALL_PARAMS = [
  417, 418, 431, 432, 433, 434, 435, 436, 437, 438, 439, 440, 451, 452,
  453, 454, 455, 456, 457, 458, 459, 460, 472, 473, 474, 475, 477, 478,
  492, 494, 496, 497, 498,
] as const;

export type Group19DParam = (typeof GROUP19D_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP19D_SHIPPED_PARAMS: readonly Group19DParam[] = [];

export interface Group19DVerdict {
  /** parameters3.md parameter number. */
  param: Group19DParam;
  /** Scorer dim in services/scoring/dims_group19d.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

const NO_MAP = "puudub — asenduskaarti pole";

export const GROUP19D_NO_MAP: Group19DVerdict[] = [
  {
    param: 417,
    dim: "dim_smart_lock",
    nearestMap: NO_MAP,
    reason:
      "Nutuluku sobivus selgub ainult kohapeal ust mõõtes (ukse paksus, " +
      "lukukorpuse mõõt, backset) — kaardigeomeetrias ukselehte pole (EI " +
      "OLE hinnangut): vajab ostja ja korteriühistu kontrolli — ära feigi.",
  },
  {
    param: 418,
    dim: "dim_motion_lighting",
    nearestMap: NO_MAP,
    reason:
      "Õue liikumisvalgustuse katvus selgub ainult pimedas kohapealsel " +
      "külastusel — hetktõmmis ei tea, milline lamp põleb ja kuhu ta " +
      "näitab (EI OLE hinnangut): vajab ostja õhtust kontrolli — ära feigi.",
  },
  {
    param: 431,
    dim: "dim_posttension_slab",
    nearestMap: NO_MAP,
    reason:
      "Järelpingestatud plaadi kaablite kulg selgub ainult " +
      "ehitusdokumentidest/EHR-ist ja inseneri kohapealsest hinnangust — " +
      "kaardilt puurida ei tohi, pime puurimine lõhub kaableid (EI OLE " +
      "hinnangut): vajab inseneri kontrolli — ära feigi.",
  },
  {
    param: 432,
    dim: "dim_rooflines",
    nearestMap: NO_MAP,
    reason:
      "Ebatavaliste katusejoonte (orud, läbiviigud, liited) lekkirisk " +
      "selgub ainult katuse füüsilisel kohapealsel ülevaatusel — " +
      "hoonekeskmetelt orge ei loe (EI OLE hinnangut): vajab katusemeistri " +
      "või inseneri kontrolli — ära feigi.",
  },
  {
    param: 433,
    dim: "dim_stair_geometry",
    nearestMap: NO_MAP,
    reason:
      "Trepi laiuse ja kalde vastavus selgub ainult kohapeal mõõdulindiga " +
      "mõõtes — korruseplaanita kaardilt trepiastet ei mõõda (EI OLE " +
      "hinnangut): vajab ostja DIY-kontrolli — ära feigi.",
  },
  {
    param: 434,
    dim: "dim_pocket_door",
    nearestMap: NO_MAP,
    reason:
      "Taskuukse raami seisukord ja siinide kulumine selguvad ainult " +
      "kohapeal ust liigutades — seina sisse ei näe üheltki kaardilt (EI " +
      "OLE hinnangut): vajab ostja kontrolli — ära feigi.",
  },
  {
    param: 435,
    dim: "dim_sunken_living",
    nearestMap: NO_MAP,
    reason:
      "Süvistatud elutoa astme komistusrisk ja ümberehituse võimalus " +
      "selguvad ainult kohapealsel külastusel — põranda astet kaardilt ei " +
      "loeta (EI OLE hinnangut): vajab ostja ja ehitusloa kontrolli — ära " +
      "feigi.",
  },
  {
    param: 436,
    dim: "dim_skylight_leaks",
    nearestMap: NO_MAP,
    reason:
      "Katuseakende lekked ja tihendite seisukord selguvad ainult kohapeal " +
      "raami ja siselae jälgi kontrollides — katuseakna tihendit kaardilt " +
      "ei hinda (EI OLE hinnangut): vajab vihmajärgset külastust või " +
      "inseneri — ära feigi.",
  },
  {
    param: 437,
    dim: "dim_radiator_footprint",
    nearestMap: NO_MAP,
    reason:
      "Radiaatorite tegelik jalajälg ja möbleerimispiirang selguvad ainult " +
      "kohapeal ruume mõõtes — radiaatorit kaardil pole (EI OLE " +
      "hinnangut): vajab ostja laser-mõõtja kontrolli — ära feigi.",
  },
  {
    param: 438,
    dim: "dim_sprayfoam_hurdle",
    nearestMap: NO_MAP,
    reason:
      "Pritsvahu taha peidetud konstruktsiooni kontrollitavus selgub ainult " +
      "inseneri kohapealsel hinnangul — vaht varjab sarikaid ja lekkejälgi " +
      "ka inspektori eest, rääkimata kaardist (EI OLE hinnangut): vajab " +
      "inseneri kontrolli — ära feigi.",
  },
  {
    param: 439,
    dim: "dim_ungrounded_outlets",
    nearestMap: NO_MAP,
    reason:
      "Maandamata pistikupesad selguvad ainult GFCI-testri või " +
      "pistikutestriga kohapeal — seina sisse pistiku maandust kaardilt ei " +
      "loeta (EI OLE hinnangut): vajab ostja DIY-komplekti kontrolli — ära " +
      "feigi.",
  },
  {
    param: 440,
    dim: "dim_soffit_fascia",
    nearestMap: NO_MAP,
    reason:
      "Räästaaluse ja otsalaua mädanik selgub ainult redelilt katsudes ja " +
      "torkides — räästa puitu kaardilt ei katsu (EI OLE hinnangut): vajab " +
      "kohapealset ülevaatust — ära feigi.",
  },
  {
    param: 451,
    dim: "dim_vehicle_clearance",
    nearestMap: NO_MAP,
    reason:
      "Garaaži ja värava läbipääs kaasaegsele autole (kõrgus, laius, " +
      "pöörderaadius) selgub ainult kohapeal mõõtes ja proovisõidul — " +
      "väravaava laiust kaardilt ei mõõda (EI OLE hinnangut): vajab ostja " +
      "kontrolli — ära feigi.",
  },
  {
    param: 452,
    dim: "dim_appliance_cutout",
    nearestMap: NO_MAP,
    reason:
      "Kodumasinate paigaldusavade mõõdud ja ventilatsioon selguvad ainult " +
      "kohapeal mõõtes — kööginišši kaardil pole (EI OLE hinnangut): vajab " +
      "ostja mõõdulindi kontrolli — ära feigi.",
  },
  {
    param: 453,
    dim: "dim_closet_depth",
    nearestMap: NO_MAP,
    reason:
      "Kappide tegelik sügavus ja kasutusmugavus selguvad ainult kohapeal " +
      "mõõtes — kapi sisemust kaardilt ei mõõda (EI OLE hinnangut): vajab " +
      "ostja kontrolli — ära feigi.",
  },
  {
    param: 454,
    dim: "dim_stair_headroom",
    nearestMap: NO_MAP,
    reason:
      "Trepi läbikäigukõrgus selgub ainult kohapeal trepil mõõtes — pea " +
      "kõrgust astme kohal kaardilt ei loeta (EI OLE hinnangut): vajab " +
      "ostja DIY-kontrolli — ära feigi.",
  },
  {
    param: 455,
    dim: "dim_kitchen_exhaust",
    nearestMap: NO_MAP,
    reason:
      "Köögi väljatõmbe kanaliseerimine (välja või retsirkulatsioon, kanali " +
      "kulg) selgub ainult kohapeal kappe ja kanaleid kontrollides — kanali " +
      "kulgu kaardil pole (EI OLE hinnangut): vajab inseneri või ostja " +
      "kontrolli — ära feigi.",
  },
  {
    param: 456,
    dim: "dim_window_treatment",
    nearestMap: NO_MAP,
    reason:
      "Aknakatte kinnitusvõimalus selgub ainult kohapeal aknaavasid ja " +
      "seinamaterjali kontrollides — karniisi kinnitust kaardilt ei hinda " +
      "(EI OLE hinnangut): vajab ostja külastust — ära feigi.",
  },
  {
    param: 457,
    dim: "dim_subfloor_squeak",
    nearestMap: NO_MAP,
    reason:
      "Aluspõranda nagin viimistluse all selgub ainult kohapeal põrandal " +
      "kõndides — naginat kaardilt ei kuule (EI OLE hinnangut): vajab ostja " +
      "külastust — ära feigi.",
  },
  {
    param: 458,
    dim: "dim_fan_boxes",
    nearestMap: NO_MAP,
    reason:
      "Laeventilaatori harukarpide kandevõime selgub ainult elektriku " +
      "kohapealsel kontrollil (karbi avamine) — tavaline valgustikarp " +
      "ventilaatorit ei kanna ja karbi sisu kaardil pole (EI OLE " +
      "hinnangut): vajab elektriku kontrolli — ära feigi.",
  },
  {
    param: 459,
    dim: "dim_bath_ventilation",
    nearestMap: NO_MAP,
    reason:
      "Vannitoa ventilatsioon (aken või ventilaator, kanali tõmme) selgub " +
      "ainult kohapeal — ventilaatori tõmmet kaardilt ei mõõda (EI OLE " +
      "hinnangut): vajab niiskusmõõtja kontrolli — ära feigi.",
  },
  {
    param: 460,
    dim: "dim_paint_finish",
    nearestMap: NO_MAP,
    reason:
      "Sisevärvi viimistluse kvaliteet ja kulumine selguvad ainult kohapeal " +
      "päevavalguses seini vaadates — värvikihi kvaliteeti kaardilt ei " +
      "hinda (EI OLE hinnangut): vajab ostja külastust — ära feigi.",
  },
  {
    param: 472,
    dim: "dim_downspout_term",
    nearestMap: "p50 drenaažiproksi (#151): veest kaugel = kuiv eeldus — MITTE suubumine",
    reason:
      "Vihmaveetorude suubumine (vundamendist eemale või äärde) selgub " +
      "ainult kohapeal vihma ajal või järel — toru otsa asukohta kaardilt " +
      "ei loeta (EI OLE hinnangut): vajab ostja kontrolli — ära feigi.",
  },
  {
    param: 473,
    dim: "dim_exterior_outlets",
    nearestMap: NO_MAP,
    reason:
      "Õue pistikupesade olemasolu ja kaugus selguvad ainult kohapeal maja " +
      "ümber käies — õuepistikut kaardil pole (EI OLE hinnangut): vajab " +
      "ostja kontrolli — ära feigi.",
  },
  {
    param: 474,
    dim: "dim_driveway_material",
    nearestMap: NO_MAP,
    reason:
      "Sissesõidutee katte materjal ja hooldusvajadus (praod, vajumine) " +
      "selguvad ainult kohapealsel ülevaatusel — katte pragusid kaardilt ei " +
      "loeta (EI OLE hinnangut): vajab ostja külastust — ära feigi.",
  },
  {
    param: 475,
    dim: "dim_water_heater_place",
    nearestMap: NO_MAP,
    reason:
      "Boileri paigutusest tulenev lekkirisk (korrus, äravool, alus) selgub " +
      "ainult kohapeal tehnoruumi kontrollides — tehnoruumi sisu kaardil " +
      "pole (EI OLE hinnangut): vajab inseneri hinnangut — ära feigi.",
  },
  {
    param: 477,
    dim: "dim_patio_slope",
    nearestMap: NO_MAP,
    reason:
      "Terrassi kalle (majast eemale) ja vajumine selguvad ainult kohapeal " +
      "vesiloodiga mõõtes — terrassi kallet kaardilt ei mõõda (EI OLE " +
      "hinnangut): vajab ostja DIY-kontrolli — ära feigi.",
  },
  {
    param: 478,
    dim: "dim_hosebib_pressure",
    nearestMap: NO_MAP,
    reason:
      "Õue veekraani surve ja külmakindlus selguvad ainult kohapeal kraani " +
      "avades — kraanisurvet kaardilt ei loeta (EI OLE hinnangut): vajab " +
      "ostja kontrolli — ära feigi.",
  },
  {
    param: 492,
    dim: "dim_pet_urine",
    nearestMap: NO_MAP,
    reason:
      "Lemmiklooma uriini imbumine aluspõrandasse selgub ainult " +
      "niiskusmõõtja (Protimeter) ja UV-lambiga kohapeal — vaiba all " +
      "peidus, kaardilt ammugi mitte (EI OLE hinnangut): vajab inseneri " +
      "kontrolli — ära feigi.",
  },
  {
    param: 494,
    dim: "dim_chimney_draft",
    nearestMap: NO_MAP,
    reason:
      "Korstna tõmbe pöördumised selguvad ainult küttehooajal kohapeal " +
      "suitsukatsel — korstna tõmmet kaardilt ei mõõda (EI OLE hinnangut): " +
      "vajab korstnapühkija või inseneri akti — ära feigi.",
  },
  {
    param: 496,
    dim: "dim_deck_dryrot",
    nearestMap: NO_MAP,
    reason:
      "Terrassilaua-alune maja-vamm selgub ainult laudu tõstes ja katsudes " +
      "kohapeal — laua-alust mädanikku kaardilt ei näe (EI OLE hinnangut): " +
      "vajab inseneri kontrolli — ära feigi.",
  },
  {
    param: 497,
    dim: "dim_galv_pipe",
    nearestMap: NO_MAP,
    reason:
      "Tsingitud terastorude sisemine korrosioon ja ummistus selguvad ainult " +
      "torumehe kohapealsel surveproovil või kaamerauuringul — väljast " +
      "paistab terve toru (EI OLE hinnangut): vajab torumehe kontrolli — " +
      "ära feigi.",
  },
  {
    param: 498,
    dim: "dim_fireplace_separation",
    nearestMap: NO_MAP,
    reason:
      "Kamina konstruktiivne eraldatus hoonest (praod, vajumine) selgub " +
      "ainult inseneri kohapealsel hinnangul — kamina vundamendi pragu " +
      "kaardilt ei loeta (EI OLE hinnangut): vajab ehitusekspertiisi — ära " +
      "feigi.",
  },
];

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP19D_HOOK =
  "G19D-HOOK (#211): no shared-file wiring — no layers ship, verdicts + dims only.";
