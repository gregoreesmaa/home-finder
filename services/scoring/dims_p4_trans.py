"""P4 trans dims (issues #275 demo + #349 coverage): Transpordiamet accident
ingestion + seven coverage params off the same source family.

Demo param (this ingestion's anchor):
* P4-012 Traffic-accident blackspots + rescue drive-time -> dim_accident_blackspots

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-018 Snow/road maintenance class -> dim_winter_road_class
* P4-023 Airport + military noise zones -> dim_noise_zone_trans
* P4-026 Municipal fix-it responsiveness -> dim_fixit_response
* P4-037 Policy exposure, restriction leg -> dim_policy_restrictions
* P4-046 Dread removal, 2nd-exit leg -> dim_dread_egress
* P4-047 Small horrors, event-traffic leg -> dim_horrors_events
* P4-054 Quarry blast + truck season, truck-route leg -> dim_quarry_trucks

OPENNESS VERDICT (checked 2026-09-13, 12 tiny requests total, custom UA,
one HEAD/GET each, /tmp/hf-p4-trans cache kept for the PR record, never
committed):
* OPEN (keyless): andmed.eesti.ee dataset metadata API
  ``/api/datasets/slug/inimkannatanutega-liiklusonnetuste-andmed`` ->
  HTTP 200 application/json, 6783 B, access PUBLIC, accrual MONTHLY,
  licence CC_BY_3.0, org Transpordiamet (statistical owner; collection:
  PPA). Distributions include ``lo_2011_2026.csv`` via a Transpordiamet
  pilv share link. Ranged peek (bytes 0-2500) -> HTTP 206 text/csv,
  ``;``-delimited header ending in ``X koordinaat;Y koordinaat``; first
  data row is Tallinn / Põhja-Tallinn / Sepa tn, so the Tallinn
  (Omavalitsus) filter is proven on live bytes. Old host
  avaandmed.eesti.ee 301s to andmed.eesti.ee (catalogue page itself is a
  JS shell, "Teabevärav" only server-rendered - the API is the honest
  entry point, not the HTML page).
* DATED NEGATIVE (keeps verdict per #275): Tark Tee incidents /
  restrictions / truck traffic have no keyless machine-readable feed.
  tarktee.ee root -> HTTP 200 but a 66 KB driver-app shell with zero
  api/datex/avaandmed/download/wfs/rest links; the legacy ArcGIS public
  endpoint tarktee.mnt.ee 301s to tarktee.transpordiamet.ee (host moved,
  no documented keyless JSON-shape re-probed to stay polite); the DATEX II
  profile doc exists but consumer reports note the SRTI hazard feeds need
  a registered key. Incident/restriction/truck legs therefore stay NULL
  with an Estonian EI OLE reason until a keyless shape is confirmed.
* DATED NEGATIVE (keeps verdict): pullable noise zones. Tallinn's
  map-applications page (HTTP 200, 141 KB) names no müra/noise download -
  strategic END maps are viewer pages, EANS zones are not an open feed.
  The zone join below is proven on fixtures only.
* NOT OPEN as row-level feeds (EI OLE legs, named in reasons):
  Päästeamet komando drive-time, teeregister maintenance classes,
  Tallinna talihoolduse tasemed, quarry blast timetables, automaks
  calculator internals (EMTA module owns that slice).

CRS CAVEAT (verified on live bytes, reviewable): X/Y koordinaat are
L-EST97 metres (e.g. 6589196.459 / 568050.8757 on a 2025 Harju row), NOT
WGS84 - and older rows (e.g. the 2011 Tallinn/Sepa row) have EMPTY X/Y.
The offline reader keeps raw x/y and SKIPS rows without finite
coordinates (never faked); projection L-EST97 -> WGS84 is an explicit
integration step on the first full pull (Maa-amet converter/GDAL), after
which accident_pois_from_points maps projected points. Fixtures carry
WGS84 directly. TTL: accidents monthly (portal accrualPeriodicity),
Tark Tee incident shapes daily-on-reopen, noise END-cycle.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components; every NULL reason says "EI OLE"
and names the missing input. Transport errors are never cached as data
(fetch_cached stores only HTTP 200 bodies over a minimum size, else
returns None). Measured zero is handled per param: a joined count of 0
from an exhaustive list (event calendars) scores high, while a missing
join (None) stays NULL; for the casualty-only accident register, an
empty buffer stays NULL (absence from a casualty register is not a
safety verdict - stated, not hidden). No distance gradients on zone
params (P4-023 distance only gates the join window, the score comes from
the zone label alone).

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_cached(url, cache_dir, filename, ttl_s): polite pull, one GET
  with an identifying UA and a 30 s timeout; cache hit within TTL makes
  NO request; single attempt, no retries (HTTP 429 is a stop signal,
  AGENTS.md 7.4). Network lives ONLY here; scorers and tests never touch
  it.
* parse_accidents_csv / tallinn_accidents / accident_severity /
  accident_pois_from_points: pure offline readers over the cached CSV
  (``;``-delimited, utf-8-sig, real header pinned by test).

Style mirrors services/scoring/dims_p4_peatus.py (#314/#376): pure
scorers (origin, pois) -> (Optional[int 0..100], Estonian reason), local
helpers (no livability import - importing it here would turn the future
central hook into a cycle, same precedent as PRs #100/#106/#115). No
Overpass fragment is staged: positions arrive via the CSV join, not via
snapshot tags, so there is nothing honest for the live path to fetch -
stated, not omitted by accident.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #349's body states it
  "extends the demoed ingestion ... no new plumbing expected": the seven
  coverage dims reuse fetch_cached plus the point-buffer / zone-join
  shapes, each reading its own POI kind - no second source is pulled.
* Per-source slices, not full params: P4-037 keeps the EMTA automaks
  slice (dims_p4_emta) and the peatus GTFS offset slice; this module adds
  only the Transpordiamet restriction leg. P4-046 keeps the EHR
  heat-redundancy slice and the Elektrilevi backup-feed NULL; this
  module adds only the teeregister 2nd-exit leg. P4-047 keeps the kudocs
  KU-complaint slice; this module adds only the event-traffic leg.
  P4-054 keeps the maa-subsurface deposit-buffer slice; this module adds
  only the truck-route leg. P4-018 keeps the OSM winter_service NULL;
  this module adds the road-class band. P4-023 keeps the EHR NULL; this
  module adds the zone band. P4-026 keeps the arireg cost-echo NULL;
  this module adds the hex-rate band. Distinct dim keys throughout so
  the central hook can weight slices independently.
* Empty accident buffer is NULL, not "safe": the register holds only
  casualty accidents (2011+), so zero nearby is unknown. The rescue
  drive-time half is EI OLE in every P4-012 reason (scored reasons say
  "päästeaeg liidestamata", never a faked time).
* Winter classes 1-4 are fixture codelist positions (1 = best); they
  MUST be remapped to the real teeregister/talihooldus codelist on the
  first pull (docs/p4_trans.md checklist) - stated in the reason via
  "hooldusklass".
* Quarry in-window scores a flat exposure (45): the blast timetable is
  EI OLE, so no seasonal band is faked from a buffer distance.

Integration (deliberately NOT done here): projecting L-EST97 -> WGS84,
splicing POI kinds into livability, and rebalancing livability.WEIGHTS
must be one joint change across all batches - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. No shared files touched: 3 new files only.
"""

