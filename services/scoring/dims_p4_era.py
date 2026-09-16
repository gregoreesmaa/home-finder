"""P4 building-era mix dims (issue #555): wooden / panel / new taste axis.

Second leg of the EHR-backfill hunt (#537): G2 EHR per-code facts
(#234/#537) score building *facts*; era mix is an *area
aggregation* of the same codes - different grain, different dims.
Heritage layers mark designated monuments, not the everyday era
fabric; price medians (#525) do not condition on era (this mix is
their future covariate, not a replacement).

GATE VERDICT (no new probe: reuses the inspected #537 evidence,
commit 7424533, probed 2026-09-16 - re-hammering the same unrouted
base the same day would be impolite): GATE UNMET. #537 proved the
EHR Avaandmete live base UNROUTED (``/api/av/v1/version`` and
``/alus/reports`` -> HTTP 404 "default backend" on live), so no
anonymous per-``ehr_code`` query is reachable and no build-year
field (ehitusaasta / esmane kasutus) could be confirmed on Harjumaa
codes - the fill rate is unknown because the pipe is dry, not
because the field was read. Per this issue's contract ("no field,
no issue") production joins stay NULL with the gate reason; the
aggregation below is fixture-proven for the day the route is
restored. Reopen checklist: re-GET ``/api/av/v1/version``; if 200,
walk ``/alus/reports`` -> one ``/info/reports/eh_ehitised`` pull ->
confirm the year field + Harjumaa fill rate -> wire records into
aggregate_era_mix. No fetcher ships here: with no reachable URL a
fetch function would be an untestable promise (nothing unverified
is ever fetched).

TASTE FRAMING (docs/layers.md conformance): character overlay
(first, no score field - era_character says "this street is wooden
/ panel / new-build", never scored); taste legs only: old-charm
delight (capped), new-build delight (warranty/efficiency taste,
capped). Honesty rule pinned by tests: era != condition (a rotten
wooden house outscores nothing; renovation grants #538 are the
condition cousin).

GRAIN (reviewer call, privacy reasoning): asum / micro-area with at
least MIN_BUILDINGS = 5 year-known buildings. Era mix must never
identify single houses, so thinner areas stay NULL and per-house
era display stays out (the taste question is about streets, not
doors).

ERA BANDS (from the Harjumaa stock distribution): pre-1945 wooden
town (Kalamaja/Pelgulinn fabric), 1945-1990 serial/panel mass
housing (Lasnamae/Oismae/Mustamae), post-1990 new-build sprawl and
infill (Viimsi/Rae/Lasnamae-infill). Dominant fabric: pre-1945
share >= 0.4 -> puitasum; 1945-1990 share >= 0.5 -> paneel;
post-1990 share >= 0.5 -> uusasum; else sega. CC BY-SA attribution
rides in reasons.

Integration (deliberately NOT done here): splicing into
livability.WEIGHTS and any /layers overlay is one joint change
across batches. No shared files touched: 3 new files only. EHR
files untouched.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Minimum year-known buildings per micro-area (privacy: era mix must
#: never identify single houses).
MIN_BUILDINGS = 5

#: Era cut years: pre-1945 wooden town / 1945-1990 serial-panel mass
#: housing / post-1990 new-build (Harjumaa stock reading).
ERA_CUT_OLD = 1945
ERA_CUT_NEW = 1990

#: Dominant-fabric thresholds (share of year-known stock).
WOODEN_SHARE = 0.4   # pre-1945 -> puitasum (wooden towns are mixed)
PANEL_SHARE = 0.5    # 1945-1990 -> paneel
NEW_SHARE = 0.5      # post-1990 -> uusasum

#: Old-charm leg: pre-1945 share = delight, capped at 70.
CHARM_BANDS = [(0.1, 35), (0.25, 50), (0.4, 60), (float("inf"), 70)]
#: New-build leg: post-1990 share = delight, capped at 70.
NEWBUILD_BANDS = [(0.15, 35), (0.35, 50), (0.5, 60), (float("inf"), 70)]

#: Nearest-mix join window (micro-area grain around the listing).
MIX_WINDOW_M = 500.0

#: Gate reason: production joins stay NULL until #537 reopens.
GATE_NULL = ("Ajastumiksi info puudub (EI OLE EHR avaandmete "
             "liidestust hetktõmmes: #537 toestas, et live-baas pole "
             "ruuditav - ehitusaasta vali kinnitamata)")


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


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _year(v) -> Optional[int]:
    """Sanitised construction year: plausible 1700..2030 int, else None."""
    if isinstance(v, bool):
        return None
    try:
        y = int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return y if 1700 <= y <= 2030 else None


def aggregate_era_mix(records: List[dict]) -> Optional[dict]:
    """Building-year records -> micro-area era mix. Pure.

    Records carry ``year`` (construction / first-use year). Returns
    ``{"pre1945": share, "mid": share, "post1990": share,
    "n": year-known count}`` over year-known buildings, or None when
    fewer than MIN_BUILDINGS buildings carry a usable year (privacy:
    thin areas stay NULL; era mix must never identify houses).
    Shares sum to 1.0; unknown-year records count for nothing.
    """
    if not records:
        return None
    years = [_year(r.get("year")) for r in records if isinstance(r, dict)]
    years = [y for y in years if y is not None]
    n = len(years)
    if n < MIN_BUILDINGS:
        return None
    pre = sum(1 for y in years if y < ERA_CUT_OLD)
    mid = sum(1 for y in years if ERA_CUT_OLD <= y <= ERA_CUT_NEW)
    post = sum(1 for y in years if y > ERA_CUT_NEW)
    return {"pre1945": pre / n, "mid": mid / n, "post1990": post / n, "n": n}


def era_character(mix: Optional[dict]) -> str:
    """Character overlay label (no score): the street's era fabric."""
    if mix is None:
        return "ajastumiks teadmata"
    if mix.get("pre1945", 0) >= WOODEN_SHARE:
        return "puitasum"
    if mix.get("mid", 0) >= PANEL_SHARE:
        return "paneel"
    if mix.get("post1990", 0) >= NEW_SHARE:
        return "uusasum"
    return "sega"


