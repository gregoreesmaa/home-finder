"""P4 events-feed dims (issue #540): Piletimaailm scheduled-events
feed.json (urituuste infovoog) as calendar join scorers.

Source (probed 2026-09-16, one polite GET per endpoint, labelled
one-off User-Agent, `--max-time 25`, raw files at /tmp/hf-probes/ --
one-off PR record, never committed):
* Feed: https://www.piletimaailm.com/performances/feed.json ->
  HTTP 200, 5 087 134 bytes, application/json -- ALIVE (catalogue
  `updated` 2022-11-23 notwithstanding; newest rows dated 2026-10-16,
  oldest 2026-09-16 = a ~30-day forward window, 397 events).
* Schema (21 keys): id, name, name_en, date ("2026/09/16 14:00:00
  +0300"), buy_ticket_url, info_url, organizer_name, event_id,
  updated_at, category, free_seat_count, image_url/thumb, state
  ("on_sale"), full_description(_plain), location_venue_id,
  location_venue_name, location_venue_hall_name,
  location_address_address, location_address_city. NO coordinates.
* Fill: venue 100% (397/397), city 86% (343/397), category 99.5%
  (395/397: Teater 308, Kino 75, Muusika 8, Tants 2, Tsirkus 1,
  Festival 1). 33 organizers, 69 venue strings, 46 city slots.
* Tallinn: 88 events across 11 venue strings (~8 physical venues once
  "Eesti Draamateater."-style dupes merge): Draamateater 44 (Pärnu
  mnt 5), Theatrum 14 (Vene 14), Noblessner 7 (Peetri 10), Kumu 7
  (Weizenbergi 34), Mere 9 (Mere pst 5, 3 spellings), Salme 5
  (Salme 12), Estonia 1, Süda saal 1 -- ALL theatre; evening (>=18h)
  share ~86%.
* NOT covered: Lauluväljak, stadium, Pirita, fireworks permits --
  no big-crowd venue string observed. The P4-047 horrors leg stays
  NULL honestly; this feed serves the P4-045 evening-culture leg.
* Guide PDF https://www.piletimaailm.com/downloads/yrituste_voog_api.pdf
  -> HTTP 404 (1 331-byte HTML miss): site restructured since the
  catalogue entry. Documented negative; the live schema is
  self-describing (field names above), so nothing is blocked.

Params (this module only -- sibling batches own disjoint sets):
* P4-045 evening-culture leg: per-venue 30-day event-days ->
  evening-density bands (joined 0 scores calm, missing join NULL).
* P4-047 horrors leg: documented NULL (ticketed theatre/cinema only).
  dims_p4_trans.horrors_events (Transpordiamet leg), dims_p4_paaste
  calendar dims, and dims_p4_events (kultuurikava-shell verdict) stay
  untouched cousins -- distinct dim keys, no double-score.

HONESTY (AGENTS.md section 7.2): venue names merge by spelling rules
only (case/whitespace/trailing-dot/"Tallinn," affixes -- never fuzzy);
venue coordinates are NEVER guessed (VENUE_ADDRESSES carries the
feed's own address strings with coords None until the harvest
geocodes them against ADS/Maa-amet). Ungeocoded or unknown venue ->
NULL with EI OLE + the venue-calendar buyer check. Ticketed events
only -- free/neighbourhood events stay uncovered (legend says so).
Transport errors RAISE (never cached as data); HTTP 429 propagates.

Style mirrors services/scoring/dims_p4_events.py (#310/#375): pure
(venue_key, calendar) -> (Optional[int 0..100], Estonian reason),
absolute bands, hermetic fixture tests. Network lives only in
fetch_events_feed (single polite GET, file cache, TTL); tests never
call it.

BANDS (p4_trans precedent shape, locked 2026-09-16 on the measured
per-venue 30-day event-days: Draamateater 44, Theatrum 14, Mere 9,
Noblessner/Kumu 7, Salme 5, Estonia/Suda 1):
* 0 event-days (joined, real calm) -> 80; <=5 -> 60; above -> 40.
  Reasons annualise (x365/30) and name the evening share.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Annual harvest (issue constraint) DESPITE the 30-day window: each
  pull is a dated sample, not a yearly census -- reasons name the
  window ("30 paeva aknas"). A denser cadence is a harvest-schedule
  change, not a code change.
* Evening = start hour >= 18 local (feed timestamps carry +0300/+0200;
  the parser honours the offset). Matinees still count toward
  event-days (a full house at noon still fills parking).
* Venue dedup is spelling-only: "Eesti Draamateater" ==
  "Eesti Draamateater." and the three "Mere Kultuurikeskus" spellings
  merge; anything else stays split (splitting is honest, over-merging
  is fake).

Integration (deliberately NOT done here): listing->venue catchment
(geocoded venue table + nearest-venue wiring) inside livability
scoring and rebalancing livability.WEIGHTS must be one joint change
across all parameter batches.
"""

