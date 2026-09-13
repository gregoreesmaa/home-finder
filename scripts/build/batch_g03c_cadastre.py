"""Group 3 cadastre-C evidence probe (issue #153): p254/p256/p258/p273/p277.

Stdlib only. Offline, snapshot-only (NO network): this builder builds
NO raster — all five params are documented no-map (see
apps/web/lib/layers_group03c.ts), so there is no field to master. What
it does instead is REPLAY the verdict evidence from LOCAL snapshot
extracts, so a reviewer can re-derive GROUP03C_EVIDENCE without
trusting the author's shell history. Pure logic + snapshot readers
live at module top so unit tests stay hermetic.

HONESTY (load-bearing): per-wetland protection status (EELIS register),
soil pH (ESDAC/SoilGrids) and unregistered burdens (invisible by
definition) are NOT in the 2026-09-12 snapshot — this script can only
recount what OSM mapped (springs, wells, wetlands, reserves, shores)
and confirm the soil file carries zero soil attributes. It never
emits scores, layers or rasters.

Replay (needs the snapshot dir, NOT committed):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/natural=spring -o /tmp/hf-c-spring.pbf --overwrite
  osmium export /tmp/hf-c-spring.pbf -o /tmp/hf-c-spring.geojsonseq
  # ... same for man_made=water_well, natural=wetland,
  #     leisure=nature_reserve, boundary=protected_area ...
  python3 scripts/build/batch_g03c_cadastre.py \\
      --stat springsTagged=/tmp/hf-c-spring.geojsonseq \\
      --stat wetlandsTagged=/tmp/hf-c-wetland.geojsonseq \\
      --soil ~/hf-data/2026-09-12/osm/derived-soil.geojson
  # verify the TS registry still matches the locked evidence:
  python3 scripts/build/batch_g03c_cadastre.py --check-ts \\
      apps/web/lib/layers_group03c.ts
Outputs: evidence JSON on stdout (counts a map builder would consume).
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Locked evidence (mirrors apps/web/lib/layers_group03c.ts GROUP03C_EVIDENCE
# exactly — scripts/build/test_batch_g03c.py parses that file and fails on
# drift). Numbers are tagged-feature counts from `osmium tags-filter nwr/
# <expr>` + `osmium export` on harjumaa-260911.osm.pbf, 2026-09-12.
# ---------------------------------------------------------------------------

LOCKED_EVIDENCE = {
    "springsTagged": 43,
    "springsPoints": 35,
    "wellsTagged": 30,
    "wellsPoints": 28,
    "wetlandsTagged": 1264,
    "wetlandsPoly": 667,
    "wetlandsLine": 637,
    "reservesLeisureTagged": 137,
    "reservesLeisurePoly": 32,
    "protectedAreaTagged": 167,
    "protectedAreaPoly": 51,
    "soilFileFeatures": 53,
    "soilFileSoilAttrs": 0,
}

#: Geometry-bucket names used by summarize_features.
GEOM_BUCKETS = ("Point", "LineString", "MultiPolygon")

#: OSM tag keys that would count as soil evidence (ESDAC/SoilGrids-style).
#: derived-soil.geojson carries none of these (verified: barrier/gate
#: junk only) — any hit flips the p258 verdict input, never the verdict.
SOIL_KEYS = frozenset({
    "soil", "soil:ph", "ph", "soil:texture", "texture", "clay", "sand",
    "silt", "peat", "organic", "soilgrids", "esdac", "soil:type",
})

#: Tag keys proving a feature is a mapped OSM object (vs an untagged
#: relation member the export carries along).
MAPPED_KEYS = ("natural", "waterway", "man_made", "leisure", "boundary")


def summarize_features(features):
    """Count tagged/untagged features + geometry split (pure).

    `features` is a list of GeoJSON Feature dicts (or (props, geomtype)
    pairs — the CLI normalises exports into these). Tagged = carries at
    least one MAPPED_KEYS property. Untagged members are reported, never
    silently folded into the verdict counts.
    """
    out = {"tagged": 0, "untagged": 0, "by_geom": {g: 0 for g in GEOM_BUCKETS},
           "by_geom_other": 0}
    for ft in features:
        if isinstance(ft, (list, tuple)):
            props, geomtype = ft
        else:
            props = (ft.get("properties") or {})
            geomtype = ((ft.get("geometry") or {}).get("type"))
        if any(k in props for k in MAPPED_KEYS):
            out["tagged"] += 1
        else:
            out["untagged"] += 1
        if geomtype in out["by_geom"]:
            out["by_geom"][geomtype] += 1
        else:
            out["by_geom_other"] += 1
    return out


def has_soil_attrs(props):
    """True when a properties dict carries any soil-evidence key (pure)."""
    return any(str(k).lower() in SOIL_KEYS for k in (props or {}))


def iter_export_features(path):
    """Yield GeoJSON features from a LOCAL export file (pure reader).

    Accepts RS-delimited geojsonseq (osmium export default) and plain
    .geojson FeatureCollections. Snapshot-local only — no network.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    features = []
    for line in text.splitlines():
        line = line.lstrip("\x1e").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "FeatureCollection":
            features.extend(obj.get("features") or [])
        elif obj.get("type") == "Feature":
            features.append(obj)
    return features


def summarize_soil_file(path):
    """Count soil-file features + soil-attribute hits (pure reader)."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc["features"] if isinstance(doc, dict) else doc
    hits = sum(1 for ft in feats
               if has_soil_attrs((ft.get("properties") or {})))
    return {"features": len(feats), "soil_attrs": hits}


def check_ts_registry(ts_path):
    """Compare GROUP03C_EVIDENCE in the TS registry vs LOCKED_EVIDENCE.

    Returns a list of "key: ts!=locked" mismatch strings (empty = in
    sync). Keeps the web verdict file and this probe honest with each
    other without sharing code across the language boundary.
    """
    with open(ts_path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"GROUP03C_EVIDENCE\s*=\s*\{(.*?)\}\s*as const",
                  text, re.S)
    if not m:
        return ["GROUP03C_EVIDENCE block not found"]
    found = dict(re.findall(r"(\w+):\s*(\d+)", m.group(1)))
    bad = []
    for key, locked in LOCKED_EVIDENCE.items():
        if found.get(key) != str(locked):
            bad.append("%s: ts=%s locked=%s"
                       % (key, found.get(key), locked))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stat", action="append", default=[],
                    metavar="NAME=PATH",
                    help="local export file to summarise (repeatable)")
    ap.add_argument("--soil", default=None, metavar="PATH",
                    help="local derived-soil.geojson to audit")
    ap.add_argument("--check-ts", default=None, metavar="PATH",
                    help="verify the TS registry matches LOCKED_EVIDENCE")
    args = ap.parse_args(argv)
    report = {}
    for item in args.stat:
        name, _, path = item.partition("=")
        if not name or not path or not os.path.isfile(path):
            print("bad --stat %r (want NAME=local-file)" % item,
                  file=sys.stderr)
            return 2
        report[name] = summarize_features(iter_export_features(path))
    if args.soil:
        if not os.path.isfile(args.soil):
            print("soil file not found: %s" % args.soil, file=sys.stderr)
            return 2
        report["soil"] = summarize_soil_file(args.soil)
    if args.check_ts:
        bad = check_ts_registry(args.check_ts)
        report["ts_drift"] = bad
        if bad:
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
