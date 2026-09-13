"""P4 KAUR dims (issues #285 demo + #359 coverage): Keskkonnaagentuur.

Params (this module only — sibling legs untouched):
* P4-015 Insurability: flood zones (demo, batch 1 — KAUR source (1))
* P4-016 Engineering geology, groundwater-protection leg (batch 2)
* P4-023 Airport + military noise, Ämari-rattle cross-check leg (batch 2)
* P4-024 Country-health nuisances, pollen-monitoring leg (batch 2)
* P4-031 Backyard weather, Harku-baseline + station-density leg (batch 3)
* P4-042 Smell/dawn-chorus, smoke-episode cross-check leg (batch 4)
* P4-046 Dread removal, draining-ground-floor leg (batch 4)
* P4-053 Odour roses, sector + calendar leg (batch 5)
* P4-056 Enclosed-courtyard trap, fume-hold validation leg (batch 5)
* P4-058 Falling-ice + cliff retreat, storm-surge erosion leg (batch 5)
* P4-059 Wood-burning restrictions, enforcement-recency leg (batch 5)

OPENNESS VERDICT (checked 2026-09-13, mixed — dated negative on the
zone bulk keeps per #285 acceptance; the open API host below stays
the re-pull anchor). Polite evidence, 9 tiny requests total (custom
UA, short timeouts, paced >=4 s, raw pages cached at /tmp/hf-p4-kaur/
for the PR record, never committed; redirects not spidered, no
scraping, no auth attempts):
* HEAD https://keskkonnaagentuur.ee/ -> HTTP 200 (Drupal; CSP frame-src
  already points at keskkonnaportaal.ee and xgis.maaamet.ee — the data
  lives in the portal, not the agency front page).
* GET https://keskkonnaagentuur.ee/ (113 152 B, "Avaleht |
  Keskkonnaagentuur") — links to the open-data service page
  /teenused-ja-aruandlus/teenused/keskkonnainfo-ja-avaandmed and to
  https://keskkonnaportaal.ee/; zero WFS/API/CSV hrefs on the front
  page itself.
* HEAD https://www.ilmateenistus.ee/ -> HTTP 200 (Cloudflare).
* GET .../keskkonnainfo-ja-avaandmed (95 074 B) — an e-service
  catalogue (Keskkonnaportaal, KESE, EELIS infoleht, ILM+ app): human
  portals, no bulk endpoint on the page.
* HEAD https://keskkonnaportaal.ee/ -> HTTP 200 (server KEMIT).
* GET https://keskkonnaportaal.ee/et/avaandmed (163 537 B, "Avaandmed |
  Keskkonnaportaal") — documents: EELIS + Geoserver WMS/WFS services,
  the KAIA file store (met seire, warnings, radar, model forecasts),
  the "Keskkonna ja ilma valdkonna andmeteenused" API environment
  (climate/hydro seire, KOTKAS, KESE, EELIS; CSV downloader UI), and a
  dataset catalogue. Documented services, not yet a verified URL.
* GET .../keskkonna-ja-ilma-valdkonna-andmeteenused (160 993 B) —
  links the live PostgREST host below with ready-made example queries
  (f_kliima_paev / f_kliima_tund / f_hydroseire / f_keskkonnaseire).
* GET keskkonnaandmed.envir.ee/f_kliima_paev?...&limit=1 -> HTTP 200
  (server postgrest/12.0.1, 261 B): a real row back, anonymously —
  Tallinn-Harku (AJHARK01) daily air pressure 2023-12-01. OPEN as the
  re-pull anchor for the station/observation slices.
* HEAD https://www.efas.eu/ -> HTTP 301 (not followed, polite stop) —
  the #239 EFAS fallback stays unverified here.
Dated negative keeps the zone-bulk verdict: no anonymous per-parcel
bulk URL for the flood-zone polygons, the groundwater-protection
zones, or the air/pollen station registry was verified 2026-09-13,
so KAUR_BULK_URL stays None and fetch performs no requests. Flood
WFS verification itself belongs to overturn #239 (G8 track) — this
module must not pre-empt it; the P4-015 demo proves the zone-join
shape on fixtures only. Reopening checklist lives in docs/p4_kaur.md.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its joined components (zone kind + name, or
station name + flag, or sector days); every NULL reason says "EI OLE"
and names the missing input. Transport errors are never cached as
data (fetch stores a body only on HTTP 200 with JSON content, else
returns None). A joined cell/station in the window scores — while a
missing join (no snapshot, no row in the window, unknown label) stays
NULL: absence of data is unknown, never good. Distances are
bird-flight, never routed. Scores never hit 0 or 100: a single KAUR
slice never prices insurance, proves calm, or clears a parcel — the
caps in the band tables say so explicitly.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_kaur_snapshot(cache_dir): polite pull, max 1 download / 365 d
  per cache dir (KAUR_TTL_S; parameters4.md P4-015/P4-016 cadence is
  annual bulk — flood and groundwater zones move on planning cycles,
  not weekly; the climate-observation rows ride the same annual
  ticket as reference rows, with KAUR publications triggering an
  out-of-band re-pull). Cache hit within TTL performs NO request.
  While no per-parcel bulk endpoint exists (KAUR_BULK_URL None) it
  performs no request at all and returns the fresh-cache path or
  None. Single GET with an identifying UA once a bulk URL is known,
  no retries (HTTP 429 is a stop signal, 7.4).
* parse_kaur_snapshot / zones_to_pois / stations_to_pois /
  snapshot_to_pois: pure offline readers over the cached JSON
  snapshot (schema documented below). Network lives ONLY in
  fetch_kaur_snapshot; scorers and tests never touch it.
* One snapshot, two tables, no new plumbing for coverage: "zones"
  feeds P4-015/P4-016/P4-046/P4-058, "stations" feeds P4-023/P4-024/
  P4-031/P4-042/P4-056/P4-059 (this is why demo + coverage pair in
  ONE PR — #359 expects no new plumbing). P4-053/P4-056/P4-059 also
  read caller-supplied context cells (sector / courtyard / burn-rule
  rows owned by the wind-rose, LiDAR, and restriction-register legs);
  fixtures hand-build them exactly as a future hook would.

Snapshot schema (what a future adapter would store; fixtures match):
  {"zones": [{"zone_id": str, "name": str, "zone": str, "lat": float,
              "lon": float}],
   "stations": [{"station_id": str, "name": str, "s_kind": str,
                 "lat": float, "lon": float, "level": str|None,
                 "episode": bool|None, "rattle": bool|None}]}
zone in {t10, t100, t1000, surge, gw_strict, gw_mild}; s_kind in
{air, pollen, met, wind}; level in {korge, keskmine, madal} (pollen
season level; other kinds leave it None). episode = recent
smoke/pollution episode at the station; rattle = AMari-rattle flag.
Rows with unknown zone/s_kind tokens or without finite coords are
skipped, never faked; a missing/unparseable file parses to None
(unknown), never to an empty snapshot. episode/rattle values that
are not real booleans read as None (unknown): an unknown episode is
neither an episode nor a quiet proof.

Context cells (caller-supplied, NOT from the snapshot — fixture-built
in tests, hook-built in production):
  {"kind": "kaur_ctx_p4", "ctx": "sector", "name": str,
   "emitter": str, "downwind_days": int|float, "lat": float,
   "lon": float} — odour sector footprint (P4-053).
  {"kind": "kaur_ctx_p4", "ctx": "court", "name": str,
   "enclosure": "korge"|"keskmine", "lat": float, "lon": float} —
   enclosed-courtyard morphology cell (P4-056; the LiDAR enclosure
   index owns the morphology precision).
  {"kind": "kaur_ctx_p4", "ctx": "burn_rule", "name": str,
   "rule": "keelatud"|"piiratud", "lat": float, "lon": float} —
   wood-burning restriction rule cell (P4-059; the restriction
   register owns the rule itself, this module scores enforcement).

Style mirrors services/scoring/dims_p4_rb.py (#281/#355, the honest-
plumbing precedent): pure scorers (origin, pois) -> (Optional[int
0..100], Estonian reason), local helpers (no livability import —
importing it here would turn the future central hook into a cycle,
same precedent as PRs #100/#106/#115). Unlike peatus there is NO
staged Overpass fragment and no tag mapping: OSM has no honest tag
for KAUR flood zones, pollen levels, or odour sectors, so there is
nothing for the live path to fetch (same rationale as the group20a
no-map batches).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because the #359 body states it
  extends the demoed ingestion with "no new plumbing expected": the
  ten coverage params ride the same two snapshot tables (zones for
  P4-016/P4-046/P4-058, stations for P4-023/P4-024/P4-031/P4-042 plus
  validation for P4-056/P4-059) and the documented ctx-cell
  convention — P4-053/P4-056/P4-059 need rows their owner legs
  supply, not a second KAUR fetch (said in docs/p4_kaur.md).
* Bands are first-cut judgments with no live calibration (flood
  T10 -> 25 frequent, T100 -> 45, surge -> 50, T1000 -> 65,
  measured clear -> 80; gw strict -> 30, mild -> 55, clear -> 75;
  pollen korge -> 40 / keskmine -> 55 / madal -> 70; rattle -> 45,
  quiet -> 70; episode -> 40, quiet -> 65; Harku-only -> 50,
  1-2 local stations -> 65, 3+ -> 75; sector >15 downwind days ->
  35, 6-15 -> 50, <=5 -> 65; court korge+episode -> 40, korge
  alone -> 55, keskmine -> 65; surge erosion -> 45, clear -> 75;
  keelatud+episode -> 25, keelatud quiet -> 50, piiratud+episode ->
  40, piiratud quiet -> 60); they MUST be recalibrated from a real
  snapshot on reopen (docs/p4_kaur.md checklist). Unknown labels
  stay NULL: an unverified label is not a class.
* Sibling-leg split (no double-scoring): paaste owns the P4-015
  fire-density slice, the P4-042 chimney-notice cells, the P4-058
  ice-fall notices, and the P4-059 rule join itself; trans owns the
  P4-023 zone gradient and the P4-046 second-exit check; EGT/Maa-amet
  own turvas/karst/alvar (P4-016) and the LiDAR enclosure index
  (P4-056). Every kaur dim scores ONLY its KAUR slice and names the
  owner leg in its reason — all dim keys carry the _kaur suffix.
* P4-015 window 300 m (parcel-adjacent zone cell) vs the 3 km
  station cross-check radius (air/pollen/rattle signals carry
  across the asum); P4-031 counts met/wind stations inside 2 km
  (backyard truth is local); P4-053 sectors gate at 1500 m (sector
  footprint, never a circle buffer around the emitter).
* P4-059 scores enforcement recency, not the rule: a rule cell
  without a monitoring station in 3 km stays NULL (enforcement is
  unjudgeable without a monitor — the paaste rule join already
  scores the stranded-stove risk itself).
* Annual TTL (KAUR_TTL_S = 365 d): flood/groundwater zones move on
  planning cycles and the station rows are reference rows; yearly
  re-pull converges per AGENTS.md section 7.4 while new KAUR
  publications trigger an out-of-band re-pull. Stated, not hidden.

Integration (deliberately NOT done here): wiring the snapshot into a
listing pipeline plus rebalancing livability.WEIGHTS must be one joint
change across all batches — existing tests pin set(WEIGHTS) exactly,
so per-batch WEIGHTS edits would break every sibling. No shared files
touched: 3 new files only.
"""

