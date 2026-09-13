"""P4 paaste batch: Paasteamet (Rescue Board) honest-shape dims (issues #276, #350).

Params (this module only — demo + coverage paired in one PR because the
coverage body (#350) states it extends the demo ingestion, #276):
* P4-012 Accident blackspots + rescue drive-time (demo via P4-012)
* P4-015 Insurability: flood/theft zones (Paasteamet slice: fire density)
* P4-042 Smell/dawn-chorus map (Paasteamet slice: chimney-smoke teated)
* P4-047 Small horrors calendar (Paasteamet slice: event-traffic teated)
* P4-058 Falling-ice roofs + cliff retreat (Paasteamet slice: ice-fall)
* P4-059 Wood-burning restriction zones (Paasteamet slice: chimney notices)
* P4-062 Rat complaints + ice-fall warnings (Paasteamet slice: ice warnings)

HONESTY (AGENTS.md section 7.2): Paasteamet publishes statistics as human
HTML pages plus a documented open-dataset catalogue (verified 2026-09-13,
three polite pulls, cached to /tmp/hf-paaste-cache, full evidence in
docs/p4_paaste.md) — but the three pulls located NO machine-readable event
feed (no csv/json/xml/api dataset download; dated negative, kept). So this
module never emits a measured gradient: point inventories (blackspots,
komando points, ice/smoke notices, hex-watch flags) are caller-supplied
until a future adapter job owns them, zone/rule tables travel in the
explicit `coverage` argument, and every dim without its input returns None
with an Estonian reason that says "hinnang" and "EI OLE" and points at the
concrete buyer-side check. NULL stays NULL.

Openness verdict (2026-09-13, three polite single-GET pulls, probe UA,
no retries, full evidence in docs/p4_paaste.md):
* https://www.rescue.ee/ : OPEN, HTTP 200, 142 kB human HTML.
* https://www.rescue.ee/et/statistika : OPEN as human HTML tables/hub,
  HTTP 200, 132 kB; links to KOV-level stats, the avaandmed portal query
  `?ih=paasteamet`, and a Recommy dashboard — NO dataset file download
  (no csv/xls/json/xml/api href; dated negative, kept).
* https://www.rescue.ee/et/juhend/avaandmed : OPEN catalogue of named
  open datasets (metsa-/maastikutulekahjud, ohtlikud ettevotted,
  veevotukohad, avalikud varjumiskohad) via the national Teabevarav;
  human pages, no direct machine endpoint pulled (dated negative, kept).
  Polite automation stops at sufficient (AGENTS.md section 7.4).

Ingestion contract: a monthly-cron adapter snapshots the statistika hub
page (polite UA, file cache, TTL below); this module's pure helper parses
one HTML payload into the dataset catalogue the dims cite, and the
`coverage` dict carries that catalogue plus the caller-resolved tables.
Transport errors are never cached as data (fetch raises, cache untouched);
HTTP 429 is a stop signal, not a retry dare.

Style mirrors services/scoring/livability.py and sibling batch
dims_p4_ilm.py (#308/#374): scorers are pure and offline-tested. The
uniform scorer shape is (origin, pois, coverage=None) — the optional
third argument IS the new plumbing the coverage issue anticipates
("no new plumbing expected unless a param needs it"): zone/rule tables
(linnaosa fire class, burn restriction), the event calendar, and the
de-icing season have no honest snapshot channel (stuffing linnaosa tables
into OSM POIs would abuse the POI channel), so they travel explicitly.
Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100).

Deliberately NO Overpass fragment and NO tag mapping here (unlike proxy
batches): Paasteamet data is not OSM data, and the point inventories are
caller-supplied until a future adapter job owns them — inventing a
fragment would be dishonest plumbing. The POI kinds below are caller-side
contracts documented here, not snapshot tags.

Judgment calls (reviewable per AGENTS.md section 7.5):
* P4-012 blackspot bands (0 -> 75, 1 -> 60, 2-3 -> 40, 4+ -> 20 in a
  500 m buffer) are coarse count bands, and the komando leg is a
  straight-line penalty only (-10 past 5 km, floored 0): the module holds
  NO komando coordinates and computes NO routed time, and the reason says
  "linnulennult (hinnang, mitte marsruudi-aeg)". Pairing rationale: the
  demo param needs both legs to answer "is this crossing safe", and a
  buffer count without the drive-time half would fake completeness.
* P4-015 bands (madal -> 70, keskmine -> 50, korge -> 25) score only the
  Paasteamet fire-density slice and say so; "korge" appends the
  illiquidity-flag pointer (kindlustus-keeldumise risk). Flood/theft legs
  (Keskkonnaagentuur, PPA, insurer tariffs) are NOT joined. Unknown class
  tokens read as None (never guessed).
* P4-042 scores ONLY inside a caller-supplied smoke-notice cell (800 m
  coarse cell, capped 45, "jame hinnang, mitte ukse-tapsus"); outside any
  cell is NULL, never a clean-air score — absence of notices is not
  absence of smoke.
* P4-047 scores the city-wide event calendar (0 -> 75, 1-2 -> 60,
  3-5 -> 45, 6+ -> 30 notices/year), ignoring origin like the ilm city
  baseline: Tallinn fireworks/event-traffic teated are city-level, and a
  per-parcel ramp off a city calendar would be fake precision.
* P4-058 recency runs off caller-supplied notice seasons ("2025/26")
  against coverage["season"]: same season -> 35, previous -> 45, older
  -> 55, undated -> capped 45. The module takes NO wall-clock time
  (hermetic, deterministic); season strings are caller clock.
* P4-059 rule join (keelatud -> 20 stranded-stove, piiratud -> 50,
  lubatud -> 75) scores the rule, not a measurement; EHR stove inventory
  is NOT joined. Unknown rule tokens read as None.
* P4-062 scores ONLY inside a caller-supplied hex-watch flag (500 m
  coarse read, capped 40, flags listed); the rat-complaint leg
  (Keskkonnaamet) is NOT joined and the reason says so. Outside is NULL,
  never addresses (hex only by construction).

Integration (deliberately NOT done here): the monthly-cron snapshotter,
any livability hook, and rebalancing livability.WEIGHTS must be one
joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
"""

