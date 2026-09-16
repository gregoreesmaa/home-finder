"""P4 events dims (issues #310 demo + #375 coverage): Tallinna
kultuurikalender off the kultuurikava.ee app API + fireworks-leg NULL.

Demo (#310): Tallinna event & fireworks calendars via P4-033 Seasonal
nuisance calendar end-to-end in Tallinn.
Coverage (#375): P4-047 Small horrors calendar, fireworks-alleys slice
— graduated here as a documented NULL: the dig below proves the
kultuurikava API carries no fireworks-permit feed (25 cultural
categories, no ilutulestik), so there is no coverage join to build.

OPENNESS DIG (2026-09-16, AGENTS.md section 7.7 — the 2026-09-13
verdict stopped at the React shell and refused to chase its app API;
section 7.7 reverses that call for keyless endpoints). Polite
evidence, 6 tiny reads + 2 static-asset fetches total (labelled
one-off user-agent `home-finder events dig (issue #310, one-off, ...,
no scrape)`, 2-4 s pacing, `--max-time 25-40`, headers + visible-text
+ bundle-static scope only, no scraping, no auth, no retries — HTTP
429/errors are a stop signal; none hit). Raw bodies kept at
/tmp/hf-dig-events/ (one-off PR record, never committed):
* GET https://kultuurikava.ee/ -> HTTP 200 (1796 B): SPA shell,
  bundle /static/js/main.07d7e3b5.js (same hash as 2026-09-13).
* GET the bundle -> HTTP 200 (1 458 747 B). Static read names the
  backend: REACT_APP_API_URL="https://www.kultuurikava.ee" plus a
  published anonymous client token
  REACT_APP_API_TOKEN="1499ddfb3cb59057a9f201a4e6faf6fe68bde294"
  (embedded in the shipped bundle — every visitor's browser sends it;
  keyless, no login; login-gated /auth, /myprofile, /extranet and the
  :8443 admin "Muuda" edit link are NOT part of this deliverable).
  Public read actions: api/?do=events (city/county/kind/date/keyword
  filters, order/start/limit, format=json), api/?do=getbyurl
  (type=event|place, alias slug), api/?do=categories,
  api/?do=totalevents, utility/?do=notemptycounties.
* GET api/?do=categories&token=<public>&lang=nat&format=json ->
  HTTP 200 (1712 B): 25 cultural categories (Teater, Muusika, Kino,
  Pidu & Klubi, Sport, Pere ja lapsed, Näitus, Mess ja laat,
  Kirjandus, Varia, Kirik, Huvialad (+8 alaliiki), Muu,
  Rahvakultuur, Tants, Ametkondlik, Ajalugu) — NO fireworks /
  ilutulestik / permit category anywhere.
* GET api/?do=events&...&city=tallinn&order=starta&start=0&limit=2&
  format=json&showall=false&alltimes=true&ignoremuseums=true ->
  HTTP 200 (15 357 B): envelope
  {code,message,data:{total,events}} with data.total=1309 upcoming
  Tallinn rows. Row schema: {id, name, start_time, end_time (unix),
  place_id, place_name, place_url, city, county, categories[id],
  isfree, times[], ticketurl[], url, image, ...}. The sample row is a
  multi-year museum exhibition (start 2019, end 2026) — hence the
  scorer counts event STARTS in the window (the season pulse), not
  everything active.
* GET utility/?do=notemptycounties -> HTTP 200 (21 111 B): coverage
  roster incl. Harjumaa (county_internalurl "harjumaa") + its valds
  (Anija, Joelahtme, ...) and Tallinn city; country has 17 counties.
* GET api/?do=getbyurl&type=place&url=paks-margareeta-tallinn-0 ->
  HTTP 200 (4364 B): place records carry address + lat/lng — but
  there is NO places bulk endpoint (per-alias lookup only), so a
  venue-distance join would need per-venue enumeration (refused as
  scraping, AGENTS.md section 5). The honest grain is the CITY
  calendar (same value for every Tallinn listing at one snapshot —
  a temporal signal, recalibrated on re-pull), never a faked
  per-venue score. (A full-URL `url=` probe first returned
  code -1 "Incorrect object 2" — the alias-slug form above is the
  documented-by-behaviour correction.)
* Refresh: rows carry created/modified unix timestamps (sample
  modified 1789441301 = September 2026) — the feed is live and
  current, not a stale dump.

Honest shapes:
* P4-033 `events_calendar`: SCORED city-grain calendar — starts in
  the next 30 days off the cached Tallinn snapshot (bands below,
  first-cut, MUST be recalibrated from a real histogram on reopen;
  never 100/never 0: the leg is partial by construction and events
  are not a disaster). Windows run off the snapshot's fetched_at
  (stated in every reason); freshness is the TTL/re-pull problem,
  not a scorer filter. Non-Tallinn listings and missing snapshots
  stay NULL with an Estonian EI OLE reason.
* P4-047 `fireworks_calendar`: NULL for EVERY input — dated
  fireworks permits exist nowhere in this feed (no category, no
  permit fields; Piletilevi ticket links are commerce, not permits).
  The reason cites the 2026-09-16 category evidence and points at
  the permit desk + the komun/KÜ/paaste cousin slices.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_events_snapshot(cache_dir): polite pull, max 1 download /
  24 h per cache dir (EVENTS_TTL_S; the feed states no cadence, so
  daily per AGENTS.md section 5 polite-cron guidance). Cache hit
  within TTL performs NO request. One bounded GET (city=tallinn,
  start=0, limit=FETCH_LIMIT) with the identifying UA; the body is
  stored only on HTTP 200 with JSON content, else None is returned
  and nothing is cached (transport errors are never data). No
  retries — HTTP 429/errors are a stop signal. If the site rotates
  the published token, the pull degrades to None (honest NULL),
  never to a guess. The scorer never calls this; tests cover the
  cache-hit and transport-error paths with a stubbed opener, never
  the network.
* parse_events_snapshot / upcoming_starts: pure offline readers
  over the cached envelope (schema above). Malformed rows are
  skipped, never faked; a missing/unparseable file parses to None
  (unknown), never to an empty calendar.

Style mirrors services/scoring/dims_p4_bikes.py (#309): pure
scorers (listing, snapshot) -> (Optional[int 0..100], Estonian
reason), local helpers (no livability import — importing it here
would turn the future central hook into a cycle, same precedent as
PRs #100/#106/#115). Higher = calmer fit (livability convention:
100 is best); a busy festival month scores LOW, never 0.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE module because #375 says it extends the
  demoed ingestion with "no new plumbing expected" — the coverage
  slice IS the same snapshot read for permits (absent, pinned NULL
  with the category evidence), not a second pipeline.
* Starts-in-window, not active-in-window: permanent exhibitions
  (sample: 2019-2026) would otherwise paint every month busy. The
  nuisance pulse is openings/performances.
* City grain, not venue grain: no places bulk exists (per-alias
  only), so per-venue distance scoring would be enumeration, not
  polling. Every Tallinn listing shares the month value; the reason
  says so.
* kultuur (church) category rows are ordinary parish concerts, not
  bell permits — the bells/noise-permit leg stays a buyer-side
  check, named in the reason.
* The published client token is committed as a documented constant:
  it is the site's own anonymous read token (shipped to every
  browser), grants no privileged access, and is the only
  reproducible pull path. Rotation degrades to NULL, never to fake.

Integration (deliberately NOT done here): wiring the snapshot into
a listing pipeline plus rebalancing livability.WEIGHTS must be one
joint change across all batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling. No
shared files touched.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: kultuurikava.ee app-API host (REACT_APP_API_URL in the shipped
#: bundle /static/js/main.07d7e3b5.js, verified 2026-09-16).
KULTUURIKAVA_API = "https://www.kultuurikava.ee/api/"

#: The site's published anonymous read token (REACT_APP_API_TOKEN in
#: the same public bundle — sent by every visitor's browser, no
#: login, no privileged access). If the site rotates it, the fetch
#: below degrades to None (honest NULL), never to a guess.
KULTUURIKAVA_TOKEN = "1499ddfb3cb59057a9f201a4e6faf6fe68bde294"

#: Snapshot city (the demo scope is Tallinn; county=harjumaa and the
#: other 16 counties are the reopening checklist, not this pull).
SNAPSHOT_CITY = "tallinn"

#: Max one download per 24 h per cache dir (the feed states no
#: cadence, so daily per AGENTS.md section 5 polite-cron guidance).
EVENTS_TTL_S = 24 * 3600

#: Next-30-day season window for the starts pulse.
WINDOW_DAYS = 30

#: Bounded page (single GET per pull; total is recorded, never paged
#: through — paging 1309 rows would be 7+ pulls per day).
FETCH_LIMIT = 500

#: Snapshot filename inside the cache dir (raw API envelope, what the
#: server sent — parsing never mutates the cache).
CACHE_FILENAME = "events-tallinn.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
EVENTS_UA = ("home-finder P4-033 events pull "
             "(max 1 req/24h, city snapshot, no scrape)")


def _events_url(city: str = SNAPSHOT_CITY,
                limit: int = FETCH_LIMIT) -> str:
    params = urllib.parse.urlencode({
        "do": "events",
        "token": KULTUURIKAVA_TOKEN,
        "lang": "nat",
        "city": city,
        "order": "starta",
        "start": 0,
        "limit": limit,
        "format": "json",
        "showall": "false",
        "alltimes": "true",
        "ignoremuuseums": "true",
    })
    return KULTUURIKAVA_API + "?" + params


def fetch_events_snapshot(cache_dir: str,
                          ttl_s: int = EVENTS_TTL_S,
                          city: str = SNAPSHOT_CITY,
                          limit: int = FETCH_LIMIT) -> Optional[str]:
    """Polite Tallinn calendar pull with a stated TTL. Path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise one bounded GET with EVENTS_UA and a 30 s timeout; the
    body is stored only on HTTP 200 with JSON content, else None is
    returned and nothing is cached (transport errors are never data).
    No retries — HTTP 429/errors are a stop signal. The scorer never
    calls this; tests cover the cache-hit and transport-error paths
    with a stubbed opener, never the network.
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
        req = urllib.request.Request(_events_url(city, limit),
                                     headers={"User-Agent": EVENTS_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "json" not in ctype:
                return None
            body = resp.read()
        try:
            json.loads(body)
        except ValueError:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached snapshot (pure; fixtures match schema).
# ---------------------------------------------------------------------------

def _as_ts(value) -> Optional[int]:
    """Unix timestamp or None when malformed (never faked)."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value <= 0:
        return None
    return value


def parse_events_snapshot(path: str) -> Optional[dict]:
    """Read a cached calendar envelope. Offline, stdlib.

    Returns {"city", "fetched_at" (file mtime), "total", "events":
    [{id, name, start_time, end_time, place_name, city, county,
    categories}]} with malformed rows skipped (never faked), or None
    when the file is missing/unparseable (unknown, never an empty
    calendar — the scorer must not read "no file" as "no events").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    data = raw.get("data")
    if not isinstance(data, dict):
        return None
    rows = data.get("events")
    if not isinstance(rows, list):
        return None
    total = data.get("total")
    events = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        start = _as_ts(row.get("start_time"))
        if start is None:
            continue
        cats = row.get("categories")
        events.append({
            "id": row.get("id"),
            "name": row.get("name") if isinstance(
                row.get("name"), str) else "",
            "start_time": start,
            "end_time": _as_ts(row.get("end_time")),
            "place_name": row.get("place_name") if isinstance(
                row.get("place_name"), str) else "",
            "city": row.get("city") if isinstance(
                row.get("city"), str) else "",
            "county": row.get("county") if isinstance(
                row.get("county"), str) else "",
            "categories": [c for c in cats if isinstance(c, int)]
            if isinstance(cats, list) else [],
        })
    try:
        fetched_at = int(os.path.getmtime(path))
    except OSError:
        return None
    return {
        "city": SNAPSHOT_CITY,
        "fetched_at": fetched_at,
        "total": total if isinstance(total, int) else len(events),
        "events": events,
    }


def upcoming_starts(snapshot: Optional[dict],
                    window_days: int = WINDOW_DAYS) -> Optional[List[int]]:
    """Parsed snapshot (or None) -> sorted start-times in the window.

    The season pulse: events STARTING within [fetched_at,
    fetched_at + window_days] (permanent exhibitions started years
    ago never count, however long they run). Returns None when there
    is no snapshot to index (unknown); an empty list means a parsed
    snapshot with a genuinely calm month ahead.
    """
    if not isinstance(snapshot, dict):
        return None
    fetched = snapshot.get("fetched_at")
    rows = snapshot.get("events")
    if not isinstance(fetched, int) or not isinstance(rows, list):
        return None
    end = fetched + window_days * 86400
    return sorted(r["start_time"] for r in rows
                  if isinstance(r, dict)
                  and isinstance(r.get("start_time"), int)
                  and fetched <= r["start_time"] < end)


# ---------------------------------------------------------------------------
# P4-033: Tallinn season pulse (demo, scored city grain).
# ---------------------------------------------------------------------------

#: Starts in the next 30 days -> calm-fit score (high = calm month,
#: buyer-favourable; a busy festival month scores LOW, never 0 —
#: events are not a disaster — and calm never 100: the leg is
#: partial by construction). First-cut bands, MUST be recalibrated
#: from a real histogram on reopen.
CALM_BANDS = [(0, 85), (9, 70), (49, 55), (199, 40), (float("inf"), 30)]


def _band(value: int, bands: List[Tuple[float, int]]) -> int:
    """First score whose threshold covers the value."""
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _is_tallinn(listing) -> bool:
    """City grain: only Tallinn listings take the Tallinn calendar."""
    if not isinstance(listing, dict):
        return True  # Tallinn-scope default (documented)
    city = listing.get("city")
    if city is None:
        return True
    return isinstance(city, str) and city.strip().lower() in (
        "tallinn", "tallinna linn")


def dim_events_calendar(listing: Optional[dict],
                        snapshot: Optional[dict]) -> Score:
    """P4-033: Tallinn season pulse off the kultuurikava snapshot.

    City grain: every Tallinn listing shares the month value (there
    is no places bulk for a venue join — per-alias enumeration would
    be scraping, not polling). Windows run off the snapshot's
    fetched_at (stated in the reason); a missing snapshot, a
    non-Tallinn listing, or an unparseable snapshot stays NULL with
    an Estonian EI OLE reason (unknown is never calm).
    """
    if not _is_tallinn(listing):
        city = listing.get("city") if isinstance(listing, dict) else "?"
        return None, ("Ürituskalendri hinnang puudub (EI OLE Tallinna "
                      "kalendrit sellele kuulutusele: linnaks on märgitud "
                      "'%s', hetktõmmis katab ainult Tallinna — ära feigi)"
                      % city)
    starts = upcoming_starts(snapshot)
    if starts is None:
        return None, ("Ürituskalendri hinnang puudub (EI OLE Tallinna "
                      "kultuurikalendri hetktõmmist: allikat pole tõmmatud "
                      "või on fail loetamatu — kontrolli Lauluväljaku ja "
                      "Pirita kalendreid ning kirikukellade/müra lubasid "
                      "sealt, kuula Kesklinna/Pirita serva kohapeal; "
                      "kruiisipäevad dims_p4_sadam'is, jahiteated "
                      "dims_p4_kesk'is, ära feigi)")
    n = len(starts)
    s = _band(n, CALM_BANDS)
    day = _day(snapshot["fetched_at"])
    if n == 0:
        return s, ("Ürituste-hõrenduse hinnang (Tallinna linna-kalender, "
                   "hetktõmmis %s: järgmise 30 päeva jooksul ei alga ühtegi "
                   "kultuurikava üritust — rahulik kuu) → skoor %d "
                   "(kruiisipäevad dims_p4_sadam'is, jahiteated "
                   "dims_p4_kesk'is)" % (day, s))
    word = "üks algav üritus" if n == 1 else "%d algavat üritust" % n
    soon = _day(starts[0])
    return s, ("Ürituste-hõrenduse hinnang (Tallinna linna-kalender, "
               "hetktõmmis %s: järgmise 30 päeva jooksul %s, lähim %s) → "
               "skoor %d (püsiekspositsioonid pulsis ei loe; "
               "kruiisipäevad dims_p4_sadam'is, jahiteated "
               "dims_p4_kesk'is)" % (day, word, soon, s))


def dim_fireworks_calendar(listing: Optional[dict],
                           snapshot: Optional[dict]) -> Score:
    """P4-047: NULL — the kultuurikava feed carries no permit calendar.

    Dated 2026-09-16 dig: 25 cultural categories, no fireworks /
    ilutulestik / permit category or field anywhere in the schema —
    Piletilevi ticket links are commerce, not permits. Every input,
    snapshot or not, stays NULL (a firework guess off concert rows
    would be fake precision, OTA PR #131 precedent).
    """
    return None, ("Ilutulestiku-kalendri hinnangut pole (EI OLE "
                  "kuupäevatud ilutulestiku-lubade voogu: kultuurikava "
                  "rakendusliideses on 25 kultuurikategooriat "
                  "(kontrollitud 2026-09-16) ja ilutulestiku kategooriat "
                  "ega loavälja seal pole — piletilingid on kaubandus, "
                  "mitte load; küsi korraldaja lubasid linnavalitsusest "
                  "või Päästeametist ning kuula jaanipäeva ja "
                  "aastavahetuse paiku kohapeal; mürakaebused ja sahavedu "
                  "dims_p4_komun'is, KÜ logid dims_p4_kudocs'is, "
                  "üritusliikluse kalender dims_p4_paaste'is, ära feigi)")


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_EVENTS_DIMS = (
    ("events_calendar", "P4-033", dim_events_calendar),
    ("fireworks_calendar", "P4-047", dim_fireworks_calendar),
)


def score_p4_events(listing: Optional[dict],
                    snapshot: Optional[dict]
                    ) -> Dict[str, Optional[int]]:
    """Both P4 events dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_EVENTS_DIMS). The
    fireworks leg is None by design — no permit feed exists."""
    return {key: fn(listing, snapshot)[0] for key, _, fn in P4_EVENTS_DIMS}
