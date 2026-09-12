"""Group 10 utility-registry OSM proximity dimensions, batch C (issue #121).

Params (this agent only — sibling batches own disjoint sets):
* p51  high-speed internet availability (confirmed-telecom-mast proximity)
* p53  water source type (mapped public-water-point proximity)
* p54  waste management system (mapped waste-collection-point proximity)
* p262 ISP redundancy (confirmed-telecom-mast count, disjoint from p216)
* p265 over-the-air (OTA) reception (mapped broadcast-mast proximity)

HONESTY (AGENTS.md section 7.2): KKIS/TTJA registries and KOV ÜVK master
plans are NOT in the 2026-09-12 snapshot, so every scorer below is an
honestly-labeled OSM-derived PROXY. Titles, legends, and reasons must say
"kaardistatud" (mapped) and "hinnang" (estimate), never claim measured
broadband coverage, tap-water source, collection service, or signal field
strength. p51's registry type is BOOLEAN (connected/not); the registry is
absent, so the proxy is a 0-100 score, never a fake boolean.

Style mirrors services/scoring/livability.py and sibling batches
dims_group10.py (#105) / dims_group10b.py (#107): every scorer is pure
and offline-tested — (origin, pois) -> (Optional[int 0..100], Estonian
reason). Network lives only in livability.fetch_pois; this module adds
no network calls, only the query fragment + tag mapping the live path
needs.

Helpers are local copies (not imported from livability or the sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and siblings #105/#107).

Tag verification (2026-09-12, done once by the author with osmium
tags-count/tags-filter against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
extraction used nwr/ filters throughout — node-only would silently drop
way-mapped features, PR #118):
* man_made=mast: 219 uses, of which ~199 carry tower:type=communication
  (confirmed telecom use); man_made=communications_tower: 4;
  man_made=tower: 276 (mostly non-telecom: church/clock/observation).
* man_made=antenna: 44; communication:television=yes: 6;
  communication:radio=yes: 1 — sparse, so p265 absence is a soft floor.
* man_made=water_well: 29; natural=spring: 40;
  amenity=drinking_water: 88 (~157 mapped public water points).
* amenity=waste_disposal: 709; amenity=recycling: 1034 (dense);
  amenity=waste_basket: 6347 (street litter bins — deliberately
  excluded, furniture not collection service);
  man_made=wastewater_plant: 36 (disamenity, different param — excluded).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p51 uses the CONFIRMED-telecom subset only (tower:type=communication
  masts + communications_tower), not every man_made=mast — that keeps it
  disjoint from sibling p52 (nearest of ANY mapped mast) and avoids
  scoring church towers as broadband. Generic untyped masts are excluded
  here, not denied: the reason says "kinnitatud sidekasutusega".
* p262 counts confirmed-telecom masts within 3 km (redundancy depth),
  disjoint from sibling p216 (ALL masts within 5 km) by kind subset AND
  radius. Zero mapped feeds = 30, not 15: rural feeds are thinly mapped
  yet backhaul still reaches the house.
* p53 scores nearest mapped PUBLIC water point (drinking_water/well/
  spring). It does NOT know the house's tap source — Tallinn flats are
  centrally supplied regardless of distance — so bands are modest and
  the reason names the ÜVK gap explicitly.
* p54 scores nearest mapped collection point (waste_disposal/recycling).
  Waste baskets are excluded (litter furniture); wastewater plants are
  excluded (odour disamenity belongs to a different param).
* p265 scores nearest mapped broadcast radiator (antenna/radio/TV tags).
  Cellular masts are excluded even though many carry broadcast too —
  that keeps it disjoint from p51/p262; the reason says "ringhääling".
  Aviation nav aids (airmark=beacon, e.g. airport ILS localizers) are
  excluded: they are narrow-beam landing aids, not home broadcast
  (OTA-spread research 2026-09-12: ~40 of 51 exported
  antenna/radio/TV features are ILS beacons, collapsing to 6 of 17
  derived-ota.json points — scoring them painted the airport
  surroundings 100 for runway beams). Tallinna teletorn (the county's
  dominant high-power DVB-T/FM site) maps as man_made=
  communications_tower, so by the disjointness rule it scores as
  telecom, never broadcast — the source set is small masts only.
  Bands are therefore radio-horizon-order (10/20/30 km, soft 60
  floor), never a tight proximity gradient: VHF/UHF reception from
  30–100 m masts reaches tens of km, so any 1–5 km banding would be
  fake precision. A gradient OTA map cannot be honestly built from
  this source set (uniform real coverage → flat wash); p265 stays a
  coarse per-listing proxy only.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP10C_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP10C_POI_KIND (telecom/broadcast-aware
via kinds_from_tags — static mapping alone cannot split confirmed
telecom from generic masts, so the hook must route man_made/tower tags
through kinds_from_tags, threading tower:type through), centroiding way
geometries to points (ways are the rule for collection points; raw
way nodes would multi-count — residual twin risk per PR #118 must be
noted by the hook author), and rebalancing livability.WEIGHTS must be
one joint change across all parameter batches — existing tests pin
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


def _count_within_m(origin: Tuple[float, float], pois: List[dict],
                    kinds: set, radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radii are judgment calls: broadcast antennas are sparse (scorer
# OTA_RADIUS_M is 30 km radio-horizon-order, but the fragment lines
# below still query at 5 km — widening them belongs to the joint
# integration change, see the OTA_RADIUS_M note), telecom masts
# mid-sparse (5 km search, 3 km redundancy count), water points
# mid-density (3 km), collection points dense (2 km).
# Both node[...] and way[...] lines are required (nwr/ parity): collection
# points and antennas are frequently way-mapped; node-only drops them.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP10C_OVERPASS_FRAGMENT = """
  node["man_made"~"mast|tower|communications_tower|antenna"](around:5000,{lat},{lon});
  node["tower:type"="communication"](around:5000,{lat},{lon});
  node["communication:radio"="yes"](around:5000,{lat},{lon});
  node["communication:television"="yes"](around:5000,{lat},{lon});
  node["man_made"="water_well"](around:3000,{lat},{lon});
  node["natural"="spring"](around:3000,{lat},{lon});
  node["amenity"~"drinking_water|waste_disposal|recycling"](around:3000,{lat},{lon});
  way["man_made"~"mast|tower|communications_tower|antenna"](around:5000,{lat},{lon});
  way["man_made"="water_well"](around:3000,{lat},{lon});
  way["amenity"~"drinking_water|waste_disposal|recycling"](around:3000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND. man_made
#: needs the telecom/broadcast-aware kinds_from_tags below (static mapping
#: alone cannot split confirmed-telecom masts from church towers), so the
#: central hook must route man_made/tower tags through kinds_from_tags.
GROUP10C_POI_KIND = [
    ("man_made", {"mast": "telecom", "tower": "telecom",
                  "communications_tower": "telecom", "antenna": "broadcast",
                  "water_well": "waterpoint"}),
    ("natural", {"spring": "waterpoint"}),
    ("amenity", {"drinking_water": "waterpoint",
                 "waste_disposal": "wastepoint", "recycling": "wastepoint"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 10-batch-C kind matching the OSM tags, else None. Pure.

    Telecom-aware: man_made=mast/tower counts as "telecom" ONLY with
    tower:type=communication (confirmed telecom use — sibling p52's
    "mast" kind covers the generic remainder). communications_tower is
    telecom by definition. Broadcast-aware: man_made=antenna, or any
    feature tagged communication:radio/television=yes, maps to
    "broadcast" (checked before the mast rule so a TV-tagged mast
    scores as broadcast, not telecom). Aviation nav aids
    (airmark=beacon — airport ILS localizers etc.) map to None even
    when built as man_made=antenna: landing beams are not broadcast.
    """
    tags = tags or {}
    if str(tags.get("airmark", "")).split(";")[0] == "beacon":
        return None
    if (str(tags.get("communication:radio", "")).split(";")[0] == "yes"
            or str(tags.get("communication:television", "")).split(";")[0] == "yes"):
        return "broadcast"
    mm = str(tags.get("man_made", "")).split(";")[0]
    if mm == "antenna":
        return "broadcast"
    if mm == "communications_tower":
        return "telecom"
    if mm in ("mast", "tower"):
        if str(tags.get("tower:type", "")).split(";")[0] == "communication":
            return "telecom"
        return None
    if mm == "water_well":
        return "waterpoint"
    if str(tags.get("natural", "")).split(";")[0] == "spring":
        return "waterpoint"
    amenity = str(tags.get("amenity", "")).split(";")[0]
    if amenity == "drinking_water":
        return "waterpoint"
    if amenity in ("waste_disposal", "recycling"):
        return "wastepoint"
    return None


# ---------------------------------------------------------------------------
# p51: high-speed internet availability (confirmed-telecom-mast proxy).
# ---------------------------------------------------------------------------

#: Telecom-mast search radius in metres (mid-sparse tier).
INTERNET_RADIUS_M = 5000.0


def dim_internet(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p51: nearest confirmed-telecom mast (kinnitatud sidekasutus)."""
    if not origin or pois is None:
        return None, "Internetiinfo puudub"
    m = _nearest_m(origin, pois, {"telecom"})
    if m is None or m > INTERNET_RADIUS_M:
        return 35, ("Kinnitatud sidekasutusega masti 5 km raadiuses pole "
                    "kaardistatud (levihinnang, mitte mõõdetud katvus; "
                    "TTJA/KKIS registrit snapshots pole)")
    s = _band(m, [(500, 100), (1200, 85), (2500, 70)])
    return s, ("Lähim kinnitatud sidekasutusega mast %s "
               "(levihinnang, mitte mõõdetud katvus)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p53: water source type (mapped public-water-point proxy).
# ---------------------------------------------------------------------------

#: Public-water-point search radius in metres (mid-density tier).
WATER_RADIUS_M = 3000.0


def dim_water(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p53: nearest mapped public water point (joogivesi/kaev/allikas)."""
    if not origin or pois is None:
        return None, "Veevarustuse info puudub"
    m = _nearest_m(origin, pois, {"waterpoint"})
    if m is None or m > WATER_RADIUS_M:
        return 45, ("Kaardistatud avalikku veepunkti 3 km raadiuses pole "
                    "(ÜVK/tsentraalse veevarustuse registrit snapshots pole; "
                    "maja kraanivee allikat hinnang ei tea)")
    s = _band(m, [(400, 100), (800, 85), (1500, 70)])
    return s, ("Lähim kaardistatud avalik veepunkt %s "
               "(veevarustuse hinnang, mitte maja veeallika mõõtmine)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p54: waste management system (mapped collection-point proxy).
# ---------------------------------------------------------------------------

#: Collection-point search radius in metres (dense tier).
WASTE_RADIUS_M = 2000.0


def dim_waste(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p54: nearest mapped waste collection point (jäätmejaam/taara)."""
    if not origin or pois is None:
        return None, "Jäätmeinfo puudub"
    m = _nearest_m(origin, pois, {"wastepoint"})
    if m is None or m > WASTE_RADIUS_M:
        return 50, ("Kaardistatud jäätmekogumispunkti 2 km raadiuses pole "
                    "(korraldatud veo hinnang, mitte teenuse mõõtmine)")
    s = _band(m, [(300, 100), (600, 85), (1000, 70)])
    return s, ("Lähim kaardistatud jäätmekogumispunkt %s "
               "(korraldatud veo hinnang)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p262: ISP redundancy (confirmed-telecom-mast count proxy).
# ---------------------------------------------------------------------------

#: Telecom-redundancy count radius in metres (mid-sparse tier).
REDUNDANCY_RADIUS_M = 3000.0


def dim_redundancy(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p262: confirmed-telecom masts within 3 km (dubleerimise sügavus)."""
    if not origin or pois is None:
        return None, "Sideoperaatorite info puudub"
    n = _count_within_m(origin, pois, {"telecom"}, REDUNDANCY_RADIUS_M)
    if n == 0:
        return 30, ("Kinnitatud sidekasutusega maste 3 km raadiuses pole "
                    "kaardistatud (dubleerimise hinnang, mitte mõõdetud levi)")
    s = _band(n, [(1, 60), (3, 80), (float("inf"), 100)])
    return s, ("Kinnitatud sidekasutusega maste 3 km raadiuses: %d "
               "(dubleerimise hinnang, mitte mõõdetud levi)") % n


# ---------------------------------------------------------------------------
# p265: over-the-air reception (mapped broadcast-mast proxy).
# ---------------------------------------------------------------------------

#: Broadcast-mast search radius in metres (sparse tier, radio-horizon
#: order: VHF/UHF radio horizon d ≈ 4.12·(√h_tx + √h_rx) km gives
#: ~36 km for a 30 m mast / ~45–55 km for 60–100 m masts at 10 m
#: receive height — mapped heights where present are 30–100 m — so
#: county-scale tens-of-km bands are the honest order of magnitude.
#: NOTE for the integration follow-up: the live Overpass fragment above
#: still queries antenna/radio/TV tags at around:5000; widening those
#: lines toward ~30000 belongs to the joint hook change, otherwise the
#: scorer reads the soft floor wherever the query window clips.
#: A gradient OTA map layer is rejected (see module docstring): with an
#: honest calibration the county reads near-flat, so p265 stays a
#: coarse per-listing proxy only.
OTA_RADIUS_M = 30000.0


def dim_ota(origin: Optional[Tuple[float, float]],
            pois: Optional[List[dict]]) -> Score:
    """p265: nearest mapped broadcast radiator (antenn/ringhääling)."""
    if not origin or pois is None:
        return None, "Ringhäälinguinfo puudub"
    m = _nearest_m(origin, pois, {"broadcast"})
    if m is None or m > OTA_RADIUS_M:
        return 60, ("Kaardistatud ringhäälingumasti 30 km raadiuses pole "
                    "(OTA-hinnang, mitte mõõdetud väljatugevus)")
    s = _band(m, [(10000, 100), (20000, 85), (30000, 70)])
    return s, ("Lähim kaardistatud ringhäälingumast %s "
               "(OTA-hinnang, mitte mõõdetud väljatugevus)") % _fmt_m(m)


#: Registry for the central weight-rebalance follow-up: (dims key, param id, fn).
GROUP10C_DIMS = (
    ("internet", "p51", dim_internet),
    ("water", "p53", dim_water),
    ("waste", "p54", dim_waste),
    ("redundancy", "p262", dim_redundancy),
    ("ota", "p265", dim_ota),
)


def score_group10c(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 10 batch-C dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP10C_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP10C_DIMS}
