"""P4 TPR dims (issues #250 demo + #334 coverage): Tallinna planeeringute register.

Params (this module only — sibling #236 owns PLANK/TPR for parameters3
Group 5 this-parcel zoning; nothing here touches dims_group05*.py):
* P4-006 neighbouring detailplaneering pipeline, 500 m (demo, batch 1)
* P4-005 ehitusluba/kasutusluba existence, TPR elluviimine leg (batch 1)
* P4-050 permit glut vs completions, TPR forward-pipeline leg (batch 5)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#250 acceptance): the Tallinna planeeringute register is a human-facing
web register with NO open bulk endpoint. Polite evidence, ~5 tiny
requests total (custom UA, headers + one 83 kB front page, no scrape):
* HEAD https://tpr.tallinn.ee/ -> HTTP 200, Apache, text/html (83 331 B)
* GET  https://tpr.tallinn.ee/ -> "<title>Tpr</title>" Angular SPA
  (main-*.js is 3.9 MB — deliberately NOT downloaded, polite stop)
* HEAD main-*.js -> application/javascript, 3 960 409 B (size probe only)
* PLANK WFS https://planeeringud.ee/geoserver/wfs?...GetCapabilities
  -> HTTP 301 to https://livekluster.ehr.ee/ui/ehr/v1/detailsearch/
  PLANNINGS_SEARCH (E-ehitus SPA): the old GeoServer endpoint is gone.
Raw headers/page cached at /tmp/tpr-open/ (TTL: one-off check, kept
for the PR record, never committed). So the live path below is honest
plumbing with NO live data: fetch_tpr_snapshot performs NO request
while TPR_BULK_URL is None, every scorer then returns None with an
Estonian EI OLE reason, and the scored shapes are proven on fixtures
only. Reopening checklist lives in docs/p4_tpr.md.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components; every NULL reason says "EI OLE"
and names the missing input. Transport errors are never cached as data
(fetch_tpr_snapshot stores a body only on HTTP 200 with JSON content,
else returns None). A measured zero from the snapshot (0 menetluses
plans in the buffer while the snapshot holds plans elsewhere; an area
row with pipeline_units == 0) scores — a real no-pipeline signal —
while a missing join (no snapshot, no row in the window, count None)
stays NULL: absence of data is unknown, never good. Distances are
bird-flight, never routed or parcel-exact.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_tpr_snapshot(cache_dir): polite pull, max 1 download / 7 d per
  cache dir (TPR_TTL_S; parameters4.md P4-006 cadence: weekly; P4-050
  counts are quarterly but pulled on the same weekly ticket). Cache hit
  within TTL performs NO request. While no open bulk endpoint exists
  (TPR_BULK_URL is None) it performs no request at all and returns the
  fresh-cache path or None. Single GET with an identifying UA once a
  bulk URL is known, no retries (HTTP 429 is a stop signal, 7.4).
* parse_tpr_snapshot / plans_to_pois / areas_to_pois /
  snapshot_to_pois: pure offline readers over the cached JSON snapshot
  (schema documented below). Network lives ONLY in fetch_tpr_snapshot;
  scorers and tests never touch it.
* One snapshot, two tables, no new source for coverage: "plans" feeds
  P4-006 + P4-005, "areas" feeds P4-050 (this is why demo + coverage
  pair in ONE PR — #334 expects no new plumbing, said in docs/p4_tpr.md).

Snapshot schema (what a future adapter would store; fixtures match it):
  {"plans": [{"plan_id": str, "stage": str, "lat": float, "lon": float,
              "impl_permits": int|None, "impl_units": int|None}],
   "areas": [{"area_code": str, "lat": float, "lon": float,
              "pipeline_units": int|None, "completions_units": int|None}]}
Malformed rows are skipped, never faked; a missing/unparseable file
parses to None (unknown), never to an empty snapshot.

Style mirrors services/scoring/dims_p4_peatus.py (#314/#376, the honest-
plumbing precedent): pure scorers (origin, pois) -> (Optional[int
0..100], Estonian reason), local helpers (no livability import —
importing it here would turn the future central hook into a cycle,
same precedent as PRs #100/#106/#115). Unlike peatus there is NO
staged Overpass fragment and no tag mapping: OSM has no honest tag for
TPR menetlus stages, so there is nothing for the live path to fetch
(same rationale as the group20a no-map batches).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because the #334 body states it
  "extends the demoed ingestion" with "no new plumbing expected": the
  areas table is a same-snapshot second table, not a second source.
* Pipeline counts ONLY stage == "menetluses" (case-insensitive, the
  parameters4.md P4-006 wording). Neighbour in-flight labels
  (algatatud/vastuvõetud/avalik väljapanek) are NOT counted until
  verified against the live register — conservative by design.
* P4-006 zero-in-buffer scores 90 (clear) ONLY when the snapshot holds
  plans elsewhere (measured clear); a snapshot with no plan POIs at
  all stays NULL (no snapshot, not a clear verdict).
* P4-006 bands are a first-cut judgment with no live calibration
  (0 -> 90, 1 -> 65, 2-3 -> 40, >= 4 -> 20); they MUST be recalibrated
  from a real snapshot on reopen (docs/p4_tpr.md checklist).
* P4-005 is presence-only: a kehtestatud plan within 150 m WITH
  impl_permits > 0 scores 75 capped (TPR leg only, never a bankability
  verdict — EHR join missing). A plan without permit records, or no
  plan in the window, stays NULL: a missing TPR link is not proof of
  no permit. The dim is binary by shape (75 | None).
* P4-050 prefers the glut ratio (pipeline/completions, TPR forward
  pipeline over EHR-style completions in the same row) and falls back
  to a pipeline-only band flagged "ainult torustik" when completions
  are missing; completions == 0 with pipeline > 0 is pure pipeline
  (20), 0/0 is NULL (andmelünk). Window 1000 m micro-area, quarterly
  framing, weekly pull ticket.
* Sibling-leg split (no double-scoring): P4-005 bankability stays in
  dims_p4_ehr.dim_permit_bankable (EHR leg, 100/50/20) and P4-050
  falling prices stay in dims_p4_maa_tehingud.dim_permit_glut_price_leg
  (tehingud leg); this module scores ONLY the TPR elluviimine /
  forward-pipeline legs with _tpr-suffixed dim keys. The EHR P4-050
  NULL ("needs a quarterly micro-area table") is exactly the gap the
  TPR areas table fills on its leg.

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

#: Human register (verified 2026-09-13: HTTP 200 Angular SPA, no bulk link).
TPR_INDEX_URL = "https://tpr.tallinn.ee/"

#: Open bulk endpoint: NONE found 2026-09-13 (dated negative, see module
#: docstring). Stays None until the reopening checklist in docs/p4_tpr.md
#: names a verified bulk URL; while None, fetch performs no requests.
TPR_BULK_URL: Optional[str] = None

#: Max one download per 7 d per cache dir (parameters4.md P4-006: weekly;
#: P4-050 quarterly counts ride the same weekly ticket). Stated TTL.
TPR_TTL_S = 7 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "tpr-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
TPR_UA = "home-finder TPR openness-check (max 1 req/7d, no scrape)"

#: Plan stage counted as in-flight pipeline (parameters4.md P4-006).
PIPELINE_STAGE = "menetluses"


def fetch_tpr_snapshot(cache_dir: str,
                       ttl_s: int = TPR_TTL_S,
                       bulk_url: Optional[str] = TPR_BULK_URL,
                       ) -> Optional[str]:
    """Polite TPR snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with TPR_UA and a 30 s
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
        req = urllib.request.Request(bulk_url, headers={"User-Agent": TPR_UA})
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

