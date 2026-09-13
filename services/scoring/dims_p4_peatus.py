"""P4 peatus dims (issues #314 demo + #376 coverage): Peatus.ee GTFS transit dims.

Params (this module only — no sibling owns Peatus.ee GTFS P4 params):
* P4-061 last-shop/pharmacy/ATM + bus-cut tracker (demo, batch 5)
* P4-037 policy exposure: car-tax / car-free exposure offset (batch 3)
* P4-045 third places + keeper effect: evening access (batch 4)
* P4-048 small delights: <15 min access per delight (batch 4)
* P4-049 taxi/guest test: Saturday guest arrival (batch 4)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per #314):
``https://peatus.ee/gtfs/gtfs.zip`` (the parameters3.md section 5.12 URL)
currently does NOT serve a GTFS zip. Polite evidence, 3 tiny requests total
(headers + one 601-byte range peek, custom UA, no scrape):
* HEAD /gtfs/gtfs.zip -> HTTP/2 302, location: /reitti/gtfs/gtfs.zip
* HEAD /reitti/gtfs/gtfs.zip -> HTTP/2 200, content-type text/html, 1311 bytes
* ranged GET (bytes 0-600) -> "<title>Rakendus on suletud</title>" (app closed)
Raw headers cached at /tmp/peatus-gtfs-head*.txt (TTL: one-off check, kept
for the PR record, never committed). So the live path below is honest
plumbing with NO live data: fetch_gtfs_zip returns None when the feed is
closed/unreachable, every scorer then returns None with an Estonian EI OLE
reason, and the scored shapes are proven on fixtures only. Reopening
checklist lives in docs/p4_peatus.md.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components; every NULL reason says "EI OLE" and
names the missing input. Transport errors are never cached as data
(fetch_gtfs_zip writes the zip only on HTTP 200 with zip content, else
returns None). A stop with a measured zero (deps == 0 from GTFS) scores
low — a real no-service signal — while a missing join (deps is None)
stays NULL: absence of data is unknown, never bad. Distances are
bird-flight at 75 m/min (livability walk speed), never routed.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_gtfs_zip(cache_dir): polite pull, max 1 download / 24 h per cache
  dir (GTFS_TTL_S; parameters3.md section 5.12 cadence: daily cron 03:30
  UTC). Cache hit within TTL performs NO request. Single GET with an
  identifying UA, no retries (HTTP 429 is a stop signal, AGENTS.md 7.4).
* read_gtfs_tables / services_with / departures_per_stop / stop_coords /
  stop_pois_from_counts: pure offline readers over the cached zip (same
  split as scripts/build/batch_b4_common.read_gtfs). Network lives ONLY
  in fetch_gtfs_zip; scorers and tests never touch it.
* Windows over one zip, no new source: Wednesday all-day (exposure +
  cut baseline), Wednesday >= 18:00 (evening, P4-045), Saturday all-day
  (guest arrival, P4-049), previous vintage Wednesday (cut diff, P4-061).

Style mirrors services/scoring/dims_group12.py (#126, the GTFS
precedent): pure scorers (origin, pois) -> (Optional[int 0..100],
Estonian reason), local helpers (no livability import — importing it
here would turn the future central hook into a cycle, same precedent as
PRs #100/#106/#115), plus the staged Overpass fragment + tag mapping
the live path needs on integration.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because the #376 body states it
  "extends the demoed ingestion": the evening/Saturday windows and the
  prev-vintage diff are same-zip extensions, no new plumbing or source.
  Said here as #376 acceptance requires.
* Exposure/evening/Saturday windows are 750 m (a usable walk to the
  stop); the cut tracker and the <15 min delight access use 1500 m /
  1125 m (15 min x 75 m/min). Beyond-window is NULL (unknown), not 0.
* Exposure bands reuse the 2026-09-12 group-12 Wednesday calibration
  (median 138, p10 42 deps/stop/day) without re-measuring: the feed is
  closed, so recalibration is impossible — stated, not hidden.
  Evening/Saturday bands are first-cut judgments with no prior
  calibration; they MUST be recalibrated from a real vintage on reopen
  (docs/p4_peatus.md checklist).
* P4-048 delights access is distance-only: <15 min access is a walk
  fact, so a mapped stop (deps None) still scores while count-based
  dims stay NULL. The reason flags "marsruutimata".
* P4-061 prev == 0 with cur > 0 is new service (90); prev == cur == 0
  is persistent measured no-service (20), not unknown.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with P4_PEATUS_OVERPASS_FRAGMENT,
livability._POI_KIND with the stop_p4 mapping, and rebalancing
livability.WEIGHTS must be one joint change across all batches —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits
would break every sibling. No shared files touched: 3 new files only.
"""

