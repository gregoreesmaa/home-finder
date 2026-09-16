"""Seveso danger-polygon sidecar builder (issue #613): cached CSV -> map polygons.

Stdlib only. Offline, snapshot-only (NO network): the weekly Seveso CSV
pull lives in services/scoring/dims_p4_seveso.py (fetch_seveso_snapshot,
polite cache-first, 7 d TTL); this builder converts the already-cached
``ohtlikud_kaitised_ohualad.csv`` into the map sidecar
``<snap>/seveso/seveso-areas.json`` consumed by /api/layers/seveso/areas.
Pure logic at module top so unit tests stay hermetic; the sidecar write
runs only via the documented rebuild command.

SCOPE: danger POLYGONS only (Päästeamet register, CC BY-NC-ND 4.0 —
attribute, keep raw unmodified, NO re-interpolated raster). Rows carry
the scorer-parity danger class (toxic/heat/overpressure/combustion/
unknown, see classify_danger — same rules as
services/scoring/dims_p4_seveso.py). Point rows (ohtlikud_kaitised.csv)
are REFUSED here — the scorer-side point fallback never paints.

HONESTY (load-bearing): malformed rows are SKIPPED (never faked); a
missing input file writes NOTHING and reports ok=False (unknown, never
a partial zone list presented as complete). Rings keep register
L-EST97 WKT outer rings projected ONCE to WGS84 GeoJSON [lon, lat]
order (holes ignored fail-safe towards over-coverage, scorer parity);
ALL polygons are kept (dropping area would fake absence).

Rebuild: python3 scripts/build/batch_seveso.py \\
    --danger /tmp/hf-seveso-cache/ohtlikud_kaitised_ohualad.csv \\
    --snap ~/hf-data/2026-09-12
"""

import argparse
import csv
import io
import json
import math
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("seveso", "seveso-areas.json")

#: Publisher attribution (CC BY-NC-ND 4.0 — stamped in stats, not rows).
ATTRIBUTION = ("Päästeameti ohtlike ettevõtete register "
               "(opendata.smit.ee, CC BY-NC-ND 4.0)")

#: Danger classes in binding (worst-first) order for mixed labels.
DANGERS = ("toxic", "heat", "overpressure", "combustion", "unknown")


def classify_danger(raw: Optional[str]) -> str:
    """Map an ohu_tuup label to a danger class (pure, fail-closed).

    Scorer parity with services/scoring/dims_p4_seveso.py
    classify_danger: mixed labels classify binding (toxic wins).
    """
    text = (raw or "").lower()
    if "mürgised" in text or "murgised" in text:
        return "toxic"
    if "ülerõhk" in text or "ulerohk" in text:
        return "overpressure"
    if "soojus" in text:
        return "heat"
    if "põlem" in text or "polem" in text or "combust" in text:
        return "combustion"
    return "unknown"


# --- L-EST97 (EPSG:3301) -> WGS84, labelled approximate (~1 m). Copied,
# not imported, from services/scoring/dims_p4_seveso.py (itself a port
# of scripts/build/batch_tervise.py #511 via batch_accblack.py #522).
# Same constants, same datum label: per-issue files stay rebase-safe. ---

_LEST_A = 6378137.0
_LEST_F = 1 / 298.257222101
_LEST_E2 = 2 * _LEST_F - _LEST_F * _LEST_F
_LEST_E = math.sqrt(_LEST_E2)

_LEST_PHI0 = math.radians(57.5175539305556)
_LEST_LAM0 = math.radians(24.0)
_LEST_PHI1 = math.radians(59.3333333333333)
_LEST_PHI2 = math.radians(58.0)
_LEST_E0 = 500000.0
_LEST_N0 = 6375000.0


def _lest_m(phi: float) -> float:
    return math.cos(phi) / math.sqrt(1 - _LEST_E2 * math.sin(phi) ** 2)


def _lest_t(phi: float) -> float:
    s = _LEST_E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - s) / (1 + s)) ** (_LEST_E / 2)


_LEST_M1, _LEST_M2 = _lest_m(_LEST_PHI1), _lest_m(_LEST_PHI2)
_LEST_T1, _LEST_T2 = _lest_t(_LEST_PHI1), _lest_t(_LEST_PHI2)
_LEST_T0 = _lest_t(_LEST_PHI0)
_LEST_N = ((math.log(_LEST_M1) - math.log(_LEST_M2))
           / (math.log(_LEST_T1) - math.log(_LEST_T2)))
_LEST_FF = _LEST_M1 / (_LEST_N * _LEST_T1 ** _LEST_N)
_LEST_RHO0 = _LEST_A * _LEST_FF * _LEST_T0 ** _LEST_N


