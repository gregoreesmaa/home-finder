"""P4 official-air adapter: Keskkonnaagentuur seirejaamad register (issue #524).

Buyer report: the courtyard-air (hooviohk) layer reads empty. Verified
2026-09-16: the sensor.community DIY pull finds 0 outdoor Tallinn
stations right now (honest-empty, not a bug) — but Estonia operates
official air-monitoring stations, and their REGISTER is machine-open.

OPENNESS VERDICT (checked 2026-09-16, POSITIVE — no dated negative):
`https://keskkonnaandmed.envir.ee/` is a keyless PostgREST 12.0.1
endpoint (`application/openapi+json`, 302 tables) and
`/f_seirejaamad` serves the environmental monitoring station register
as JSON without auth (verified rows carry `nimi`, `seisund`,
`sr_programm_nimi`, `ehak_tekst`, `kkr_kood`, and `kesk_x/kesk_y`
coords). Filtering `sr_programm_nimi=ilike.*ohu*` returns the
"Valisohu kvaliteedi seire" programme, including "Tallinn Rahu"
(Harju maakond, Tallinn, Pohja-Tallinna linnaosa, seisund Kasutusel).
Full probe evidence in docs/p4_ohuseire.md. Polite round: four small
GETs total (two truncated index reads, one 3-row sample, one 10-row
filtered pull), labelled one-off user-agent, paced >=3 s, short
timeouts, raw bodies cached at /tmp/hf-524-probe/ (one-off PR record,
never committed).

HONESTY (AGENTS.md section 7.2): register coords are L-EST97 metres
(EPSG:3301), converted here to WGS84 with a pure-stdlib Lambert
inverse (parameters quoted from the PROJ EPSG:3301 definition,
agreement with PROJ verified <0.01 m on four live stations in dev —
see docs; the conversion is labelled `teisendatud` in every reason).
Reference stations interpolate across districts, so the honest shape
is a coarse 2 km district-coverage hinnang (1 station -> 60, 2+ ->
70, cap 70 — never a calibrated measurement, never a doorstep value,
never heating truth). DIY stations stay as-is: dims_p4_senscom.py is
untouched (live when present, empty when absent); this module owns
ONLY the official-register leg and reasons cross-reference the DIY
leg instead of re-scoring it.

Style mirrors services/scoring/dims_p4_senscom.py (#306, the closest
ingestion precedent: fetch + parse + bbox extract travel explicitly,
scorers take an optional snapshot) and dims_p4_ookla.py (#268):
scorers are pure and offline-tested — (origin, pois, ohuseire=None)
-> (Optional[int 0..100], Estonian reason). The optional third
argument IS the demoed ingestion product (the Tallinn-extract
snapshot). Network lives only in fetch_ohuseire_dump (polite GETs,
file cache, TTL); tests never call it. The module is stdlib-only
(json + urllib + math, no new dependency).

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* OHUSEIRE_RADIUS_M = 2000 m: reference stations represent districts,
  not balconies (deliberately wider than the DIY 500 m window:
  reference inlets interpolate, balconies do not).
* Bands (1 -> 60, 2+ -> 70, cap 70): one official witness makes the
  district watched, never measured; two agree it is covered. Dull by
  design, challengeable with exposure data.
* Tallinn membership is the register's own `ehak_tekst` admin label
  containing "Tallinn" (exact substring on the authority's text, never
  a coordinate guess) plus converted coords inside the Tallinn bbox
  (join-key precedent: statkov #485 identity-join-or-NULL).
* Only `seisund == "Kasutusel"` stations count (in-use register
  state); "Peatatud" (suspended) and coordless rows are skipped and
  COUNTED in the extract (`n_skipped`), never silently dropped.
* OHUSEIRE_TTL_S = 7 d: the station inventory moves on installation
  timescales (weekly re-pull, daily-cron compatible); the snapshot
  date travels in the extract and is echoed in every reason.
* Test fixtures are fully synthetic (clearly labelled) — real
  observed values appear only in docs/p4_ohuseire.md, never as
  ingested data.
* Machine-checkable invariant kept by the tests: "EI OLE" appears
  ONLY in documented no-map NULL reasons, never in scored-proxy
  reasons (same precedent as dims_p4_osm / dims_p4_ookla / senscom).

Integration (deliberately NOT done here): feeding this dim with the
ingested snapshot inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling. No shared files touched:
3 new files only. Never touch dims_p4_senscom.py (the DIY P4-031 leg)
or any dims_group*.py.
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated register pulls.
# ---------------------------------------------------------------------------

#: Machine-open PostgREST register (verified 2026-09-16: HTTP 200,
#: application/json, no key). Station inventory with L-EST97 coords.
OHUSEIRE_BASE_URL = "https://keskkonnaandmed.envir.ee"
OHUSEIRE_STATIONS_PATH = "/f_seirejaamad"
#: Programme substring selecting the outdoor-air monitoring register
#: (verified value: "Valisohu kvaliteedi seire;Valisohu kvaliteedi
#: seire linnades" — match on the unaccented stem, case-insensitive,
#: so accent drift cannot silently empty the extract).
OHUSEIRE_PROGRAMME_NEEDLE = "valisohu"
#: Register state that counts as an operating witness.
OHUSEIRE_ACTIVE_STATE = "Kasutusel"
#: Admin-label substring for Tallinn membership (the register's own
#: `ehak_tekst`, e.g. "Harju maakond, Tallinn, Pohja-Tallinna
#: linnaosa" — identity join on authority text, never guessed).
OHUSEIRE_TALLINN_NEEDLE = "Tallinn"

#: At most one live pull per week (inventory moves on installation
#: timescales; AGENTS.md section 5 daily-cron compatible).
OHUSEIRE_TTL_S = 7 * 24 * 3600
OHUSEIRE_CACHE_NAME = "ohuseire-seirejaamad.json"
OHUSEIRE_SNAPSHOT_NAME = "ohuseire-tallinn.json"

#: District-coverage join radius in metres (reference inlets
#: interpolate — see judgment calls).
OHUSEIRE_RADIUS_M = 2000.0

#: Generous Tallinn bbox for the extract step (city + Viimsi /
#: Maardu fringe; the join is nearest-station, never an
#: admin-boundary claim). Same bbox precedent as dims_p4_ookla.
TALLINN_BBOX = {"lon_min": 24.3, "lon_max": 25.1,
                "lat_min": 59.3, "lat_max": 59.6}

USER_AGENT = ("home-finder-p4-ohuseire/1.0 (Estonia open-data weekly adapter; "
              "polite single-pull, cache-first)")


def _stations_url(limit: int = 1000) -> str:
    query = urllib.parse.urlencode({
        "sr_programm_nimi": "ilike.*ohu*",
        "limit": limit,
        "select": ("nimi,kesk_x,kesk_y,seisund,sr_programm_nimi,"
                   "ehak_tekst,keht_staatus,kkr_kood"),
    })
    return OHUSEIRE_BASE_URL + OHUSEIRE_STATIONS_PATH + "?" + query


def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, OHUSEIRE_CACHE_NAME)


def snapshot_cache_path(cache_dir: str) -> str:
    """Small Tallinn-extract JSON produced by the operator step."""
    return os.path.join(cache_dir, OHUSEIRE_SNAPSHOT_NAME)


def cache_is_fresh(path: str, ttl_s: int = OHUSEIRE_TTL_S,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_s."""
    try:
        age_s = (now if now is not None else time.time()) - os.path.getmtime(path)
    except OSError:
        return False
    return age_s < ttl_s


