"""P4 Ookla Speedtest Open Data fallback dims (issue #268, single param).

Params (this module only — the Ookla SLICE of the param; sibling
slices are owned elsewhere and untouched):
* P4-009 Power/internet reliability at address: the Ookla
  "Speedtest Open Data Tallinn tiles (fallback)" slice (source (5),
  batch 1, demo in #268). Disjoint from
  dims_p4_elektrilevi.dim_power_reliability, which owns the
  Elektrilevi feeder-SAIDI slice (NULL: unpublished DSO feed), from
  dims_p4_elering.dim_system_adequacy, which owns the Elering
  national-series slice (NULL: national aggregate, no feeder
  signal), and from the TTJA netikaart / operator-map / OpenCellID
  broadband slices (their own demos #266/#267/#230-masters, not
  this source).

OPENNESS VERDICT (checked 2026-09-13, POSITIVE — no dated
negative): the Ookla fixed/mobile z16 tiles are machine-open, no
key, no auth. Polite evidence, 9 tiny requests total with a
labelled one-off user-agent, headers + visible-text scope reads
plus two bounded analytical range-reads only (no bulk download —
the global quarterly parquets are 167–349 MB; the demo never
pulls them whole), raw bodies cached at /tmp/hf-ookla/ (one-off
PR record, never committed):
* https://www.ookla.com/ookla-for-good/open-data -> HTTP 200,
  119826 bytes, "Global Fixed Broadband and Mobile Network Maps"
  + "Download this data" in visible text — the open-data landing
  is reachable and names both layers.
* https://raw.githubusercontent.com/teamookla/ookla-open-data/master/README.md
  -> HTTP 200, 14893 bytes — the dataset README documents: z16
  tiles (~610.8 m at the equator), quarterly aggregates from Q1
  2019 through the most recently completed quarter (Q1 2026),
  Shapefile + Parquet (WKT, EPSG:4326), GPS-quality Speedtest
  samples averaged per tile, no-sign-request S3 layout
  s3://ookla-open-data/{shapefiles,parquet}/performance/type={fixed,mobile}/
  year=YYYY/quarter=Q/, plus the centroid-filter tutorial. License:
  CC BY-NC-SA 4.0 with a suggested attribution string (kept in
  docs/p4_ookla.md; this non-commercial repo reuses a handful of
  attributed sample rows as test fixtures only).
* HEAD .../parquet/performance/type=fixed/year=2026/quarter=1/2026-01-01_performance_fixed_tiles.parquet
  -> HTTP 200, Content-Length 348853499, Last-Modified
  2026-04-13 — MACHINE-OPEN, no key (headers only, no body).
* HEAD .../type=mobile/.../2026-01-01_performance_mobile_tiles.parquet
  -> HTTP 200, Content-Length 175330099, Last-Modified
  2026-04-13 — MACHINE-OPEN, no key (headers only, no body).
* Bounded DuckDB range-reads over the two Q1-2026 parquets
  (httpfs, predicate pushdown on tile_x/tile_y — column chunks
  only, files never downloaded whole): Tallinn bbox
  lon 24.3–25.1 / lat 59.3–59.6 holds 1914 fixed tiles (23465
  tests, 8536 devices; download p25/med/p75 = 92624/154425/
  220187 kbps, median upload 117012 kbps, median latency 5 ms)
  and 1706 mobile tiles (9084 tests, 4906 devices; download
  p25/med/p75 = 94047/220138/381664 kbps, median upload 26276
  kbps, median latency 15 ms). Dense Kesklinn tiles carry
  36–151 tests each. Tallinn coverage for 2026-Q1 is therefore
  PROVEN live — this is the fallback layer the param needs.
Verdict: POSITIVE. The per-tile download averages ARE a local
signal (unlike Elering's national series), so the honest shape
is a coarse raster hinnang per the issue — never a per-address
measurement.

HONESTY (AGENTS.md section 7.2): a ~0.6 km quarterly tile says
which speed band an address sits in, not what the flat's
contract delivers — and it says nothing about power cuts
(Elektrilevi SAIDI stays unpublished). Numbers enter sorts
while reasons do not, so every scored band is capped at 85
(never 100 on tile proxy alone) and every scored reason names
the tile distance, the quarter, the test/device counts, and
the missing pieces (per-address measurement, feeder outage
history, TTJA address check). NULL stays NULL with an
Estonian reason saying "hinnang" and "EI OLE": no snapshot
cached, no qualifying tile within 1 km, or no origin to join.
Machine-checkable invariant kept by the tests: "EI OLE"
appears ONLY in documented no-map NULL reasons, never in
scored-proxy reasons (same precedent as dims_p4_osm).

Style mirrors services/scoring/dims_p4_elering.py (#265, the
closest ingestion precedent: fetch + parse + summarize travel
explicitly, scorers take an optional snapshot) and
dims_p4_osm.py (#280, the closest scored-proxy precedent:
capped bands, coverage gaps read as gaps): scorers are pure
and offline-tested — (origin, pois, ookla=None) ->
(Optional[int 0..100], Estonian reason). The optional third
argument IS the demoed ingestion product (the Tallinn-extract
snapshot), so the param is wired to the demoed ingestion with
fixture proof. Network lives only in fetch_ookla_parquet
(single polite GET per layer per quarter, file cache, TTL);
tests never call it. Parquet parsing needs no new dependency:
fetch caches the quarterly file, the documented DuckDB
one-liner filters the Tallinn bbox into a small JSON extract,
and this module loads/summarizes/scores that JSON with stdlib
only.

Helpers are local copies (not imported from livability or
sibling batches): a future central hook may import this module
alongside them, and importing any of them here would turn that
into a cycle (same precedent as batch B3, PR #100, and
sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Fixed + mobile share ONE module because #268 names both
  layers as one source ("Ookla fixed/mobile tiles") for a
  single param — splitting would re-verify the same bucket
  twice (same demo+coverage precedent as comapps #302+#371,
  but here both dims are scored, not NULL).
* Band edges (30/100/300 Mbit/s -> 35/55/75/85) come from EU
  broadband tiers (30 = fast-broadband line, 100 = ultrafast)
  checked against the live Tallinn Q1-2026 quartiles (fixed
  p25/med/p75 = 93/154/220 Mbit/s): most of Tallinn lands at
  75, weak spots at 55/35, the top tail at capped 85. Same
  edges for both layers — both are experienced download
  kbps, and one mapping stays reviewable.
* OOKLA_MIN_TESTS = 5: a quarterly tile with fewer than 5
  GPS-quality tests is a household anecdote, not a band
  signal; such tiles are ignored (never averaged in).
* Nearest qualifying tile wins within OOKLA_RADIUS_M = 1000 m
  of the tile centroid; tiles are NOT averaged or smoothed —
  smoothing would fake a gradient between measured squares.
* OOKLA_TTL_DAYS = 90 follows the source cadence (quarterly
  releases), not parameters4.md's "monthly": a monthly
  re-pull would re-fetch identical bytes. The compliant
  middle ground is documented in docs/p4_ookla.md (monthly
  HEAD freshness check, quarterly GET).
* Test fixtures mix 8 real observed Tallinn rows (bounded
  2026-09-13 range-read, attributed per CC BY-NC-SA — see
  docs/p4_ookla.md) with synthetic edge rows (weak band,
  thin tile, far tile). Real rows pin the live shape;
  synthetic rows pin the edges no live row covers.
* The power half of P4-009 is NOT scored here even though
  the param covers it: Ookla measures throughput, not
  outages. The reasons point at the rikkekaart live map for
  cuts — scoring throughput as reliability would claim the
  full param on a partial signal (same split-slice precedent
  as P4-020: ATA notices in dims_p4_ata, bureau scores NULL
  in dims_p4_creditinfo).

Integration (deliberately NOT done here): feeding these dims
with the ingested snapshot inside livability scoring and
rebalancing livability.WEIGHTS must be one joint change
across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break
every sibling.
"""

