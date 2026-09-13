"""P4 EANS dims (issues #296 demo + #366 coverage): EANS Tallinn noise-zone
ingestion + two honest-shape dims off that source family.

Demo param (this ingestion's anchor):
* P4-023 Airport + military noise zones -> dim_airport_noise_zone
  (zone join over the EANS approach-corridor leg, never walk-gradient)

Coverage param (extends the demoed ingestion, no new plumbing):
* P4-055 Harbour/air timetable nuisances -> dim_harbour_air_calendar
  (calendar dim over the EANS lennuinfo / Sadam / Männiku notice leg)

OPENNESS VERDICT (checked 2026-09-13, 10 tiny requests total, custom UA,
one GET each, paced >= 4 s, /tmp/hf-p4-eans cache kept for the PR record,
never committed; no retries - HTTP 429/errors are a stop signal):
* DATED NEGATIVE (keeps verdict): EANS publishes no keyless
  machine-readable noise-zone feed. https://www.eans.ee/ (== eans.ee) ->
  HTTP 200, 569 681 B corporate site; visible-text sweep (3.8k chars) 0
  for müra/noise/avaandmed/open data/API/kaart/tsoon, zero matching
  hrefs - timetables and procedures are passenger/pilot pages, never a
  bulk zone feed.
* DATED NEGATIVE: national-portal machine search. The new-style
  /api/datasets?query= shape -> HTTP 400 "property query should not
  exist"; the CKAN /api/3/action/package_search shape -> HTTP 404
  "Cannot GET" (corroborates the kudocs #261 and EHR #249 findings:
  the portal has no CKAN API). No EANS/noise dataset reachable that way.
* DATED NEGATIVE: harbour/air timetable machine feeds. https://www.ts.ee/
  (Port of Tallinn) -> HTTP 200, 137 469 B; human schedule pages exist
  (/saabuvad-liinireisid/, /laevad-sadamas/) but the visible-text sweep
  is 0 for avaandmed/open data/API/GTFS/müra/noise - CLOSED as a machine
  timetable feed. https://mil.ee/ (Kaitsevägi) -> HTTP 200, 201 348 B;
  front-page sweep 0 for laskmine/laskmisteated/Männiku/teated/
  avaandmed/API ('harjutus' x2 menu hits only) - Männiku laskmisteated
  are human news, never a calendar feed.
* CONFIRMED LEAD, viewer only: https://transpordiamet.ee/mura-ja-valisohk
  -> HTTP 200, 214 053 B; names the strategic-noise viewer
  https://xgis.maaamet.ee/xgis2/page/app/myrakaart ('mürakaart' x1,
  'kaardirakendus' x2, zero shp/geojson/WFS/download/avaandmed links).
  The viewer itself -> HTTP 200 but a 1 243 B JS bootstrap shell
  ("X-GIS 2.0 [myrakaart]", 21 visible chars, zero service/download
  links): chasing service URLs out of app config would exceed a polite
  probe budget (same precedent as the lumekaart/veebikaart shells in
  the citynotices #283 module). Strategic END zones are viewer pages;
  EANS approach corridors are not an open feed at all.
So fetch_eans_snapshot below targets the documented zone/notice snapshot
layout with stated TTLs, and both dims score ONLY joined records. The
zone join and the calendar are proven on fixtures only - see
docs/p4_eans.md for the full note and the reopen checklist.

HONESTY (AGENTS.md section 7.2): the P4-023 dim is a zone join, never a
walk-gradient (parameters4.md: "zone join, never walk-gradient (G9
covers roads only)"); distance only gates the join window, the score
comes from the zone label alone. The P4-055 dim is a calendar dim with
expiry (parameters4.md P4-055 shape: "calendar dims"); the score comes
from the dated entry alone. Every scored reason says "hinnang" and
prints its components; every NULL reason says "EI OLE" and names the
missing input. Transport errors are never cached as data (fetch_cached
stores only HTTP 200 bodies over a minimum size). Measured zero is not
applicable: notices are dated events, not exhaustive calendars, and
zones are mapped polygons - an empty/expired buffer stays NULL
(unknown, never "quiet"); a future-dated notice stays NULL (impact
starts on its start date).

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_cached(url, cache_dir, filename, ttl_s): polite pull, one GET
  with an identifying UA and a 30 s timeout; cache hit within TTL makes
  NO request; single attempt, no retries. Network lives ONLY here;
  readers, scorers and tests never touch it.
* parse_noise_zones: zone-snapshot CSV -> [{zone_key, zone, source,
  updated}] (observed layout documented below; unknown zone tokens read
  as None, keyless rows skipped).
* parse_schedule_notices: notice-snapshot CSV -> [{notice_key, label,
  start, end, area}] (ISO dates kept raw; malformed stay dateless and
  can never score).
* index_by_zone: per-parcel join index (first row wins).

Style mirrors services/scoring/dims_p4_citynotices.py (#283/#357): pure
scorers (origin, pois[, today]) -> (Optional[int 0..100], Estonian
reason), local helpers (no livability import - importing it here would
turn the future central hook into a cycle, same precedent as PRs
#100/#106/#115). No Overpass fragment is staged: positions arrive via
the zone/notice join, not via snapshot tags, so there is nothing honest
for the live path to fetch - stated, not omitted by accident.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #366's body states it
  "extend[s] the demoed ingestion ... no new plumbing expected": the
  harbour/air calendar reads the same cached EANS snapshot family (the
  Ämari-rattle corridors are the same approach-corridor geography as
  the P4-023 zones; Sadam/Männiku notices share the fetch + TTL +
  expiry shapes), each dim reading its own POI kind. No second source
  is pulled.
* Per-source slices, not full params: P4-023 keeps the EHR
  insulation-requirement NULL (dims_p4_ehr dim_noise_zone), the KAUR
  Ämari-rattle cross-check leg (dims_p4_kaur dim_mura_kaur) and the
  trans END strategic band (dims_p4_trans dim_noise_zone_trans) for
  their owners - this module adds ONLY the EANS approach-corridor leg.
  P4-055 keeps the Elron raudteemüra-ööaknad NULL (dims_p4_elron
  dim_elron_night_maintenance); this module adds ONLY the
  harbour/air (Sadam/EANS/Männiku) notice leg. Distinct dim keys
  throughout so the central hook can weight slices independently.
* The zone band mirrors the trans P4-023 mapping (lennumüra -> 35,
  õppus -> 50, sadam -> 60, high = quieter) on purpose: the values
  encode exposure severity, which is source-independent, and the
  central hook rebalances slices anyway. The POI kind
  (noisezone_eans vs noisezone_p4) and the reason keep the slices
  distinguishable - stated, not hidden.
* The calendar window is 2 km (propagation gate for water-/air-carried
  sound: foghorns across the bay, Ämari rattle corridors over North
  Tallinn - never a gradient, the score is flat). An active notice
  scores a flat exposure (45, like the citynotices construction/snow
  dims); expired, future-dated and dateless entries stay NULL.
* TTLs: zones quarterly (90 d - END maps move on the 5-year cycle and
  EANS procedures change rarely, so quarterly re-checks converge per
  AGENTS.md 7.4); harbour/air notices weekly (7 d - sailing/firing
  notices turn over weekly, same cadence as the citynotices eelinfo).
* today is an optional third scorer arg (date or YYYY-MM-DD, default
  date.today()) so the expiry logic is hermetic in tests and live-
  honest in production; the central hook keeps calling (origin, pois).

Integration (deliberately NOT done here): zone-polygon join upstream
(point-in-polygon done offline), notice geocoding (street/area labels
-> WGS84 via the ADS/Maa-amet step), splicing POI kinds into
livability, and rebalancing livability.WEIGHTS must be one joint change
across all batches - existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling. No shared files
touched: 3 new files only.
"""