def fetch_ohuseire_dump(cache_dir: Optional[str] = None,
                        ttl_s: int = OHUSEIRE_TTL_S) -> Tuple[str, str]:
    """Fetch the air-programme station register politely (cached, TTL).

    Cache-first single GET with a polite User-Agent and a 20 s
    timeout (10-row filtered pull observed at 2.8 kB). Transport
    errors RAISE (never cached as data, AGENTS.md section 7.2); an
    error body is never written to the cache. HTTP 429 propagates as
    a stop signal; the stale cache is left untouched. Returns (raw
    text, provenance) with provenance "cache" or "live".
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-ohuseire")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if cache_is_fresh(path, ttl_s):
        with open(path, encoding="utf-8") as fh:
            return fh.read(), "cache"
    req = urllib.request.Request(_stations_url(), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        body = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body, "live"


# ---------------------------------------------------------------------------
# L-EST97 (EPSG:3301) -> WGS84, pure stdlib (no new dependency).
# ---------------------------------------------------------------------------

#: Lambert Conformal Conic parameters quoted from the PROJ EPSG:3301
#: definition (`+proj=lcc +lat_0=57.5175539305556 +lon_0=24
#: +lat_1=59.3333333333333 +lat_2=58 +x_0=500000 +y_0=6375000
#: +ellps=GRS80`). Agreement with PROJ verified <0.01 m on four live
#: register stations in dev (see docs/p4_ohuseire.md) — the committed
#: tests pin plausibility bounds + round-trip instead of PROJ itself
#: (hermetic suite, no optional dependency).
_LEST_A = 6378137.0
_LEST_F_INV = 298.257222101
_LEST_LAT0 = math.radians(57.5175539305556)
_LEST_LON0 = math.radians(24.0)
_LEST_LAT1 = math.radians(59.3333333333333)
_LEST_LAT2 = math.radians(58.0)
_LEST_FE = 500000.0
_LEST_FN = 6375000.0
_LEST_E2 = 2.0 / _LEST_F_INV - (1.0 / _LEST_F_INV) ** 2
_LEST_E = math.sqrt(_LEST_E2)


def _lest_m(phi: float) -> float:
    return math.cos(phi) / math.sqrt(1.0 - _LEST_E2 * math.sin(phi) ** 2)


def _lest_t(phi: float) -> float:
    s = _LEST_E * math.sin(phi)
    return math.tan(math.pi / 4.0 - phi / 2.0) / (
        ((1.0 - s) / (1.0 + s)) ** (_LEST_E / 2.0))


_LEST_M1 = _lest_m(_LEST_LAT1)
_LEST_M2 = _lest_m(_LEST_LAT2)
_LEST_T1 = _lest_t(_LEST_LAT1)
_LEST_T2 = _lest_t(_LEST_LAT2)
_LEST_T0 = _lest_t(_LEST_LAT0)
_LEST_N = ((math.log(_LEST_M1) - math.log(_LEST_M2))
           / (math.log(_LEST_T1) - math.log(_LEST_T2)))
_LEST_F = _LEST_M1 / (_LEST_N * _LEST_T1 ** _LEST_N)
_LEST_RHO0 = _LEST_A * _LEST_F * _LEST_T0 ** _LEST_N


def lest_to_wgs84(x: float, y: float) -> Tuple[float, float]:
    """L-EST97 metres -> (lon, lat) WGS84 degrees (pure, ellipsoidal).

    Iterative latitude recovery (12 iterations — millimetre
    convergence); EST97-vs-WGS84 datum difference is sub-metre and
    rides inside the 2 km join radius, labelled `teisendatud`.
    """
    dx = x - _LEST_FE
    dy = _LEST_RHO0 - (y - _LEST_FN)
    rho = math.copysign(math.hypot(dx, dy), _LEST_N)
    theta = math.atan2(dx, dy)
    tval = (rho / (_LEST_A * _LEST_F)) ** (1.0 / _LEST_N)
    phi = math.pi / 2.0 - 2.0 * math.atan(tval)
    for _ in range(12):
        s = _LEST_E * math.sin(phi)
        phi = (math.pi / 2.0 - 2.0 * math.atan(
            tval * (((1.0 - s) / (1.0 + s)) ** (_LEST_E / 2.0))))
    return (math.degrees(_LEST_LON0 + theta / _LEST_N), math.degrees(phi))


# ---------------------------------------------------------------------------
# Tallinn extract: canonical official air-station rows.
# ---------------------------------------------------------------------------

#: Accent fold table so accent drift cannot silently empty the
#: extract ("Valisohu" matches "Välisõhu", "Pohja" matches "Põhja").
_FOLD_FROM = "äöõüšžÄÖÕÜŠŽ"
_FOLD_TO = "aoouszAOOUSZ"


def _fold(text: str) -> str:
    return text.translate(str.maketrans(_FOLD_FROM, _FOLD_TO)).lower()


def _to_float(raw: object) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(str(raw).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def parse_ohuseire_dump(text: str) -> List[dict]:
    """Parse one register payload into candidate station rows (pure).

    Keeps every row with parseable L-EST coords (programme/state/
    city filtering happens in tallinn_extract, so the parse stays a
    faithful extract, never a pre-scored selection). Raises
    ValueError on unparseable JSON or a non-list payload (transport
    garbage is never a station list).
    """
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ValueError("ohuseire JSON ei parsinud: %s" % exc)
    if not isinstance(payload, list):
        raise ValueError("ohuseire vastus pole loend")
    rows: List[dict] = []
    for rec in payload:
        if not isinstance(rec, dict):
            continue
        x = _to_float(rec.get("kesk_x"))
        y = _to_float(rec.get("kesk_y"))
        if x is None or y is None:
            continue
        rows.append({
            "name": rec.get("nimi") if isinstance(rec.get("nimi"), str) else "?",
            "lest_x": x,
            "lest_y": y,
            "status": rec.get("seisund"),
            "programme": rec.get("sr_programm_nimi"),
            "ehak": rec.get("ehak_tekst"),
            "kkr": rec.get("kkr_kood"),
        })
    return rows


def tallinn_extract(rows: List[dict], bbox: Optional[dict] = None,
                    fetched: Optional[str] = None) -> Dict[str, object]:
    """Build the snapshot the dim consumes from parsed rows (pure).

    Keeps operating ("Kasutusel") outdoor-air-programme stations whose
    own admin label names Tallinn and whose converted coords fall in
    the bbox. Skipped rows are COUNTED (`n_skipped`), never silently
    dropped. The fetch date travels in the extract and is echoed in
    every reason.
    """
    box = dict(bbox or TALLINN_BBOX)
    stations: List[dict] = []
    skipped = 0
    for row in rows or []:
        if not isinstance(row, dict):
            skipped += 1
            continue
        programme = row.get("programme")
        if not isinstance(programme, str) or \
                OHUSEIRE_PROGRAMME_NEEDLE not in _fold(programme):
            skipped += 1
            continue
        if row.get("status") != OHUSEIRE_ACTIVE_STATE:
            skipped += 1
            continue
        ehak = row.get("ehak")
        if not isinstance(ehak, str) or OHUSEIRE_TALLINN_NEEDLE not in ehak:
            skipped += 1
            continue
        try:
            lon, lat = lest_to_wgs84(float(row["lest_x"]), float(row["lest_y"]))
        except (TypeError, ValueError, KeyError):
            skipped += 1
            continue
        if not (box["lon_min"] <= lon <= box["lon_max"]
                and box["lat_min"] <= lat <= box["lat_max"]):
            skipped += 1
            continue
        stations.append({"name": row.get("name", "?"), "lat": lat, "lon": lon,
                         "lest_x": row["lest_x"], "lest_y": row["lest_y"],
                         "ehak": ehak, "kkr": row.get("kkr"),
                         "converted": "L-EST97->WGS84 teisendatud hinnang"})
    if fetched is None:
        fetched = time.strftime("%Y-%m-%d", time.gmtime())
    return {"fetched": fetched, "bbox": box,
            "stations": stations, "n_stations": len(stations),
            "n_skipped": skipped}


def load_ohuseire_snapshot(cache_dir: str) -> Optional[dict]:
    """Load a cached Tallinn-extract JSON, or None when absent/unreadable.

    A missing or corrupt extract is never data (same envelope
    precedent as senscom load_senscom_snapshot) — the dim reports the
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
    """Coarse witness-count band (capped — register proximity is coverage)."""
    if n <= 1:
        return 60
    return 70


