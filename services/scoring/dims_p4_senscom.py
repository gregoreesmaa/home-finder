"""P4 sensor.community DIY-air demo dim (issue #306, single param).

Params (this module only — the sensor.community SLICE of the param;
sibling slices are owned elsewhere and untouched):
* P4-031 Backyard weather + DIY air: the "sensor.community DIY
  outdoor-location density (frost/wind pockets)" slice (source (1),
  batch 3, demo in #306). Disjoint from dims_p4_ilm.dim_backyard_weather,
  which owns the Ilmateenistus Tallinn-Harku city-baseline slice
  (documented NULL pointing AT the sensor-density check), from
  dims_p4_ehr.dim_backyard_weather, which owns the EHR heating-type
  echo slice (NULL + kütte-liik echo), from
  dims_p4_maa_lidar.dim_backyard_weather, which owns the LiDAR DEM
  cold-air-drainage slice, from dims_p4_kaur.dim_mikrokliima_kaur,
  which owns the KAUR met/wind-station density slice, and from the
  OSM slice (documented NULL: bus shelters are not balcony facts).
  This module owns ONLY the DIY sensor-density leg; reasons
  cross-reference the sibling legs instead of re-scoring them.

OPENNESS VERDICT (checked 2026-09-13, POSITIVE — no dated
negative): the sensor.community live feed is machine-open, no key,
no auth, CORS `*`. Polite evidence, 6 requests total with a
labelled one-off user-agent, paced >=3 s, short timeouts, raw
bodies cached at /tmp/hf-senscom/ (one-off PR record, never
committed):
* HEAD .../static/v2/data.json -> HTTP/2 200,
  `content-type: application/json`, `content-length: 8610582`,
  `last-modified: Sun, 13 Sep 2026 15:15:29 GMT`,
  `accept-ranges: bytes`, `access-control-allow-origin: *`.
* Bounded range-read bytes 0-8191 of the same feed -> HTTP 206,
  a JSON array of observation records with `location{latitude,
  longitude, country, indoor}`, `sensor{sensor_type{name}}`,
  `sensordatavalues[]`, `timestamp` (first records: PPD42NS +
  DHT22 in DE).
* HEAD https://archive.sensor.community/ -> HTTP/2 200 (daily
  per-sensor CSV archive reachable; the demo ingests the live
  feed, the archive is the re-pull/history anchor).
* GET https://sensor.community/ -> HTTP 200, 45-byte JS stub
  (`window.location.href = "/en"`); GET .../en/ -> HTTP 200,
  29 791 bytes, links `creativecommons.org/publicdomain/zero/1.0`
  (CC0) and calls the network "open data, civic tech network".
* One full GET of the live feed (8 609 312 bytes, 9.8 s) proves
  Tallinn coverage live: 17 866 records in a ~5-minute rolling
  window (15:11:06 -> 15:16:15 UTC), 5 EE records at 3 distinct
  OUTDOOR locations — Tallinn bbox loc 23610 (59.38, 24.642;
  SDS011 + DS18B20), Viljandi loc 46248 (BME280 + SDS011),
  Rapla loc 86012 (PMS5003). Full probe record in docs/p4_senscom.md.
Verdict: POSITIVE. Live DIY outdoor locations ARE a local
backyard signal (unlike the single Harku station), so the honest
shape is a coarse density hinnang per the issue — never a
calibrated measurement, never a heating-truth score.

HONESTY (AGENTS.md section 7.2): uncalibrated citizen sensors say
which blocks have local witnesses, not what a balcony measures —
and they say nothing about heating truth (EHR kütte liik stays
unjoined). Numbers enter sorts while reasons do not, so every
scored band is capped at 80 (never 100 on DIY proxy alone) and
every scored reason names the sensor count, the radius, the
snapshot date, and the missing pieces (Harku city baseline, EHR
heating truth, LiDAR DEM frost screen), without ever claiming a
measurement. Only distinct OUTDOOR locations count (deduped by
location id — three boards on one balcony are one witness, not
three; indoor boards measure living rooms, never backyards, and
locations with an unknown indoor flag are ignored fail-closed).
A thin network is unknown, never good: 0 locations in radius, no
snapshot, or no origin all stay NULL with an Estonian reason
saying "hinnang" and "EI OLE" plus the concrete buyer-side check
(sensor.community map, on-site shade/wind). Machine-checkable
invariant kept by the tests: "EI OLE" appears ONLY in documented
no-map NULL reasons, never in scored-proxy reasons (same
precedent as dims_p4_osm / dims_p4_ookla).

Style mirrors services/scoring/dims_p4_ookla.py (#268, the
closest ingestion precedent: fetch + parse + bbox extract travel
explicitly, scorers take an optional snapshot) and
dims_p4_osm.py (#280, the closest scored-proxy precedent: capped
bands, coverage gaps read as gaps): scorers are pure and
offline-tested — (origin, pois, senscom=None) ->
(Optional[int 0..100], Estonian reason). The optional third
argument IS the demoed ingestion product (the Tallinn-extract
snapshot), so the param is wired to the demoed ingestion with
fixture proof. Network lives only in fetch_senscom_dump (single
polite GET, file cache, TTL); tests never call it. The module is
stdlib-only (json + urllib, no new dependency).

Helpers are local copies (not imported from livability or
sibling batches): a future central hook may import this module
alongside them, and importing any of them here would turn that
into a cycle (same precedent as batch B3, PR #100, and
sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* SENSCOM_RADIUS_M = 500 m: frost pockets and wind tunnels are
  sub-block facts — a DIY sensor 2 km away says nothing about
  the backyard (tighter than the KAUR 2 km met/wind window on
  purpose: reference stations interpolate, balconies do not).
* Density bands (1 location -> 60, 2-3 -> 70, 4+ -> 80, cap 80):
  one uncalibrated witness is weak evidence the block breathes
  watched air; four-plus is a watched block, still never above
  80 without calibration or heating truth. Challengeable, dull
  by design.
* Indoor filter is fail-closed: only an explicit outdoor marker
  (`indoor` 0/False) counts. Indoor boards and unknown-flag
  locations are ignored, never scored as absence.
* SENSCOM_TTL_S = 24 h follows the repo cron cadence (AGENTS.md
  section 5: adapters poll daily), not the feed's ~5-minute
  refresh: sensor DENSITY moves on installation timescales, so
  at most one live pull per day; the snapshot date travels in
  the extract and is echoed in every scored reason.
* Test fixtures are fully synthetic (clearly labelled) and model
  only the observed 2026-09-13 field names — real observed
  values appear only in docs/p4_senscom.md section 1, never as
  ingested data (same fixture precedent as dims_p4_ilm).
* `exact_location` rounding is consumed as-is: rounded coords
  make the 500 m join noisier, never a gradient claim — the
  reason reports the count and the nearest distance, not a
  metre-precise exposure.

Integration (deliberately NOT done here): feeding this dim with
the ingested snapshot inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling. No shared files
touched: 3 new files only. Never touch dims_p4_ilm.py (the
Harku-baseline P4-031 leg) or any dims_group*.py.
"""