import csv
import datetime
import io
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

#: EANS public site (verified 2026-09-13: HTTP 200 corporate site, no
#: keyless noise-zone feed - dated negative, see module docstring).
EANS_URL = "https://www.eans.ee/"

#: Transpordiamet noise topic page (verified 2026-09-13: HTTP 200, names
#: the X-GIS mürakaart viewer, no download links).
NOISE_TOPIC_URL = "https://transpordiamet.ee/mura-ja-valisohk"

#: Strategic-noise viewer (verified 2026-09-13: HTTP 200, 1.2 KB JS
#: bootstrap shell - viewer only, no server-rendered service links).
MYRAKAART_URL = "https://xgis.maaamet.ee/xgis2/page/app/myrakaart"

#: Port of Tallinn arrivals board (verified 2026-09-13: HTTP 200 human
#: schedule pages, no machine timetable feed - dated negative).
SADAM_SCHEDULE_URL = "https://www.ts.ee/saabuvad-liinireisid/"

#: Zone polygons move on the END 5-year cycle / EANS procedure changes:
#: at most one snapshot refresh per 90 d per cache dir (daily cron would
#: only re-check, never re-pull inside TTL).
ZONES_TTL_S = 90 * 24 * 3600

#: Sailing/firing/air notices turn over weekly (same cadence as the
#: citynotices eelinfo): at most one refresh per 7 d per cache dir.
NOTICES_TTL_S = 7 * 24 * 3600