import csv
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Dataset metadata API (keyless, verified 2026-09-13: HTTP 200 JSON,
#: access PUBLIC, accrual MONTHLY, CC_BY_3.0, org Transpordiamet).
ACCIDENTS_META_URL = (
    "https://andmed.eesti.ee/api/datasets/slug/"
    "inimkannatanutega-liiklusonnetuste-andmed"
)

#: Accident CSV distribution (keyless, verified 2026-09-13: HTTP 206
#: text/csv on a bytes 0-2500 peek, ``;``-delimited, X/Y koordinaat in
#: L-EST97, Tallinn filter proven on the first live row).
ACCIDENTS_CSV_URL = (
    "https://pilv.transpordiamet.ee/s/Iiee4OAYFq4lT1v/download"
    "?path=%2F&files=lo_2011_2026.csv"
)

#: Portal accrual is MONTHLY: at most one metadata/CSV refresh per 30 d
#: per cache dir (daily cron would only re-check, never re-pull inside TTL).
ACCIDENTS_TTL_S = 30 * 24 * 3600

#: Tark Tee incident/restriction shapes, if a keyless feed is ever
#: confirmed, would refresh daily; until then the TTL only documents the
#: intended cadence (feeds gated, see module docstring).
TARKTEE_TTL_S = 24 * 3600

#: Identifying user agent for the polite pull (single GET, no scrape).
TRANS_UA = "home-finder trans openness-check (monthly CSV max, no scrape)"

#: Minimum plausible CSV body: the live header alone is ~1.4 KB, so
#: anything smaller is an error page, never data.
CSV_MIN_BYTES = 1024


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = ACCIDENTS_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with TRANS_UA and a 30 s timeout; the body is stored only on
    HTTP 200 with at least CSV_MIN_BYTES bytes, else None is returned
    and nothing is cached (transport errors are never data). No retries
    - HTTP 429/errors are a stop signal. Scorers never call this; tests
    cover the cache-hit and error paths with a stubbed opener, never
    the network.
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
        req = urllib.request.Request(url, headers={"User-Agent": TRANS_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < CSV_MIN_BYTES:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached accident CSV (pure; real header shape).
# ---------------------------------------------------------------------------

#: Municipality value marking Tallinn rows in the live CSV ("Omavalitsus").
TALLINN_COMMUNE = "Tallinn"


def parse_accidents_csv(path: str) -> List[dict]:
    """Parse the cached Transpordiamet casualty-accident CSV. Offline.

    ``;``-delimited, utf-8-sig (live header verified 2026-09-13 via a
    2.5 KB range peek). Returns raw row-dicts; no filtering, no
    projection - callers apply tallinn_accidents and the L-EST97 -> WGS84
    step documented above.
    """
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def tallinn_accidents(rows: List[dict]) -> List[dict]:
    """Keep Tallinn-municipality rows (Omavalitsus == Tallinn). Pure."""
    return [r for r in rows if r.get("Omavalitsus") == TALLINN_COMMUNE]


def accident_severity(row: dict) -> int:
    """Severity weight: 3 per death + 1 per injured; garbage -> 0. Pure."""
    def _num(key: str) -> int:
        v = row.get(key)
        if isinstance(v, bool):
            return 0
        try:
            n = int(str(v).strip())
        except (TypeError, ValueError, AttributeError):
            return 0
        return n if n > 0 else 0
    return 3 * _num("Hukkunuid") + _num("Vigastatuid")


def accident_pois_from_points(points: List[dict]) -> List[dict]:
    """Projected accident points -> scorer POIs. Pure.

    Points carry WGS84 ``lat``/``lon`` (projection happens upstream, see
    the CRS caveat) plus ``dead``/``injured`` ints and a ``year``. Rows
    without finite coordinates are skipped, never faked; severity is
    recomputed here so scorer and reader agree.
    """
    pois = []
    for pt in points:
        try:
            lat = float(pt["lat"])
            lon = float(pt["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(pt.get("lat"), bool) or isinstance(pt.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        dead = pt.get("dead")
        injured = pt.get("injured")
        dead = dead if isinstance(dead, int) and dead >= 0 else 0
        injured = injured if isinstance(injured, int) and injured >= 0 else 0
        pois.append({"kind": "accident_p4", "lat": lat, "lon": lon,
                     "dead": dead, "injured": injured,
                     "sev": 3 * dead + injured,
                     "year": pt.get("year")})
    return pois


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


def _int(poi: dict, key: str) -> Optional[int]:
    """Sanitised non-negative int: bool/negative/garbage -> None. Pure."""
    v = poi.get(key)
    if isinstance(v, bool):
        return None
    try:
        n = int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _label(poi: dict, key: str, allowed: Tuple[str, ...]) -> Optional[str]:
    """Sanitised codelist label: exact match only, else None. Pure."""
    v = poi.get(key)
    return v if isinstance(v, str) and v in allowed else None


def _nearest(origin: Tuple[float, float], kind: str,
             pois: List[dict]) -> Optional[Tuple[float, dict]]:
    """(distance_m, poi) of the nearest well-formed POI of kind, else None."""
    best = None
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != kind:
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


def _in_window(origin: Tuple[float, float], kind: str,
               pois: List[dict], window_m: float) -> List[Tuple[float, dict]]:
    """All well-formed POIs of kind within window_m, with distances. Pure."""
    out = []
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != kind:
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
        if d <= window_m:
            out.append((d, p))
    return out


# ---------------------------------------------------------------------------
# Windows + bands (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: P4-012 blackspot buffer: casualty accidents within 300 m count.
BLACKSPOT_WINDOW_M = 300.0
#: Buffer severity sum (3/death + 1/injured) -> score (high = calmer).
BLACKSPOT_BANDS = [(1, 65), (3, 50), (6, 35), (float("inf"), 20)]
#: P4-018 road-class join reads the parcel's street within 150 m.
WINTER_WINDOW_M = 150.0
#: P4-018 fixture codelist positions (1 = best winter class).
WINTER_CLASSES = ("1", "2", "3", "4")
#: P4-018 hooldusklass -> score (high = better winter maintenance).
WINTER_BANDS = {"1": 85, "2": 65, "3": 45, "4": 30}
#: P4-023 zone join window (gates the join only, never gradients).
NOISE_WINDOW_M = 1000.0
#: P4-023 zone labels -> score (high = quieter zone).
NOISE_ZONE_SCORES = {"lennumüra": 35, "õppus": 50, "sadam": 60}
#: P4-026 hex window (one hex responsiveness readout per listing).
FIXIT_WINDOW_M = 500.0
#: P4-026 fix-it rate -> score (high = responsive); needs n >= 5 reports.
FIXIT_MIN_N = 5
FIXIT_BANDS = [(0.5, 40), (0.8, 60), (float("inf"), 80)]
#: P4-037 restriction-exposure window.
RESTRICTION_WINDOW_M = 500.0
#: P4-037 restriction kind -> exposure score (high = less exposed).
RESTRICTION_SCORES = {"sulgemine": 45, "piirang": 55, "tasuline": 60}
#: P4-046 2nd-exit check window (fringe-parcel egress).
EGRESS_WINDOW_M = 300.0
#: P4-046 exit count -> redundancy score.
EGRESS_SCORES = {0: 30, 1: 55}
EGRESS_TWO_PLUS = 85
#: P4-047 event-traffic calendar window.
EVENT_WINDOW_M = 500.0
#: P4-047 event days/year on the street -> score (high = calmer street).
EVENT_BANDS = [(0, 80), (5, 60), (float("inf"), 40)]
#: P4-054 truck-route buffer (Maardu/Harku fringe exposure).
TRUCK_WINDOW_M = 1000.0
#: P4-054 in-buffer exposure (flat: the blast timetable is EI OLE).
TRUCK_SCORE = 45


# ---------------------------------------------------------------------------
# P4-012: accident blackspots + rescue drive-time (demo param).
# ---------------------------------------------------------------------------

def dim_accident_blackspots(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-012: casualty-accident buffer band (high = calmer crossing).

    Point-buffer join over the Transpordiamet casualty register
    (Tallinn rows, projected WGS84): severity summed in a 300 m buffer.
    An empty buffer stays NULL - the register holds only casualty
    accidents, so zero nearby is unknown, never a safety verdict. The
    Päästeamet drive-time half is not an open feed (päästeaeg
    liidestamata in every reason, never a faked time).
    """
    if not origin or pois is None:
        return None, ("Ohtlike ristmike info puudub (EI OLE Tallinna "
                      "avarii-liidestust hetktõmmes: Transpordiameti CSV "
                      "pole liidestatud või päästeaeg puudub)")
    hits = _in_window(origin, "accident_p4", pois, BLACKSPOT_WINDOW_M)
    if not hits:
        return None, ("Registris pole läheduses inimkannatanutega õnnetust "
                      "- see pole ohutushinnang (EI OLE: register hoiab "
                      "ainult kannatanutega juhtumeid, päästeaeg "
                      "liidestamata)")
    sev = sum(_int(p, "sev") if _int(p, "sev") is not None else 0
              for _, p in hits)
    sev = max(sev, 1)
    s = _band(sev, BLACKSPOT_BANDS)
    assert s is not None
    nearest_m = min(d for d, _ in hits)
    return s, ("Avarii-mustri hinnang: %d kannatanutega õnnetust 300 m "
               "puhvris (raskus %d, lähima %s) -> skoor %d; päästeaeg "
               "liidestamata" % (len(hits), sev, _fmt_m(nearest_m), s))


# ---------------------------------------------------------------------------
# P4-018: snow/road maintenance class (coverage param).
# ---------------------------------------------------------------------------

def dim_winter_road_class(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-018: winter maintenance class band (high = better plowed).

    Per-parcel road-class join: the nearest roadclass_p4 within 150 m
    carries the street's hooldusklass (fixture codelist 1-4, best first;
    remap to the real teeregister/talihooldus codelist on first pull).
    Only this slice - the OSM winter_service NULL stays its own slice.
    """
    if not origin or pois is None:
        return None, ("Talvise hooldusklassi info puudub (EI OLE "
                      "teeregistri/talihoolduse liidestust hetktõmmes)")
    hit = _nearest(origin, "roadclass_p4", pois)
    if hit is None or hit[0] > WINTER_WINDOW_M:
        return None, ("Läheduses pole teelõigu hooldusklassi - hinnangut "
                      "pole (EI OLE liidestatud teeregistrit, mitte "
                      "mõõdetud hooldamata tee)")
    dist_m, poi = hit
    cls = _label(poi, "maint_class", WINTER_CLASSES)
    if cls is None:
        return None, ("Teelõik %s, aga hooldusklass puudub või tundmatu - "
                      "talvist võimet ei saa lugeda (EI OLE klassi "
                      "liidestust)" % _fmt_m(dist_m))
    return WINTER_BANDS[cls], ("Talvise hoolduse hinnang: teelõik %s, "
                               "hooldusklass %s -> skoor %d"
                               % (_fmt_m(dist_m), cls, WINTER_BANDS[cls]))


# ---------------------------------------------------------------------------
# P4-023: airport + military noise zones (coverage param).
# ---------------------------------------------------------------------------

def dim_noise_zone_trans(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-023: strategic-noise zone band (high = quieter zone).

    Zone join, never walk-gradient: the nearest noisezone_p4 within
    1 km carries its containing zone's label (point-in-polygon done
    offline); the score comes from the label alone, distance only gates
    the join. Outside every mapped zone stays NULL (unknown, not quiet).
    Only this slice - the EHR insulation-requirement NULL stays its own.
    """
    if not origin or pois is None:
        return None, ("Mürataseme info puudub (EI OLE strateegilise "
                      "mürakaardi/EANS-tsoonide liidestust hetktõmmes)")
    hit = _nearest(origin, "noisezone_p4", pois)
    if hit is None or hit[0] > NOISE_WINDOW_M:
        return None, ("Aadress pole kaardistatud müratsoonis - hinnangut "
                      "pole (EI OLE tsooniliidestust, mitte mõõdetud "
                      "vaikus)")
    dist_m, poi = hit
    zone = _label(poi, "zone", tuple(NOISE_ZONE_SCORES))
    if zone is None:
        return None, ("Mürakaardi kirje %s, aga tsoonimärgis puudub - "
                      "mürataset ei saa lugeda (EI OLE tsooniliidestust)"
                      % _fmt_m(dist_m))
    s = NOISE_ZONE_SCORES[zone]
    return s, ("Müratsooni hinnang (tsooniliidestus, mitte kaugusgradient): "
               "tsoon %s, kirje %s -> skoor %d"
               % (zone, _fmt_m(dist_m), s))


# ---------------------------------------------------------------------------
# P4-026: municipal fix-it responsiveness (coverage param).
# ---------------------------------------------------------------------------

def dim_fixit_response(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-026: hex fix-it rate band (high = responsive).

    Hex responsiveness rate (fixed/total reports, abiliin/e-teenused
    where published): the nearest fixithex_p4 within 500 m scores when
    it aggregates at least 5 reports; thinner hexes and unpublished
    areas stay NULL. Only this slice - the arireg cost-echo NULL stays
    its own.
    """
    if not origin or pois is None:
        return None, ("Heakorra-kiiruse info puudub (EI OLE abiliini/"
                      "e-teenuste hex-liidestust hetktõmmes)")
    hit = _nearest(origin, "fixithex_p4", pois)
    if hit is None or hit[0] > FIXIT_WINDOW_M:
        return None, ("Läheduses pole heakorra-hexi kirjet - hinnangut "
                      "pole (EI OLE avaldatud raporteid, mitte mõõdetud "
                      "hooldamatus)")
    dist_m, poi = hit
    n = _int(poi, "n")
    rate_raw = poi.get("rate")
    rate = (float(rate_raw) if isinstance(rate_raw, (int, float))
            and not isinstance(rate_raw, bool)
            and math.isfinite(float(rate_raw)) else None)
    if n is None or rate is None or n < FIXIT_MIN_N:
        return None, ("Hex %s, aga raporteid liiga vähe või määr "
                      "puudub - kiirust ei saa lugeda (EI OLE "
                      "piisavat hex-liidestust)" % _fmt_m(dist_m))
    rate = min(max(rate, 0.0), 1.0)
    s = _band(rate, FIXIT_BANDS)
    assert s is not None
    return s, ("Heakorra-kiiruse hinnang: hex %s, %d raportit, "
               "lahendusmäär %.0f%% -> skoor %d"
               % (_fmt_m(dist_m), n, 100 * rate, s))


# ---------------------------------------------------------------------------
# P4-037: policy exposure, restriction leg (coverage param).
# ---------------------------------------------------------------------------

def dim_policy_restrictions(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-037: traffic-restriction exposure band (high = less exposed).

    Only the Transpordiamet restriction leg: the nearest restriction_p4
    within 500 m, labelled by its ``restriction`` field
    (sulgemine/piirang/tasuline from liikluspiirangute teated where
    published - a separate field because ``kind`` is the POI
    discriminator). The automaks slice lives in dims_p4_emta and the
    GTFS alternative slice in dims_p4_peatus - this is never a full
    exposure verdict.
    """
    if not origin or pois is None:
        return None, ("Piirangu-mõjutuse info puudub (EI OLE "
                      "liikluspiirangute liidestust hetktõmmes: Tark Tee "
                      "voog võtmeta)")
    hit = _nearest(origin, "restriction_p4", pois)
    if hit is None or hit[0] > RESTRICTION_WINDOW_M:
        return None, ("Läheduses pole piirangu-kirjet - hinnangut pole "
                      "(EI OLE piiranguliidestust, mitte mõõdetud "
                      "vabadus)")
    dist_m, poi = hit
    kind = _label(poi, "restriction", tuple(RESTRICTION_SCORES))
    if kind is None:
        return None, ("Piirangu-kirje %s, aga liik puudub või tundmatu - "
                      "mõjutust ei saa lugeda (EI OLE piiranguliidestust)"
                      % _fmt_m(dist_m))
    s = RESTRICTION_SCORES[kind]
    return s, ("Piirangu-mõjutuse hinnang (ainult Transpordiameti pool): "
               "kirje %s, liik %s -> skoor %d; automaksu- ja "
               "ühistranspordi-pool liidestamata"
               % (_fmt_m(dist_m), kind, s))


# ---------------------------------------------------------------------------
# P4-046: dread removal, 2nd-exit leg (coverage param).
# ---------------------------------------------------------------------------

def dim_dread_egress(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-046: second-exit redundancy band (high = hard to strand).

    Only the teeregister 2nd-exit leg: the nearest egress_p4 within
    300 m carries the fringe parcel's exit-road count (2+ best). Heat
    redundancy lives in dims_p4_ehr, backup-feed in dims_p4_elektrilevi -
    this is the road-egress leg only, never the full dread verdict.
    """
    if not origin or pois is None:
        return None, ("Varuväljapääsu info puudub (EI OLE teeregistri "
                      "väljapääsu-liidestust hetktõmmes)")
    hit = _nearest(origin, "egress_p4", pois)
    if hit is None or hit[0] > EGRESS_WINDOW_M:
        return None, ("Läheduses pole väljapääsu-kirjet - hinnangut pole "
                      "(EI OLE teeregistri liidestust)")
    dist_m, poi = hit
    exits = _int(poi, "exits")
    if exits is None:
        return None, ("Väljapääsu-kirje %s, aga teede arv puudub - "
                      "dubleeritust ei saa lugeda (EI OLE "
                      "väljapääsu-liidestust)" % _fmt_m(dist_m))
    s = EGRESS_TWO_PLUS if exits >= 2 else EGRESS_SCORES.get(exits, 30)
    return s, ("Varuväljapääsu hinnang (ainult teeregistri pool): kirje "
               "%s, väljapääsuteid %d -> skoor %d"
               % (_fmt_m(dist_m), exits, s))


# ---------------------------------------------------------------------------
# P4-047: small horrors, event-traffic leg (coverage param).
# ---------------------------------------------------------------------------

def dim_horrors_events(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-047: event-traffic calendar band (high = calmer street).

    Only the Transpordiamet/Pääste event-traffic leg: the nearest
    eventtraffic_p4 within 500 m carries event days/year on the street
    (fireworks alleys, race closures). Event calendars are exhaustive
    lists, so a joined 0 is a real calm signal (80); a missing join is
    NULL. The KÜ-complaint slice lives in dims_p4_kudocs.
    """
    if not origin or pois is None:
        return None, ("Üritusliikluse info puudub (EI OLE sündmuste "
                      "liikluskalendri liidestust hetktõmmes)")
    hit = _nearest(origin, "eventtraffic_p4", pois)
    if hit is None or hit[0] > EVENT_WINDOW_M:
        return None, ("Läheduses pole üritusliikluse kirjet - hinnangut "
                      "pole (EI OLE kalendriliidestust)")
    dist_m, poi = hit
    days = _int(poi, "days_per_year")
    if days is None:
        return None, ("Üritusliikluse kirje %s, aga päevade arv puudub - "
                      "rütmi ei saa lugeda (EI OLE kalendriliidestust)"
                      % _fmt_m(dist_m))
    s = _band(days, EVENT_BANDS)
    assert s is not None
    return s, ("Üritusliikluse hinnang (kalendriliidestus): kirje %s, "
               "%d ürituspäeva/aastas -> skoor %d"
               % (_fmt_m(dist_m), days, s))


# ---------------------------------------------------------------------------
# P4-054: quarry blast + truck season, truck-route leg (coverage param).
# ---------------------------------------------------------------------------

def dim_quarry_trucks(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-054: truck-route exposure (flat exposure inside the buffer).

    Only the Transpordiamet truck-route leg: a truckroute_p4 within
    1 km (raskeveokite marsruudid, Maardu/Harku fringe) scores a flat
    exposure - the blast timetable is EI OLE, so no seasonal band is
    faked from a distance. Beyond-buffer stays NULL (unknown, not
    quiet). The deposit-buffer slice lives in dims_p4_maa_subsurface.
    """
    if not origin or pois is None:
        return None, ("Karjääriveo info puudub (EI OLE raskeveokite "
                      "marsruutide liidestust hetktõmmes; lõhkamise "
                      "ajagraafik puudub)")
    hit = _nearest(origin, "truckroute_p4", pois)
    if hit is None or hit[0] > TRUCK_WINDOW_M:
        return None, ("Läheduses pole veomarsruudi kirjet - hinnangut "
                      "pole (EI OLE marsruudiliidestust, mitte mõõdetud "
                      "vaikus)")
    dist_m, _ = hit
    return TRUCK_SCORE, ("Karjääriveo hinnang (marsruudiliidestus, "
                        "tasane: ajagraafik liidestamata): veomarsruut "
                        "%s -> skoor %d" % (_fmt_m(dist_m), TRUCK_SCORE))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_TRANS_DIMS = (
    ("accident_blackspots", "P4-012", dim_accident_blackspots),
    ("winter_road_class", "P4-018", dim_winter_road_class),
    ("noise_zone_trans", "P4-023", dim_noise_zone_trans),
    ("fixit_response", "P4-026", dim_fixit_response),
    ("policy_restrictions", "P4-037", dim_policy_restrictions),
    ("dread_egress", "P4-046", dim_dread_egress),
    ("horrors_events", "P4-047", dim_horrors_events),
    ("quarry_trucks", "P4-054", dim_quarry_trucks),
)


def score_p4_trans(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 trans dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_TRANS_DIMS}

