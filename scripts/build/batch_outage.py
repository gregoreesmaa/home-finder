"""Live-outage harvester (issue #729): GetApplicationData -> sidecar.

Pole/operator pull ONLY (5-min cadence per the issue; live data goes
stale in minutes — never CI, never unit tests). The repo holds this
code plus hermetic tests; the sidecar lives in cache//tmp and on the
pole as ``built/outage/table.json`` (served at ``GET /v1/outage``,
honest 503 until the first pull).

SOURCE (verified 2026-09-19, UA ``home-finder-research/0.1``,
``--max-time`` 30, 429 = stop): keyless
``geoserver-api/GetApplicationData`` -> 200, ~130 KB double-encoded
JSON ``scopes.p.{areas,dynareas,outages}``. Field semantics pinned
from ``geoserver-api/content/configuration.js`` (see
services/scoring/dims_p4_outage.py + docs/p4_outage.md §1):
fc/fcc = active faults + affected customers, pc/pcc = active
planned, uc/ucc = upcoming planned.

Usage:
  python3 scripts/build/batch_outage.py --pull --cache-dir DIR \
      --out sidecar.json
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

#: Live JSON endpoint (keyless, verified 2026-09-19).
OUTAGE_URL = ("https://rikkekaart.elektrilevi.ee/"
              "geoserver-api/GetApplicationData")

#: Freshness ceiling in seconds (live data, issue constraint).
TTL_S = 300

#: Identifying user agent for the polite pull.
OUTAGE_UA = ("home-finder outage ingest (polite 5-min pulls, single GET, "
             "file cache; contact via GitHub home-finder)")

#: Double-encoded envelope keys (outer JSON string -> scopes.p.*).
ENVELOPE_TABLES = ("areas", "dynareas", "outages")


def decode_application_data(body: str) -> Optional[Dict[str, Any]]:
    """Parse the double-encoded GetApplicationData body (pure).

    Returns ``{"areas": [...], "dynareas": [...], "outages": [...]}``
    with list tables, or None when the envelope is missing or
    malformed (transport garbage is never a record).
    """
    try:
        outer = json.loads(body)
    except ValueError:
        return None
    if isinstance(outer, str):
        try:
            outer = json.loads(outer)
        except ValueError:
            return None
    if not isinstance(outer, dict):
        return None
    scopes = outer.get("scopes")
    if not isinstance(scopes, dict):
        return None
    inner = scopes.get("p")
    if not isinstance(inner, dict):
        return None
    out: Dict[str, Any] = {}
    for table in ENVELOPE_TABLES:
        rows = inner.get(table)
        out[table] = [r for r in rows if isinstance(r, dict)] \
            if isinstance(rows, list) else []
    return out


def build_sidecar(decoded: Dict[str, Any],
                  now: Optional[datetime] = None) -> Dict[str, Any]:
    """Decoded tables -> timestamped sidecar (pure).

    Keeps every area row verbatim (dims pick Tallinn/Harju — no
    pre-scored selection) plus outage-type tallies for the doc
    record. Raises ValueError on a table-less payload.
    """
    if not isinstance(decoded, dict) or not decoded.get("areas"):
        raise ValueError("tühjendatud väljavõte (areas-tabel puudub)")
    at = now or datetime.now(tz=timezone.utc)
    tallies: Dict[str, int] = {}
    for row in decoded.get("outages", []):
        t = row.get("t")
        if isinstance(t, str):
            tallies[t] = tallies.get(t, 0) + 1
    return {
        "pulled_at": at.isoformat(),
        "ttl_s": TTL_S,
        "source": OUTAGE_URL,
        "areas": decoded["areas"],
        "n_dynareas": len(decoded.get("dynareas", [])),
        "outage_tallies": tallies,
    }


def fetch_application_data(cache_dir: str, timeout_s: int = 30) -> str:
    """Single polite GET of the live JSON (never cached as data on error).

    Transport errors RAISE (never written as data); HTTP 429 raises
    immediately (stop signal, no retry). Returns the raw body text
    (callers decode + timestamp it — the cache file is the sidecar,
    rewritten on every pull).
    """
    req = urllib.request.Request(OUTAGE_URL,
                                 headers={"User-Agent": OUTAGE_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", 200)
            if status == 429:
                raise RuntimeError("HTTP 429 — stop, do not retry: "
                                   + OUTAGE_URL)
            if status != 200:
                raise RuntimeError("HTTP %s: %s" % (status, OUTAGE_URL))
            raw = resp.read()
    except Exception:
        raise
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("vastus ei ole UTF-8: %s" % exc)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: --pull fetches live and writes the sidecar. Returns exit code."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pull", action="store_true",
                    help="fetch GetApplicationData and write the sidecar")
    ap.add_argument("--cache-dir", default="/tmp/hf-outage")
    ap.add_argument("--out", default=None,
                    help="sidecar path (default <cache-dir>/outage-table.json)")
    args = ap.parse_args(argv)
    if not args.pull:
        print("error: keeldun - elavat tõmmet pole (--pull puudub): "
              "hetkeseisu ei ehitata vahemälust, ainult päris "
              "GetApplicationData päringust.", file=sys.stderr)
        return 2
    try:
        body = fetch_application_data(args.cache_dir)
        decoded = decode_application_data(body)
        if decoded is None:
            print("vastuse kest ei parsinud (EI OLE kirjet)", file=sys.stderr)
            return 1
        sidecar = build_sidecar(decoded)
    except Exception as exc:  # transport/HTTP errors stay errors
        print("tõmme ebaõnnestus: %s" % exc, file=sys.stderr)
        return 1
    out = args.out or os.path.join(args.cache_dir, "outage-table.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh, ensure_ascii=False)
    os.replace(tmp, out)
    print("wrote %d areas -> %s" % (len(sidecar["areas"]), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
