"""Group 20 subjective-A per-listing dimensions (issue #212).

Params (this agent only — sibling batches own disjoint sets):
* p18 neighbourhood vibe (ALWAYS None — buyer taste slider, do not fake)
* p81 pride of ownership on the block (ALWAYS None — block observation)
* p85 neighbourhood demographic balance (ALWAYS None — REL2021 not in snapshot)
* p90 civic and social engagement (ALWAYS None — buyer engagement slider)
* p98 universal design / accessibility (ALWAYS None — per-listing fact)
* p104 entertaining capacity (ALWAYS None — floorplan fact)
* p105 creative/studio potential (ALWAYS None — room-attribute fact)
* p122 child safety features (ALWAYS None — per-listing walkthrough fact)
* p126 pet-specific architecture (ALWAYS None — per-listing fact)
* p127 downsizing suitability (ALWAYS None — buyer life-stage slider)
* p128 co-buying compatibility (ALWAYS None — buyer-group questionnaire)
* p131 architectural style (ALWAYS None — buyer taste slider, do not fake)
* p133 design philosophies (ALWAYS None — buyer taste slider)
* p134 emotional resonance (ALWAYS None — gut-feeling veto, buyer only)
* p136 technological privacy (ALWAYS None — buyer sensitivity slider)
* p161 local political and civic alignment (ALWAYS None — REL2021 not in snapshot)
* p163 holiday decorating culture (ALWAYS None — seasonal block observation)
* p164 trick-or-treater volume (ALWAYS None — block observation, no count)
* p165 transient neighbour density (ALWAYS None — STR scrape not in snapshot)

HONESTY (AGENTS.md section 7.2): Group 20's primary source is the Buyer
Preference Questionnaire (0-5 slider weights, trade-off toggles, budget
thresholds) plus in-person block observation protocols and the "gut
feeling" veto (p500) — none of which exist in the 2026-09-12 snapshot
by construction. The alternates (Statistikaamet REL2021 1 km grid
tables RL21004/RL21202, Inside-Airbnb / Booking.com transient density
scrapers) are likewise absent. Every dim therefore returns None for
EVERY input including missing origin: inventing an area gradient for a
buyer-side fact would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
buyer-side input (profile slider, listing walkthrough, block
observation, KÜ enquiry) — never a faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_group03b.py (#152): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls. Unlike proxy batches it also adds no Overpass fragment and no
tag mapping: there is no honest snapshot tag to query for taste,
life-stage fit, or December decorations, so there is nothing for the
live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* All nineteen stay NULL even where a theoretically mappable cousin
  exists (p85/p161 census grids, p165 STR density): the cousin source
  is not in the snapshot, and a census-grid gradient would score the
  AREA's composition, not the BUYER's fit — the param's actual
  question. Scoring composition as fit misleads by construction.
* Per-listing facts (p98/p104/p105/p122/p126) stay NULL rather than
  scoring listing-text keywords: keyword NLP is a portal-adapter job
  (Group 1), not a place dim, and stuffing it here would double-score
  the ad text.
* The reasons name the concrete buyer-side check (küsimustiku
  liugur, kuulutuse + vaatlus, kvartali vaatlus, KÜ päring) so the
  NULL is actionable, not a dead end.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# p18/p81/p85/p90/p98/p104/p105/p122/p126/p127/p128/p131/p133/p134/p136/
# p161/p163/p164/p165: documented no-map buyer-side NULLs (OTA PR #131
# precedent). Each is a buyer-profile slider fact, a per-listing /
# per-building walkthrough fact, or a block observation with no honest
# area signal; the scorer reports the gap with a concrete buyer-side
# check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_neighborhood_vibe(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p18: NULL — neighbourhood vibe is a buyer taste-slider fact (no map)."""
    return None, ("Naabruskonna hõng on ostja maitse-hinnang (EI OLE kaardikiht): "
                  "see sõltub ostjaprofiili küsimustiku liuguritest, mitte piirkonna "
                  "andmetest — hinda kohapealsel jalutuskäigul, ära feigi ala skoori")


