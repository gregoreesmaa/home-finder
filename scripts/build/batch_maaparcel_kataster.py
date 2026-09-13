"""Maa-amet kataster parcel sidecar builder (issue #491): WFS cache -> map polygons.

Stdlib only. Offline, snapshot-only (NO network): the polite WFS pull is
a documented one-off harvest (see docs/overturn_maa.md, #491 addendum:
5 polite GETs, UA home-finder-research/0.1, paced >= 3 s, count <= 100,
HTTP 429 = stop, raw bodies at /tmp/hf-491-maa-parcel/, never committed).
This builder converts an already-cached ``ky_kehtiv`` GeoJSON pull (+ the
cached KKIS ``kma_avalik_asjaoigus`` pull for the touch join) into the map
sidecar ``<snap>/maa/parcel-areas.json`` consumed by
/api/layers/maaparcel/areas. Pure logic at module top so unit tests stay
hermetic (synthetic fixtures only); the sidecar write runs only via the
documented rebuild command.

SCOPE (one layer, honest): this builder serves ONLY "maaparcel" (p364
ships twice -- the scorer hint lives in
services/scoring/dims_overturn_maa.py; this module answers the map
question: whose form is this lot). Parcel polygons carry an omandivorm
CLASS (Eraomand / Munitsipaalomand / Riigiomand / muu incl. the live
Avalik-oiguslik omand sample + NULL), never a suspicion score -- the map
paints register facts, exactly like the floodzone zone-membership
choropleth (issue #487). No raster, no gradient, no distance field.

HONESTY (load-bearing): the sidecar covers a harvested SAMPLE window
(Kesklinn 24.74-24.76 / 59.428-59.438, 100 parcels, 2026-09-13 -- outside
the window is teadmata, never empty); malformed features are SKIPPED
(never faked); a missing/unparseable cache yields NO sidecar rows for
that file (unknown, never "no parcels" -- the route serves
honestly-empty and the legend says outside = teadmata, mitte tuhi).
The KKIS touch count is a coarse puute-liide (centroid OR any vertex
either way -- meter-scale utility strips miss parcel centroids, so a
centroid-only join would undercount; labelled jame in the sidecar
provenance, never a deed check). Maardlad (10 levialad in the market
window, 0 in the parcel window) are a harvest TALLY only -- painting
deposit polygons as a buyer layer is a second question for a follow-up;
p76/p229 scorer dims are untouched.

Rebuild: python3 scripts/build/batch_maaparcel_kataster.py \\
    --parcels /tmp/hf-491-maa-parcel/kk_ky100_window.json \\
    --kkis /tmp/hf-491-maa-parcel/kkis10_window.json \\
    --snap ~/hf-data/2026-09-12
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("maa", "parcel-areas.json")

#: Harvest window + date (baked into the sidecar provenance).
SAMPLE_BBOX = [24.74, 59.428, 24.76, 59.438]
HARVEST_DATE = "2026-09-13"

#: Paint classes (register facts, never scores). "muu" folds the live
#: "Avalik-oiguslik omand" sample + NULL/unknown (documented judgment:
#: a fourth fill for 2/100 parcels would be noise; the raw omvorm rides
#: along in every row so the fold stays reviewable).
CLASS_BY_OMVORM = {
    "Eraomand": "era",
    "Munitsipaalomand": "muni",
    "Riigiomand": "riik",
}

Ring = List[Tuple[float, float]]


def valid_lonlat(x: float, y: float) -> bool:
    """Plausible EPSG:4326 pair (lon, lat order -- GeoJSON, not WFS GML)."""
    return (-180.0 <= x <= 180.0) and (-90.0 <= y <= 90.0)


def clean_ring(coords) -> Optional[Ring]:
    """Raw coordinate list -> [(lon, lat)] ring or None (never faked).

    Bar: >= 4 finite plausible pairs (closed or closable); non-list or
    ragged input is None.
    """
    if not isinstance(coords, list) or len(coords) < 4:
        return None
    ring: Ring = []
    for pt in coords:
        if (not isinstance(pt, (list, tuple)) or len(pt) != 2
                or not all(isinstance(n, (int, float)) for n in pt)):
            return None
        x, y = float(pt[0]), float(pt[1])
        if not (x == x and y == y) or not valid_lonlat(x, y):  # NaN-safe
            return None
        ring.append((x, y))
    return ring


def rings_of_feature(feat: dict) -> List[Ring]:
    """Exterior rings of a Polygon/MultiPolygon feature (else [])."""
    try:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
    except AttributeError:
        return []
    polys: list = []
    if gtype == "Polygon" and isinstance(coords, list):
        polys = [coords]
    elif gtype == "MultiPolygon" and isinstance(coords, list):
        polys = [p for p in coords if isinstance(p, list)]
    rings: List[Ring] = []
    for poly in polys:
        if poly and isinstance(poly[0], list):
            ring = clean_ring(poly[0])
            if ring is not None:
                rings.append(ring)
    return rings


def ring_contains(ring: Ring, x: float, y: float) -> bool:
    """Ray-cast containment (same math as dims_overturn_flood joins)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def touches(parcel_ring: Ring, kkis_rings: List[Ring]) -> bool:
    """Coarse touch join (jame): centroid OR any vertex either way.

    Meter-scale KKIS strips (kanalisatsioonitrass, isiklik kasutusõigus)
    routinely miss parcel centroids, so centroid-only containment would
    undercount to ~zero on the live sample (verified: 0/100 centroid vs
    5/100 touch on the #491 harvest). Segment-intersection completeness
    is deliberately NOT attempted -- this is a hint count, never a deed
    check (the RIK extract stays named in the layer legend).
    """
    n = len(parcel_ring)
    cx = sum(p[0] for p in parcel_ring) / n
    cy = sum(p[1] for p in parcel_ring) / n
    for kr in kkis_rings:
        if ring_contains(kr, cx, cy):
            return True
        if any(ring_contains(kr, vx, vy) for vx, vy in parcel_ring):
            return True
        if any(ring_contains(parcel_ring, vx, vy) for vx, vy in kr):
            return True
    return False


