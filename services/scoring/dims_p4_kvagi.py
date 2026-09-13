"""P4 kvagi dims (issues #297 demo + #367 coverage): Kaitsevägi
training-area open-data ingestion + three honest-shape dims off that
source family.

Demo param (this ingestion's anchor):
* P4-023 Airport + military noise zones -> dim_exercise_noise_zone
  (zone join over the Kaitsevägi exercise-notice leg, never
  walk-gradient; currency comes from the dated Brontos calendar)

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-033 Seasonal nuisance calendar -> dim_exercise_season_calendar
  (calendar dim over the Tallinn-audible exercise weeks)
* P4-055 Harbour/air timetable nuisances -> dim_manniku_weekend_calendar
  (calendar dim over the Männiku weekend-pops leg only)

OPENNESS VERDICT (checked 2026-09-13, 8 tiny requests total, one GET
each, paced >= 5 s, labelled one-off user-agent
"home-finder kvagi openness-check #297 (one-off, single GETs, file
cache for PR record; contact via GitHub home-finder)", /tmp cache
kept for the PR record, never committed; no retries - HTTP 429/errors
are a stop signal):
* https://mil.ee/ -> HTTP 200, 201 348 B. Visible-text sweep (~7.6k
  chars) 0 for laskmine/laskmisteated/Männiku/teated/avaandmed/API/
  csv/geojson/wfs/müra ("rss" x1, "kaart" x1 chrome only). Links to
  /kaitsevagi/harjutusvaljad/, /kaitsevagi/oppused/, /uudised/,
  /feed/. Front page is a storefront, never a notice feed.
* https://mil.ee/kaitsevagi/harjutusvaljad/ -> HTTP 200, 1 151 541 B
  (~88.5k visible chars). Rich HUMAN area guide: Männiku x19,
  laskmine x31, müra x33, Tapa/Sirgala/Soodla named, Tallinn x9; 0
  for laskmisteated/teated/csv/geojson/wfs. Links to the teadmiseks/
  safety page, the valjaoppealade-avaandmed/ open-data page, static
  PDF maps and an ArcGIS webappviewer (viewer shell, same
  stop-at-shell precedent as lumekaart/veebikaart in #283 and
  mürakaart in #296 - chasing app config exceeds a polite budget).
* https://mil.ee/kaitsevagi/oppused/ -> HTTP 200, 147 089 B (6.7k
  visible chars). Thin overview, no dated exercise calendar at page
  level; links to eesti-sisesed/rahvusvahelised subpages (human
  pages, not followed - same stop-at-human-page rule).
* https://mil.ee/feed/ -> HTTP 200, 7 327 B. 10 news headlines with
  pubDate, zero geo/category exercise metadata - headlines, never a
  structured exercise calendar.
* https://mil.ee/kaitsevagi/harjutusvaljad/teadmiseks/ -> HTTP 200,
  129 957 B. Human safety notice ("Teadmiseks kohalikule elanikule
  ja metsas liikujale!"); 0 for csv/geojson/wfs/json/download -
  buyer-side reading, not a feed.
* CONFIRMED OPEN:
  https://mil.ee/kaitsevagi/harjutusvaljad/valjaoppealade-avaandmed/
  -> HTTP 200, 129 947 B. The page declares machine-readable open
  data ("masinloetavas formaadis"), sourced from the Brontos
  register of national-defence training areas, under CC 3.0 BY-SA:
  training objects (with coordinates) plus info-board schedules
  ("infotahvli graafikud"). Schedule rows appear ~1 week ahead,
  change live ("võivad jooksvalt muutuda") and the running month is
  deleted next month ("Jooksva kuu harjutuste andmed kustutatakse
  järgmisel kuul").
* CONFIRMED OPEN:
  https://mil.ee/wp-content/uploads/training-grounds/training_ground_schedule.json
  -> HTTP 200, 132 800 B (page states 129.69 KB). 68 area-month
  rows; the 10 current-month (2026-09) rows carry 475 dated
  exercises, incl. MÄNNIKU harjutusväli (54, among them a Saturday
  2026-09-19 SHOOTING) and the parameters4.md trio SOODLA (9) /
  SIRGALA (49) / KAITSEVÄE KESKPOLÜGOON (144). Observed layout:
  [{trainingAreaId, trainingAreaName, year, month, additionalInfo
  (incl. the published MÜRATASEMED noise legend), approvedAt,
  exercises: [{id, startDate, endDate (ISO UTC), exerciseType
  (TACTICS/SHOOTING/BLASTING), trainingObjects (codes), noiseLevel
  (LOW/AVERAGE/HIGH/VERY_HIGH/ABSENT), status}]}].
* CONFIRMED OPEN:
  https://mil.ee/wp-content/uploads/training-grounds/training_ground_mapdata.json
  -> HTTP 200, 581 619 B (page states 567.99 KB). 38 areas with
  EPSG:3857 polygons plus coded training objects (code/name/polygon)
  and area contact points. Männiku bbox-centroid inverts to
  ~59.34/24.73 (Nõmme edge) - the projection math below checks out
  against geography.
So fetch_cached below targets the two JSON snapshots with stated
TTLs, and all three dims score ONLY dated, noise-carrying entries.
The zone join and the calendars are proven on fixtures only - see
docs/p4_kvagi.md for the full note and the reopen checklist.

HONESTY (AGENTS.md section 7.2): the P4-023 dim is a zone join,
never a walk-gradient (parameters4.md: "zone join, never
walk-gradient (G9 covers roads only)"); the gate only decides
membership, the score is flat per band. The P4-033/P4-055 dims are
calendar dims with expiry (parameters4.md shapes: "calendar dims
with dates" / "calendar dims"); the score comes from the dated
entry alone. Every scored reason says "hinnang" and prints its
components; every NULL reason says "EI OLE" and names the missing
input. Transport errors are never cached as data (fetch_cached
stores only HTTP 200 bodies over a minimum size). Entries with
noiseLevel ABSENT (silent tactics without blank ammo, per the
published MÜRATASEMED legend) or unknown/missing noise can never
score - an empty/active-silent buffer stays NULL (unknown or
silent, never "quiet" as a claim); expired, future-dated and
dateless entries stay NULL (impact starts on the start day, day
grain). Areas outside the parameters4.md Tallinn-audible set never
score in these dims.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_cached(url, cache_dir, filename, ttl_s): polite pull, one GET
  with an identifying UA and a 30 s timeout; cache hit within TTL
  makes NO request; single attempt, no retries. Network lives ONLY
  here; readers, scorers and tests never touch it.
* parse_schedule: schedule JSON -> [{area_id, area, year, month,
  approved_at, entries: [{id, start_day, end_day (YYYY-MM-DD or
  None when malformed - dateless entries can never score), kind,
  noise, status, objects}]}]. Unknown noise/kind tokens are kept
  raw (never guessed); rows without an area name are skipped (no
  join key - keeping them would fake coverage).
* parse_mapdata: mapdata JSON -> [{area_id, area, anchor (WGS84
  lat/lon = bbox-centre of all area polygons through the exact
  inverse-Mercator below), n_objects, contact}]. The anchor is a
  join convenience for the gate, not a precision claim - stated.
* index_by_area_month: per-area-month join index (first row wins).

Style mirrors services/scoring/dims_p4_eans.py (#296/#366): pure
scorers (origin, pois[, today]) -> (Optional[int 0..100], Estonian
reason), local helpers (no livability import - importing it here
would turn the future central hook into a cycle, same precedent as
PRs #100/#106/#115). No Overpass fragment is staged: positions
arrive via the Brontos join (area anchor), not via snapshot tags,
so there is nothing honest for the live path to fetch - stated,
not omitted by accident.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #367's body states
  it "extend[s] the demoed ingestion ... no new plumbing expected":
  the seasonal calendar and the Männiku weekend calendar read the
  same cached Brontos snapshots as the P4-023 zone join, each dim
  reading its own filter. No second source is pulled.
* Per-source slices, not full params: P4-023 keeps the EANS
  approach-corridor leg (dims_p4_eans dim_airport_noise_zone), the
  EHR insulation-requirement NULL, the KAUR Ämari-rattle leg and the
  trans END band for their owners - this module adds ONLY the
  Kaitsevägi exercise-notice leg. P4-033 keeps the Sadam cruise /
  Lauluväljak / bells / hunting / snow-dump legs for their future
  source issues - this module adds ONLY the Kaitsevägi exercise-week
  leg (parameters4.md source 5). P4-055 keeps the Sadam foghorn/
  icebreaker legs and the EANS lennuinfo leg
  (dims_p4_eans dim_harbour_air_calendar) plus the Elron
  raudteemüra-ööaknad NULL (dims_p4_elron) - this module adds ONLY
  the Männiku weekend-pops leg (parameters4.md source 3). Distinct
  dim keys and a disjoint POI kind throughout so the central hook
  can weight slices independently; P4-023/P4-033 may fire together
  on one Männiku week (different buyer questions - insulation hit
  vs when-loud - same accepted overlap as EANS zone+calendar).
* Tallinn-audible set = MÄNNIKU + SOODLA + SIRGALA + KAITSEVÄE
  KESKPOLÜGOON, exactly the areas parameters4.md names for these
  legs (P4-023 source 3 "Tapa/Sirgala/Soodla - Tallinn kuuluvus",
  P4-055 source 3 Männiku; Keskpolügoon is the Tapa central
  polygon). Audibility is NOT distance-modelled beyond the uniform
  gate - far polygons simply never gate a Tallinn origin, which is
  the data speaking, not a fudge (never a gradient).
* Uniform 3 km audibility gate for all three dims (heavy-weapons
  audibility: VERY_HIGH = artillery per the published legend).
  Flat scores inside, NULL outside - the gate is membership, never
  a gradient (same precedent as the EANS 2 km propagation gate).
* Day grain: Brontos slices are sub-day (05:00-20:59Z); the buyer
  question is which days/weeks are loud, so entries collapse to
  [start_day, end_day] and impact starts on the start day.
* Scores mirror the sibling bands on purpose (values encode
  exposure severity, source-independent, hook rebalances anyway):
  P4-023 zone = 50 (the EANS/trans õppus band), P4-033/P4-055
  calendars = flat 45 (the EANS/citynotices active-calendar
  exposure). POI kind + reason keep slices distinguishable.
* TTLs: schedule 1 d (rows appear ~1 week ahead and change live;
  daily cron re-checks, never re-pulls inside TTL), mapdata 90 d
  (polygons/contacts stable). CC 3.0 BY-SA is honoured by linking
  the source page in docs/p4_kvagi.md; no scraped dump is
  committed - tests use hand-written synthetic fixtures.
* today is an optional third scorer arg (date or YYYY-MM-DD,
  default date.today()) so the expiry logic is hermetic in tests
  and live-honest in production; the central hook keeps calling
  (origin, pois).

Integration (deliberately NOT done here): area-anchor computation
upstream (offline polygon step feeding exercisenoise_kvagi POIs),
splicing the POI kind into livability, and rebalancing
livability.WEIGHTS must be one joint change across all batches -
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits
would break every sibling. No shared files touched: 3 new files
only.
"""