def dim_pride_of_ownership(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p81: NULL — pride of ownership is a block-observation fact (no map)."""
    return None, ("Uhkus kvartali üle on kohapealse vaatluse hinnang (EI OLE "
                  "registriandmeid): hoovide ja fassaadide hooldusseisundit "
                  "hetktõmmises pole — vaata kvartal üle jalgsi, kaardikiht puudub")


def dim_demographic_balance(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p85: NULL — demographics need the REL2021 grid, absent here (no map)."""
    return None, ("Demograafiline tasakaal eeldaks Statistikaameti REL2021 1 km "
                  "ruudustikku, mida hetktõmmises pole (EI OLE hinnangut): sobivus "
                  "tuleneb ostjaprofiili eelistusest, mitte ala skoorist — ära feigi")


def dim_civic_engagement(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p90: NULL — civic engagement is a buyer participation-slider fact (no map)."""
    return None, ("Kodanikuaktiivsus on ostja osaluseelistuse hinnang (EI OLE "
                  "kaardikiht): seltside ja ürituste tihedust hetktõmmises pole — "
                  "märgi oma kaasatuse liugur küsimustikus, ala skoor puudub")


def dim_universal_design(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p98: NULL — accessibility is a per-listing/per-building fact (no map)."""
    return None, ("Ligipääsetavus on konkreetse korteri ja hoone fakt (EI OLE ala "
                  "skoor): lift, lävepakud ja ukse laiused selguvad kuulutusest ja "
                  "vaatluselt — hinnang tuleb vaatluselt, mitte kaardilt")


def dim_entertaining_capacity(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p104: NULL — entertaining capacity is a floorplan fact (no map)."""
    return None, ("Võõrustamisvõimekus on põrandaplaani fakt (EI OLE kaardikiht): "
                  "tubade arv ja avatud köök-elutuba on kuulutuse andmed — "
                  "ostjaprofiili seltsielu-liugur kaalub, kaardi-hinnang puudub")


def dim_studio_potential(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p105: NULL — studio potential is a room-attribute fact (no map)."""
    return None, ("Stuudiopotentsiaal on ruumiomaduste hinnang (EI OLE alaandmeid): "
                  "valgus, lae kõrgus ja eraldi sissepääs selguvad kuulutusest ja "
                  "vaatluselt — kaardikiht puudub, ära feigi")


def dim_child_safety(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p122: NULL — child safety is a per-listing walkthrough fact (no map)."""
    return None, ("Lapsuturvalisus on korteri ja trepikoja fakt (EI OLE kaardikiht): "
                  "pistikukaitsed, rõdupiirded ja trepikoja värav selguvad vaatlusel "
                  "— KOV intsidentide tabelit hetktõmmises pole, hinnang tuleb kohapealt")


def dim_pet_architecture(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p126: NULL — pet architecture is a per-listing fact (no map)."""
    return None, ("Lemmikulooma-sobiv arhitektuur on korteri fakt (EI OLE ala "
                  "skoor): põrandamaterjal, rõdu ja jalutusmetsa eelistus tulevad "
                  "kuulutusest ja ostjaprofiilist — kaardi-hinnang puudub")


def dim_downsizing(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p127: NULL — downsizing fit is a buyer life-stage slider fact (no map)."""
    return None, ("Kahandamise sobivus on eluetapi-eelistuse hinnang (EI OLE "
                  "kaardikiht): ühe tasapinna soov ja hoolduskoormuse taluvus on "
                  "ostjaprofiili liugurid, mitte piirkonna fakt — ära feigi")


def dim_cobuying(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p128: NULL — co-buying fit is a buyer-group questionnaire fact (no map)."""
    return None, ("Koosostu sobivus on ostjate koosluse hinnang (EI OLE alaandmeid): "
                  "eraldi tiibade ja privaatsuse vajadus selgub ostjaprofiili "
                  "küsimustikust, mitte kaardilt — kaardikiht puudub")


def dim_architectural_style(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p131: NULL — architectural style is a buyer taste-slider fact (no map)."""
    return None, ("Arhitektuuristiil on maitse-eelistuse hinnang (EI OLE kaardikiht): "
                  "puit, paneel või uusarendus meeldib või ei — ostjaprofiili "
                  "stiili-liugur otsustab, ala skoor puudub")


def dim_design_philosophy(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p133: NULL — design philosophy is a buyer taste-slider fact (no map)."""
    return None, ("Disainifilosoofia on maitse-hinnang (EI OLE registriandmeid): "
                  "minimalism või hubasus ei ole kaardistatav — ostjaprofiili "
                  "küsimustik kaalub, kaardikiht puudub")


def dim_emotional_resonance(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p134: NULL — emotional resonance is the buyer's gut-feeling veto (no map)."""
    return None, ("Emotsionaalne kõla on sisetunde-hinnang (EI OLE mõõdetav): "
                  "kõhutunde veto kuulub ostjale, mitte kaardile — ükski ala skoor "
                  "ei asenda kohapealset vaatlust")


def dim_tech_privacy(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p136: NULL — tech privacy is a buyer sensitivity-slider fact (no map)."""
    return None, ("Tehnoloogiline privaatsus on ostja tundlikkuse hinnang (EI OLE "
                  "kaardikiht): kaamerate ja nutiseadmete taluvus on ostjaprofiili liugur "
                  "— hetktõmmises pole seirekaarti, ära feigi")


def dim_civic_alignment(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p161: NULL — civic alignment needs the REL2021 grid, absent here (no map)."""
    return None, ("Poliitiline ja kodaniku-ühtekuuluvus eeldaks REL2021 ruudustikku, "
                  "mida hetktõmmises pole (EI OLE hinnangut): väärtusruumi sobivus "
                  "on ostjaprofiili küsimus, mitte ala skoor — ära feigi")


def dim_holiday_decor(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p163: NULL — holiday decor is a seasonal block-observation fact (no map)."""
    return None, ("Pühade-kaunistamise kultuur on kvartali vaatluse hinnang (EI OLE "
                  "registriandmeid): tuled ja pärjad paistavad hooajal kohapeal — "
                  "kaardikiht puudub, külasta detsembris")


def dim_trick_or_treat(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p164: NULL — trick-or-treater volume is a block-observation fact (no map)."""
    return None, ("Kommikülastajate hulk on kvartali vaatluse hinnang (EI OLE "
                  "loendust): lastega perede tihedust hetktõmmises pole — küsi "
                  "naabritelt kohapeal, kaardikiht puudub")


def dim_transient_neighbors(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p165: NULL — transient density needs the STR scrape, absent here (no map)."""
    return None, ("Läbikäivate naabrite tihedus eeldaks lühiajalise üüri tiheduse "
                  "kraapimist, mida hetktõmmises pole (EI OLE hinnangut): "
                  "üürikorterite osakaal on hoone fakt — küsi KÜ-lt, ära feigi "
                  "ala skoori")


GROUP20A_DIMS = (
    ("vibe", "p18", dim_neighborhood_vibe),
    ("pride_ownership", "p81", dim_pride_of_ownership),
    ("demographic_balance", "p85", dim_demographic_balance),
    ("civic_engagement", "p90", dim_civic_engagement),
    ("universal_design", "p98", dim_universal_design),
    ("entertaining", "p104", dim_entertaining_capacity),
    ("studio_potential", "p105", dim_studio_potential),
    ("child_safety", "p122", dim_child_safety),
    ("pet_arch", "p126", dim_pet_architecture),
    ("downsizing", "p127", dim_downsizing),
    ("cobuying", "p128", dim_cobuying),
    ("arch_style", "p131", dim_architectural_style),
    ("design_philosophy", "p133", dim_design_philosophy),
    ("emotional_resonance", "p134", dim_emotional_resonance),
    ("tech_privacy", "p136", dim_tech_privacy),
    ("civic_alignment", "p161", dim_civic_alignment),
    ("holiday_decor", "p163", dim_holiday_decor),
    ("trick_or_treat", "p164", dim_trick_or_treat),
    ("transient_neighbors", "p165", dim_transient_neighbors),
)


def score_group20a(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All nineteen Group 20 batch-A dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP20A_DIMS). Every value is
    None by design — buyer-side facts, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP20A_DIMS}
