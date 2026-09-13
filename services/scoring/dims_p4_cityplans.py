"""P4 cityplans dims (issues #282 demo + #356 coverage): Tallinna strategic
plans & stats (uldplaneering 2035, transpordi arengukava, arengukava,
ehitusstatistika, aarealade kava, tram plans).

Params (this module only — sibling legs untouched, see the split below):
* P4-014 tram-extension construction phase, tram-timetable slice (demo,
  batch 1 — parameters4.md P4-014 sources (2)+(3): tram timetables,
  transpordi arengukava + uldplaneering 2035)
* P4-006 neighbouring-plan pressure, uldplaneering arenguala leg
  (coverage, batch 1 — P4-006 source (3): uldplaneering 2035
  lahtematerjalid + teemaplaneeringud)
* P4-019 KOV fiscal health, arengukava investment-table leg (coverage,
  batch 2 — P4-019 source (5): Tallinna arengukava investeeringute tabel)
* P4-025 micro-liquidity, rahvastikuprognoos leg (coverage, batch 2 —
  P4-025 source (6): arengukava rahvastikuprognoos per linnaosa)
* P4-037 policy exposure, planned-zone leg (coverage, batch 3 — P4-037
  sources (2)+(3): tasulise parkimise + autovaba ala laienemisplaanid,
  ummikumaksu arutelud/otsused)
* P4-041 glimpse economics, vaatekoridor-preservation leg (coverage,
  batch 4 — P4-041 source (4): uldplaneering vaatekohtade register)
* P4-050 permit glut vs completions, ehitusstatistika leg (coverage,
  batch 5 — P4-050 source (4): Tallinna ehitusstatistika per linnaosa)
* P4-061 last-shop/pharmacy/ATM + bus-cut tracker, aarealade-kava leg
  (coverage, batch 5 — P4-061 source (5): aarealade teenuste kava)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#282 acceptance): the strategic plans & stats live as human-facing CMS
pages and document libraries with NO open bulk endpoint. Polite
evidence, ~7 tiny requests total (custom UA, headers + one 74 kB plan
page, no scrape):
* HEAD https://www.tallinn.ee/et/uldplaneering -> HTTP 301 to
  https://www.tallinn.ee/et/kristiine/uldplaneering (generic slugs
  route into district subsites — Cloudflare CMS, no stable bulk URL)
* HEAD https://www.tallinn.ee/et/arengukava -> HTTP 301 to a district
  subsite (same CMS routing)
* HEAD https://www.tallinn.ee/et/transpordi-arengukava -> HTTP 404
  (no stable transport-plan slug)
* HEAD https://www.railbaltica.org/ -> HTTP 200 WordPress (press
  releases only — timetable feed covered by the sibling #281 RB probe)
* HEAD https://www.tlt.ee/ -> HTTP 301 to https://tlt.ee/ (WordPress;
  machine GTFS feed already covered by sibling dims_p4_peatus)
* GET https://www.tallinn.ee/et/kristiine/uldplaneering -> HTTP 200,
  text/html, 74 300 B, "<title>Uldplaneering | Tallinn</title>", zero
  avaandmed/opendata/geojson/wfs/csv/xlsx links (human page).
Raw headers/page cached at /tmp/cityplans-open/ (TTL: one-off check,
kept for the PR record, never committed). So the live path below is
honest plumbing with NO live data: fetch_cityplans_snapshot performs
NO request while CITYPLANS_BULK_URL is None, every scorer then
returns None with an Estonian EI OLE reason, and the scored shapes
are proven on fixtures only. Reopening checklist lives in
docs/p4_cityplans.md.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components including timetable expiry where
dated; every NULL reason says "EI OLE" and names the missing input.
Transport errors are never cached as data (fetch_cityplans_snapshot
stores a body only on HTTP 200 with JSON content, else returns
None). A measured value from the snapshot (live tram phase in the
window; an arenguala/investment/forecast/policy/corridor/stats/
fringe row in the window; measured clear where stated) scores — a
real signal — while a missing join (no snapshot, no row in the
window, count None, expiry unknown, timetable expired) stays NULL:
absence of data is unknown, never good. Distances are bird-flight,
never routed or parcel-exact.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_cityplans_snapshot(cache_dir): polite pull, max 1 download /
  30 d per cache dir (CITYPLANS_TTL_S; parameters4.md P4-014 cadence:
  monthly, expiry-dated; all seven coverage legs ride the same
  monthly ticket — strategic reservations, investment tables,
  forecasts, planned zones, view corridors, quarterly stats and the
  fringe checklist change on plan milestones, not weekly; weekly
  freshness for P4-006 stays with the sibling TPR leg). Cache hit
  within TTL performs NO request. While no open bulk endpoint exists
  (CITYPLANS_BULK_URL is None) it performs no request at all and
  returns the fresh-cache path or None. Single GET with an
  identifying UA once a bulk URL is known, no retries (HTTP 429 is a
  stop signal, 7.4).
* parse_cityplans_snapshot / tramworks_to_pois / arengualad_to_pois /
  investments_to_pois / forecasts_to_pois / policy_to_pois /
  corridors_to_pois / buildstats_to_pois / fringe_to_pois /
  snapshot_to_pois: pure offline readers over the cached JSON
  snapshot (schema documented below). Network lives ONLY in
  fetch_cityplans_snapshot; scorers and tests never touch it.
* One snapshot, eight tables, no new source for coverage:
  "tramworks" feeds P4-014, "arengualad" feeds P4-006,
  "investeeringud" feeds P4-019, "prognoos" feeds P4-025,
  "poliitika" feeds P4-037, "vaatekoridorid" feeds P4-041,
  "ehitusstat" feeds P4-050, "aarealad" feeds P4-061 (this is why
  demo + coverage pair in ONE PR — #356 expects no new plumbing
  beyond the demoed ingestion).

Snapshot schema (what a future adapter would store; fixtures match it):
  {"tramworks": [{"work_id": str, "title": str, "phase": str,
                  "lat": float, "lon": float,
                  "valid_from": "YYYY-MM-DD"|None,
                  "valid_until": "YYYY-MM-DD"|None}],
   "arengualad": [{"zone_id": str, "kind": "arenguala"|"teemaplaneering",
                   "lat": float, "lon": float}],
   "investeeringud": [{"area_code": str, "lat": float, "lon": float,
                       "invest_m_eur": float|None,
                       "trend": "kasv"|"stabiilne"|"kahaneb"|None}],
   "prognoos": [{"area_code": str, "lat": float, "lon": float,
                 "pop_change_pct": float|None,
                 "school_plan": "avatakse"|"suletakse"|"stabiilne"|None}],
   "poliitika": [{"zone_id": str,
                  "kind": "tasuline_parkimine"|"autovaba"|
                          "ummikumaks_arutelu",
                  "lat": float, "lon": float}],
   "vaatekoridorid": [{"corr_id": str, "lat": float, "lon": float}],
   "ehitusstat": [{"area_code": str, "lat": float, "lon": float,
                   "permits_q": int|None, "completions_q": int|None}],
   "aarealad": [{"settlement": str, "lat": float, "lon": float,
                 "shop": bool, "pharmacy": bool, "atm": bool,
                 "bus_cuts": bool}]}
Malformed rows are skipped, never faked; a missing/unparseable file
parses to None (unknown), never to an empty snapshot. A tram row
without a parseable valid_until has unknown expiry and is excluded
from scoring (the calendar dim is only honest when expiry-dated).

Style mirrors services/scoring/dims_p4_rb.py (#281/#355, the honest-
plumbing precedent): pure scorers (origin, pois) -> (Optional[int
0..100], Estonian reason), local helpers (no livability import —
importing it here would turn the future central hook into a cycle,
same precedent as PRs #100/#106/#115). There is NO staged Overpass
fragment and no tag mapping: OSM has no honest tag for tram works
phases, arengukava investment rows, planned congestion zones or
fringe checklists, so there is nothing for the live path to fetch
(same rationale as the group20a no-map batches).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because the #356 body states it
  "extends the demoed ingestion" with "no new plumbing expected":
  the seven coverage tables are same-snapshot second tables, not new
  sources (same pairing rationale as the #281/#355 RB PR, which
  landed while this branch was being prepared — see the sibling-leg
  split below).
* P4-014 pairing rationale (why a second P4-014 leg after #281):
  the RB PR scores the Rail Baltica Ulemiste-works slice
  (dim_ehitusfaas_rb off the rbestonia timetable); this module scores
  the TRAM slice of the same param's source list (P4-014 sources
  (2)+(3): Vanasadama tramm / Pelguranna-Liivalaia timetables,
  transpordi arengukava + uldplaneering 2035). Same calendar shape
  and bands (ehituses -> 35, planeerimisel -> 55, valmis -> 75),
  same 800 m nuisance footprint — consistency is deliberate — with
  _cityplans-suffixed keys so the slices never double-score. Bands
  MUST be recalibrated from a real timetable on reopen.
* P4-006 pairing rationale: kataster/TPR/RB score the this-parcel,
  menetluses-register and corridor-reservation legs; this module
  scores ONLY the uldplaneering arenguala/teemaplaneering leg
  (source (3)). Softer bands than the RB corridor leg (<=200 m ->
  50, <=500 m -> 65, measured clear -> 85): a development area is
  planning pressure, not a reserved corridor at the doorstep.
* P4-019 scores the TREND (kasv/stabiilne/kahaneb) from the
  arengukava table, printing the invest figure as context; the
  maamaks rate level + trend stays in dims_p4_emta.dim_fiscal_health
  (EMTA slice). Incomplete rows (invest None, trend unknown) stay
  NULL. Window 1500 m (linnaosa grain).
* P4-025 scores the rahvastikuprognoos pop_change_pct band modulated
  by the school open/close plan (suletakse -10, avatakse +5 capped);
  the REL2021 1 km age/migration/vacancy grid stays in
  dims_p4_rel2021.dim_micro_liquidity_rel and the school-feed NULL
  stays in dims_p4_haridus. Window 1500 m (linnaosa grain).
* P4-037 scores ONLY the planned-zone exposure (ummikumaks_arutelu
  -> 45 flagged "arutelu, mitte otsus", autovaba -> 50,
  tasuline_parkimine -> 60); automaks bands stay in EMTA, the
  restriction leg in trans, commute offsets in peatus/TLT. The dim
  does NOT know the buyer's car dependence — the reason says so and
  points at the EMTA leg. Window 600 m.
* P4-041 scores ONLY corridor preservation (inside a registered
  vaatekoridor -> 65 capped): the corridor constrains future
  blockage, it is NOT a view guarantee — the reason says
  "sailimise tugi, mitte vaate garantii" and points at the
  EHR/AER piilukas class for the actual glimpse. No "clear"
  score: absence of a corridor is not a view verdict. Window 300 m.
* P4-050 prefers the glut ratio (permits/completions, quarterly
  ehitusstatistika over the same linnaosa row) with the same bands
  as the TPR leg (<=0.5 -> 80, <=1 -> 60, <=2 -> 40, else 20) and
  the same pipeline-only fallback flagged "ainult torustik";
  completions == 0 with permits > 0 is pure pipeline (20), 0/0 is
  NULL (andmelunk). Window 1500 m (linnaosa grain — coarser than
  the TPR 1000 m micro-area, said in the reason). The EHR P4-050
  NULL ("needs a quarterly micro-area table") is the gap both the
  TPR areas table and this stats table fill on their legs; falling
  prices stay in the tehingud leg.
* P4-061 scores ONLY the aarealade-kava fringe checklist
  (shop/pharmacy/ATM present + bus_cuts flag): 3 -> 80, 2 -> 60,
  1 -> 40, 0 -> 25, bus_cuts -10 (floor 20). The GTFS prev-vs-cur
  cut diff stays in dims_p4_peatus.dim_bus_cut and the TLT NULL
  slice stays put. Window 2000 m (fringe-settlement grain).

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

#: Human plan pages (verified 2026-09-13: CMS HTML, district-subsite
#: routing, no bulk links — see module docstring).
CITYPLANS_INDEX_URL = "https://www.tallinn.ee/et/kristiine/uldplaneering"

#: Open bulk endpoint: NONE found 2026-09-13 (dated negative, see module
#: docstring). Stays None until the reopening checklist in
#: docs/p4_cityplans.md names a verified bulk URL; while None, fetch
#: performs no requests.
CITYPLANS_BULK_URL: Optional[str] = None

#: Max one download per 30 d per cache dir (parameters4.md P4-014:
#: monthly, expiry-dated; all seven coverage legs ride the same
#: monthly ticket). Stated TTL.
CITYPLANS_TTL_S = 30 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "cityplans-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
CITYPLANS_UA = "home-finder cityplans openness-check (max 1 req/30d, no scrape)"

#: Tram-work phases counted by the P4-014 calendar dim (same vocabulary
#: as the RB slice — one param, one phase language).
PHASE_ACTIVE = "ehituses"
PHASE_PLANNED = "planeerimisel"
PHASE_DONE = "valmis"


def fetch_cityplans_snapshot(cache_dir: str,
                             ttl_s: int = CITYPLANS_TTL_S,
                             bulk_url: Optional[str] = CITYPLANS_BULK_URL,
                             ) -> Optional[str]:
    """Polite cityplans snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with CITYPLANS_UA and a
    30 s timeout; the body is stored only on HTTP 200 with JSON content,
    else None is returned and nothing is cached (transport errors are
    never data). No retries — HTTP 429/errors are a stop signal. Scorers
    never call this; tests cover the cache-hit and no-endpoint paths
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
    if bulk_url is None:
        return None
    try:
        req = urllib.request.Request(bulk_url,
                                     headers={"User-Agent": CITYPLANS_UA})
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

