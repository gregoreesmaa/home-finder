"""P4 asum polygon-join kernel: geocoded rows x polygons (issue #525).

Buyer report: per-asum asking medians read empty. The #495 verdict
stands (adapter records carry no `asum` key, no asum polygons
vendored, bar MIN_N=5) — this module builds the missing second half
of the ASUMEDIA_REOPEN checklist: the polygon-join half. #495's
kernel (`dims_p4_own_asum.py`, untouched) groups rows that ALREADY
carry an exact `asum` key; this module attaches that key from
coordinates x polygons, so geocoded snapshots can feed the #495
kernel without ever guessing from free text.

WFS VERDICT (2026-09-16, two polite single GETs, probe UA, no
retries, full evidence in docs/p4_asum_reopen.md): the proven path
(`gsavalik.envir.ee/geoserver/wfs`, #491 precedent) serves
GetCapabilities with 1091 typenames and GeoJSON polygons
(`ehak:linnade_piirid`, 1-feature pull parses as MultiPolygon in
L-EST97 metres) — but ZERO asum-grain layers. EHAK stops at
linn/omavalitsus/asustusuksus grain; the 84 Tallinna asum polygons
are not in this WFS. So production ships with an EMPTY polygon
snapshot (honest-empty, never fake medians, thin stays NULL) and the
fetch below refuses to guess a typename: `ASUM_WFS_TYPENAME = None`
until a polygon source is vendored or named.

Join discipline (statkov #485 identity-join-or-NULL precedent, same
as #495): rows join by point-in-polygon containment ONLY. Rows
without coords, rows outside every polygon, and free-text address
mentions never join (a "Kalamaja" substring is not an exact key).
Skipped rows are COUNTED, never silently dropped.

Threshold: MIN_N = 5, byte parity with MIN_N in
services/scoring/dims_p4_own_asum.py and ASUMEDIA_MIN_N in
apps/web/lib/layers_asumedia.ts (pinned by test on all three sides).
Groups below MIN_N stay NULL with their n labeled. No band table is
calibrated here: bands belong to the reopen PR, off the real
accumulated store (fixtures must never calibrate production).

Style mirrors dims_p4_own_asum.py (#495): pure, offline, stdlib-only
(json + statistics + urllib), no livability/sibling imports (a future
central hook may import this module alongside them — importing any of
them here would turn that into a cycle, batch B3 precedent). Reasons
are Estonian, say "hinnang" for estimates and "EI OLE" + missing
input + buyer check for NULLs.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Ring rule: outer ring contains, holes exclude (standard even-odd);
  boundary points count as inside (a listing on the line belongs to
  the asum rather than to nowhere — dull, documented).
* First-containing-polygon wins on overlaps (polygons from one
  authority layer should tile; overlaps are a source fix, not a
  weighting question here).
* Polygon snapshot TTL 30 d (admin boundaries move on
  reorganisation timescales, paaste-register precedent).
* Test fixtures are fully synthetic (unit-square polygons, clearly
  labelled) — real observed values appear only in
  docs/p4_asum_reopen.md, never as ingested data.

Integration (deliberately NOT done here): vending the 84 asum
polygons, accumulating geocoded snapshots, calibrating bands, and
rebalancing livability.WEIGHTS must be one joint change — existing
tests pin set(WEIGHTS) exactly. No shared files touched: 3 new files
only. Never touch dims_p4_own_asum.py, layers_asumedia.ts, or any
dims_group*.py.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[float], str]  # (median EUR/m2 | None, Estonian reason)

# Minimum snapshots per asum for an honest median (Land Board
# publications >= 5 precedent — parity pinned three ways, see test).
MIN_N = 5

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Proven WFS path (#491 precedent; verified 2026-09-16: HTTP 200,
#: 1 345 735 B GetCapabilities, 1091 typenames, GeoJSON output).
ASUM_WFS_BASE = "https://gsavalik.envir.ee/geoserver/wfs"
#: Asum-grain typename: NONE — documented-absent (dated 2026-09-16:
#: zero asum/linnaosa-grain layers in the 1091-name tally; EHAK stops
#: at linn/asustusuksus). The fetcher raises rather than guessing.
ASUM_WFS_TYPENAME: Optional[str] = None
ASUM_USER_AGENT = (
    "home-finder-p4-asum-join/1.0 (Estonia open-data monthly adapter; "
    "polite single-pull, cache-first)"
)
#: Admin boundaries move on reorganisation timescales: at most one
#: live pull per month.
ASUM_POLY_TTL_S = 30 * 86400
ASUM_POLY_CACHE_NAME = "asum-polygons.json"


def _wfs_url(typename: str, count: int = 1000) -> str:
    query = urllib.parse.urlencode({
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": typename,
        "count": count,
        "outputFormat": "application/json",
    })
    return ASUM_WFS_BASE + "?" + query


def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, ASUM_POLY_CACHE_NAME)


def cache_is_fresh(path: str, ttl_s: int = ASUM_POLY_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def fetch_polygons_snapshot(
    cache_dir: Optional[str] = None,
    ttl_s: int = ASUM_POLY_TTL_S,
    typename: Optional[str] = ASUM_WFS_TYPENAME,
) -> Tuple[str, str]:
    """Polite cached pull of the asum polygon layer (live path, NOT unit-run).

    Cache-first single GET. `typename=None` (the honest default: no
    asum-grain layer exists) raises a dated, actionable error BEFORE
    any network — the fetcher never guesses a layer name. Any
    transport error (HTTP error, timeout, 429, decode failure) raises
    and the cache file is left untouched; 429 stops the run. Returns
    (raw GeoJSON text, provenance) with provenance "cache" or "live".
    """
    if typename is None:
        raise RuntimeError(
            "Asumi polügoone WFS-is pole (EI OLE hetktõmmis): "
            "2026-09-16 GetCapabilities-loendus (1091 kihti) ei leidnud "
            "asumi-täpsusega kihti — EHAK peatub linna/asustusüksuse "
            "täpsusel; anna typename kaasa või vendo polügoonid")
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-asum-join")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if cache_is_fresh(path, ttl_s):
        with open(path, encoding="utf-8") as fh:
            return fh.read(), "cache"
    req = urllib.request.Request(
        _wfs_url(typename), headers={"User-Agent": ASUM_USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        if resp.status == 429:
            raise RuntimeError("WFS vastas 429 — peatu, ara reetry")
        if resp.status != 200:
            raise RuntimeError(
                "WFS vastas HTTP %s — vahemalu puutumata" % resp.status
            )
        body = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body, "live"


# ---------------------------------------------------------------------------
# Pure kernel: GeoJSON parse + point-in-polygon + join + medians.
# ---------------------------------------------------------------------------

def _ring_coords(ring: object) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    if not isinstance(ring, list):
        return pts
    for pos in ring:
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue
        x, y = pos[0], pos[1]
        if isinstance(x, bool) or isinstance(y, bool):
            continue
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) \
                and math.isfinite(x) and math.isfinite(y):
            pts.append((float(x), float(y)))
    return pts


def parse_polygons_geojson(text: str,
                           name_field: str = "nimi") -> List[dict]:
    """Parse a GeoJSON FeatureCollection into named polygons (pure).

    Returns [{name, polys: [[outer, hole, ...], ...]}] with lon/lat
    (or L-EST metre — the kernel is unit-agnostic, caller keeps rows
    and polygons in ONE frame) ring tuples. Unnamed features fall
    back to the feature id, then "teadmata-N". Raises ValueError on
    unparseable JSON or a non-FeatureCollection payload.
    """
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ValueError("asumi-GeoJSON ei parsinud: %s" % exc)
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection" \
            or not isinstance(payload.get("features"), list):
        raise ValueError("asumi-vastus pole FeatureCollection")
    out: List[dict] = []
    for index, feat in enumerate(payload["features"]):
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry") if isinstance(feat.get("geometry"), dict) \
            else None
        if geom is None:
            continue
        gtype = geom.get("type")
        raw = geom.get("coordinates")
        polys: List[List[List[Tuple[float, float]]]] = []
        if gtype == "Polygon" and isinstance(raw, list):
            rings = [_ring_coords(r) for r in raw]
            if rings and len(rings[0]) >= 4:
                polys.append(rings)
        elif gtype == "MultiPolygon" and isinstance(raw, list):
            for poly in raw:
                if not isinstance(poly, list):
                    continue
                rings = [_ring_coords(r) for r in poly]
                if rings and len(rings[0]) >= 4:
                    polys.append(rings)
        if not polys:
            continue
        props = feat.get("properties") if isinstance(feat.get("properties"), dict) \
            else {}
        name = props.get(name_field)
        if not isinstance(name, str) or not name.strip():
            fid = feat.get("id")
            name = str(fid) if fid is not None else "teadmata-%d" % index
        out.append({"name": name.strip(), "polys": polys})
    return out


def _point_on_segment(lon: float, lat: float,
                      x1: float, y1: float, x2: float, y2: float) -> bool:
    """True when the point lies on the segment (pure, exact arithmetic)."""
    cross = (lon - x1) * (y2 - y1) - (lat - y1) * (x2 - x1)
    if cross != 0.0:
        return False
    return (min(x1, x2) <= lon <= max(x1, x2)
            and min(y1, y2) <= lat <= max(y1, y2))


def _point_in_ring(lon: float, lat: float,
                   ring: List[Tuple[float, float]]) -> bool:
    """Even-odd containment; boundary counts as inside (pure)."""
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if _point_on_segment(lon, lat, x1, y1, x2, y2):
            return True
        if ((y1 > lat) != (y2 > lat)):
            xinters = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon <= xinters:
                inside = not inside
    return inside


def polygon_contains(lon: float, lat: float, polygon: dict) -> bool:
    """True when the point is in the named polygon (holes exclude)."""
    for rings in polygon.get("polys", []):
        if not rings:
            continue
        if _point_in_ring(lon, lat, rings[0]) and not any(
                _point_in_ring(lon, lat, hole) for hole in rings[1:]):
            return True
    return False


def _row_coords(row: dict) -> Optional[Tuple[float, float]]:
    """(lon, lat) for a geocoded row (None when absent — never guessed)."""
    if not isinstance(row, dict):
        return None
    lon, lat = row.get("lon"), row.get("lat")
    if isinstance(lon, bool) or isinstance(lat, bool):
        return None
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        return None
    if not (math.isfinite(lon) and math.isfinite(lat)):
        return None
    return float(lon), float(lat)


def _eur_m2(row: dict) -> Optional[float]:
    """EUR/m2 asking for one snapshot row (None when unusable)."""
    ppm = row.get("price_per_m2")
    if isinstance(ppm, bool):
        return None
    if isinstance(ppm, (int, float)):
        try:
            value = float(ppm)
        except (TypeError, ValueError):
            value = None
        if value is not None and math.isfinite(value) and value > 0:
            return value
    try:
        price = float(row.get("price"))
        area = float(row.get("area_m2"))
    except (TypeError, ValueError):
        return None
    if (math.isfinite(price) and math.isfinite(area)
            and price > 0 and area > 0):
        return price / area
    return None


def join_rows_to_polygons(rows: List[dict],
                          polygons: List[dict]) -> Tuple[List[dict], int]:
    """Attach exact `asum` keys by containment (pure).

    Returns (joined_rows, skipped): joined rows carry the polygon
    name as `asum` (first containing polygon wins on overlaps);
    coordless rows, rows outside every polygon, and priceless rows
    are skipped and COUNTED. Free-text addresses never join — only
    coordinates do.
    """
    joined: List[dict] = []
    skipped = 0
    for row in rows or []:
        coords = _row_coords(row) if isinstance(row, dict) else None
        value = _eur_m2(row) if isinstance(row, dict) else None
        if coords is None or value is None:
            skipped += 1
            continue
        lon, lat = coords
        hit = None
        for polygon in polygons or []:
            if isinstance(polygon, dict) and polygon_contains(lon, lat, polygon):
                hit = polygon.get("name")
                break
        if not isinstance(hit, str) or not hit:
            skipped += 1
            continue
        out = dict(row)
        out["asum"] = hit
        joined.append(out)
    return joined, skipped


def group_by_asum(rows: List[dict]) -> Tuple[Dict[str, List[float]], int]:
    """Group usable EUR/m2 values by exact asum key (pure).

    Returns (groups, skipped): rows without the joined key or
    without a usable price are skipped and COUNTED (same envelope
    as dims_p4_own_asum.group_by_asum — this module feeds that
    kernel, so the shapes agree by construction).
    """
    groups: Dict[str, List[float]] = {}
    skipped = 0
    for row in rows:
        if not isinstance(row, dict):
            skipped += 1
            continue
        key = row.get("asum")
        if not isinstance(key, str) or not key.strip():
            skipped += 1
            continue
        value = _eur_m2(row)
        if value is None:
            skipped += 1
            continue
        groups.setdefault(key.strip(), []).append(value)
    return groups, skipped


def describe_asum(asum: str, values: List[float],
                  min_n: int = MIN_N) -> Score:
    """(median EUR/m2 | None, Estonian reason) for one asum's group.

    Thin groups (< min_n) stay NULL with their n labeled — never a
    faked median (same rule as dims_p4_own_asum.describe_asum).
    """
    n = len(values)
    if n < min_n:
        return None, (
            "Asumi \"%s\" küsi-mediaani hinnang puudub (EI OLE piisavalt "
            "geokodeeritud snapshotte): %d liitunud snapshotti, vaja "
            "vähemalt %d — oota päevase korje kogunemist, ära feigi ühe "
            "kuulutuse hinnast asumi taset" % (asum, n, min_n))
    median = statistics.median(sorted(values))
    return median, (
        "Asumi \"%s\" küsi-mediaani hinnang: %.0f €/m² (%d liitunud "
        "snapshotti, polügoon-liide, küsi-, mitte sulgunud tehinguhind "
        "— võrdle maakleri tehingutega, ära loe garantiiks"
        % (asum, median, n))


def describe_joined_store(rows: List[dict],
                          min_n: int = MIN_N) -> Dict[str, Score]:
    """Whole joined-store medians: asum -> (median | None, reason).

    Every joined asum appears (thin ones as labeled NULLs). An empty
    polygon snapshot joins nothing, so this returns {} — honest-empty
    by construction, never a fake median.
    """
    groups, _skipped = group_by_asum(rows)
    return {asum: describe_asum(asum, values, min_n)
            for asum, values in sorted(groups.items())}
