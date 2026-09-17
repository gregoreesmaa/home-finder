"""Density 1 km choropleth sidecar builder (issue #622): INSPIRE PD WFS -> areas.

Stdlib only (json). Offline, snapshot-only (NO network): the INSPIRE PD
WFS harvest is a polite one-off (custom UA, single GetCapabilities +
single DescribeFeatureType + ONE Harjumaa bbox GetFeature; 429 stops
the run — see docs/p4_density.md); this builder converts the cached
GeoJSON into the map sidecar ``<snap>/density/density-areas.json``
consumed by /api/layers/density/areas. Pure logic at module top so
unit tests stay hermetic; the sidecar write runs only via the
documented rebuild command.

SCOPE: population-density CHARACTER choropleth, never a score field —
urban buzz vs quiet is taste, not good/bad. Classes are OUR bins over
the publisher's inhabitants count (stated in the legend, never
scores): 0 (empty OR privacy-masked <4 — honestly one class, never
"empty") / 1-9 / 10-99 / 100-999 / 1000-4999 / 5000+. Squares are
painted EXACTLY (1 km cells are the field, edges included — never
interpolated, never smoothed).

HONESTY (load-bearing): vintage rides everywhere (2024 people != 2026
people). Outside every square is NULL (never rural — unmapped is not
uninhabited). A missing input writes NOTHING (unknown, never
partial); per-file counts are stamped in stats.

Rebuild: python3 scripts/build/batch_density.py \\
    --json /tmp/hf-622-cache/harju-pd.json --snap ~/hf-data/2026-09-12
"""

import argparse
import json
import os
import sys
from collections import Counter
from typing import Dict, List, Optional, Tuple

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("density", "density-areas.json")

#: Publisher attribution (CC0 — still attributed; stamped in stats).
ATTRIBUTION = "Maa- ja Ruumiamet INSPIRE PD 1x1 km (CC0, Statistikaamet)"

#: Reference period of the harvested series (verified live 2026-09-17).
VINTAGE = "2024"

#: Our inhabitant bins (index = class). Stated as ours in the legend.
CLASS_NAMES = ["0", "1-9", "10-99", "100-999", "1000-4999", "5000+"]


def density_class(value: Optional[float]) -> int:
    """Bin an inhabitants count into a choropleth class 0-5.

    0 covers BOTH empty and privacy-masked (<4) squares: the feed does
    not distinguish them, so neither do we (never "empty").
    Unparseable values are -1 (dropped + counted by the caller).
    """
    if value is None:
        return -1
    try:
        v = float(value)
    except (TypeError, ValueError):
        return -1
    if v != v or v == float("inf") or v == float("-inf"):
        return -1
    if v <= 0:
        return 0
    if v < 10:
        return 1
    if v < 100:
        return 2
    if v < 1000:
        return 3
    if v < 5000:
        return 4
    return 5


def square_record(feature: Dict) -> Optional[Dict]:
    """One sidecar row from a WFS feature, or None (dropped + counted).

    Keeps zone_id + inhabitants + class + prefilter box + the single
    quad ring (rounded to 5 decimals ~1 m — 1 km squares need no more).
    """
    try:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        zone_id = props.get("inspireid_identifier_localid")
        cls = density_class(props.get("value_statisticalvalue_value"))
        ring = geom.get("coordinates", [[]])[0]
        if not isinstance(zone_id, str) or cls < 0:
            return None
        if geom.get("type") != "Polygon" or len(ring) < 4:
            return None
        pts = [[round(float(x), 5), round(float(y), 5)] for x, y in ring]
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        value = int(float(props["value_statisticalvalue_value"]))
        return {
            "zone_id": zone_id,
            "value": value,
            "cls": cls,
            "b": [min(lons), min(lats), max(lons), max(lats)],
            "r": [pts],
        }
    except (TypeError, ValueError, IndexError, KeyError, AttributeError):
        return None


def build_sidecar(rows: List[Dict], stats: Dict) -> Dict:
    """Assemble the sidecar doc (JSON-serializable)."""
    return {
        "vintage": VINTAGE,
        "source": ATTRIBUTION,
        "unit": "inhabitants per 1 km square",
        "classes": ["0 (tühi/varjatud)", "1-9", "10-99", "100-999", "1000-4999", "5000+"],
        "bins": "our bins over inhabitants (never scores)",
        "stats": stats,
        "areas": rows,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the density areas sidecar.")
    ap.add_argument("--json", required=True, help="Cached Harjumaa PD GetFeature GeoJSON.")
    ap.add_argument("--snap", required=True, help="Snapshot dir.")
    args = ap.parse_args(argv)
    if not os.path.exists(args.json):
        print("missing input %s: wrote NOTHING (unknown, never partial)" % args.json)
        return 1
    try:
        with open(args.json, encoding="utf-8") as fh:
            doc = json.load(fh)
        features = doc.get("features", [])
        assert isinstance(features, list)
    except (ValueError, OSError, AssertionError, AttributeError) as exc:
        print("unreadable input %s (%s): wrote NOTHING" % (args.json, exc))
        return 1
    rows: List[Dict] = []
    dropped = 0
    band_counts = Counter()
    for f in features:
        row = square_record(f if isinstance(f, dict) else {})
        if row is None:
            dropped += 1
            continue
        rows.append(row)
        band_counts[row["cls"]] += 1
    stats = {
        "squares": len(rows),
        "dropped": dropped,
        "bands": [band_counts[i] for i in range(6)],
        "vintage": VINTAGE,
    }
    dest = os.path.join(args.snap, SIDECAR_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(build_sidecar(rows, stats), fh)
    print(
        "ok=True %s squares=%d dropped=%d bands=%s"
        % (dest, len(rows), dropped, stats["bands"])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