#: Identifying user agent for the polite pull (single GET, no scrape).
EANS_UA = "home-finder eans openness-check (quarterly zones max, no scrape)"

#: Minimum plausible snapshot body: the documented CSV header alone is
#: ~60 B, so anything smaller is an error page, never data.
SNAPSHOT_MIN_BYTES = 64


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = ZONES_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with EANS_UA and a 30 s timeout; the body is stored only on
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
        req = urllib.request.Request(url, headers={"User-Agent": EANS_UA})
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
# Offline readers over the cached snapshot (pure; documented layout).
# ---------------------------------------------------------------------------

#: Canonical zone labels carried by noisezone_eans POIs (exposure class
#: of the containing EANS/Sadam/harjutusväljade polygon; point-in-polygon
#: is done offline, the reader keeps the label).
EANS_ZONES = ("lennumüra", "sadam", "õppus")

#: Canonical timetable-nuisance labels carried by schednuisance_eans
#: POIs (udusignaal = Sadam foghorns, jäämurre = icebreakers Tallinn
#: Bay, ämari = EANS lennuinfo Ämari-rattle corridors, männiku =
#: Kaitsevägi Männiku laskmisteated, Nõmme edge).
EANS_NUISANCES = ("udusignaal", "jäämurre", "ämari", "männiku")

#: ISO calendar dates carried by schednuisance_eans POIs.
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def parse_noise_zones(csv_text: str) -> List[dict]:
    """Zone-snapshot CSV -> [{zone_key, zone, source, updated}]. Offline.

    Semicolon-separated, BOM-tolerant. Unknown zone tokens read as None
    (never guessed); rows without a zone_key are skipped (no join key -
    keeping them would fake join coverage). No personal data in this
    layout by construction (zone-level polygons, no subject rows).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []
    for row in reader:
        key = _clean(row.get("zone_key"))
        if not key:
            continue
        zone = _clean(row.get("zone"))
        zone = zone if zone in EANS_ZONES else None
        records.append({"zone_key": key, "zone": zone,
                        "source": _clean(row.get("source")),
                        "updated": _clean(row.get("updated"))})
    return records


def parse_schedule_notices(csv_text: str) -> List[dict]:
    """Notice-snapshot CSV -> [{notice_key, label, start, end, area}]. Offline.

    Semicolon-separated, BOM-tolerant. Unknown labels read as None;
    dates are kept raw (ISO validation is the scorer's job - malformed
    stays dateless and can never score); rows without a notice_key are
    skipped (keeping them would fake calendar coverage).
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    records = []
    for row in reader:
        key = _clean(row.get("notice_key"))
        if not key:
            continue
        label = _clean(row.get("label"))
        label = label if label in EANS_NUISANCES else None
        records.append({"notice_key": key, "label": label,
                        "start": _clean(row.get("start")),
                        "end": _clean(row.get("end")),
                        "area": _clean(row.get("area"))})
    return records


