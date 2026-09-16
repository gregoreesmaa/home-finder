"""Measured canopy heights from the CHM vegetation-height model (issue #546).

Upgrades the Group 18 geometry-proxy legs (p65 fall zone, p395 leaf
burden, p479 moss/shade cross-checks in ``dims_group18veg``) with measured
LiDAR canopy metres. Buyer questions are unchanged; only the legs get
metres instead of guesses.

Source: Maa- ja Ruumiamet taimkatte korgusmudel (CHM), CC BY 4.0, ANNUAL.
WMS ``teenus.maaamet.ee/ows/wms-chm`` (probed 2026-09-16: HTTP 200,
25 vintage layers CHM2008-11 .. CHM2024_suvi + aggregate ``CHM``,
CRS EPSG:3301, formats image/png + image/jpeg). Resolution 4 m since
2017 (10 m before); classes 1-4 / 4-10 / 10-20 / 20-30 / >30 m in
0.5 m steps, max assumed 50 m.

Where CHM contradicts OSM tree geometry, CHM wins (measured beats
mapped); the discrepancy note lives in the reason, never a silent
overwrite.

Style mirrors ``dims_group18veg``: pure scorers, (origin, canopy) ->
(Optional[int 0..100], Estonian reason). No network here — the annual
bulk job turns WMS/file cells into the per-listing ``canopy`` artefact
the scorers join against. Transport errors are never cached as data
(there is no cache here at all).

Judgment calls (reviewable):
* Artefact shape: {"vintage", "max_h_25m", "max_h_100m", "decid_near"}.
  max_h_* are the max CHM cell in metres; None means no CHM cover in
  that window (NOT zero trees — a nodata window scores the honest
  fallback, never "no trees").
* Fall zone radius = measured height, capped at 40 m (old proxy cap was
  a flat 25 m; the >30 m class + 50 m assumed max justify 40 m — full
  table in docs/group18chm-canopy.md). Bands follow the CHM class
  breaks 4/10/20/30 m.
* Height != species/health: the deciduous split stays an OSM proxy
  (``decid_near``); unknown leaf takes the moderate path, never the
  worst band (veg-module precedent).
* Vintage is stated in every scored reason (canopy grows / gets cut —
  TTL annual); unknown vintages are still scored but flagged
  "tundmatu vintage" so years never mix silently.
* No-data (canopy None, or both heights None) -> None with a
  "CHM puudub" reason. Absence of CHM cover is thin mapping, never a
  measured zero.

Integration (deliberately NOT done here): the bulk job + any
livability hook stay a joint change (per-batch hook edits break every
sibling — veg-module precedent). No WEIGHTS / livability / layers /
registry edits.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Vintages observed live on 2026-09-16 (GetCapabilities, 25 layers).
CHM_VINTAGES = frozenset({
    "2008-11",
    "2012_kevad", "2012_suvi",
    "2013_kevad", "2013_suvi",
    "2014",
    "2015_kevad", "2015_suvi",
    "2017", "2017_suvi",
    "2018_kevad", "2018_suvi",
    "2019_kevad", "2019_suvi",
    "2020_kevad", "2020_suvi",
    "2021_kevad", "2021_suvi",
    "2022_kevad", "2022_suvi",
    "2023_kevad", "2023_suvi",
    "2024_kevad", "2024_suvi",
})
#: Licence + publisher (catalogue claim, restated in every doc reason).
CHM_LICENCE = "CC BY 4.0 (Maa- ja Ruumiamet)"
#: Measured fall-zone cap (m): old proxy cap 25 m -> 40 m, see docs.
FALL_CAP_M = 40.0


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def check_vintage(vintage: object) -> bool:
    """True when the artefact vintage is a known WMS layer (pure)."""
    return isinstance(vintage, str) and vintage in CHM_VINTAGES


def _vintage_note(canopy: dict) -> str:
    v = canopy.get("vintage")
    if check_vintage(v):
        return "CHM %s" % v
    return "CHM tundmatu vintage (%s)" % ("puudub" if v is None else v)


def _heights(canopy: Optional[dict]) -> Optional[Tuple[Optional[float], Optional[float]]]:
    """(max_h_25m, max_h_100m) or None when there is no CHM artefact."""
    if not isinstance(canopy, dict):
        return None
    h25 = canopy.get("max_h_25m")
    h100 = canopy.get("max_h_100m")
    h25 = h25 if isinstance(h25, (int, float)) and h25 >= 0 else None
    h100 = h100 if isinstance(h100, (int, float)) and h100 >= 0 else None
    if h25 is None and h100 is None:
        return None
    return h25, h100


def histogram(values: List[float], edges: List[float]) -> List[int]:
    """Bin counts for edges (pure helper for the pre/post upgrade check).

    Returns len(edges)+1 counts: below edges[0], between, above
    edges[-1]. Used by docs/group18chm-canopy.md; tested on fixtures.
    """
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


# ---------------------------------------------------------------------------
# p65 upgrade: measured fall zone — radius IS the measured height.
# INVERTED burden: taller measured canopy overhead -> lower score.
# ---------------------------------------------------------------------------

def dim_chm_fall(origin: Optional[Tuple[float, float]],
                 canopy: Optional[dict]) -> Score:
    """p65 upgrade: storm-fall liability from measured canopy metres."""
    if not origin or _heights(canopy) is None:
        return None, "CHM andmed puuduvad – kukkumistsooni hinnangut pole"
    assert canopy is not None
    h25, _ = _heights(canopy)  # type: ignore[misc]
    tag = _vintage_note(canopy)
    if h25 is None:
        return 80, ("25 m aknas CHM katet pole – tormioht teadmata, "
                    "eeldatud väike (%s, mõõdetud)" % tag)
    h = min(h25, FALL_CAP_M)
    s = _band(h, [(1, 85), (4, 70), (10, 55), (20, 40), (30, 25)])
    assert s is not None
    if h25 > FALL_CAP_M:
        s = 15
    return s, ("Kõrgeim mõõdetud võra 25 m aknas: %.1f m "
               "(kukkumistsoon ~%.0f m, %s)" % (h25, h, tag))


# ---------------------------------------------------------------------------
# p395 upgrade: measured leaf burden — height + deciduous proxy.
# INVERTED burden. Unknown leaf stays moderate, never worst.
# ---------------------------------------------------------------------------

def dim_chm_leaf(origin: Optional[Tuple[float, float]],
                 canopy: Optional[dict]) -> Score:
    """p395 upgrade: autumn leaf burden from measured height + leaf proxy."""
    if not origin or _heights(canopy) is None:
        return None, "CHM andmed puuduvad – lehekoormuse hinnangut pole"
    assert canopy is not None
    _, h100 = _heights(canopy)  # type: ignore[misc]
    tag = _vintage_note(canopy)
    if h100 is None or h100 < 1:
        return 90, ("100 m aknas mõõdetud võra alla 1 m – "
                    "lehekoormus väike (%s, mõõdetud)" % tag)
    decid = canopy.get("decid_near")
    if decid is True:
        s = _band(h100, [(4, 65), (10, 50), (20, 35)])
        assert s is not None
        s = 20 if h100 > 20 else s
        return s, ("Lehtpuu võra kuni %.1f m 100 m aknas "
                   "(sügiskoormuse hinnang, %s)" % (h100, tag))
    return 55, ("Võra kuni %.1f m 100 m aknas, lehetüüp kaardistamata – "
                "lehekoormus võimalik (%s, mõõdetud kõrgus)" % (h100, tag))


# ---------------------------------------------------------------------------
# p479 cross-check: measured shade/dampness burden (moss-risk cousin).
# INVERTED burden: tall canopy close up -> lower score (shade + damp).
# ---------------------------------------------------------------------------

def dim_chm_shade(origin: Optional[Tuple[float, float]],
                  canopy: Optional[dict]) -> Score:
    """p479 cross-check: garden shade / dampness from measured canopy."""
    if not origin or _heights(canopy) is None:
        return None, "CHM andmed puuduvad – varjuhinnangut pole"
    assert canopy is not None
    h25, _ = _heights(canopy)  # type: ignore[misc]
    tag = _vintage_note(canopy)
    if h25 is None or h25 < 4:
        return 85, ("25 m aknas mõõdetud võra alla 4 m – aed valgusküllane "
                    "(%s, mõõdetud)" % tag)
    s = _band(h25, [(10, 65), (20, 45), (30, 30)])
    assert s is not None
    s = 20 if h25 > 30 else s
    return s, ("Kõrge võra (%.1f m) 25 m aknas – varju/niiskuse koormus "
               "(samblariski hinnang, %s)" % (h25, tag))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
CHM_DIMS = (
    ("chm_fall", "p65", dim_chm_fall),
    ("chm_leaf", "p395", dim_chm_leaf),
    ("chm_shade", "p479", dim_chm_shade),
)


def score_chm(origin: Optional[Tuple[float, float]],
              canopy: Optional[dict]) -> Dict[str, Optional[int]]:
    """All three CHM upgrade dims for one listing (rebalance entry point)."""
    return {key: fn(origin, canopy)[0] for key, _, fn in CHM_DIMS}


#: Honest Estonian web labels for the follow-up layers batch.
LAYER_META = {
    "chm_fall": {
        "param": 65,
        "title": "Puu kukkumistsoon (mõõdetud)",
        "good": "roheline = madal mõõdetud võra",
        "bad": "punane = kõrge mõõdetud võra krundi kohal",
        "source": "Maa-amet CHM (CC BY 4.0, aastavintage)",
    },
    "chm_leaf": {
        "param": 395,
        "title": "Lehekoormus (mõõdetud kõrgus)",
        "good": "roheline = mõõdetud võra alla 1 m",
        "bad": "punane = kõrge lehtpuu võra (hinnang, liik kaardistusest)",
        "source": "Maa-amet CHM + OSM lehetüüp (CC BY 4.0)",
    },
    "chm_shade": {
        "param": 479,
        "title": "Varju/niiskuse koormus (mõõdetud)",
        "good": "roheline = madal mõõdetud võra",
        "bad": "punane = kõrge võra varjutab (samblariski hinnang)",
        "source": "Maa-amet CHM (CC BY 4.0, aastavintage)",
    },
}
