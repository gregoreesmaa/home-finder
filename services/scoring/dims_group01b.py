"""Group 1 listing-portal per-listing dimensions, batch B (issue #203).

Params (this agent only — sibling batches own disjoint sets):
* p121 multi-generational living (ALWAYS None — floorplan fact)
* p129 nanny/au pair quarters (ALWAYS None — interior fact)
* p140 cosmetic palette (ALWAYS None — photo/NLP fact)
* p180 hidden structural space (ALWAYS None — plan/EHR fact)
* p191 radiant heated flooring (ALWAYS None — listing heating fact)
* p192 spa and recovery amenities (ALWAYS None — equipment fact)
* p193 acoustically treated home theater (ALWAYS None — room-build fact)
* p194 climate-controlled storage (ALWAYS None — interior fact)
* p195 sculleries/butler's pantry (ALWAYS None — floorplan fact)
* p198 motor courts (ALWAYS None — parcel driveway design, NOT area parking)
* p200 specialty culinary integration (ALWAYS None — equipment fact)
* p268 server/network closet space (ALWAYS None — interior tech fact)
* p285 indoor/outdoor blurring (ALWAYS None — photo architecture fact)
* p286 bulk pantry volume (ALWAYS None — floorplan fact)
* p288 pet quarantine zones (ALWAYS None — interior fact)
* p289 hobby mess containment (ALWAYS None — side-room fact)
* p290 multi-use micro spaces (ALWAYS None — floorplan fact)
* p300 superficial flip indicators (ALWAYS None — transaction-history fact)
* p412 package theft vulnerability (ALWAYS None — entry-regime fact,
  NOT parcel-locker distance)
* p489 staging illusions (ALWAYS None — listing photo fact)

HONESTY (AGENTS.md section 7.2): all twenty are Tier 1 scraped-syndication
facts (parameters3.md section 5.1: KV.ee, City24, Kinnisvara24, Osta,
Okidoki + brokerage KVXML feeds, NLP/vision extraction). Interior
finishes, room-level equipment and photo staging leave no honest area
signal in the OSM snapshot, so every dim stays NULL with a buyer-check
reason. Reasons say "hinnang" (estimate) and "EI OLE" (no estimate
exists) — never measured palettes, verified wiring closets, or resolved
theft risk.

Style mirrors services/scoring/livability.py and sibling batch
dims_group03b.py (#152): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls. There is deliberately NO Overpass fragment, NO POI-kind mapping
and NO kinds_from_tags here: with zero proxy dims there is no live-path
wiring to document (unlike batch G03B, which ships three proxies).

Helpers are absent on purpose (not even a local haversine copy): NULL
dims measure no distance, and copying dead helpers would suggest a
proxy exists. A future central hook only needs GROUP01B_DIMS.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p198 from amenity=parking/highway=service density was considered and
  REJECTED: a circular maneuvering court is a parcel-level driveway
  design, not area parking supply. The reason names the aerial-photo +
  site-visit check instead.
* p412 from amenity=parcel_locker proximity was considered and
  REJECTED: theft risk depends on stairwell regime + street exposure,
  not locker distance — a locker gradient would be fake precision
  (OTA PR #131 precedent).
* p300 from transaction recency alone was considered and REJECTED:
  recency does not measure cheap renovation; the reason points at
  Maa-amet transaction history + build quality per listing.
* All twenty return None for EVERY input including missing origin:
  inventing a gradient from zero signal would be fake precision. The
  reasons point at the listing/plan/registry check the buyer must do.

Integration (deliberately NOT done here): NULL dims need no
livability.OVERPASS_QUERY fragment, no _POI_KIND rows, no centroiding
and no WEIGHTS change — rebalancing livability.WEIGHTS must be one
joint change across all parameter batches (existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling).
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_multigen(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p121: NULL — dual-living suitability is a floorplan fact (do not fake)."""
    return None, ("Mitme põlvkonna sobivus on kuulutuse põhiplaanifakt "
                  "(eraldi sissepääs/teine köök): piirkonna kaardil puudub "
                  "aus pindmine signaal (EI OLE hinnangut) — vajab kuulutuse "
                  "plaani ja kohapealset kontrolli, ära feigi")