def index_by_zone(records: List[dict]) -> Dict[str, dict]:
    """Per-parcel join index (one zone record per key; first row wins)."""
    index = {}  # type: Dict[str, dict]
    for rec in records:
        key = rec.get("zone_key")
        if key and str(key) not in index:
            index[str(key)] = rec
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


def _nearest(origin: Tuple[float, float], kind: str,
             pois: List[dict]) -> Optional[Tuple[float, dict]]:
    """(distance_m, poi) of the nearest well-formed POI of kind, else None."""
    best = None
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        ll = _valid_point(p)
        if ll is None:
            continue
        d = _haversine_m(origin, ll[0], ll[1])
        if best is None or d < best[0]:
            best = (d, p)
    return best


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


def _label(poi: dict, key: str, allowed: Tuple[str, ...]) -> Optional[str]:
    """Sanitised codelist label: exact match only, else None. Pure."""
    v = poi.get(key)
    return v if isinstance(v, str) and v in allowed else None


Today = Union[datetime.date, str, None]


def _today_iso(today: Today) -> str:
    """Normalise the calendar cursor to YYYY-MM-DD (default: today)."""
    if today is None:
        return datetime.date.today().isoformat()
    if isinstance(today, datetime.date):
        return today.isoformat()
    return str(today)


def _window_state(start: object, end: object,
                  today_iso: str) -> Optional[str]:
    """'active' | 'expired' | 'future' for ISO start/end, else None.

    ISO YYYY-MM-DD strings compare lexicographically. Missing or
    malformed dates -> None (dateless entries can never score, and
    score as nothing - not as quiet, not as exposure).
    """
    if not (isinstance(start, str) and isinstance(end, str)):
        return None
    if not (_ISO_RE.match(start) and _ISO_RE.match(end)):
        return None
    if start <= today_iso <= end:
        return "active"
    if today_iso > end:
        return "expired"
    return "future"


# ---------------------------------------------------------------------------
# Windows + scores (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: P4-023 zone join window (gates the join only, never gradients).
NOISE_WINDOW_M = 1000.0
#: P4-023 EANS-leg zone labels -> score (high = quieter zone; mirrors
#: the trans END band on purpose - values encode exposure severity).
NOISE_ZONE_SCORES = {"lennumüra": 35, "õppus": 50, "sadam": 60}
#: P4-055 harbour/air notice window: propagation gate for
#: water-/air-carried sound (foghorns across the bay, Ämari rattle
#: corridors over North Tallinn) - never a gradient, the score is flat.
NUISANCE_WINDOW_M = 2000.0
#: Active dated timetable nuisance nearby: flat exposure (never a
#: gradient; the "schedulable" half is the dates themselves).
NUISANCE_ACTIVE_SCORE = 45


# ---------------------------------------------------------------------------
# P4-023: airport + military noise, EANS approach-corridor leg (demo).
# ---------------------------------------------------------------------------

