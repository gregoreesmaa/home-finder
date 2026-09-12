"""Group 18 street-traffic OSM dimensions (issue #113).

Params (this agent only — sibling batches own disjoint sets; Group 18 is
parameters3.md section 5.18, re-derived here from street/OSM tags because
the Group 18 primaries — Maa-amet 3D meshes, PVLib ray-tracing, VIIRS —
carry no traffic, parking, calming, or lighting signal):
* p82  street traffic volume and speed (road-class/speed-limit PROXY)
* p83  on-street parking density (amenity=parking + parking=street_side)
* p166 traffic calming measures (traffic_calming=*)
* p350 seasonal street lighting (lit=yes way proximity, winter proxy)
* p441 school traffic gridlock (school + arterial co-proximity PROXY)

HONESTY (AGENTS.md section 7.2): live traffic volumes are NOT in the
snapshot, so p82/p441 MUST be honestly-labeled road-class/speed-limit
proxies — green = calm local streets, red = arterials — never presented
as measured traffic. Every p82/p441 reason says "hinnang" (estimate) and
"mitte mõõdetud liiklus" (not measured traffic); LAYER_META below carries
the same labels for the future web layer (title/legend/source).

Style mirrors services/scoring/livability.py: every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100], Estonian reason).
Network lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability): a future central
hook may import this module from livability.py, and importing livability
here would turn that into a cycle (same precedent as PRs #100/#106).

Tag verification (2026-09-12, done once by the author with osmium against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime):
* highway arterial ways: 4979 (motorway|trunk|primary|secondary).
* maxspeed on ways: 14526 (50: 6065, 30: 2579, 90: 1350, 70: 1152, ...).
* traffic_calming objects: 2726 (table: 1819, bump: 428, island: 227,
  rumble_strip: 119, hump: 93, mini_bumps: 30, rest marginal).
* lit ways: 32390 (yes: 27160, no: 5193, 24/7: 18, automatic: 18,
  limited: 1) — static values only, NO seasonal schedules anywhere.
* amenity=school objects: ~460 (p441 school leg reuses livability's
  existing "school" kind, so no new fetch is needed for it — same
  precedent as p88 reusing bus_stop in PR #101).
* amenity=parking objects: 14902, of which on-street subtypes
  street_side: 3297, lane: 511, on_kerb: 4, layby: 22. Bare
  parking:lane:* / parking:street_side way tags: 0 in the snapshot, so
  p83 reads the amenity=parking subtypes instead (documented below).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p82 proxy: highway class is primary, parsed maxspeed refines. Class wins
  ties (a slowed primary still carries volume). maxspeed<=30 alone never
  demotes an arterial; it only keeps a local street calm. Fallback (no
  arterial within 1.5 km) is 90, not 100: maxspeed tagging is patchy, so
  an unmapped fast road may exist.
* p83 reads ONLY on-street subtypes (street_side/lane/on_kerb/layby):
  surface/garage/underground supply is another group's scope, and counting
  it would reward mall lots as street parking. Fallback is a mild 40:
  parking mapping is city-skewed, so absence is weak evidence.
* p166 direction: mapped calming nearby scores UP (quieter/safer
  residential street), capped at 80 — a speed table is a mild good, not
  an amenity. traffic_calming=no is explicitly excluded.
* p350 seasonal aspect is UNMAPPABLE (see lit values above), so this is a
  dark-season lighting proxy: lit=yes/24/7/automatic/limited way
  proximity. Fallback 40 (rural unlit is normal, not bad).
* p441 is a double proxy (school proximity x arterial proximity) and the
  reason names both distances. No school within 500 m scores 85 (no
  drop-off exposure); a nearby school without a nearby arterial scores 70
  (local-street pickup congestion only).
* One POI carries one kind: a lit primary way-center reads as fast_road,
  not lit_street (priority: calming > parking > road > lit). Losing one
  lit point is negligible — lit coverage is dense (27k ways).

Delivery (stated per the task brief): scorer dims ONLY, no raster masters.
Why: (1) these dims are way-geometry (arterial/lit corridors), not the
point-kernel shape the walk-raster pipeline stamps — corridor rasters need
a new length-weighted builder, not a reuse; (2) five county+metro masters
means five full-Harjumaa Dijkstra stamp runs plus hook edits to
layers.ts/snapshot.ts, which already collide with four open sibling PRs
(#100/#101/#103/#106 and the B1/B4 layer batches); (3) the repo precedent
(PRs #101/#106) is scorer-first with one central integration later.
LAYER_META below stages the honest web labels for that follow-up.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP18_OVERPASS_FRAGMENT (routing power/
highway tags through kinds_from_tags where static mapping cannot split),
livability._POI_KIND with GROUP18_POI_KIND, and rebalancing
livability.WEIGHTS must be one joint change across all parameter batches —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would
break every sibling.
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


def _count_within_m(
    origin: Tuple[float, float], pois: List[dict], kinds: set, radius_m: float
) -> int:
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
# Radii are judgment calls: arterials/speed effects carry (1.5 km),
# lit corridors read at night-walk scale (1 km), calming and parking are
# hyper-local (500 m). The school leg reuses livability's school kind.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP18_OVERPASS_FRAGMENT = """
  node["traffic_calming"](around:500,{lat},{lon});
  node["amenity"="parking"](around:500,{lat},{lon});
  way["highway"~"motorway|trunk|primary|secondary"](around:1500,{lat},{lon});
  way["maxspeed"](around:1500,{lat},{lon});
  way["traffic_calming"](around:500,{lat},{lon});
  way["lit"~"yes|24/7|automatic|limited"](around:1000,{lat},{lon});
  way["amenity"="parking"](around:500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND. Value-split
#: tags (maxspeed tiers, lit variants, parking subtypes, any traffic_calming
#: value) need kinds_from_tags below — the static table alone cannot split
#: them, so the central hook must route these keys through kinds_from_tags.
GROUP18_POI_KIND = [
    ("highway", {"motorway": "fast_road", "trunk": "fast_road",
                 "primary": "fast_road", "secondary": "busy_road"}),
    ("traffic_calming", {"table": "calming", "bump": "calming",
                         "island": "calming", "rumble_strip": "calming",
                         "hump": "calming", "mini_bumps": "calming",
                         "painted_island": "calming", "choker": "calming",
                         "cushion": "calming", "yes": "calming"}),
    ("lit", {"yes": "lit_street", "24/7": "lit_street",
             "automatic": "lit_street", "limited": "lit_street"}),
]

#: Highway classes that proxy high-volume arterials (verified in snapshot).
FAST_HIGHWAY = frozenset({"motorway", "trunk", "primary"})
#: Highway classes that proxy busy distributors.
BUSY_HIGHWAY = frozenset({"secondary"})
#: amenity=parking subtypes that are genuinely on-street (verified counts in
#: the module docstring). surface/garage/underground are out of scope.
ONSTREET_PARKING = frozenset({"street_side", "lane", "on_kerb", "layby"})
#: lit=* values meaning "this way is lit" (lit=no excluded by construction).
LIT_VALUES = frozenset({"yes", "24/7", "automatic", "limited"})


def _max_speed(value: object) -> Optional[int]:
    """Parse an OSM maxspeed tag ('50', '30;50', 'EE:urban') to an int."""
    if not isinstance(value, str):
        return None
    first = value.split(";")[0].strip()
    try:
        v = int(float(first))
    except ValueError:
        return None
    return v if v > 0 else None


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 18 kind matching the OSM tags, else None. Pure.

    Priority (documented judgment call): calming > parking > road class /
    speed > lit, so one way-center feeds exactly one scorer and arterials
    always read as roads, never as lighting.
    """
    if not isinstance(tags, dict):
        return None
    tc = tags.get("traffic_calming", "")
    if isinstance(tc, str) and tc.split(";")[0].strip() not in ("", "no"):
        return "calming"
    if tags.get("amenity") == "parking":
        sub = tags.get("parking", "")
        sub = sub.split(";")[0].strip() if isinstance(sub, str) else ""
        return "street_parking" if sub in ONSTREET_PARKING else None
    hw = tags.get("highway", "")
    hw = hw.split(";")[0].strip() if isinstance(hw, str) else ""
    v = _max_speed(tags.get("maxspeed"))
    if hw in FAST_HIGHWAY or (v is not None and v >= 70):
        return "fast_road"
    if hw in BUSY_HIGHWAY or (v is not None and 40 <= v <= 60):
        return "busy_road"
    lit = tags.get("lit", "")
    lit = lit.split(";")[0].strip() if isinstance(lit, str) else ""
    if lit in LIT_VALUES and hw:
        return "lit_street"
    return None


# ---------------------------------------------------------------------------
# p82: street traffic volume and speed — road-class/speed-limit PROXY.
# INVERTED: closer arterials -> lower score. Never measured traffic.
# ---------------------------------------------------------------------------

def dim_traffic(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p82: calm local street (high) vs arterial exposure (low), estimated
    from road class + speed limit — NOT measured traffic volumes."""
    if not origin or pois is None:
        return None, "Liiklusinfo puudub"
    d_fast = _nearest_m(origin, pois, {"fast_road"})
    d_busy = _nearest_m(origin, pois, {"busy_road"})
    if d_fast is None and d_busy is None:
        return 90, ("Rahulik tänav: kiirteed/magistraalid kaugemal kui "
                    "1,5 km (teeklassi hinnang, mitte mõõdetud liiklus)")
    scores = []
    if d_fast is not None:
        scores.append((_band(d_fast, [(100, 25), (200, 40), (400, 55),
                                      (800, 70), (1500, 85)]), d_fast, "kiirtee"))
    if d_busy is not None:
        scores.append((_band(d_busy, [(100, 45), (200, 60), (400, 75),
                                      (800, 85), (1500, 90)]), d_busy, "magistraal"))
    assert scores
    s, d, _label = min(scores, key=lambda t: (t[0], t[1]))
    assert s is not None
    return s, ("Liikluse hinnang (teeklass/kiiruspiirang, mitte mõõdetud "
               "liiklus): lähim %s" % _fmt_m(d))


# ---------------------------------------------------------------------------
# p83: on-street parking density (amenity=parking street subtypes).
# ---------------------------------------------------------------------------

def dim_parking(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p83: mapped on-street parking bays within 300 m (density is good)."""
    if not origin or pois is None:
        return None, "Parkimisinfo puudub"
    n = _count_within_m(origin, pois, {"street_parking"}, 300)
    if n == 0:
        return 40, "Kaardistatud tänavaparklat 300 m raadiuses pole"
    s = _band(n, [(2, 65), (5, 80)])
    assert s is not None
    return min(s, 90), "Kaardistatud tänavaparklaid 300 m raadiuses: %d" % n


# ---------------------------------------------------------------------------
# p166: traffic calming measures (traffic_calming=* proximity/count).
# ---------------------------------------------------------------------------

def dim_calming(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p166: mapped calming (tables/bumps/islands) within 500 m scores up —
    a calmer residential street. Capped below true amenities."""
    if not origin or pois is None:
        return None, "Liiklusrahustite info puudub"
    n = _count_within_m(origin, pois, {"calming"}, 500)
    if n == 0:
        return 45, "Kaardistatud liiklusrahusteid 500 m raadiuses pole"
    s = _band(n, [(1, 65), (3, 80)])
    assert s is not None
    return s, "Kaardistatud liiklusrahusteid 500 m raadiuses: %d" % n


# ---------------------------------------------------------------------------
# p350: seasonal street lighting — dark-season lighting proxy via lit ways.
# ---------------------------------------------------------------------------

def dim_lighting(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p350: mapped lit street proximity (winter-lighting proxy). The
    seasonal schedule itself is unmappable — OSM lit=* is static — so the
    reason never claims seasonal measurement."""
    if not origin or pois is None:
        return None, "Tänavavalgustuse info puudub"
    m = _nearest_m(origin, pois, {"lit_street"})
    if m is None:
        return 40, ("Valgustatud tänav kaardistamata või kaugemal kui 1 km "
                    "(talvevalgustuse hinnang)")
    s = _band(m, [(150, 100), (300, 85), (500, 70), (1000, 55)])
    assert s is not None
    return s, "Lähim valgustatud tänav %s (talvevalgustuse hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p441: school traffic gridlock — school x arterial co-proximity PROXY.
# INVERTED: exposed drop-off congestion -> lower score. Never measured.
# ---------------------------------------------------------------------------

def dim_school_gridlock(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p441: drop-off gridlock exposure estimate from a nearby school PLUS
    a nearby arterial (either alone is not gridlock)."""
    if not origin or pois is None:
        return None, "Kooli tipptunni info puudub"
    m_school = _nearest_m(origin, pois, {"school"})
    if m_school is None or m_school > 500:
        return 85, ("Kool kaugemal kui 500 m – kooli tipptunni ummikuoht "
                    "väike (hinnang, mitte mõõdetud liiklus)")
    m_road = _nearest_m(origin, pois, {"fast_road", "busy_road"})
    if m_road is None or m_road > 300:
        return 70, ("Kooli tipptunni hinnang: kool %s, magistraalid kaugel "
                    "– ummikuoht mõõdukas" % _fmt_m(m_school))
    s = _band(m_school, [(150, 25), (300, 40), (500, 55)])
    assert s is not None
    return s, ("Kooli tipptunni ummiku hinnang (mitte mõõdetud liiklus): "
               "kool %s, magistraal %s" % (_fmt_m(m_school), _fmt_m(m_road)))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP18_DIMS = (
    ("traffic", "p82", dim_traffic),
    ("parking", "p83", dim_parking),
    ("calming", "p166", dim_calming),
    ("lighting", "p350", dim_lighting),
    ("school_gridlock", "p441", dim_school_gridlock),
)


def score_group18(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 18 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP18_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP18_DIMS}


#: Honest Estonian web labels for the follow-up layers batch. p82/p441 say
#: "hinnang" (estimate/proxy) in the title itself — never bare "traffic".
LAYER_META = {
    "traffic": {
        "param": 82,
        "title": "Tänavaliiklus (teeklassi hinnang)",
        "good": "roheline = rahulik kohalik tänav (hinnang)",
        "bad": "punane = magistraali mõju (hinnang, mitte mõõdetud liiklus)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(teeklass + kiiruspiirang; hinnang, mitte mõõdetud liiklus)"),
    },
    "parking": {
        "param": 83,
        "title": "Tänavaparkimine",
        "good": "roheline = tänavaparklad jalutuskäigu kaugusel",
        "bad": "punane = kaardistatud tänavaparklad kaugel",
        "source": "kohalik hetktõmmis 2026-09-12 (amenity + parking)",
    },
    "calming": {
        "param": 166,
        "title": "Liiklusrahustid",
        "good": "roheline = rahustatud elamutänav",
        "bad": "punane = rahusteid kaardistamata",
        "source": "kohalik hetktõmmis 2026-09-12 (traffic_calming)",
    },
    "lighting": {
        "param": 350,
        "title": "Tänavavalgustus (talveproxy)",
        "good": "roheline = valgustatud tänav lähedal",
        "bad": "punane = valgustatud tänav kaugel",
        "source": "kohalik hetktõmmis 2026-09-12 (lit; staatiline, mitte hooajagraafik)",
    },
    "school_gridlock": {
        "param": 441,
        "title": "Kooli tipptund (hinnang)",
        "good": "roheline = kool kaugel või rahulikul tänaval",
        "bad": "punane = kool magistraali ääres (ummikuoht, hinnang)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(kool + teeklass; hinnang, mitte mõõdetud liiklus)"),
    },
}
