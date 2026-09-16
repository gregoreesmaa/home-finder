"""State-land + auction polygon sidecar builder (issue #615): cached WFS GeoJSON -> map polygons.

Stdlib only. Offline, snapshot-only (NO network): the KATRI + auction
WFS pull is a polite one-off harvest (custom UA, paced >= 4 s, 429
stops the run — see docs/p4_riigimaa.md §6); this builder converts the
already-cached GetFeature GeoJSON files (state_property_ownership
pages + maaoksjon:auction, Harju window, EPSG:4326) into the map
sidecar ``<snap>/stateland/stateland-areas.json`` consumed by
/api/layers/stateland/areas. Pure logic at module top so unit tests
stay hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE: STATE parcels (katri:state_property_ownership, class "state")
+ ACTIVE auction parcels (maaoksjon:auction with status Avaldatud AND
a parseable-future offer_deadline, class "auction" with the date
carried — auction flags EXPIRE, never go stale silently). Usage-rights
/ maintenance / contract slices are REFUSED (rights, not ownership);
unreformed land is REFUSED on this pass (no rows pulled — a later
harvest may add it as its own class, never silently folded into
"state"). The scorer's forest/other split stays scorer-side: ZERO
harvested rows carry a forest signal (no RMK manager, no mets in
vara_liik/nimetus — provisional heuristic, see docs), so the map
paints ONE state class and the legend says the forest leg is
unobserved here.

HONESTY (load-bearing): expired/non-Avaldatud/unparseable-deadline
auctions are SKIPPED (never flagged); malformed rows are SKIPPED
(never faked); a missing input file writes NOTHING and reports
ok=False (unknown, never a partial zone list presented as complete).
Rings keep the service's EPSG:4326 GeoJSON [lon, lat] order into the
sidecar (no axis flip — pinned by test); ALL exterior rings are kept
(MultiPolygon members are real area, dropping them would fake
absence); interior holes are dropped (sub-parcel detail neither
consumer resolves — documented).

Rebuild: python3 scripts/build/batch_stateland.py \\
    --katri /tmp/hf-615-cache/katri_p0.json \\
    --katri /tmp/hf-615-cache/katri_p5000.json \\
    --katri /tmp/hf-615-cache/katri_p10000.json \\
    --auction /tmp/hf-615-cache/auction2.json \\
    --snap ~/hf-data/2026-09-12
(any --katri may repeat; --auction may be omitted when not cached)
"""

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys
from typing import Dict, List, Optional

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("stateland", "stateland-areas.json")

#: Publisher attribution (CC BY 4.0 — stamped in stats, not rows).
ATTRIBUTION = ("Maa- ja Ruumiamet (Land and Spatial Administration), "
               "licence CC BY 4.0")

#: Map classes (scorer parity: state adjacency vs auction warning).
CLASSES = ("state", "auction")

_DEADLINE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


def parse_deadline(raw: object) -> Optional[_dt.date]:
    """offer_deadline "17.09.2026 kell 10:00" -> date, None when unparseable."""
    m = _DEADLINE_RE.search(str(raw or ""))
    if not m:
        return None
    try:
        return _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _finite_lonlat(pt) -> Optional[tuple]:
    """[lon, lat] pair -> (lat, lon) when finite, else None."""
    if not isinstance(pt, (list, tuple)) or len(pt) < 2:
        return None
    try:
        lon, lat = float(pt[0]), float(pt[1])
    except (TypeError, ValueError):
        return None
    if isinstance(pt[0], bool) or not (
            math.isfinite(lat) and math.isfinite(lon)):
        return None
    return (lat, lon)


def _exterior_rings(geom: dict) -> List[List[tuple]]:
    """GeoJSON Polygon/MultiPolygon -> exterior rings as (lat, lon) lists.

    Interior holes are dropped (documented): the scorer gates on
    adjacency and the map paints membership fills — holes are
    sub-parcel detail neither consumer resolves.
    """
    if not isinstance(geom, dict):
        return []
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not isinstance(coords, list):
        return []
    polys: List[list] = []
    if gtype == "Polygon":
        polys = [coords]
    elif gtype == "MultiPolygon":
        polys = [p for p in coords if isinstance(p, list)]
    else:
        return []
    rings = []
    for poly in polys:
        if not poly or not isinstance(poly[0], list):
            continue
        ring = [_finite_lonlat(pt) for pt in poly[0]]
        ring = [pt for pt in ring if pt is not None]
        if len(ring) >= 4:
            rings.append(ring)
    return rings


def parse_katri_collection(text: str) -> Optional[List[dict]]:
    """KATRI ownership GeoJSON text -> state records (or None when unparseable).

    Returns [{zone_id, nimi, cls, tunnus, valitseja, polys}]; malformed
    features skipped. None means unknown (never an empty zone list).
    """
    try:
        collection = json.loads(text)
    except ValueError:
        return None
    if not isinstance(collection, dict):
        return None
    feats = collection.get("features")
    if not isinstance(feats, list):
        return None
    zones = []
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties")
        geom = feat.get("geometry")
        if not isinstance(props, dict):
            continue
        rings = _exterior_rings(geom) if isinstance(geom, dict) else []
        if not rings:
            continue
        tunnus = str(props.get("katastritunnus") or "").strip()
        zones.append({
            "zone_id": tunnus or str(props.get("fid") or "tundmatu"),
            "nimi": str(props.get("nimetus") or ""),
            "cls": "state",
            "tunnus": tunnus,
            "valitseja": str(props.get("riigivara_valitseja") or ""),
            "polys": rings,
        })
    return zones


