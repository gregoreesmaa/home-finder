"""Group 11 OSM dims (issue #95): hermetic scorer + plumbing tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and parse mapping runs on a static Overpass-style payload.
"""

import dims_group11b as g11
import livability
from dims_group11b import (
    GROUP11_POI_KIND,
    GROUP11_QUERY_LINES,
    dim_alley,
    dim_letterbox,
    dim_postal,
    dim_trail_privacy,
    dim_worship,
    score_group11,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# 0.001 deg lat ~= 111 m here; 0.001 deg lon ~= 57 m.


def test_worship_bands_and_reasons():
    v, r = dim_worship(TALLINN, [_poi("worship", 0.001)])  # ~111 m
    assert v == 100 and "pühakoda" in r
    v2, _ = dim_worship(TALLINN, [_poi("worship", 0.010)])  # ~1.1 km
    assert v2 == 60
    v3, r3 = dim_worship(TALLINN, [])
    assert v3 == 20 and "puudub" in r3


def test_letterbox_bands_and_reasons():
    v, r = dim_letterbox(TALLINN, [_poi("letter_box", 0.002)])  # ~222 m
    assert v == 100 and "postkast" in r
    v2, _ = dim_letterbox(TALLINN, [_poi("letter_box", 0.012)])  # ~1.3 km
    assert v2 == 50
    v3, r3 = dim_letterbox(TALLINN, [])
    # mild fallback: letter_box OSM coverage is thin, absence is weak evidence
    assert v3 == 30 and "pole" in r3


def test_alley_capped_and_neutral_when_absent():
    v, r = dim_alley(TALLINN, [_poi("alley", 0.001)])  # ~111 m
    assert v == 80 and "ligipääs" in r  # capped: mild convenience, not amenity
    v2, _ = dim_alley(TALLINN, [_poi("alley", 0.004)])  # ~445 m
    assert v2 == 60
    v3, r3 = dim_alley(TALLINN, [])
    assert v3 == 50 and "neutraalne" in r3  # absence is normal, not bad


def test_trail_privacy_is_inverted():
    near, r = dim_trail_privacy(TALLINN, [_poi("trail", 0.0005)])  # ~56 m
    assert near == 35 and "privaatsus" in r  # floor, never lower
    mid, _ = dim_trail_privacy(TALLINN, [_poi("trail", 0.003)])  # ~334 m
    assert mid == 80
    # beyond 500 m every mapped trail scores 80 (negligible privacy effect);
    # only a truly unmapped vicinity scores 90:
    far, _ = dim_trail_privacy(TALLINN, [_poi("trail", 0.010)])  # ~1.1 km
    assert far == 80
    assert near < mid <= far, "closer trail must mean a lower privacy score"
    v, r = dim_trail_privacy(TALLINN, [])
    assert v == 90 and "pole" in r


def test_trail_ignores_urban_sidewalks():
    # highway=footway/cycleway never become the "trail" kind: a sidewalk at
    # the doorstep must not tank the privacy score.
    v, _ = dim_trail_privacy(TALLINN, [_poi("footway", 0.0001)])
    assert v == 90


def test_postal_bands_and_reasons():
    v, r = dim_postal(TALLINN, [_poi("post_office", 0.004)])  # ~445 m
    assert v == 100 and "postkontor" in r
    v2, _ = dim_postal(TALLINN, [_poi("post_office", 0.015)])  # ~1.7 km
    assert v2 == 60
    v3, r3 = dim_postal(TALLINN, [_poi("parcel_locker", 0.004)])
    assert v3 == 100, "parcel lockers count as mail delivery points"
    v4, r4 = dim_postal(TALLINN, [])
    assert v4 == 25 and "kaardistamata" in r4


def test_missing_data_returns_none_with_reason():
    for fn in (dim_worship, dim_letterbox, dim_alley, dim_trail_privacy, dim_postal):
        v, r = fn(None, [_poi("worship", 0.001)])
        assert v is None and "puudub" in r
        v2, r2 = fn(TALLINN, None)
        assert v2 is None and "puudub" in r2


def test_scores_stay_in_absolute_bounds():
    pois = [_poi(k, d) for k, d in (
        ("worship", 0.0005), ("letter_box", 0.02), ("alley", 0.002),
        ("trail", 0.001), ("post_office", 0.008))]
    for fn in (dim_worship, dim_letterbox, dim_alley, dim_trail_privacy, dim_postal):
        v, _ = fn(TALLINN, pois)
        assert v is not None and 0 <= v <= 100


def test_score_group11_registry():
    out = score_group11(TALLINN, [_poi("worship", 0.001)])
    assert set(out) == {"worship", "letterbox", "alley", "trail_privacy", "postal"}
    assert out["worship"] == 100
    assert out["trail_privacy"] == 90  # no trail nearby -> private
    assert len(g11.GROUP11_DIMS) == 5
    assert [p for _, p, _ in g11.GROUP11_DIMS] == ["p169", "p346", "p419", "p466", "p470"]


def test_query_fragment_names_all_group11_tags():
    for tag in ("place_of_worship", "monastery", "letter_box", "post_office",
                "parcel_locker", '"highway"="path"', '"service"="alley"'):
        assert tag in GROUP11_QUERY_LINES, tag
    assert "{lat}" in GROUP11_QUERY_LINES and "{lon}" in GROUP11_QUERY_LINES
    assert "http" not in GROUP11_QUERY_LINES, "query must not hardcode a host"


def test_kind_table_maps_new_tags_via_parse():
    payload = {"elements": [
        {"type": "node", "lat": 59.1, "lon": 24.1, "tags": {"amenity": "place_of_worship"}},
        {"type": "node", "lat": 59.2, "lon": 24.2, "tags": {"amenity": "monastery"}},
        {"type": "node", "lat": 59.3, "lon": 24.3, "tags": {"amenity": "letter_box"}},
        {"type": "node", "lat": 59.4, "lon": 24.4, "tags": {"amenity": "post_office"}},
        {"type": "node", "lat": 59.5, "lon": 24.5, "tags": {"amenity": "parcel_locker"}},
        {"type": "way", "center": {"lat": 59.6, "lon": 24.6}, "tags": {"highway": "path"}},
        {"type": "way", "center": {"lat": 59.7, "lon": 24.7},
         "tags": {"highway": "service", "service": "alley"}},
        # pre-existing kinds must survive the appended same-key tuples:
        {"type": "node", "lat": 59.8, "lon": 24.8, "tags": {"amenity": "school"}},
        {"type": "node", "lat": 59.9, "lon": 24.9, "tags": {"highway": "bus_stop"}},
        {"type": "way", "center": {"lat": 60.0, "lon": 25.0},
         "tags": {"highway": "service"}},  # plain driveway: no kind
    ]}
    kinds = [(p["kind"], p["lat"]) for p in livability.parse_overpass(payload)]
    assert ("worship", 59.1) in kinds
    assert ("worship", 59.2) in kinds
    assert ("letter_box", 59.3) in kinds
    assert ("post_office", 59.4) in kinds
    assert ("post_office", 59.5) in kinds  # locker merges into postal kind
    assert ("trail", 59.6) in kinds
    assert ("alley", 59.7) in kinds
    assert ("school", 59.8) in kinds
    assert ("bus_stop", 59.9) in kinds
    assert all(lat != 60.0 for _, lat in kinds)
    assert len(GROUP11_POI_KIND) == 3


def test_livability_hook_fetches_group11_tags():
    # The marked hook in livability.py splices the fragment into the live
    # query; fetch_pois formats it with {lat}/{lon} like the base query.
    for tag in ("place_of_worship", "letter_box", "post_office",
                "parcel_locker", 'highway"="path', 'service"="alley'):
        assert tag in livability.OVERPASS_QUERY, tag
    assert "(around:1500,1.5,2.5)" in livability.OVERPASS_QUERY.format(lat=1.5, lon=2.5)