import math
import os
import re
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Statistika hub (verified 2026-09-13: HTTP 200, human HTML hub + links).
PAASTE_STATS_URL = "https://www.rescue.ee/et/statistika"
#: Open-dataset catalogue (verified 2026-09-13: HTTP 200, named datasets).
PAASTE_AVAANDMED_URL = "https://www.rescue.ee/et/juhend/avaandmed"
#: National portal query the hub links to (reference only, never pulled here).
PAASTE_PORTAL_URL = "https://avaandmed.eesti.ee/datasets?ih=paasteamet"
PAASTE_USER_AGENT = (
    "home-finder-p4-paaste/1.0 (Estonia open-data monthly adapter; "
    "polite single-pull, cache-first)"
)
#: Stats update monthly/annual per parameters4.md P4-012 TTL: at most one
#: live pull per month, cache wins inside the TTL.
PAASTE_CACHE_TTL_S = 30 * 86400
PAASTE_CACHE_NAME = "paasteamet-statistika.html"

#: Point-inventory POI kinds (caller-side contracts, NOT snapshot tags).
BLACKSPOT_KIND = "blackspot"  # accident blackspot point {lat, lon}
RESCUE_STATION_KIND = "rescue_station"  # komando point {lat, lon, name}
ICE_NOTICE_KIND = "ice_notice"  # dated ice-fall notice {lat, lon, street, season}
SMOKE_NOTICE_KIND = "smoke_notice"  # chimney-smoke cell rep {lat, lon, area}
HEX_WATCH_KIND = "hex_watch"  # hex operational flag rep {lat, lon, hex, flags}

#: Spatial honesty radii (coarse reads, never doorway precision).
BLACKSPOT_RADIUS_M = 500.0
SMOKE_RADIUS_M = 800.0
ICE_RADIUS_M = 300.0
HEX_RADIUS_M = 500.0
#: Straight-line komando distance past which the drive-time penalty applies.
STATION_FAR_KM = 5.0