def _nearby(origin: Tuple[float, float],
            stations: List[dict]) -> List[Tuple[dict, float]]:
    """Operating official stations within the district radius (pure).

    No averaging, no smoothing — the band counts watched districts
    near the address (same no-smoothing precedent as senscom _nearby:
    smoothing would fake a gradient between reference inlets).
    """
    out: List[Tuple[dict, float]] = []
    for station in stations:
        if not isinstance(station, dict):
            continue
        lat = station.get("lat")
        lon = station.get("lon")
        if isinstance(lat, bool) or not isinstance(lat, (int, float)):
            continue
        if isinstance(lon, bool) or not isinstance(lon, (int, float)):
            continue
        dist = _haversine_m(origin, float(lat), float(lon))
        if dist <= OHUSEIRE_RADIUS_M:
            out.append((station, dist))
    out.sort(key=lambda pair: pair[1])
    return out


# ---------------------------------------------------------------------------
# P4-031 official-register slice: coarse district-coverage hinnang.
# ---------------------------------------------------------------------------

def _null_no_origin() -> Score:
    return None, ("Ametliku öhujaama hinnang eeldab aadressi koordinaate "
                  "(EI OLE hinnangut ilma asukohata): lähimaid "
                  "Keskkonnaagentuuri jaamu saab siduda vaid teada aadressiga "
                  "— kontrolli ohuseire kaarti ja hoovi kohapeal, ära feigi")