import datetime
import math
import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple, Union

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Brontos training-schedule snapshot (verified 2026-09-13: HTTP 200,
#: ~130 KB JSON, 68 area-month rows, CC 3.0 BY-SA open data).
SCHEDULE_URL = ("https://mil.ee/wp-content/uploads/training-grounds/"
                "training_ground_schedule.json")

#: Brontos training-area map snapshot (verified 2026-09-13: HTTP 200,
#: ~568 KB JSON, 38 areas with EPSG:3857 polygons, CC 3.0 BY-SA).
MAPDATA_URL = ("https://mil.ee/wp-content/uploads/training-grounds/"
               "training_ground_mapdata.json")

#: Human open-data page declaring the machine-readable snapshots.
AVAANDMED_URL = "https://mil.ee/kaitsevagi/harjutusvaljad/valjaoppealade-avaandmed/"

#: Schedule rows appear ~1 week ahead and change live, the running
#: month rolls: at most one snapshot refresh per 24 h per cache dir
#: (daily cron would only re-check, never re-pull inside TTL).
SCHEDULE_TTL_S = 24 * 3600

#: Area polygons and contact points are stable: at most one refresh
#: per 90 d per cache dir.
MAPDATA_TTL_S = 90 * 24 * 3600

#: Identifying user agent for the polite pull (single GET, open data).
KVAGI_UA = "home-finder kvagi openness-check #297 (daily schedule max, no scrape)"

#: Minimum plausible snapshot body: a real monthly file always carries
#: all area rows (tens of KB observed), so anything smaller is an
#: error page, never data.
SNAPSHOT_MIN_BYTES = 4096


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = SCHEDULE_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with KVAGI_UA and a 30 s timeout; the body is stored only on
    HTTP 200 with at least SNAPSHOT_MIN_BYTES bytes, else None is
    returned and nothing is cached (transport errors are never data).
    No retries - HTTP 429/errors are a stop signal. Scorers and readers
    never call this; tests cover the cache-hit and error paths with a
    stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": KVAGI_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < SNAPSHOT_MIN_BYTES:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached snapshots (pure; observed layout).
# ---------------------------------------------------------------------------

#: Areas parameters4.md names Tallinn-audible for these legs (P4-023
#: source 3: Tapa/Sirgala/Soodla; P4-055 source 3: Männiku;
#: Keskpolügoon is the Tapa central polygon - see judgment calls).
TALLINN_AUDIBLE_AREAS = ("MÄNNIKU harjutusväli", "SOODLA harjutusväli",
                         "SIRGALA harjutusväli", "KAITSEVÄE KESKPOLÜGOON")

#: Noise levels that carry sound (per the published MÜRATASEMED
#: legend). ABSENT = silent tactics without blank ammo; unknown or
#: missing noise never scores (never guessed).
SCORING_NOISES = ("LOW", "AVERAGE", "HIGH", "VERY_HIGH")

#: Day grain of a Brontos timestamp (sub-day slices collapse to days).
_DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _clean(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _day(value: Optional[object]) -> Optional[str]:
    """YYYY-MM-DD day of an ISO timestamp, else None (never guessed)."""
    if not isinstance(value, str):
        return None
    m = _DAY_RE.match(value.strip())
    if not m:
        return None
    try:
        datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))


