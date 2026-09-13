"""P4 RB dims (issues #281 demo + #355 coverage): Rail Baltica Estonia.

Params (this module only — sibling legs untouched):
* P4-014 Rail Baltica / tram-extension construction phase (demo, batch 1)
* P4-006 neighbouring detailplaneering pipeline, RB/tram-corridor
  reservation leg (coverage, batch 1 — parameters4.md P4-006 source (6))

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#281 acceptance): Rail Baltica Estonia has NO open bulk endpoint for a
machine-readable Uhlemiste construction timetable. Polite evidence,
7 tiny requests total (custom UA, headers + two front pages, one
3 kB wp-json search, no scrape):
* HEAD https://www.railbaltica.org/ -> HTTP 200, WordPress
  (wp-json search "Ulemiste" returns news posts only — press
  releases such as the tram-tunnel completion and the
  Uhlemiste-Lasnamae construction start — no timetable feed)
* HEAD https://railbaltica.ee/ -> HTTP 200 BUT the body is a Zone
  parking page ("Domain is Registered", 71 533 B, zero data links)
* HEAD https://www.rbestonia.ee/ -> HTTP 200, "Rail Baltic Estonia -
  Avaleht" (101 682 B front page, human site)
* GET https://www.rbestonia.ee/avalikud-andmed/ -> HTTP 200
  ("Avalikud andmed", 149 328 B): links to dokumendid / ehituse-seis /
  hanked / kvartaalsed-infokirjad (human document library), one
  /naidissoidugraafik/ sample-passenger-timetable page, and the
  gis.railbaltica.org ArcGIS Experience Builder viewer (human map,
  no bulk download). The ".json" hits are WordPress plumbing
  (oEmbed/emoji/gravityforms) — no CSV/XLSX/WFS/ICS bulk feed.
Raw headers/pages cached at /tmp/rb-open/ (TTL: one-off check, kept
for the PR record, never committed). So the live path below is honest
plumbing with NO live data: fetch_rb_snapshot performs NO request
while RB_BULK_URL is None, scorers stay NULL with an Estonian EI OLE
reason, and the scored shapes are proven on fixtures only.
Reopening checklist lives in docs/p4_rb.md.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components including the timetable expiry;
every NULL reason says "EI OLE" and names the missing input.
Transport errors are never cached as data (fetch_rb_snapshot stores
a body only on HTTP 200 with JSON content, else returns None). A
measured value from the snapshot (active phase in the window; a
corridor row in the window; zero corridors with corridors elsewhere)
scores — while a missing join (no snapshot, no row in the window,
expiry unknown, timetable expired) stays NULL: absence of data is
unknown, never good. Distances are bird-flight, never routed.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_rb_snapshot(cache_dir): polite pull, max 1 download / 30 d
  per cache dir (RB_TTL_S; parameters4.md P4-014 cadence: monthly,
  expiry-dated; the P4-006 RB leg rides the same monthly ticket —
  corridor reservations change on project milestones, not weekly).
  Cache hit within TTL performs NO request. While no open bulk
  endpoint exists (RB_BULK_URL is None) it performs no request at
  all and returns the fresh-cache path or None. Single GET with an
  identifying UA once a bulk URL is known, no retries (HTTP 429 is
  a stop signal, 7.4).
* parse_rb_snapshot / works_to_pois / corridors_to_pois /
  snapshot_to_pois: pure offline readers over the cached JSON
  snapshot (schema documented below). Network lives ONLY in
  fetch_rb_snapshot; scorers and tests never touch it.
* One snapshot, two tables, no new source for coverage: "works"
  feeds P4-014, "corridors" feeds P4-006 (this is why demo +
  coverage pair in ONE PR — #355 expects no new plumbing, said in
  docs/p4_rb.md).

Snapshot schema (what a future adapter would store; fixtures match it):
  {"works": [{"work_id": str, "title": str, "phase": str, "lat": float,
              "lon": float, "valid_from": "YYYY-MM-DD"|None,
              "valid_until": "YYYY-MM-DD"|None}],
   "corridors": [{"corr_id": str, "name": str, "lat": float, "lon": float}]}
Malformed rows are skipped, never faked; a missing/unparseable file
parses to None (unknown), never to an empty snapshot. A work row
without a parseable valid_until has unknown expiry and is excluded
from scoring (the calendar dim is only honest when expiry-dated);
rows not yet started (today < valid_from) are future work and score
only via the corridor leg.

Style mirrors services/scoring/dims_p4_tpr.py (#250/#334, the honest-
plumbing precedent): pure scorers (origin, pois) -> (Optional[int
0..100], Estonian reason), local helpers (no livability import —
importing it here would turn the future central hook into a cycle,
same precedent as PRs #100/#106/#115). Unlike peatus there is NO
staged Overpass fragment and no tag mapping: OSM has no honest tag
for RB construction phases or corridor reservations, so there is
nothing for the live path to fetch (same rationale as the group20a
no-map batches).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because the #355 body states it
  "extends the demoed ingestion" with "no new plumbing expected":
  the corridors table is a same-snapshot second table (P4-006
  source (6): "Rail Baltica/tram-corridor reservations"), not a
  second source.
* P4-014 is a calendar dim: the scorer takes an optional `today`
  (ISO "YYYY-MM-DD" or date, default date.today()) so the expiry
  rule is deterministic under test; production callers pass the
  valuation date. Tests always pass explicit dates (hermetic).
* P4-014 bands are a first-cut judgment with no live calibration
  (ehituses -> 35 nuisance-now/premium-later, planeerimisel -> 55
  future works uncertain, valmis -> 75 nuisance gone + connection
  premium); they MUST be recalibrated from a real timetable on
  reopen (docs/p4_rb.md checklist). Unknown phase strings stay
  NULL: an unverified label is not a phase.
* P4-014 window 800 m (nuisance footprint: dust/night works/
  detours carry further than a planning buffer) vs the 500 m
  P4-006 planning buffer — bird-flight in both, never routed.
* P4-006 RB leg bands (<=150 m -> 30 at the doorstep, <=500 m ->
  55 reservation pressure, measured clear -> 85) are first-cut too;
  a missing corridor link is unknown (NULL), never clear.
* Sibling-leg split (no double-scoring): P4-006 this-parcel and
  register legs stay in dims_p4_maa_kataster.dim_naaber_planeering
  and dims_p4_tpr.dim_pipeline_500m; this module scores ONLY the
  RB/tram-corridor reservation leg with _rb-suffixed dim keys.

Integration (deliberately NOT done here): wiring the snapshot into a
listing pipeline plus rebalancing livability.WEIGHTS must be one joint
change across all batches — existing tests pin set(WEIGHTS) exactly,
so per-batch WEIGHTS edits would break every sibling. No shared files
touched: 3 new files only.
"""