def parse_tpr_snapshot(path: str) -> Optional[dict]:
    """Read a cached TPR snapshot file. Offline, stdlib.

    Returns {"plans": [...], "areas": [...]} with malformed rows skipped,
    or None when the file is missing/unparseable (unknown, never an
    empty snapshot — scorers must not read "no file" as "no plans").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    plans = raw.get("plans") if isinstance(raw.get("plans"), list) else []
    areas = raw.get("areas") if isinstance(raw.get("areas"), list) else []
    return {"plans": [r for r in plans if isinstance(r, dict)],
            "areas": [r for r in areas if isinstance(r, dict)]}


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


def _sane_count(v) -> Optional[int]:
    """Sanitised unit count: ints only, bool/negative/garbage -> None."""
    if isinstance(v, bool):
        return None
    try:
        n = int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def plans_to_pois(plans: List[dict]) -> List[dict]:
    """Plan rows -> scorer POIs. Rows without coords stay out (never faked)."""
    pois = []
    for row in plans:
        ll = _finite_latlon(row) if isinstance(row, dict) else None
        if ll is None:
            continue
        lat, lon = ll
        stage = row.get("stage")
        pois.append({
            "kind": "plan_p4",
            "lat": lat, "lon": lon,
            "plan_id": str(row.get("plan_id") or "tundmatu"),
            "stage": str(stage).strip().lower() if stage is not None else None,
            "impl_permits": _sane_count(row.get("impl_permits")),
            "impl_units": _sane_count(row.get("impl_units")),
        })
    return pois


def areas_to_pois(areas: List[dict]) -> List[dict]:
    """Area rows -> scorer POIs. Rows without coords stay out (never faked)."""
    pois = []
    for row in areas:
        ll = _finite_latlon(row) if isinstance(row, dict) else None
        if ll is None:
            continue
        lat, lon = ll
        pois.append({
            "kind": "tpr_area_p4",
            "lat": lat, "lon": lon,
            "area_code": str(row.get("area_code") or "tundmatu"),
            "pipeline_units": _sane_count(row.get("pipeline_units")),
            "completions_units": _sane_count(row.get("completions_units")),
        })
    return pois


def snapshot_to_pois(snapshot: Optional[dict]) -> List[dict]:
    """Parsed snapshot (or None) -> scorer POIs for all three dims. Pure."""
    if not isinstance(snapshot, dict):
        return []
    plans = snapshot.get("plans")
    areas = snapshot.get("areas")
    pois: List[dict] = []
    if isinstance(plans, list):
        pois.extend(plans_to_pois(plans))
    if isinstance(areas, list):
        pois.extend(areas_to_pois(areas))
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


# ---------------------------------------------------------------------------
# Windows + bands (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: P4-006 pipeline buffer (parameters4.md: 500 m).
PIPELINE_WINDOW_M = 500.0
#: P4-005 same-parcel/block tolerance (bird-flight judgment call).
PARCEL_WINDOW_M = 150.0
#: P4-050 micro-area window (judgment call).
MICRO_AREA_WINDOW_M = 1000.0

#: menetluses-plan count in 500 m -> pipeline score (high = clear).
#: First-cut bands, MUST be recalibrated from a real snapshot on reopen.
PIPELINE_BANDS = [(0, 90), (1, 65), (3, 40), (float("inf"), 20)]
#: P4-005 presence score (capped: TPR leg only, never bankability).
PERMIT_PRESENT_SCORE = 75
#: Glut ratio pipeline/completions -> score (high = balanced pipeline).
GLUT_BANDS = [(0.5, 80), (1.0, 60), (2.0, 40), (float("inf"), 20)]
#: Pipeline-only fallback (no completions row) -> score, flagged hinnang.
PIPELINE_ONLY_BANDS = [(0, 85), (50, 65), (200, 45), (float("inf"), 25)]


# ---------------------------------------------------------------------------
# P4-006: neighbouring detailplaneering pipeline, 500 m (demo param).
# ---------------------------------------------------------------------------

def dim_pipeline_500m(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-006: menetluses-plan pipeline count in 500 m (high = clear).

    Per-parcel buffer join over the TPR snapshot: counts neighbouring
    detailplaneeringud in stage "menetluses" within 500 m. Zero counts
    score 90 ONLY when the snapshot holds plans elsewhere (measured
    clear); a snapshot with no plan POIs at all stays NULL.
    """
    if not origin or pois is None:
        return None, ("Torustiku info puudub (EI OLE TPR-hetktõmmist: "
                      "avaandmete liidest pole, register on veebivaade)")
    if not _has_kind(pois, "plan_p4"):
        return None, ("Torustiku info puudub (EI OLE plaani-TPR-hetktõmmist "
                      "hetkel: tühi tõmmis ei ole puhas otsus)")
    hits = _near(origin, pois, "plan_p4", PIPELINE_WINDOW_M)
    pipe = [(d, p) for d, p in hits if p.get("stage") == PIPELINE_STAGE]
    n = len(pipe)
    s = _band(n, PIPELINE_BANDS)
    assert s is not None
    if n == 0:
        near_txt = ("lähim plaan %s" % _fmt_m(hits[0][0])) if hits else \
            "500 m raadiuses plaane pole"
        return s, ("Detailplaneeringute torustik (hinnang): 500 m raadiuses "
                   "menetluses plaane 0 (%s) → skoor %d"
                   % (near_txt, s))
    d0, p0 = pipe[0]
    return s, ("Detailplaneeringute torustik (hinnang): 500 m raadiuses "
               "menetluses plaane %d (lähim %s %s) → skoor %d"
               % (n, p0.get("plan_id"), _fmt_m(d0), s))


