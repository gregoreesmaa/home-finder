"""Group 4 title/legal per-listing dimensions (issue #204).

Params (this agent only — sibling batches own disjoint sets), names from
parameters3.md section 5.4 (truncated table names reconstructed from the
DB column names in the same rows):
* p76  mineral, water, and timber rights (dim_mineral_timber_rights)
* p80  deed covenants, non-HOA (dim_deed_covenants)
* p139 property stigma (dim_property_stigma)
* p144 title cleanliness (dim_title_cleanliness)
* p229 mineral right severances (dim_mineral_severance)
* p242 stigmatized property laws (dim_stigma_laws)
* p248 existing lease encumbrances (dim_lease_encumbrance)
* p271 view preservation covenants (dim_view_covenant)
* p274 air rights (dim_air_rights)
* p276 adverse possession risks (dim_adverse_possession)
* p279 morals clauses in deeds (dim_morals_clause)
* p361 trust and LLC transferability (dim_trust_llc_transfer)
* p362 probate and estate sale delays (dim_probate_delay)
* p364 ground lease realities (dim_ground_lease)
* p367 squatter and holdover laws (dim_squatter_holdover)
* p369 co-op board approval (dim_coop_approval)
* p428 title cloud resolution (dim_title_cloud)

HONESTY (AGENTS.md section 7.2): the primary source for the whole group
is e-Kinnistusraamat (RIK X-Road / commercial portal, Tier 2 PAID
registry) — it is NOT in the OSM snapshot by construction, so ALL
seventeen dims stay NULL with a concrete buyer-check reason. Reasons
say "hinnang" (estimate) and "EI OLE" (no estimate available) and name
the check the buyer must do instead (registry extract, notary title
audit, Ametlikud Teadaanded, e-Äriregister pledge register, KKIS) —
never a faked score. Precedent: p71 easements NULL dim, #151.

Style mirrors services/scoring/dims_group03.py NULL dims (p68/p71/p75,
#151): every scorer is pure and offline-tested — (origin, pois) ->
(None, Estonian reason). No Overpass fragment, no POI kinds, no tag
mapping: there is no tag family to fetch (zero deed/lien/mortgage/
lease/covenant keys county-wide — see GROUP04_EVIDENCE in
apps/web/lib/layers_group04.ts), so the NULL dims need no fetch at all.

Tag verification (2026-09-13, done once by the author with osmium
tags-count against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf,
NOT at runtime; 2627 distinct keys scanned):
* deed/lien/mortgage/lease/covenant: 0 each — nothing to calibrate.
* owner 13 + ownership 1 vs institutional operator 7710: the only
  owner-ish tags mark managed facilities, never parcel title.
* board:title 146 (signage) + protection_title 41 (heritage) are name
  strings, not ownership facts.

Judgment calls (reviewable per AGENTS.md section 7.5):
* ALL seventeen return None for EVERY input including missing origin:
  inventing a gradient from zero registry signal would be fake
  precision (OTA PR #131 precedent). p139/p242 (stigma) deliberately
  stay NULL too: no incident archive is in the snapshot, and a
  crime-proximity gradient would brand whole streets on unproven
  per-parcel history.
* p271 (view covenants) stays NULL even though height models exist:
  a viewshed shows what is visible today, not what the deed forbids
  building — the legal question needs the covenant text.
* p362 (probate delays) stays NULL: Ametlikud Teadaanded notices are
  the honest signal and are not in the snapshot; OSM has no proxy.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / _POI_KIND wiring (nothing to fetch) and no
WEIGHTS edit — rebalancing livability.WEIGHTS must be one joint change
across all parameter batches (existing tests pin set(WEIGHTS) exactly,
so per-batch WEIGHTS edits would break every sibling).
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_mineral_timber_rights(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """p76: NULL — mineral/water/timber rights are registry facts (no map)."""
    return None, ("Maavara-, vee- ja puiduõiguste info e-Kinnistusraamatust "
                  "snapshots pole (EI OLE hinnangut; OSM-is deed-märgendeid "
                  "pole) — kontrolli kinnistusraamatu väljavõtet notari "
                  "õigusauditis")


def dim_deed_covenants(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p80: NULL — deed covenants are per-parcel contract facts (no map)."""
    return None, ("Kitsenduste (mitte-ühistu) info e-Kinnistusraamatust/KKIS-ist "
                  "snapshots pole (EI OLE hinnangut; covenant-märgendeid "
                  "OSM-is pole) — kontrolli kinnistusraamatu väljavõtet")