def _null_no_snapshot() -> Score:
    return None, ("Keskkonnaagentuuri Tallinna väljavõtet pole vahemällu "
                  "tõmmatud (EI OLE hinnangut): nädalane registritõmme "
                  "puudub — linnaosa ametlik jaam (Harku linnabaas, "
                  "DIY-võrk) selgub registri väljavõttest ja kohapealsest "
                  "kontrollist, ära feigi tühjast vahemälust skoori")


def _null_empty(fetched: object) -> Score:
    return None, ("Keskkonnaagentuuri Tallinna väljavõte on tühi (%s, EI OLE "
                  "hinnangut): ühtegi töötavat välisõhujaama Tallinnas "
                  "kirjas pole — võimalik registrimuudatus või "
                  "filtrimisviga — kontrolli seirejaamade registrist ja "
                  "hoovi kohapeal, ära feigi"
                  % (fetched if isinstance(fetched, str) else "teadmata"))


def _null_no_station(fetched: object) -> Score:
    return None, ("%.0f m raadiuses EI OLE ühtegi töötavat "
                  "Keskkonnaagentuuri välisõhujaama (EI OLE hinnangut; "
                  "väljavõte %s): lähim ametlik jaam on linnaosafaktist "
                  "kaugemal — DIY-võrk (sensor.community) ja hoovi "
                  "kohapealne kontroll jäävad, ära feigi tühjast "
                  "registrist skoori"
                  % (OHUSEIRE_RADIUS_M,
                     fetched if isinstance(fetched, str) else "teadmata"))