import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated quarterly tile pulls.
# ---------------------------------------------------------------------------

#: Public S3 website endpoint for the open-data bucket (no key needed).
OOKLA_S3_BASE = "https://ookla-open-data.s3.amazonaws.com"

#: Latest completed quarter per the dataset README (checked
#: 2026-09-13). Rolls quarterly — ookla_url() builds any
#: quarter, so a new release needs no code change.
OOKLA_LATEST_YEAR = 2026
OOKLA_LATEST_QUARTER = 1
OOKLA_LATEST_LABEL = "2026-Q1"

#: Quarterly re-pull per the source cadence (see judgment calls:
#: parameters4.md P4-009 says monthly, the source releases
#: quarterly — TTL follows the source).
OOKLA_TTL_DAYS = 90

#: Nearest-tile join radius in metres (tile pitch is ~0.6 km).
OOKLA_RADIUS_M = 1000.0

#: Tiles with fewer quarterly tests are anecdotes, not bands.
OOKLA_MIN_TESTS = 5

#: Generous Tallinn bbox for the extract step (city + Viimsi /
#: Maardu fringe; hex assignment is nearest-tile, never an
#: admin-boundary claim). Documented in docs/p4_ookla.md.
TALLINN_BBOX = {"lon_min": 24.3, "lon_max": 25.1,
                "lat_min": 59.3, "lat_max": 59.6}

