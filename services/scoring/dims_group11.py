"""Group 11 OSM-based livability dimensions (issue #95).

Five pure, offline-tested scorers following the `dim_*` pattern in
livability.py: each takes `(origin, pois)` and returns
`(score|None, Estonian reason)`. Scores are absolute 0..100; `None` is
returned ONLY when the origin or the POI list itself is missing (never
as a guess). An absent POI kind means "not mapped nearby", which each
scorer handles with a documented fallback — not silence.

Param IDs (Group 11, all OSM-based, Harjumaa scope via the shared query):

* p169 proximity to philosophical/religious sites
  (`amenity=place_of_worship|monastery`).
* p346 mailbox placement/security (`amenity=letter_box`).
* p419 alleyway access (`highway=service` + `service=alley` ways).
* p466 public-trail privacy loss, INVERTED scale (`highway=path` ways).
* p470 mail delivery location (`amenity=post_office|parcel_locker`).

Judgment calls (reviewable per AGENTS.md §7.5):

* p169 scores proximity as a community/cultural amenity, like schools and
  services. Bell noise is a real downside for some buyers, but the repo
  convention is proximity-is-good and the reason string names the site
  type so buyers can judge.
* p346 fallback is a mild 30 (not 15): OSM `letter_box` coverage in
  Estonia is thin, so absence is weak evidence of a bad mailbox
  situation. The reason says "kaardistatud ... pole" (not mapped),
  never "there is none".
* p419 fallback is a NEUTRAL 50: most homes have no mapped alley nearby
  and that is normal, not bad. Presence scores up to 80 (a mild rear-
  access convenience, capped below true amenities).
* p466 is inverted (closer trail = lower privacy score) with a floor of
  35 and a ceiling of 90: a nearby trail is still a walking amenity, and
  unmapped trails may exist. Only `highway=path` (informal/recreational
  trails) counts — urban `footway`/`cycleway` sidewalks are deliberately
  excluded, otherwise every city listing would score the floor.
* p470 merges `parcel_locker` into the `post_office` kind (same
  precedent as `doctors` -> `clinic` in livability.py): both are
  parcel-receiving points and no other scorer consumes these kinds.

Network lives in livability.py (`resolve`/`fetch_pois`, cached 30d);
this module only exports the query fragment (GROUP11_QUERY_LINES) and
the tag mapping (GROUP11_POI_KIND) that livability.py splices in via a
marked hook. Weighting into `combine`/`enrich_row` is intentionally NOT
done here: `WEIGHTS` is pinned by existing tests and shared across
parallel batch agents, so rebalancing must happen once, centrally
(`score_group11` below is the entry point for that follow-up).
"""

import math
from typing import Dict, List, Optional, Tuple

# Overpass QL statements for the Group 11 tags. Spliced inside the (...)
# block of livability.OVERPASS_QUERY by the marked hook; {lat}/{lon}
# placeholders match the shared .format() call in fetch_pois. Way radii
# stay at 500 m (privacy/access effects are short-range) while amenity
# nodes use the shared 1500 m window.
GROUP11_QUERY_LINES = """\
  node["amenity"~"place_of_worship|monastery|letter_box|post_office|parcel_locker"](around:1500,{lat},{lon});
  way["amenity"~"place_of_worship|monastery|letter_box|post_office|parcel_locker"](around:1500,{lat},{lon});
  way["highway"="path"](around:500,{lat},{lon});
  way["service"="alley"](around:500,{lat},{lon});
"""

# Extra (tagkey, {value: kind}) entries appended to livability._POI_KIND.
# Kept as separate same-key tuples (not dict mutation) so the hook is a
# pure append; parse_overpass tries each tuple in order.
GROUP11_POI_KIND = [
    ("amenity", {"place_of_worship": "worship", "monastery": "worship",
                 "letter_box": "letter_box", "post_office": "post_office",
                 "parcel_locker": "post_office"}),
    ("highway", {"path": "trail"}),
    ("service", {"alley": "alley"}),
]


def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres (local copy: this module must not
    import livability, which imports this module via the hook)."""
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


def dim_worship(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """p169: philosophical/religious site proximity (OSM place_of_worship)."""
    if not origin or pois is None:
        return None, "Pühakodade info puudub"
    m = _nearest_m(origin, pois, {"worship"})
    if m is None:
        return 20, "Läheduses kaardistatud pühakoda puudub"
    s = _band(m, [(400, 100), (800, 80), (1200, 60)])
    return s, "Lähim pühakoda %s" % _fmt_m(m)


def dim_letterbox(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """p346: mailbox placement/security (OSM amenity=letter_box)."""
    if not origin or pois is None:
        return None, "Postkasti info puudub"
    m = _nearest_m(origin, pois, {"letter_box"})
    if m is None:
        return 30, "Läheduses kaardistatud postkasti pole"
    s = _band(m, [(300, 100), (600, 85), (1000, 70), (1500, 50), (2500, 30)])
    return s, "Lähim postkast %s" % _fmt_m(m)


def dim_alley(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """p419: alleyway (rear-lane) access (OSM service=alley ways)."""
    if not origin or pois is None:
        return None, "Taga-tänavate info puudub"
    m = _nearest_m(origin, pois, {"alley"})
    if m is None:
        return 50, "Kaardistatud taga-tänav läheduses puudub (neutraalne)"
    s = _band(m, [(150, 80), (300, 70), (500, 60)])
    return s, "Taga-tänava ligipääs %s" % _fmt_m(m)


def dim_trail_privacy(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """p466: public-trail privacy loss, INVERTED (OSM highway=path).

    Closer mapped trail -> more foot traffic past the home -> lower
    score. Urban footway/cycleway sidewalks are NOT in the "trail" kind.
    """
    if not origin or pois is None:
        return None, "Matkaradade info puudub"
    m = _nearest_m(origin, pois, {"trail"})
    if m is None:
        return 90, "Kaardistatud matkarada läheduses pole"
    s = _band(m, [(100, 35), (250, 60), (500, 80)])
    return s, "Lähim matkarada %s (privaatsus)" % _fmt_m(m)


def dim_postal(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """p470: mail delivery location (OSM post_office + parcel_locker)."""
    if not origin or pois is None:
        return None, "Postiteenuste info puudub"
    # Both kinds: the parser merges locker->post_office, but the scorer
    # must not depend on that (other POI sources may keep them split).
    m = _nearest_m(origin, pois, {"post_office", "parcel_locker"})
    if m is None:
        return 25, "Postkontor/pakiautomaat üle 2 km või kaardistamata"
    s = _band(m, [(500, 100), (1000, 80), (2000, 60)])
    return s, "Lähim postkontor/pakiautomaat %s" % _fmt_m(m)


# Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP11_DIMS = (
    ("worship", "p169", dim_worship),
    ("letterbox", "p346", dim_letterbox),
    ("alley", "p419", dim_alley),
    ("trail_privacy", "p466", dim_trail_privacy),
    ("postal", "p470", dim_postal),
)


def score_group11(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 11 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP11_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP11_DIMS}
