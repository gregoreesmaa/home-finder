"""Quarry danger-polygon sidecar builder (issue #614): cached WFS GML -> map polygons.

Stdlib only. Offline, snapshot-only (NO network): the Maa-amet WFS pull
is a polite one-off harvest (custom UA, paced, 429 stops the run —
see docs/p4_maavara_extract.md §6); this builder converts the
already-cached GetFeature GML files (active extraction permits +
active exploration areas, Harjumaa L-EST97 window) into the map sidecar
``<snap>/quarry/quarry-areas.json`` consumed by
/api/layers/quarry/areas. Pure logic at module top so unit tests stay
hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE: permitted EXTRACTION areas (ms:maeeraldis_aktiivne, class
"active") + licensed EXPLORATION areas (ms:Aktiivne_uuringuala, class
"exploration"), CC BY 4.0 with Maa- ja Ruumiamet attribution. Applied-
for extraction (taotletav) is REFUSED here — an application is not a
permit (scorer parity: taotletav rides the exploration-grade watch
scorer-side, never the map). Deposit/reserve/prospective layers are
REFUSED — occurrence mapping, not permitted area.

HONESTY (load-bearing): only permit-ACTIVE extraction rows join
(ME_OLEK == "aktiivne" AND LOA_LOPP parseable-future; unknown/expired
status NEVER paints as active). Exploration rows keep their weak watch
class with the permit date carried (loa_lopp — the map legend says
dated watch-flag, liveness stays scorer-side). Malformed rows are
SKIPPED (never faked); a missing input file writes NOTHING and reports
ok=False (unknown, never a partial zone list). Rings keep the register
L-EST97 outer rings projected ONCE to WGS84 GeoJSON [lon, lat] order
(holes ignored fail-safe towards over-coverage, scorer parity); ALL
polygons of a multipolygon are kept (dropping area would fake absence).

Rebuild: python3 scripts/build/batch_quarry.py \\
    --extract /tmp/hf-614-cache/extract.gml \\
    --explore /tmp/hf-614-cache/explore.gml \\
    --snap ~/hf-data/2026-09-12
(either --<table> may be omitted when that pull is not cached)
"""

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("quarry", "quarry-areas.json")

#: Publisher attribution (CC BY 4.0 — stamped in stats, not rows).
ATTRIBUTION = ("Maa- ja Ruumiamet (Land and Spatial Administration), "
               "licence CC BY 4.0")

#: Map classes (scorer parity: active extraction vs exploration watch).
CLASSES = ("active", "exploration")


def parse_loa_lopp(raw: object) -> Optional[_dt.date]:
    """LOA_LOPP YYYYMMDD -> date, None when missing/unparseable (pure)."""
    text = str(raw or "").strip()
    if not re.fullmatch(r"\d{8}", text):
        return None
    try:
        return _dt.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


# --- L-EST97 (EPSG:3301) -> WGS84, labelled approximate (~1 m). Copied,
# not imported, from services/scoring/dims_p4_seveso.py (port of
# scripts/build/batch_tervise.py #511 via batch_accblack.py #522).
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


_MEMBER_RE = re.compile(r"<gml:featureMember>(.*?)</gml:featureMember>",
                        re.DOTALL)
_TAG_RE = re.compile(r"<ms:([A-Z_]+)>(.*?)</ms:\1>", re.DOTALL)
_RING_RE = re.compile(
    r"<gml:outerBoundaryIs>\s*<gml:LinearRing>\s*"
    r"<gml:coordinates>(.*?)</gml:coordinates>",
    re.DOTALL)
_PAIR_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _parse_coords(text: str) -> List[Tuple[float, float]]:
    """gml:coordinates "E,N E,N ..." -> [(easting, northing)] (pure)."""
    nums = _PAIR_RE.findall(text or "")
    pts = []
    for i in range(0, len(nums) - 1, 2):
        try:
            pts.append((float(nums[i]), float(nums[i + 1])))
        except ValueError:
            continue
    return pts


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