def parse_schedule(obj: object) -> List[dict]:
    """Schedule JSON -> [{area_id, area, year, month, approved_at,
    entries: [{id, start_day, end_day, kind, noise, status, objects}]}].

    Offline. Malformed timestamps read as dateless (None) and can
    never score; unknown kind/noise tokens are kept raw (the scorer
    admits only SCORING_NOISES); rows without an area name are
    skipped (no join key - keeping them would fake coverage).
    """
    records = []
    if not isinstance(obj, list):
        return records
    for row in obj:
        if not isinstance(row, dict):
            continue
        area = _clean(row.get("trainingAreaName"))
        if not area:
            continue
        entries = []
        raw_entries = row.get("exercises")
        if isinstance(raw_entries, list):
            for e in raw_entries:
                if not isinstance(e, dict):
                    continue
                objects = e.get("trainingObjects")
                entries.append({
                    "id": e.get("id"),
                    "start_day": _day(e.get("startDate")),
                    "end_day": _day(e.get("endDate")),
                    "kind": _clean(e.get("exerciseType")),
                    "noise": _clean(e.get("noiseLevel")),
                    "status": _clean(e.get("status")),
                    "objects": list(objects) if isinstance(objects, list)
                    else [],
                })
        records.append({"area_id": row.get("trainingAreaId"), "area": area,
                        "year": row.get("year"), "month": row.get("month"),
                        "approved_at": _clean(row.get("approvedAt")),
                        "entries": entries})
    return records


