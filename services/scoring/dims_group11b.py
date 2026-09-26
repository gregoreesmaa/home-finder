"""Group 11 OSM-based livability dimensions, batch B3 (issue #95).

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

from typing import Dict, List, Optional, Tuple

from walk_access import (
    WALK_TAG,
    FootGraph,
    bands_for,
    nearest_walk_m,
)

# ---------------------------------------------------------------------------
# 814-HOOK (#814): pedestrian-access legs route the foot graph when a
# graph is injected, else the legacy bird-flight path (bit-identical).
# This module must not import livability (cycle via the hook); the walk
# helpers come from walk_access (stdlib-only, no sibling imports).
# Legacy band tables live in *_BANDS consts; bands_for picks the
# rescaled walk table on the walk path. Windows bound routing work only.
# ---------------------------------------------------------------------------

#: Legacy haversine band tables (walk recalibration via bands_for).
WORSHIP_BANDS = [(400, 100), (800, 80), (1200, 60)]
LETTERBOX_BANDS = [(300, 100), (600, 85), (1000, 70), (1500, 50), (2500, 30)]
ALLEY_BANDS = [(150, 80), (300, 70), (500, 60)]
TRAIL_PRIVACY_BANDS = [(100, 35), (250, 60), (500, 80)]
POSTAL_BANDS = [(500, 100), (1000, 80), (2000, 60)]
#: Routing windows (legacy band maxima; bound routing work only).
WORSHIP_WINDOW_M = 1200.0
LETTERBOX_WINDOW_M = 2500.0
ALLEY_WINDOW_M = 500.0
TRAIL_PRIVACY_WINDOW_M = 500.0
POSTAL_WINDOW_M = 2000.0


def _walked(reason: str, method: str) -> str:
    """Append the walk marker on the routed path, else the reason as-is."""
    return reason + (WALK_TAG if method == "walk" else "")

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


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def dim_worship(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]],
                graph: Optional[FootGraph] = None) -> Tuple[Optional[int], str]:
    """p169: philosophical/religious site proximity (OSM place_of_worship).

    814: routed foot-graph metres when graph is given, else legacy
    (bit-identical).
    """
    if not origin or pois is None:
        return None, "Pühakodade info puudub"
    m, method = nearest_walk_m(origin, pois, {"worship"},
                               WORSHIP_WINDOW_M, graph)
    if m is None:
        return 20, "Läheduses kaardistatud pühakoda puudub"
    s = _band(m, bands_for(method, WORSHIP_BANDS))
    return s, _walked("Lähim pühakoda %s" % _fmt_m(m), method)


def dim_letterbox(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]],
                  graph: Optional[FootGraph] = None) -> Tuple[Optional[int], str]:
    """p346: mailbox placement/security (OSM amenity=letter_box).

    814: routed foot-graph metres when graph is given, else legacy
    (bit-identical).
    """
    if not origin or pois is None:
        return None, "Postkasti info puudub"
    m, method = nearest_walk_m(origin, pois, {"letter_box"},
                               LETTERBOX_WINDOW_M, graph)
    if m is None:
        return 30, "Läheduses kaardistatud postkasti pole"
    s = _band(m, bands_for(method, LETTERBOX_BANDS))
    return s, _walked("Lähim postkast %s" % _fmt_m(m), method)


def dim_alley(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]],
              graph: Optional[FootGraph] = None) -> Tuple[Optional[int], str]:
    """p419: alleyway (rear-lane) access (OSM service=alley ways).

    814: routed foot-graph metres when graph is given, else legacy
    (bit-identical).
    """
    if not origin or pois is None:
        return None, "Taga-tänavate info puudub"
    m, method = nearest_walk_m(origin, pois, {"alley"},
                               ALLEY_WINDOW_M, graph)
    if m is None:
        return 50, "Kaardistatud taga-tänav läheduses puudub (neutraalne)"
    s = _band(m, bands_for(method, ALLEY_BANDS))
    return s, _walked("Taga-tänava ligipääs %s" % _fmt_m(m), method)


def dim_trail_privacy(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]],
                      graph: Optional[FootGraph] = None) -> Tuple[Optional[int], str]:
    """p466: public-trail privacy loss, INVERTED (OSM highway=path).

    Closer mapped trail -> more foot traffic past the home -> lower
    score. Urban footway/cycleway sidewalks are NOT in the "trail" kind.

    814: routed foot-graph metres when graph is given, else legacy
    (bit-identical). Inversion is orthogonal to the measurement: the
    rescaled bands keep the same inverted shape.
    """
    if not origin or pois is None:
        return None, "Matkaradade info puudub"
    m, method = nearest_walk_m(origin, pois, {"trail"},
                               TRAIL_PRIVACY_WINDOW_M, graph)
    if m is None:
        return 90, "Kaardistatud matkarada läheduses pole"
    s = _band(m, bands_for(method, TRAIL_PRIVACY_BANDS))
    return s, _walked("Lähim matkarada %s (privaatsus)" % _fmt_m(m), method)


def dim_postal(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]],
               graph: Optional[FootGraph] = None) -> Tuple[Optional[int], str]:
    """p470: mail delivery location (OSM post_office + parcel_locker).

    814: routed foot-graph metres when graph is given, else legacy
    (bit-identical).
    """
    if not origin or pois is None:
        return None, "Postiteenuste info puudub"
    # Both kinds: the parser merges locker->post_office, but the scorer
    # must not depend on that (other POI sources may keep them split).
    m, method = nearest_walk_m(origin, pois, {"post_office", "parcel_locker"},
                               POSTAL_WINDOW_M, graph)
    if m is None:
        return 25, "Postkontor/pakiautomaat üle 2 km või kaardistamata"
    s = _band(m, bands_for(method, POSTAL_BANDS))
    return s, _walked("Lähim postkontor/pakiautomaat %s" % _fmt_m(m), method)


# Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP11_DIMS = (
    ("worship", "p169", dim_worship),
    ("letterbox", "p346", dim_letterbox),
    ("alley", "p419", dim_alley),
    ("trail_privacy", "p466", dim_trail_privacy),
    ("postal", "p470", dim_postal),
)


def score_group11(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]],
                  graph: Optional[FootGraph] = None) -> Dict[str, Optional[int]]:
    """All five Group 11 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP11_DIMS).

    814: graph routes the pedestrian-access legs; None keeps legacy.
    """
    return {key: fn(origin, pois, graph)[0] for key, _, fn in GROUP11_DIMS}