import datetime
import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple, Union

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Human status page (verified 2026-09-13: HTTP 200, document library).
RB_INDEX_URL = "https://www.rbestonia.ee/ehituse-seis/"

#: Open bulk endpoint: NONE found 2026-09-13 (dated negative, see module
#: docstring). Stays None until the reopening checklist in docs/p4_rb.md
#: names a verified bulk URL; while None, fetch performs no requests.
RB_BULK_URL: Optional[str] = None

#: Max one download per 30 d per cache dir (parameters4.md P4-014: monthly,
#: expiry-dated; the P4-006 RB leg rides the same monthly ticket).
#: Stated TTL.
RB_TTL_S = 30 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "rb-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
RB_UA = "home-finder RB openness-check (max 1 req/30d, no scrape)"

#: Work phases counted by the P4-014 calendar dim (parameters4.md P4-014).
PHASE_ACTIVE = "ehituses"
PHASE_PLANNED = "planeerimisel"
PHASE_DONE = "valmis"


def fetch_rb_snapshot(cache_dir: str,
                      ttl_s: int = RB_TTL_S,
                      bulk_url: Optional[str] = RB_BULK_URL,
                      ) -> Optional[str]:
    """Polite RB snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with RB_UA and a 30 s
    timeout; the body is stored only on HTTP 200 with JSON content, else
    None is returned and nothing is cached (transport errors are never
    data). No retries — HTTP 429/errors are a stop signal. Scorers never
    call this; tests cover the cache-hit and no-endpoint paths with a
    stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    if bulk_url is None:
        return None
    try:
        req = urllib.request.Request(bulk_url, headers={"User-Agent": RB_UA})
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

def parse_rb_snapshot(path: str) -> Optional[dict]:
    """Read a cached RB snapshot file. Offline, stdlib.

    Returns {"works": [...], "corridors": [...]} with malformed rows
    skipped, or None when the file is missing/unparseable (unknown,
    never an empty snapshot — scorers must not read "no file" as
    "no works").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    works = raw.get("works") if isinstance(raw.get("works"), list) else []
    corrs = (raw.get("corridors")
             if isinstance(raw.get("corridors"), list) else [])
    return {"works": [r for r in works if isinstance(r, dict)],
            "corridors": [r for r in corrs if isinstance(r, dict)]}


