"""Measured building heights from 3D LoD1/LoD2 (issue #547).

Sharpens the G18 sun/shade/privacy legs (solar/shade/privacy/dayopen/
glassglare/fishbowl run on footprint geometry with 20 m+ bands) with
measured z_max per building — plus records the free EHR/address join
path (ehr_gid/ads_oid), never rebuilt here.

Source: Maa- ja Ruumiamet Eesti 3D hoonete LoD1/LoD2, CC BY 4.0.
800 000+ buildings from ETAK 2D + ALS clouds; per-feature etak_id,
ehr_gid, ads_oid, z_min/z_max (EH2000), type, ALS year. Recomputed
yearly (Q1); attributes refreshed several times a year. File downloads
(GDB + CityGML) per municipality.

Probe (2026-09-16, UA home-finder-idea-probe/1.0, single page pull):
https://geoportaal.maaruum.ee/eng/spatial-data/download-3d-data-p837.html
-> HTTP 200, 778 287 B, 1027 hooned_lod1 + 1012 hooned_lod2 refs,
hooned_lod2-Tallinn-{citygml,gdb,obj}.zip present, last update
29.04.2026. The 33 MB zip itself was NOT downloaded (polite: the page
proves servability; the annual bulk job downloads once/TTL).

Style mirrors dims_group18chm (#546): pure scorers, (origin, bldg) ->
(Optional[int 0..100], Estonian reason). No network here — the annual
bulk job parses Tallinn LoD2 CityGML into the per-listing ``bldg``
artefact the scorers join against. GDB/CityGML need GDAL-class tooling;
the harvest script must state that dependency (issue constraint) — this
module stays stdlib-only.

Judgment calls (reviewable):
* Artefact: {"als_year", "nearest": {"z_max","dist_m","etak_id",
  "ehr_gid","lod"}}. z_max = LoD1 flat-roof max height (EH2000 minus
  ground is the bulk job's business; scorers take height-over-ground).
* Shade: shadow length L = h / tan(winter-sun altitude). Tallinn
  December noon altitude ~7-12 deg; 12 deg (tan ~0.213, factor ~4.7)
  is the stated dull middle. dist <= L -> shaded.
* LoD1 flat roofs overstate parapet shade: capped hinnang, never
  survey-grade (legend + every reason say "hinnang"; LoD2 roof shapes
  only where they improve it — the artefact records which LOD won).
* ALS year in every scored reason (heights go stale where building
  continues); unknown year flags "tundmatu ALS-aasta".
* No-data (bldg None, or nearest None) -> None with an EHR/ALS-naming
  reason. No building within 100 m -> high honest scores, not NULL
  (absence of a tall neighbour IS the signal for shade/privacy).
* One-building worked example: shade_polygon() below; docs carry the
  numbers.

Integration (deliberately NOT done here): bulk job + livability hook
are a joint change. No WEIGHTS / livability / layers / registry edits.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Licence + publisher (catalogue claim, restated in docs + LAYER_META).
LOD_LICENCE = "CC BY 4.0 (Maa- ja Ruumiamet)"
#: Stated dull-middle winter-sun altitude for Tallinn (degrees).
WINTER_SUN_ALT_DEG = 12.0
#: Shadow-length factor 1/tan(12 deg) ~ 4.70.
SHADOW_FACTOR = 1.0 / math.tan(math.radians(WINTER_SUN_ALT_DEG))


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def shadow_length_m(height_m: float,
                    alt_deg: float = WINTER_SUN_ALT_DEG) -> float:
    """Shadow length for a height at a sun altitude (pure)."""
    return height_m / math.tan(math.radians(alt_deg))


def shade_polygon(height_m: float, azimuth_deg: float,
                  alt_deg: float = WINTER_SUN_ALT_DEG) -> Dict[str, float]:
    """Shade offset vector (dx, dy, length) for the worked example.

    Pure: shadow falls opposite the sun azimuth. Units metres.
    """
    length = shadow_length_m(height_m, alt_deg)
    away = math.radians((azimuth_deg + 180.0) % 360.0)
    return {"dx_m": round(length * math.sin(away), 1),
            "dy_m": round(length * math.cos(away), 1),
            "length_m": round(length, 1)}


def ehr_link_rate(buildings: List[dict]) -> Optional[float]:
    """ehr_gid fill rate over a bulk-job building list (pure probe helper).

    Returns 0..1, or None for an empty list. Records the free EHR join
    path without rebuilding it.
    """
    if not buildings:
        return None
    linked = sum(1 for b in buildings if b.get("ehr_gid"))
    return linked / len(buildings)


def _nearest(bldg: Optional[dict]) -> Optional[dict]:
    if not isinstance(bldg, dict):
        return None
    n = bldg.get("nearest")
    if not isinstance(n, dict):
        return None
    h, d = n.get("z_max"), n.get("dist_m")
    if not isinstance(h, (int, float)) or not isinstance(d, (int, float)):
        return None
    if h <= 0 or d < 0:
        return None
    return n


def _als_note(bldg: dict) -> str:
    y = bldg.get("als_year")
    if isinstance(y, int) and 2000 <= y <= 2100:
        return "ALS %d" % y
    return "tundmatu ALS-aasta"


# ---------------------------------------------------------------------------
# Shade: winter-sun shadow from measured z_max.
# ---------------------------------------------------------------------------

def dim_bldg_shade(origin: Optional[Tuple[float, float]],
                   bldg: Optional[dict]) -> Score:
    """Neighbour-shade burden from measured building height (hinnang)."""
    if not origin or not isinstance(bldg, dict) or _nearest(bldg) is None:
        return None, "3D-hoone andmed puuduvad – varjuhinnangut pole (EHR/ALS)"
    n = _nearest(bldg)
    assert n is not None
    h, d = float(n["z_max"]), float(n["dist_m"])
    tag = "%s, %s (hinnang, mitte mõõdistus)" % (
        _als_note(bldg), n.get("lod", "LoD teadmata"))
    shadow = h * SHADOW_FACTOR
    if d <= shadow:
        s = _band(h, [(9, 55), (15, 45), (25, 35)])
        assert s is not None
        s = 25 if h > 25 else s
        return s, ("Naaberhoone %.1f m varjutab talvepäikese "
                   "(vari ~%.0f m, %s)" % (h, shadow, tag))
    if d <= 2 * shadow:
        return 70, ("Naaberhoone %.1f m, vari ~%.0f m – "
                    "talvevari võimalik (%s)" % (h, shadow, tag))
    return 85, ("Naaberhoone %.1f m kaugusel %.0f m – "
                "talvevari väike (%s)" % (h, d, tag))


# ---------------------------------------------------------------------------
# Overlooking: measured height + distance (privacy/glass-glare cousin).
# ---------------------------------------------------------------------------

def dim_bldg_overlook(origin: Optional[Tuple[float, float]],
                      bldg: Optional[dict]) -> Score:
    """Overlooking burden from measured neighbour height + distance."""
    if not origin or not isinstance(bldg, dict) or _nearest(bldg) is None:
        return None, "3D-hoone andmed puuduvad – privaatsushinnangut pole"
    n = _nearest(bldg)
    assert n is not None
    h, d = float(n["z_max"]), float(n["dist_m"])
    tag = "%s (hinnang)" % _als_note(bldg)
    if d > 100:
        return 90, ("Lähim hoone kaugemal kui 100 m – "
                    "pealtvaade väike (%s)" % tag)
    if h >= 20 and d <= 30:
        return 35, ("%.0f m hoone %.0f m kaugusel – aknad vastamisi "
                    "(%s)" % (h, d, tag))
    if h >= 10 and d <= 50:
        return 55, ("%.0f m hoone %.0f m kaugusel – pealtvaade "
                    "võimalik (%s)" % (h, d, tag))
    return 75, ("%.0f m hoone %.0f m kaugusel – pealtvaade mõõdukas "
                "(%s)" % (h, d, tag))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
BLDG_DIMS = (
    ("bldg_shade", "p405", dim_bldg_shade),
    ("bldg_overlook", "p468", dim_bldg_overlook),
)


def score_bldg(origin: Optional[Tuple[float, float]],
               bldg: Optional[dict]) -> Dict[str, Optional[int]]:
    """Both 3D-height dims for one listing (rebalance entry point)."""
    return {key: fn(origin, bldg)[0] for key, _, fn in BLDG_DIMS}


#: Honest Estonian web labels for the follow-up layers batch.
LAYER_META = {
    "bldg_shade": {
        "param": 405,
        "title": "Naabri vari (mõõdetud kõrgus, hinnang)",
        "good": "roheline = talvevari väike",
        "bad": "punane = kõrge naaber varjutab",
        "source": "Maa-amet 3D LoD (CC BY 4.0, ALS-aasta kirjas)",
    },
    "bldg_overlook": {
        "param": 468,
        "title": "Pealtvaade (mõõdetud kõrgus, hinnang)",
        "good": "roheline = hooned kaugel/madalad",
        "bad": "punane = kõrge naaber lähedal",
        "source": "Maa-amet 3D LoD (CC BY 4.0, ALS-aasta kirjas)",
    },
}
