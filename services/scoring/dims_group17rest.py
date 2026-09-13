"""Group 17 HOA-rest per-listing dimensions (issue #196).

Params (this agent only — sibling batches own disjoint sets):
* p4 maintenance costs (ALWAYS None — per-KÜ EUR fact, do not fake)
* p49 HOA restrictions (ALWAYS None — per-KÜ rulebook fact, do not fake)
* p142 HOA financial reserves (ALWAYS None — per-KÜ EUR fact, do not fake)
* p145 vehicle restrictions (ALWAYS None — KÜ rules, not KOV orders)
* p152 condo owner-occupancy ratio (ALWAYS None — per-building fact)
* p167 trash/recycling etiquette (ALWAYS None — behaviour + scored twice)
* p245 private road maintenance (mapped private-road proximity hinnang)
* p246 HOA special assessment history (ALWAYS None — per-KÜ EUR fact)
* p247 utility sub-metering (ALWAYS None — per-building metering fact)
* p278 shared maintenance phrasing (ALWAYS None — listing text, not place)
* p368 HOA rental caps (ALWAYS None — per-KÜ rulebook fact, do not fake)
* p427 HOA initiation fees (ALWAYS None — per-KÜ EUR fact, do not fake)

HONESTY (AGENTS.md section 7.2): the e-Äriregister KÜ annual
reports, board cards, Creditinfo/MTA arrears and EKÜL baselines are
NOT in the 2026-09-12 snapshot, so the eleven document facts stay
NULL with a KÜ-document reason, and p245 is a coarse OSM-derived
PROXY. Reasons say "hinnang" (estimate) and name what is missing —
never a KÜ teehooldus agreement, an Äriregister entry, or a
põhikiri ruling.

Style mirrors services/scoring/livability.py and sibling batch
dims_group05c.py (#163): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #163).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
service roads, PR #118):
* privroad predicate (access=private AND highway in
  service/track/unclassified/residential/living_street AND service
  not driveway/parking_aisle): 1086 objects county-wide (541 in the
  Tallinn window lon 24.55-24.90 lat 59.36-59.50: Tiskrevälja,
  Kakumäe/Merirahu private streets, Viimsi erateed). 20351
  access=private objects drop out BY DESIGN: 18290 non-road objects
  (parking lots, pitches, pools — a car park is not a road), 874
  private driveways/parking aisles (single-parcel, never an
  agreement road), the rest footway/path/cycleway fragments.
* gates (barrier=gate): 6547 features county-wide — DOCUMENTED but
  not consumed (a gate marks a compound entrance, not a maintenance
  agreement; compounds would double-count where their private roads
  already stamp).
* vehicle restrictions: motor_vehicle=no/private + access=no are KOV
  traffic orders (Old Town pedestrian zone, park paths), not KÜ
  house rules — consuming them would relabel city orders as HOA
  policy. p145 stays NULL.
* waste etiquette: bin proximity is already scored twice
  (compost p187 + leafdrop p312, dims_group17a) plus general
  drop-offs (p54 taara) — a third waste gradient duplicates them
  while saying nothing about etiquette. p167 stays NULL.
* costs/reserves/levies/fees/caps/rules/tenure/metering/phrasing:
  zero matching keys anywhere in the PBF — per-document facts with
  no area signal to calibrate.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p245 bands track the raster formula loosely (100*d/(d+200): 100 m
  ~= 33, 200 m = 50, 400 m ~= 67): <=100 m scores 35, <=200 m 50,
  beyond-200 m 70 (calm: public-street area, reason says so), and
  no mapped road within 800 m scores 85. Under 100 m the reason
  flags the KÜ teehooldus check.
* p4/p49/p142/p145/p152/p167/p246/p247/p278/p368/p427 return None
  for EVERY input including missing origin: inventing a gradient
  from zero signal (duplicating compost/leafdrop/p54, or relabeling
  KOV traffic orders) would be fake precision (OTA PR #131
  precedent). The reasons point at the KÜ-document/Äriregister
  check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP17REST_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP17REST_POI_KIND, centroiding way
geometries to points (private roads are ways; raw way nodes would
multi-count — residual twin risk per PR #118 must be noted by the
hook author), and rebalancing livability.WEIGHTS must be one joint
change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _nearest_m(origin: Tuple[float, float], pois: List[dict], kinds: set) -> Optional[float]:
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            d = _haversine_m(origin, p["lat"], p["lon"])
            if best is None or d < best:
                best = d
    return best


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radius is a judgment call: private roads are dense enough in town
# for an 800 m search. Both node[...] and way[...] lines are required
# (nwr/ parity): shared private roads are ways; node-only drops them
# (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP17REST_OVERPASS_FRAGMENT = """
  node["highway"~"service|track|unclassified|residential|living_street"]["access"="private"](around:800,{lat},{lon});
  way["highway"~"service|track|unclassified|residential|living_street"]["access"="private"](around:800,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "privroad" = mapped shared private road for the upkeep-burden dim
#: (parking lots, pitches, pools, driveways and footways map to None:
#: a car park is not a road, a driveway is not an agreement road).
GROUP17REST_POI_KIND = [
    ("highway", {"service": "privroad", "track": "privroad",
                 "unclassified": "privroad", "residential": "privroad",
                 "living_street": "privroad"}),
]

#: service values that are single-parcel, never agreement roads.
DROP_SERVICE = ("driveway", "parking_aisle")


def _first_value(value) -> str:
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 17-rest kind matching the OSM tags, else None. Pure.

    Shared private roads (access=private on a road-class highway,
    excluding driveways/parking aisles) map to "privroad". Plain
    public streets map to None (not a burden); parking, pitches,
    pools, driveways, aisles and footways map to None (not roads).
    """
    tags = tags or {}
    if _first_value(tags.get("access")) != "private":
        return None
    if _first_value(tags.get("highway")) not in (
            "service", "track", "unclassified", "residential", "living_street"):
        return None
    if _first_value(tags.get("service")) in DROP_SERVICE:
        return None
    return "privroad"


# ---------------------------------------------------------------------------
# p245: private road maintenance (mapped-road proximity hinnang).
# ---------------------------------------------------------------------------

#: Raster half in metres (mirrors G17R_CAL.privroad in the TS + builder).
PRIVROAD_HALF_M = 200.0


def dim_privroad(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p245: upkeep-burden calmness from nearest mapped shared private road."""
    if not origin or pois is None:
        return None, "Erateede info puudub (erateede hetktõmmis)"
    m = _nearest_m(origin, pois, {"privroad"})
    if m is None:
        return 85, "Erateed 800 m raadiuses kaardistamata (hinnang: avalike tänavate piirkond)"
    s = _band(m, [(100, 35), (200, 50), (400, 70)])
    assert s is not None
    if s <= 50:
        return s, "Eratee koormus (hinnang): lähim jagatud eratee %s — küsi KÜ-lt teehoolduslepingut" % _fmt_m(m)
    return s, "Eratee koormus (hinnang): lähim jagatud eratee %s (avalik tänav lähedal)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p4/p49/p142/p145/p152/p167/p246/p247/p278/p368/p427: documented
# no-map KÜ-document NULLs (OTA PR #131 precedent). Each is a
# per-document/per-building fact with no honest area signal; the
# scorer reports the gap with a concrete buyer check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_maintcost(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p4: NULL — maintenance costs are a per-KÜ EUR fact (no map)."""
    return None, "Hoolduskulud teadmata (KÜ majandusaasta aruanne; hetktõmmises pole kuluridu — kontrolli Äriregistrist)"


def dim_hoarestrict(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p49: NULL — HOA restrictions are a per-KÜ rulebook fact (no map)."""
    return None, "KÜ piirangud teadmata (KÜ põhikiri/kodukord; hetktõmmises pole reeglistikku — küsi KÜ-lt)"


def dim_reserves(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p142: NULL — financial reserves are a per-KÜ EUR fact (no map)."""
    return None, "Remondifond teadmata (KÜ bilanss; hetktõmmises pole reserviandmeid — kontrolli Äriregistrist)"


def dim_vehiclerestrict(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p145: NULL — vehicle rules are KÜ policy, not KOV orders (no map)."""
    return None, "Sõidukipiirangud teadmata (KÜ parkimiskord; kaardistatud sõidukeelud on KOV liikluskorraldus — küsi KÜ-lt)"


def dim_occupancy(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p152: NULL — owner-occupancy is a per-building fact (no map)."""
    return None, "Omanike osakaal teadmata (hoone elanike koosseis; hetktõmmises pole omandiandmeid — küsi KÜ-lt)"


def dim_trashetiquette(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p167: NULL — etiquette is behaviour, already scored twice (no map)."""
    return None, "Prügikäitlus teadmata (KÜ jäätmekord; jäätmepunktide lähedus on juba compost/leafdrop — hinda kohapeal)"


def dim_assessment(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p246: NULL — special assessments are a per-KÜ EUR fact (no map)."""
    return None, "Eriarved (lisamaksed) teadmata (KÜ otsused; hetktõmmises pole maksustamisandmeid — kontrolli Äriregistrist)"


def dim_submeter(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p247: NULL — sub-metering is a per-building metering fact (no map)."""
    return None, "Alammõõturid teadmata (hoone mõõtesüsteem; hetktõmmises pole mõõturite andmeid — küsi KÜ-lt)"


def dim_sharedphrase(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p278: NULL — phrasing is listing text, not a place field (no map)."""
    return None, "Hooldussõnastus pole kaardikiht (kuulutuse tekst, mitte koht — loe kuulutusest)"


def dim_rentalcap(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p368: NULL — rental caps are a per-KÜ rulebook fact (no map)."""
    return None, "Üüripiirang teadmata (KÜ põhikiri; hetktõmmises pole reeglistikku — küsi KÜ-lt enne üüriplaani)"


def dim_initfee(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p427: NULL — initiation fees are a per-KÜ EUR fact (no map)."""
    return None, "Sisseastumismaks teadmata (KÜ tasumäär; hetktõmmises pole tasuandmeid — küsi KÜ-lt)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP17REST_DIMS: Dict[str, Tuple[str, object]] = {
    "maintcost": ("Hoolduskulud (kontroll)", dim_maintcost),
    "hoarestrict": ("KÜ piirangud (kontroll)", dim_hoarestrict),
    "reserves": ("Remondifond (kontroll)", dim_reserves),
    "vehiclerestrict": ("Sõidukipiirang (kontroll)", dim_vehiclerestrict),
    "occupancy": ("Omanike osakaal (kontroll)", dim_occupancy),
    "trashetiquette": ("Prügikäitlus (kontroll)", dim_trashetiquette),
    "privroad": ("Eratee koormus (proksi)", dim_privroad),
    "assessment": ("Eriarved (kontroll)", dim_assessment),
    "submeter": ("Alammõõturid (kontroll)", dim_submeter),
    "sharedphrase": ("Hooldussõnastus (kontroll)", dim_sharedphrase),
    "rentalcap": ("Üüripiirang (kontroll)", dim_rentalcap),
    "initfee": ("Sisseastumismaks (kontroll)", dim_initfee),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP17REST_PARAM_IDS = {
    "maintcost": 4,
    "hoarestrict": 49,
    "reserves": 142,
    "vehiclerestrict": 145,
    "occupancy": 152,
    "trashetiquette": 167,
    "privroad": 245,
    "assessment": 246,
    "submeter": 247,
    "sharedphrase": 278,
    "rentalcap": 368,
    "initfee": 427,
}


def score_group17rest(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 17-rest dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP17REST_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