def dim_nanny_quarters(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p129: NULL — a keeper's room is an interior fact (do not fake)."""
    return None, ("Hoidjapinna olemasolu on kuulutuse sisefakt (eraldi tuba/ "
                  "vannituba): OSM-i pind seda ei näita (EI OLE hinnangut) — "
                  "kontrolli kuulutuse plaani ja pindala, ära feigi")


def dim_cosmetic_palette(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p140: NULL — palette is a photo/NLP judgment (do not fake)."""
    return None, ("Kosmeetiline palett on fotode ja NLP hinnang (värvid, "
                  "materjalid): kaardikihil puudub aus mõõdetav signaal "
                  "(EI OLE hinnangut) — otsusta fotode ja külastuse põhjal, "
                  "ära feigi")


def dim_hidden_space(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p180: NULL — hidden structural space needs plan/EHR (do not fake)."""
    return None, ("Peidetud konstruktsiooniruum (nišid, pööninguvaru) selgub "
                  "plaanilt ja ehitisregistrist: kaardil ausat signaali pole "
                  "(EI OLE hinnangut) — küsi plaan ja EHR-i andmed, ära feigi")


def dim_radiant_floor(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p191: NULL — underfloor heating is a listing fact (do not fake)."""
    return None, ("Põrandaküte on kuulutuse küttefakt: piirkonna soojuskaardil "
                  "puudub korteripõhine signaal (EI OLE hinnangut) — "
                  "kontrolli kuulutuse kütte kirjeldust, ära feigi")


def dim_spa_recovery(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p192: NULL — spa equipment is a listing fact (do not fake)."""
    return None, ("Spaa- ja taastumisalad (saun, bassein, külmavann) on "
                  "kuulutuse varustusfakt: kaardikiht seda ei mõõda "
                  "(EI OLE hinnangut) — loe kuulutuse mugavuste loetelu, "
                  "ära feigi")


def dim_acoustic_theater(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p193: NULL — room acoustic treatment is a build fact (do not fake)."""
    return None, ("Helitöödeldud kodukino on siseruumi ehitusfakt: välismüra "
                  "kaart ei hinda tuba (EI OLE hinnangut) — küsi "
                  "ehitusdokumentatsiooni, ära feigi")


def dim_climate_storage(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p194: NULL — climate-controlled storage is interior (do not fake)."""
    return None, ("Kliimakontrolliga hoiuruum on kuulutuse sisefakt: kaardil "
                  "signaali pole (EI OLE hinnangut) — kontrolli kuulutuse "
                  "hoiuruumide kirjeldust, ära feigi")


def dim_scullery(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p195: NULL — a scullery is a floorplan fact (do not fake)."""
    return None, ("Abiköök/butleri sahver on põhiplaani fakt: kaardikiht seda "
                  "ei näita (EI OLE hinnangut) — vaata kuulutuse plaani, "
                  "ära feigi")


def dim_motor_court(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p198: NULL — a motor court is parcel driveway design (do not fake).

    Area parking density (amenity=parking/highway=service) was rejected
    as a proxy: it measures supply around the listing, not the
    maneuvering court on the plot.
    """
    return None, ("Manööverväljak (motor court) on krundi-põhine sissesõidu "
                  "lahendus, mitte piirkonna parkimistihedus: parkla/proksi "
                  "gradient valetaks (EI OLE ausat hinnangut) — hinda "
                  "aerofotolt ja kohapeal, ära feigi")


def dim_culinary_suite(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p200: NULL — specialty culinary gear is a listing fact (do not fake)."""
    return None, ("Erikulinaarne sisustus (pitsaahi, teppanyaki, veinikülmik) "
                  "on kuulutuse varustusfakt: kaardil signaali pole (EI OLE "
                  "hinnangut) — loe kuulutuse köögi loetelu, ära feigi")


def dim_server_closet(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p268: NULL — a network closet is an interior fact (do not fake)."""
    return None, ("Serveri-/võrgukapp on siseruumi fakt (ventilatsioon, "
                  "elekter): kaardikiht seda ei mõõda (EI OLE hinnangut) — "
                  "kontrolli kuulutuse tehnoruumi kirjeldust, ära feigi")


def dim_indoor_outdoor(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p285: NULL — indoor/outdoor blur is a photo fact (do not fake)."""
    return None, ("Sise- ja välisruumi sulandumine (lükandseinad, "
                  "terrassiavad) on arhitektuuri-fakt fotodelt: kaardil "
                  "signaali pole (EI OLE hinnangut) — otsusta fotode ja "
                  "külastuse põhjal, ära feigi")


def dim_bulk_pantry(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p286: NULL — pantry volume is a floorplan fact (do not fake)."""
    return None, ("Hulgisahvri maht on põhiplaani ja sisefakt: kaardikiht "
                  "seda ei näita (EI OLE hinnangut) — vaata kuulutuse "
                  "plaani ja sahvri kirjeldust, ära feigi")


def dim_pet_quarantine(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p288: NULL — a pet separation room is interior (do not fake)."""
    return None, ("Lemmikloomade eraldusala on kuulutuse sisefakt: kaardil "
                  "signaali pole (EI OLE hinnangut) — küsi müüjalt eraldi "
                  "ruumi olemasolu, ära feigi")


def dim_hobby_mess(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p289: NULL — mess containment is a side-room fact (do not fake)."""
    return None, ("Hobiräbu eraldusvõime (töötuba, helikindel nurk) on "
                  "sisefakt: kaardikiht seda ei mõõda (EI OLE hinnangut) — "
                  "kontrolli kuulutuse kõrvalruume, ära feigi")


def dim_micro_spaces(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p290: NULL — micro spaces are a floorplan fact (do not fake)."""
    return None, ("Mitmeotstarbelised mikroruumid on põhiplaani fakt: kaardil "
                  "signaali pole (EI OLE hinnangut) — loe kuulutuse plaani, "
                  "ära feigi")


def dim_flip_indicators(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p300: NULL — flip signs need history + photos (do not fake).

    Transaction recency alone was rejected as a proxy: a quick resale
    does not measure cheap renovation.
    """
    return None, ("Pinnapealse flipi tunnused (odav renoveerimine, kiire "
                  "edasimüük) selguvad tehinguajaloost ja fotodest: "
                  "kaardigradient valetaks (EI OLE hinnangut) — kontrolli "
                  "Maa-ameti tehinguajalugu ja ehituskvaliteeti, ära feigi")


def dim_package_theft(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p412: NULL — theft risk is an entry-regime fact (do not fake).

    amenity=parcel_locker proximity was rejected as a proxy: locker
    distance does not measure stairwell-regime + street-exposure risk.
    """
    return None, ("Pakivarguse risk sõltub trepikoja režiimist ja tänava "
                  "asendist, mitte pakiautomaadi kaugusest: lockeri-proksi "
                  "gradient valetaks (EI OLE ausat hinnangut) — hinda "
                  "sissepääsu ja hoiu lahendust kohapeal, ära feigi")


def dim_staging_illusions(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """p489: NULL — staging tricks are a photo fact (do not fake)."""
    return None, ("Lavastusillusioonid (lainurkfotod, virtuaalne mööbel) on "
                  "kuulutuse fotofakt: kaardil signaali pole (EI OLE "
                  "hinnangut) — võrdle fotosid plaani ja külastusega, "
                  "ära feigi")


GROUP01B_DIMS = (
    ("multigen", "p121", dim_multigen),
    ("nanny_quarters", "p129", dim_nanny_quarters),
    ("cosmetic_palette", "p140", dim_cosmetic_palette),
    ("hidden_space", "p180", dim_hidden_space),
    ("radiant_floor", "p191", dim_radiant_floor),
    ("spa_recovery", "p192", dim_spa_recovery),
    ("acoustic_theater", "p193", dim_acoustic_theater),
    ("climate_storage", "p194", dim_climate_storage),
    ("scullery", "p195", dim_scullery),
    ("motor_court", "p198", dim_motor_court),
    ("culinary_suite", "p200", dim_culinary_suite),
    ("server_closet", "p268", dim_server_closet),
    ("indoor_outdoor", "p285", dim_indoor_outdoor),
    ("bulk_pantry", "p286", dim_bulk_pantry),
    ("pet_quarantine", "p288", dim_pet_quarantine),
    ("hobby_mess", "p289", dim_hobby_mess),
    ("micro_spaces", "p290", dim_micro_spaces),
    ("flip_indicators", "p300", dim_flip_indicators),
    ("package_theft", "p412", dim_package_theft),
    ("staging_illusions", "p489", dim_staging_illusions),
)


def score_group01b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All twenty Group 1 batch-B dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP01B_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP01B_DIMS}