import math
import os
import time
import urllib.request
import zipfile
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Canonical Peatus.ee GTFS static URL (parameters3.md section 5.12).
#: 2026-09-13: 302s to /reitti/gtfs/gtfs.zip, which serves "Rakendus on
#: suletud" HTML instead of a zip (dated negative, see module docstring).
GTFS_URL = "https://peatus.ee/gtfs/gtfs.zip"

#: Max one download per 24 h per cache dir (parameters3.md: 1 download/24h,
#: daily cron 03:30 UTC). Stated TTL for the polite pull.
GTFS_TTL_S = 24 * 3600

#: Zip filename inside the cache dir.
CACHE_FILENAME = "peatus-gtfs.zip"

#: Identifying user agent for the polite pull (no scrape, single GET).
GTFS_UA = "home-finder GTFS openness-check (1 req/24h max, no scrape)"

#: Evening window start for P4-045 (third places evening access).
EVENING_FROM = "18:00:00"

#: GTFS tables the offline readers need (same five as batch_b4_common).
GTFS_TABLES = ("calendar.txt", "trips.txt", "stop_times.txt",
               "stops.txt", "routes.txt")


def fetch_gtfs_zip(cache_dir: str,
                   ttl_s: int = GTFS_TTL_S,
                   url: str = GTFS_URL) -> Optional[str]:
    """Polite Peatus.ee GTFS pull with a stated TTL. Returns zip path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise one
    GET with GTFS_UA and a 30 s timeout; the body is stored only on HTTP 200
    with zip content, else None is returned and nothing is cached (transport
    errors are never data). No retries — HTTP 429/errors are a stop signal.
    Scorers never call this; tests cover the cache-hit and error paths with
    a stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": GTFS_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "zip" not in ctype:
                return None
            body = resp.read()
        if len(body) < 1024 or body[:2] != b"PK":
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached zip (pure; same split as batch_b4_common).
# ---------------------------------------------------------------------------

def read_gtfs_tables(zip_path: str) -> Dict[str, List[dict]]:
    """Read the five GTFS tables from a cached snapshot zip. Offline, stdlib."""
    import csv
    import io
    out: Dict[str, List[dict]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in GTFS_TABLES:
            with zf.open(name) as fh:
                out[name] = list(csv.DictReader(
                    io.TextIOWrapper(fh, encoding="utf-8-sig")))
    return out


def services_with(calendar_rows: List[dict], day: str) -> set:
    """service_ids running on the given weekday column (e.g. wednesday)."""
    return {c["service_id"] for c in calendar_rows if c.get(day) == "1"}


def departures_per_stop(gtfs: Dict[str, List[dict]], service_ids: set,
                        after: Optional[str] = None) -> Dict[str, int]:
    """stop_id -> departures over the given services; optional time floor.

    after="18:00:00" keeps evening departures only (string comparison is
    safe: GTFS times are zero-padded HH:MM:SS, and past-midnight 25:xx:xx
    still sorts after 18:00:00). Pure.
    """
    trip_ok = {t["trip_id"] for t in gtfs["trips.txt"]
               if t.get("service_id") in service_ids}
    cnt: Dict[str, int] = {}
    for row in gtfs["stop_times.txt"]:
        if row.get("trip_id") not in trip_ok:
            continue
        if after is not None and (row.get("departure_time") or "") < after:
            continue
        sid = row.get("stop_id")
        if sid:
            cnt[sid] = cnt.get(sid, 0) + 1
    return cnt


def stop_coords(stops_rows: List[dict]) -> Dict[str, Tuple[float, float]]:
    """stop_id -> (lon, lat); malformed rows are skipped, never faked."""
    out: Dict[str, Tuple[float, float]] = {}
    for row in stops_rows:
        try:
            sid = row.get("stop_id")
            lon = float(row["stop_lon"])
            lat = float(row["stop_lat"])
        except (TypeError, ValueError, KeyError):
            continue
        if sid and math.isfinite(lon) and math.isfinite(lat):
            out[sid] = (lon, lat)
    return out


def stop_pois_from_counts(coords: Dict[str, Tuple[float, float]],
                          cur: Dict[str, int],
                          prev: Optional[Dict[str, int]] = None,
                          eve: Optional[Dict[str, int]] = None,
                          sat: Optional[Dict[str, int]] = None) -> List[dict]:
    """GTFS stops -> scorer POIs with all P4 windows attached. Pure.

    coords: stop_id -> (lon, lat); cur: current Wednesday departures;
    prev: previous-vintage Wednesday departures (cut diff); eve: Wednesday
    departures >= 18:00; sat: Saturday departures. Stops missing a window
    keep None there (scorer stays NULL with an EI OLE reason). Hermetic.
    """
    prev = prev or {}
    eve = eve or {}
    sat = sat or {}
    pois = []
    for sid, (lon, lat) in coords.items():
        pois.append({"kind": "stop_p4", "lat": lat, "lon": lon,
                     "deps_wed": cur.get(sid),
                     "deps_prev": prev.get(sid),
                     "deps_eve": eve.get(sid),
                     "deps_sat": sat.get(sid)})
    return pois


# ---------------------------------------------------------------------------
# Live-path wiring (staged constants only; NOT spliced in here, see above).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
P4_PEATUS_OVERPASS_FRAGMENT = """
  node["highway"="bus_stop"](around:1500,{lat},{lon});
  node["public_transport"="platform"](around:1500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND on integration.
P4_PEATUS_POI_KIND = [
    ("highway", {"bus_stop": "stop_p4"}),
    ("public_transport", {"platform": "stop_p4",
                          "stop_position": "stop_p4"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """P4 peatus kind for OSM tags (stop positions only), else None. Pure."""
    if not isinstance(tags, dict):
        return None
    if tags.get("highway") == "bus_stop":
        return "stop_p4"
    if tags.get("public_transport") in ("platform", "stop_position"):
        return "stop_p4"
    return None


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; local to avoid import cycles).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _count(poi: dict, key: str) -> Optional[int]:
    """Sanitised departure count: ints only, bool/negative/garbage -> None."""
    v = poi.get(key)
    if isinstance(v, bool):
        return None
    try:
        n = int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _nearest(origin: Tuple[float, float],
             pois: List[dict]) -> Optional[Tuple[float, dict]]:
    """(distance_m, poi) of the nearest well-formed stop_p4, else None. Pure."""
    best = None
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != "stop_p4":
            continue
        try:
            lat = float(p["lat"])
            lon = float(p["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(p.get("lat"), bool) or isinstance(p.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if best is None or d < best[0]:
            best = (d, p)
    return best


# ---------------------------------------------------------------------------
# Windows + bands (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: Walk speed 4.5 km/h = livability SPEED_WALK_KMH, as metres per minute.
WALK_M_PER_MIN = 75.0
#: P4-061 cut tracker reads the settlement stop within 1500 m.
STOP_WINDOW_M = 1500.0
#: P4-037/045/049 alternative-access dims read the stop within 750 m.
ALT_WINDOW_M = 750.0
#: P4-048 delights <15 min access = 15 min x 75 m/min bird-flight.
WALK15_M = 1125.0

#: Cut fraction (cur-prev)/prev -> score (high = stable/growing service).
CUT_BANDS = [(-0.30, 20), (-0.10, 45), (0.10, 70), (float("inf"), 90)]
#: Wednesday departures -> exposure-offset score (high = strong alternative).
#: Anchored on the 2026-09-12 group-12 calibration (median 138, p10 42).
EXPOSURE_BANDS = [(0, 20), (29, 40), (79, 60), (149, 80), (float("inf"), 100)]
#: Wednesday departures >= 18:00 -> evening-access score (first-cut bands).
EVENING_BANDS = [(0, 20), (3, 40), (9, 60), (19, 80), (float("inf"), 100)]
#: Saturday departures -> guest-arrival score (first-cut bands).
SAT_BANDS = [(0, 20), (7, 40), (19, 60), (39, 80), (float("inf"), 100)]
#: Walk distance -> <15 min access score (high = closer).
WALK_BANDS = [(300, 100), (600, 85), (900, 70), (1125, 55)]


# ---------------------------------------------------------------------------
# P4-061: last-shop/pharmacy/ATM + bus-cut tracker (demo param).
# ---------------------------------------------------------------------------

def dim_bus_cut(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """P4-061: bus-cut band from the GTFS prev-vs-cur diff (high = stable).

    Per-listing Tallinn-fringe reading of the settlement checklist: the
    nearest stop's Wednesday departures this vintage vs the previous one.
    Single-vintage (no prev) stays NULL — a cut cannot be measured from
    one timetable. Unknown when inputs are missing or no stop is near.
    """
    if not origin or pois is None:
        return None, ("Bussikärpe info puudub (EI OLE GTFS-vintsi "
                      "hetktõmmises: allikas peatus.ee on suletud, "
                      "võrdlusvintsi pole)")
    hit = _nearest(origin, pois)
    if hit is None or hit[0] > STOP_WINDOW_M:
        return None, ("Lähim peatus kaugemal kui 1,5 km — kärpehinnangut "
                      "pole (EI OLE GTFS-ühendust, mitte mõõdetud kärbe)")
    dist_m, poi = hit
    cur = _count(poi, "deps_cur")
    prev = _count(poi, "deps_prev")
    if cur is None or prev is None:
        missing = "jooksev" if cur is None else "eelmine"
        return None, ("Peatus %s, aga %s GTFS-vints puudub — kärbet ei saa "
                      "ühe sõiduplaani pealt mõõta (EI OLE võrdlusvintsi)"
                      % (_fmt_m(dist_m), missing))
    if prev <= 0:
        if cur > 0:
            return 90, ("Bussiteenus (hinnang): peatus %s, eelmises vintsis "
                        "väljumisi polnud, nüüd %d väljumist/kolmapäev — "
                        "uus teenus" % (_fmt_m(dist_m), cur))
        return 20, ("Bussiteenus (hinnang): peatus %s, mõlemas vintsis "
                    "väljumisi pole — püsiv teenusepuudus, mitte andmelünk"
                    % _fmt_m(dist_m))
    cut = (cur - prev) / prev
    s = _band(cut, CUT_BANDS)
    assert s is not None
    return s, ("Bussikärbe (hinnang): peatus %s, eelmine vints %d vs nüüd "
               "%d väljumist/kolmapäev (%+.0f%%) → skoor %d"
               % (_fmt_m(dist_m), prev, cur, 100 * cut, s))


# ---------------------------------------------------------------------------
# P4-037: policy exposure offset (coverage param).
# ---------------------------------------------------------------------------

def dim_policy_exposure(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-037: commute-alternative offset (high = strong alternative).

    Only the GTFS half of the param: frequent service nearby offsets
    automaks/car-free exposure. Car-dependence itself is not in the
    snapshot, so this is an offset band, never a full exposure verdict.
    """
    if not origin or pois is None:
        return None, ("Alternatiivse ühenduse info puudub (EI OLE "
                      "GTFS-ühendust hetktõmmises: allikas peatus.ee "
                      "on suletud)")
    hit = _nearest(origin, pois)
    if hit is None or hit[0] > ALT_WINDOW_M:
        return None, ("Lähim peatus kaugemal kui 750 m — alternatiivi "
                      "hinnangut pole (EI OLE ühendust, mitte mõõdetud "
                      "sõltuvus autost)")
    dist_m, poi = hit
    deps = _count(poi, "deps_wed")
    if deps is None:
        return None, ("Peatus %s, aga kolmapäeva väljumistabel puudub — "
                      "alternatiivi ei saa lugeda (EI OLE GTFS-liidestust)"
                      % _fmt_m(dist_m))
    s = _band(deps, EXPOSURE_BANDS)
    assert s is not None
    return s, ("Automaksu-riskikaitse (hinnang, ainult ühistranspordi pool): "
               "peatus %s, %d väljumist/kolmapäev → skoor %d"
               % (_fmt_m(dist_m), deps, s))


# ---------------------------------------------------------------------------
# P4-045: third places evening access (coverage param).
# ---------------------------------------------------------------------------

def dim_third_places(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-045: evening access to third places (high = evening service).

    Only the GTFS half of the param: Wednesday departures after 18:00 at
    the nearest stop. Sauna/pub/library hours and keeper tenure are not
    in the snapshot, so this is an access band, never a belonging verdict.
    """
    if not origin or pois is None:
        return None, ("Õhtuse ühenduse info puudub (EI OLE GTFS-õhtutabelit "
                      "hetktõmmises: allikas peatus.ee on suletud)")
    hit = _nearest(origin, pois)
    if hit is None or hit[0] > ALT_WINDOW_M:
        return None, ("Lähim peatus kaugemal kui 750 m — õhtuse juurdepääsu "
                      "hinnangut pole (EI OLE ühendust)")
    dist_m, poi = hit
    eve = _count(poi, "deps_eve")
    if eve is None:
        return None, ("Peatus %s, aga õhtune väljumistabel (pärast 18:00) "
                      "puudub — õhtust juurdepääsu ei saa lugeda (EI OLE "
                      "GTFS-õhtuakent)" % _fmt_m(dist_m))
    s = _band(eve, EVENING_BANDS)
    assert s is not None
    return s, ("Õhtune juurdepääs (hinnang): peatus %s, %d väljumist pärast "
               "18:00/kolmapäev → skoor %d" % (_fmt_m(dist_m), eve, s))


# ---------------------------------------------------------------------------
# P4-048: small delights <15 min access (coverage param).
# ---------------------------------------------------------------------------

def dim_delights_access(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-048: <15 min walk access (high = closer stop).

    Distance-only by design: <15 min access is a walk fact, so a mapped
    stop scores even before the GTFS frequency join lands. Bench/forest/
    swim/gym delight positions and allotment queues are not in the
    snapshot — this is the transit-access leg only, never the joy verdict.
    """
    if not origin or pois is None:
        return None, ("Juurdepääsu info puudub (EI OLE peatuse kaardistust "
                      "hetktõmmises)")
    hit = _nearest(origin, pois)
    if hit is None or hit[0] > WALK15_M:
        return None, ("Lähim peatus kaugemal kui 15 min jalgsi — "
                      "juurdepääsu hinnangut pole (EI OLE ühendust 15 min "
                      "aknas, mitte mõõdetud rõõmupuudus)")
    dist_m, _ = hit
    walk_min = dist_m / WALK_M_PER_MIN
    s = _band(dist_m, WALK_BANDS)
    assert s is not None
    return s, ("Rõõmude juurdepääs (hinnang, linnulennult, marsruutimata): "
               "peatus %s ≈ %d min jalgsi → skoor %d"
               % (_fmt_m(dist_m), int(round(walk_min)), s))


# ---------------------------------------------------------------------------
# P4-049: taxi/guest Saturday arrival (coverage param).
# ---------------------------------------------------------------------------

def dim_guest_arrival(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-049: Saturday guest-arrival access (high = Saturday service).

    Only the GTFS half of the param: Saturday departures at the nearest
    stop. Findability, name pronounceability, guest parking and entrance
    tidiness are not in the snapshot — access band only, never the pride
    verdict.
    """
    if not origin or pois is None:
        return None, ("Külaliste saabumise info puudub (EI OLE "
                      "GTFS-laupäevatabelit hetktõmmises: allikas "
                      "peatus.ee on suletud)")
    hit = _nearest(origin, pois)
    if hit is None or hit[0] > ALT_WINDOW_M:
        return None, ("Lähim peatus kaugemal kui 750 m — laupäevase "
                      "saabumise hinnangut pole (EI OLE ühendust)")
    dist_m, poi = hit
    sat = _count(poi, "deps_sat")
    if sat is None:
        return None, ("Peatus %s, aga laupäeva väljumistabel puudub — "
                      "külaliste saabumist ei saa lugeda (EI OLE "
                      "GTFS-laupäevaakent)" % _fmt_m(dist_m))
    s = _band(sat, SAT_BANDS)
    assert s is not None
    return s, ("Külaliste saabumine laupäeval (hinnang): peatus %s, %d "
               "väljumist/laupäev → skoor %d" % (_fmt_m(dist_m), sat, s))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
P4_PEATUS_DIMS = (
    ("bus_cut", "P4-061", dim_bus_cut),
    ("policy_exposure", "P4-037", dim_policy_exposure),
    ("third_places", "P4-045", dim_third_places),
    ("delights_access", "P4-048", dim_delights_access),
    ("guest_arrival", "P4-049", dim_guest_arrival),
)


def score_p4_peatus(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 peatus dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_PEATUS_DIMS}
