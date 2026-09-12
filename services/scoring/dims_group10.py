"""Group 10 utility-grid OSM proximity dimensions (issue #105).

Params (this agent only — sibling batches own disjoint sets):
* p52  cellular signal strength (telecom-mast proximity)
* p135 electromagnetic field (EMF) distance (power-infra distance)
* p211 substation proximity (power=substation)
* p214 overhead power line vulnerability (power=line/minor_line, inverted)
* p404 proximity to high-voltage lines (voltage>=110kV ways, inverted)

HONESTY (AGENTS.md section 7.2): these are OSM power/telecom PROXIMITY
layers, not measured volts, field strengths, or coverage maps. Titles,
legends, and reasons must say "kaardistatud" (mapped) proximity, never
claim measured EMF exposure or operator coverage.

Style mirrors services/scoring/livability.py: every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100], Estonian reason).
Network lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability): a future central
hook may import this module from livability.py, and importing livability
here would turn that into a cycle (same precedent as batch B3, PR #100).

Tag verification (2026-09-12, done once by the author with osmium against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime):
* power=tower: 3689 node features; power=substation: 1120 features;
  power=line: 539 ways, of which 517 carry a voltage tag
  (110000 V: 239, 10000 V: 146, 35000 V: 92, 330000 V: 24, rest mixed).
* man_made=mast: 219 points; man_made=tower: ~300 points;
  man_made=communications_tower: 5 points.
* power=tower/pole nodes double as overhead-line proxies: a distribution
  line whose way is unmapped still shows its poles.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p52 scores mast proximity as a signal-availability proxy. Closer is
  better; the floor is 30 (not 15) because rural Estonia often has usable
  signal kilometres from the nearest mapped mast, and absence mostly
  reflects thin tower mapping, not a measured dead zone.
* p135 vs p404 overlap deliberately: p135 is everyday-EMF distance to ANY
  grid infra (distribution lines, poles, substations); p404 is the
  transmission-corridor disamenity (110/330 kV ways only, stricter bands).
* p211 follows the repo proximity-is-good convention (reliable local grid)
  like p169/worship in batch B3; the reason names the distance so buyers
  who dislike substation neighbours can judge for themselves.
* p214/p404 are inverted (closer = lower score) with soft floors: a mapped
  line nearby is a probabilistic storm/outage and resale factor, not a
  certain outage; unmapped buried cables may exist anywhere.
* High-voltage means parsed max voltage >= 110000 V (Elering transmission
  tier: 110/330 kV). 35 kV and below is distribution, not transmission.
  Untagged power=line ways count as generic overhead (p214/p135) but never
  as high-voltage (p404) — guessing voltage would fake precision.

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP10_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP10_POI_KIND
(voltage-aware via kinds_from_tags for power=line, so the hook must thread
a voltage field through), and rebalancing livability.WEIGHTS must be one
joint change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Transmission tier: parsed max voltage at or above this is high-voltage.
HV_VOLTS = 110000

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
# Radii are judgment calls: masts and HV ways are sparse (5 km), substations
# mid-density (3 km), distribution poles/lines dense (1.5 km).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP10_OVERPASS_FRAGMENT = """
  node["man_made"~"mast|tower|communications_tower"](around:5000,{lat},{lon});
  node["power"~"substation|tower|pole"](around:3000,{lat},{lon});
  node["power"~"line|minor_line"](around:1500,{lat},{lon});
  way["power"="substation"](around:3000,{lat},{lon});
  way["power"~"line|minor_line"](around:5000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND. power=line
#: needs the voltage-aware kinds_from_tags below (static mapping alone
#: cannot split HV transmission from distribution), so the central hook
#: must route power tags through kinds_from_tags, not this table alone.
GROUP10_POI_KIND = [
    ("man_made", {"mast": "mast", "tower": "mast",
                  "communications_tower": "mast"}),
    ("power", {"substation": "substation", "tower": "powerline",
               "pole": "powerline", "minor_line": "powerline",
               "line": "powerline"}),
]


def _max_volts(voltage: object) -> Optional[int]:
    """Parse an OSM voltage tag ('110000', '330000;110000') to max volts."""
    if not isinstance(voltage, str):
        return None
    best: Optional[int] = None
    for part in voltage.replace("kV", "000").replace(" ", "").split(";"):
        try:
            v = int(float(part))
        except ValueError:  # unparseable segment, try the next
            continue
        if v <= 0:
            continue
        # Bare "110"/"330" style values are kV, not volts.
        if v < 1000:
            v *= 1000
        if best is None or v > best:
            best = v
    return best


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 10 kind matching the OSM tags, else None. Pure.

    Voltage-aware: power=line with max parsed voltage >= HV_VOLTS maps to
    "hvline" (p404); any other power=line stays "powerline" (p214/p135).
    """
    tags = tags or {}
    for tagkey, mapping in GROUP10_POI_KIND:
        val = str(tags.get(tagkey, "")).split(";")[0]
        if val in mapping:
            kind = mapping[val]
            if tagkey == "power" and val == "line":
                v = _max_volts(tags.get("voltage"))
                if v is not None and v >= HV_VOLTS:
                    return "hvline"
            return kind
    return None


# ---------------------------------------------------------------------------
# p52: cellular signal strength (telecom-mast proximity proxy).
# ---------------------------------------------------------------------------

def dim_signal(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p52: nearest mapped telecom mast (man_made=mast/tower)."""
    if not origin or pois is None:
        return None, "Mobiililevi info puudub"
    m = _nearest_m(origin, pois, {"mast"})
    if m is None:
        return 30, "Kaardistatud mobiilimast üle 5 km (levis võib olla nõrk)"
    s = _band(m, [(500, 100), (1200, 85), (2500, 70), (5000, 50)])
    return s, "Lähim kaardistatud mobiilimast %s (lekihinnang, mitte mõõdetud levi)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p135: EMF distance (any grid infra: lines, poles, towers, substations).
# ---------------------------------------------------------------------------

def dim_emf(origin: Optional[Tuple[float, float]],
            pois: Optional[List[dict]]) -> Score:
    """p135: distance to nearest mapped grid infra (kaugem = parem)."""
    if not origin or pois is None:
        return None, "EMF-kauguse info puudub"
    m = _nearest_m(origin, pois, {"powerline", "hvline", "substation"})
    if m is None:
        return 100, "Läheduses kaardistatud elektriliini/alajaama pole"
    s = _band(m, [(100, 25), (200, 45), (400, 65), (800, 85)])
    return s, "Lähim kaardistatud elektritaristu %s (kaugushinnang, mitte mõõdetud väli)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p211: substation proximity (repo convention: proximity is good).
# ---------------------------------------------------------------------------

def dim_substation(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p211: nearest mapped substation (power=substation)."""
    if not origin or pois is None:
        return None, "Alajaamade info puudub"
    m = _nearest_m(origin, pois, {"substation"})
    if m is None:
        return 30, "Kaardistatud alajaam üle 3 km"
    s = _band(m, [(400, 100), (800, 85), (1500, 70), (3000, 50)])
    return s, "Lähim kaardistatud alajaam %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p214: overhead power line vulnerability, INVERTED (closer = lower).
# ---------------------------------------------------------------------------

def dim_overhead(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p214: nearest mapped overhead line/pole (lähem = tormihaavatavam)."""
    if not origin or pois is None:
        return None, "Õhuliinide info puudub"
    m = _nearest_m(origin, pois, {"powerline", "hvline"})
    if m is None:
        return 90, "Kaardistatud õhuliini läheduses pole"
    s = _band(m, [(200, 45), (500, 65), (1000, 80)])
    return s, "Lähim kaardistatud õhuliin %s (tormihaavatavuse hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p404: high-voltage line proximity, INVERTED (closer = lower).
# ---------------------------------------------------------------------------

def dim_hvline(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p404: nearest mapped >=110 kV line (lähem = halvem)."""
    if not origin or pois is None:
        return None, "Kõrgepingeliinide info puudub"
    m = _nearest_m(origin, pois, {"hvline"})
    if m is None:
        return 100, "Kõrgepingeliini (≥110 kV) kaardistamata läheduses"
    s = _band(m, [(100, 25), (200, 45), (400, 65), (800, 85)])
    return s, "Lähim kaardistatud kõrgepingeliin %s (koridorihinnang)" % _fmt_m(m)


#: Registry for the central weight-rebalance follow-up: (dims key, param id, fn).
GROUP10_DIMS = (
    ("signal", "p52", dim_signal),
    ("emf", "p135", dim_emf),
    ("substation", "p211", dim_substation),
    ("overhead", "p214", dim_overhead),
    ("hvline", "p404", dim_hvline),
)


def score_group10(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 10 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP10_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP10_DIMS}
