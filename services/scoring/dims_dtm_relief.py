"""DTM relief/flatness character + taste-dependent scorer legs (issue #553).

Source: Maa-amet DTM (WCS ``teenus.maaamet.ee/ows/wcs-dtm``), CC BY 4.0,
ANNUAL. Probed 2026-09-16 (UA ``home-finder-idea-probe/1.0``): HTTP 200,
3 coverages ``dtm-25`` / ``dtm-10`` / ``dtm-1``, CRS EPSG:3301 (L-EST97),
all-Estonia envelope N 6375000..6635000 / E 365000..740000, native
GeoTIFF. DescribeCoverage ``dtm-1``: 1 m grid (375000 x 260000 cells).
One Harjumaa GetCoverage window (dtm-25, E 540000..541000 /
N 6588000..6589000, 40x40 float32, 6824 B): elevations 4.29..7.78 m,
mean 5.98 m — the service serves real DTM, no key, no 429.

Flatness is taste-dependent (a cyclist's green is a view-seeker's red),
so this module ships the EELIS #488 shape: a character overlay first
(hypsometric tint + slope bands, NO score field) plus capped
taste-dependent scorer legs, each labelled with its named taste
(cyclist / view-seeker / flood-avoider). No plain good/bad gradient.

Legs (each capped, each labelled):
* lowland-dampness flag (flood-avoider, bad side; flood-layer cousin).
* viewpoint-elevation leg (view-seeker taste-match, capped at 75).
* cycling-effort leg (cyclist mobility cost).
* klint-edge build-complexity flag (geotechnical buyer check, never a ban).

Style mirrors ``dims_group18chm``: pure scorers,
(origin, relief) -> (Optional[int 0..100], Estonian reason). No network
here — the annual bulk job turns WCS cells into the per-listing
``relief`` artefact the scorers join against. Transport errors are never
cached as data (there is no cache here at all).

Artefact shape: {"vintage", "z_m", "slope_pct", "relief_m",
"klint_near_m"}. ``z_m`` = DTM elevation at the listing (m); ``slope_pct``
= local grade in percent (rise/run*100); ``relief_m`` = max-min in the
~100 m window (relative elevation); ``klint_near_m`` = distance to the
mapped klint edge (p336 input for the cross-check, optional).
None means the bulk job has no DTM cell there (NOT flat — a nodata
window scores NULL, never "tasane").

Judgment calls (reviewable):
* Bands are coarse first cuts on the 1/5/10/25 m grids: tasane <2%,
  lauge 2-5%, moodukas 5-10%, jarske 10-20%, klint >20%. 1 m resolves
  streets, not kerbs/driveway crowns — micro-grade stays a buyer check.
* Viewpoint leg caps at 75: "korgusmudel naitab vaadet, mitte keeldu" —
  elevation is a taste match, never a top score on its own.
* Klint flag needs BOTH near edge (<=50 m) AND measured slope >10%:
  nearness alone is the old p336 proxy, steepness alone is any hill.
* Vintage: the WCS carries no per-cell vintage tag, so the artefact
  vintage is the tile survey year ("YYYY"); unknown vintages still score
  but say "tundmatu vintage" so years never mix silently (annual TTL).
* No landslide-risk scoring (slope != slide risk — legend must say so)
  and no view-shed monetisation (sea-view premium stays price modelling).

Integration (deliberately NOT done here): bulk job + any livability /
layers / registry edits stay a joint change (per-batch hook edits break
every sibling). No WEIGHTS / livability / layers edits.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Licence + publisher (catalogue claim, restated in doc reasons).
DTM_LICENCE = "CC BY 4.0 (Maa- ja Ruumiamet)"
#: CRS observed live on the WCS (DescribeCoverage srsName).
DTM_CRS = "EPSG:3301"
#: Coverages observed live on 2026-09-16 (resolutions, not vintages).
DTM_COVERAGES = frozenset({"dtm-25", "dtm-10", "dtm-1"})
#: Klint-edge proximity gate (m): needs measured steepness too.
KLINT_NEAR_M = 50.0
#: Klint steepness gate (percent).
KLINT_SLOPE_PCT = 10.0

#: Character slope bands (percent): label only, never a score.
SLOPE_BANDS = (
    (2.0, "tasane"),
    (5.0, "lauge"),
    (10.0, "mõõdukas"),
    (20.0, "järske"),
    (float("inf"), "klint"),
)


def check_vintage(vintage: object) -> bool:
    """True when the artefact vintage is a plausible tile survey year."""
    if not isinstance(vintage, str):
        return False
    v = vintage.strip()
    return len(v) == 4 and v.isdigit() and 2012 <= int(v) <= 2026


def _vintage_note(relief: dict) -> str:
    v = relief.get("vintage")
    if check_vintage(v):
        return "DTM %s" % v
    return "DTM tundmatu vintage (%s)" % ("puudub" if v is None else v)


def _nums(relief: Optional[dict]) -> Optional[Tuple[float, float]]:
    """(z_m, slope_pct) or None when there is no DTM artefact."""
    if not isinstance(relief, dict):
        return None
    z = relief.get("z_m")
    s = relief.get("slope_pct")
    z = z if isinstance(z, (int, float)) else None
    s = s if isinstance(s, (int, float)) and s >= 0 else None
    if z is None or s is None:
        return None
    return float(z), float(s)


def slope_character(slope_pct: float) -> str:
    """Slope-band label for the character overlay (no score)."""
    for limit, label in SLOPE_BANDS:
        if slope_pct <= limit:
            return label
    return SLOPE_BANDS[-1][1]


def character(relief: Optional[dict]) -> str:
    """Area-character prose: what the ground does here (never a score)."""
    if not isinstance(relief, dict) or _nums(relief) is None:
        return "DTM katet pole – pinnamood teadmata"
    z, s = _nums(relief)  # type: ignore[misc]
    band = slope_character(s)
    rel = relief.get("relief_m")
    rel_txt = ("; reljeef %.0f m" % rel) if isinstance(rel, (int, float)) else ""
    return "kõrgus %.1f m, %s kalle (%.1f%%)%s" % (z, band, s, rel_txt)


def histogram(values: List[float], edges: List[float]) -> List[int]:
    """Bin counts for edges (pure helper for the calibration check)."""
    counts = [0] * (len(edges) + 1)
    for v in values:
        placed = False
        for i, e in enumerate(edges):
            if v <= e:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return counts


def _band(value: float, bands: List[Tuple[float, int]]) -> int:
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


# ---------------------------------------------------------------------------
# Taste-dependent legs (each capped, each labelled with its named taste).
# ---------------------------------------------------------------------------

def dim_lowland(origin: Optional[Tuple[float, float]],
                relief: Optional[dict]) -> Score:
    """Lowland-dampness flag (flood-avoider taste, bad side)."""
    if not origin or _nums(relief) is None:
        return None, "DTM andmed puuduvad – madaliku hinnangut pole"
    assert relief is not None
    z, _ = _nums(relief)  # type: ignore[misc]
    tag = _vintage_note(relief)
    if z <= 3.0:
        s = 35
    elif z <= 5.0:
        s = 55
    elif z <= 8.0:
        s = 65
    else:
        s = 75
    return s, ("madalik %.1f m – %s (%s, mõõdetud; üleujutuskihi sugulane)"
               % (z, "niiske" if s <= 55 else "kuivemapoolne", tag))


def dim_viewpoint(origin: Optional[Tuple[float, float]],
                  relief: Optional[dict]) -> Score:
    """Viewpoint-elevation leg (view-seeker taste-match, capped at 75)."""
    if not origin or not isinstance(relief, dict):
        return None, "DTM andmed puuduvad – vaatehinnangut pole"
    rel = relief.get("relief_m")
    tag = _vintage_note(relief)
    if _nums(relief) is None:
        return None, "DTM andmed puuduvad – vaatehinnangut pole"
    if not isinstance(rel, (int, float)):
        return 60, ("reljeef teadmata – vaade eeldatud keskmine (%s, hinnang)"
                    % tag)
    s = _band(float(rel), [(2, 55), (6, 65), (12, 70)])
    if s > 75:
        s = 75
    return s, ("reljeef %.0f m – vaatemaitse (%s, mõõdetud; max 75)"
               % (float(rel), tag))


def dim_cycling(origin: Optional[Tuple[float, float]],
                relief: Optional[dict]) -> Score:
    """Cycling-effort leg (cyclist mobility cost)."""
    if not origin or _nums(relief) is None:
        return None, "DTM andmed puuduvad – rattasõidu hinnangut pole"
    assert relief is not None
    _, s = _nums(relief)  # type: ignore[misc]
    tag = _vintage_note(relief)
    pts = _band(s, [(2, 80), (5, 65), (10, 50), (20, 35)])
    if s > 20:
        pts = 25
    return pts, ("kalle %.1f%% (%s) – rattur (%s, mõõdetud)"
                 % (s, slope_character(s), tag))


def dim_klint_build(origin: Optional[Tuple[float, float]],
                    relief: Optional[dict]) -> Score:
    """Klint-edge build-complexity flag (geotechnical buyer check)."""
    if not origin or _nums(relief) is None:
        return None, "DTM andmed puuduvad – klindihinnangut pole"
    assert relief is not None
    _, s = _nums(relief)  # type: ignore[misc]
    near = relief.get("klint_near_m")
    tag = _vintage_note(relief)
    if not isinstance(near, (int, float)):
        return 65, ("klindi kaugus teadmata – ehitaus tavaline (%s, hinnang)"
                    % tag)
    if float(near) <= KLINT_NEAR_M and s > KLINT_SLOPE_PCT:
        return 40, ("klindi serv ≤%.0f m + kalle %.1f%% – ehituslik lisakontroll "
                    "(%s, mõõdetud; kõrgusmudel näitab vaadet, mitte keeldu)"
                    % (KLINT_NEAR_M, s, tag))
    return 65, ("klint kaugel/lage – ehitaus tavaline (%s, mõõdetud)" % tag)


def p336_crosscheck(osm_near_m: Optional[float],
                    slope_pct: Optional[float]) -> str:
    """OSM cliff proximity vs measured slope agreement label.

    Returns one of: "mõlemad märgivad" / "ainult OSM" / "ainult mõõdetud" /
    "mõlemad vaikivad" / "andmed puuduvad".
    """
    if osm_near_m is None or slope_pct is None:
        return "andmed puuduvad"
    osm = osm_near_m <= 100.0
    meas = slope_pct > KLINT_SLOPE_PCT
    if osm and meas:
        return "mõlemad märgivad"
    if osm and not meas:
        return "ainult OSM"
    if not osm and meas:
        return "ainult mõõdetud"
    return "mõlemad vaikivad"


DIMS = {
    "lowland": ("Madaliku niiskus (flood-avoider)", dim_lowland),
    "viewpoint": ("Vaate-reljeef (view-seeker, max 75)", dim_viewpoint),
    "cycling": ("Rattasõidu kalle (cyclist)", dim_cycling),
    "klint_build": ("Klindi ehituskeerukus (buyer check)", dim_klint_build),
}

LAYER_META = {
    "source": "Maa-amet DTM (WCS wcs-dtm)",
    "licence": DTM_LICENCE,
    "crs": DTM_CRS,
    "coverages": sorted(DTM_COVERAGES),
    "shape": "character overlay + capped taste legs (no 0-100 gradient)",
}


def score_dtm(origin: Optional[Tuple[float, float]],
              relief: Optional[dict]) -> Dict[str, Score]:
    """Score every DTM leg (pure; NULL where the artefact is missing)."""
    return {key: fn(origin, relief) for key, (_, fn) in DIMS.items()}
