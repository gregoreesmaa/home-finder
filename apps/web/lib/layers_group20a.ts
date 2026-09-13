// Group 20 subjective-A verdicts (parameters3.md §5.20, issue #212):
// p18 neighbourhood vibe, p81 pride of ownership on the block, p85
// neighbourhood demographic balance, p90 civic and social engagement,
// p98 universal design / accessibility, p104 entertaining capacity,
// p105 creative/studio potential, p122 child safety features, p126
// pet-specific architecture, p127 downsizing suitability, p128
// co-buying compatibility, p131 architectural style, p133 design
// philosophies, p134 emotional resonance, p136 technological privacy,
// p161 local political and civic alignment, p163 holiday decorating
// culture, p164 trick-or-treater volume, p165 transient neighbour
// density.
//
// VERDICT: all nineteen are documented NO-MAP (OTA PR #131 precedent —
// gradient map rejected where honest calibration cannot discriminate)
// with scorer dims in services/scoring/dims_group20a.py. This file owns
// the verdict registry; it is self-contained on purpose (mirrors the
// Group 03B file shape) and lands + tests green on its own.
//
// WHY no layer ships (buyer-profile facts, not area data):
// * Group 20's primary source is the Buyer Preference Questionnaire
//   (0-5 slider weights, trade-off toggles, budget thresholds) plus
//   in-person block observation protocols and the "gut feeling" veto.
//   None of those exist in the 2026-09-12 snapshot by construction —
//   a gradient map would score the BUYER, not the PLACE.
// * The alternates (Statistikaamet REL2021 1 km grid tables RL21004 /
//   RL21202, Inside-Airbnb / Booking.com transient density scrapers)
//   are likewise not in the snapshot, so even the two params with a
//   real alternate (p85 demographics, p161 civic alignment, p165
//   transient density) stay per-buyer NULLs rather than faked area
//   scores (AGENTS.md §7 honest systems).
// * Per-listing / per-building facts (p98 accessibility, p104
//   entertaining, p105 studio, p122 child safety, p126 pet
//   architecture) resolve from the listing text + walkthrough, never
//   from an area gradient: the same doorway is accessible or not
//   regardless of which block it stands on.
// * Taste sliders (p18 vibe, p131 style, p133 philosophy, p134
//   resonance, p136 tech privacy, p127 downsizing, p128 co-buying,
//   p90 engagement) are buyer-life-stage facts: one buyer's 100 is
//   another's 0, so any single area score misleads by construction.
// * Block observations (p81 pride of ownership, p163 holiday decor,
//   p164 trick-or-treaters) are seasonal/behavioural: they show on a
//   December evening walk, never in a frozen OSM extract.
//
// G20A-HOOK (#212): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP20A_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group20a.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP20A_ALL_PARAMS = [
  18, 81, 85, 90, 98, 104, 105, 122, 126, 127, 128, 131, 133, 134, 136,
  161, 163, 164, 165,
] as const;