import json
import os
import time
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Keyless bulk API (verified alive 2026-09-16).
EVENTS_FEED_URL = "https://www.piletimaailm.com/performances/feed.json"

#: Annual harvest is plenty (issue constraint; event feed, not telemetry).
EVENTS_TTL_DAYS = 365

#: CC BY-SA 3.0: attribute the Drama Theatre Foundation feed.
EVENTS_ATTRIBUTION = ("Eesti Draamateater (Piletimaailm urituste "
                      "infovoog), CC BY-SA 3.0")

USER_AGENT = ("home-finder Piletimaailm events ingest (polite annual pulls, "
              "single GET, file cache; contact via GitHub home-finder)")

#: Evening cutoff (local start hour, feed timestamps carry the offset).
EVENING_HOUR = 18

#: 30-day forward window observed 2026-09-16 (reasons name the window).
WINDOW_DAYS = 30


def _cache_path(cache_dir: str) -> str:
    """Cache file for the feed snapshot (flat dir, fixed name)."""
    return os.path.join(cache_dir, "piletimaailm-feed.json")


def cache_is_fresh(path: str, ttl_days: int = EVENTS_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_events_feed(url: str = EVENTS_FEED_URL,
                      cache_dir: str = "/tmp/hf-cache",
                      ttl_days: int = EVENTS_TTL_DAYS) -> str:
    """Fetch the feed politely (single GET, cached, TTL-stated).

    Returns the local path. Transport errors RAISE (never cached as
    data); HTTP 429 propagates (stop signal, stale cache untouched).
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if cache_is_fresh(path, ttl_days):
        return path
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    with open(path, "wb") as f:
        f.write(body)
    return path


def normalise_venue(name: str) -> str:
    """Spelling-only venue key (no fuzzy merge, no guessing).

    Lowercase + whitespace collapse + one trailing dot stripped +
    a single leading "tallinn, "/"tallinn " or trailing
    ", tallinn"/" tallinn" affix removed (the three Mere spellings
    observed 2026-09-16). Anything else stays a distinct key.
    """
    key = " ".join(name.lower().split()).rstrip(".").strip()
    if key.startswith("tallinn, "):
        key = key[len("tallinn, "):]
    elif key.startswith("tallinn "):
        key = key[len("tallinn "):]
    if key.endswith(", tallinn"):
        key = key[:-len(", tallinn")]
    elif key.endswith(" tallinn"):
        key = key[:-len(" tallinn")]
    return key.strip().rstrip(".")


#: Manual venue table (reviewer call per the issue): address strings are
#: the feed's own 2026-09-16 values; coords stay None until the harvest
#: geocodes them (never guessed here).
VENUE_ADDRESSES: Dict[str, Dict[str, Optional[str]]] = {
    "eesti draamateater": {"address": "Pärnu mnt 5", "city": "Tallinn",
                           "lat": None, "lon": None},
    "theatrumi saal": {"address": "Vene 14, Tallinn", "city": "Tallinn",
                       "lat": None, "lon": None},
    "noblessneri valukoja nobeli saal": {"address": "Peetri 10, Tallinn",
                                         "city": "Tallinn",
                                         "lat": None, "lon": None},
    "kumu auditoorium": {"address": "A. Weizenbergi 34, Tallinn",
                         "city": "Tallinn", "lat": None, "lon": None},
    "mere kultuurikeskus": {"address": "Mere pst 5", "city": "Tallinn",
                            "lat": None, "lon": None},
    "salme kultuurikeskus": {"address": "Salme tn 12", "city": "Tallinn",
                             "lat": None, "lon": None},
    "rahvusooper estonia": {"address": "Estonia pst 4", "city": "Tallinn",
                            "lat": None, "lon": None},
    "teatri- ja muusikamuuseumi peeter süda saal": {
        "address": "Müürivahe 12, 10146 Tallinn", "city": "Tallinn",
        "lat": None, "lon": None},
}


def parse_event_date(text: str) -> Optional[datetime]:
    """Feed date ("2026/09/16 14:00:00 +0300") -> aware datetime/None."""
    try:
        return datetime.strptime(text.strip(), "%Y/%m/%d %H:%M:%S %z")
    except (ValueError, AttributeError):
        return None


def parse_events_feed(text: str) -> List[Dict[str, Optional[object]]]:
    """Parse a feed snapshot into event rows (sparse-tolerant).

    Rows carry venue_raw, venue_key, date (datetime/None), evening
    (bool/None when undated), category, city, address. Undated or
    venueless rows are SKIPPED (never scored as calm).
    """
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(payload, list):
        return []
    events: List[Dict[str, Optional[object]]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        venue_raw = item.get("location_venue_name") or ""
        if not isinstance(venue_raw, str) or not venue_raw.strip():
            continue
        moment = (parse_event_date(item["date"])
                  if isinstance(item.get("date"), str) else None)
        category = item.get("category")
        events.append({
            "venue_raw": venue_raw.strip(),
            "venue_key": normalise_venue(venue_raw),
            "date": moment,
            "evening": (moment.hour >= EVENING_HOUR
                        if moment is not None else None),
            "category": (category.strip() if isinstance(category, str)
                         and category.strip() else None),
            "city": (item.get("location_address_city") or None),
            "address": (item.get("location_address_address") or None),
        })
    return events


def build_venue_calendar(
        events: List[Dict[str, Optional[object]]]
) -> Dict[str, Dict[str, object]]:
    """Aggregate event rows -> {venue_key: calendar}.

    Undated rows count toward `events` but NOT toward `event_days`
    (a date is required to claim a day). Calendars hold distinct-date
    event_days, evening_days, total events, and the category set.
    """
    days: Dict[str, set] = {}
    evening: Dict[str, int] = {}
    total: Dict[str, int] = {}
    categories: Dict[str, set] = {}
    for ev in events:
        key = ev["venue_key"]
        if not isinstance(key, str):
            continue
        days.setdefault(key, set())
        evening[key] = evening.get(key, 0)
        total[key] = total.get(key, 0) + 1
        categories.setdefault(key, set())
        if ev["category"]:
            categories[key].add(ev["category"])
        moment = ev["date"]
        if moment is not None:
            days[key].add(moment.date().isoformat())
            if ev["evening"]:
                evening[key] += 1
    return {key: {"event_days": len(days[key]),
                  "evening_days": evening.get(key, 0),
                  "events": total[key],
                  "categories": sorted(categories[key])}
            for key in total}


def dim_culture_evenings(
        venue_key: Optional[str],
        calendar: Optional[Dict[str, Dict[str, object]]],
) -> Score:
    """P4-045 leg: per-venue 30-day event-days -> 80/60/40.

    Joined 0 event-days scores 80 (real calm); a missing venue join
    stays NULL with EI OLE + the venue-calendar buyer check.
    """
    if venue_key and calendar and venue_key in calendar:
        cell = calendar[venue_key]
        days = int(cell.get("event_days", 0))
        eve = int(cell.get("evening_days", 0))
        yearly = round(days * 365.0 / WINDOW_DAYS)
        tail = ("(%d urituspaeva 30 paeva aknas, sh %d ohtust; "
                "~%d paeva/aastas; piletivoog, tasuta/naabruskonna "
                "uritused katmata)" % (days, eve, yearly))
        if days == 0:
            return 80, ("Kultuurikalendri rahu hinnang: vaikne %s -- "
                        "uhtki piletiga uritust 30 paeva aknas "
                        "(Piletimaailm, toeline vaikus)" % tail)
        if days <= 5:
            return 60, ("Kultuurikalendri hinnang: rahulik %s -- "
                        "harv ohtune tegevus, kuula hooaja tippudel "
                        "kohapeal" % tail)
        return 40, ("Kultuurikalendri hinnang: tihe %s -- sagedased "
                    "ohtused uritused, liiklus/mura/parklate koormus "
                    "uritusepaevadel; kuula kohapeal" % tail)
    return None, ("Ohtukultuuri tiheduse hinnangut pole (EI OLE selle "
                  "koha piletikalendri vastet -- teadmata/geokodeerimata "
                  "sündmuspaik voi 30 paeva aken puudu): kontrolli "
                  "Lauluväljaku/Pirita/kultuurimajade kalendreid, "
                  "piletilevi infovoogu ja kuula ohtuti kohapeal")


def dim_horrors_crowds(
        venue_key: Optional[str],
        calendar: Optional[Dict[str, Dict[str, object]]],
) -> Score:
    """P4-047 leg: NULL -- the feed has no big-crowd venues.

    The 2026-09-16 snapshot holds ticketed theatre/cinema only (no
    Lauluvaljak, stadium, Pirita rows), so crowd-traffic/noise days
    cannot be banded from it. Every input returns NULL with the
    buyer-side checks (sibling Transpordiamet/Päästeamet legs named).
    """
    return None, ("Suururituste rahvahulga-hinnangut pole (EI OLE "
                  "Lauluväljaku/staadioni/Pirita rahvahulga-voogu -- "
                  "piletivoog katab ainult teatri/kino saale): "
                  "kontrolli Lauluväljaku ja Pirita kalendreid, "
                  "urituste liiklusteavet (dims_p4_trans, "
                  "dims_p4_paaste) ja kuula suururituste ajal kohapeal")


#: Registry for UI/API wiring on integration: param -> (title, fn).
P4_EVENTS_FEED_DIMS: Dict[str, Tuple[str, object]] = {
    "culture_evenings": ("Õhtukultuuri tihedus (Piletimaailm)",
                         dim_culture_evenings),
    "horrors_crowds": ("Suurürituste rahvahulk (EI OLE)",
                       dim_horrors_crowds),
}


def score_p4_events_feed(
        venue_key: Optional[str],
        calendar: Optional[Dict[str, Dict[str, object]]],
) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All P4-events-feed dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in P4_EVENTS_FEED_DIMS.items():
        v, reason = fn(venue_key, calendar)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
