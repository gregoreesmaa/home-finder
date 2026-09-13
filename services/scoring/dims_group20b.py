"""Group 20 subjective per-listing dimensions, batch B (issue #213).

Params (this agent only — sibling batches own disjoint sets):
* p168 community mutual aid (ALWAYS None — buyer taste slider)
* p170 local volunteerism (ALWAYS None — buyer lifestyle preference)
* p239 multi-sensory garden suitability (ALWAYS None — per-parcel garden fact)
* p281 asynchronous work zones (ALWAYS None — interior layout fact)
* p283 quarantine suitability (ALWAYS None — unit layout fact)
* p349 neighborhood pet density (ALWAYS None — no registry, buyer taste)
* p380 community disaster resilience (ALWAYS None — social-capital hinnang)
* p383 intentional cohousing community (ALWAYS None — buyer lifestyle choice)
* p385 golf course errant ball risk (ALWAYS None — fairway-adjacent parcel fact)
* p388 gated community security theater (ALWAYS None — buyer value judgment)
* p390 language and cultural enclave fit (ALWAYS None — buyer identity preference)
* p398 toxic ornamental landscaping (ALWAYS None — per-garden observation fact)
* p410 biophilic design integration (ALWAYS None — interior/architecture fact)
* p413 neighborhood surveillance culture (ALWAYS None — buyer privacy preference)
* p449 holiday light traffic (ALWAYS None — seasonal block observation)
* p461 hoarder neighbor proximity (ALWAYS None — no registry, block observation)
* p488 flaw permanence (ALWAYS None — per-listing repair hinnang)
* p490 buyer timeline desperation (ALWAYS None — buyer-side urgency input)
* p500 the "gut feeling" veto (ALWAYS None — buyer's on-site veto decision)

HONESTY (AGENTS.md section 7.2): Group 20 is Tier 4 (Subjective Buyer
Alignment & Biological Intuition, parameters3.md section 5.20). The
primary source is the Buyer Preference Questionnaire (0-5 slider scale
weights, trade-off toggles, budget thresholds); the graceful fallback
is In-Person Block Observation Protocols & the 'Gut Feeling' Veto.
Neither buyer-profile sliders nor block observations are area data in
the 2026-09-12 snapshot, so every dim in this batch stays NULL with
a buyer-check reason. Reasons say "hinnang" (estimate) and "EI OLE"
(not measurable / not an area score) and name the buyer-side input —
never a faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_group03b.py (#152): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls. Unlike proxy batches there is no Overpass fragment and no tag
mapping here: there is nothing honest to query, so there is nothing
to wire (see the G20B verdict registry for the per-param record).

Helpers are local (only the Score alias is needed — all-None scorers
take no distances): a future central hook may import this module
alongside livability, and importing any of it here would turn that
into a cycle (same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p385 (golf errant-ball risk) is the one param with a tempting OSM
  proxy (golf-course polygons exist in Harjumaa). It still ships no
  map: risk is fairway-adjacent AND directional (slice-side parcels
  only), so a radial distance gradient would paint red blobs that
  penalise perfectly safe neighbours — fake precision (OTA PR #131
  precedent). It stays a per-listing buyer check (site visit + seller
  disclosure of fairway-boundary exposure).
* p390 (language/cultural enclave fit) is deliberately not mapped
  from census grids: fit is the BUYER's identity preference (a
  slider), and painting enclave gradients would be both beside the
  buyer's taste and sensitive. The questionnaire setting decides.
* p413 (surveillance culture) is deliberately not mapped from camera
  counts: counting cameras would measure the opposite of the param
  (the buyer's privacy attitude — some buyers WANT watchful streets).
* p461 (hoarder neighbour) has no registry by construction; p449
  (holiday lights) is seasonal (December-only signal); p490/p500 are
  buyer-side inputs/vetoes, not property attributes at all.
* All 19 dims return None for EVERY input including missing origin:
  inventing area scores from zero area signal would be fake
  precision. The reasons point at the questionnaire slider, the
  block observation, or the viewing the buyer must do instead.

Integration (deliberately NOT done here): there is nothing to splice
into livability.OVERPASS_QUERY / livability._POI_KIND and no
livability.WEIGHTS change — all-None dims contribute no area signal.
A future central hook only needs this module's GROUP20B_DIMS.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# p168: community mutual aid (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_mutual_aid(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p168: NULL — mutual-aid culture is a buyer-taste slider, not an area score."""
    return None, ("Naabriabi kultuur on ostja-eelistuse hinnang (küsimustiku "
                  "slider, EI OLE kaardimõõt): vajab ostja profiili sätet ja "
                  "kohapealset suhtlust, mitte piirkonna skoori — ära feigi")