USER_AGENT = ("home-finder ookla ingest (polite quarterly pull, single GET "
              "per layer, file cache; contact via GitHub home-finder)")

_QUARTER_START = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}


def ookla_url(service: str, year: int, quarter: int) -> str:
    """HTTPS URL of one quarterly global tile file (documented S3 layout).

    Raises ValueError on an unknown layer / out-of-range quarter /
    pre-2019 year instead of building a URL that 404s.
    """
    if service not in ("fixed", "mobile"):
        raise ValueError("service must be 'fixed' or 'mobile': %r" % (service,))
    if quarter not in _QUARTER_START:
        raise ValueError("quarter must be 1..4: %r" % (quarter,))
    if year < 2019:
        raise ValueError("Ookla tiles start at Q1 2019: %r" % (year,))
    day = "%d-%s" % (year, _QUARTER_START[quarter])
    return ("%s/parquet/performance/type=%s/year=%d/quarter=%d/"
            "%s_performance_%s_tiles.parquet"
            % (OOKLA_S3_BASE, service, year, quarter, day, service))


def quarter_label(year: int, quarter: int) -> str:
    """Short 'YYYY-QN' label as echoed in scored reasons."""
    return "%d-Q%d" % (year, quarter)


def _cache_path(cache_dir: str, service: str, year: int, quarter: int) -> str:
    """Single quarterly-layer cache file (flat dir, no subdirs)."""
    return os.path.join(cache_dir, "ookla-%s-%dQ%d.parquet"
                        % (service, year, quarter))


def snapshot_cache_path(cache_dir: str, year: int, quarter: int) -> str:
    """Small Tallinn-extract JSON produced by the documented DuckDB step."""
    return os.path.join(cache_dir, "ookla-tallinn-%dQ%d.json"
                        % (year, quarter))