#: Web-Mercator (EPSG:3857) half-circumference, metres.
_MERC_HALF = 20037508.34


def mercator_to_wgs84(x: float, y: float) -> Tuple[float, float]:
    """Exact inverse spherical-Mercator: (x, y) metres -> (lat, lon).

    Pure projection math (EPSG:3857 definition), not a lookup - the
    mapdata polygons arrive in EPSG:3857 (crs stated per geometry).
    """
    lon = x / _MERC_HALF * 180.0
    lat = math.degrees(2 * math.atan(math.exp(math.radians(
        y / _MERC_HALF * 180.0))) - math.pi / 2)
    return lat, lon


def parse_mapdata(obj: object) -> List[dict]:
    """Mapdata JSON -> [{area_id, area, anchor, n_objects, contact}].

    Offline. anchor = WGS84 (lat, lon) bbox-centre over all area
    polygon rings (a join convenience for the audibility gate, not a
    precision claim); areas without a usable ring get anchor None
    (they can never gate - never guessed). Contacts are passed
    through raw (published area contact points).
    """
    records = []
    if not isinstance(obj, list):
        return records
    for row in obj:
        if not isinstance(row, dict):
            continue
        area = _clean(row.get("trainingAreaName"))
        if not area:
            continue
        xs: List[float] = []
        ys: List[float] = []
        shape = row.get("shape")
        geoms = shape.get("geometries") if isinstance(shape, dict) else None
        if isinstance(geoms, list):
            for g in geoms:
                if not isinstance(g, dict):
                    continue
                coords = g.get("coordinates")
                polys = []
                if g.get("type") == "Polygon" and isinstance(coords, list):
                    polys = [coords]
                elif g.get("type") == "MultiPolygon" and isinstance(
                        coords, list):
                    polys = [p for p in coords if isinstance(p, list)]
                for poly in polys:
                    for ring in poly:
                        if not isinstance(ring, list):
                            continue
                        for pt in ring:
                            if (isinstance(pt, list) and len(pt) >= 2
                                    and isinstance(pt[0], (int, float))
                                    and isinstance(pt[1], (int, float))
                                    and not isinstance(pt[0], bool)
                                    and not isinstance(pt[1], bool)):
                                xs.append(float(pt[0]))
                                ys.append(float(pt[1]))
        anchor = None
        if xs and ys:
            anchor = mercator_to_wgs84((min(xs) + max(xs)) / 2,
                                       (min(ys) + max(ys)) / 2)
        objects = row.get("trainingObjects")
        records.append({"area_id": row.get("trainingAreaId"), "area": area,
                        "anchor": anchor,
                        "n_objects": len(objects)
                        if isinstance(objects, list) else 0,
                        "contact": {"phone": _clean(row.get("contactPhone")),
                                    "email": _clean(row.get("contactEmail"))}})
    return records