import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated live-feed pulls.
# ---------------------------------------------------------------------------

#: Machine-open live feed (verified 2026-09-13: HTTP 200, ~8.6 MB,
#: application/json, no key, CORS *). A ~5-minute rolling window of
#: observation records — the demo ingests it, the daily cron re-pulls it.
SENSCOM_DATA_URL = "https://data.sensor.community/static/v2/data.json"

#: Daily per-sensor CSV archive index (verified 2026-09-13: HTTP 200) —
#: history/re-pull anchor, never pulled by the demo.
SENSCOM_ARCHIVE_INDEX_URL = "https://archive.sensor.community/"

#: At most one live pull per day (density moves on installation
#: timescales; AGENTS.md section 5 daily-cron cadence).
SENSCOM_TTL_S = 24 * 3600
SENSCOM_CACHE_NAME = "sensor-community-data.json"
SENSCOM_SNAPSHOT_NAME = "sensor-community-tallinn.json"

#: Backyard join radius in metres (sub-block facts — see judgment calls).
SENSCOM_RADIUS_M = 500.0

#: Generous Tallinn bbox for the extract step (city + Viimsi /
#: Maardu fringe; the join is nearest-location, never an
#: admin-boundary claim). Same bbox precedent as dims_p4_ookla.
TALLINN_BBOX = {"lon_min": 24.3, "lon_max": 25.1,
                "lat_min": 59.3, "lat_max": 59.6}