# ---------------------------------------------------------------------------
# p170: local volunteerism (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_volunteerism(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p170: NULL — volunteerism is a buyer lifestyle preference, not an area score."""
    return None, ("Kohalik vabatahtlikkus on ostja elustiili-hinnang (küsimustik, "
                  "EI OLE registrimõõt): selgub kogukonnaga suheldes, mitte "
                  "hetktõmmisest — ära feigi")


# ---------------------------------------------------------------------------
# p239: multi-sensory garden suitability (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_garden_sensory(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p239: NULL — garden suitability is a per-parcel fact, not an area score."""
    return None, ("Mitmeaastase aia sobivus on krundi-põhine hinnang (EI OLE "
                  "kaardimõõt): vajab krundi vaatlust (muld, valgus, tuul), "
                  "mitte piirkonna skoori — ära feigi")


# ---------------------------------------------------------------------------
# p281: asynchronous work zones (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_work_zones(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p281: NULL — work-from-home zones are an interior layout fact."""
    return None, ("Asünkroonse töö tsoonid on korteri-põhine sisefakt (hinnang "
                  "plaanilt, EI OLE kaardimõõt): tubade arv ja paigutus loevad, "
                  "mitte asukoht — mitut tsooni vaja on, ütleb ostja küsimustik "
                  "— ära feigi")


# ---------------------------------------------------------------------------
# p283: quarantine suitability (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_quarantine(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p283: NULL — quarantine suitability is a unit-layout fact."""
    return None, ("Karantini-sobivus on elamu-põhine paigutuse hinnang (eraldi "
                  "sissepääs/tuba, EI OLE kaardimõõt): selgub plaanilt ja "
                  "vaatlusel — ära feigi")


# ---------------------------------------------------------------------------
# p349: neighborhood pet density (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_pet_density(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p349: NULL — pet density has no registry; buyer taste + block watch."""
    return None, ("Naabruskonna lemmikloomatihedust registris pole (EI OLE "
                  "mõõdetav hinnang): loeb ostja enda lemmik-eelistus "
                  "(küsimustiku slider) + bloki vaatlus — ära feigi")


# ---------------------------------------------------------------------------
# p380: community disaster resilience (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_disaster_resilience(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p380: NULL — crisis readiness is a social-capital hinnang, not a map."""
    return None, ("Kogukonna kriisivalmidus on sotsiaalse kapitali hinnang (EI OLE "
                  "kaardimõõt): vajab KOV/kogukonna päringut ja ostja "
                  "riski-eelistust (küsimustik) — ära feigi")


# ---------------------------------------------------------------------------
# p383: intentional cohousing community (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_cohousing(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p383: NULL — cohousing fit is the buyer's lifestyle choice."""
    return None, ("Kooselamise kogukond on ostja elustiili-valik (hinnang "
                  "küsimustikus, EI OLE piirkonna skoor): kas ostja tahab "
                  "ühiselu, otsustab ostja — ära feigi")


# ---------------------------------------------------------------------------
# p385: golf course errant ball risk (no honest gradient — always None).
# ---------------------------------------------------------------------------