def index_by_area_month(records: List[dict]) -> Dict[tuple, dict]:
    """Per-area-month join index (first row wins)."""
    index = {}  # type: Dict[tuple, dict]
    for rec in records:
        key = (rec.get("area"), rec.get("year"), rec.get("month"))
        if key[0] and key not in index:
            index[key] = rec
    return index


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; local to avoid import cycles).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = (math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2)
         * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _valid_point(poi: dict) -> Optional[Tuple[float, float]]:
    """(lat, lon) for a well-formed point, else None. Pure."""
    try:
        lat = float(poi["lat"])
        lon = float(poi["lon"])
    except (TypeError, ValueError, KeyError):
        return None
    if isinstance(poi.get("lat"), bool) or isinstance(poi.get("lon"), bool):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    return lat, lon


def _in_window(origin: Tuple[float, float], kind: str,
               pois: List[dict], window_m: float) -> List[Tuple[float, dict]]:
    """All well-formed POIs of kind within window_m, with distances."""
    out = []
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        ll = _valid_point(p)
        if ll is None:
            continue
        d = _haversine_m(origin, ll[0], ll[1])
        if d <= window_m:
            out.append((d, p))
    return out


Today = Union[datetime.date, str, None]


def _today_iso(today: Today) -> str:
    """Normalise the calendar cursor to YYYY-MM-DD (default: today)."""
    if today is None:
        return datetime.date.today().isoformat()
    if isinstance(today, datetime.date):
        return today.isoformat()
    return str(today)


def _window_state(start_day: object, end_day: object,
                  today_iso: str) -> Optional[str]:
    """'active' | 'expired' | 'future' for YYYY-MM-DD days, else None.

    Missing or malformed days -> None (dateless entries can never
    score, and score as nothing - not as quiet, not as exposure).
    Impact starts on the start day (day grain - see judgment calls).
    """
    if not (isinstance(start_day, str) and isinstance(end_day, str)):
        return None
    if not (_DAY_RE.match(start_day) and _DAY_RE.match(end_day)):
        return None
    if start_day <= today_iso <= end_day:
        return "active"
    if today_iso > end_day:
        return "expired"
    return "future"