def parse_auction_collection(text: str,
                             today: Optional[_dt.date] = None
                             ) -> Optional[List[dict]]:
    """Auction GeoJSON text -> active auction records (or None when unparseable).

    Only status == "Avaldatud" AND parseable-future offer_deadline join
    (expired auctions must not flag, unknown expiry must not flag
    either — scorer parity). Returns [{zone_id, nimi, cls, deadline,
    purpose, url, polys}]; skipped rows counted by the caller via
    len deltas. None means unknown (never an empty zone list).
    """
    if today is None:
        today = _dt.date.today()
    try:
        collection = json.loads(text)
    except ValueError:
        return None
    if not isinstance(collection, dict):
        return None
    feats = collection.get("features")
    if not isinstance(feats, list):
        return None
    zones = []
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties")
        geom = feat.get("geometry")
        if not isinstance(props, dict):
            continue
        if (props.get("status") or "").strip() != "Avaldatud":
            continue
        deadline = parse_deadline(props.get("offer_deadline"))
        if deadline is None or deadline < today:
            continue
        rings = _exterior_rings(geom) if isinstance(geom, dict) else []
        if not rings:
            continue
        purpose = str(props.get("purpose") or "").strip()
        zones.append({
            "zone_id": str(props.get("id") or "tundmatu"),
            "nimi": "%s (%s)" % (purpose or "oksjon",
                                 props.get("offer_deadline") or "tähtaeg?"),
            "cls": "auction",
            "deadline": "%02d.%02d.%04d" % (deadline.day, deadline.month,
                                           deadline.year),
            "purpose": purpose,
            "url": str(props.get("url") or ""),
            "polys": rings,
        })
    return zones


def bbox_lonlat(polys: List[List[tuple]]) -> List[float]:
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
        base = {
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "nimi": str(row.get("nimi") or ""),
            "cls": row.get("cls"),
            # Uniform shape (validator parity with isStatelandArea):
            # state rows carry tunnus/valitseja, auction rows carry
            # deadline/purpose/url; the other half stays "" (never null,
            # never absent — absent fields would fail the sidecar).
            "tunnus": str(row.get("tunnus") or ""),
            "valitseja": str(row.get("valitseja") or ""),
            "deadline": str(row.get("deadline") or ""),
            "purpose": str(row.get("purpose") or ""),
            "url": str(row.get("url") or ""),
            "b": bbox_lonlat(rings),
            "r": [[[lo, la] for la, lo in ring] for ring in rings],
        }
        rows.append(base)
    return rows


def build_sidecar(inputs: Dict[str, object], snap_dir: str) -> Dict[str, object]:
    """Cached WFS GeoJSON files -> <snap>/stateland/stateland-areas.json.

    inputs maps "katri" to a list of GeoJSON paths (or []) and
    "auction" to a path or None (not provided — skipped, counted). A
    provided-but-missing or unparseable file: writes NOTHING and
    reports ok=False (unknown, never a partial zone list). No network,
    ever.
    """
    zones: List[dict] = []
    tables: Dict[str, int] = {}
    skipped_tables: List[str] = []
    katri_paths = inputs.get("katri") or []
    if not katri_paths:
        skipped_tables.append("katri")
    for i, path in enumerate(katri_paths):
        try:
            with open(path, "r", encoding="utf-8") as fh:  # type: ignore[arg-type]
                text = fh.read()
        except OSError as exc:
            return {"ok": False, "error": "unreadable katri[%d]: %s" % (i, exc)}
        parsed = parse_katri_collection(text)
        if parsed is None:
            return {"ok": False, "error": "unparseable katri[%d]" % i}
        zones.extend(parsed)
    tables["katri"] = len([z for z in zones if z.get("cls") == "state"])
    auction_path = inputs.get("auction")
    if not auction_path:
        skipped_tables.append("auction")
    else:
        try:
            with open(auction_path, "r", encoding="utf-8") as fh:  # type: ignore[arg-type]
                text = fh.read()
        except OSError as exc:
            return {"ok": False, "error": "unreadable auction: %s" % (exc,)}
        parsed = parse_auction_collection(text)
        if parsed is None:
            return {"ok": False, "error": "unparseable auction"}
        zones.extend(parsed)
        tables["auction"] = len([z for z in zones if z.get("cls") == "auction"])
    rows = to_sidecar(zones)
    dest_dir = os.path.join(snap_dir, "stateland")
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
    ap = argparse.ArgumentParser(description="Build state-land sidecar.")
    ap.add_argument("--katri", action="append", default=[],
                    help="Cached katri:state_property_ownership GeoJSON (repeatable)")
    ap.add_argument("--auction", default=None,
                    help="Cached maaoksjon:auction GeoJSON")
    ap.add_argument("--snap", required=True,
                    help="Snapshot dir to write to")
    args = ap.parse_args(argv)
    stats = build_sidecar({"katri": args.katri, "auction": args.auction},
                          args.snap)
    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
