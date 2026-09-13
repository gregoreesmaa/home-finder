// Group 1 listing-portal verdicts, batch B (parameters3.md §5.1, issue #203):
// p121 multi-generational living, p129 nanny/au pair quarters,
// p140 cosmetic palette, p180 hidden structural space,
// p191 radiant heated flooring, p192 spa and recovery amenities,
// p193 acoustically treated home theater, p194 climate-controlled
// storage, p195 sculleries/butler's pantry, p198 motor courts,
// p200 specialty culinary integration, p268 server/network closet,
// p285 indoor/outdoor blurring, p286 bulk pantry volume,
// p288 pet quarantine zones, p289 hobby mess containment,
// p290 multi-use micro spaces, p300 superficial flip indicators,
// p412 package theft vulnerability, p489 staging illusions.
//
// VERDICT: all twenty are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group01b.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 batch-B file shape) and lands + tests green on its own.
//
// WHY no layer ships: every param in this batch is a per-listing fact
// extracted from portal text/photos/floorplans (Tier 1 scraped
// syndication: KV.ee, City24, Kinnisvara24, Osta, Okidoki + brokerage
// KVXML feeds, §5.1). Interior finishes, room-level equipment and photo
// staging leave no honest area signal in the OSM snapshot — a gradient
// painted from area data would score the neighbourhood for what only
// the listing itself can answer, so each dim stays a per-listing NULL
// with a buyer-check reason (AGENTS.md §7 honest systems).
//
// Considered and REJECTED near-miss proxies (reviewable, §7.5):
// * p198 motor courts from amenity=parking / highway=service density:
//   a circular maneuvering court is a parcel-level driveway design,
//   not area parking supply — the gradient would reward/penalise
//   listings for the wrong thing, so it stays a NULL dim judged from
//   aerial photo + site visit.
// * p412 package theft vulnerability from amenity=parcel_locker
//   proximity: risk depends on stairwell regime + street exposure,
//   not locker distance — a locker gradient would be fake precision.
//   (No parcel_locker kind ships in this batch either: nothing here
//   consumes it.)
// * p300 superficial flip indicators from transaction recency: recency
//   alone does not measure cheap renovation — the check is Maa-amet
//   transaction history + build quality, per listing.
//
// G01B-HOOK (#203): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP01B_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group01b.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP01B_ALL_PARAMS = [
  121, 129, 140, 180, 191, 192, 193, 194, 195, 198, 200, 268, 285, 286,
  288, 289, 290, 300, 412, 489,
] as const;

