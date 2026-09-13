// Group 20 subjective-B verdicts (parameters3.md §5.20, issue #213):
// p168 community mutual aid, p170 local volunteerism, p239 multi-sensory
// garden suitability, p281 asynchronous work zones, p283 quarantine
// suitability, p349 neighborhood pet density, p380 community disaster
// resilience, p383 intentional cohousing, p385 golf errant-ball risk,
// p388 gated-community security theater, p390 language/cultural enclave
// fit, p398 toxic ornamental planting, p410 biophilic design, p413
// surveillance culture, p449 holiday-light traffic, p461 hoarder-neighbor
// proximity, p488 flaw permanence, p490 buyer timeline desperation,
// p500 the "gut feeling" veto.
//
// VERDICT: all nineteen are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group20b.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 3 batch-B file shape) and lands + tests green on its own.
//
// WHY no layer ships (Tier 4 per parameters3.md §5.20 — Subjective Buyer
// Alignment & Biological Intuition): the primary source is the Buyer
// Preference Questionnaire (0–5 slider scale weights, trade-off toggles,
// budget thresholds) and the graceful fallback is In-Person Block
// Observation Protocols & the 'Gut Feeling' Veto. Buyer-profile sliders
// and block observations are not area data — no OSM tag search can
// discriminate them, so there are no snapshot counts to lock (nothing
// honest to count) and no gradient to calibrate:
// * Taste sliders (p168, p170, p383, p388, p390, p413, p490): the score
//   IS the buyer's preference — mapping an area value would answer a
//   question nobody asked (e.g. camera counts for p413 would measure
//   the opposite of the buyer's privacy attitude).
// * Per-parcel/per-unit facts (p239, p281, p283, p398, p410, p461,
//   p488): soil/light/rooms/species/materials/neighbours belong to the
//   listing, not the hectare — an area gradient would smear one garden
//   over the whole block.
// * Seasonal/registry gaps (p349, p449, p461): no pet, lights, or
//   hoarder registry exists; p449's signal is December-only.
// * Social capital (p380): crisis readiness is community fabric, not
//   mappable stock.
// * p385 golf errant-ball risk is the tempting proxy (courses exist in
//   Harjumaa) and is still no-map BY DESIGN: risk is fairway-adjacent
//   AND directional (slice-side parcels only), so a radial gradient
//   would penalise safe neighbours — fake precision. Per-listing buyer
//   check (site visit + seller disclosure) instead.
// * p500 gut veto is not a score at all: the buyer's on-site veto
//   overrides every number.
//
// G20B-HOOK (#213): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP20B_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group20b.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP20B_ALL_PARAMS = [
  168, 170, 239, 281, 283, 349, 380, 383, 385, 388, 390, 398, 410, 413,
  449, 461, 488, 490, 500,
] as const;