# ---------------------------------------------------------------------------
# P4-005: ehitusluba/kasutusluba existence, TPR elluviimine leg (coverage).
# ---------------------------------------------------------------------------

def dim_tpr_permit_existence(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-005: permit-existence presence dim (75 | None).

    Only the TPR half of the param: a kehtestatud plan within 150 m WITH
    elluviimine permit records (impl_permits > 0) scores 75 capped. A
    plan without permit records, or no plan in the window, stays NULL —
    a missing TPR link is not proof of no permit. EHR bankability join
    missing by design (never a bankability verdict).
    """
    if not origin or pois is None:
        return None, ("Loa info puudub (EI OLE TPR-hetktõmmist: avaandmete "
                      "liidest pole, register on veebivaade)")
    hits = _near(origin, pois, "plan_p4", PARCEL_WINDOW_M)
    if not hits:
        return None, ("Loa info puudub (EI OLE TPR-elluviimise seost 150 m "
                      "aknas — seose puudumine ei ole loa puudumise tõend)")
    for d, p in hits:
        permits = p.get("impl_permits")
        if (isinstance(permits, int) and permits > 0
                and p.get("stage") == "kehtestatud"):
            return PERMIT_PRESENT_SCORE, (
                "Ehitusloa olemasolu (hinnang, ainult TPR-pool): plaan %s "
                "(%s, kehtestatud, elluviimises lube %d) → skoor %d "
                "(EHR-ristkontroll puudub — mitte pangakõlblikkuse otsus)"
                % (p.get("plan_id"), _fmt_m(d), permits,
                   PERMIT_PRESENT_SCORE))
    d0, p0 = hits[0]
    return None, ("Loa info puudub (EI OLE TPR-elluviimise lubade kirjet: "
                  "lähim plaan %s %s, etapis '%s' — lubade seost pole)"
                  % (p0.get("plan_id"), _fmt_m(d0), p0.get("stage")))


# ---------------------------------------------------------------------------
# P4-050: permit glut vs completions, TPR forward-pipeline leg (coverage).
# ---------------------------------------------------------------------------

def dim_tpr_permit_glut(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-050: glut ratio or pipeline-only band per micro-area (high = calm).

    Prefers pipeline/completions from the nearest tpr_area_p4 row within
    1000 m; falls back to a pipeline-only band flagged "ainult torustik"
    when completions are missing. Quarterly framing, weekly pull ticket.
    """
    if not origin or pois is None:
        return None, ("Mikropiirkonna torustiku info puudub (EI OLE "
                      "TPR-mahutabelit hetkel: avaandmete liidest pole)")
    hits = _near(origin, pois, "tpr_area_p4", MICRO_AREA_WINDOW_M)
    if not hits:
        return None, ("Mikropiirkonna torustiku info puudub (EI OLE "
                      "TPR-mahurea seost 1 km aknas)")
    d0, a0 = hits[0]
    pipe = a0.get("pipeline_units")
    done = a0.get("completions_units")
    code = a0.get("area_code")
    if pipe is None and done is None:
        return None, ("Mikropiirkonna torustiku info puudub (EI OLE "
                      "mahuarve piirkonnas %s — rida ilma arvudeta)"
                      % code)
    if pipe is not None and done is not None:
        if pipe == 0 and done == 0:
            return None, ("Mikropiirkonna torustiku info puudub (EI OLE "
                          "mahuandmeid piirkonnas %s — 0/0 on andmelünk, "
                          "mitte tasakaaluotsus)" % code)
        if done <= 0:
            return 20, ("Loatorustiku vs valmimise suhe (hinnang): piirkond "
                        "%s %s, torustikus %d, valminud %d — puhas torustik "
                        "ilma valmimiseta → skoor 20"
                        % (code, _fmt_m(d0), pipe, done))
        ratio = pipe / done
        s = _band(ratio, GLUT_BANDS)
        assert s is not None
        return s, ("Loatorustiku vs valmimise suhe (hinnang, ainult "
                   "TPR-torustik): piirkond %s %s, torustikus %d vs "
                   "valminud %d (suhe %.1f) → skoor %d"
                   % (code, _fmt_m(d0), pipe, done, ratio, s))
    assert pipe is not None  # done is None here
    s = _band(pipe, PIPELINE_ONLY_BANDS)
    assert s is not None
    return s, ("Loatorustiku maht (hinnang, ainult torustik, "
               "kasutuslubade-liides puudub): piirkond %s %s, torustikus "
               "%d ühikut → skoor %d" % (code, _fmt_m(d0), pipe, s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_TPR_DIMS = (
    ("pipeline_500m", "P4-006", dim_pipeline_500m),
    ("permit_existence_tpr", "P4-005", dim_tpr_permit_existence),
    ("permit_glut_tpr", "P4-050", dim_tpr_permit_glut),
)


def score_p4_tpr(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 TPR dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_TPR_DIMS}