def dim_property_stigma(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p139: NULL — stigma is per-parcel history, never an area gradient."""
    return None, ("Stigma-ajaloo (surm/kuritegu) arhiivi snapshots pole "
                  "(EI OLE hinnangut; lähedus-gradient brändiks terve "
                  "tänava) — küsi müüjalt/notarilt avaldamiskohustuse "
                  "täitmist")


def dim_title_cleanliness(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p144: NULL — title cleanliness needs the registry extract (no map)."""
    return None, ("Omandi puhtuse (koormatised, pandiõigused) päringut "
                  "e-Kinnistusraamatust snapshots pole (EI OLE hinnangut) "
                  "— telli notari õigusaudit enne broneerimislepingut")


def dim_mineral_severance(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p229: NULL — mineral severances are registry facts (no map)."""
    return None, ("Maavaraõiguste eraldamise info e-Kinnistusraamatust "
                  "snapshots pole (EI OLE hinnangut) — kontrolli "
                  "kinnistusraamatu väljavõtet notari õigusauditis")


def dim_stigma_laws(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p242: NULL — stigma statutes are law, not a map layer."""
    return None, ("Stigma-avaldamiskohustuse statuudi sisu snapshots pole "
                  "(EI OLE hinnangut; gradient ei lahenda krundi "
                  "avaldamisküsimust) — küsi notari/õigusnõu hinnangut")


def dim_lease_encumbrance(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p248: NULL — lease encumbrances are registry facts (no map)."""
    return None, ("Üüri-/rendikoormatiste info e-Kinnistusraamatust "
                  "snapshots pole (EI OLE hinnangut; lease-märgendeid "
                  "OSM-is pole) — kontrolli kinnistusraamatu väljavõtet "
                  "ja üürilepinguid")


def dim_view_covenant(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p271: NULL — view covenants are contract text, not a viewshed."""
    return None, ("Vaate-kitsenduse lepinguteksti snapshots pole (EI OLE "
                  "hinnangut; kõrgusmudel näitab vaadet, mitte keeldu) "
                  "— kontrolli kinnistusraamatu väljavõtet")


def dim_air_rights(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p274: NULL — air rights are registry facts (no map)."""
    return None, ("Õhuõiguste (krundi-kohase ehitusõiguse) info "
                  "e-Kinnistusraamatust snapshots pole (EI OLE hinnangut) "
                  "— kontrolli kinnistusraamatu väljavõtet ja "
                  "detailplaneeringut")


def dim_adverse_possession(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p276: NULL — adverse possession is a per-parcel legal fact (no map)."""
    return None, ("Igamisriski kasutusajaloo tõendeid snapshots pole (EI "
                  "OLE hinnangut) — kontrolli kinnistusraamatu väljavõtet "
                  "ja katastri piirimõõdistust")


def dim_morals_clause(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p279: NULL — morals clauses are deed text, not a map layer."""
    return None, ("Moraaliklausli lepinguteksti e-Kinnistusraamatust "
                  "snapshots pole (EI OLE hinnangut) — kontrolli "
                  "kinnistusraamatu väljavõtet")


def dim_trust_llc_transfer(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """p361: NULL — transfer structure is a per-deal legal fact (no map)."""
    return None, ("Usaldusfondi/osaühingu omandistruktuuri snapshots pole "
                  "(EI OLE hinnangut) — kontrolli notari ja "
                  "e-Äriregistri päringuga")


def dim_probate_delay(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p362: NULL — probate state needs notices, not geometry."""
    return None, ("Pärimismenetluse teateid (Ametlikud Teadaanded) "
                  "snapshots pole (EI OLE hinnangut) — kontrolli "
                  "Ametlikke Teadaandeid ja notarilt menetluse seisu")


def dim_ground_lease(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p364: NULL — ground-lease terms are registry facts (no map)."""
    return None, ("Hoonestusõiguse/rendi tingimuste infot "
                  "e-Kinnistusraamatust snapshots pole (EI OLE hinnangut) "
                  "— kontrolli kinnistusraamatu väljavõtet")


def dim_squatter_holdover(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p367: NULL — occupation history is a per-parcel fact (no map)."""
    return None, ("Asustusajaloo (ebaseaduslik asustus/üürniku jäämine) "
                  "andmeid snapshots pole (EI OLE hinnangut) — kontrolli "
                  "kinnistusraamatu väljavõtet ja krundi kohapeal")


def dim_coop_approval(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p369: NULL — co-op approval is a building-level fact (no map)."""
    return None, ("Ühistu põhikirja/nõusoleku infot snapshots pole (EI OLE "
                  "hinnangut; maja-, mitte piirkonnafakt) — küsi "
                  "ühistult/müüjalt kirjalikku kinnitust")


def dim_title_cloud(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p428: NULL — title-cloud resolution needs a legal audit (no map)."""
    return None, ("Omandi hägususe (vaidlused, kohtuotsused Riigi Teatajas) "
                  "andmeid snapshots pole (EI OLE hinnangut) — telli "
                  "notari õigusaudit enne broneerimislepingut")


GROUP04_DIMS = (
    ("mineral_timber_rights", "p76", dim_mineral_timber_rights),
    ("deed_covenants", "p80", dim_deed_covenants),
    ("property_stigma", "p139", dim_property_stigma),
    ("title_cleanliness", "p144", dim_title_cleanliness),
    ("mineral_severance", "p229", dim_mineral_severance),
    ("stigma_laws", "p242", dim_stigma_laws),
    ("lease_encumbrance", "p248", dim_lease_encumbrance),
    ("view_covenant", "p271", dim_view_covenant),
    ("air_rights", "p274", dim_air_rights),
    ("adverse_possession", "p276", dim_adverse_possession),
    ("morals_clause", "p279", dim_morals_clause),
    ("trust_llc_transfer", "p361", dim_trust_llc_transfer),
    ("probate_delay", "p362", dim_probate_delay),
    ("ground_lease", "p364", dim_ground_lease),
    ("squatter_holdover", "p367", dim_squatter_holdover),
    ("coop_approval", "p369", dim_coop_approval),
    ("title_cloud", "p428", dim_title_cloud),
)


def score_group04(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All seventeen Group 4 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP04_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP04_DIMS}
