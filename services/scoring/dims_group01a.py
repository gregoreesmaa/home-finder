"""Group 1 listing-portal per-listing dimensions, batch A (issue #202).

Params (this agent only — sibling batches own disjoint sets):
* p1 purchase price (listing fact — ALWAYS None)
* p5 utility costs (listing fact — ALWAYS None)
* p22 number of bedrooms (floorplan fact — ALWAYS None)
* p23 number of bathrooms (floorplan fact — ALWAYS None)
* p24 floor plan flow (broker-NLP score — ALWAYS None)
* p25 kitchen functionality (broker-NLP score — ALWAYS None)
* p26 dedicated workspace (broker-NLP score — ALWAYS None)
* p27 storage space (broker-NLP score — ALWAYS None)
* p28 parking and garage (listing fact — ALWAYS None)
* p32 move-in readiness (broker-NLP score — ALWAYS None)
* p36 quality of finishes (photo/visit fact — ALWAYS None)
* p37 outdoor living space (listing fact — ALWAYS None)
* p39 smart home features (listing fact — ALWAYS None)
* p92 primary suite isolation (floorplan fact — ALWAYS None)
* p93 laundry room placement (floorplan fact — ALWAYS None)
* p94 mudroom and entry transition (floorplan fact — ALWAYS None)
* p99 flex space and outbuildings (listing fact — ALWAYS None)
* p109 heavy gear storage (listing fact — ALWAYS None)
* p110 outdoor kitchen potential (listing fact — ALWAYS None)
* p119 backup heating sources (listing fact — ALWAYS None)

HONESTY (AGENTS.md section 7.2): Group 1 is Tier 1 scraped/ingested
syndication (parameters3.md section 5.1: KV.ee, City24, Kinnisvara24,
broker KVXML feeds, broker-NLP extraction). Every param in this batch
describes ONE listing — its price, its floorplan, its kitchen — never
the area around it. The 2026-09-12 OSM snapshot carries no area signal
that discriminates these per-listing facts (a "nearest mapped parking"
proxy for p28 would score the neighbourhood's parking, not THIS
listing's garage — fake precision, OTA PR #131 precedent), so all
twenty dims stay NULL with a buyer-check reason. Reasons say "hinnang"
(estimate) and "EI OLE" (there is no estimate here) and name the
listing artefact the buyer must check instead — never a measured
price, count, or score.

Style mirrors sibling batch dims_group03b.py (#152): every scorer is
pure and offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois; this
module adds no network calls and no Overpass fragment — there is
nothing honest to query for per-listing facts.

Helpers are deliberately absent (not even local copies): NULL dims
need no distance math, and importing livability or sibling batches
here would turn a future central hook into a cycle (same precedent
as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* All twenty dims return None for EVERY input including missing
  origin: inventing a score from zero signal would be fake precision.
* p28 parking is the closest call: OSM maps parking lots, but area
  parking density says nothing about whether THIS listing includes a
  garage or reserved spot, so it stays NULL with a kuulutus-check
  reason rather than a misleading proxy.
* p1/p5 stay NULL even though Maa-amet transaction data exists in
  principle: it is not in the snapshot, and a map gradient of past
  area sales is not this listing's asking price or utility bill.

Integration (deliberately NOT done here): there is no
GROUP01A_OVERPASS_FRAGMENT and no GROUP01A_POI_KIND — NULL dims need
no live-path wiring. Consuming these dims (listing-DB values with
NULL-as-missing semantics) plus rebalancing livability.WEIGHTS must
be one joint change across all parameter batches — existing tests
pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break
every sibling.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_purchase_price(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p1: NULL — asking price is a listing fact, no area signal (do not fake)."""
    return None, ("Ostuhind on kuulutuse-fakt, millele snapshotis piirkonna-signaali "
                  "pole (EI OLE hinnangut): võrdle kuulutuse hinda Maa-ameti "
                  "tehinguandmete ja maakleri KOV-tabeliga, ära feigi")


