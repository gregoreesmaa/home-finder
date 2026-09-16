"""Keskkonnaagentuur seirejaamad harvest + build (issue #610).

Polite single-fetch harvest of the keyless PostgREST station register
(f_seirejaamad, outdoor-air programme slice) and an offline build of
the Tallinn station-point extract the ohuseire map overlay serves.
Stdlib only; network lives ONLY in fetch_cached/main.

Feed verdict (2026-09-16, see services/scoring/dims_p4_ohuseire.py and
docs/p4_ohuseire.md; aggregates only, raw bodies never committed):
PostgREST 12.0.1, 302 tables, keyless; air-programme slice
(sr_programm_nimi ilike valisohu) is a handful of rows including
"Tallinn Rahu" (Harju maakond, Tallinn, Pohja-Tallinna linnaosa,
Kasutusel, kesk 540568/6590159). Station coords are L-EST97 metres,
projected offline via the labelled inverse-LCC below (same math as
batch_tervise.py, PROJ-agreement <0.01 m on live stations pinned in
the scorer docs). Only Kasutusel rows whose own admin label names
Tallinn and whose converted coords fall in the Tallinn bbox place;
Peatatud/coordless/other-programme rows are COUNTED (n_skipped),
never silently dropped and never scored.

Thinness (load-bearing, maintainer decision): ~3 stations in/near
Harjumaa — the layer ships thin as-is (honest 2 km district bands, NO
interpolation, NO raster master). The map kernel is the flat district
band (nearest station within 2 km -> 60); the scorer's 2+ -> 70 lives
scorer-side only (stated on the legend + here, never hidden). DIY
sensor.community stations stay untouched (dims_p4_senscom.py is never
re-scored here). Station names ride the legend (count + names) and
the sidecar (join key for future exposure legs, never personal data).
Licence: open register (keskkonnaandmed, no key) — attribution rides
the legend + docs/p4_ohuseire.md.
"""

import json
import os
import sys
import time
import urllib.request
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_p4_ohuseire import (OHUSEIRE_STATIONS_PATH, TALLINN_BBOX,
                              lest_to_wgs84, parse_ohuseire_dump,
                              tallinn_extract)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Station register root (verified 2026-09-16: keyless PostgREST 12.0.1).
OHUSEIRE_BASE_URL = "https://keskkonnaandmed.envir.ee"

#: Air-programme slice query (small payload, tens of rows). The õ in
#: *õhu* is load-bearing: plain *ohu* also matches "ohustatud"
#: (threatened plant communities — 360 wrong-programme rows, zero air
#: stations; caught live 2026-09-16, never shipped).
OHUSEIRE_QUERY = (OHUSEIRE_STATIONS_PATH
                  + "?sr_programm_nimi=ilike.*%C3%B5hu*&limit=1000&select="
                  + "nimi,kesk_x,kesk_y,seisund,sr_programm_nimi,"
                  + "ehak_tekst,keht_staatus,kkr_kood")

#: Station inventory moves on installation timescales: 7 d TTL.
OHUSEIRE_TTL_S = 7 * 24 * 3600

#: Identifying user agent for the polite pull (paced single GETs, no scrape).
OHUSEIRE_UA = (
    "home-finder-610-ohuseire/1.0 "
    "(polite weekly harvest, paced single GETs; "
    "GitHub gregoreesmaa/home-finder issue 610)"
)

#: Seconds between harvest GETs (polite pacing on top of the TTL).
OHUSEIRE_PACE_S = 3

#: Minimum plausible body: the 10-row probe was 2 775 bytes — anything
#: smaller is an error page, never data.
DUMP_MIN_BYTES = 1_000

#: Vintage stamped on the extract (harvest date, re-verified per pull).
OHUSEIRE_VINTAGE = "2026-09-16"

#: Default cache dir (raw bulk lives here; /tmp only, AGENTS.md 5).
DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-610-ohuseire")


def fetch_cached(url: str, cache_dir: str, filename: str,
                 min_bytes: int,
                 ttl_s: int = OHUSEIRE_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with OHUSEIRE_UA and a 60 s timeout; the body is stored only
    on HTTP 200 with at least min_bytes bytes, else None is returned and
    nothing is cached (transport errors are never data). No retries —
    HTTP 429/errors are a stop signal. Scorers never call this; tests
    cover the pure build, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": OHUSEIRE_UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status != 200:
                return None
            body = resp.read()
    except Exception:
        return None
    if len(body) < min_bytes:
        return None
    try:
        with open(dest, "wb") as f:
            f.write(body)
    except OSError:
        return None
    return dest


# ---------------------------------------------------------------------------
# Pure offline build (hermetic, pinned by test_batch_ohuseire.py).
# ---------------------------------------------------------------------------

def build_sidecar(dump_text: str, out_dir: str) -> dict:
    """Build ohuseire/ohuseire-points.json from the register dump."""
    import json as _json
    try:
        fetched = len(_json.loads(dump_text))
    except ValueError:
        fetched = 0
    rows = parse_ohuseire_dump(dump_text)
    extract = tallinn_extract(rows, dict(TALLINN_BBOX),
                              fetched=OHUSEIRE_VINTAGE)
    stations = extract["stations"]
    points = [{"lat": s["lat"], "lon": s["lon"], "name": s["name"]}
              for s in stations]
    doc = {
        "vintage": OHUSEIRE_VINTAGE,
        "licence": "keskkonnaandmed.envir.ee avaandmed (Keskkonnaagentuur, keyless PostgREST)",
        "accuracy": ("L-EST97 (EPSG:3301) inverse-LCC pooramine, "
                     "PROJ-kokkulepe <0.01 m (docs/p4_ohuseire.md)"),
        "counts": {"stations": len(points), "total": len(points)},
        "dropped": {"fetched_rows": fetched,
                    "parsed_rows": len(rows),
                    "skipped": extract["n_skipped"]},
        "points": points,
    }
    ohu_dir = os.path.join(out_dir, "ohuseire")
    os.makedirs(ohu_dir, exist_ok=True)
    with open(os.path.join(ohu_dir, "ohuseire-points.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return doc


def main(cache_dir: str = DEFAULT_CACHE_DIR,
         out_dir: Optional[str] = None) -> int:
    """Harvest the register slice (polite, TTL-guarded) and build."""
    dump_path = fetch_cached(OHUSEIRE_BASE_URL + OHUSEIRE_QUERY, cache_dir,
                             "seirejaamad.json", DUMP_MIN_BYTES)
    if dump_path is None:
        print("ohuseire harvest incomplete (transport refused or thin "
              "body); no sidecar written")
        return 1
    with open(dump_path, encoding="utf-8") as f:
        dump_text = f.read()
    doc = build_sidecar(dump_text,
                        out_dir or os.path.join(cache_dir, "snapshot"))
    print("ohuseire extract: %d stations %s (vintage %s)" % (
        doc["counts"]["total"], doc["counts"], doc["vintage"]))
    print("dropped: %s" % (doc["dropped"],))
    print("stations: %s" % ([p["name"] for p in doc["points"]],))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
