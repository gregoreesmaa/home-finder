"""P4 citynotices dims (issues #283 demo + #357 coverage): tallinn.ee
operational-notices ingestion + two calendar dims off that source.

Demo param (this ingestion's anchor):
* P4-014 Rail Baltica / tram construction phase -> dim_construction_phase

Coverage param (extends the demoed ingestion, no new plumbing):
* P4-018 Snow/road maintenance class -> dim_snow_notices

OPENNESS VERDICT (checked 2026-09-13, 9 single GETs total, custom UA,
30 s timeout, /tmp/hf-p4-citynotices cache kept for the PR record,
never committed; no retries - HTTP 429/errors are a stop signal):
* OPEN as server-rendered HTML (keyless, no auth): www.tallinn.ee root
  301s to /et (HTTP 200, 137 KB, Cloudflare + CMS). The traffic-services
  page /et/teenused-ja-teave/transport-liiklus (HTTP 200, 124 KB) links
  the snow page /et/lumi (HTTP 200, 57 KB: "Tallinna tänavate
  talihooldus 2025/2026", city clears all city-owned streets, links
  https://gis.tallinn.ee/lumekaart/) and the weekly news listing
  /et/uudised?news_heading=7465 (HTTP 200, 146 KB) with dated weekly
  slugs (/et/uudis/eelinfo-14-20-september, ...-7-september-13-
  september, ... back to 13-19-juuli). One detail page
  /et/uudis/eelinfo-14-20-september (HTTP 200, 135 KB) is plain dated
  weekday blocks ("Teisipäev, 15. september 9.00 ...").
* HONESTY LIMIT on the above: the observed eelinfo items are district-
  elder EVENT AGENDAS (linnaosavanemate eelinfo), not road-closure
  notices - the readers below parse the dated-listing structure, they
  do NOT claim an agenda item is a closure. Works/snow semantics arrive
  only via explicitly dated entries with street labels.
* DATED NEGATIVE (keeps verdict): a keyless MACHINE feed for
  closures/construction/snow-clearing rows. /avaandmed/ (HTTP 200,
  75 KB) is a "Teabevärav" JS shell with no server-rendered datasets;
  opendata.tallinn.ee is DNS NXDOMAIN (per the TLT module); the
  lumekaart and veebikaart map apps (HTTP 200, ~5 KB each) are ArcGIS
  Web AppBuilder shells - service URLs live in app config, not
  confirmed (chasing them would exceed a polite probe budget); Tark Tee
  incident feeds need a registered key (per the trans module). Row-
  level notice joins are therefore proven on fixtures only.
* GEOCODE GAP (explicit integration step): notices name STREETS
  ("Kivila tn 19" style), never coordinates. Readers keep raw street
  labels + ISO dates and NEVER fake WGS84; addresses become POIs via
  the ADS/Maa-amet geocode step on the first full pull (same precedent
  as the trans module's deferred L-EST97 -> WGS84 projection).
  Fixtures carry WGS84 directly.

HONESTY (AGENTS.md section 7.2): both dims are calendar dims with
expiry (parameters4.md P4-014 shape), never distance gradients -
distance only gates the join window, the score comes from the dated
entry alone. Every scored reason says "hinnang" and prints its
components including the expiry date; every NULL reason says "EI OLE"
and names the missing input. Transport errors are never cached as
data (fetch_cached stores only HTTP 200 bodies over a minimum size).
Measured zero is not applicable here (notices are dated events, not
exhaustive calendars): an empty/expired buffer stays NULL (unknown,
never "quiet"); a future-dated entry stays NULL (impact starts on its
start date - no premium faked from a plan).

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_cached(url, cache_dir, filename, ttl_s): polite pull, one GET
  with an identifying UA and a 30 s timeout; cache hit within TTL
  makes NO request; single attempt, no retries. Network lives ONLY
  here; readers, scorers and tests never touch it.
* parse_notice_index: uudised-listing HTML -> [{slug, url, title}]
  (observed anchor shape /et/uudis/<slug>, pinned by test).
* parse_notice_detail: detail HTML -> [{weekday, date_label, text}]
  (observed "Teisipäev, 15. september 9.00 ..." blocks).
* parse_ee_daterange: "14. - 20. september" + year -> ISO (start, end);
  unknown month or dayless label -> (None, None), never guessed.
* parse_snow_info: /et/lumi HTML -> {season, lumekaart_url}
  (observed "2025/2026" + lumekaart link).

Style mirrors services/scoring/dims_p4_trans.py (#275/#349): pure
scorers (origin, pois[, today]) -> (Optional[int 0..100], Estonian
reason), local helpers (no livability import - importing it here
would turn the future central hook into a cycle, same precedent as
PRs #100/#106/#115). No Overpass fragment is staged: positions
arrive via the geocoded notice join, not via snapshot tags, so there
is nothing honest for the live path to fetch - stated, not omitted.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #357's body states
  it "extend[s] the demoed ingestion ... no new plumbing expected":
  dim_snow_notices reuses fetch_cached plus the buffer/expiry shapes,
  reading its own POI kind - no second source is pulled.
* Per-source slices, not full params: P4-014 keeps the RB Rail /
  tram-timetable, EHR-corridor and Elron slices for their owners -
  this module adds ONLY the tallinn.ee notice leg. P4-018 keeps the
  trans road-class band, the OSM winter_service NULL and the TLT
  winter-ops NULL; this module adds ONLY the tallinn.ee snow-notice
  leg. Distinct dim keys throughout so the central hook can weight
  slices independently.
* A published snow-clearing notice scores as temporary exposure (45),
  NOT as network membership: city practice ("viime lumi, teisalda
  auto") restricts parking during clearing ops, so the notice states
  nuisance, never coverage. No coverage band is faked from it.
* Future-dated entries stay NULL with their start date in the reason:
  scoring a plan as "premium later" would fake the premium half of
  the Buy Q ("dust 2 yrs, value later?") from a date alone.
* today is an optional third scorer arg (date or YYYY-MM-DD, default
  date.today()) so the expiry logic is hermetic in tests and live-
  honest in production; the central hook keeps calling (origin, pois).

Integration (deliberately NOT done here): ADS/Maa-amet geocoding of
street labels -> WGS84, splicing POI kinds into livability, and
rebalancing livability.WEIGHTS must be one joint change across all
batches - existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling. No shared files touched:
3 new files only.
"""