def dim_official_air(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]] = None,
                     ohuseire: Optional[dict] = None) -> Score:
    """P4-031 official-register slice: coarse district-coverage hinnang.

    Counts operating Keskkonnaagentuur outdoor-air stations within
    2 km of the address (1 -> 60, 2+ -> 70, cap 70). A thin or missing
    register stays NULL — an unwatched district is unknown, never
    good. `pois` is accepted for the uniform scorer shape and ignored
    (register stations are not OSM POIs).
    """
    _ = pois
    if origin is None:
        return _null_no_origin()
    stations = ohuseire.get("stations") if isinstance(ohuseire, dict) else None
    if stations is None:
        return _null_no_snapshot()
    fetched = ohuseire.get("fetched") if isinstance(ohuseire, dict) else None
    if not stations:
        return _null_empty(fetched)
    nearby = _nearby(origin, stations)
    if not nearby:
        return _null_no_station(fetched)
    n = len(nearby)
    score = _band_density(n)
    nearest, dist = nearby[0]
    name = nearest.get("name") if isinstance(nearest, dict) else "?"
    return score, ("Ametliku öhujaama hinnang %d/100: Keskkonnaagentuuri "
                   "töötavaid välisõhujaamu %d tk %.0f m raadiuses (lähim "
                   "%s ~%.0f m, L-EST97->WGS84 teisendatud hinnang; "
                   "väljavõte %s) — see on linnaosa katvushinnang, mitte "
                   "hoovi mõõtmine: DIY-võrk (sensor.community), Harku "
                   "linnabaas ja EHR kütte liik pole selles hinnangus — "
                   "külmakotid ja tuulekoridorid kontrolli kohapeal"
                   % (score, n, OHUSEIRE_RADIUS_M, name, dist,
                      fetched if isinstance(fetched, str) else "teadmata"))


P4_OHUSEIRE_DIMS = (
    ("official_air_ohuseire", "P4-031", dim_official_air),
)

#: Param-number wiring for the central weight-rebalance follow-up. The
#: KEY is distinct from senscom's `backyard_air_senscom` (no import
#: collision); the NUMBER shares buyer-param slice P4-031 by design —
#: the rebalance follow-up must weight only one leg per question.
P4_OHUSEIRE_PARAM_IDS = {
    "official_air_ohuseire": 31,
}


def score_p4_ohuseire(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]] = None,
                      ohuseire: Optional[dict] = None
                      ) -> Dict[str, Optional[int]]:
    """The P4 official-air dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_OHUSEIRE_DIMS). The value
    is a capped district-coverage hinnang band when the Tallinn
    extract covers the address, else None by design — never a faked
    per-backyard measurement."""
    return {key: fn(origin, pois, ohuseire)[0] for key, _, fn in P4_OHUSEIRE_DIMS}