def parse_extract_gml(xml_text: str,
                      today: Optional[_dt.date] = None) -> Optional[List[dict]]:
    """Parse maeeraldis_aktiivne GML into zone records (pure).

    Returns [{zone_id, nimi, cls, loa, loa_lopp, operaator, polys}]
    with polys as lists of [(lat, lon)] exterior rings. Only
    permit-ACTIVE rows join (ME_OLEK == "aktiivne" AND LOA_LOPP
    parseable-future); anything else is skipped, never painted.
    None means unknown (never an empty zone list).
    """
    if today is None:
        today = _dt.date.today()
    if not isinstance(xml_text, str) or "<gml:featureMember>" not in xml_text:
        return None
    zones = []
    for member in _MEMBER_RE.findall(xml_text):
        attrs = dict(_TAG_RE.findall(member))
        if (attrs.get("ME_OLEK", "").strip().lower() != "aktiivne"):
            continue
        lopp = (attrs.get("LOA_LOPP") or "").strip()
        if parse_loa_lopp(lopp) is None or parse_loa_lopp(lopp) <= today:
            continue
        rings = []
        for block in _RING_RE.findall(member):
            ring = project_ring_wgs84(_parse_coords(block))
            if len(ring) >= 4:
                rings.append(ring)
        if not rings:
            continue
        zones.append({
            "zone_id": (attrs.get("ME_ID") or "").strip() or "tundmatu",
            "nimi": ((attrs.get("NIMETUS") or "").strip() or "tundmatu"),
            "cls": "active",
            "loa": (attrs.get("LOA_NUMBER") or "").strip(),
            "loa_lopp": lopp,
            "operaator": (attrs.get("KAEVANDAJA") or "").strip(),
            "polys": rings,
        })
    return zones


def parse_explore_gml(xml_text: str) -> Optional[List[dict]]:
    """Parse Aktiivne_uuringuala GML into watch records (pure).

    Returns [{zone_id, nimi, cls, loa, loa_lopp, operaator, polys}];
    rows keep the weak watch class with the permit date carried (the
    map legend says dated watch-flag — liveness stays scorer-side).
    None means unknown (never an empty zone list).
    """
    if not isinstance(xml_text, str) or "<gml:featureMember>" not in xml_text:
        return None
    zones = []
    for member in _MEMBER_RE.findall(xml_text):
        attrs = dict(_TAG_RE.findall(member))
        rings = []
        for block in _RING_RE.findall(member):
            ring = project_ring_wgs84(_parse_coords(block))
            if len(ring) >= 4:
                rings.append(ring)
        if not rings:
            continue
        zones.append({
            "zone_id": (attrs.get("U_ALA_ID") or "").strip() or "tundmatu",
            "nimi": ((attrs.get("U_ALA_NIMI") or "").strip() or "tundmatu"),
            "cls": "exploration",
            "loa": (attrs.get("LOA_NR") or "").strip(),
            "loa_lopp": (attrs.get("LOA_LOPP") or "").strip(),
            "operaator": (attrs.get("U_TEOSTAJA") or "").strip(),
            "polys": rings,
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
        if row.get("cls") not in CLASSES:
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
            "cls": row.get("cls"),
            "loa": str(row.get("loa") or ""),
            "loa_lopp": str(row.get("loa_lopp") or ""),
            "operaator": str(row.get("operaator") or ""),
            "b": bbox_lonlat(rings),
            "r": [[[lo, la] for la, lo in ring] for ring in rings],
        })
    return rows


def build_sidecar(inputs: Dict[str, Optional[str]],
                  snap_dir: str) -> Dict[str, object]:
    """Cached WFS GML files -> <snap>/quarry/quarry-areas.json.

    inputs maps cli flag ("extract"/"explore") to a GML path or None
    (table not provided — skipped, counted). A provided-but-missing or
    unparseable file: writes NOTHING and reports ok=False (unknown,
    never a partial zone list). No network, ever.
    """
    zones: List[dict] = []
    tables: Dict[str, int] = {}
    skipped_tables: List[str] = []
    parsers = {"extract": parse_extract_gml, "explore": parse_explore_gml}
    for flag in ("extract", "explore"):
        path = inputs.get(flag)
        if not path:
            skipped_tables.append(flag)
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            return {"ok": False, "error": "unreadable %s: %s" % (flag, exc)}
        parsed = parsers[flag](text)
        if parsed is None:
            return {"ok": False, "error": "unparseable %s" % flag}
        zones.extend(parsed)
        tables[flag] = len(parsed)
    rows = to_sidecar(zones)
    dest_dir = os.path.join(snap_dir, "quarry")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(snap_dir, SIDECAR_PATH)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False)
    by_cls: Dict[str, int] = {}
    for row in rows:
        by_cls[str(row["cls"])] = by_cls.get(str(row["cls"]), 0) + 1
    return {"ok": True, "dest": dest, "zones": len(rows),
            "skipped": len(zones) - len(rows), "tables": tables,
            "by_cls": by_cls, "skipped_tables": skipped_tables,
            "attribution": ATTRIBUTION}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build quarry danger sidecar.")
    ap.add_argument("--extract", default=None,
                    help="Cached maeeraldis_aktiivne GetFeature GML")
    ap.add_argument("--explore", default=None,
                    help="Cached Aktiivne_uuringuala GetFeature GML")
    ap.add_argument("--snap", required=True,
                    help="Snapshot dir to write to")
    args = ap.parse_args(argv)
    stats = build_sidecar({"extract": args.extract,
                           "explore": args.explore}, args.snap)
    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