import datetime
import math
import os
import re
import time
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple, Union

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Weekly notice listing (verified 2026-09-13: HTTP 200, 146 KB
#: server-rendered HTML with dated /et/uudis/<slug> items).
NOTICE_INDEX_URL = "https://www.tallinn.ee/et/uudised?news_heading=7465"

#: Snow-maintenance page (verified 2026-09-13: HTTP 200, 57 KB,
#: "Tallinna tänavate talihooldus 2025/2026" + lumekaart link).
SNOW_INFO_URL = "https://www.tallinn.ee/et/lumi"

#: Weekly eelinfo cadence: at most one index refresh per 7 d per cache
#: dir (daily cron would only re-check, never re-pull inside TTL).
NOTICES_TTL_S = 7 * 24 * 3600

#: Snow info is seasonal (autumn refresh per P4-018): at most one
#: refresh per 30 d per cache dir outside the season rollover.
SNOW_TTL_S = 30 * 24 * 3600

#: Identifying user agent for the polite pull (single GET, no scrape).
CITYNOTICES_UA = (
    "home-finder citynotices openness-check (weekly index max, no scrape)"
)

#: Minimum plausible page body: the live listing/detail pages are
#: 50-150 KB, so anything smaller is an error page, never data.
HTML_MIN_BYTES = 1024

#: Detail-item URL shape observed live 2026-09-13
#: (/et/uudis/eelinfo-14-20-september, ...).
NOTICE_HREF_RE = re.compile(r"^/et/uudis/([a-z0-9-]+)/?$")

#: Season label observed on /et/lumi ("2025/2026").
SEASON_RE = re.compile(r"\b(20\d{2})/(20\d{2})\b")

#: Estonian month names -> month number (for the calendar readers).
EE_MONTHS = {
    "jaanuar": 1, "veebruar": 2, "märts": 3, "aprill": 4,
    "mai": 5, "juuni": 6, "juuli": 7, "august": 8,
    "september": 9, "oktoober": 10, "november": 11, "detsember": 12,
}

#: "14. - 20. september" / "15. september" / "14.-20. september".
DATERANGE_RE = re.compile(
    r"(\d{1,2})\.\s*(?:[–\-]\s*(\d{1,2})\.\s*)?([a-zõäöü]+)",
    re.IGNORECASE,
)

#: ISO calendar dates carried by geocoded notice POIs.
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = NOTICES_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise one GET with CITYNOTICES_UA and a 30 s timeout; the body
    is stored only on HTTP 200 with at least HTML_MIN_BYTES bytes,
    else None is returned and nothing is cached (transport errors are
    never data). No retries - HTTP 429/errors are a stop signal.
    Scorers and readers never call this; tests cover the cache-hit
    and error paths with a stubbed opener, never the network.
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
        req = urllib.request.Request(url,
                                     headers={"User-Agent": CITYNOTICES_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < HTML_MIN_BYTES:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached pages (pure; shapes pinned by tests on
# fixtures mirroring the live bytes observed 2026-09-13).
# ---------------------------------------------------------------------------

class _NoticeIndexParser(HTMLParser):
    """Collect /et/uudis/<slug> anchors with their link text. Pure."""

    def __init__(self) -> None:
        super().__init__()
        self.items: List[dict] = []
        self._href: Optional[str] = None
        self._text: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        self._href = href if NOTICE_HREF_RE.match(href) else None
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            m = NOTICE_HREF_RE.match(self._href)
            assert m is not None
            title = " ".join("".join(self._text).split())
            if title:
                self.items.append({"slug": m.group(1),
                                   "url": self._href, "title": title})
            self._href = None
            self._text = []


def parse_notice_index(html: str) -> List[dict]:
    """Notice-listing HTML -> [{slug, url, title}]. Offline.

    Mirrors the live /et/uudised listing (dated /et/uudis/<slug>
    anchors). Structure only: whether an item is a works notice or
    an event agenda is decided from its dated detail entries, never
    from the slug.
    """
    parser = _NoticeIndexParser()
    parser.feed(html)
    return parser.items


class _NoticeDetailParser(HTMLParser):
    """Collect visible text in document order. Pure."""

    def __init__(self) -> None:
        super().__init__()
        self.chunks: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = " ".join(data.split())
            if text:
                self.chunks.append(text)


#: Weekday headings observed in live detail pages.
EE_WEEKDAYS = ("Esmaspäev", "Teisipäev", "Kolmapäev", "Neljapäev",
               "Reede", "Laupäev", "Pühapäev")


def parse_notice_detail(html: str) -> List[dict]:
    """Detail HTML -> [{weekday, date_label, text}]. Offline.

    Mirrors the live eelinfo shape ("Teisipäev, 15. september 9.00
    ..."): each weekday-headed block becomes one dated entry with
    its raw Estonian date label kept (ISO normalisation is
    parse_ee_daterange's job, with an explicit year).
    """
    parser = _NoticeDetailParser()
    parser.feed(html)
    text = " ".join(parser.chunks)
    entries = []
    pat = re.compile(
        r"(Esmaspäev|Teisipäev|Kolmapäev|Neljapäev|Reede|Laupäev|Pühapäev)"
        r"\s*,?\s*(\d{1,2}\.\s*[a-zõäöü]+(?:\s*\d{4})?)",
        re.IGNORECASE,
    )
    marks = list(pat.finditer(text))
    for i, m in enumerate(marks):
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks)
                    else len(text)].strip()
        if body:
            entries.append({"weekday": m.group(1),
                            "date_label": m.group(2).strip(), "text": body})
    return entries


def parse_ee_daterange(label: str, year: int) -> Tuple[Optional[str],
                                                      Optional[str]]:
    """Estonian date-range label + explicit year -> (start, end) ISO.

    "14. - 20. september" + 2026 -> ("2026-09-14", "2026-09-20");
    "15. september" -> that single day twice. Unknown month, dayless
    label or impossible date -> (None, None): never guessed, the
    caller keeps such entries dateless (they can never score).
    """
    m = DATERANGE_RE.search(label)
    if not m:
        return None, None
    month = EE_MONTHS.get(m.group(3).lower())
    if month is None:
        return None, None
    try:
        start = datetime.date(year, month, int(m.group(1)))
        end = datetime.date(year, month, int(m.group(2) or m.group(1)))
    except ValueError:
        return None, None
    if end < start:
        return None, None
    return start.isoformat(), end.isoformat()


def parse_snow_info(html: str) -> Dict[str, Optional[str]]:
    """Snow page HTML -> {season, lumekaart_url}. Offline.

    Mirrors /et/lumi ("Tallinna tänavate talihooldus 2025/2026" +
    the lumekaart href). No per-street levels are published in the
    page HTML - the map app is the JS shell gated in the verdict -
    so this reader reports the season window only, never a street
    class.
    """
    m = SEASON_RE.search(html)
    season = "%s/%s" % (m.group(1), m.group(2)) if m else None
    lum = re.search(r'href="([^"]*lumekaart[^"]*)"', html)
    return {"season": season,
            "lumekaart_url": lum.group(1) if lum else None}


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

#: P4-014 construction-notice buffer: dated works within 500 m count.
CONSTR_WINDOW_M = 500.0
#: Active dated works nearby: flat nuisance exposure (never a gradient;
#: the "premium later" half needs timetables this source has no rows).
CONSTR_ACTIVE_SCORE = 45
#: P4-018 snow-notice buffer: dated clearing ops within 500 m count.
SNOW_WINDOW_M = 500.0
#: Active dated clearing op nearby: flat exposure (parking/move-car
#: nuisance during the op - never faked as network membership).
SNOW_ACTIVE_SCORE = 45


# ---------------------------------------------------------------------------
# P4-014: Rail Baltica / tram construction phase, notice leg (demo).
# ---------------------------------------------------------------------------

def dim_construction_phase(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]],
                           today: Today = None) -> Score:
    """P4-014: dated-works calendar dim with expiry (high = calmer now).

    Only the tallinn.ee notice leg: constr_notice_p4 POIs carry the
    geocoded street plus the ISO start/end of the works notice. An
    in-effect entry in the buffer scores a flat exposure; expired,
    future-dated and dateless entries stay NULL (unknown, never
    quiet); no join stays NULL. The RB Rail / tram-timetable,
    EHR-corridor and Elron slices belong to their owners.
    """
    if not origin or pois is None:
        return None, ("Ehitusfaasi info puudub (EI OLE tallinn.ee "
                      "teateliidestust hetktõmmes)")
    now = _today_iso(today)
    hits = _in_window(origin, "constr_notice_p4", pois, CONSTR_WINDOW_M)
    if not hits:
        return None, ("Läheduses pole ehitusteate kirjet - hinnangut "
                      "pole (EI OLE teateteliidestust, mitte mõõdetud "
                      "vaikus)")
    active = [(d, p) for d, p in hits
              if _window_state(p.get("start"), p.get("end"), now)
              == "active"]
    if active:
        nearest_m = min(d for d, _ in active)
        latest_end = max(str(p["end"]) for _, p in active)
        labels = sorted({str(p.get("label", "teade")) for _, p in active})
        return CONSTR_ACTIVE_SCORE, (
            "Ehitusfaasi hinnang: %d kehtivat teadet 500 m puhvris "
            "(lähim %s, kehtib kuni %s: %s) -> skoor %d"
            % (len(active), _fmt_m(nearest_m), latest_end,
               "; ".join(labels[:3]), CONSTR_ACTIVE_SCORE))
    states = {_window_state(p.get("start"), p.get("end"), now)
              for _, p in hits}
    if states <= {"expired", None} and "expired" in states:
        return None, ("Lähedased ehitusteaded on aegunud - hinnangut "
                      "pole (EI OLE kehtivat teadet, mitte mõõdetud "
                      "vaikus)")
    if states <= {"future", None} and "future" in states:
        earliest = min(str(p["start"]) for _, p in hits
                       if isinstance(p.get("start"), str)
                       and _ISO_RE.match(p["start"]))
        return None, ("Lähedased ehitustööd algavad %s - mõju algab "
                      "siis (EI OLE veel kehtivat teadet)" % earliest)
    return None, ("Lähedased ehitusteaded on kuupäevata - faasi ei saa "
                  "lugeda (EI OLE kehtivat teadet)")