def _overlaps_weekend(start_day: str, end_day: str) -> bool:
    """True when a YYYY-MM-DD span covers a Saturday or Sunday. Pure."""
    try:
        s = datetime.date(*map(int, start_day.split("-")))
        e = datetime.date(*map(int, end_day.split("-")))
    except (ValueError, TypeError):
        return False
    if e < s:
        return False
    span = (e - s).days
    to_sat = (5 - s.weekday()) % 7
    to_sun = (6 - s.weekday()) % 7
    return span >= to_sat or span >= to_sun


# ---------------------------------------------------------------------------
# Windows + scores (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: Uniform blast-audibility gate for all three dims (membership only,
#: never a gradient - VERY_HIGH = artillery per the published legend).
AUDIBLE_WINDOW_M = 3000.0
#: P4-023 Kaitsevägi-leg zone band (high = calmer; mirrors the
#: EANS/trans õppus band on purpose - exposure severity is
#: source-independent).
EXERCISE_ZONE_SCORE = 50
#: Active dated exercise nearby: flat exposure (never a gradient;
#: the "schedulable" half is the dates themselves - mirrors the
#: EANS/citynotices active-calendar exposure).
EXERCISE_CALENDAR_SCORE = 45


def _audible_active(origin: Tuple[float, float], pois: List[dict],
                    today_iso: str, area: Optional[str] = None,
                    weekends_only: bool = False
                    ) -> List[Tuple[float, dict]]:
    """(distance, poi) hits: exercisenoise_kvagi in gate, area audible,
    entry day-active today, noise sound-carrying.

    area limits to one training area (the Männiku leg); weekends_only
    keeps entries overlapping Sat/Sun. Malformed, dateless, silent
    (ABSENT), unknown-noise and out-of-set entries never pass.
    """
    hits = []
    for dist_m, poi in _in_window(origin, "exercisenoise_kvagi", pois,
                                  AUDIBLE_WINDOW_M):
        if poi.get("area") not in TALLINN_AUDIBLE_AREAS:
            continue
        if area is not None and poi.get("area") != area:
            continue
        if poi.get("noise") not in SCORING_NOISES:
            continue
        start_day = poi.get("start")
        end_day = poi.get("end")
        if _window_state(start_day, end_day, today_iso) != "active":
            continue
        if weekends_only and not _overlaps_weekend(start_day, end_day):
            continue
        hits.append((dist_m, poi))
    return hits


# ---------------------------------------------------------------------------
# P4-023: airport + military noise, Kaitsevägi exercise leg (demo).
# ---------------------------------------------------------------------------

def dim_exercise_noise_zone(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]],
                            today: Today = None) -> Score:
    """P4-023: Kaitsevägi-leg exercise zone band (high = calmer week).

    Zone join, never walk-gradient: a dated Brontos entry for a
    Tallinn-audible area whose anchor sits within 3 km is a zone
    hit; the score is the flat õppus band when the hit is day-active
    today with sound-carrying noise. Distance only gates the join.
    Outside every audible area, or with only silent/expired/future/
    dateless entries nearby, stays NULL (unknown or silent, never
    quiet). Only this slice - the EANS approach-corridor leg, the
    EHR insulation NULL, the KAUR rattle leg and the trans END band
    stay their own slices.
    """
    if not origin or pois is None:
        return None, ("Õppusemüra info puudub (EI OLE Brontose "
                      "harjutusgraafiku liidestust hetktõmmes)")
    now = _today_iso(today)
    hits = _audible_active(origin, pois, now)
    if not hits:
        return None, ("Läheduses pole kehtivat Kaitsevägi õppuse kirjet "
                      "Tallinna-kuuldaval alal - hinnangut pole (EI OLE "
                      "kehtivat graafikukirjet: ala pole kuuldav, kirje on "
                      "aegunud/tulevane/kuupäevata või harjutusmoonata "
                      "vaikne taktika, mitte mõõdetud vaikus)")
    dist_m, poi = min(hits, key=lambda h: h[0])
    return EXERCISE_ZONE_SCORE, (
        "Õppusemüra tsooni-hinnang (tsooniliidestus + kehtiv graafik, "
        "mitte kaugusgradient): ala %s, kirje %s (%s kuni %s, "
        "müratase %s) -> skoor %d"
        % (poi.get("area"), _fmt_m(dist_m), poi.get("start"),
           poi.get("end"), poi.get("noise"), EXERCISE_ZONE_SCORE))


# ---------------------------------------------------------------------------
# P4-033: seasonal nuisance calendar, exercise-week leg (coverage).
# ---------------------------------------------------------------------------

