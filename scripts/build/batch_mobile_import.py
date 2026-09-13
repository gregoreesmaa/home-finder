"""One-time import of OpenCellID Estonia cells into the snapshot.

Source: OpenCellID country export (CC-BY-SA 4.0, Unwired Labs —
attribution in the layer source + docs/layers.md; ShareAlike noted
for redistributors). Daily exports, cells observed in the last 18
months. Download needs a free API token (local use only, NEVER
committed — export OPENCELLID_TOKEN or pass --token-file):
  curl -o /tmp/ocid248.csv.gz "https://opencellid.org/ocid/downloads?token=$TOK&type=mcc&file=248.csv.gz"
MCC 248 = Estonia. One 130 KB file, polite by design (fair-use cap is
2 downloads/day/file — this script runs once, cached forever).

What lands in the snapshot: LTE cells only (mobile broadband —
GSM is voice-era, UMTS 42 cells is sunset spectrum, NR 0 mapped).
MNC mapping (Estonian allocation): 1=Telia, 2=Elisa, 3=Tele2.
Crowdsourced positions are antenna-estimates with metre-scale jitter,
so the map layer is a DENSITY proxy (half/sigma calibrated), never a
per-address signal claim. Absence = no crowdsourced cell (includes
under-mapping — the legend must say so).

Usage:
  python3 scripts/build/batch_mobile_import.py --csv /tmp/ocid248.csv.gz \\
      --snap ~/hf-data/2026-09-12
Writes <snap>/osm/derived-mobile.json: [{lon, lat, tags:{radio,operaator}}].
"""

import argparse
import csv
import gzip
import json
import os

# Estonian MNC allocation (documented judgment call — verify against
# future exports if shares shift).
OPERATORS = {"1": "Telia", "2": "Elisa", "3": "Tele2"}

# Radios scoring as mobile broadband (NR would join when mapped).
BROADBAND_RADIOS = {"LTE"}


MIN_SAMPLES = 3  # fewer fixes = unreliable footprint, dropped


def parse_row(row):
    """OpenCellID CSV row -> point dict or None (junk skipped).

    Columns: radio,mcc,net,area,cell,unit,lon,lat,range,samples,...
    What we keep is the MEASUREMENT: range = how far from the centroid
    this cell was still heard (its observed footprint radius, metres),
    samples = how many fixes support it. The centroid itself is NOT the
    tower — the dots on the map are measurement sites, never masts.
    """
    if len(row) < 10:
        return None
    radio, mcc, net = row[0].strip(), row[1].strip(), row[2].strip()
    if mcc != "248" or radio not in BROADBAND_RADIOS:
        return None
    try:
        lon, lat = float(row[6]), float(row[7])
        arange, samples = float(row[8]), int(row[9])
    except ValueError:
        return None
    if arange <= 0 or samples < MIN_SAMPLES:
        return None
    if not (23.0 <= lon <= 25.8 and 58.2 <= lat <= 59.8):
        return None
    return {"lon": round(lon, 6), "lat": round(lat, 6),
            "tags": {"radio": radio,
                     "operaator": OPERATORS.get(net, "teadmata"),
                     "ulatus_m": str(int(arange))}}


def import_csv(path):
    """Dedupe (lon, lat, radio, operator) cells from a .csv.gz export."""
    opener = gzip.open if path.endswith(".gz") else open
    seen, out = set(), []
    with opener(path, "rt", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            p = parse_row(row)
            if not p:
                continue
            key = (p["lon"], p["lat"], p["tags"]["radio"],
                   p["tags"]["operaator"])
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--snap", required=True)
    args = ap.parse_args()
    pts = import_csv(args.csv)
    out = os.path.join(args.snap, "osm", "derived-mobile.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pts, f)
    print("wrote %d LTE cells -> %s" % (len(pts), out))


if __name__ == "__main__":
    main()
