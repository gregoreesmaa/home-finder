"""Group 18 leftover dimensions: batch GENV (issue #124).

Params (this agent only — sibling batches own disjoint sets):
* p63  light pollution (valgusreostuse proksi (hinnang): lit=yes +
  street_lamp density -> dark-sky score)
* p181 urban heat island effect (kuumasaare proksi (hinnang): building
  density + mapped-green cooling ramp -> cool-island score)

HONESTY (load-bearing, AGENTS.md §7.2): NOAA/NASA VIIRS nighttime-lights
radiance and Landsat thermal UHI mapping are NOT in the 2026-09-12
snapshot, so neither dim reports magnitudes, Bortle classes, or degrees.
Both scorers are OSM PROXIMITY/DENSITY proxies: high score = dark/cool
(green), low score = lit/sealed (red). Every non-None reason says
"proksi (hinnang)"; no reason mentions magnitudes or Celsius. Unknown
(origin or POI list missing) stays None — never a faked number.

Claim widths (deliberate): the live scorer sees only tagged POIs, so
* p63 counts mapped light sources (lit=yes tags + street lamps) — new
  lamps mapped tomorrow change the score, unmapped lamps are invisible;
  the reason says "kaardistatud valgusallikas".
* p181 counts mapped buildings (sealed-footprint proxy) plus the
  mapped-green cooling ramp; the raster refines this with the full
  road graph (car-graph vertices are not live POIs). The reason says
  "hoonestustiheduse proksi".
Unmapped darkness/greenery never punishes: absence in-window reads as
dark/cool evidence, capped conservatively below 100 (the county raster,
which sees the full snapshot, scores true absence up to 100).

Style mirrors services/scoring/livability.py: pure (origin, pois) ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. Network lives only in livability.fetch_pois; this module adds no
network calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12 snapshot, done once by the author, NOT at
runtime): lit=yes x119712 nodes + x25991 ways and highway=street_lamp
x29473 nodes in harjumaa-260911.osm.pbf (nwr/ filter — PR #118);
building=* x252589 ways (+236 relations; building-tagged NODES are
entrances/parts, excluded — see builder). Green kinds (park/forest)
come from the BASE query (no new fetch).

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP18B_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP18B_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _count_within_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# nwr/ filters (PR #118): lit features and buildings are usually mapped
# as ways/areas — node-only would silently drop them. "out center"
# already returns way centroids for the live path; the builder resolves
# centroids offline the same way.
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP18B_POI_KIND = [
    ("lit", {"yes": "lit_area"}),
    ("highway", {"street_lamp": "streetlamp"}),
    # building=* is open vocabulary (yes/house/apartments/...): any value
    # maps to "building" via kinds_from_tags below, not via this table.
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP18B_OVERPASS_FRAGMENT = """
  nwr["lit"="yes"](around:400,{lat},{lon});
  node["highway"="street_lamp"](around:400,{lat},{lon});
  nwr["building"](around:300,{lat},{lon});"""

#: Density halves: score = 100*H/(n+H), n = sources in window.
#: Locked 2026-09-12 from snapshot probes (buildings = area-assembly
#: centroids only, 252140 county-wide; lit = 20 m dedupe cells, 74798
#: county-wide; witness table in scripts/build/batch_genv_exposure.py).
DARK_HALF = 200.0   # lit 20 m cells / 400 m: Balti 570 -> 26, Nomme 114 -> 64
COOL_HALF = 50.0    # buildings / 250 m: Balti 60 -> 45, Nomme 187 -> 21
COOL_BONUS = 8.0    # mapped-green cooling ramp, mirrors raster builder
COOL_RANGE_M = 500.0


def _count_cells_within_m(origin: Tuple[float, float], pois: List[dict],
                           kinds: set, radius_m: float, cell_m: float = 20.0) -> int:
    """Distinct ~cell_m location cells within radius (node+area twin guard).

    Lit tags twin: a lit=yes node (stop, signal) sitting on a lit=yes way
    would otherwise count twice for one lamp row (PR #118 family). The
    raster builder dedupes the same way before stamping.
    """
    from livability import haversine_km
    seen = set()
    for p in pois or []:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if haversine_km(origin, (p["lat"], p["lon"])) * 1000.0 <= radius_m:
                seen.add((round(p["lon"] * 57.29 * 1000 / cell_m),
                          round(p["lat"] * 110.57 * 1000 / cell_m)))
    return len(seen)


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 18b kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP18B_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    # building=* is open vocabulary: any value (except explicit "no")
    # is a sealed footprint.
    b = (tags or {}).get("building", "").split(";")[0]
    if b and b != "no":
        return "building"
    return None


def _density(half: float, n: int) -> int:
    return max(0, min(100, int(round(100.0 * half / (n + half)))))


# ---------------------------------------------------------------------------
# p63: dark-sky proxy (mapped lit sources within 400 m).
# ---------------------------------------------------------------------------

def dim_darksky(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p63: darkness from the count of mapped light sources nearby."""
    if not origin or pois is None:
        return None, "Valgusreostuse info puudub (proksi)"
    # The 400 m window fully covers a lamp row's influence, so an empty
    # window IS dark evidence (unlike noise, which carries past its
    # window) — 100, honestly qualified as "kaardistatud".
    n = _count_cells_within_m(origin, pois, {"lit_area", "streetlamp"}, 400.0)
    if n == 0:
        return 100, "Kaardistatud valgusallikas puudub 400 m raadiuses (pimeduse proksi (hinnang): pime)"
    return (_density(DARK_HALF, n),
            "Valgusreostuse proksi (hinnang): kaardistatud valgusallikaid %d 400 m raadiuses" % n)


# ---------------------------------------------------------------------------
# p181: cool-island proxy (mapped buildings within 250 m + green ramp).
# ---------------------------------------------------------------------------

def dim_coolisland(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p181: coolness from mapped building density + nearby green."""
    if not origin or pois is None:
        return None, "Kuumasaare info puudub (proksi)"
    # Heat influence carries past the 250 m window, so absence caps at 90
    # (conservative); the formula caps there too, so one nearby shed (n=1
    # -> 98 raw) can never beat a genuinely open field.
    n = _count_within_m(origin, pois, {"building"}, 250.0)
    if n == 0:
        base = 90
        txt = "kaardistatud hooneid pole 250 m raadiuses"
    else:
        base = min(90, _density(COOL_HALF, n))
        txt = "kaardistatud hooneid %d 250 m raadiuses" % n
    m_nat = _nearest_m(origin, pois, {"park", "forest"})
    if m_nat is not None and m_nat <= COOL_RANGE_M:
        bonus = round(COOL_BONUS * (1.0 - m_nat / COOL_RANGE_M))
        score = min(100, base + bonus)
        return (score,
                "Kuumasaare proksi (hinnang): %s, haljasala %s" %
                (txt, "%d m" % int(round(m_nat)) if m_nat < 1000 else "~%.1f km" % (m_nat / 1000.0)))
    return base, "Kuumasaare proksi (hinnang): %s (kaardistatud haljasala kaugel)" % txt


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP18B_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "darksky": ("Valgusreostus / pime taevas (proksi, hinnang)", dim_darksky),
    "coolisland": ("Kuumasaar / jahedus (proksi, hinnang)", dim_coolisland),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP18B_PARAM_IDS = {
    "darksky": 63,
    "coolisland": 181,
}


def score_group18b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 18b dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP18B_DIMS.items():
        v, reason = fn(origin, pois)
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
