"""Batch 6 leftover scorer dimensions (issue #133): p17 + p386.

Two pure, offline-tested scorers in the `dim_*` style of livability.py:
each takes `(origin, pois)` and returns `(score|None, Estonian reason)`.
Scores are absolute 0..100; `None` is returned ONLY when the origin or
the POI list itself is missing (never as a guess).

Params (this agent only — sibling batches own disjoint sets):
* p17 proximity to family/friends -> buyer-supplied "family" POIs
  (nearest distance bands; no-map verdict, see BATCH6_NO_MAP in
  apps/web/lib/layers_batch6.ts — where YOUR family lives is not a
  place attribute, so no registry and no honest OSM proxy exists).
* p386 university-town rental bleed -> campus-proximity pressure proxy
  (INVERTED nearest university/college/dormitory; mirrors the rentbleed
  map layer half 800 m, never euros).

HONESTY (load-bearing, AGENTS.md section 7.2): the family coordinates
come from the BUYER at query time (never Overpass — no amenity tag
means "family"), and the rental registries are NOT in the 2026-09-12
snapshot, so every reason says "hinnang" (estimate) and the p386 reason
names the OSM tags measured. p386 is NEVER presented in EUR.

Tag verification (2026-09-12, local snapshot PBF — no network; same
counts as layers_batch6.ts, verified once by the author with osmium
against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf):
* amenity=university: 12, amenity=college: 12, building=dormitory: 16,
  amenity=dormitory: 2 (outlines collapse to reps extraction-side;
  scorers dedupe, documented below).

Calibration locked 2026-09-12 from snapshot probes
(Balti/Viru/TalTech/Viimsi/rural):
* p17 bands are a judgment call (visit-frequency framing): <=500 m: 100,
  <=1 km: 90, <=2 km: 75, <=5 km: 60, <=15 km: 40, else 25.
* p386 100*d/(d+800): TalTech doorstep ~10, Balti ~40, Viru ~55,
  Viimsi ~90, rural 100 (mirrors the map master exactly).

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUPB6_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUPB6_POI_KIND, and rebalancing
livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be one joint
change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
`university`/`college` kinds already flow through the live path via the
schools variety ladder; `dormitory` needs the mapping below and
`family` NEVER enters the fetch (buyer input only).
"""

import math
from typing import Callable, Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


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


def _deduped(pois: List[dict], kinds: set) -> List[dict]:
    """POIs of the given kinds with identical coords collapsed to one.

    The snapshot carries node+way-centre dupes; 1e-6 deg is ~10 cm, so
    no two real campus objects ever share a key.
    """
    seen: set = set()
    out: List[dict] = []
    for p in pois:
        if p.get("kind") not in kinds or p.get("lat") is None:
            continue
        key = (p["kind"], round(p["lat"], 6), round(p["lon"], 6))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


#: Campus kinds that proxy student-rental pressure (verified in snapshot).
CAMPUS_KINDS = {"university", "college", "dormitory"}

#: p17 bands: nearest buyer-supplied family point (closer reads higher).
FAMILY_BANDS = [(500, 100), (1000, 90), (2000, 75), (5000, 60),
                (15000, 40), (float("inf"), 25)]

#: p386 half-distance in metres (== the rentbleed map layer half).
RENT_HALF_M = 800.0


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping (campus only — family
# POIs are buyer input at query time and MUST NOT be Overpass-fetched).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUPB6_OVERPASS_FRAGMENT = """
  node["amenity"~"university|college|dormitory"](around:3000,{lat},{lon});
  node["building"="dormitory"](around:3000,{lat},{lon});
  way["amenity"~"university|college|dormitory"](around:3000,{lat},{lon});
  way["building"="dormitory"](around:3000,{lat},{lon});"""

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUPB6_POI_KIND = [
    ("amenity", {"university": "university", "college": "college",
                 "dormitory": "dormitory"}),
    ("building", {"dormitory": "dormitory"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """Batch 6 kind for OSM tags (campus only), else None. Pure."""
    if not isinstance(tags, dict):
        return None
    for tagkey, mapping in GROUPB6_POI_KIND:
        val = tags.get(tagkey, "")
        val = val.split(";")[0].strip() if isinstance(val, str) else ""
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p17: proximity to family/friends — buyer-supplied POIs (no-map scorer).
# ---------------------------------------------------------------------------

def dim_family_proximity(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p17: nearer family reads higher (visit-frequency framing).

    Family points arrive as kind="family" POIs supplied by the BUYER —
    never from Overpass (no amenity tag means "family"). No family POI
    -> None ("asukoht määramata"), never a faked distance.
    """
    if not origin or pois is None:
        return None, "Perekonna/sõprade info puudub"
    m = _nearest_m(origin, pois, {"family"})
    if m is None:
        return None, "Perekonna asukoht määramata (lisa aadress hinnangu jaoks)"
    s = _band(m, FAMILY_BANDS)
    assert s is not None
    return s, ("Lähedaste-proksi (ostja aadress, hinnang): lähim %s"
               % _fmt_m(m))


# ---------------------------------------------------------------------------
# p386: university-town rental bleed -> campus-proximity pressure proxy.
# ---------------------------------------------------------------------------

def _quiet(d_m: float, half_m: float) -> int:
    """Distance -> calmness 0..100: 0 on the source, 50 at half_m."""
    return int(round(100.0 * d_m / (d_m + half_m)))


def dim_rental_pressure(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p386: student-rental pressure proxy (near campus = low score, red).

    Owner-occupier framing (documented judgment call): high pressure
    near universities/dorms reads bad. Mirrors the rentbleed map master
    (same 800 m half). Never euros — the rental registries are not in
    the snapshot.
    """
    if not origin or pois is None:
        return None, "Ülikoolide info puudub"
    camp = _deduped(pois, CAMPUS_KINDS)
    best: Optional[float] = None
    for p in camp:
        d = _haversine_m(origin, p["lat"], p["lon"])
        if best is None or d < best:
            best = d
    if best is None:
        return 100, "Üürisurve-proksi: kaardistatud ülikool/ühiselamu 3 km+ kaugusel"
    return (_quiet(best, RENT_HALF_M),
            "Üürisurve-proksi (hinnang, mitte üüriregister): lähim ülikool/ühiselamu %s"
            % _fmt_m(best))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUPB6_DIMS: Tuple[Tuple[str, str, Callable], ...] = (
    ("family_proximity", "p17", dim_family_proximity),
    ("rental_pressure", "p386", dim_rental_pressure),
)


def score_batch6(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both batch 6 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUPB6_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUPB6_DIMS}