# ---------------------------------------------------------------------------
# P4-018: snow/road maintenance class, notice leg (coverage param).
# ---------------------------------------------------------------------------

def dim_snow_notices(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]],
                     today: Today = None) -> Score:
    """P4-018: dated snow-op calendar dim with expiry (high = calmer).

    Only the tallinn.ee notice leg: snow_notice_p4 POIs carry the
    geocoded street plus the ISO start/end of the clearing-op notice
    (lumekoristuse teade). An in-effect op in the buffer scores a
    flat exposure; expired, future-dated and dateless entries stay
    NULL; no join stays NULL (unknown, never "winter trap"). The
    teeregister/talihooldus class band lives in dims_p4_trans, the
    OSM winter_service and TLT winter-ops NULLs stay their own.
    """
    if not origin or pois is None:
        return None, ("Lumekoristuse info puudub (EI OLE tallinn.ee "
                      "teateliidestust hetktõmmes)")
    now = _today_iso(today)
    hits = _in_window(origin, "snow_notice_p4", pois, SNOW_WINDOW_M)
    if not hits:
        return None, ("Läheduses pole lumeteate kirjet - hinnangut "
                      "pole (EI OLE teateteliidestust, mitte mõõdetud "
                      "lumetu tee)")
    active = [(d, p) for d, p in hits
              if _window_state(p.get("start"), p.get("end"), now)
              == "active"]
    if active:
        nearest_m = min(d for d, _ in active)
        latest_end = max(str(p["end"]) for _, p in active)
        return SNOW_ACTIVE_SCORE, (
            "Lumekoristuse hinnang: %d kehtivat teadet 500 m puhvris "
            "(lähim %s, kehtib kuni %s) -> skoor %d"
            % (len(active), _fmt_m(nearest_m), latest_end,
               SNOW_ACTIVE_SCORE))
    states = {_window_state(p.get("start"), p.get("end"), now)
              for _, p in hits}
    if states <= {"expired", None} and "expired" in states:
        return None, ("Lähedased lumeteated on aegunud (hooaeg "
                      "lõppenud) - hinnangut pole (EI OLE kehtivat "
                      "teadet)")
    if states <= {"future", None} and "future" in states:
        earliest = min(str(p["start"]) for _, p in hits
                       if isinstance(p.get("start"), str)
                       and _ISO_RE.match(p["start"]))
        return None, ("Lähedased lumetööd algavad %s - mõju algab "
                      "siis (EI OLE veel kehtivat teadet)" % earliest)
    return None, ("Lähedased lumeteated on kuupäevata - rütmi ei saa "
                  "lugeda (EI OLE kehtivat teadet)")


#: Registry for the central weight-rebalance follow-up: (dim key, param).
P4_CITYNOTICES_DIMS = (
    ("constr_phase", "P4-014", dim_construction_phase),
    ("snow_notices", "P4-018", dim_snow_notices),
)


def score_p4_citynotices(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]],
                         today: Today = None) -> Dict[str, Optional[int]]:
    """P4 citynotices dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois, today)[0] for key, _, fn in
            P4_CITYNOTICES_DIMS}