def _finite_latlon(row: dict) -> Optional[Tuple[float, float]]:
    """(lat, lon) when both are finite non-bool numbers, else None."""
    try:
        lat = row["lat"]
        lon = row["lon"]
        if isinstance(lat, bool) or isinstance(lon, bool):
            return None
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError, KeyError):
        return None
    if math.isfinite(lat) and math.isfinite(lon):
        return lat, lon
    return None


def _iso_date(v) -> Optional[datetime.date]:
    """Parse an ISO YYYY-MM-DD value; garbage/missing -> None."""
    if isinstance(v, datetime.date):
        return v
    if not isinstance(v, str):
        return None
    try:
        return datetime.date.fromisoformat(v.strip())
    except ValueError:
        return None


def works_to_pois(works: List[dict]) -> List[dict]:
    """Work rows -> scorer POIs. Rows without coords stay out (never
    faked); expiry strings are normalised to ISO or None (unknown)."""
    pois = []
    for row in works:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        phase = row.get("phase")
        pois.append({
            "kind": "rb_work_p4",
            "lat": lat, "lon": lon,
            "work_id": str(row.get("work_id") or "tundmatu"),
            "title": str(row.get("title") or "tundmatu"),
            "phase": (str(phase).strip().lower()
                      if phase is not None else None),
            "valid_from": _iso_date(row.get("valid_from")),
            "valid_until": _iso_date(row.get("valid_until")),
        })
    return pois


def corridors_to_pois(corridors: List[dict]) -> List[dict]:
    """Corridor rows -> scorer POIs. Rows without coords stay out."""
    pois = []
    for row in corridors:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        pois.append({
            "kind": "rb_corridor_p4",
            "lat": lat, "lon": lon,
            "corr_id": str(row.get("corr_id") or "tundmatu"),
            "name": str(row.get("name") or "tundmatu"),
        })
    return pois


def snapshot_to_pois(snapshot: Optional[dict]) -> List[dict]:
    """Parsed snapshot (or None) -> scorer POIs for both dims. Pure."""
    if not isinstance(snapshot, dict):
        return []
    works = snapshot.get("works")
    corrs = snapshot.get("corridors")
    pois: List[dict] = []
    if isinstance(works, list):
        pois.extend(works_to_pois(works))
    if isinstance(corrs, list):
        pois.extend(corridors_to_pois(corrs))
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


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _near(origin: Tuple[float, float], pois: List[dict], kind: str,
          window_m: float) -> List[Tuple[float, dict]]:
    """[(distance_m, poi)] of well-formed POIs of kind within window. Pure."""
    hits = []
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        try:
            lat = p["lat"]
            lon = p["lon"]
            if isinstance(lat, bool) or isinstance(lon, bool):
                continue
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError, KeyError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if d <= window_m:
            hits.append((d, p))
    hits.sort(key=lambda h: h[0])
    return hits