export type Group20AParam = (typeof GROUP20A_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP20A_SHIPPED_PARAMS: readonly Group20AParam[] = [];

export interface Group20AVerdict {
  /** parameters3.md parameter number. */
  param: Group20AParam;
  /** Scorer dim in services/scoring/dims_group20a.py carrying this param. */
  dim: string;
  /** Nearest buyer-side input a buyer can answer today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP20A_NO_MAP: Group20AVerdict[] = [
  {
    param: 18,
    dim: "dim_neighborhood_vibe",
    nearestMap: "puudub — ostjaprofiili küsimustik (hõngu-liugur)",
    reason:
      "Naabruskonna hõng on ostja maitse-hinnang (EI OLE kaardikiht): " +
      "see sõltub ostjaprofiili küsimustiku liuguritest, mitte piirkonna " +
      "andmetest — hinda kohapealsel jalutuskäigul, ära feigi ala skoori.",
  },
  {
    param: 81,
    dim: "dim_pride_of_ownership",
    nearestMap: "puudub — kvartali vaatlus kohapeal (hooldusseisund)",
    reason:
      "Uhkus kvartali üle on kohapealse vaatluse hinnang (EI OLE " +
      "registriandmeid): hoovide ja fassaadide hooldusseisundit " +
      "hetktõmmises pole — vaata kvartal üle jalgsi, kaardikiht puudub.",
  },
  {
    param: 85,
    dim: "dim_demographic_balance",
    nearestMap: "puudub — ostjaprofiili eelistus + REL2021 ruudustik (pole hetktõmmises)",
    reason:
      "Demograafiline tasakaal eeldaks Statistikaameti REL2021 1 km " +
      "ruudustikku, mida hetktõmmises pole (EI OLE hinnangut): sobivus " +
      "tuleneb ostjaprofiili eelistusest, mitte ala skoorist — ära feigi.",
  },
  {
    param: 90,
    dim: "dim_civic_engagement",
    nearestMap: "puudub — ostjaprofiili küsimustik (kaasatuse-liugur)",
    reason:
      "Kodanikuaktiivsus on ostja osaluseelistuse hinnang (EI OLE " +
      "kaardikiht): seltside ja ürituste tihedust hetktõmmises pole — " +
      "märgi oma kaasatuse liugur küsimustikus, ala skoor puudub.",
  },
  {
    param: 98,
    dim: "dim_universal_design",
    nearestMap: "puudub — kuulutus + kohapealne vaatlus (lift, lävepakud)",
    reason:
      "Ligipääsetavus on konkreetse korteri ja hoone fakt (EI OLE ala " +
      "skoor): lift, lävepakud ja ukse laiused selguvad kuulutusest ja " +
      "vaatluselt — hinnang tuleb vaatluselt, mitte kaardilt.",
  },
  {
    param: 104,
    dim: "dim_entertaining_capacity",
    nearestMap: "puudub — kuulutus (põrandaplaan) + seltsielu-liugur",
    reason:
      "Võõrustamisvõimekus on põrandaplaani fakt (EI OLE kaardikiht): " +
      "tubade arv ja avatud köök-elutuba on kuulutuse andmed — " +
      "ostjaprofiili seltsielu-liugur kaalub, kaardi-hinnang puudub.",
  },
  {
    param: 105,
    dim: "dim_studio_potential",
    nearestMap: "puudub — kuulutus + kohapealne vaatlus (valgus, lagi)",
    reason:
      "Stuudiopotentsiaal on ruumiomaduste hinnang (EI OLE alaandmeid): " +
      "valgus, lae kõrgus ja eraldi sissepääs selguvad kuulutusest ja " +
      "vaatluselt — kaardikiht puudub, ära feigi.",
  },
  {
    param: 122,
    dim: "dim_child_safety",
    nearestMap: "puudub — kohapealne vaatlus (piirded, väravad)",
    reason:
      "Lapsuturvalisus on korteri ja trepikoja fakt (EI OLE kaardikiht): " +
      "pistikukaitsed, rõdupiirded ja trepikoja värav selguvad vaatlusel " +
      "— KOV intsidentide tabelit hetktõmmises pole, hinnang tuleb kohapealt.",
  },
  {
    param: 126,
    dim: "dim_pet_architecture",
    nearestMap: "puudub — kuulutus + ostjaprofiil (lemmikulooma-liugur)",
    reason:
      "Lemmikulooma-sobiv arhitektuur on korteri fakt (EI OLE ala " +
      "skoor): põrandamaterjal, rõdu ja jalutusmetsa eelistus tulevad " +
      "kuulutusest ja ostjaprofiilist — kaardi-hinnang puudub.",
  },
  {
    param: 127,
    dim: "dim_downsizing",
    nearestMap: "puudub — ostjaprofiili küsimustik (eluetapi-liugurid)",
    reason:
      "Kahandamise sobivus on eluetapi-eelistuse hinnang (EI OLE " +
      "kaardikiht): ühe tasapinna soov ja hoolduskoormuse taluvus on " +
      "ostjaprofiili liugurid, mitte piirkonna fakt — ära feigi.",
  },
  {
    param: 128,
    dim: "dim_cobuying",
    nearestMap: "puudub — ostjaprofiili küsimustik (koosluse vajadused)",
    reason:
      "Koosostu sobivus on ostjate koosluse hinnang (EI OLE alaandmeid): " +
      "eraldi tiibade ja privaatsuse vajadus selgub ostjaprofiili " +
      "küsimustikust, mitte kaardilt — kaardikiht puudub.",
  },
  {
    param: 131,
    dim: "dim_architectural_style",
    nearestMap: "puudub — ostjaprofiili küsimustik (stiili-liugur)",
    reason:
      "Arhitektuuristiil on maitse-eelistuse hinnang (EI OLE kaardikiht): " +
      "puit, paneel või uusarendus meeldib või ei — ostjaprofiili " +
      "stiili-liugur otsustab, ala skoor puudub.",
  },
  {
    param: 133,
    dim: "dim_design_philosophy",
    nearestMap: "puudub — ostjaprofiili küsimustik (disaini-liugur)",
    reason:
      "Disainifilosoofia on maitse-hinnang (EI OLE registriandmeid): " +
      "minimalism või hubasus ei ole kaardistatav — ostjaprofiili " +
      "küsimustik kaalub, kaardikiht puudub.",
  },
  {
    param: 134,
    dim: "dim_emotional_resonance",
    nearestMap: "puudub — kohapealne vaatlus (kõhutunde veto, p500)",
    reason:
      "Emotsionaalne kõla on sisetunde-hinnang (EI OLE mõõdetav): " +
      "kõhutunde veto kuulub ostjale, mitte kaardile — ükski ala skoor " +
      "ei asenda kohapealset vaatlust.",
  },
  {
    param: 136,
    dim: "dim_tech_privacy",
    nearestMap: "puudub — ostjaprofiili küsimustik (privaatsus-liugur)",
    reason:
      "Tehnoloogiline privaatsus on ostja tundlikkuse hinnang (EI OLE " +
      "kaardikiht): kaamerate ja nutiseadmete taluvus on ostjaprofiili liugur " +
      "— hetktõmmises pole seirekaarti, ära feigi.",
  },
  {
    param: 161,
    dim: "dim_civic_alignment",
    nearestMap: "puudub — ostjaprofiili eelistus + REL2021 ruudustik (pole hetktõmmises)",
    reason:
      "Poliitiline ja kodaniku-ühtekuuluvus eeldaks REL2021 ruudustikku, " +
      "mida hetktõmmises pole (EI OLE hinnangut): väärtusruumi sobivus " +
      "on ostjaprofiili küsimus, mitte ala skoor — ära feigi.",
  },
  {
    param: 163,
    dim: "dim_holiday_decor",
    nearestMap: "puudub — kvartali vaatlus hooajal (tuled, pärjad)",
    reason:
      "Pühade-kaunistamise kultuur on kvartali vaatluse hinnang (EI OLE " +
      "registriandmeid): tuled ja pärjad paistavad hooajal kohapeal — " +
      "kaardikiht puudub, külasta detsembris.",
  },
  {
    param: 164,
    dim: "dim_trick_or_treat",
    nearestMap: "puudub — kvartali vaatlus + naabrite küsitlus",
    reason:
      "Kommikülastajate hulk on kvartali vaatluse hinnang (EI OLE " +
      "loendust): lastega perede tihedust hetktõmmises pole — küsi " +
      "naabritelt kohapeal, kaardikiht puudub.",
  },
  {
    param: 165,
    dim: "dim_transient_neighbors",
    nearestMap: "puudub — KÜ päring (üürikorterite osakaal)",
    reason:
      "Läbikäivate naabrite tihedus eeldaks lühiajalise üüri tiheduse " +
      "kraapimist, mida hetktõmmises pole (EI OLE hinnangut): " +
      "üürikorterite osakaal on hoone fakt — küsi KÜ-lt, ära feigi " +
      "ala skoori.",
  },
];

/**
 * OSM tags evaluated per param: NONE consumed. Every entry documents
 * the absence — these nineteen are buyer-profile slider facts and
 * block observations, and no OSM key honestly proxies taste,
 * life-stage fit, or who decorates in December. The per-listing dims
 * use no snapshot tags at all (the app serves the frozen snapshot,
 * never live Overpass).
 */
export const GROUP20A_CONSIDERED_TAGS: Record<Group20AParam, string> = {
  18: "(puudub — ostjaprofiili maitse-liugur, OSM-is signaali pole)",
  81: "(puudub — kvartali hooldusseisundi vaatlus, OSM-is signaali pole)",
  85: "(puudub — REL2021 ruudustik, hetktõmmises pole)",
  90: "(puudub — ostja kaasatuseelistus, OSM-is signaali pole)",
  98: "(puudub — korteri/hoone fakt kuulutusest, OSM-is signaali pole)",
  104: "(puudub — põrandaplaani fakt kuulutusest, OSM-is signaali pole)",
  105: "(puudub — ruumiomaduste vaatlus, OSM-is signaali pole)",
  122: "(puudub — korteri/trepikoja vaatluse fakt, OSM-is signaali pole)",
  126: "(puudub — korteri fakt + ostjaprofiili liugur, OSM-is signaali pole)",
  127: "(puudub — ostja eluetapi-liugurid, OSM-is signaali pole)",
  128: "(puudub — ostjate koosluse küsimustik, OSM-is signaali pole)",
  131: "(puudub — ostja stiili-liugur, OSM-is signaali pole)",
  133: "(puudub — ostja disaini-liugur, OSM-is signaali pole)",
  134: "(puudub — ostja sisetunne/kõhutunde veto, OSM-is signaali pole)",
  136: "(puudub — ostja privaatsus-liugur; seirekaarti hetktõmmises pole)",
  161: "(puudub — REL2021 ruudustik, hetktõmmises pole)",
  163: "(puudub — hooajaline kvartali vaatlus, OSM-is signaali pole)",
  164: "(puudub — kvartali vaatlus + naabrite küsitlus, OSM-is signaali pole)",
  165: "(puudub — lühiajalise üüri kraaping + KÜ päring, hetktõmmises pole)",
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP20A_HOOK =
  "G20A-HOOK (#212): no shared-file wiring — no layers ship, verdicts + dims only.";