def dim_utility_costs(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p5: NULL — utility bills are a listing fact, no area signal (do not fake)."""
    return None, ("Kõrvalkulud on kuulutuse-fakt (KÜ eelarve / kommunaalide väljavõte), "
                  "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): "
                  "küsi maaklerilt viimase 12 kuu arveid, ära feigi")


def dim_bedrooms(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p22: NULL — bedroom count is a floorplan fact (do not fake)."""
    return None, ("Magamistubade arv on korruseplaani fakt, millele snapshotis "
                  "piirkonna-signaali pole (EI OLE hinnangut): loe tubade arv "
                  "kuulutuse plaanilt, mitte naabruskonna kaardilt, ära feigi")


def dim_bathrooms(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p23: NULL — bathroom count is a floorplan fact (do not fake)."""
    return None, ("Vannitubade arv on korruseplaani fakt, millele snapshotis "
                  "piirkonna-signaali pole (EI OLE hinnangut): kontrolli "
                  "sanitaarruumide arvu kuulutuse plaanilt ja fotodelt, ära feigi")


def dim_floor_plan_flow(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p24: NULL — plan flow is a broker-NLP per-listing score (do not fake)."""
    return None, ("Plaanilahenduse voolavus on maakleri-NLP kuulutuse-põhine hinne, "
                  "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): "
                  "hinda läbikäidavust kohapeal plaaniga käes, ära feigi")


def dim_kitchen(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p25: NULL — kitchen functionality is a per-listing score (do not fake)."""
    return None, ("Köögi funktsionaalsus on kuulutuse-põhine hinne (seadmed, "
                  "tööpinnad, paigutus), millele snapshotis piirkonna-signaali pole "
                  "(EI OLE hinnangut): kontrolli fotodelt ja kohapeal, ära feigi")


def dim_workspace(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p26: NULL — dedicated workspace is a per-listing fact (do not fake)."""
    return None, ("Eraldi tööruumi olemasolu on kuulutuse-fakt, millele snapshotis "
                  "piirkonna-signaali pole (EI OLE hinnangut): otsi plaanilt "
                  "suletavat kabinetti/kontorinurka, ära feigi")


def dim_storage(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p27: NULL — storage space is a per-listing fact (do not fake)."""
    return None, ("Hoiuruumi maht (panipaik, garderoob, sahver) on kuulutuse-fakt, "
                  "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): "
                  "küsi panipaiga m2 kuulutusest, ära feigi")


def dim_parking(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p28: NULL — area parking density is NOT this listing's garage (do not fake)."""
    return None, ("Parkimine/garaaž on kuulutuse-fakt (koha number, hind ja "
                  "omandivorm), millele snapshotis ausat piirkonna-signaali pole "
                  "(EI OLE hinnangut): kaardistatud parklad ei tõlgi, kas SELLES "
                  "kuulutuses on koht, ära feigi")


def dim_move_in_readiness(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p32: NULL — move-in readiness is a per-listing condition score (do not fake)."""
    return None, ("Sissekolimise valmidus on kuulutuse-põhine seisukorra hinne, "
                  "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): "
                  "hinda remondivajadust fotode ja kohapealse ülevaatusega, ära feigi")


def dim_finishes(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p36: NULL — finish quality is a photo/visit fact (do not fake)."""
    return None, ("Viimistluse kvaliteet on foto/külastuse fakt, millele snapshotis "
                  "piirkonna-signaali pole (EI OLE hinnangut): hinda materjale "
                  "fotodelt ja kohapeal, ära feigi")


def dim_outdoor_living(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p37: NULL — outdoor living space is a per-listing fact (do not fake)."""
    return None, ("Õue-eluruum (rõdu, terrass, aed) on kuulutuse-fakt, millele "
                  "snapshotis piirkonna-signaali pole (EI OLE hinnangut): kontrolli "
                  "pinna m2 ja orientatsiooni kuulutusest, ära feigi")


def dim_smart_home(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p39: NULL — smart home features are a per-listing fact (do not fake)."""
    return None, ("Nutikodu funktsioonid on kuulutuse-fakt, millele snapshotis "
                  "piirkonna-signaali pole (EI OLE hinnangut): küsi seadmete "
                  "nimekirja ja juhtimisplatvormi maaklerilt, ära feigi")


def dim_primary_suite(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p92: NULL — primary suite isolation is a floorplan fact (do not fake)."""
    return None, ("Magamistoa eraldatus (oma vannituba/garderoob) on korruseplaani "
                  "fakt, millele snapshotis piirkonna-signaali pole (EI OLE "
                  "hinnangut): loe plaanilt privaatsust, ära feigi")


def dim_laundry(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p93: NULL — laundry placement is a floorplan fact (do not fake)."""
    return None, ("Pesuruumi paigutus on korruseplaani fakt, millele snapshotis "
                  "piirkonna-signaali pole (EI OLE hinnangut): otsi plaanilt "
                  "eraldi pesuruumi või -nurka, ära feigi")


def dim_mudroom(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p94: NULL — mudroom/entry transition is a floorplan fact (do not fake)."""
    return None, ("Esiku/porandaruumi üleminek on korruseplaani fakt, millele "
                  "snapshotis piirkonna-signaali pole (EI OLE hinnangut): hinda "
                  "esiku suurust ja porandavahet plaanilt, ära feigi")


def dim_flex_space(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p99: NULL — flex space/outbuildings are a per-listing fact (do not fake)."""
    return None, ("Paindlik lisa-pind (kõrvalhooned, abihooned) on kuulutuse-fakt, "
                  "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): "
                  "kontrolli abihoonete registriandmeid ja kuulutuse loetelu, "
                  "ära feigi")


def dim_gear_storage(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p109: NULL — heavy gear storage is a per-listing fact (do not fake)."""
    return None, ("Rasketehnika hoiustamise võimalus on kuulutuse-fakt, millele "
                  "snapshotis piirkonna-signaali pole (EI OLE hinnangut): küsi "
                  "garaaži kõrgust, uste laiust ja kandevõimet, ära feigi")


def dim_outdoor_kitchen(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p110: NULL — outdoor kitchen potential is a per-listing fact (do not fake)."""
    return None, ("Väliköögi potentsiaal on kuulutuse-fakt (õue suurus, vesi, elekter), "
                  "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): "
                  "kontrolli kommunikatsioonide olemasolu õuealal, ära feigi")


def dim_backup_heating(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p119: NULL — backup heating is a per-listing systems fact (do not fake)."""
    return None, ("Varukütte allikad (ahi, kamin, generaator) on kuulutuse-fakt, "
                  "millele snapshotis piirkonna-signaali pole (EI OLE hinnangut): "
                  "küsi küttesüsteemide nimekirja ja hoolduslugu, ära feigi")


GROUP01A_DIMS = (
    ("purchase_price", "p1", dim_purchase_price),
    ("utility_costs", "p5", dim_utility_costs),
    ("bedrooms", "p22", dim_bedrooms),
    ("bathrooms", "p23", dim_bathrooms),
    ("floor_plan_flow", "p24", dim_floor_plan_flow),
    ("kitchen", "p25", dim_kitchen),
    ("workspace", "p26", dim_workspace),
    ("storage", "p27", dim_storage),
    ("parking", "p28", dim_parking),
    ("move_in_readiness", "p32", dim_move_in_readiness),
    ("finishes", "p36", dim_finishes),
    ("outdoor_living", "p37", dim_outdoor_living),
    ("smart_home", "p39", dim_smart_home),
    ("primary_suite", "p92", dim_primary_suite),
    ("laundry", "p93", dim_laundry),
    ("mudroom", "p94", dim_mudroom),
    ("flex_space", "p99", dim_flex_space),
    ("gear_storage", "p109", dim_gear_storage),
    ("outdoor_kitchen", "p110", dim_outdoor_kitchen),
    ("backup_heating", "p119", dim_backup_heating),
)


def score_group01a(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All twenty Group 1 batch-A dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP01A_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP01A_DIMS}
