"""Keyed TomTom flow-speed harvester (issue #671).

Runs ONLY on a user-supplied env key (TOMTOM_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test).

ToS step-zero verdict (docs/p4_tomtom_matrix.md section 0, repeated in
docs/p4_tomtom_flow.md section 0): SHORT-TERM CACHE ONLY (TomTom
Portal Terms 11.4 + 11.6). No sidecars are committed and no tables are
stored: --pull fills a git-ignored operator cache dir (TTL-capped,
cache-control max-age honored), --build reads that cache (or fixture
files) and prints counts + calibration stats to stdout.

Delegates the pull to services/scoring/dims_tomtom_flow.fetch_flow
(quota cap FLOW_MAX_CALLS = 80 per 1 d window = ~40 probes x 2 bands,
429 = stop, transport never cached), so quota/TTL semantics agree with
the scorer by construction.

Usage:
  TOMTOM_API_KEY=... python3 scripts/build/batch_tomtom_flow.py \\
      --pull --build --band morning --cache-dir DIR
Key placement: export the variable in the operator shell only (see
docs/p4_tomtom_flow.md section 7); never commit it, never put it in
repo files.
"""

import argparse
import glob
import json
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_tomtom_flow import (  # noqa: E402
    FLOW_BANDS,
    FLOW_MAX_CALLS,
    FLOW_TTL_S,
    TOMTOM_KEY_ENV,
    _quota_used,
    build_table,
    calibrate_vs_delay,
    fetch_flow,
    parse_flow_response,
)

#: Static arterial probe list (approximate public road midpoints;
#: the operator extends/refines to ~40 via --probes-file - probe
#: coordinates are public facts, never TomTom Results, so committing
#: them is ToS-clean).
DEFAULT_PROBES = (
    {"probe_id": "parnu-mnt", "lat": 59.4200, "lon": 24.7300},
    {"probe_id": "tartu-mnt", "lat": 59.4280, "lon": 24.7800},
    {"probe_id": "narva-mnt", "lat": 59.4420, "lon": 24.7850},
    {"probe_id": "pirita-tee", "lat": 59.4550, "lon": 24.8100},
    {"probe_id": "paldiski-mnt", "lat": 59.4350, "lon": 24.6900},
    {"probe_id": "mustamae-tee", "lat": 59.4100, "lon": 24.7000},
    {"probe_id": "sopruse-pst", "lat": 59.4150, "lon": 24.7150},
    {"probe_id": "liivalaia", "lat": 59.4300, "lon": 24.7600},
    {"probe_id": "jarvevana-tee", "lat": 59.4050, "lon": 24.7650},
    {"probe_id": "peterburi-tee", "lat": 59.4250, "lon": 24.8300},
)


def _load_probes(path: Optional[str]) -> List[dict]:
    if not path:
        return list(DEFAULT_PROBES)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    probes = data.get("probes", data) if isinstance(data, dict) else data
    out = []
    for p in probes:
        if not isinstance(p, dict):
            continue
        try:
            out.append({"probe_id": p.get("probe_id", p.get("id")),
                        "lat": float(p["lat"]), "lon": float(p["lon"])})
        except (TypeError, ValueError, KeyError):
            continue
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed TomTom flow pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--band", default="morning", choices=list(FLOW_BANDS))
    ap.add_argument("--probes-file", default=None)
    ap.add_argument("--delay-file", default=None,
                    help="Bus-delay corridor factors JSON for calibration.")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--fixture-dir", default=None,
                    help="Fixture flow JSONs for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if not os.environ.get(TOMTOM_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TomTom võti selles terminalis (vt "
              "docs/p4_tomtom_flow.md §7); midagi ei päritud, midagi "
              "ei kirjutatud." % TOMTOM_KEY_ENV, file=sys.stderr)
        return 2

    probes = _load_probes(args.probes_file)
    if args.pull:
        expected = ["tomtom_flow_%s_%s.json" % (p["probe_id"], args.band)
                    for p in probes]
        try:
            if expected and all(
                    os.path.exists(os.path.join(args.cache_dir, f))
                    and time.time() - os.path.getmtime(
                        os.path.join(args.cache_dir, f)) < FLOW_TTL_S
                    for f in expected):
                print("ok: värske puhver, uusi päringuid ei tehtud (%s)"
                      % args.cache_dir)
                if not args.build:
                    return 0
                args.pull = False
        except OSError:
            pass
    if args.pull and _quota_used(args.cache_dir) >= FLOW_MAX_CALLS:
        print("error: keeldun - TomTom Flow kvoot on täis (80 "
              "päringut / ööpäevas); midagi ei päritud.",
              file=sys.stderr)
        return 2
    if args.pull:
        if not probes:
            print("error: sondipunktide loend on tühi; midagi ei "
                  "päritud.", file=sys.stderr)
            return 1
        pulled = 0
        for p in probes:
            dest = fetch_flow(p["lat"], p["lon"], args.cache_dir,
                              "tomtom_flow_%s_%s.json"
                              % (p["probe_id"], args.band))
            if dest is not None:
                pulled += 1
        if pulled == 0:
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver, täis kvoot või transport/429) - midagi uut "
                  "ei puhvritatud.", file=sys.stderr)
            return 1
        print("ok: %d Flow-päringut puhvritatud (%s)" % (pulled,
                                                        args.cache_dir))
    if args.build:
        rows: List[dict] = []
        paths = (sorted(glob.glob(os.path.join(args.fixture_dir, "*.json")))
                 if args.fixture_dir else
                 [os.path.join(args.cache_dir,
                               "tomtom_flow_%s_%s.json" % (p["probe_id"],
                                                           args.band))
                  for p in probes])
        for p in paths:
            if not os.path.exists(p):
                continue
            sample = parse_flow_response(p)
            pid = os.path.basename(p).replace("tomtom_flow_", "")
            pid = pid.rsplit("_", 1)[0].rsplit(".", 1)[0] \
                if "_" in pid else pid.rsplit(".", 1)[0]
            rows.append({"probe_id": pid, "band": args.band,
                         "current": sample["current"],
                         "freeflow": sample["freeflow"]})
        table = build_table(rows)
        out = {"counts": table["counts"]}
        if args.delay_file:
            with open(args.delay_file, encoding="utf-8") as fh:
                delay = json.load(fh)
            factors = delay.get("factors", delay) \
                if isinstance(delay, dict) else {}
            out["calibration"] = calibrate_vs_delay(
                table["rows"], factors if isinstance(factors, dict) else {})
            out["calibration"].pop("details", None)
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