def dim_exercise_season_calendar(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]],
                                 today: Today = None) -> Score:
    """P4-033: dated exercise-week calendar dim (high = calmer now).

    Only the Kaitsevägi exercise-week leg: exercisenoise_kvagi POIs
    carry the area anchor plus the ISO start/end of the Brontos
    entry. A day-active, sound-carrying entry in the buffer scores a
    flat exposure and the reason prints its dates (the "millal vali"
    answer); expired, future-dated, dateless and silent entries stay
    NULL. The Sadam/bells/hunting/snow-dump legs belong to their
    future source issues.
    """
    if not origin or pois is None:
        return None, ("Õppusenädalate info puudub (EI OLE Brontose "
                      "harjutusgraafiku liidestust hetktõmmes)")
    now = _today_iso(today)
    hits = _audible_active(origin, pois, now)
    if not hits:
        return None, ("Läheduses pole kehtivat õppusenädalat "
                      "Tallinna-kuuldaval alal - hinnangut pole (EI OLE "
                      "kehtivat graafikukirjet, mitte mõõdetud vaikus)")
    nearest_m = min(d for d, _ in hits)
    latest_end = max(str(p["end"]) for _, p in hits)
    areas = sorted({str(p.get("area", "ala")) for _, p in hits})
    return EXERCISE_CALENDAR_SCORE, (
        "Õppusenädalate hinnang: %d kehtivat kirjet 3 km puhvris "
        "(lähim %s, kehtib kuni %s: %s) -> skoor %d"
        % (len(hits), _fmt_m(nearest_m), latest_end,
           "; ".join(areas[:3]), EXERCISE_CALENDAR_SCORE))


# ---------------------------------------------------------------------------
# P4-055: harbour/air timetable nuisances, Männiku leg (coverage).
# ---------------------------------------------------------------------------

def dim_manniku_weekend_calendar(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]],
                                 today: Today = None) -> Score:
    """P4-055: Männiku weekend-pops calendar dim (high = calmer now).

    Only the Männiku weekend-pops leg (parameters4.md source 3):
    entries for MÄNNIKU harjutusväli overlapping Sat/Sun that are
    day-active today score a flat exposure; weekday-only, expired,
    future-dated, dateless and silent entries stay NULL. The Sadam
    foghorn/icebreaker legs and the EANS lennuinfo leg
    (dims_p4_eans) plus the Elron ööaknad NULL (dims_p4_elron) stay
    their own slices.
    """
    if not origin or pois is None:
        return None, ("Männiku nädalavahetuse-müra info puudub (EI OLE "
                      "Brontose Männiku-graafiku liidestust hetktõmmes)")
    now = _today_iso(today)
    hits = _audible_active(origin, pois, now, area="MÄNNIKU harjutusväli",
                           weekends_only=True)
    if not hits:
        return None, ("Läheduses pole kehtivat Männiku nädalavahetuse "
                      "kirjet - hinnangut pole (EI OLE kehtivat "
                      "nädalavahetuse-graafikukirjet: ainult argipäevane, "
                      "aegunud/tulevane/kuupäevata või vaikne kirje, "
                      "mitte mõõdetud vaikus)")
    nearest_m = min(d for d, _ in hits)
    latest_end = max(str(p["end"]) for _, p in hits)
    return EXERCISE_CALENDAR_SCORE, (
        "Männiku nädalavahetuse-müra hinnang: %d kehtivat kirjet 3 km "
        "puhvris (lähim %s, kehtib kuni %s) -> skoor %d"
        % (len(hits), _fmt_m(nearest_m), latest_end,
           EXERCISE_CALENDAR_SCORE))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_KVAGI_DIMS = (
    ("exercise_noise_zone", "P4-023", dim_exercise_noise_zone),
    ("exercise_season_calendar", "P4-033", dim_exercise_season_calendar),
    ("manniku_weekend_calendar", "P4-055", dim_manniku_weekend_calendar),
)


def score_p4_kvagi(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]],
                   today: Today = None) -> Dict[str, Optional[int]]:
    """All three P4 kvagi dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_KVAGI_DIMS)."""
    return {key: fn(origin, pois, today)[0] for key, _, fn in P4_KVAGI_DIMS}