_TABLES = ("tramworks", "arengualad", "investeeringud", "prognoos",
           "poliitika", "vaatekoridorid", "ehitusstat", "aarealad")


def parse_cityplans_snapshot(path: str) -> Optional[dict]:
    """Read a cached cityplans snapshot file. Offline, stdlib.

    Returns the eight tables with malformed rows skipped, or None when
    the file is missing/unparseable (unknown, never an empty snapshot
    — scorers must not read "no file" as "no pressure").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    out: Dict[str, list] = {}
    for table in _TABLES:
        rows = raw.get(table)
        out[table] = ([r for r in rows if isinstance(r, dict)]
                      if isinstance(rows, list) else [])
    return out


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


def _num(v) -> Optional[float]:
    """Finite non-bool number or None (never faked from garbage)."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def tramworks_to_pois(works: List[dict]) -> List[dict]:
    """Tram-work rows -> scorer POIs. Rows without coords stay out
    (never faked); expiry strings are normalised to ISO or None."""
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
            "kind": "cityplan_tram_p4",
            "lat": lat, "lon": lon,
            "work_id": str(row.get("work_id") or "tundmatu"),
            "title": str(row.get("title") or "tundmatu"),
            "phase": (str(phase).strip().lower()
                      if phase is not None else None),
            "valid_from": _iso_date(row.get("valid_from")),
            "valid_until": _iso_date(row.get("valid_until")),
        })
    return pois