def _has_kind(pois: List[dict], kind: str) -> bool:
    """True when the snapshot holds at least one well-formed POI of kind."""
    return bool(_near((0.0, 0.0), pois, kind, 20_000_000.0))


def _as_today(today: Union[None, str, datetime.date]) -> datetime.date:
    """Normalise the valuation date; None means the actual current date."""
    if today is None:
        return datetime.date.today()
    parsed = _iso_date(today)
    if parsed is None:
        raise ValueError("today must be ISO YYYY-MM-DD or a date, got %r"
                         % (today,))
    return parsed


# ---------------------------------------------------------------------------
# Windows + bands (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: P4-014 construction-nuisance window (parameters4.md: calendar dim;
#: 800 m nuisance footprint is the module judgment call).
NUISANCE_WINDOW_M = 800.0
#: P4-006 corridor-reservation buffer (parameters4.md: 500 m).
CORRIDOR_WINDOW_M = 500.0
#: Doorstep distance: a reservation on the buyer's street.
DOORSTEP_WINDOW_M = 150.0

#: Phase -> score (high = calm/good for the buyer today). First-cut
#: bands, MUST be recalibrated from a real timetable on reopen.
PHASE_SCORES = {
    PHASE_ACTIVE: 35,
    PHASE_PLANNED: 55,
    PHASE_DONE: 75,
}
#: Nearest corridor reservation distance -> pressure score (high = calm).
NEAR_PRESSURE_SCORE = 30
FAR_PRESSURE_SCORE = 55
#: Measured clear: no corridor in 500 m while the snapshot holds
#: corridors elsewhere.
CLEAR_SCORE = 85


# ---------------------------------------------------------------------------
# P4-014: Rail Baltica / tram construction phase, calendar dim (demo).
# ---------------------------------------------------------------------------

def dim_ehitusfaas_rb(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]],
                      today: Union[None, str, datetime.date] = None,
                      ) -> Score:
    """P4-014: nearest live timetable phase within 800 m (high = calm).

    Calendar dim with expiry: only work rows whose timetable covers the
    valuation date count (valid_from <= today <= valid_until; a row
    without a parseable valid_until has unknown expiry and is
    excluded). Expired/unknown rows never score — a stale timetable is
    unknown, not good. Beyond-window is unknown, never calm.
    """
    if not origin or pois is None:
        return None, ("Ehitusfaasi info puudub (EI OLE RB-hetktõmmist: "
                      "masinloetavat ehitusgraafikut pole, allikad on "
                      "veebiuudised ja dokumendid)")
    day = _as_today(today)
    if not _has_kind(pois, "rb_work_p4"):
        return None, ("Ehitusfaasi info puudub (EI OLE tööde-RB-hetktõmmist "
                      "hetkel: tühi tõmmis ei ole rahulik otsus)")
    hits = _near(origin, pois, "rb_work_p4", NUISANCE_WINDOW_M)
    live: List[Tuple[float, dict]] = []
    stale = 0
    for d, p in hits:
        start = p.get("valid_from")
        end = p.get("valid_until")
        if end is None:
            stale += 1
            continue
        if start is not None and day < start:
            stale += 1
            continue
        if day > end:
            stale += 1
            continue
        live.append((d, p))
    if not live:
        if stale:
            return None, ("Ehitusfaasi info puudub (EI OLE kehtivat "
                          "graafikut %s seisuga: %d lähedast tööd on "
                          "aegunud/tundmatu kehtivusega — vana graafik ei "
                          "ole rahulik otsus)" % (day.isoformat(), stale))
        return None, ("Ehitusfaasi info puudub (EI OLE RB-tööd 800 m "
                      "aknas %s seisuga — akna taga on teadmata, mitte "
                      "rahulik)" % day.isoformat())
    d0, p0 = live[0]
    phase = p0.get("phase")
    score = PHASE_SCORES.get(phase) if isinstance(phase, str) else None
    if score is None:
        return None, ("Ehitusfaasi info puudub (EI OLE kinnitatud faasi: "
                      "töö %s %s on märgitud '%s' — kontrollimata silt "
                      "ei ole faas)" % (p0.get("work_id"), _fmt_m(d0), phase))
    end_txt = p0.get("valid_until").isoformat()
    if phase == PHASE_ACTIVE:
        why = ("müra/tolm täna, ühenduse väärtus hiljem")
    elif phase == PHASE_PLANNED:
        why = ("tulevased tööd, mõju ebaselge")
    else:
        why = ("tööd valmis, ühendus olemas")
    return score, ("RB/trammi ehitusfaas (hinnang, graafik kehtib kuni "
                   "%s): töö %s '%s' %s, faas '%s' (%s) → skoor %d"
                   % (end_txt, p0.get("work_id"), p0.get("title"),
                      _fmt_m(d0), phase, why, score))