export type Group01BParam = (typeof GROUP01B_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP01B_SHIPPED_PARAMS: readonly Group01BParam[] = [];

export interface Group01BVerdict {
  /** parameters3.md parameter number. */
  param: Group01BParam;
  /** Scorer dim in services/scoring/dims_group01b.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP01B_NO_MAP: Group01BVerdict[] = [
  {
    param: 121,
    dim: "dim_multigen",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse põhiplaanifakt)",
    reason:
      "Mitme põlvkonna sobivus on kuulutuse põhiplaanifakt (eraldi " +
      "sissepääs/teine köök): piirkonna kaardil puudub aus pindmine " +
      "signaal (EI OLE hinnangut) — vajab kuulutuse plaani ja " +
      "kohapealset kontrolli, ära feigi.",
  },
  {
    param: 129,
    dim: "dim_nanny_quarters",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse sisefakt)",
    reason:
      "Hoidjapinna olemasolu on kuulutuse sisefakt (eraldi tuba/ " +
      "vannituba): OSM-i pind seda ei näita (EI OLE hinnangut) — " +
      "kontrolli kuulutuse plaani ja pindala, ära feigi.",
  },
  {
    param: 140,
    dim: "dim_cosmetic_palette",
    nearestMap: "puudub — asenduskaarti pole (fotode/NLP hinnang)",
    reason:
      "Kosmeetiline palett on fotode ja NLP hinnang (värvid, " +
      "materjalid): kaardikihil puudub aus mõõdetav signaal (EI OLE " +
      "hinnangut) — otsusta fotode ja külastuse põhjal, ära feigi.",
  },
  {
    param: 180,
    dim: "dim_hidden_space",
    nearestMap: "puudub — asenduskaarti pole (plaan/EHR-i fakt)",
    reason:
      "Peidetud konstruktsiooniruum (nišid, pööninguvaru) selgub " +
      "plaanilt ja ehitisregistrist: kaardil ausat signaali pole " +
      "(EI OLE hinnangut) — küsi plaan ja EHR-i andmed, ära feigi.",
  },
  {
    param: 191,
    dim: "dim_radiant_floor",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse küttefakt)",
    reason:
      "Põrandaküte on kuulutuse küttefakt: piirkonna soojuskaardil " +
      "puudub korteripõhine signaal (EI OLE hinnangut) — kontrolli " +
      "kuulutuse kütte kirjeldust, ära feigi.",
  },
  {
    param: 192,
    dim: "dim_spa_recovery",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse varustusfakt)",
    reason:
      "Spaa- ja taastumisalad (saun, bassein, külmavann) on kuulutuse " +
      "varustusfakt: kaardikiht seda ei mõõda (EI OLE hinnangut) — " +
      "loe kuulutuse mugavuste loetelu, ära feigi.",
  },
  {
    param: 193,
    dim: "dim_acoustic_theater",
    nearestMap: "puudub — müramapp ei mõõda tuba (siseruumi ehitusfakt)",
    reason:
      "Helitöödeldud kodukino on siseruumi ehitusfakt: välismüra kaart " +
      "ei hinda tuba (EI OLE hinnangut) — küsi ehitusdokumentatsiooni, " +
      "ära feigi.",
  },
  {
    param: 194,
    dim: "dim_climate_storage",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse sisefakt)",
    reason:
      "Kliimakontrolliga hoiuruum on kuulutuse sisefakt: kaardil " +
      "signaali pole (EI OLE hinnangut) — kontrolli kuulutuse " +
      "hoiuruumide kirjeldust, ära feigi.",
  },
  {
    param: 195,
    dim: "dim_scullery",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse põhiplaanifakt)",
    reason:
      "Abiköök/butleri sahver on põhiplaani fakt: kaardikiht seda ei " +
      "näita (EI OLE hinnangut) — vaata kuulutuse plaani, ära feigi.",
  },
  {
    param: 198,
    dim: "dim_motor_court",
    nearestMap: "puudub — parkla-polügoon ei mõõda krundi manööverväljaku",
    reason:
      "Manööverväljak (motor court) on krundi-põhine sissesõidu " +
      "lahendus, mitte piirkonna parkimistihedus: parkla/proksi " +
      "gradient valetaks (EI OLE ausat hinnangut) — hinda aerofotolt " +
      "ja kohapeal, ära feigi.",
  },
  {
    param: 200,
    dim: "dim_culinary_suite",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse varustusfakt)",
    reason:
      "Erikulinaarne sisustus (pitsaahi, teppanyaki, veinikülmik) on " +
      "kuulutuse varustusfakt: kaardil signaali pole (EI OLE " +
      "hinnangut) — loe kuulutuse köögi loetelu, ära feigi.",
  },
  {
    param: 268,
    dim: "dim_server_closet",
    nearestMap: "puudub — asenduskaarti pole (siseruumi tehnofakt)",
    reason:
      "Serveri-/võrgukapp on siseruumi fakt (ventilatsioon, elekter): " +
      "kaardikiht seda ei mõõda (EI OLE hinnangut) — kontrolli " +
      "kuulutuse tehnoruumi kirjeldust, ära feigi.",
  },
  {
    param: 285,
    dim: "dim_indoor_outdoor",
    nearestMap: "puudub — asenduskaarti pole (fotode arhitektuurifakt)",
    reason:
      "Sise- ja välisruumi sulandumine (lükandseinad, terrassiavad) on " +
      "arhitektuuri-fakt fotodelt: kaardil signaali pole (EI OLE " +
      "hinnangut) — otsusta fotode ja külastuse põhjal, ära feigi.",
  },
  {
    param: 286,
    dim: "dim_bulk_pantry",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse põhiplaanifakt)",
    reason:
      "Hulgisahvri maht on põhiplaani ja sisefakt: kaardikiht seda ei " +
      "näita (EI OLE hinnangut) — vaata kuulutuse plaani ja sahvri " +
      "kirjeldust, ära feigi.",
  },
  {
    param: 288,
    dim: "dim_pet_quarantine",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse sisefakt)",
    reason:
      "Lemmikloomade eraldusala on kuulutuse sisefakt: kaardil " +
      "signaali pole (EI OLE hinnangut) — küsi müüjalt eraldi ruumi " +
      "olemasolu, ära feigi.",
  },
  {
    param: 289,
    dim: "dim_hobby_mess",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse kõrvalruumifakt)",
    reason:
      "Hobiräbu eraldusvõime (töötuba, helikindel nurk) on sisefakt: " +
      "kaardikiht seda ei mõõda (EI OLE hinnangut) — kontrolli " +
      "kuulutuse kõrvalruume, ära feigi.",
  },
  {
    param: 290,
    dim: "dim_micro_spaces",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse põhiplaanifakt)",
    reason:
      "Mitmeotstarbelised mikroruumid on põhiplaani fakt: kaardil " +
      "signaali pole (EI OLE hinnangut) — loe kuulutuse plaani, " +
      "ära feigi.",
  },
  {
    param: 300,
    dim: "dim_flip_indicators",
    nearestMap: "puudub — tehinguajalugu on Maa-ametis, mitte kaardil",
    reason:
      "Pinnapealse flipi tunnused (odav renoveerimine, kiire " +
      "edasimüük) selguvad tehinguajaloost ja fotodest: kaardigradient " +
      "valetaks (EI OLE hinnangut) — kontrolli Maa-ameti " +
      "tehinguajalugu ja ehituskvaliteeti, ära feigi.",
  },
  {
    param: 412,
    dim: "dim_package_theft",
    nearestMap: "puudub — pakiautomaadi lähedus ei mõõda vargusriski",
    reason:
      "Pakivarguse risk sõltub trepikoja režiimist ja tänava asendist, " +
      "mitte pakiautomaadi kaugusest: lockeri-proksi gradient valetaks " +
      "(EI OLE ausat hinnangut) — hinda sissepääsu ja hoiu lahendust " +
      "kohapeal, ära feigi.",
  },
  {
    param: 489,
    dim: "dim_staging_illusions",
    nearestMap: "puudub — asenduskaarti pole (kuulutuse fotofakt)",
    reason:
      "Lavastusillusioonid (lainurkfotod, virtuaalne mööbel) on " +
      "kuulutuse fotofakt: kaardil signaali pole (EI OLE hinnangut) — " +
      "võrdle fotosid plaani ja külastusega, ära feigi.",
  },
];

/**
 * Verdict counts backing the no-map call (no snapshot area signal
 * exists for listing-interior/NLP facts by construction — Tier 1
 * scraped syndication answers these per listing, never per hexagon).
 */
export const GROUP01B_EVIDENCE = {
  ownedParams: 20,
  proxyDims: 0,
  nullDims: 20,
  snapshotAreaSignals: 0,
} as const;

/**
 * OSM tags evaluated per param and rejected for a gradient map
 * (documents the near-miss proxies for the record; the NULL dims use
 * no snapshot tags at all — the app serves the frozen snapshot, never
 * live Overpass).
 */
export const GROUP01B_CONSIDERED_TAGS: Record<Group01BParam, string> = {
  121: "(puudub — kuulutuse põhiplaanifakt, snapshots pole)",
  129: "(puudub — kuulutuse sisefakt, snapshots pole)",
  140: "(puudub — fotode/NLP fakt, snapshots pole)",
  180: "(puudub — plaan/EHR-i fakt, snapshots pole)",
  191: "(puudub — kuulutuse küttefakt, snapshots pole)",
  192: "(puudub — kuulutuse varustusfakt, snapshots pole)",
  193: "(puudub — siseruumi ehitusfakt, snapshots pole)",
  194: "(puudub — kuulutuse sisefakt, snapshots pole)",
  195: "(puudub — kuulutuse põhiplaanifakt, snapshots pole)",
  198: '(tagasi lükatud: amenity=parking/highway=service — tihedus ei mõõda krundi manööverväljaku)',
  200: "(puudub — kuulutuse varustusfakt, snapshots pole)",
  268: "(puudub — siseruumi tehnofakt, snapshots pole)",
  285: "(puudub — fotode arhitektuurifakt, snapshots pole)",
  286: "(puudub — kuulutuse põhiplaanifakt, snapshots pole)",
  288: "(puudub — kuulutuse sisefakt, snapshots pole)",
  289: "(puudub — kuulutuse kõrvalruumifakt, snapshots pole)",
  290: "(puudub — kuulutuse põhiplaanifakt, snapshots pole)",
  300: "(puudub — tehinguajaloo fakt, snapshots pole)",
  412: "(tagasi lükatud: amenity=parcel_locker — lockeri kaugus ei mõõda vargusriski)",
  489: "(puudub — kuulutuse fotofakt, snapshots pole)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP01B_HOOK =
  "G01B-HOOK (#203): no shared-file wiring — no layers ship, verdicts + dims only.";