def arengualad_to_pois(rows: List[dict]) -> List[dict]:
    """Arenguala/teemaplaneering rows -> scorer POIs."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        kind = row.get("kind")
        pois.append({
            "kind": "cityplan_arenguala_p4",
            "lat": lat, "lon": lon,
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "zkind": (str(kind).strip().lower()
                      if kind is not None else None),
        })
    return pois


def investments_to_pois(rows: List[dict]) -> List[dict]:
    """Arengukava investment rows -> scorer POIs (incomplete figures
    stay None — never zero-filled)."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        trend = row.get("trend")
        pois.append({
            "kind": "cityplan_invest_p4",
            "lat": lat, "lon": lon,
            "area_code": str(row.get("area_code") or "tundmatu"),
            "invest_m_eur": _num(row.get("invest_m_eur")),
            "trend": (str(trend).strip().lower()
                      if trend is not None else None),
        })
    return pois


def forecasts_to_pois(rows: List[dict]) -> List[dict]:
    """Rahvastikuprognoos rows -> scorer POIs."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        plan = row.get("school_plan")
        pois.append({
            "kind": "cityplan_prognoos_p4",
            "lat": lat, "lon": lon,
            "area_code": str(row.get("area_code") or "tundmatu"),
            "pop_change_pct": _num(row.get("pop_change_pct")),
            "school_plan": (str(plan).strip().lower()
                            if plan is not None else None),
        })
    return pois


def policy_to_pois(rows: List[dict]) -> List[dict]:
    """Planned-zone rows -> scorer POIs."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        kind = row.get("kind")
        pois.append({
            "kind": "cityplan_poliitika_p4",
            "lat": lat, "lon": lon,
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "zkind": (str(kind).strip().lower()
                      if kind is not None else None),
        })
    return pois