def lest97_to_wgs84(northing: float, easting: float) -> Tuple[float, float]:
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m (see above)."""
    if not (math.isfinite(northing) and math.isfinite(easting)):
        raise ValueError("non-finite L-EST97 coordinate")
    rho = math.copysign(
        math.hypot(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0)),
        _LEST_N)
    theta = math.atan2(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0))
    t = (rho / (_LEST_A * _LEST_FF)) ** (1 / _LEST_N)
    lam = theta / _LEST_N + _LEST_LAM0
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(20):
        s = _LEST_E * math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - s) / (1 + s)) ** (_LEST_E / 2))
    return math.degrees(phi), math.degrees(lam)


_NUM_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_WKT_RING_RE = re.compile(
    r"POLYGON\s*\(\(\s*([^()]*?)\)", re.IGNORECASE | re.DOTALL)


def _parse_wkt_outer_ring(wkt: str) -> List[Tuple[float, float]]:
    """Parse a POLYGON WKT outer ring to [(easting, northing)] (pure).

    Keeps the outer ring only (holes ignored — fail-safe towards
    over-coverage, scorer parity). Unparseable WKT reads as [].
    """
    m = _WKT_RING_RE.search(wkt or "")
    if not m:
        return []
    ring: List[Tuple[float, float]] = []
    for pair in m.group(1).split(","):
        nums = _NUM_RE.findall(pair)
        if len(nums) < 2:
            continue
        try:
            ring.append((float(nums[0].replace(",", ".")),
                         float(nums[1].replace(",", "."))))
        except ValueError:
            continue
    return ring


def project_ring_wgs84(ring: List[Tuple[float, float]]
                       ) -> List[Tuple[float, float]]:
    """Project an L-EST97 (easting, northing) ring to [(lat, lon)] (pure).

    Vertices that fail to project are dropped; a ring left with fewer
    than 4 vertices reads as unusable (callers skip it, never fake it).
    """
    out: List[Tuple[float, float]] = []
    for easting, northing in ring:
        try:
            out.append(lest97_to_wgs84(northing, easting))
        except ValueError:
            continue
    return out


def parse_danger_csv(csv_text: str) -> Optional[List[dict]]:
    """Parse ohtlikud_kaitised_ohualad.csv into zone records (pure).

    ;-separated, quote-tolerant. Returns [{zone_id, nimi, danger,
    danger_label, aadress, polys}] with polys as lists of [(lat, lon)]
    exterior rings; malformed rows skipped. None means unknown (never
    an empty zone list).
    """
    try:
        reader = csv.DictReader(io.StringIO((csv_text or "").lstrip("\ufeff")),
                                delimiter=";")
        rows = list(reader)
    except (csv.Error, ValueError):
        return None
    if not rows or "WKT" not in (reader.fieldnames or []):
        return None
    zones = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ring = project_ring_wgs84(_parse_wkt_outer_ring(row.get("WKT") or ""))
        if len(ring) < 4:
            continue
        ident = (row.get("kaitise_id") or "").strip() or "tundmatu"
        zones.append({
            "zone_id": ident,
            "nimi": ((row.get("nimi") or "").strip() or "tundmatu"),
            "danger": classify_danger(row.get("ohu_tuup")),
            "danger_label": (row.get("ohu_tuup") or "").strip(),
            "aadress": (row.get("aadress") or "").strip(),
            "polys": [ring],
        })
    return zones


def bbox_lonlat(polys: List[List[Tuple[float, float]]]) -> List[float]:
    """Prefilter box [minlon, minlat, maxlon, maxlat] over (lat, lon) rings."""
    los = [lo for ring in polys for _, lo in ring]
    las = [la for ring in polys for la, _ in ring]
    return [min(los), min(las), max(los), max(las)]


def to_sidecar(zones: Optional[List[dict]]) -> List[dict]:
    """Zone records -> sidecar rows (GeoJSON [lon, lat] rings + box).

    None (unknown snapshot) -> [] stays OUT of the writer: build_sidecar
    refuses to write it (unknown is never an empty zone list). Malformed
    rows are skipped, never faked.
    """
    rows = []
    for row in zones or []:
        if not isinstance(row, dict):
            continue
        if row.get("danger") not in DANGERS:
            continue
        polys = row.get("polys")
        if (not isinstance(polys, list) or not polys
                or any(not (isinstance(ring, list) and len(ring) >= 4)
                       for ring in polys)):
            continue
        try:
            rings = [[(float(la), float(lo)) for la, lo in ring]
                     for ring in polys]
        except (TypeError, ValueError):
            continue
        rows.append({
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "nimi": str(row.get("nimi") or "tundmatu"),
            "danger": row.get("danger"),
            "danger_label": str(row.get("danger_label") or ""),
            "aadress": str(row.get("aadress") or ""),
            "b": bbox_lonlat(rings),
            "r": [[[lo, la] for la, lo in ring] for ring in rings],
        })
    return rows


def build_sidecar(danger_path: Optional[str],
                  snap_dir: str) -> Dict[str, object]:
    """Cached danger CSV -> <snap>/seveso/seveso-areas.json.

    A missing or unparseable file: writes NOTHING and reports ok=False
    (unknown, never a partial zone list). No network, ever.
    """
    if not danger_path:
        return {"ok": False, "error": "no danger CSV provided"}
    try:
        with open(danger_path, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except OSError as exc:
        return {"ok": False, "error": "unreadable danger CSV: %s" % (exc,)}
    zones = parse_danger_csv(text)
    if zones is None:
        return {"ok": False, "error": "unparseable danger CSV"}
    rows = to_sidecar(zones)
    dest_dir = os.path.join(snap_dir, "seveso")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(snap_dir, SIDECAR_PATH)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    by_danger: Dict[str, int] = {}
    harju = 0
    for row in rows:
        by_danger[str(row["danger"])] = by_danger.get(str(row["danger"]), 0) + 1
        if "Harju" in str(row["aadress"]):
            harju += 1
    return {"ok": True, "dest": dest, "zones": len(rows),
            "skipped": len(zones) - len(rows), "harju": harju,
            "by_danger": by_danger, "attribution": ATTRIBUTION}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build Seveso danger sidecar.")
    ap.add_argument("--danger", default=None,
                    help="Cached ohtlikud_kaitised_ohualad.csv")
    ap.add_argument("--snap", required=True,
                    help="Snapshot dir to write to")
    args = ap.parse_args(argv)
    stats = build_sidecar(args.danger, args.snap)
    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