#: P4-015 linnaosa fire-density classes (unknown tokens -> None, never guessed).
FIRE_CLASSES = ("madal", "keskmine", "korge")
#: P4-059 restriction rules (unknown tokens -> None, never guessed).
BURN_RULES = ("keelatud", "piiratud", "lubatud")

#: Estonian month names for calendar reasons.
MONTH_ET = {
    1: "jaanuar", 2: "veebruar", 3: "marts", 4: "aprill",
    5: "mai", 6: "juuni", 7: "juuli", 8: "august",
    9: "september", 10: "oktoober", 11: "november", 12: "detsember",
}


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points (pure)."""
    r = 6371.0
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dla = math.radians(b[0] - a[0])
    dlo = math.radians(b[1] - a[1])
    h = (math.sin(dla / 2.0) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2.0) ** 2)
    return 2.0 * r * math.asin(min(1.0, math.sqrt(h)))


def _pois_of(pois: Optional[List[dict]], kind: str) -> List[dict]:
    out = []
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        if p.get("lat") is None or p.get("lon") is None:
            continue
        out.append(p)
    return out


def _count_within(origin: Tuple[float, float], pois: List[dict],
                  radius_m: float) -> int:
    return sum(1 for p in pois
               if haversine_km(origin, (p["lat"], p["lon"])) * 1000.0 <= radius_m)


def _nearest(origin: Tuple[float, float],
             pois: List[dict]) -> Tuple[Optional[dict], Optional[float]]:
    best = None
    best_km = None
    for p in pois:
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if best_km is None or km < best_km:
            best, best_km = p, km
    return best, best_km


def _coverage(coverage: Optional[dict]) -> dict:
    return coverage if isinstance(coverage, dict) else {}


def _season_start(season: Optional[object]) -> Optional[int]:
    """Parse a "2025/26" de-icing season to its start year (pure)."""
    if not isinstance(season, str):
        return None
    m = re.match(r"^\s*(\d{4})\s*/\s*\d{2}\s*$", season)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Ingestion: polite cached pull (live path, NOT unit-run) + pure parse.
# ---------------------------------------------------------------------------

def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, PAASTE_CACHE_NAME)


def fetch_stats_snapshot(
    cache_dir: Optional[str] = None,
    ttl_s: int = PAASTE_CACHE_TTL_S,
) -> Tuple[str, str]:
    """Polite cached pull of the statistika hub page (live path, NOT unit-run).

    Cache wins inside the TTL; on a live pull any transport error
    (HTTP error, timeout, 429, decode failure) raises and the cache file
    is left untouched — transport errors are never cached as data, and
    429 stops the run. Returns (html, provenance) with provenance
    "cache" or "live".
    """
    if cache_dir is None:
        cache_dir = os.path.join("/tmp", "hf-paaste-cache")
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < ttl_s:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(), "cache"
    req = urllib.request.Request(
        PAASTE_STATS_URL, headers={"User-Agent": PAASTE_USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        if resp.status == 429:
            raise RuntimeError("Paasteamet vastas 429 — peatu, ara reetry")
        if resp.status != 200:
            raise RuntimeError(
                "Paasteamet vastas HTTP %s — vahemalu puutumata" % resp.status
            )
        body = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body, "live"


_HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)

#: Hub sub-page paths that carry a statistics table worth citing.
_STATS_PATH_RE = re.compile(
    r'/et/(statistika|paeaeste|hoonetulekahjud|tulekahjudes|'
    r'veeonnetustes|kodunoustamised|vabatahtlike|uuringud)[^"]*',
    re.IGNORECASE,
)


def parse_stats_snapshot(html_text: str) -> dict:
    """Parse one statistika-hub payload into the dataset catalogue (pure).

    Extracts the statistics-table sub-pages, the national-portal query
    link, and the dashboard embed the hub references. Unknown pages are
    ignored (never guessed); a payload with none of the three reads as
    an explicitly empty catalogue (dated-negative friendly), never an
    error — absence of tables is data about openness, not a failure.
    """
    hrefs = set(_HREF_RE.findall(html_text or ""))
    tables = sorted({h.split("#")[0] for h in hrefs if _STATS_PATH_RE.search(h)})
    portal = None
    for h in hrefs:
        if "avaandmed.eesti.ee" in h and "paasteamet" in h:
            portal = h
            break
    dashboards = sorted({h for h in hrefs if "recommy.com" in h})
    return {
        "tables": tables,
        "portal": portal,
        "dashboards": dashboards,
        "source": "Paasteamet statistika-hub (rescue.ee, inimloetav koondleht)",
    }


# ---------------------------------------------------------------------------
# P4-012 (demo): accident blackspots + rescue drive-time (point-buffer).
# ---------------------------------------------------------------------------

#: Blackspot-count bands within the buffer: coarse count bands, capped.
BLACKSPOT_BANDS = ((0, 75), (1, 60), (3, 40))


def dim_blackspot_drive_time(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]],
                             coverage: Optional[dict] = None) -> Score:
    """P4-012: blackspot count buffer + straight-line komando penalty."""
    if not origin:
        return None, ("Ohtlikud ristmikud teadmata (EI OLE hinnangut): aadress "
                      "puudub — Transpordiameti onnetuspunktide ja Paasteameti "
                      "komandode (Pohja-Tallinn, Lasnamae, Nomme) kaugus "
                      "selgub aadressi puhvrist, mitte tühjalt")
    spots = _pois_of(pois, BLACKSPOT_KIND)
    stations = _pois_of(pois, RESCUE_STATION_KIND)
    if not spots and not stations:
        return None, ("Ohtlikud ristmikud teadmata (EI OLE hinnangut): "
                      "onnetuspunktide ega komandode inventuuri hetktõmmises "
                      "pole — Paasteameti sündmuste statistika on inimloetav "
                      "koondleht, masinloetavat voogu pole; kontrolli Tark Tee "
                      "intsidente ja lähima komando kaugust kohapeal")
    n = _count_within(origin, spots, BLACKSPOT_RADIUS_M)
    for limit, pts in BLACKSPOT_BANDS:
        if n <= limit:
            score = pts
            break
    else:
        score = 20
    station_txt = "komandode inventuuri pole (EI OLE sõiduaja-hinnangut)"
    if stations:
        nearest, km = _nearest(origin, stations)
        assert nearest is not None and km is not None
        if km > STATION_FAR_KM:
            score = max(0, score - 10)
        station_txt = ("lähim komando %s %.1f km linnulennult (hinnang, "
                       "mitte marsruudi-aeg)" % (nearest.get("name") or "teadmata",
                                                 km))
    stats = _coverage(coverage).get("stats") or {}
    src_txt = ("; Paasteameti koondleht: %d tabelit"
               % len(stats.get("tables", [])) if stats else "")
    return score, ("Ohtlike kohtade puhvri-hinnang: %d onnetuspunkti 500 m "
                   "raadiuses, %s%s — ristmiku ohutus selgub Tark Tee "
                   "intsidentidest ja kooliteede kaardilt" % (n, station_txt,
                                                              src_txt))


# ---------------------------------------------------------------------------
# P4-015 (coverage): insurability fire-density slice (zone join).
# ---------------------------------------------------------------------------

#: Fire-density class bands: the Paasteamet slice only (never a full tariff).
FIRE_BANDS = {"madal": 70, "keskmine": 50, "korge": 25}


def dim_insurability(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]],
                    coverage: Optional[dict] = None) -> Score:
    """P4-015: linnaosa fire-density zone join + illiquidity flag."""
    cov = _coverage(coverage)
    linnaosa = cov.get("linnaosa")
    zones = cov.get("fire_zones") or {}
    cls = zones.get(linnaosa) if linnaosa else None
    if cls not in FIRE_BANDS:
        return None, ("Kindlustatavus teadmata (EI OLE hinnangut): linnaosa "
                      "tulekahjutiheduse tsoonitabelit hetktõmmises pole — "
                      "Paasteameti sündmuste statistika on inimloetav "
                      "koondleht; uuri PZU/ERGO/If tariifitsoone ja KÜ "
                      "kahjuajalugu, uleujutus/varguse jalad on liitmata")
    score = FIRE_BANDS[cls]
    if cls == "korge":
        return score, ("Tulekahjutiheduse tsoon %s: KORGE (hinnang — "
                       "kindlustus-keeldumise / hinnatousu risk, mittelikviidsuse "
                       "lipp): uuri kindlustuspakkumist enne broneerimist; "
                       "uleujutus- ja vargustsoonid on liitmata"
                       % (linnaosa or "?"))
    return score, ("Tulekahjutiheduse tsoon %s: %s (hinnang — ainult "
                   "Paasteameti tuleloik, mitte tariif): uleujutus- ja "
                   "vargustsoonid ning kindlustuspakkumine selguvad "
                   "kindlustusandjalt" % (linnaosa or "?", cls))


# ---------------------------------------------------------------------------
# P4-042 (coverage): chimney-smoke notice cells (coarse hinnang cells).
# ---------------------------------------------------------------------------

def dim_smoke_chorus(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]],
                    coverage: Optional[dict] = None) -> Score:
    """P4-042: coarse smoke-notice cell flag (inside scores, outside NULLs)."""
    notices = _pois_of(pois, SMOKE_NOTICE_KIND)
    if not origin or not notices:
        return None, ("Lõhna/kooriku kaart teadmata (EI OLE hinnangut): "
                      "korstnasuitsu teadete inventuuri (Nomme/Merivälja "
                      "kütteperiood) hetktõmmises pole — pagari/lilla "
                      "ankrud vs suitsu/prügimaja kaebused selguvad "
                      "Keskkonnaameti lõhnakaebustest, mitte ukse-täpsuselt")
    hit = None
    hit_km = None
    for p in notices:
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if km * 1000.0 <= SMOKE_RADIUS_M and (hit_km is None or km < hit_km):
            hit, hit_km = p, km
    if hit is None:
        return None, ("Lõhna/kooriku kaart teadmata (EI OLE hinnangut): "
                      "aadress ei jää uhtegi suitsuteadete jämedasse "
                      "piirkonda — teadete puudumine ei ole puhta õhu "
                      "hinnang; küsi Keskkonnaameti lõhnakaebusi sektori "
                      "kaupa")
    cov = _coverage(coverage)
    season = cov.get("smoke_season") or {}
    areas = ", ".join(season.get("areas") or [hit.get("area") or "teadmata"])
    return 45, ("Korstnasuitsu piirkond %s (ulempiir 45, jäme hinnang, "
                "mitte ukse-täpsus): kütteperioodi suits %s kandis — "
                "pagari/lilla vs suitsu tasakaal selgub kohapealsel "
                "jalutuskäigul" % (hit.get("area") or "teadmata", areas))


# ---------------------------------------------------------------------------
# P4-047 (coverage): small-horrors event calendar (city-wide calendar dim).
# ---------------------------------------------------------------------------

#: Yearly notice-count bands for the city event-traffic calendar.
HORROR_BANDS = ((0, 75), (2, 60), (5, 45))


def dim_small_horrors(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]],
                      coverage: Optional[dict] = None) -> Score:
    """P4-047: city-wide event-traffic calendar band (origin-independent)."""
    cal = _coverage(coverage).get("event_calendar")
    if not isinstance(cal, dict) or not cal:
        return None, ("Väikesed õudused teadmata (EI OLE hinnangut): "
                      "üritusliikluse/ilutulestiku teadete kalendrit "
                      "hetktõmmises pole — kajakad/lehepuhurid/mopeedid "
                      "selguvad Keskkonnaameti mürakaebustest, 4am sahavedu "
                      "talihoolduse veograafikust")
    months = sorted(m for m in cal if isinstance(m, int) and 1 <= m <= 12)
    total = sum(len(cal[m]) for m in months if isinstance(cal[m], list))
    for limit, pts in HORROR_BANDS:
        if total <= limit:
            score = pts
            break
    else:
        score = 30
    peak = ", ".join(MONTH_ET[m] for m in months[:3]) or "teadmata kuud"
    return score, ("Tallinna ürituskalendri hinnang: %d teadet (%s jm — "
                   "hinnang, mitte ukse-täpsus): ilutulestiku alleed ja "
                   "sahaveo hommikud selguvad teadete kalendrist"
                   % (total, peak))


# ---------------------------------------------------------------------------
# P4-058 (coverage): falling-ice notices with dates (dated parcel dims).
# ---------------------------------------------------------------------------

def dim_falling_ice(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]],
                    coverage: Optional[dict] = None) -> Score:
    """P4-058: dated ice-fall notice flag with season recency (in-radius only)."""
    notices = _pois_of(pois, ICE_NOTICE_KIND)
    if not origin or not notices:
        return None, ("Jääpurika-risk teadmata (EI OLE hinnangut): "
                      "jääpurikate/lume teadete inventuuri (tänav + "
                      "hooaeg) hetktõmmises pole — katuse tüüp (EHR) ja "
                      "rannikuastangu nihe (Maa-amet) on liitmata; "
                      "kontrolli KÜ katusehoolduse kulusid")
    near = [p for p in notices
            if haversine_km(origin, (p["lat"], p["lon"])) * 1000.0 <= ICE_RADIUS_M]
    if not near:
        return None, ("Jääpurika-risk teadmata (EI OLE hinnangut): "
                      "300 m raadiuses dateeritud teadet pole — teadete "
                      "puudumine ei ole ohutuse hinnang; kontrolli KÜ "
                      "katusehoolduse kulusid ja tänava hoiatusi")
    now_year = _season_start(_coverage(coverage).get("season"))
    best = None
    for p in near:
        yr = _season_start(p.get("season"))
        if yr is None:
            rank = 2  # undated: capped mid flag, never fresh
        elif now_year is None:
            rank = 2
        elif yr == now_year:
            rank = 0
        elif yr == now_year - 1:
            rank = 1
        else:
            rank = 3
        if best is None or rank < best[0]:
            best = (rank, p)
    assert best is not None
    rank, hit = best
    street = hit.get("street") or "teadmata tänav"
    if rank == 0:
        return 35, ("Jääpurika-teade %s (jooksev hooaeg %s, hinnang): "
                    "kõnnitee vastutus selgub KÜ katusehooldusest ja "
                    "tänava hoiatustest" % (street, hit.get("season")))
    if rank == 1:
        return 45, ("Jääpurika-teade %s (eelmine hooaeg %s, hinnang): "
                    "korda võib — kontrolli, kas katus on hooldatud"
                    % (street, hit.get("season")))
    if rank == 3:
        return 55, ("Jääpurika-teade %s (vana, %s, nõrk hinnang): "
                    "katus võib olla vahepeal hooldatud — küsi KÜ-lt"
                    % (street, hit.get("season")))
    return 45, ("Jääpurika-teade %s (dateerimata, ulempiir 45, hinnang): "
                "hooaeg puudub — kontrolli tänava hoiatusi ja KÜ "
                "katusehooldust" % street)


# ---------------------------------------------------------------------------
# P4-059 (coverage): wood-burning restriction rule join.
# ---------------------------------------------------------------------------

#: Restriction-rule bands: the rule join, never a measurement.
BURN_BANDS = {"keelatud": 20, "piiratud": 50, "lubatud": 75}


def dim_burn_restriction(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]],
                         coverage: Optional[dict] = None) -> Score:
    """P4-059: per-parcel tahkekutte rule join (stranded-stove check)."""
    cov = _coverage(coverage)
    linnaosa = cov.get("linnaosa")
    zones = cov.get("burn_zones") or {}
    rule = zones.get(linnaosa) if linnaosa else None
    if rule not in BURN_BANDS:
        return None, ("Tahkekütte piirang teadmata (EI OLE hinnangut): "
                      "piirangualade tabelit (Kesklinn/Vanalinna prioriteet) "
                      "hetktõmmises pole — EHR kütte liik ja korstnateated "
                      "on liitmata; uuri Keskkonnaameti piiranguteateid ja "
                      "kuulutuse ahi/kamin-märget")
    score = BURN_BANDS[rule]
    if rule == "keelatud":
        return score, ("Tahkekütte tsoon %s: KEELATUD (hinnang — ahjuvara "
                       "võib jääda hätta): kontrolli EHR kütte liiki ja "
                       "kliimakava üleminekutsoone" % (linnaosa or "?"))
    return score, ("Tahkekütte tsoon %s: %s (hinnang — reegli-liides, "
                   "mitte mõõt): ahju/kamina vara selgub EHR-ist ja "
                   "kuulutusest" % (linnaosa or "?", rule))


# ---------------------------------------------------------------------------
# P4-062 (coverage): hex operational flags (Päästeamet ice-warning slice).
# ---------------------------------------------------------------------------

def dim_hex_watch(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]],
                  coverage: Optional[dict] = None) -> Score:
    """P4-062: coarse hex-watch flag read (inside scores, outside NULLs)."""
    flags = _pois_of(pois, HEX_WATCH_KIND)
    if not origin or not flags:
        return None, ("Kvartali hooldus teadmata (EI OLE hinnangut): "
                      "jääpurika-hoiatuste heksilippe hetktõmmises pole — "
                      "rotikaebused (Keskkonnaamet) on liitmata; uuri KÜ "
                      "prügiveo/hoolduse kulusid")
    hit = None
    hit_km = None
    for p in flags:
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if km * 1000.0 <= HEX_RADIUS_M and (hit_km is None or km < hit_km):
            hit, hit_km = p, km
    if hit is None:
        return None, ("Kvartali hooldus teadmata (EI OLE hinnangut): "
                      "500 m raadiuses heksilippu pole — lippude "
                      "puudumine ei ole hooldatuse hinnang (heks, mitte "
                      "aadressid); küsi KÜ-lt")
    names = ", ".join(hit.get("flags") or ["teadmata lipp"])
    return 40, ("Heksi hoolduslipp %s (ulempiir 40, jäme hinnang, heks "
                "mitte aadress): %s — rotikaebuste jalg on liitmata, "
                "kontrolli KÜ hoolduskulusid" % (hit.get("hex") or "?",
                                                 names))


#: Registry for UI/API wiring on integration: key -> (param id, title, fn).
P4PAASTE_DIMS = {
    "blackspot_drive_time": ("P4-012", "Õnnetuskohad + pääste sõiduaeg",
                             dim_blackspot_drive_time),
    "insurability": ("P4-015", "Kindlustatavus (tule-tihedus)",
                     dim_insurability),
    "smoke_chorus": ("P4-042", "Lõhna/kooriku piirkond",
                     dim_smoke_chorus),
    "small_horrors": ("P4-047", "Väikesed õudused (kalender)",
                      dim_small_horrors),
    "falling_ice": ("P4-058", "Jääpurikad (dateeritud)",
                    dim_falling_ice),
    "burn_restriction": ("P4-059", "Tahkekütte piirang (reegel)",
                         dim_burn_restriction),
    "hex_watch": ("P4-062", "Heksi hoolduslipud",
                  dim_hex_watch),
}

#: Param-number wiring for the central weight-rebalance follow-up.
P4PAASTE_PARAM_IDS = {
    "blackspot_drive_time": 12,
    "insurability": 15,
    "smoke_chorus": 42,
    "small_horrors": 47,
    "falling_ice": 58,
    "burn_restriction": 59,
    "hex_watch": 62,
}


def score_p4_paaste(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]],
                    coverage: Optional[dict] = None
                    ) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All seven P4-paaste dims at once: ({key: score}, [reasons]).

    NULL dims contribute no reasons (no fake evidence) — same rollup
    contract as sibling score_p4_ilm.
    """
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key, (_, _, fn) in P4PAASTE_DIMS.items():
        v, reason = fn(origin, pois, coverage)
        dims[key] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