def classify(omvorm) -> str:
    """Raw omvorm value -> paint class (muu folds unknown, documented)."""
    if isinstance(omvorm, str):
        return CLASS_BY_OMVORM.get(omvorm, "muu")
    return "muu"


def bbox_lonlat(rings: List[Ring]) -> List[float]:
    """Prefilter box [minlon, minlat, maxlon, maxlat] over GeoJSON rings."""
    xs = [x for r in rings for x, _ in r]
    ys = [y for r in rings for _, y in r]
    return [min(xs), min(ys), max(xs), max(ys)]


def build_sidecar(parcels_doc: dict, kkis_doc: Optional[dict]) -> List[dict]:
    """Cached GeoJSON docs -> sidecar rows (skips malformed, never fakes).

    Row: {tunnus, cls, omvorm, siht1, pindala, aadress, kkis, b, r}.
    kkis is the coarse touch-hit count (jame, see touches()); None when
    no KKIS cache was supplied (unknown, never zero).
    """
    kkis_feat_rings: List[List[Ring]] = []
    if isinstance(kkis_doc, dict):
        for feat in (kkis_doc.get("features") or []):
            if isinstance(feat, dict):
                rings = rings_of_feature(feat)
                if rings:
                    kkis_feat_rings.append(rings)
    rows: List[dict] = []
    feats = parcels_doc.get("features") if isinstance(parcels_doc, dict) else None
    if not isinstance(feats, list):
        return rows
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        rings = rings_of_feature(feat)
        if not rings:
            continue
        props = feat.get("properties")
        if not isinstance(props, dict):
            continue
        tunnus = props.get("tunnus")
        if not isinstance(tunnus, str) or not tunnus:
            continue
        omvorm = props.get("omvorm")
        siht1 = props.get("siht1")
        pindala = props.get("pindala")
        aadress = props.get("l_aadress")
        rows.append({
            "tunnus": tunnus,
            "cls": classify(omvorm),
            "omvorm": omvorm if isinstance(omvorm, str) else "teadmata",
            "siht1": siht1 if isinstance(siht1, str) else "teadmata",
            "pindala": pindala if isinstance(pindala, (int, float)) else None,
            "aadress": aadress if isinstance(aadress, str) else "teadmata",
            "kkis": (sum(1 for fr in kkis_feat_rings
                          if any(touches(ring, fr) for ring in rings))
                     if kkis_doc is not None else None),
            "b": bbox_lonlat(rings),
            "r": [[[x, y] for x, y in ring] for ring in rings],
        })
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    """Rebuild command (only writer; tests use build_sidecar directly)."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parcels", required=True,
                    help="cached kataster:ky_kehtiv GeoJSON pull")
    ap.add_argument("--kkis", default=None,
                    help="cached kma_avalik_asjaoigus GeoJSON pull (optional)")
    ap.add_argument("--snap", required=True, help="snapshot dir to write to")
    args = ap.parse_args(argv)
    with open(args.parcels, encoding="utf-8") as fh:
        parcels_doc = json.load(fh)
    kkis_doc = None
    if args.kkis:
        with open(args.kkis, encoding="utf-8") as fh:
            kkis_doc = json.load(fh)
    rows = build_sidecar(parcels_doc, kkis_doc)
    out = os.path.join(args.snap, SIDECAR_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    payload = {
        "provenance": ("Maa-amet WFS kataster:ky_kehtiv proovivalim "
                       "(Kesklinn 24.74-24.76/59.428-59.438), seisuga %s; "
                       "KKIS-puute arv jame puute-liide (issue #491)"
                       % HARVEST_DATE),
        "bbox": SAMPLE_BBOX,
        "harvest_date": HARVEST_DATE,
        "parcels": rows,
    }
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    print("wrote %d parcels -> %s" % (len(rows), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