def dim_golf_ball_risk(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p385: NULL — fairway-adjacent parcel fact; a radial gradient would fake it."""
    return None, ("Eksinud golfipalli risk on krundi-põhine rajaääre-fakt (hinnang: "
                  "kas krunt langeb löögisuunda, EI OLE raadiuse-gradient): "
                  "kauguskiht karistaks ka ohutuid naabreid — vajab kohapealset "
                  "kontrolli ja müüja teavet — ära feigi")


# ---------------------------------------------------------------------------
# p388: gated community security theater (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_gated_security(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p388: NULL — gated security is a buyer value judgment, not an area score."""
    return None, ("Suletud kogukonna turvateater on ostja väärtushinnang "
                  "(küsimustiku slider, EI OLE kaardimõõt): kas värav rahustab "
                  "või võõrandab, otsustab ostja — ära feigi")


# ---------------------------------------------------------------------------
# p390: language and cultural enclave fit (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_culture_enclave(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p390: NULL — enclave fit is the buyer's identity preference."""
    return None, ("Keele-/kultuurikoloonia sobivus on ostja identiteedi-eelistuse "
                  "hinnang (küsimustik, EI OLE kaardiskoor): koloonia "
                  "kaardistamine läheks ostja maitsest mööda — otsustab ostja "
                  "profiil — ära feigi")


# ---------------------------------------------------------------------------
# p398: toxic ornamental landscaping (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_toxic_planting(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p398: NULL — toxic ornamentals are a per-garden observation fact."""
    return None, ("Mürgised ilutaimed on aia-põhine vaatlusfakt (hinnang kohapeal, "
                  "EI OLE kaardimõõt): liigid selguvad krundil, mitte "
                  "hetktõmmisest — ära feigi")


# ---------------------------------------------------------------------------
# p410: biophilic design integration (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_biophilic(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p410: NULL — biophilic design is an interior/architecture fact."""
    return None, ("Biofiilne disain on interjööri/arhitektuuri hinnang (EI OLE "
                  "kaardimõõt): materjalid, valgus ja rohelus selguvad ostja "
                  "vaatlusel (küsimustiku slider seab kaalu) — ära feigi")


# ---------------------------------------------------------------------------
# p413: neighborhood surveillance culture (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_surveillance_culture(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p413: NULL — surveillance attitude is a buyer privacy preference."""
    return None, ("Naabrivalve-kultuur on ostja privaatsuseelistuse hinnang "
                  "(küsimustiku slider, EI OLE kaameratiheduse skoor): kaamerate "
                  "lugemine mõõdaks vastupidist — otsustab ostja — ära feigi")


# ---------------------------------------------------------------------------
# p449: holiday light traffic (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_holiday_lights(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p449: NULL — holiday-light traffic is a seasonal block observation."""
    return None, ("Pühadevalgustuse liiklus on hooajaline bloki-vaatlus (hinnang "
                  "detsembris, EI OLE aastaringne kaardimõõt): selgub kohapeal "
                  "hooajal + ostja pühade-eelistusest (küsimustik) — ära feigi")


# ---------------------------------------------------------------------------
# p461: hoarder neighbor proximity (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_hoarder_neighbor(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p461: NULL — no hoarder registry exists; block observation only."""
    return None, ("Kogujanaabri lähedust registris pole (EI OLE mõõdetav hinnang): "
                  "selgub ainult bloki vaatlusel ja müüja teabest — ära feigi")


# ---------------------------------------------------------------------------
# p488: flaw permanence (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_flaw_permanence(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p488: NULL — flaw permanence is a per-listing repair hinnang."""
    return None, ("Puuduse püsivus on pakkumise-põhine remondihinnang (kas viga on "
                  "parandatav, EI OLE piirkonna skoor): vajab ostja kohapealset "
                  "ülevaatust/inspektorit, mitte kaarti — ära feigi")


# ---------------------------------------------------------------------------
# p490: buyer timeline desperation (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_timeline_desperation(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """p490: NULL — timeline urgency is the buyer's own input, not a place fact."""
    return None, ("Ostja ajahäda on ostja enda sisendi hinnang (kui kiirelt on vaja "
                  "kolida, EI OLE kaardimõõt): kaalu seab ostja profiil "
                  "(küsimustik), mitte asukoht — ära feigi")


# ---------------------------------------------------------------------------
# p500: the "gut feeling" veto (no area signal — always None).
# ---------------------------------------------------------------------------

def dim_gut_veto(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p500: NULL — the gut veto is the buyer's on-site decision, not a score."""
    return None, ("Kõhutunde veto on ostja isiklik bloki-vaatluse hinnang (kohapeal, "
                  "EI OLE skooritav): kui koht tundub vale, langeb pakkumine "
                  "välja — kaarti sellele pole — ära feigi")


GROUP20B_DIMS = (
    ("mutual_aid", "p168", dim_mutual_aid),
    ("volunteerism", "p170", dim_volunteerism),
    ("garden_sensory", "p239", dim_garden_sensory),
    ("work_zones", "p281", dim_work_zones),
    ("quarantine", "p283", dim_quarantine),
    ("pet_density", "p349", dim_pet_density),
    ("disaster_resilience", "p380", dim_disaster_resilience),
    ("cohousing", "p383", dim_cohousing),
    ("golf_ball_risk", "p385", dim_golf_ball_risk),
    ("gated_security", "p388", dim_gated_security),
    ("culture_enclave", "p390", dim_culture_enclave),
    ("toxic_planting", "p398", dim_toxic_planting),
    ("biophilic", "p410", dim_biophilic),
    ("surveillance_culture", "p413", dim_surveillance_culture),
    ("holiday_lights", "p449", dim_holiday_lights),
    ("hoarder_neighbor", "p461", dim_hoarder_neighbor),
    ("flaw_permanence", "p488", dim_flaw_permanence),
    ("timeline_desperation", "p490", dim_timeline_desperation),
    ("gut_veto", "p500", dim_gut_veto),
)


def score_group20b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All nineteen Group 20 batch-B dims for one listing (entry point for
    the weight-rebalance follow-up; keys match GROUP20B_DIMS). Every value
    is None by design — buyer-profile inputs carry no area signal."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP20B_DIMS}