def corridors_to_pois(rows: List[dict]) -> List[dict]:
    """Vaatekoridor rows -> scorer POIs."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        pois.append({
            "kind": "cityplan_vaade_p4",
            "lat": lat, "lon": lon,
            "corr_id": str(row.get("corr_id") or "tundmatu"),
        })
    return pois


def buildstats_to_pois(rows: List[dict]) -> List[dict]:
    """Ehitusstatistika rows -> scorer POIs (missing counts stay None —
    a missing count is a gap, never zero)."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        pois.append({
            "kind": "cityplan_ehitusstat_p4",
            "lat": lat, "lon": lon,
            "area_code": str(row.get("area_code") or "tundmatu"),
            "permits_q": _num(row.get("permits_q")),
            "completions_q": _num(row.get("completions_q")),
        })
    return pois


def fringe_to_pois(rows: List[dict]) -> List[dict]:
    """Aarealade-kava fringe checklist rows -> scorer POIs."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        pois.append({
            "kind": "cityplan_aareala_p4",
            "lat": lat, "lon": lon,
            "settlement": str(row.get("settlement") or "tundmatu"),
            "shop": bool(row.get("shop")),
            "pharmacy": bool(row.get("pharmacy")),
            "atm": bool(row.get("atm")),
            "bus_cuts": bool(row.get("bus_cuts")),
        })
    return pois


_READERS = {
    "tramworks": tramworks_to_pois,
    "arengualad": arengualad_to_pois,
    "investeeringud": investments_to_pois,
    "prognoos": forecasts_to_pois,
    "poliitika": policy_to_pois,
    "vaatekoridorid": corridors_to_pois,
    "ehitusstat": buildstats_to_pois,
    "aarealad": fringe_to_pois,
}


def snapshot_to_pois(snapshot: Optional[dict]) -> List[dict]:
    """Parsed snapshot (or None) -> scorer POIs for all eight dims. Pure."""
    if not isinstance(snapshot, dict):
        return []
    pois: List[dict] = []
    for table, reader in _READERS.items():
        rows = snapshot.get(table)
        if isinstance(rows, list):
            pois.extend(reader(rows))
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

#: P4-014 tram-nuisance window (parameters4.md: calendar dim; 800 m
#: nuisance footprint matches the RB slice — one param, one footprint).
NUISANCE_WINDOW_M = 800.0
#: P4-006 arenguala buffer (parameters4.md: 500 m).
ARENGUALA_WINDOW_M = 500.0
#: Arenguala near band: planning pressure on the buyer's street.
NEAR_ARENGUALA_M = 200.0
#: P4-019/P4-025/P4-050 linnaosa-grain window (coarser than parcel joins).
LINNAOSA_WINDOW_M = 1500.0
#: P4-037 planned-zone window (commute-relevant surroundings).
POLICY_WINDOW_M = 600.0
#: P4-041 vaatekoridor window (corridor adjacency, not a view radius).
VAATE_WINDOW_M = 300.0
#: P4-061 fringe-settlement window (settlement grain, not a stop radius).
FRINGE_WINDOW_M = 2000.0

#: Tram phase -> score (high = calm/good for the buyer today). Same
#: bands as the RB slice by design; MUST be recalibrated from a real
#: timetable on reopen.
PHASE_SCORES = {
    PHASE_ACTIVE: 35,
    PHASE_PLANNED: 55,
    PHASE_DONE: 75,
}
#: Arenguala distance -> pressure score (high = calm). Softer than the
#: RB corridor leg: a development area is planning pressure, not a
#: reserved corridor at the doorstep.
ARENGUALA_NEAR_SCORE = 50
ARENGUALA_FAR_SCORE = 65
#: Measured clear: no arenguala in 500 m while the snapshot holds
#: arengualas elsewhere.
ARENGUALA_CLEAR_SCORE = 85
#: Arengukava investment trend -> fiscal-health score (high = healthy).
TREND_SCORES = {
    "kasv": 75,
    "stabiilne": 60,
    "kahaneb": 40,
}
#: Planned-zone kind -> exposure score (high = less exposed).
POLICY_SCORES = {
    "ummikumaks_arutelu": 45,
    "autovaba": 50,
    "tasuline_parkimine": 60,
}
#: Vaatekoridor preservation (capped: corridor support, never a view).
VAATE_SCORE = 65
#: Ehitusstatistika glut ratio (permits/completions) -> score.
GLUT_BANDS = ((0.5, 80), (1.0, 60), (2.0, 40))
GLUT_HIGH_SCORE = 20
#: Pipeline-only fallback (completions missing): permits/q -> score.
PIPE_ONLY_BANDS = ((0, 85), (50, 70), (200, 45))
PIPE_ONLY_HIGH_SCORE = 25
#: Pure pipeline (permits > 0, completions == 0).
PURE_PIPE_SCORE = 20
#: Fringe checklist: present services (shop/pharmacy/ATM) -> score.
FRINGE_BANDS = {3: 80, 2: 60, 1: 40, 0: 25}
FRINGE_CUT_PENALTY = 10
FRINGE_FLOOR = 20
#: Prognoos school-plan modulation.
SCHOOL_CLOSE_PENALTY = 10
SCHOOL_OPEN_BONUS = 5
PROGNOOS_CAP = 80
PROGNOOS_FLOOR = 20


# ---------------------------------------------------------------------------
# P4-014: tram-extension construction phase, calendar dim (demo).
# ---------------------------------------------------------------------------

def dim_tramfaas_cityplans(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]],
                           today: Union[None, str, datetime.date] = None,
                           ) -> Score:
    """P4-014: nearest live tram-timetable phase within 800 m (high = calm).

    Calendar dim with expiry: only tram rows whose timetable covers the
    valuation date count (valid_from <= today <= valid_until; a row
    without a parseable valid_until has unknown expiry and is
    excluded). Expired/unknown rows never score — a stale timetable is
    unknown, not good. Beyond-window is unknown, never calm. Only the
    tram slice of the param: Ulemiste RB works stay in dim_ehitusfaas_rb.
    """
    if not origin or pois is None:
        return None, ("Trammitööde faasi info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat trammigraafikut pole, "
                      "allikad on veebiuudised ja dokumendid)")
    day = _as_today(today)
    if not _has_kind(pois, "cityplan_tram_p4"):
        return None, ("Trammitööde faasi info puudub (EI OLE trammi-"
                      "hetktõmmist hetkel: tühi tõmmis ei ole rahulik "
                      "otsus)")
    hits = _near(origin, pois, "cityplan_tram_p4", NUISANCE_WINDOW_M)
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
            return None, ("Trammitööde faasi info puudub (EI OLE kehtivat "
                          "trammigraafikut %s seisuga: %d lähedast tööd on "
                          "aegunud/tundmatu kehtivusega — vana graafik ei "
                          "ole rahulik otsus)" % (day.isoformat(), stale))
        return None, ("Trammitööde faasi info puudub (EI OLE trammitööd "
                      "800 m aknas %s seisuga — akna taga on teadmata, "
                      "mitte rahulik)" % day.isoformat())
    d0, p0 = live[0]
    phase = p0.get("phase")
    score = PHASE_SCORES.get(phase) if isinstance(phase, str) else None
    if score is None:
        return None, ("Trammitööde faasi info puudub (EI OLE kinnitatud "
                      "faasi: töö %s %s on märgitud '%s' — kontrollimata "
                      "silt ei ole faas)" % (p0.get("work_id"), _fmt_m(d0),
                                             phase))
    end_txt = p0.get("valid_until").isoformat()
    if phase == PHASE_ACTIVE:
        why = ("müra/tolm täna, trammiväärtus hiljem")
    elif phase == PHASE_PLANNED:
        why = ("tulevased trammiteed, mõju ebaselge")
    else:
        why = ("tramm valmis, ühendus olemas")
    return score, ("Trammitööde faas (hinnang, graafik kehtib kuni %s): "
                   "töö %s '%s' %s, faas '%s' (%s) → skoor %d"
                   % (end_txt, p0.get("work_id"), p0.get("title"),
                      _fmt_m(d0), phase, why, score))


# ---------------------------------------------------------------------------
# P4-006: uldplaneering arenguala leg, 500 m (coverage).
# ---------------------------------------------------------------------------

def dim_arenguala_cityplans(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-006: nearest uldplaneering arenguala/teemaplaneering in 500 m.

    Only the strategic-plan leg of the param: near (<=200 m) scores 50,
    inside 500 m scores 65, and a measured clear (no arenguala in 500 m
    while the snapshot holds arengualas elsewhere) scores 85. No
    arenguala link is unknown (NULL), never clear. Sibling
    kataster/TPR/RB legs untouched.
    """
    if not origin or pois is None:
        return None, ("Arenguala info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat uldplaneeringu kihti "
                      "pole, allikad on veebikaart ja dokumendid)")
    if not _has_kind(pois, "cityplan_arenguala_p4"):
        return None, ("Arenguala info puudub (EI OLE arenguala-hetktõmmist "
                      "hetkel: tühi tõmmis ei ole puhas otsus)")
    hits = _near(origin, pois, "cityplan_arenguala_p4", ARENGUALA_WINDOW_M)
    if not hits:
        return ARENGUALA_CLEAR_SCORE, (
            "Uldplaneeringu arenguala (hinnang): 500 m raadiuses "
            "arenguala/teemaplaneeringut pole (tõmmises on alasid mujal) "
            "→ skoor %d" % ARENGUALA_CLEAR_SCORE)
    d0, z0 = hits[0]
    if d0 <= NEAR_ARENGUALA_M:
        return ARENGUALA_NEAR_SCORE, (
            "Uldplaneeringu arenguala (hinnang): %s lähedal (%s) — "
            "planeerimissurve tänaval → skoor %d"
            % (z0.get("zone_id"), _fmt_m(d0), ARENGUALA_NEAR_SCORE))
    return ARENGUALA_FAR_SCORE, (
        "Uldplaneeringu arenguala (hinnang): lähim %s %s (500 m aknas) — "
        "arengusurve → skoor %d"
        % (z0.get("zone_id"), _fmt_m(d0), ARENGUALA_FAR_SCORE))