def dim_airport_noise_zone(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-023: EANS-leg strategic-noise zone band (high = quieter zone).

    Zone join, never walk-gradient: the nearest noisezone_eans within
    1 km carries its containing polygon's label (point-in-polygon done
    offline - Lasnamäe/Pirita/Kesklinn approach corridors, Sadam
    ship/heli notice areas, harjutusväljade audibility); the score comes
    from the label alone, distance only gates the join. Outside every
    mapped zone stays NULL (unknown, not quiet). Only this slice - the
    EHR insulation-requirement NULL, the KAUR Ämari-rattle leg and the
    trans END band stay their own slices.
    """
    if not origin or pois is None:
        return None, ("Mürataseme info puudub (EI OLE EANS/strateegilise "
                      "mürakaardi tsooniliidestust hetktõmmes)")
    hit = _nearest(origin, "noisezone_eans", pois)
    if hit is None or hit[0] > NOISE_WINDOW_M:
        return None, ("Aadress pole kaardistatud EANS müratsoonis - "
                      "hinnangut pole (EI OLE tsooniliidestust, mitte "
                      "mõõdetud vaikus)")
    dist_m, poi = hit
    zone = _label(poi, "zone", tuple(NOISE_ZONE_SCORES))
    if zone is None:
        return None, ("EANS mürakaardi kirje %s, aga tsoonimärgis puudub "
                      "või on tundmatu - müraaset ei saa lugeda (EI OLE "
                      "tsooniliidestust)" % _fmt_m(dist_m))
    s = NOISE_ZONE_SCORES[zone]
    return s, ("EANS müratsooni hinnang (tsooniliidestus, mitte "
               "kaugusgradient): tsoon %s, kirje %s -> skoor %d"
               % (zone, _fmt_m(dist_m), s))


# ---------------------------------------------------------------------------
# P4-055: harbour/air timetable nuisances, notice leg (coverage).
# ---------------------------------------------------------------------------

def dim_harbour_air_calendar(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]],
                             today: Today = None) -> Score:
    """P4-055: dated timetable-nuisance calendar dim (high = calmer now).

    Only the harbour/air notice leg: schednuisance_eans POIs carry the
    geocoded notice area plus the ISO start/end of the sailing/firing/
    rattle notice (udusignaal/jäämurre/ämari/männiku). An in-effect
    entry in the buffer scores a flat exposure; expired, future-dated
    and dateless entries stay NULL (unknown, never quiet); no join
    stays NULL. The Elron raudteemüra-ööaknad slice belongs to its
    owner (dims_p4_elron).
    """
    if not origin or pois is None:
        return None, ("Sadama/lennu ajakavamüra info puudub (EI OLE "
                      "EANS/Sadama/Männiku teatekalendri liidestust "
                      "hetktõmmes)")
    now = _today_iso(today)
    hits = _in_window(origin, "schednuisance_eans", pois, NUISANCE_WINDOW_M)
    if not hits:
        return None, ("Läheduses pole sadama/lennu müra teate kirjet - "
                      "hinnangut pole (EI OLE teatekalendri liidestust, "
                      "mitte mõõdetud vaikus)")
    active = [(d, p) for d, p in hits
              if _window_state(p.get("start"), p.get("end"), now)
              == "active"]
    if active:
        nearest_m = min(d for d, _ in active)
        latest_end = max(str(p["end"]) for _, p in active)
        labels = sorted({str(p.get("label", "teade")) for _, p in active})
        return NUISANCE_ACTIVE_SCORE, (
            "Sadama/lennu müra hinnang: %d kehtivat teadet 2 km puhvris "
            "(lähim %s, kehtib kuni %s: %s) -> skoor %d"
            % (len(active), _fmt_m(nearest_m), latest_end,
               "; ".join(labels[:3]), NUISANCE_ACTIVE_SCORE))
    states = {_window_state(p.get("start"), p.get("end"), now)
              for _, p in hits}
    if states <= {"expired", None} and "expired" in states:
        return None, ("Lähedased sadama/lennu teated on aegunud - hinnangut "
                      "pole (EI OLE kehtivat teadet, mitte mõõdetud "
                      "vaikus)")
    if states <= {"future", None} and "future" in states:
        earliest = min(str(p["start"]) for _, p in hits
                       if isinstance(p.get("start"), str)
                       and _ISO_RE.match(p["start"]))
        return None, ("Lähedased sadama/lennu häiringud algavad %s - mõju "
                      "algab siis (EI OLE veel kehtivat teadet)" % earliest)
    return None, ("Lähedased sadama/lennu teated on kuupäevata - rütmi ei "
                  "saa lugeda (EI OLE kehtivat teatekalendrit)")


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_EANS_DIMS = (
    ("airport_noise_eans", "P4-023", dim_airport_noise_zone),
    ("harbour_air_calendar", "P4-055", dim_harbour_air_calendar),
)


def score_p4_eans(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]],
                  today: Today = None) -> Dict[str, Optional[int]]:
    """Both P4 EANS dims for one listing (entry point for the follow-up)."""
    return {key: (fn(origin, pois, today)
                  if fn is dim_harbour_air_calendar
                  else fn(origin, pois))[0]
            for key, _, fn in P4_EANS_DIMS}