USER_AGENT = ("home-finder-p4-senscom/1.0 (Estonia open-data daily adapter; "
              "polite single-pull, cache-first)")


def _cache_path(cache_dir: str) -> str:
    """Single live-feed cache file (flat dir, no subdirs)."""
    return os.path.join(cache_dir, SENSCOM_CACHE_NAME)


def snapshot_cache_path(cache_dir: str) -> str:
    """Small Tallinn-extract JSON produced by the operator step."""
    return os.path.join(cache_dir, SENSCOM_SNAPSHOT_NAME)


def cache_is_fresh(path: str, ttl_s: int = SENSCOM_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def fetch_senscom_dump(cache_dir: Optional[str] = None,
                       ttl_s: int = SENSCOM_TTL_S) -> Tuple[str, str]:
    """Fetch the live feed politely (cached, TTL).

    Cache-first single GET with a polite User-Agent and a 60 s
    timeout (~8.6 MB observed). Transport errors RAISE (never
    cached as data, AGENTS.md section 7.2); an error body is never
    written to the cache. Treat HTTP 429 as a stop signal: it
    propagates, the stale cache is left untouched. Returns (raw
    text, provenance) with provenance "cache" or "live" — callers
    parse + bbox-filter the text into a Tallinn snapshot.
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-senscom")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if cache_is_fresh(path, ttl_s):
        with open(path, encoding="utf-8") as fh:
            return fh.read(), "cache"
    req = urllib.request.Request(SENSCOM_DATA_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        body = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body, "live"


# ---------------------------------------------------------------------------
# Tallinn extract: canonical outdoor sensor-location rows.
# ---------------------------------------------------------------------------

def _to_float(raw: object) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(str(raw).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _is_outdoor(location: dict) -> bool:
    """True only for an explicit outdoor marker (fail-closed).

    Indoor boards measure living rooms, never backyards; an
    unknown/missing flag is ignored rather than guessed as
    outdoor — missing data must shrink the witness count toward
    NULL, never inflate it.
    """
    return location.get("indoor") in (0, False)


def parse_senscom_dump(text: str) -> List[dict]:
    """Parse one data.json payload into deduped OUTDOOR locations (pure).

    One location id = one witness no matter how many boards it
    carries (three boards on one balcony are one balcony, not
    three). Rows without a location, without parseable in-range
    coords, or without an explicit outdoor flag are skipped —
    keeping them would fake network coverage (same join-key
    precedent as ookla coerce_tile skipping centroid-less rows).
    Raises ValueError on unparseable JSON or a non-list payload
    (transport garbage is never a location list).
    """
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ValueError("sensor.community JSON ei parsinud: %s" % exc)
    if not isinstance(payload, list):
        raise ValueError("sensor.community vastus pole loend")
    by_id: Dict[object, dict] = {}
    for rec in payload:
        if not isinstance(rec, dict):
            continue
        loc = rec.get("location")
        if not isinstance(loc, dict):
            continue
        if not _is_outdoor(loc):
            continue
        lat = _to_float(loc.get("latitude"))
        lon = _to_float(loc.get("longitude"))
        if lat is None or lon is None:
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            continue
        stype = ((rec.get("sensor") or {}).get("sensor_type") or {}).get("name")
        key = loc.get("id")
        if key is None:
            key = (lat, lon)  # id-less rows dedup by rounded coords
        entry = by_id.setdefault(
            key, {"id": key, "lat": lat, "lon": lon, "types": []})
        if isinstance(stype, str) and stype and stype not in entry["types"]:
            entry["types"].append(stype)
    return [by_id[k] for k in sorted(by_id, key=repr)]


def tallinn_extract(records: List[dict], bbox: Optional[dict] = None,
                    fetched: Optional[str] = None) -> Dict[str, object]:
    """Build the snapshot the dim consumes from parsed locations.

    Keeps every outdoor location inside the bbox (thin network
    included — the scorer applies the radius join and the NULL
    contract, so the snapshot stays a faithful extract, never a
    pre-scored selection). The fetch date travels in the extract
    and is echoed in every scored reason.
    """
    box = dict(bbox or TALLINN_BBOX)
    sensors = [r for r in (records or [])
               if isinstance(r, dict)
               and isinstance(r.get("lat"), (int, float))
               and isinstance(r.get("lon"), (int, float))
               and box["lat_min"] <= float(r["lat"]) <= box["lat_max"]
               and box["lon_min"] <= float(r["lon"]) <= box["lon_max"]]
    if fetched is None:
        fetched = time.strftime("%Y-%m-%d", time.gmtime())
    return {"fetched": fetched, "bbox": box,
            "sensors": sensors, "n_sensors": len(sensors)}


def load_senscom_snapshot(cache_dir: str) -> Optional[dict]:
    """Load a cached Tallinn-extract JSON, or None when absent/unreadable.

    A missing or corrupt extract is never data (same envelope
    precedent as ookla load_ookla_snapshot) — the dim reports the
    gap with a NULL reason instead.
    """
    path = snapshot_cache_path(cache_dir)
    try:
        with open(path, encoding="utf-8") as fh:
            snapshot = json.load(fh)
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


def _band_density(n: int) -> int:
    """Coarse witness-count band (capped — DIY proxy never earns 100)."""
    if n <= 1:
        return 60
    if n <= 3:
        return 70
    return 80


def _nearby(origin: Tuple[float, float],
            sensors: List[dict]) -> List[Tuple[dict, float]]:
    """Outdoor locations within the backyard radius, nearest first (pure).

    No averaging, no smoothing — the band counts watched
    backyards near the address (same no-smoothing precedent as
    ookla _nearest_tile: smoothing would fake a gradient between
    measured points).
    """
    out: List[Tuple[dict, float]] = []
    for sensor in sensors:
        if not isinstance(sensor, dict):
            continue
        lat = sensor.get("lat")
        lon = sensor.get("lon")
        if isinstance(lat, bool) or not isinstance(lat, (int, float)):
            continue
        if isinstance(lon, bool) or not isinstance(lon, (int, float)):
            continue
        dist = _haversine_m(origin, float(lat), float(lon))
        if dist <= SENSCOM_RADIUS_M:
            out.append((sensor, dist))
    out.sort(key=lambda pair: pair[1])
    return out


# ---------------------------------------------------------------------------
# P4-031 sensor.community slice: coarse DIY-density hinnang.
# ---------------------------------------------------------------------------

def _null_no_origin() -> Score:
    return None, ("Hooviõhu DIY-hinnang eeldab aadressi koordinaate "
                  "(EI OLE hinnangut ilma asukohata): lähimaid "
                  "välisandureid saab siduda vaid teada aadressiga — "
                  "kontrolli sensor.community kaardilt anduritihedust ja "
                  "hoovi varju/tuult kohapeal, ära feigi")


def _null_no_snapshot() -> Score:
    return None, ("sensor.community Tallinna väljavõtet pole vahemällu "
                  "tõmmatud (EI OLE hinnangut): ööpäevane tõmme puudub — "
                  "hoovi mikrokliima (külmakotid, tuulekoridorid) selgub "
                  "sensor.community kaardi anduritihedusest ja kohapealsest "
                  "kontrollist, ära feigi tühjast vahemälust skoori")


def _null_empty(fetched: object) -> Score:
    return None, ("sensor.community Tallinna väljavõte on tühi (%s, EI OLE "
                  "hinnangut): ühtegi välisandurit Tallinnas kirjas pole — "
                  "võimalik võrgu hõrenemine või filtrimisviga — kontrolli "
                  "sensor.community kaardilt ja hoovi kohapeal, ära feigi"
                  % (fetched if isinstance(fetched, str) else "teadmata"))


def _null_no_sensor(fetched: object) -> Score:
    return None, ("%.0f m raadiuses EI OLE ühtegi sensor.community "
                  "DIY-välisandurit (EI OLE hinnangut; väljavõte %s): "
                  "lähim võrguandur on hoovifaktist kaugemal — külmakotid "
                  "ja tuulekoridorid selguvad kohapealsest varju/tuule "
                  "kontrollist ja sensor.community kaardilt, ära feigi "
                  "tühjast võrgust skoori"
                  % (SENSCOM_RADIUS_M,
                     fetched if isinstance(fetched, str) else "teadmata"))


def dim_backyard_air(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]] = None,
                     senscom: Optional[dict] = None) -> Score:
    """P4-031 sensor.community slice: coarse DIY-density hinnang, capped.

    Counts distinct OUTDOOR DIY locations within 500 m of the
    address (1 -> 60, 2-3 -> 70, 4+ -> 80). Thin or missing
    network stays NULL — an unwatched block is unknown, never
    good. `pois` is accepted for the uniform scorer shape and
    ignored (DIY sensors are not OSM POIs).
    """
    _ = pois
    if origin is None:
        return _null_no_origin()
    sensors = senscom.get("sensors") if isinstance(senscom, dict) else None
    if sensors is None:
        return _null_no_snapshot()
    fetched = senscom.get("fetched") if isinstance(senscom, dict) else None
    if not sensors:
        return _null_empty(fetched)
    nearby = _nearby(origin, sensors)
    if not nearby:
        return _null_no_sensor(fetched)
    n = len(nearby)
    score = _band_density(n)
    nearest, dist = nearby[0]
    types = nearest.get("types") if isinstance(nearest, dict) else None
    type_s = ", ".join(t for t in types if isinstance(t, str)) if types else "tüüp teadmata"
    return score, ("Hooviõhu DIY-hinnang %d/100: sensor.community "
                   "välisandureid %d tk %.0f m raadiuses (lähim ~%.0f m, %s; "
                   "väljavõte %s) — see on kalibreerimata rahvaandurite "
                   "tihedushinnang, mitte hoovi mõõtmine: Harku linnabaas "
                   "(dims_p4_ilm), EHR kütte liik ega DEM-külmanõo sõel "
                   "(LiDAR) pole selles hinnangus — külmakotid ja "
                   "tuulekoridorid kontrolli kohapeal, ära feigi tihedusest "
                   "garantiid"
                   % (score, n, SENSCOM_RADIUS_M, dist, type_s,
                      fetched if isinstance(fetched, str) else "teadmata"))


P4_SENSCOM_DIMS = (
    ("backyard_air_senscom", "P4-031", dim_backyard_air),
)

#: Param-number wiring for the central weight-rebalance follow-up.
P4_SENSCOM_PARAM_IDS = {
    "backyard_air_senscom": 31,
}


def score_p4_senscom(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]] = None,
                     senscom: Optional[dict] = None
                     ) -> Dict[str, Optional[int]]:
    """The P4 sensor.community dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_SENSCOM_DIMS). The value
    is a capped density-hinnang band when the Tallinn extract
    covers the address, else None by design — never a faked
    per-backyard measurement."""
    return {key: fn(origin, pois, senscom)[0] for key, _, fn in P4_SENSCOM_DIMS}
