"""Group 9 strategic-noise dimensions: batch G09 (issue #104).

Params (this agent only — sibling batches own disjoint sets):
* p16  noise levels (liiklusmüra proksi: road + rail proximity)
* p138 natural soundscapes (vaikuse + loodusheli proksi: traffic-far + nature-near)
* p162 noise and nuisance ordinances (häiringuallikate proksi: nightlife + industry)
* p301 infrasound and low-frequency noise (madalsagedusliku müra proksi: rail + industry)
* p493 braking and acceleration noise (pidurdusmüra proksi: junctions/signals/stops)

HONESTY (load-bearing, AGENTS.md §7.2): the Transpordiamet CNOSSOS-EU
strategic noise rasters (END 2002/49/EC) are NOT in the 2026-09-12
snapshot, so none of these dims reports decibels. Every scorer is a
road/rail-traffic PROXIMITY proxy: high score = far/quiet (green),
low score = near/loud (red). Every non-None reason says "müraproksi"
(and "hinnang" where a judgment is involved); no reason mentions dB/dBA.
Unknown (origin or POI list missing) stays None — never a faked number.

Style mirrors services/scoring/livability.py: pure (origin, pois) ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. Network lives only in livability.fetch_pois; this module adds no
network calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12 snapshot + OSM, done once by the author,
NOT at runtime):
* harju-amenities.geojson: railway=rail/tram/narrow_gauge/light_rail
  x1292 LineStrings, landuse=industrial x54, highway=traffic_signals x3
  (too sparse — true junctions come from the car graph offline, see
  scripts/build/batch_g09_noise.py; the live fragment below covers
  signals/crossings/stops as the labelled proxy).
* derived-nightlife.json: 283 points (bar 137, pub 72, casino 32,
  nightclub 24, cinema 18). Cinema is seated culture, not late-night
  nuisance, so the "nightlife" kind EXCLUDES amenity=cinema (265 usable).
* derived-transit.json: 8049 stops (bus_stop kind reused for p493).
* park-areas.json: 2454 polygons / 11992 ha + derived-parks.json points
  (reused base kinds park/forest/beach/water for p138 — no new fetch).

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP09_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP09_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# Radii are judgment calls: low-frequency rail/industry rumble carries
# (~1 km window), braking hotspots are short-range (~500 m), majors and
# nightlife sit in between (~800 m).
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP09_POI_KIND = [
    ("highway", {"motorway": "major_road", "trunk": "major_road",
                 "primary": "major_road", "secondary": "major_road",
                 "tertiary": "major_road",
                 "traffic_signals": "brake_hotspot"}),
    ("railway", {"rail": "railway", "tram": "railway",
                 "narrow_gauge": "railway", "light_rail": "railway",
                 "level_crossing": "brake_hotspot"}),
    # Cinema deliberately excluded: seated culture, not late-night nuisance.
    ("amenity", {"bar": "nightlife", "pub": "nightlife",
                 "nightclub": "nightlife", "casino": "nightlife"}),
    ("landuse", {"industrial": "industrial"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP09_OVERPASS_FRAGMENT = """
  node["highway"~"motorway|trunk|primary|secondary|tertiary|traffic_signals"](around:800,{lat},{lon});
  node["railway"~"rail|tram|narrow_gauge|light_rail|level_crossing"](around:1000,{lat},{lon});
  node["amenity"~"bar|pub|nightclub|casino"](around:800,{lat},{lon});
  node["landuse"="industrial"](around:1000,{lat},{lon});
  way["highway"~"motorway|trunk|primary|secondary|tertiary"](around:800,{lat},{lon});
  way["railway"~"rail|tram|narrow_gauge|light_rail"](around:1000,{lat},{lon});
  way["landuse"="industrial"](around:1000,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 9 kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP09_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p16: general traffic-noise proxy (nearest major road or railway).
# ---------------------------------------------------------------------------

def dim_traffic(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p16: quietness from distance to the nearest major road / railway."""
    if not origin or pois is None:
        return None, "Liiklusmüra info puudub (müraproksi)"
    m = _nearest_m(origin, pois, {"major_road", "railway"})
    if m is None:
        return 85, "Suur tee/raudtee üle ~1 km (müraproksi: vaikne)"
    s = _band(m, [(100, 25), (200, 45), (400, 65), (1000, 80)])
    assert s is not None
    return s, "Liiklusmüra proksi: lähim suur tee/raudtee %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p138: natural-soundscape proxy (traffic-far base + mapped-nature bonus).
# Unmapped forest reads as "no bonus", never as faked nature: Lahemaa-scale
# woods outside park-areas.json still score their (true) traffic quietness.
# ---------------------------------------------------------------------------

def dim_quiet_nature(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p138: traffic quietness, +10 when mapped nature is within 600 m."""
    if not origin or pois is None:
        return None, "Loodusheli info puudub (müraproksi)"
    m_tr = _nearest_m(origin, pois, {"major_road", "railway"})
    m_nat = _nearest_m(origin, pois, {"park", "forest", "beach", "water"})
    if m_tr is None:
        base = 85
        tr_txt = "suur tee/raudtee üle ~1 km"
    else:
        base = _band(m_tr, [(150, 35), (300, 60), (600, 80)])
        assert base is not None
        tr_txt = "lähim suur tee/raudtee %s" % _fmt_m(m_tr)
    # Nature ramp (mirrors the raster builder exactly): full +10 inside
    # the green, fading to +0 at 600 m — no cliff at the edge.
    bonus = round(10 * max(0.0, 1.0 - m_nat / 600.0)) if m_nat is not None else 0
    score = min(100, base + bonus)
    if bonus > 0:
        return score, "Loodusheli proksi: %s, loodusala %s" % (tr_txt, _fmt_m(m_nat))
    return score, "Loodusheli proksi: %s (kaardistatud loodusala kaugel)" % tr_txt


# ---------------------------------------------------------------------------
# p162: nuisance-ordinance proxy (nearest nightlife / industrial source).
# Ordinance TEXT is legal, not spatial — this scores exposure to the
# regulated nuisance sources (late-night venues, industry), honestly labelled.
# ---------------------------------------------------------------------------

def dim_nuisance(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p162: quietness from distance to nightlife / industrial nuisance."""
    if not origin or pois is None:
        return None, "Häiringuallikate info puudub (müraproksi)"
    m = _nearest_m(origin, pois, {"nightlife", "industrial"})
    if m is None:
        return 85, "Häiringuallikas (ööelu/tööstus) üle ~1 km (müraproksi: vaikne)"
    s = _band(m, [(150, 30), (300, 55), (600, 75), (1000, 82)])
    assert s is not None
    return s, "Häiringu proksi: lähim ööelu/tööstus %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p301: low-frequency / infrasound proxy (rail + industry carry furthest).
# ---------------------------------------------------------------------------

def dim_lowfreq(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p301: quietness from distance to rail / industrial LF sources."""
    if not origin or pois is None:
        return None, "Madalsagedusliku müra info puudub (müraproksi)"
    m = _nearest_m(origin, pois, {"railway", "industrial"})
    if m is None:
        return 90, "Raudtee/tööstus kaugel (madalsagedusliku müra proksi: vaikne)"
    s = _band(m, [(200, 30), (500, 55), (1000, 75)])
    assert s is not None
    return s, "Madalsagedusliku müra proksi: lähim raudtee/tööstus %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p493: braking / acceleration proxy (signals, crossings, stops, stations).
# bus_stop + rail_station kinds come from the BASE query (no new fetch);
# true graph junctions are raster-side only (see batch_g09_noise.py).
# ---------------------------------------------------------------------------

BRAKE_KINDS = {"brake_hotspot", "bus_stop", "rail_station"}


def dim_braking(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p493: quietness from distance to braking hotspots (short-range)."""
    if not origin or pois is None:
        return None, "Pidurdusmüra info puudub (müraproksi)"
    m = _nearest_m(origin, pois, BRAKE_KINDS)
    if m is None:
        return 90, "Pidurdusallikas (ristmik/peatus) kaugel (müraproksi: vaikne)"
    s = _band(m, [(50, 30), (150, 55), (300, 75)])
    assert s is not None
    return s, "Pidurdusmüra proksi: lähim ristmik/peatus %s" % _fmt_m(m)


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP09_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "traffic": ("Liiklusmüra (proksi)", dim_traffic),
    "quiet_nature": ("Loodusheli ja vaikus (proksi)", dim_quiet_nature),
    "nuisance": ("Häiringuallikad (proksi)", dim_nuisance),
    "lowfreq": ("Madalsageduslik müra (proksi)", dim_lowfreq),
    "braking": ("Pidurdusmüra (proksi)", dim_braking),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP09_PARAM_IDS = {
    "traffic": 16,
    "quiet_nature": 138,
    "nuisance": 162,
    "lowfreq": 301,
    "braking": 493,
}


def score_group09(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 9 dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP09_DIMS.items():
        v, reason = fn(origin, pois)
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