def _joined_mix(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Tuple[Optional[dict], Optional[str]]:
    """Shared join: nearest eramix cell within the window. Pure."""
    if not origin or pois is None:
        return None, GATE_NULL
    best = None
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != "eramix_p4":
            continue
        try:
            lat = float(p["lat"])
            lon = float(p["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(p.get("lat"), bool) or isinstance(p.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if best is None or d < best[0]:
            best = (d, p)
    if best is None or best[0] > MIX_WINDOW_M:
        return None, ("Läheduses pole ajastumiksi kirjet - hinnangut pole "
                      "(EI OLE EHR ajastuliidestust, mitte ajatu maja)")
    _, poi = best
    shares = {}
    for key in ("pre1945", "mid", "post1990"):
        v = poi.get(key)
        if isinstance(v, bool):
            return None, ("Ajastumiksi kirje vigane - hinnangut pole (EI OLE "
                          "loetavat ajastuliidestust)")
        try:
            shares[key] = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None, ("Ajastumiksi kirje vigane - hinnangut pole (EI OLE "
                          "loetavat ajastuliidestust)")
        if not (math.isfinite(shares[key]) and 0.0 <= shares[key] <= 1.0):
            return None, ("Ajastumiksi kirje vigane - hinnangut pole (EI OLE "
                          "loetavat ajastuliidestust)")
    n = poi.get("n")
    if isinstance(n, bool):
        return None, ("Ajastumiksi kirje vigane - hinnangut pole (EI OLE "
                      "loetavat ajastuliidestust)")
    try:
        n_int = int(n)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, ("Ajastumiksi kirje vigane - hinnangut pole (EI OLE "
                      "loetavat ajastuliidestust)")
    if n_int < MIN_BUILDINGS:
        return None, ("Ajastumiks liiga hõre (%d maja) - hinnangut pole "
                      "(EI OLE piisavat ajastuliidestust, mitte "
                      "üksikmaja maitse)" % n_int)
    mix = dict(shares)
    mix["n"] = n_int
    return mix, None


def dim_old_charm(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """Old-charm leg: pre-1945 share = delight, capped at 70.

    Era != condition: a rotten wooden house outscores nothing (the
    renovation-grant leg #538 is the condition cousin).
    """
    mix, null = _joined_mix(origin, pois)
    if mix is None:
        assert null is not None
        return None, null
    s = _band(mix["pre1945"], CHARM_BANDS)
    assert s is not None
    return s, ("Vana-sarmi maitsehinnang (EHR ajastumiks, CC BY-SA: "
               "enne 1945 %.0f%% %d majast) -> skoor %d (lakke 70; "
               "ajastu pole seisukord)" % (100 * mix["pre1945"], mix["n"], s))


def dim_newbuild(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """New-build leg: post-1990 share = delight, capped at 70."""
    mix, null = _joined_mix(origin, pois)
    if mix is None:
        assert null is not None
        return None, null
    s = _band(mix["post1990"], NEWBUILD_BANDS)
    assert s is not None
    return s, ("Uushoone-maitse hinnang (EHR ajastumiks, CC BY-SA: "
               "peale 1990 %.0f%% %d majast) -> skoor %d (lakke 70; "
               "ajastu pole seisukord)" % (100 * mix["post1990"], mix["n"], s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_ERA_DIMS = (
    ("old_charm", "P4-era", dim_old_charm),
    ("newbuild", "P4-era", dim_newbuild),
)


def score_p4_era(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 era taste legs for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_ERA_DIMS}
