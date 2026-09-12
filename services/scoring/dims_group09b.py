"""Group 9 leftover dimensions: batch GENV (issue #124).

Params (this agent only — sibling batches own disjoint sets):
* p234 subterranean vibration (maavärina/vibratsiooni proksi (hinnang):
  rail/tram + heavy-road ground-vibration proximity)
* p408 noise frequency sensitivity (madalsagedusliku müra proksi (hinnang):
  heavy-spectrum road + rail + industry rumble proximity)
* p445 flight path seasonality (lennukoridori proksi (hinnang): Tallinn
  Airport runway-corridor exposure; seasonality itself is NOT in OSM)

HONESTY (load-bearing, AGENTS.md §7.2): the Transpordiamet CNOSSOS-EU
strategic noise rasters (END 2002/49/EC) are NOT in the 2026-09-12
snapshot, so none of these dims reports decibels, magnitudes, or
seasonal schedules. Every scorer is an OSM PROXIMITY proxy: high score
= far/calm (green), low score = near/exposed (red). Every non-None
reason says "proksi" (and "(hinnang)" where a judgment is involved);
no reason mentions dB/dBA. Unknown (origin or POI list missing) stays
None — never a faked number.

p234 vs p301 vs p408 (deliberately distinct, documented judgment):
* p301 (sibling #104) scores airborne low-frequency rumble from rail +
  industrial areas (half 500 m).
* p234 scores GROUND-BORNE vibration: steel-on-steel rail/tram pass-bys
  plus heavy-truck routes (motorway/trunk). Vibration decays faster
  than airborne rumble, so the half-distance is shorter (300 m) and
  industry (continuous plant hum, not ground vibration) is excluded.
* p408 scores the heavy-traffic SPECTRUM a frequency-sensitive person
  notices: motorway/trunk/primary + rail + industrial (half 500 m).
  It shares the half with p301 but adds the heavy-road spectrum.

p445 judgment calls: OSM carries no movement counts or seasonal
schedules, so every runway counts equally within its length tier and
the reason states "hooajalisus teadmata" (seasonality unknown).
Corridor = runway geometry + extended-centreline lobes (the builder
samples the runway axis ±8 km); the live fragment below fetches
aeroway runways/aerodromes in an 8 km window.

Style mirrors services/scoring/livability.py: pure (origin, pois) ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. Network lives only in livability.fetch_pois; this module adds no
network calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12 snapshot, done once by the author, NOT at
runtime): harju-amenities.geojson carries railway=rail x1089 / tram
x194 LineStrings; motorway/trunk/primary ways are NOT in the amenity
sweep (class-blind car graph only), so the builder consumes the
one-time PBF export derived-heavyroads.geojson (nwr/ filter — PR #118:
node-only would silently drop way-mapped carriageways); runways come
from derived-aeroway.geojson (Tallinn 08/26 E-W runway + Ämari +
grass strips, LineStrings + area twins).

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP09B_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP09B_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# nwr/ filters (PR #118): carriageways, runways and aerodromes are mapped
# as ways/areas — node-only would silently drop them. Way geometries need
# centroid handling in parse_overpass ("out center" already returns one).
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP09B_POI_KIND = [
    ("highway", {"motorway": "heavy_road", "trunk": "heavy_road",
                 "primary": "heavy_road"}),
    ("railway", {"rail": "vibra_rail", "tram": "vibra_rail",
                 "narrow_gauge": "vibra_rail", "light_rail": "vibra_rail"}),
    ("aeroway", {"runway": "runway", "aerodrome": "airfield"}),
    ("landuse", {"industrial": "industrial09b"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP09B_OVERPASS_FRAGMENT = """
  nwr["highway"~"motorway|trunk|primary"](around:2000,{lat},{lon});
  nwr["railway"~"rail|tram|narrow_gauge|light_rail"](around:2000,{lat},{lon});
  nwr["aeroway"~"runway|aerodrome"](around:8000,{lat},{lon});
  nwr["landuse"="industrial"](around:2000,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 9b kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP09B_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p234: ground-vibration proxy (rail/tram + heavy-truck routes, half 300 m).
# ---------------------------------------------------------------------------

def dim_vibration(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p234: stillness from distance to rail/tram + heavy roads."""
    if not origin or pois is None:
        return None, "Vibratsiooni info puudub (proksi)"
    m = _nearest_m(origin, pois, {"vibra_rail", "heavy_road"})
    if m is None:
        return 85, "Raudtee/raskeliiklus kaugel (vibratsiooni proksi (hinnang): rahulik)"
    s = _band(m, [(150, 30), (300, 50), (600, 70)])
    assert s is not None
    return s, "Vibratsiooni proksi (hinnang): lähim raudtee/rasketee %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p408: heavy-spectrum rumble proxy (heavy roads + rail + industry, 500 m).
# ---------------------------------------------------------------------------

def dim_lowspec(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p408: calm from distance to heavy-spectrum rumble sources."""
    if not origin or pois is None:
        return None, "Madalasagedusliku müra info puudub (proksi)"
    m = _nearest_m(origin, pois, {"heavy_road", "vibra_rail", "industrial09b"})
    if m is None:
        return 90, "Raskeliiklus/raudtee/tööstus kaugel (madalsagedusliku müra proksi (hinnang): rahulik)"
    s = _band(m, [(250, 33), (500, 50), (1000, 67)])
    assert s is not None
    return s, "Madalsagedusliku müra proksi (hinnang): lähim raskeallikas %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p445: runway-corridor proxy (nearest runway/airfield, half 1500 m).
# Length-tiering lives raster-side (builder); the live scorer treats all
# mapped runways equally and says so ("hooajalisus teadmata").
# ---------------------------------------------------------------------------

def dim_flightcorr(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p445: quiet from distance to the nearest runway / airfield."""
    if not origin or pois is None:
        return None, "Lennukoridori info puudub (proksi)"
    m = _nearest_m(origin, pois, {"runway", "airfield"})
    if m is None:
        return 95, "Lennurada kaugel (lennukoridori proksi (hinnang): väljaspool koridori)"
    s = _band(m, [(750, 33), (1500, 50), (4500, 75)])
    assert s is not None
    return s, "Lennukoridori proksi (hinnang, hooajalisus teadmata): lähim rada %s" % _fmt_m(m)


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP09B_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "vibration": ("Maavärin/vibratsioon (proksi, hinnang)", dim_vibration),
    "lowspec": ("Madalsageduslik müra (proksi, hinnang)", dim_lowspec),
    "flightcorr": ("Lennukoridor (proksi, hinnang)", dim_flightcorr),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP09B_PARAM_IDS = {
    "vibration": 234,
    "lowspec": 408,
    "flightcorr": 445,
}


def score_group09b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 9b dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP09B_DIMS.items():
        v, reason = fn(origin, pois)
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