export type Group20BParam = (typeof GROUP20B_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP20B_SHIPPED_PARAMS: readonly Group20BParam[] = [];

export interface Group20BVerdict {
  /** parameters3.md parameter number. */
  param: Group20BParam;
  /** Scorer dim in services/scoring/dims_group20b.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP20B_NO_MAP: Group20BVerdict[] = [
  {
    param: 168,
    dim: "dim_mutual_aid",
    nearestMap: "puudub — asenduskaarti pole, otsustab ostja küsimustik",
    reason:
      "Naabriabi kultuur on ostja-eelistuse hinnang (küsimustiku slider, " +
      "EI OLE kaardimõõt): piirkonna gradient ei tea, kas ostja tahab " +
      "ühtekuuluvust — ära feigi.",
  },
  {
    param: 170,
    dim: "dim_volunteerism",
    nearestMap: "puudub — asenduskaarti pole, otsustab ostja küsimustik",
    reason:
      "Kohalik vabatahtlikkus on ostja elustiili-hinnang (küsimustik, EI " +
      "OLE registrimõõt): selgub kogukonnaga suheldes, mitte " +
      "hetktõmmisest — ära feigi.",
  },
  {
    param: 239,
    dim: "dim_garden_sensory",
    nearestMap: "puudub — krundi-fakt, aitab kohapealne vaatlus",
    reason:
      "Mitmeaastase aia sobivus on krundi-põhine hinnang (EI OLE " +
      "kaardimõõt, ostja küsimustik seab kaalu): muld, valgus ja tuul " +
      "kuuluvad krundile, mitte hektarile — ära feigi.",
  },
  {
    param: 281,
    dim: "dim_work_zones",
    nearestMap: "puudub — korteri-fakt, aitab korruseplaan",
    reason:
      "Asünkroonse töö tsoonid on korteri-põhine sisefakt (hinnang " +
      "plaanilt, EI OLE kaardimõõt): tubade arv ja paigutus loevad, " +
      "mitte asukoht — ostja küsimustik ütleb, mitut tsooni vaja on.",
  },
  {
    param: 283,
    dim: "dim_quarantine",
    nearestMap: "puudub — elamu-fakt, aitab korruseplaan",
    reason:
      "Karantini-sobivus on elamu-põhine paigutuse hinnang (eraldi " +
      "sissepääs/tuba, EI OLE kaardimõõt): selgub plaanilt ja vaatlusel, " +
      "mitte piirkonna gradiendist — ära feigi.",
  },
  {
    param: 349,
    dim: "dim_pet_density",
    nearestMap: "puudub — registrit pole, aitab bloki vaatlus",
    reason:
      "Naabruskonna lemmikloomatihedust registris pole (EI OLE mõõdetav " +
      "hinnang): loeb ostja enda lemmik-eelistus (küsimustiku slider) + " +
      "bloki vaatlus — ära feigi.",
  },
  {
    param: 380,
    dim: "dim_disaster_resilience",
    nearestMap: "puudub — sotsiaalne kapital pole kaardikiht",
    reason:
      "Kogukonna kriisivalmidus on sotsiaalse kapitali hinnang (EI OLE " +
      "kaardimõõt): vajab KOV/kogukonna päringut ja ostja riski-eelistust " +
      "(küsimustik) — ära feigi.",
  },
  {
    param: 383,
    dim: "dim_cohousing",
    nearestMap: "puudub — elustiili-valik, otsustab ostja küsimustik",
    reason:
      "Kooselamise kogukond on ostja elustiili-valik (hinnang küsimustikus, " +
      "EI OLE piirkonna skoor): kas ostja tahab ühiselu, otsustab ostja — " +
      "ära feigi.",
  },
  {
    param: 385,
    dim: "dim_golf_ball_risk",
    nearestMap: "puudub — rajaääre-fakt, aitab kohapealne kontroll",
    reason:
      "Eksinud golfipalli risk on krundi-põhine rajaääre-fakt (hinnang: kas " +
      "krunt langeb löögisuunda, EI OLE raadiuse-gradient): kauguskiht " +
      "karistaks ka ohutuid naabreid — vajab kohapealset kontrolli ja " +
      "müüja teavet — ära feigi.",
  },
  {
    param: 388,
    dim: "dim_gated_security",
    nearestMap: "puudub — väärtushinnang, otsustab ostja küsimustik",
    reason:
      "Suletud kogukonna turvateater on ostja väärtushinnang (küsimustiku " +
      "slider, EI OLE kaardimõõt): kas värav rahustab või võõrandab, " +
      "otsustab ostja — ära feigi.",
  },
  {
    param: 390,
    dim: "dim_culture_enclave",
    nearestMap: "puudub — identiteedi-eelistus, otsustab ostja küsimustik",
    reason:
      "Keele-/kultuurikoloonia sobivus on ostja identiteedi-eelistuse " +
      "hinnang (küsimustik, EI OLE kaardiskoor): koloonia kaardistamine " +
      "läheks ostja maitsest mööda — otsustab ostja profiil — ära feigi.",
  },
  {
    param: 398,
    dim: "dim_toxic_planting",
    nearestMap: "puudub — aia-fakt, aitab kohapealne vaatlus",
    reason:
      "Mürgised ilutaimed on aia-põhine vaatlusfakt (hinnang kohapeal, EI " +
      "OLE kaardimõõt): liigid selguvad krundil, mitte hetktõmmisest — " +
      "ostja küsimustik ütleb, kas see loeb — ära feigi.",
  },
  {
    param: 410,
    dim: "dim_biophilic",
    nearestMap: "puudub — interjööri-fakt, aitab kohapealne vaatlus",
    reason:
      "Biofiilne disain on interjööri/arhitektuuri hinnang (EI OLE " +
      "kaardimõõt): materjalid, valgus ja rohelus selguvad ostja vaatlusel " +
      "(küsimustiku slider seab kaalu) — ära feigi.",
  },
  {
    param: 413,
    dim: "dim_surveillance_culture",
    nearestMap: "puudub — privaatsuseelistus, otsustab ostja küsimustik",
    reason:
      "Naabrivalve-kultuur on ostja privaatsuseelistuse hinnang " +
      "(küsimustiku slider, EI OLE kaameratiheduse skoor): kaamerate " +
      "lugemine mõõdaks vastupidist — otsustab ostja — ära feigi.",
  },
  {
    param: 449,
    dim: "dim_holiday_lights",
    nearestMap: "puudub — hooajaline fakt, aitab detsembri-vaatlus",
    reason:
      "Pühadevalgustuse liiklus on hooajaline bloki-vaatlus (hinnang " +
      "detsembris, EI OLE aastaringne kaardimõõt): selgub kohapeal hooajal " +
      "+ ostja pühade-eelistusest (küsimustik) — ära feigi.",
  },
  {
    param: 461,
    dim: "dim_hoarder_neighbor",
    nearestMap: "puudub — registrit pole, aitab bloki vaatlus",
    reason:
      "Kogujanaabri lähedust registris pole (EI OLE mõõdetav hinnang): " +
      "selgub ainult bloki vaatlusel ja müüja teabest — ostja küsimustik " +
      "ütleb tundlikkuse — ära feigi.",
  },
  {
    param: 488,
    dim: "dim_flaw_permanence",
    nearestMap: "puudub — pakkumise-fakt, aitab ülevaatus/inspektor",
    reason:
      "Puuduse püsivus on pakkumise-põhine remondihinnang (kas viga on " +
      "parandatav, EI OLE piirkonna skoor): vajab ülevaatust/inspektorit, " +
      "mitte kaarti — ära feigi.",
  },
  {
    param: 490,
    dim: "dim_timeline_desperation",
    nearestMap: "puudub — ostja sisend, mitte koha omadus",
    reason:
      "Ostja ajahäda on ostja enda sisendi hinnang (kui kiirelt on vaja " +
      "kolida, EI OLE kaardimõõt): kaalu seab ostja profiil (küsimustik), " +
      "mitte asukoht — ära feigi.",
  },
  {
    param: 500,
    dim: "dim_gut_veto",
    nearestMap: "puudub — veto pole skoor, otsustab kohapealne tunne",
    reason:
      "Kõhutunde veto on ostja isiklik bloki-vaatluse hinnang (kohapeal, " +
      "EI OLE skooritav): kui koht tundub vale, langeb pakkumine välja — " +
      "kaarti sellele pole — ära feigi.",
  },
];

/**
 * OSM tags evaluated per param and rejected for a gradient map. Group 20
 * inputs are questionnaire sliders and block observations by
 * construction (parameters3.md §5.20 Tier 4), so every entry documents
 * the absence: there is no honest tag query to run (the app serves the
 * frozen snapshot, never live Overpass).
 */
export const GROUP20B_CONSIDERED_TAGS: Record<Group20BParam, string> = {
  168: "(puudub — ostja küsimustiku slider; naabriabi pole OSM-i fakt)",
  170: "(puudub — ostja küsimustiku slider; vabatahtlikkus pole OSM-i fakt)",
  239: "(puudub — krundi aia-fakt; mulla/valgushetk pole OSM-i fakt)",
  281: "(puudub — korteri sisefakt; tubade paigutus pole OSM-i fakt)",
  283: "(puudub — elamu paigutuse-fakt; karantinikõlblikkus pole OSM-i fakt)",
  349: "(puudub — lemmikloomaregistrit pole; tihedus pole OSM-i fakt)",
  380: "(puudub — sotsiaalne kapital; kriisivalmidus pole OSM-i fakt)",
  383: "(puudub — ostja elustiili-valik; kooselu pole OSM-i fakt)",
  385: "(teadlikult tagasi lükatud — golfivälja raadius karistaks ohutuid naabreid; löögisuund pole OSM-i fakt)",
  388: "(puudub — ostja väärtushinnang; turvatunne pole OSM-i fakt)",
  390: "(teadlikult kaardistamata — ostja identiteedi-eelistus; koloonia pole OSM-i fakt)",
  398: "(puudub — aia liigi-fakt; ilutaimed pole OSM-i fakt)",
  410: "(puudub — interjööri-fakt; biofiilsus pole OSM-i fakt)",
  413: "(teadlikult tagasi lükatud — kaamerate lugemine mõõdaks vastupidist; hoiak pole OSM-i fakt)",
  449: "(puudub — detsembri-fakt; hooajavalgus pole OSM-i fakt)",
  461: "(puudub — registrit pole; kogujanaaber pole OSM-i fakt)",
  488: "(puudub — pakkumise remondi-fakt; parandatavus pole OSM-i fakt)",
  490: "(puudub — ostja ajahäda; kiirusvajadus pole OSM-i fakt)",
  500: "(puudub — ostja veto-otsus; kõhutunne pole OSM-i fakt)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP20B_HOOK =
  "G20B-HOOK (#213): no shared-file wiring — no layers ship, verdicts + dims only.";