# ---------------------------------------------------------------------------
# P4-006: corridor-reservation leg, 500 m (coverage).
# ---------------------------------------------------------------------------

def dim_koridor_reserv_rb(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-006: nearest RB/tram-corridor reservation within 500 m.

    Only the RB-corridor leg of the param: a reservation at the
    doorstep (<=150 m) scores 30, one inside 500 m scores 55, and a
    measured clear (no corridor in 500 m while the snapshot holds
    corridors elsewhere) scores 85. No corridor link is unknown
    (NULL), never clear. Sibling register/kataster legs untouched.
    """
    if not origin or pois is None:
        return None, ("Koridorireservi info puudub (EI OLE RB-hetktõmmist: "
                      "masinloetavat reservatsioonikihti pole, allikad on "
                      "veebikaart ja dokumendid)")
    if not _has_kind(pois, "rb_corridor_p4"):
        return None, ("Koridorireservi info puudub (EI OLE koridori-"
                      "RB-hetktõmmist hetkel: tühi tõmmis ei ole puhas "
                      "otsus)")
    hits = _near(origin, pois, "rb_corridor_p4", CORRIDOR_WINDOW_M)
    if not hits:
        return CLEAR_SCORE, ("RB/trammi koridorireserv (hinnang): 500 m "
                             "raadiuses reserveeritud koridori pole "
                             "(tõmmises on koridore mujal) → skoor %d"
                             % CLEAR_SCORE)
    d0, c0 = hits[0]
    if d0 <= DOORSTEP_WINDOW_M:
        return NEAR_PRESSURE_SCORE, (
            "RB/trammi koridorireserv (hinnang): %s otse ukse ees (%s) — "
            "tulevane ehitus/vaate risk → skoor %d"
            % (c0.get("name"), _fmt_m(d0), NEAR_PRESSURE_SCORE))
    return FAR_PRESSURE_SCORE, (
        "RB/trammi koridorireserv (hinnang): lähim %s %s (500 m aknas) — "
        "reservatsioonisurve → skoor %d"
        % (c0.get("name"), _fmt_m(d0), FAR_PRESSURE_SCORE))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_RB_DIMS = (
    ("ehitusfaas_rb", "P4-014", dim_ehitusfaas_rb),
    ("koridor_reserv_rb", "P4-006", dim_koridor_reserv_rb),
)


def score_p4_rb(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]],
                today: Union[None, str, datetime.date] = None,
                ) -> Dict[str, Optional[int]]:
    """P4 RB dims for one listing (entry point for the follow-up)."""
    out: Dict[str, Optional[int]] = {}
    for key, _, fn in P4_RB_DIMS:
        if key == "ehitusfaas_rb":
            out[key] = dim_ehitusfaas_rb(origin, pois, today)[0]
        else:
            out[key] = fn(origin, pois)[0]
    return out