# ---------------------------------------------------------------------------
# P4-019: arengukava investment-table leg (coverage).
# ---------------------------------------------------------------------------

def dim_investeering_cityplans(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-019: arengukava investment trend for the linnaosa (high = healthy).

    Only the investment-table leg of the param: the TREND scores
    (kasv -> 75, stabiilne -> 60, kahaneb -> 40), the invest figure is
    printed as context. Incomplete rows (invest None, trend unknown)
    stay NULL: a half-filled budget row is not a fiscal verdict. The
    maamaks rate level + trend stays in the EMTA slice.
    """
    if not origin or pois is None:
        return None, ("Investeeringute info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat arengukava tabelit pole, "
                      "allikas on veebidokument)")
    if not _has_kind(pois, "cityplan_invest_p4"):
        return None, ("Investeeringute info puudub (EI OLE investeeringu-"
                      "hetktõmmist hetkel: tühi tõmmis ei ole terve otsus)")
    hits = _near(origin, pois, "cityplan_invest_p4", LINNAOSA_WINDOW_M)
    if not hits:
        return None, ("Investeeringute info puudub (EI OLE arengukava rida "
                      "1500 m aknas — akna taga on teadmata, mitte terve)")
    d0, r0 = hits[0]
    trend = r0.get("trend")
    invest = r0.get("invest_m_eur")
    score = TREND_SCORES.get(trend) if isinstance(trend, str) else None
    if score is None or invest is None:
        return None, ("Investeeringute info puudub (EI OLE tervet arengukava "
                      "rida %s kohta: investeering=%s, trend=%s — poolik "
                      "eelarverida ei ole eelarveotsus)"
                      % (r0.get("area_code"), invest, trend))
    return score, ("Arengukava investeeringud (hinnang): %s %.1f mln €, "
                   "trend '%s' %s (maksumäär EMTA-liites) → skoor %d"
                   % (r0.get("area_code"), invest, trend, _fmt_m(d0),
                      score))


# ---------------------------------------------------------------------------
# P4-025: rahvastikuprognoos leg (coverage).
# ---------------------------------------------------------------------------

def _prognoos_base(pop: float) -> int:
    if pop >= 3.0:
        return 75
    if pop >= 0.0:
        return 65
    if pop >= -3.0:
        return 50
    return 35


def dim_prognoos_cityplans(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-025: rahvastikuprognoos + school plan for the linnaosa.

    Only the forecast leg of the param: pop_change_pct bands (>=+3 ->
    75, >=0 -> 65, >=-3 -> 50, else 35), modulated by the school
    open/close plan (suletakse -10, avatakse +5, capped 20..80). The
    REL2021 1 km grid stays in dims_p4_rel2021, the school-feed NULL
    stays in dims_p4_haridus.
    """
    if not origin or pois is None:
        return None, ("Prognoosi info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat rahvastikuprognoosi pole, "
                      "allikas on veebidokument)")
    if not _has_kind(pois, "cityplan_prognoos_p4"):
        return None, ("Prognoosi info puudub (EI OLE prognoosi-hetktõmmist "
                      "hetkel: tühi tõmmis ei ole likviidsusotsus)")
    hits = _near(origin, pois, "cityplan_prognoos_p4", LINNAOSA_WINDOW_M)
    if not hits:
        return None, ("Prognoosi info puudub (EI OLE prognoosirida 1500 m "
                      "aknas — akna taga on teadmata, mitte likviidne)")
    d0, r0 = hits[0]
    pop = r0.get("pop_change_pct")
    if pop is None:
        return None, ("Prognoosi info puudub (EI OLE rahvaarvu %s kohta: "
                      "prognoosirida ilma muutuseta ei ole likviidsusotsus)"
                      % r0.get("area_code"))
    base = _prognoos_base(pop)
    plan = r0.get("school_plan")
    adj = 0
    plan_txt = "koolivõrk stabiilne"
    if plan == "suletakse":
        adj = -SCHOOL_CLOSE_PENALTY
        plan_txt = "kooli sulgemine kavas (-%d)" % SCHOOL_CLOSE_PENALTY
    elif plan == "avatakse":
        adj = SCHOOL_OPEN_BONUS
        plan_txt = "kooli avamine kavas (+%d)" % SCHOOL_OPEN_BONUS
    score = max(PROGNOOS_FLOOR, min(PROGNOOS_CAP, base + adj))
    return score, ("Rahvastikuprognoos (hinnang): %s %+.1f%%, %s %s "
                   "(REL2021-ruudustik REL2021-liites) → skoor %d"
                   % (r0.get("area_code"), pop, plan_txt, _fmt_m(d0),
                      score))


# ---------------------------------------------------------------------------
# P4-037: planned-zone leg (coverage).
# ---------------------------------------------------------------------------

def dim_poliitika_kava_cityplans(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """P4-037: planned car-policy zone exposure within 600 m.

    Only the planned-zone leg of the param (ummikumaks_arutelu -> 45,
    autovaba -> 50, tasuline_parkimine -> 60). The dim does NOT know
    the buyer's car dependence — the reason says so and points at the
    EMTA automaks leg. An "arutelu" is a discussion, never a decision.
    Sibling EMTA/trans/peatus/TLT legs untouched.
    """
    if not origin or pois is None:
        return None, ("Poliitikakava info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat laienemisplaanide kihti "
                      "pole, allikad on veebidokumendid)")
    if not _has_kind(pois, "cityplan_poliitika_p4"):
        return None, ("Poliitikakava info puudub (EI OLE poliitika-"
                      "hetktõmmist hetkel: tühi tõmmis ei ole vähene "
                      "otsus)")
    hits = _near(origin, pois, "cityplan_poliitika_p4", POLICY_WINDOW_M)
    if not hits:
        return None, ("Poliitikakava info puudub (EI OLE planeeritud tsooni "
                      "600 m aknas — akna taga on teadmata, mitte vähene)")
    d0, z0 = hits[0]
    zkind = z0.get("zkind")
    score = POLICY_SCORES.get(zkind) if isinstance(zkind, str) else None
    if score is None:
        return None, ("Poliitikakava info puudub (EI OLE kinnitatud tsooni: "
                      "%s on märgitud '%s' — kontrollimata silt ei ole "
                      "tsoon)" % (z0.get("zone_id"), zkind))
    extra = ""
    if zkind == "ummikumaks_arutelu":
        extra = " (arutelu, mitte otsus)"
    return score, ("Planeeritud autopoliitika tsoon (hinnang): %s '%s' %s%s "
                   "— autosõltuvuse kontroll EMTA-liites → skoor %d"
                   % (z0.get("zone_id"), zkind, _fmt_m(d0), extra, score))


# ---------------------------------------------------------------------------
# P4-041: vaatekoridor-preservation leg (coverage).
# ---------------------------------------------------------------------------

def dim_vaatekoridor_cityplans(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-041: registered vaatekoridor adjacency within 300 m.

    Only the corridor-preservation leg of the param: inside a corridor
    scores 65 capped — the corridor constrains future blockage, it is
    NOT a view guarantee. No "clear" score: absence of a corridor is
    not a view verdict. The piilukas class stays in the EHR/AER legs.
    """
    if not origin or pois is None:
        return None, ("Vaatekoridori info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat vaatekohtade registrit "
                      "pole, allikas on uldplaneeringu dokument)")
    if not _has_kind(pois, "cityplan_vaade_p4"):
        return None, ("Vaatekoridori info puudub (EI OLE koridori-"
                      "hetktõmmist hetkel: tühi tõmmis ei ole vaateotsus)")
    hits = _near(origin, pois, "cityplan_vaade_p4", VAATE_WINDOW_M)
    if not hits:
        return None, ("Vaatekoridori info puudub (EI OLE kaitstud koridori "
                      "300 m aknas — koridori puudumine ei ole vaateotsus, "
                      "piilukas-klass EHR/AER-liites)")
    d0, c0 = hits[0]
    return VAATE_SCORE, ("Kaitstud vaatekoridor (hinnang, ülempiir %d): %s "
                         "%s — säilimise tugi, mitte vaate garantii; "
                         "piilukas-klass EHR/AER-liites → skoor %d"
                         % (VAATE_SCORE, c0.get("corr_id"), _fmt_m(d0),
                            VAATE_SCORE))


# ---------------------------------------------------------------------------
# P4-050: ehitusstatistika leg, quarterly linnaosa counts (coverage).
# ---------------------------------------------------------------------------

def dim_ehitusstat_cityplans(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-050: permit glut vs completions from quarterly linnaosa stats.

    Only the ehitusstatistika leg of the param: the glut ratio
    (permits/completions over the same linnaosa row) scores <=0.5 ->
    80, <=1 -> 60, <=2 -> 40, else 20; a missing completions count
    falls back to a pipeline-only band flagged "ainult torustik";
    permits > 0 with completions == 0 is pure pipeline (20); 0/0 is
    NULL (andmelunk). Window 1500 m — linnaosa grain, coarser than the
    TPR 1000 m micro-area. Falling prices stay in the tehingud leg.
    """
    if not origin or pois is None:
        return None, ("Ehitusstatistika info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat kvartalistatistikat pole, "
                      "allikas on veebidokument)")
    if not _has_kind(pois, "cityplan_ehitusstat_p4"):
        return None, ("Ehitusstatistika info puudub (EI OLE statistika-"
                      "hetktõmmist hetkel: tühi tõmmis ei ole pakkumisotsus)")
    hits = _near(origin, pois, "cityplan_ehitusstat_p4", LINNAOSA_WINDOW_M)
    if not hits:
        return None, ("Ehitusstatistika info puudub (EI OLE statistika-"
                      "rida 1500 m aknas — akna taga on teadmata, mitte "
                      "tasakaal)")
    d0, r0 = hits[0]
    pipe = r0.get("permits_q")
    done = r0.get("completions_q")
    area = r0.get("area_code")
    if pipe is None and done is None:
        return None, ("Ehitusstatistika info puudub (EI OLE kumbagi arvu "
                      "%s kohta: 0/0 on andmelunk, mitte tasakaal)" % area)
    if done is None:
        score = PIPE_ONLY_HIGH_SCORE
        for cap, val in PIPE_ONLY_BANDS:
            if pipe <= cap:
                score = val
                break
        return score, ("Ehitusstatistika pakkumissurve (hinnang, ainult "
                       "torustik): %s lube %s, valmimisi EI OLE "
                       "(linnaosa-täpsus, TPR-mikroala 1000 m asemel "
                       "1500 m) → skoor %d" % (area, pipe, score))
    if done == 0:
        if pipe and pipe > 0:
            return PURE_PIPE_SCORE, (
                "Ehitusstatistika pakkumissurve (hinnang): %s lube %s, "
                "valmimisi 0 — puhas torustik → skoor %d"
                % (area, pipe, PURE_PIPE_SCORE))
        return None, ("Ehitusstatistika info puudub (EI OLE kumbagi arvu "
                      "%s kohta: 0/0 on andmelunk, mitte tasakaal)" % area)
    ratio = pipe / done if pipe is not None else None
    if ratio is None:
        return None, ("Ehitusstatistika info puudub (EI OLE lubade arvu "
                      "%s kohta: ilma torustikuta ei ole suhet)" % area)
    score = GLUT_HIGH_SCORE
    for cap, val in GLUT_BANDS:
        if ratio <= cap:
            score = val
            break
    return score, ("Ehitusstatistika pakkumissurve (hinnang): %s lube %s / "
                   "valmimisi %s = %.2f %s (linnaosa-täpsus) → skoor %d"
                   % (area, pipe, done, ratio, _fmt_m(d0), score))


# ---------------------------------------------------------------------------
# P4-061: aarealade-kava fringe checklist leg (coverage).
# ---------------------------------------------------------------------------

def dim_aareala_teenus_cityplans(origin: Optional[Tuple[float, float]],
                                 pois: Optional[List[dict]]) -> Score:
    """P4-061: fringe-settlement service checklist within 2000 m.

    Only the aarealade-kava leg of the param: present services
    (shop/pharmacy/ATM) score 3 -> 80, 2 -> 60, 1 -> 40, 0 -> 25, and
    a bus_cuts flag subtracts 10 (floor 20). The GTFS prev-vs-cur cut
    diff stays in dims_p4_peatus.dim_bus_cut.
    """
    if not origin or pois is None:
        return None, ("Äärealateenuste info puudub (EI OLE cityplansi "
                      "hetktõmmist: masinloetavat aarealade kava pole, "
                      "allikas on veebidokument)")
    if not _has_kind(pois, "cityplan_aareala_p4"):
        return None, ("Äärealateenuste info puudub (EI OLE aareala-"
                      "hetktõmmist hetkel: tühi tõmmis ei ole "
                      "likviidsusotsus)")
    hits = _near(origin, pois, "cityplan_aareala_p4", FRINGE_WINDOW_M)
    if not hits:
        return None, ("Äärealateenuste info puudub (EI OLE aareala-"
                      "asulat 2000 m aknas — akna taga on teadmata, mitte "
                      "elujõuline)")
    d0, s0 = hits[0]
    present = [k for k in ("shop", "pharmacy", "atm") if s0.get(k)]
    missing = [k for k in ("shop", "pharmacy", "atm") if not s0.get(k)]
    score = FRINGE_BANDS[len(present)]
    cut_txt = "bussikärpeid EI OLE"
    if s0.get("bus_cuts"):
        score = max(FRINGE_FLOOR, score - FRINGE_CUT_PENALTY)
        cut_txt = "bussikärped (-%d)" % FRINGE_CUT_PENALTY
    miss_txt = ("kõik olemas" if not missing
                else "puudu: %s" % ", ".join(missing))
    return score, ("Äärealade teenused (hinnang): %s %d/3 (%s), %s %s "
                   "(GTFS-kärped peatus-liites) → skoor %d"
                   % (s0.get("settlement"), len(present), miss_txt,
                      cut_txt, _fmt_m(d0), score))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_CITYPLANS_DIMS = (
    ("tramfaas_cityplans", "P4-014", dim_tramfaas_cityplans),
    ("arenguala_cityplans", "P4-006", dim_arenguala_cityplans),
    ("investeering_cityplans", "P4-019", dim_investeering_cityplans),
    ("prognoos_cityplans", "P4-025", dim_prognoos_cityplans),
    ("poliitika_kava_cityplans", "P4-037", dim_poliitika_kava_cityplans),
    ("vaatekoridor_cityplans", "P4-041", dim_vaatekoridor_cityplans),
    ("ehitusstat_cityplans", "P4-050", dim_ehitusstat_cityplans),
    ("aareala_teenus_cityplans", "P4-061", dim_aareala_teenus_cityplans),
)


def score_p4_cityplans(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]],
                       today: Union[None, str, datetime.date] = None,
                       ) -> Dict[str, Optional[int]]:
    """P4 cityplans dims for one listing (entry point for the follow-up)."""
    out: Dict[str, Optional[int]] = {}
    for key, _, fn in P4_CITYPLANS_DIMS:
        if key == "tramfaas_cityplans":
            out[key] = dim_tramfaas_cityplans(origin, pois, today)[0]
        else:
            out[key] = fn(origin, pois)[0]
    return out