import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Verified open host (2026-09-13: PostgREST 12.0.1 answers anonymously;
#: f_kliima_paev returned a Tallinn-Harku row). Re-pull anchor for the
#: station/observation slices; example table URLs live on the portal
#: andmeteenused page (see module docstring).
KAUR_API_HOST = "https://keskkonnaandmed.envir.ee/"

#: Open bulk endpoint for the per-parcel zone/station reference slices:
#: NONE verified 2026-09-13 (dated negative, see module docstring).
#: Stays None until the reopening checklist in docs/p4_kaur.md names a
#: verified bulk URL; while None, fetch performs no requests.
KAUR_BULK_URL: Optional[str] = None

#: Max one download per 365 d per cache dir (parameters4.md P4-015/P4-016:
#: annual bulk; zones move on planning cycles, station rows are
#: reference rows; KAUR publications trigger an out-of-band re-pull).
#: Stated TTL.
KAUR_TTL_S = 365 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "kaur-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
KAUR_UA = "home-finder KAUR openness-check (max 1 req/365d, no scrape)"

#: Snapshot zone classes (parameters4.md KAUR slices: flood T10-T1000 +
#: storm surge; groundwater protection strict/mild).
ZONE_T10 = "t10"
ZONE_T100 = "t100"
ZONE_T1000 = "t1000"
ZONE_SURGE = "surge"
ZONE_GW_STRICT = "gw_strict"
ZONE_GW_MILD = "gw_mild"
KNOWN_ZONES = (ZONE_T10, ZONE_T100, ZONE_T1000, ZONE_SURGE,
               ZONE_GW_STRICT, ZONE_GW_MILD)

#: Snapshot station kinds (air + pollen seire, met baseline, wind).
ST_AIR = "air"
ST_POLLEN = "pollen"
ST_MET = "met"
ST_WIND = "wind"
KNOWN_STATION_KINDS = (ST_AIR, ST_POLLEN, ST_MET, ST_WIND)

#: Pollen season levels.
LVL_HIGH = "korge"
LVL_MID = "keskmine"
LVL_LOW = "madal"
KNOWN_LEVELS = (LVL_HIGH, LVL_MID, LVL_LOW)

#: Context-cell kinds (caller-supplied, never from the snapshot).
CTX_SECTOR = "sector"
CTX_COURT = "court"
CTX_BURN_RULE = "burn_rule"

#: Court enclosure classes; burn-rule classes.
ENC_HIGH = "korge"
ENC_MID = "keskmine"
RULE_BAN = "keelatud"
RULE_LIMIT = "piiratud"


def fetch_kaur_snapshot(cache_dir: str,
                        ttl_s: int = KAUR_TTL_S,
                        bulk_url: Optional[str] = KAUR_BULK_URL,
                        ) -> Optional[str]:
    """Polite KAUR snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with KAUR_UA and a 30 s
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
        req = urllib.request.Request(bulk_url, headers={"User-Agent": KAUR_UA})
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

def parse_kaur_snapshot(path: str) -> Optional[dict]:
    """Read a cached KAUR snapshot file. Offline, stdlib.

    Returns {"zones": [...], "stations": [...]} with malformed rows
    skipped, or None when the file is missing/unparseable (unknown,
    never an empty snapshot — scorers must not read "no file" as
    "no zones").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    zones = raw.get("zones") if isinstance(raw.get("zones"), list) else []
    stations = (raw.get("stations")
                if isinstance(raw.get("stations"), list) else [])
    return {"zones": [r for r in zones if isinstance(r, dict)],
            "stations": [r for r in stations if isinstance(r, dict)]}


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


def _token(value) -> Optional[str]:
    """Lowercased stripped token, or None when missing/empty."""
    if value is None:
        return None
    s = str(value).strip().lower()
    return s if s else None


def _as_bool(value) -> Optional[bool]:
    """Real booleans pass through; anything else is unknown (None)."""
    if value is True:
        return True
    if value is False:
        return False
    return None


def zones_to_pois(zones: List[dict]) -> List[dict]:
    """Zone rows -> scorer POIs. Unknown zone tokens and rows without
    coords stay out (never faked)."""
    pois = []
    for row in zones:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        zone = _token(row.get("zone"))
        if zone not in KNOWN_ZONES:
            continue
        lat, lon = ll
        pois.append({
            "kind": "kaur_zone_p4",
            "lat": lat, "lon": lon,
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "name": str(row.get("name") or "tundmatu"),
            "zone": zone,
        })
    return pois


def stations_to_pois(stations: List[dict]) -> List[dict]:
    """Station rows -> scorer POIs. Unknown kinds and rows without
    coords stay out; non-bool episode/rattle read as unknown (None)."""
    pois = []
    for row in stations:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        s_kind = _token(row.get("s_kind"))
        if s_kind not in KNOWN_STATION_KINDS:
            continue
        lat, lon = ll
        level = _token(row.get("level"))
        pois.append({
            "kind": "kaur_station_p4",
            "lat": lat, "lon": lon,
            "station_id": str(row.get("station_id") or "tundmatu"),
            "name": str(row.get("name") or "tundmatu"),
            "s_kind": s_kind,
            "level": level if level in KNOWN_LEVELS else None,
            "episode": _as_bool(row.get("episode")),
            "rattle": _as_bool(row.get("rattle")),
        })
    return pois


def snapshot_to_pois(snapshot: Optional[dict]) -> List[dict]:
    """Parsed snapshot (or None) -> scorer POIs for all dims. Pure.

    Context cells (kaur_ctx_p4) are caller-supplied and never come
    from the snapshot — tests and the future hook append them.
    """
    if not isinstance(snapshot, dict):
        return []
    pois: List[dict] = []
    if isinstance(snapshot.get("zones"), list):
        pois.extend(zones_to_pois(snapshot["zones"]))
    if isinstance(snapshot.get("stations"), list):
        pois.extend(stations_to_pois(snapshot["stations"]))
    return pois


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


def _near(origin: Tuple[float, float], pois: List[dict], kind: str,
          window_m: float,
          pred=None) -> List[Tuple[float, dict]]:
    """[(distance_m, poi)] of well-formed POIs of kind within window.

    pred optionally filters POIs (e.g. zone class); malformed coords
    never match. Pure.
    """
    hits = []
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        if pred is not None and not pred(p):
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


def _has_kind(pois: List[dict], kind: str, pred=None) -> bool:
    """True when the snapshot holds >=1 well-formed POI of kind (anywhere).

    Gates "measured clear" scores: clear is only scored when the slice
    exists elsewhere, never from an empty snapshot.
    """
    return bool(_near((0.0, 0.0), pois, kind, 20_000_000.0, pred))


# ---------------------------------------------------------------------------
# Windows + bands (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: Parcel-adjacent zone cell (flood / groundwater / surge footprints).
ZONE_WINDOW_M = 300.0
#: Station cross-check radius (air/pollen/rattle carry across the asum).
STATION_WINDOW_M = 3000.0
#: Backyard-truth radius (P4-031 microclimate is local).
MICRO_WINDOW_M = 2000.0
#: Parcel-adjacent context cells (courtyard / burn-rule register rows).
CTX_WINDOW_M = 500.0
#: Odour-sector footprint (sector shape, never a circle buffer).
SECTOR_WINDOW_M = 1500.0

#: P4-015 flood zone -> score (high = safely insurable). First-cut
#: bands, MUST be recalibrated from a real snapshot on reopen.
FLOOD_SCORES = {
    ZONE_T10: 25,
    ZONE_T100: 45,
    ZONE_SURGE: 50,
    ZONE_T1000: 65,
}
#: Measured clear: zones joined elsewhere, none at the parcel.
FLOOD_CLEAR_SCORE = 80

#: P4-016 groundwater protection -> score (high = septic/kaev free).
GW_SCORES = {
    ZONE_GW_STRICT: 30,
    ZONE_GW_MILD: 55,
}
GW_CLEAR_SCORE = 75

#: P4-023 AMari-rattle cross-check (high = quiet).
RATTLE_SCORE = 45
RATTLE_QUIET_SCORE = 70

#: P4-024 pollen season level -> score (high = easy breathing).
POLLEN_SCORES = {
    LVL_HIGH: 40,
    LVL_MID: 55,
    LVL_LOW: 70,
}

#: P4-031 station-density knowability (high = anchored microclimate).
HARKU_ONLY_SCORE = 50
FEW_STATIONS_SCORE = 65
DENSE_STATIONS_SCORE = 75

#: P4-042 smoke-episode cross-check (high = clean-air memory).
EPISODE_SCORE = 40
EPISODE_QUIET_SCORE = 65

#: P4-046 draining-ground-floor check (high = hard to strand).
BAD_GROUND_SCORE = 35
MILD_GROUND_SCORE = 60
DRY_GROUND_SCORE = 75
_BAD_GROUND = (ZONE_T10, ZONE_T100, ZONE_SURGE, ZONE_GW_STRICT)
_MILD_GROUND = (ZONE_T1000, ZONE_GW_MILD)

#: P4-053 downwind-days-per-year -> score (high = rarely downwind).
SECTOR_OFTEN_SCORE = 35
SECTOR_SOMETIMES_SCORE = 50
SECTOR_RARE_SCORE = 65

#: P4-056 courtyard trap (high = ventilated).
COURT_VALIDATED_SCORE = 40
COURT_WEAK_SCORE = 55
COURT_OPEN_SCORE = 65

#: P4-058 storm-surge erosion edge (high = stable edge).
SURGE_EDGE_SCORE = 45
SURGE_CLEAR_SCORE = 75

#: P4-059 enforcement recency (high = unenforced paper rule).
BAN_ENFORCED_SCORE = 25
BAN_QUIET_SCORE = 50
LIMIT_ENFORCED_SCORE = 40
LIMIT_QUIET_SCORE = 60


def _is_zone(*zones):
    def pred(p):
        return p.get("zone") in zones
    return pred


def _is_station(*kinds):
    def pred(p):
        return p.get("s_kind") in kinds
    return pred


def _is_ctx(ctx):
    def pred(p):
        return p.get("ctx") == ctx
    return pred


# ---------------------------------------------------------------------------
# P4-015 (demo): insurability, KAUR flood-zone leg (zone join).
# ---------------------------------------------------------------------------

def dim_kindlustatavus_kaur(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-015: nearest KAUR flood zone within 300 m (high = insurable).

    Only the KAUR flood leg of the param: T10 -> 25, T100 -> 45,
    storm-surge -> 50, T1000 -> 65, measured clear (zones joined
    elsewhere, none here) -> 80. Sibling legs (PPA theft stats, insurer
    tariff zones, paaste fire density) untouched — named, never scored.
    """
    if not origin or pois is None:
        return None, ("Kindlustatavuse info puudub (EI OLE KAUR-hetktõmmist: "
                      "masinloetavat üleujutuskihti pole liidetud, allikad on "
                      "Keskkonnaportaal ja üleujutuskaart)")
    if not _has_kind(pois, "kaur_zone_p4",
                     _is_zone(ZONE_T10, ZONE_T100, ZONE_T1000, ZONE_SURGE)):
        return None, ("Kindlustatavuse info puudub (EI OLE üleujutus-"
                      "KAUR-tõmmist hetkel: tühi tõmmis ei ole kuiv otsus)")
    hits = _near(origin, pois, "kaur_zone_p4", ZONE_WINDOW_M,
                 _is_zone(ZONE_T10, ZONE_T100, ZONE_T1000, ZONE_SURGE))
    if not hits:
        return FLOOD_CLEAR_SCORE, ("Üleujutustsoon (hinnang): 300 m raadiuses "
                                   "KAUR-tsooni pole (tõmmises on tsoone "
                                   "mujal) → skoor %d; varguse tariifi ja "
                                   "tule-tiheduse jalad on liitmata"
                                   % FLOOD_CLEAR_SCORE)
    d0, z0 = hits[0]
    score = FLOOD_SCORES[z0["zone"]]
    return score, ("Üleujutustsoon (hinnang): %s klass '%s' %s → skoor %d "
                   "(ülempiir: kindlustusmakse selgub kindlustusseltsi "
                   "tariifitsoonist, mitte sellest kihist)"
                   % (z0.get("name"), z0["zone"], _fmt_m(d0), score))


# ---------------------------------------------------------------------------
# P4-016: engineering geology, KAUR groundwater-protection leg.
# ---------------------------------------------------------------------------

def dim_pinnas_kaur(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-016: groundwater-protection zone join (high = septic free).

    Strict kaitseala -> 30 (kaev/septic restricted), mild -> 55,
    measured clear -> 75. EGT turvas/karst/alvar and Maa-amet geology
    legs untouched — named, never scored.
    """
    if not origin or pois is None:
        return None, ("Pinnase info puudub (EI OLE KAUR-põhjavee hetktõmmist: "
                      "masinloetavat kaitsealakihti pole liidetud)")
    if not _has_kind(pois, "kaur_zone_p4",
                     _is_zone(ZONE_GW_STRICT, ZONE_GW_MILD)):
        return None, ("Pinnase info puudub (EI OLE põhjavee-KAUR-tõmmist "
                      "hetkel: tühi tõmmis ei ole kuiv otsus)")
    hits = _near(origin, pois, "kaur_zone_p4", ZONE_WINDOW_M,
                 _is_zone(ZONE_GW_STRICT, ZONE_GW_MILD))
    if not hits:
        return GW_CLEAR_SCORE, ("Põhjavee kaitseala (hinnang): 300 m raadiuses "
                                "kaitseala pole (tõmmises on alasid mujal) → "
                                "skoor %d; turvas/karst/alvari ja kandevõime "
                                "jalad on liitmata (EGT/Maa-amet)"
                                % GW_CLEAR_SCORE)
    d0, z0 = hits[0]
    score = GW_SCORES[z0["zone"]]
    return score, ("Põhjavee kaitseala (hinnang): %s klass '%s' %s → skoor %d "
                   "(ülempiir: vundamendi hind selgub geotehnilisest "
                   "aruandest, mitte sellest kihist)"
                   % (z0.get("name"), z0["zone"], _fmt_m(d0), score))


# ---------------------------------------------------------------------------
# P4-023: airport + military noise, KAUR rattle cross-check leg.
# ---------------------------------------------------------------------------

def dim_mura_kaur(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """P4-023: nearest KAUR air station rattle flag within 3 km.

    Rattle flagged -> 45 (Ämari cross-check hit), quiet station ->
    70. The zone gradient itself lives in the trans/EANS leg — this
    dim validates, never gradients.
    """
    if not origin or pois is None:
        return None, ("Mürateabe info puudub (EI OLE KAUR-õhuseire hetktõmmist: "
                      "jaamu pole liidetud)")
    if not _has_kind(pois, "kaur_station_p4", _is_station(ST_AIR)):
        return None, ("Mürateabe info puudub (EI OLE õhu-KAUR-tõmmist hetkel: "
                      "tühi tõmmis ei ole vaikne otsus)")
    hits = _near(origin, pois, "kaur_station_p4", STATION_WINDOW_M,
                 _is_station(ST_AIR))
    if not hits:
        return None, ("Mürateabe info puudub (EI OLE KAUR-õhujaama 3 km "
                      "raadiuses — akna taga on teadmata, mitte vaikne)")
    d0, s0 = hits[0]
    if s0.get("rattle") is True:
        return RATTLE_SCORE, ("Müra ristkontroll (hinnang): %s on mürasündmuse "
                              "lipu all %s → skoor %d; tsoonigradient elab "
                              "trans/EANS jalas, mitte siin"
                              % (s0.get("name"), _fmt_m(d0), RATTLE_SCORE))
    if s0.get("rattle") is False:
        return RATTLE_QUIET_SCORE, ("Müra ristkontroll (hinnang): lähim %s "
                                    "vaikne %s → skoor %d (ülempiir: "
                                    "lennu/militaarmüra tsoon selgub "
                                    "müratsoonide kaardilt)"
                                    % (s0.get("name"), _fmt_m(d0),
                                       RATTLE_QUIET_SCORE))
    return None, ("Mürateabe info puudub (EI OLE kinnitatud lippu: jaam %s "
                  "rattle-staatus on teadmata — kontrollimata lipp ei ole "
                  "vaikne otsus)" % s0.get("name"))


# ---------------------------------------------------------------------------
# P4-024: country-health nuisances, KAUR pollen-monitoring leg.
# ---------------------------------------------------------------------------

def dim_tervis_kaur(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-024: nearest KAUR pollen station season level within 3 km.

    korge -> 40, keskmine -> 55, madal -> 70. Tick stats, PRIA
    spray-drift, and farm-odour legs untouched — named, never scored.
    """
    if not origin or pois is None:
        return None, ("Allergeeniteabe info puudub (EI OLE KAUR-õietolmu "
                      "hetktõmmist: jaamu pole liidetud)")
    if not _has_kind(pois, "kaur_station_p4", _is_station(ST_POLLEN)):
        return None, ("Allergeeniteabe info puudub (EI OLE õietolmu-"
                      "KAUR-tõmmist hetkel: tühi tõmmis ei ole puhas otsus)")
    hits = _near(origin, pois, "kaur_station_p4", STATION_WINDOW_M,
                 _is_station(ST_POLLEN))
    if not hits:
        return None, ("Allergeeniteabe info puudub (EI OLE KAUR-õietolmujaama "
                      "3 km raadiuses — akna taga on teadmata, mitte puhas)")
    d0, s0 = hits[0]
    level = s0.get("level")
    score = POLLEN_SCORES.get(level) if isinstance(level, str) else None
    if score is None:
        return None, ("Allergeeniteabe info puudub (EI OLE kinnitatud taset: "
                      "jaama %s tase on '%s' — kontrollimata silt ei ole tase)"
                      % (s0.get("name"), level))
    return score, ("Õietolmu hooaeg (hinnang): jaam %s tase '%s' %s → skoor %d "
                   "(jäme hinnang: puugi- ja pritsimisjalad on liitmata)"
                   % (s0.get("name"), level, _fmt_m(d0), score))


# ---------------------------------------------------------------------------
# P4-031: backyard weather + DIY air, Harku-baseline + density leg.
# ---------------------------------------------------------------------------

def dim_mikrokliima_kaur(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-031: met/wind station density within 2 km (high = anchored).

    No local station but Harku baseline in snapshot -> 50; 1-2 local
    stations -> 65; 3+ -> 75. The count rides in the reason (shape
    per parameters4.md: coarse hinnang with sensor-count reason).
    """
    if not origin or pois is None:
        return None, ("Mikrokliima info puudub (EI OLE KAUR-ilmajaamade "
                      "hetktõmmist: jaamu pole liidetud)")
    if not _has_kind(pois, "kaur_station_p4",
                     _is_station(ST_MET, ST_WIND)):
        return None, ("Mikrokliima info puudub (EI OLE ilma-KAUR-tõmmist "
                      "hetkel: tühi tõmmis ei ole soe otsus)")
    hits = _near(origin, pois, "kaur_station_p4", MICRO_WINDOW_M,
                 _is_station(ST_MET, ST_WIND))
    n = len(hits)
    if n == 0:
        return HARKU_ONLY_SCORE, ("Mikrokliima (hinnang): kohalikku jaama 2 km "
                                  "raadiuses pole, Harku baasjaam on tõmmises "
                                  "mujal → skoor %d (nõrk baasihinnang, "
                                  "andurite arv 0)" % HARKU_ONLY_SCORE)
    if n >= 3:
        d0, s0 = hits[0]
        return DENSE_STATIONS_SCORE, ("Mikrokliima (hinnang): %d jaama 2 km "
                                      "raadiuses, lähim %s %s → skoor %d "
                                      "(andurite arv %d)"
                                      % (n, s0.get("name"), _fmt_m(d0),
                                         DENSE_STATIONS_SCORE, n))
    d0, s0 = hits[0]
    return FEW_STATIONS_SCORE, ("Mikrokliima (hinnang): %d jaama 2 km "
                                "raadiuses, lähim %s %s → skoor %d "
                                "(andurite arv %d; külmatasku täpsus selgub "
                                "kohapealt)" % (n, s0.get("name"), _fmt_m(d0),
                                                FEW_STATIONS_SCORE, n))


# ---------------------------------------------------------------------------
# P4-042: smell/dawn-chorus, KAUR smoke-episode cross-check leg.
# ---------------------------------------------------------------------------

def dim_louna_kaur(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-042: nearest KAUR air station episode flag within 2 km.

    Recent smoke episode -> 40, quiet station -> 65. Coarse hinnang,
    never doorway precision; paaste chimney-notice cells untouched.
    """
    if not origin or pois is None:
        return None, ("Lõhnateabe info puudub (EI OLE KAUR-õhujaamade "
                      "hetktõmmist: jaamu pole liidetud)")
    if not _has_kind(pois, "kaur_station_p4", _is_station(ST_AIR)):
        return None, ("Lõhnateabe info puudub (EI OLE õhu-KAUR-tõmmist hetkel: "
                      "tühi tõmmis ei ole puhas otsus)")
    hits = _near(origin, pois, "kaur_station_p4", MICRO_WINDOW_M,
                 _is_station(ST_AIR))
    if not hits:
        return None, ("Lõhnateabe info puudub (EI OLE KAUR-õhujaama 2 km "
                      "raadiuses — akna taga on teadmata, mitte puhas)")
    d0, s0 = hits[0]
    if s0.get("episode") is True:
        return EPISODE_SCORE, ("Suitsuepisoodi ristkontroll (hinnang): %s on "
                               "hiljutise episoodi all %s → skoor %d (jäme "
                               "hinnang, mitte ukse-täpsus; korstnajalad "
                               "elavad pääste teadetes)"
                               % (s0.get("name"), _fmt_m(d0), EPISODE_SCORE))
    if s0.get("episode") is False:
        return EPISODE_QUIET_SCORE, ("Suitsuepisoodi ristkontroll (hinnang): "
                                     "%s vaikne %s → skoor %d (ülempiir: "
                                     "mälumärkuse ankur selgub kohapealt)"
                                     % (s0.get("name"), _fmt_m(d0),
                                        EPISODE_QUIET_SCORE))
    return None, ("Lõhnateabe info puudub (EI OLE kinnitatud episoodi: jaama "
                  "%s episoodi-staatus on teadmata)" % s0.get("name"))


# ---------------------------------------------------------------------------
# P4-046: dread removal, KAUR draining-ground-floor leg.
# ---------------------------------------------------------------------------

def dim_varu_kaur(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """P4-046: flood/groundwater at the parcel within 300 m.

    Bad ground (T10/T100/surge/gw_strict) -> 35, mild only
    (T1000/gw_mild) -> 60, measured dry -> 75. Fireplace, well-water,
    and second-exit legs untouched — named, never scored.
    """
    if not origin or pois is None:
        return None, ("Varu-kindluse info puudub (EI OLE KAUR-vee hetktõmmist: "
                      "tsoone pole liidetud)")
    if not _has_kind(pois, "kaur_zone_p4",
                     _is_zone(*(_BAD_GROUND + _MILD_GROUND))):
        return None, ("Varu-kindluse info puudub (EI OLE vee-KAUR-tõmmist "
                      "hetkel: tühi tõmmis ei ole kuiv otsus)")
    bad = _near(origin, pois, "kaur_zone_p4", ZONE_WINDOW_M,
                _is_zone(*_BAD_GROUND))
    if bad:
        d0, z0 = bad[0]
        return BAD_GROUND_SCORE, ("Drenaaž (hinnang): %s klass '%s' %s → skoor "
                                  "%d (vesi võib lõksu jätta; kamin/kaev/"
                                  "varuväljapääsu jalad on liitmata)"
                                  % (z0.get("name"), z0["zone"], _fmt_m(d0),
                                     BAD_GROUND_SCORE))
    mild = _near(origin, pois, "kaur_zone_p4", ZONE_WINDOW_M,
                 _is_zone(*_MILD_GROUND))
    if mild:
        d0, z0 = mild[0]
        return MILD_GROUND_SCORE, ("Drenaaž (hinnang): vaid leebe %s klass "
                                   "'%s' %s → skoor %d (ülempiir: täpne "
                                   "põrandakõrgus selgub kohapealt)"
                                   % (z0.get("name"), z0["zone"], _fmt_m(d0),
                                      MILD_GROUND_SCORE))
    return DRY_GROUND_SCORE, ("Drenaaž (hinnang): 300 m raadiuses veetsooni "
                              "pole (tõmmises on tsoone mujal) → skoor %d; "
                              "kamin/kaev/varuväljapääsu jalad on liitmata"
                              % DRY_GROUND_SCORE)


# ---------------------------------------------------------------------------
# P4-053: odour roses, sector + calendar leg (never a circle buffer).
# ---------------------------------------------------------------------------

def dim_lounarose_kaur(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-053: caller-supplied odour sector downwind days (high = rare).

    >15 downwind days/yr -> 35, 6-15 -> 50, <=5 -> 65. Sector shape
    only — no circle buffer around the emitter, ever.
    """
    if not origin or pois is None:
        return None, ("Lõhnarooosi info puudub (EI OLE sektoritõmmist: "
                      "tuuleroosi-sektorit pole liidetud)")
    if not _has_kind(pois, "kaur_ctx_p4", _is_ctx(CTX_SECTOR)):
        return None, ("Lõhnarooosi info puudub (EI OLE sektori-tõmmist hetkel: "
                      "tühi tõmmis ei ole puhas otsus)")
    hits = _near(origin, pois, "kaur_ctx_p4", SECTOR_WINDOW_M,
                 _is_ctx(CTX_SECTOR))
    if not hits:
        return None, ("Lõhnarooosi info puudub (EI OLE lõhnasektorit 1500 m "
                      "raadiuses — sektori taga on teadmata, mitte puhas)")
    d0, c0 = hits[0]
    try:
        days = c0["downwind_days"]
        if isinstance(days, bool):
            raise ValueError
        days = float(days)
    except (TypeError, ValueError, KeyError):
        return None, ("Lõhnarooosi info puudub (EI OLE kinnitatud "
                      "allatuule-päevi: sektor %s päevade arv on '%s' — "
                      "kontrollimata arv ei ole kalender)"
                      % (c0.get("name"), c0.get("downwind_days")))
    if days < 0:
        return None, ("Lõhnarooosi info puudub (EI OLE kinnitatud "
                      "allatuule-päevi: sektor %s arv on negatiivne)"
                      % c0.get("name"))
    if days > 15:
        score = SECTOR_OFTEN_SCORE
        how = "sageli allatuult"
    elif days > 5:
        score = SECTOR_SOMETIMES_SCORE
        how = "aeg-ajalt allatuult"
    else:
        score = SECTOR_RARE_SCORE
        how = "harva allatuult"
    return score, ("Lõhnaroos (hinnang, sektor + kalender): %s allikas '%s', "
                   "%g allatuule-päeva aastas, %s %s → skoor %d (sektorikuju, "
                   "mitte ringpuhver)"
                   % (c0.get("name"), c0.get("emitter"), days, how,
                      _fmt_m(d0), score))


# ---------------------------------------------------------------------------
# P4-056: enclosed-courtyard trap, fume-hold validation leg.
# ---------------------------------------------------------------------------

def dim_sisehoov_kaur(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-056: courtyard morphology cell + KAUR fume validation.

    Enclosed (korge) + nearby air episode -> 40 validated trap;
    korge alone -> 55 weak; keskmine -> 65. The LiDAR enclosure index
    owns the morphology precision — this dim validates fume-hold.
    """
    if not origin or pois is None:
        return None, ("Sisehoovi info puudub (EI OLE hoovitõmmist: "
                      "morfoloogiakärge pole liidetud)")
    if not _has_kind(pois, "kaur_ctx_p4", _is_ctx(CTX_COURT)):
        return None, ("Sisehoovi info puudub (EI OLE hoovi-tõmmist hetkel: "
                      "tühi tõmmis ei ole tuuline otsus)")
    hits = _near(origin, pois, "kaur_ctx_p4", CTX_WINDOW_M,
                 _is_ctx(CTX_COURT))
    if not hits:
        return None, ("Sisehoovi info puudub (EI OLE hoovikärge 500 m "
                      "raadiuses — akna taga on teadmata, mitte tuuline)")
    d0, c0 = hits[0]
    enc = c0.get("enclosure")
    if enc not in (ENC_HIGH, ENC_MID):
        return None, ("Sisehoovi info puudub (EI OLE kinnitatud "
                      "suletusklassi: hoov %s on '%s' — kontrollimata silt "
                      "ei ole klass)" % (c0.get("name"), enc))
    if enc == ENC_MID:
        return COURT_OPEN_SCORE, ("Sisehoov (hinnang): %s suletus 'keskmine' "
                                  "%s → skoor %d (ülempiir: täpne suletusindeks "
                                  "elab LiDAR-jalas)" % (c0.get("name"),
                                                         _fmt_m(d0),
                                                         COURT_OPEN_SCORE))
    air = _near(origin, pois, "kaur_station_p4", STATION_WINDOW_M,
                _is_station(ST_AIR))
    if air and air[0][1].get("episode") is True:
        return COURT_VALIDATED_SCORE, ("Sisehoov (hinnang): %s suletus 'korge' "
                                       "%s + %s episood → kinnitatud "
                                       "lõks, skoor %d"
                                       % (c0.get("name"), _fmt_m(d0),
                                          air[0][1].get("name"),
                                          COURT_VALIDATED_SCORE))
    return COURT_WEAK_SCORE, ("Sisehoov (hinnang): %s suletus 'korge' %s, "
                              "õhusepisoodi pole kinnitatud → nõrk skoor %d "
                              "(LiDAR-täpsus liitmata)"
                              % (c0.get("name"), _fmt_m(d0),
                                 COURT_WEAK_SCORE))


# ---------------------------------------------------------------------------
# P4-058: falling-ice + cliff retreat, KAUR storm-surge erosion leg.
# ---------------------------------------------------------------------------

def dim_jaapurikas_kaur(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-058: storm-surge erosion edge within 300 m (high = stable).

    Surge zone -> 45, measured clear (surge zones elsewhere) -> 75.
    Paaste ice-fall notices and roof-type legs untouched.
    """
    if not origin or pois is None:
        return None, ("Rannikuserva info puudub (EI OLE KAUR-tormitõusu "
                      "hetktõmmist: tsoone pole liidetud)")
    if not _has_kind(pois, "kaur_zone_p4", _is_zone(ZONE_SURGE)):
        return None, ("Rannikuserva info puudub (EI OLE tormitõusu-"
                      "KAUR-tõmmist hetkel: tühi tõmmis ei ole kindel otsus)")
    hits = _near(origin, pois, "kaur_zone_p4", ZONE_WINDOW_M,
                 _is_zone(ZONE_SURGE))
    if not hits:
        return SURGE_CLEAR_SCORE, ("Tormitõusu serv (hinnang): 300 m raadiuses "
                                   "tormitõusutsooni pole (tõmmises on tsoone "
                                   "mujal) → skoor %d; jääpurika- ja "
                                   "katusetüübi jalad on liitmata (Pääste/EHR)"
                                   % SURGE_CLEAR_SCORE)
    d0, z0 = hits[0]
    return SURGE_EDGE_SCORE, ("Tormitõusu serv (hinnang): %s %s → erodeeruv "
                              "serv, skoor %d (ülempiir: randajoone muutus "
                              "selgub Maa-ameti kihist; jääpurika- ja "
                              "katusejalad elavad Pääste/EHR liites)"
                              % (z0.get("name"), _fmt_m(d0),
                                 SURGE_EDGE_SCORE))


# ---------------------------------------------------------------------------
# P4-059: wood-burning restrictions, KAUR enforcement-recency leg.
# ---------------------------------------------------------------------------

def dim_tahkekyte_kaur(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-059: burn-rule cell + KAUR enforcement episode (high = paper).

    keelatud + episode -> 25 enforced, keelatud quiet -> 50,
    piiratud + episode -> 40, piiratud quiet -> 60. Scores enforcement
    recency only — the paaste rule join scores the stranded-stove risk
    itself. A rule cell without a monitoring station stays NULL.
    """
    if not origin or pois is None:
        return None, ("Tahkekütte info puudub (EI OLE piirangutõmmist: "
                      "reeglikärge pole liidetud)")
    if not _has_kind(pois, "kaur_ctx_p4", _is_ctx(CTX_BURN_RULE)):
        return None, ("Tahkekütte info puudub (EI OLE reegli-tõmmist hetkel: "
                      "tühi tõmmis ei ole lubav otsus)")
    hits = _near(origin, pois, "kaur_ctx_p4", CTX_WINDOW_M,
                 _is_ctx(CTX_BURN_RULE))
    if not hits:
        return None, ("Tahkekütte info puudub (EI OLE piirangukärge 500 m "
                      "raadiuses — akna taga on teadmata, mitte lubatud)")
    d0, c0 = hits[0]
    rule = c0.get("rule")
    if rule not in (RULE_BAN, RULE_LIMIT):
        return None, ("Tahkekütte info puudub (EI OLE kinnitatud reeglit: "
                      "kärje %s reegel on '%s' — kontrollimata silt ei ole "
                      "reegel)" % (c0.get("name"), rule))
    air = _near(origin, pois, "kaur_station_p4", STATION_WINDOW_M,
                _is_station(ST_AIR))
    if not air or air[0][1].get("episode") is None:
        return None, ("Tahkekütte info puudub (EI OLE järelevalvejaama 3 km "
                      "raadiuses kinnitatud episoodiga — jõustamist ei saa "
                      "hinnata, reeglirisk elab pääste reegliliites)")
    enforced = air[0][1].get("episode") is True
    if rule == RULE_BAN:
        score = BAN_ENFORCED_SCORE if enforced else BAN_QUIET_SCORE
        how = "jõustatud" if enforced else "paberil"
    else:
        score = LIMIT_ENFORCED_SCORE if enforced else LIMIT_QUIET_SCORE
        how = "jõustatud" if enforced else "paberil"
    return score, ("Tahkekütte järelevalve (hinnang): %s reegel '%s' %s, %s %s → "
                   "skoor %d (reegel ise elab pääste liites, mitte siin)"
                   % (c0.get("name"), rule, _fmt_m(d0),
                      air[0][1].get("name"), how, score))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_KAUR_DIMS = (
    ("kindlustatavus_kaur", "P4-015", dim_kindlustatavus_kaur),
    ("pinnas_kaur", "P4-016", dim_pinnas_kaur),
    ("mura_kaur", "P4-023", dim_mura_kaur),
    ("tervis_kaur", "P4-024", dim_tervis_kaur),
    ("mikrokliima_kaur", "P4-031", dim_mikrokliima_kaur),
    ("louna_kaur", "P4-042", dim_louna_kaur),
    ("varu_kaur", "P4-046", dim_varu_kaur),
    ("lounarose_kaur", "P4-053", dim_lounarose_kaur),
    ("sisehoov_kaur", "P4-056", dim_sisehoov_kaur),
    ("jaapurikas_kaur", "P4-058", dim_jaapurikas_kaur),
    ("tahkekyte_kaur", "P4-059", dim_tahkekyte_kaur),
)


def score_p4_kaur(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All eleven P4 KAUR dims for one listing (entry point for the
    follow-up). Missing slices stay None by design — zone join / coarse
    hinnang, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_KAUR_DIMS}