def cache_is_fresh(path: str, ttl_days: int = OOKLA_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_ookla_parquet(service: str, year: int, quarter: int,
                        cache_dir: str = "/tmp/hf-ookla",
                        ttl_days: int = OOKLA_TTL_DAYS) -> str:
    """Fetch one quarterly global tile file politely (cached, TTL).

    Cache-first single GET with a polite User-Agent and a 300 s
    timeout (the fixed file is ~349 MB). Transport errors RAISE
    (never cached as data, AGENTS.md section 7.2); HTTP errors
    raise too — an error body is never written to the cache.
    Treat HTTP 429 as a stop signal: it propagates, the stale
    cache is left untouched. Returns the cache path (never the
    bytes — callers filter the Tallinn bbox out of the file).
    """
    url = ookla_url(service, year, quarter)  # validates first
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, service, year, quarter)
    if cache_is_fresh(path, ttl_days):
        return path
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        with open(path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    return path


# ---------------------------------------------------------------------------
# Tallinn extract: canonical tile rows (whatever tool filtered the bbox —
# the documented DuckDB one-liner lives in docs/p4_ookla.md).
# ---------------------------------------------------------------------------

#: Canonical tile keys produced by coerce_tile (speeds/tests stay
#: None when the source carries no value — never guessed as 0).
OOKLA_TILE_FIELDS = (
    "tile_x",
    "tile_y",
    "avg_d_kbps",
    "avg_u_kbps",
    "avg_lat_ms",
    "tests",
    "devices",
    "quadkey",
)


def _to_float(raw: object) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_int(raw: object) -> Optional[int]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def coerce_tile(row: object) -> Optional[Dict[str, Optional[float]]]:
    """Coerce one raw tile row into canonical shape, or None to skip.

    Rows without a usable centroid (the join key) are skipped —
    keeping them would fake bbox coverage (same join-key
    precedent as kudocs parse_kudocs skipping ku_code-less
    rows). Speed/test fields may stay None: a tile whose
    download average is missing parses but never scores.
    """
    if not isinstance(row, dict):
        return None
    lon = _to_float(row.get("tile_x"))
    lat = _to_float(row.get("tile_y"))
    if lon is None or lat is None:
        return None
    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
        return None
    tile = {"tile_x": lon, "tile_y": lat}  # type: Dict[str, Optional[float]]
    for key in ("avg_d_kbps", "avg_u_kbps", "avg_lat_ms", "tests", "devices"):
        tile[key] = _to_int(row.get(key))
    quadkey = row.get("quadkey")
    tile["quadkey"] = quadkey if isinstance(quadkey, str) else None
    return tile


def summarize_ookla_tallinn(fixed_rows: List[dict], mobile_rows: List[dict],
                            year: int, quarter: int) -> Dict[str, object]:
    """Build the snapshot the dims consume from filtered tile rows.

    Skips uncoercible rows; keeps every coercible tile (thin and
    speed-less tiles included — the scorers apply MIN_TESTS and
    the avg_d guard, so the snapshot stays a faithful extract,
    never a pre-scored selection).
    """
    fixed = [t for t in (coerce_tile(r) for r in fixed_rows) if t is not None]
    mobile = [t for t in (coerce_tile(r) for r in mobile_rows) if t is not None]
    return {
        "quarter": quarter_label(year, quarter),
        "fixed": fixed,
        "mobile": mobile,
        "n_fixed": len(fixed),
        "n_mobile": len(mobile),
    }


def load_ookla_snapshot(cache_dir: str, year: int,
                        quarter: int) -> Optional[dict]:
    """Load a cached Tallinn-extract JSON, or None when absent/unreadable.

    A missing or corrupt extract is never data (same envelope
    precedent as elering parse: error bodies parse to nothing) —
    the dims report the gap with a NULL reason instead.
    """
    import json

    path = snapshot_cache_path(cache_dir, year, quarter)
    try:
        with open(path, encoding="utf-8") as f:
            snapshot = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return snapshot if isinstance(snapshot, dict) else None


# ---------------------------------------------------------------------------
# Small input helpers (local copies — no sibling imports, see docstring).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


#: Coarse download-band mapping (avg_d_kbps -> score). Edges from EU
#: broadband tiers checked against live Tallinn Q1-2026 quartiles
#: (fixed p25/med/p75 = 93/154/220 Mbit/s); capped at 85 — a tile
#: proxy never earns 100 (same cap precedent as dims_p4_osm).
_SPEED_BANDS = ((30000, 35), (100000, 55), (300000, 75))


def _band_d(avg_d_kbps: int) -> int:
    """First band score covering the download average, else the cap."""
    for limit, pts in _SPEED_BANDS:
        if avg_d_kbps < limit:
            return pts
    return 85


def _tiles(snapshot: object, layer: str) -> Optional[list]:
    if not isinstance(snapshot, dict):
        return None
    tiles = snapshot.get(layer)
    return tiles if isinstance(tiles, list) else None


def _nearest_tile(origin: Tuple[float, float],
                  tiles: List[dict]) -> Optional[Tuple[dict, float]]:
    """Nearest tile meeting MIN_TESTS with a download average, or None.

    No averaging, no smoothing — the band comes from one measured
    square (see judgment calls).
    """
    best: Optional[Tuple[dict, float]] = None
    for tile in tiles:
        if not isinstance(tile, dict):
            continue
        lat = tile.get("tile_y")
        lon = tile.get("tile_x")
        avg_d = tile.get("avg_d_kbps")
        tests = tile.get("tests")
        if not isinstance(lat, (int, float)) or isinstance(lat, bool):
            continue
        if not isinstance(lon, (int, float)) or isinstance(lon, bool):
            continue
        if not isinstance(avg_d, (int, float)) or isinstance(avg_d, bool):
            continue
        if not isinstance(tests, (int, float)) or isinstance(tests, bool):
            continue
        if tests < OOKLA_MIN_TESTS:
            continue
        dist = _haversine_m(origin, float(lat), float(lon))
        if dist > OOKLA_RADIUS_M:
            continue
        if best is None or dist < best[1]:
            best = (tile, dist)
    return best


def _fmt_mbps(kbps: object) -> str:
    if isinstance(kbps, bool):
        return str(kbps)
    if isinstance(kbps, (int, float)):
        return "%d" % round(kbps / 1000.0)
    return str(kbps)


def _fmt_km(m: float) -> str:
    return ("%.1f" % (m / 1000.0)).replace(".", ",")


def _fmt_n(n: object) -> str:
    if isinstance(n, bool):
        return str(n)
    if isinstance(n, (int, float)):
        return "%d" % n
    return "teadmata"


# ---------------------------------------------------------------------------
# P4-009 Ookla slice: coarse raster hinnang per layer (fixed + mobile).
# ---------------------------------------------------------------------------

def _null_no_origin(layer_ee: str) -> Score:
    return None, ("Ookla %s kiirusehinnang eeldab aadressi koordinaate "
                  "(EI OLE hinnangut ilma asukohata): lähima ~0,6 km "
                  "kvartaliruudu saab siduda vaid teada aadressiga — "
                  "kontrolli aadressi püsiühendust TTJA netikaardilt ja "
                  "jooksvaid katkestusi rikkekaardilt, ära feigi"
                  % layer_ee)


def _null_no_snapshot(layer_ee: str) -> Score:
    return None, ("Ookla %s Tallinna väljavõtet pole vahemällu tõmmatud "
                  "(EI OLE hinnangut): kvartali %s parquet pole selles "
                  "kvartalis alla laetud ega Tallinna ruudustikku "
                  "filtreeritud — kontrolli aadressi püsiühendust TTJA "
                  "netikaardilt ja jooksvaid katkestusi rikkekaardilt, "
                  "ära feigi tühjast vahemälust skoori"
                  % (layer_ee, OOKLA_LATEST_LABEL))


def _null_empty_layer(layer_ee: str, quarter: object) -> Score:
    return None, ("Ookla %s Tallinna väljavõte on tühi (%s kvartal, "
                  "EI OLE hinnangut): selles kvartali väljavõttes pole "
                  "ühtegi Tallinna ruutu — võimalik piirkondade "
                  "kärbe (Ookla 2026-04-16 muudatuslogi) või "
                  "filtrimisviga — kontrolli aadressi püsiühendust "
                  "TTJA netikaardilt ja jooksvaid katkestusi "
                  "rikkekaardilt, ära feigi" % (layer_ee, quarter))


def _null_no_tile(layer_ee: str, quarter: object) -> Score:
    return None, ("Ookla %s lähiruut 1 km raadiuses puudub (%s kvartal, "
                  "EI OLE hinnangut): aadress jääb Ookla ~0,6 km "
                  "ruudustikust välja või on lähiruudud liiga õhukesed "
                  "(alla %d testi kvartalis) — kontrolli aadressi "
                  "püsiühendust TTJA netikaardilt ja jooksvaid "
                  "katkestusi rikkekaardilt, ära feigi katmata ala "
                  "skoori" % (layer_ee, quarter, OOKLA_MIN_TESTS))


def _score_layer(origin: Tuple[float, float], layer: str, layer_ee: str,
                 ookla: Optional[dict]) -> Score:
    tiles = _tiles(ookla, layer)
    if tiles is None:
        return _null_no_snapshot(layer_ee)
    quarter = ookla.get("quarter") if isinstance(ookla, dict) else None
    quarter_s = quarter if isinstance(quarter, str) else OOKLA_LATEST_LABEL
    if not tiles:
        return _null_empty_layer(layer_ee, quarter_s)
    found = _nearest_tile(origin, tiles)
    if found is None:
        return _null_no_tile(layer_ee, quarter_s)
    tile, dist = found
    score = _band_d(int(tile["avg_d_kbps"]))
    up = tile.get("avg_u_kbps")
    lat_ms = tile.get("avg_lat_ms")
    extra = ""
    if isinstance(up, (int, float)) and not isinstance(up, bool):
        extra += " / üles %s Mbit/s" % _fmt_mbps(up)
    if isinstance(lat_ms, (int, float)) and not isinstance(lat_ms, bool):
        extra += ", viide %s ms" % _fmt_n(lat_ms)
    return score, ("Ookla %s kiirusehinnang %d/100 (%s kvartali koond, "
                   "lähim z16-ruut ~%s km, keskmine allalaadimine %s Mbit/s%s, "
                   "%s testi, %s seadet): see on ~0,6 km ruudu hinnang, mitte "
                   "aadressi mõõtmine — elektrikatkestuste ajalugu fiidri "
                   "kohta avalikus voogus puudub, kontrolli jooksvaid "
                   "katkestusi rikkekaardilt ja aadressi püsiühendust TTJA "
                   "netikaardilt, ära feigi ruudust aadressi garantiid"
                   % (layer_ee, score, quarter_s, _fmt_km(dist),
                      _fmt_mbps(tile["avg_d_kbps"]), extra,
                      _fmt_n(tile.get("tests")), _fmt_n(tile.get("devices"))))


def dim_ookla_fixed(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]],
                    ookla: Optional[dict] = None) -> Score:
    """P4-009 Ookla slice (fixed): coarse raster hinnang, capped at 85."""
    if origin is None:
        return _null_no_origin("fiksinterneti")
    return _score_layer(origin, "fixed", "fiksinterneti", ookla)


def dim_ookla_mobile(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]],
                     ookla: Optional[dict] = None) -> Score:
    """P4-009 Ookla slice (mobile): coarse raster hinnang, capped at 85."""
    if origin is None:
        return _null_no_origin("mobiili")
    return _score_layer(origin, "mobile", "mobiili", ookla)


P4_OOKLA_DIMS = (
    ("ookla_fixed", "P4-009", dim_ookla_fixed),
    ("ookla_mobile", "P4-009", dim_ookla_mobile),
)


def score_p4_ookla(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]],
                   ookla: Optional[dict] = None
                   ) -> Dict[str, Optional[int]]:
    """Both P4 Ookla dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_OOKLA_DIMS). Values
    are capped raster-hinnang bands when the Tallinn extract
    covers the address, else None by design — never a faked
    per-address measurement."""
    return {key: fn(origin, pois, ookla)[0] for key, _, fn in P4_OOKLA_DIMS}
