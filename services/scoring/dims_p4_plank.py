"""P4 PLANK dims (issue #251 demo, single-param): PLANK national WFS leg.

Params (this module only — sibling P4-006 legs untouched, see the split):
* P4-006 neighbouring detailplaneering pipeline, 500 m, PLANK national
  WFS leg (demo, batch 1 — parameters4.md P4-006 source (2): PLANK
  national WFS, Tallinn filter). Single-param demo: no coverage issue.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#251 acceptance): the PLANK national WFS endpoint is GONE. Polite
evidence, 4 tiny requests total (custom UA, headers + two ~3.7 kB SPA
shells, no scrape):
* HEAD https://planeeringud.ee/ -> HTTP 301 (Apache/ZoneOS) to
  https://livekluster.ehr.ee/ui/ehr/v1/detailsearch/PLANNINGS_SEARCH
* HEAD https://planeeringud.ee/geoserver/wfs -> same HTTP 301: the
  documented OGC WFS 2.0.0 base from parameters3.md Group 5 no longer
  serves WFS — it redirects to the E-ehitus platform SPA.
* GET .../geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities
  (redirects followed) -> HTTP 200 text/html, the E-ehitus SPA shell
  ("e-ehituse platvorm", Maa- ja Ruumiameti infosüsteem) — NO WFS XML,
  no GetCapabilities document. The old GeoServer endpoint is gone.
* GET https://planeeringud.ee/ (redirects followed) -> same SPA shell
  (<title>e-ehituse platvorm</title>, 3 663 B).
Raw headers/shells cached at /tmp/plank-open/ (TTL: one-off check, kept
for the PR record, never committed). A web search for a documented
PLANK bulk/API replacement surfaced nothing open (2019 data-model PDF,
EVALD guides referencing register extracts on request — not open bulk).
So the live path below is honest plumbing with NO live data:
fetch_plank_snapshot performs NO request while PLANK_BULK_URL is None,
the scorer then returns None with an Estonian EI OLE reason, and the
scored shape is proven on fixtures only. Reopening checklist lives in
docs/p4_plank.md.

HONESTY (AGENTS.md section 7.2): the scored dim says "hinnang"
(estimate) and prints its components; every NULL reason says "EI OLE"
and names the missing input. Transport errors are never cached as data
(fetch_plank_snapshot stores a body only on HTTP 200 with JSON content,
else returns None). A measured zero from the snapshot (0 menetluses
plans in the buffer while the snapshot holds Tallinn plans elsewhere)
scores — a real no-pipeline signal — while a missing join (no snapshot,
no row in the window, count None) stays NULL: absence of data is
unknown, never good. Distances are bird-flight, never routed or
parcel-exact.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_plank_snapshot(cache_dir): polite pull, max 1 download / 7 d per
  cache dir (PLANK_TTL_S; parameters4.md P4-006 cadence: weekly). Cache
  hit within TTL performs NO request. While no open bulk endpoint exists
  (PLANK_BULK_URL is None) it performs no request at all and returns the
  fresh-cache path or None. Single GET with an identifying UA once a
  bulk URL is known, no retries (HTTP 429 is a stop signal, 7.4).
* parse_plank_snapshot / plans_to_pois / snapshot_to_pois: pure offline
  readers over the cached JSON snapshot (schema documented below).
  Network lives ONLY in fetch_plank_snapshot; the scorer and tests never
  touch it.
* One snapshot, one table: "plans" feeds the single P4-006 PLANK leg
  (single-param demo — no coverage tables, unlike the TPR demo+coverage
  pair; issue #251 states no follow-up coverage issue for this source).

Snapshot schema (what a future adapter would store; fixtures match it):
  {"plans": [{"plan_id": str, "stage": str, "kov": str,
              "lat": float, "lon": float}]}
Malformed rows are skipped, never faked; non-Tallinn rows are skipped
(Tallinn filter — this demo joins neighbouring Tallinn parcels only,
parameters4.md P4-006 "Tallinn filter"); a missing/unparseable file
parses to None (unknown), never to an empty snapshot.

Style mirrors services/scoring/dims_p4_tpr.py (#250/#334, the TPR P4-006
sibling): pure scorer (origin, pois) -> (Optional[int 0..100], Estonian
reason), local helpers (no livability import — importing it here would
turn the future central hook into a cycle, same precedent as PRs
#100/#106/#115). Unlike TPR there is no second table and no staged
Overpass fragment: OSM has no honest tag for PLANK menetlus stages, so
there is nothing for the live path to fetch (same rationale as the
group20a no-map batches).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Pipeline counts ONLY stage == "menetluses" (case-insensitive, the
  parameters4.md P4-006 wording). Neighbour in-flight labels
  (algatatud/vastuvõetud/avalik väljapanek) are NOT counted until
  verified against the live PLANK codelist — conservative by design
  (same call as the TPR sibling; the kataster sibling counts
  algatatud too, pinned there — the legs differ honestly by source).
* Tallinn filter matches kov case-insensitively against
  {"tallinn", "tallinna linn"} (PLANK municipal naming varies between
  "Tallinn" and "Tallinna linn" across register exports). Rows with a
  missing/unparseable kov are skipped: an unknown municipality is never
  assumed to be Tallinn.
* P4-006 zero-in-buffer scores 90 (clear) ONLY when the snapshot holds
  Tallinn plan POIs elsewhere (measured clear); a snapshot with no
  Tallinn plan POIs at all stays NULL (no snapshot, not a clear
  verdict).
* P4-006 bands are a first-cut judgment with no live calibration
  (0 -> 90, 1 -> 65, 2-3 -> 40, >= 4 -> 20 — same first cut as the TPR
  sibling so the legs stay comparable); they MUST be recalibrated from
  a real snapshot on reopen (docs/p4_plank.md checklist).
* Sibling-leg split (no double-scoring): this module scores ONLY the
  PLANK-WFS leg with the _plank-suffixed dim key. TPR bankability stays
  in dims_p4_tpr (TPR leg), the arenguala leg in dims_p4_cityplans, the
  corridor leg in dims_p4_rb, the kataster leg in dims_p4_maa_kataster.
  On reopen, note that PLANK (national aggregate) and TPR (municipal
  register) may describe the SAME Tallinn plans — the central hook must
  decide how the legs combine rather than summing them blindly.

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

#: Documented PLANK WFS base (parameters3.md Group 5; verified 2026-09-13:
#: HTTP 301 to the E-ehitus SPA — the WFS itself is gone, see docstring).
PLANK_WFS_URL = "https://planeeringud.ee/geoserver/wfs"

#: Open bulk endpoint: NONE found 2026-09-13 (dated negative, see module
#: docstring). Stays None until the reopening checklist in docs/p4_plank.md
#: names a verified bulk URL; while None, fetch performs no requests.
PLANK_BULK_URL: Optional[str] = None

#: Max one download per 7 d per cache dir (parameters4.md P4-006: weekly).
#: Stated TTL.
PLANK_TTL_S = 7 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "plank-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
PLANK_UA = "home-finder PLANK openness-check (max 1 req/7d, no scrape)"

#: Plan stage counted as in-flight pipeline (parameters4.md P4-006).
PIPELINE_STAGE = "menetluses"

#: Tallinn kov spellings accepted by the Tallinn filter (lowercased).
TALLINN_KOVS = frozenset({"tallinn", "tallinna linn"})


def fetch_plank_snapshot(cache_dir: str,
                         ttl_s: int = PLANK_TTL_S,
                         bulk_url: Optional[str] = PLANK_BULK_URL,
                         ) -> Optional[str]:
    """Polite PLANK snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with PLANK_UA and a 30 s
    timeout; the body is stored only on HTTP 200 with JSON content, else
    None is returned and nothing is cached (transport errors are never
    data). No retries — HTTP 429/errors are a stop signal. The scorer
    never calls this; tests cover the cache-hit and no-endpoint paths
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
        req = urllib.request.Request(bulk_url, headers={"User-Agent": PLANK_UA})
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

def parse_plank_snapshot(path: str) -> Optional[dict]:
    """Read a cached PLANK snapshot file. Offline, stdlib.

    Returns {"plans": [...]} with malformed rows skipped, or None when the
    file is missing/unparseable (unknown, never an empty snapshot —
    the scorer must not read "no file" as "no plans").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    plans = raw.get("plans") if isinstance(raw.get("plans"), list) else []
    return {"plans": [r for r in plans if isinstance(r, dict)]}


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


def _is_tallinn(row: dict) -> bool:
    """True when the row's kov is a recognised Tallinn spelling."""
    kov = row.get("kov")
    if not isinstance(kov, str):
        return False
    return kov.strip().lower() in TALLINN_KOVS


def plans_to_pois(plans: List[dict]) -> List[dict]:
    """Plan rows -> scorer POIs. Non-Tallinn and coord-less rows stay out.

    The Tallinn filter is the parameters4.md P4-006 "Tallinn filter": a
    national-register row without a recognised Tallinn kov never joins a
    Tallinn parcel buffer (unknown municipality is never assumed local).
    """
    pois = []
    for row in plans:
        if not isinstance(row, dict) or not _is_tallinn(row):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        stage = row.get("stage")
        pois.append({
            "kind": "plan_plank",
            "lat": lat, "lon": lon,
            "plan_id": str(row.get("plan_id") or "tundmatu"),
            "stage": str(stage).strip().lower() if stage is not None else None,
            "kov": str(row.get("kov")).strip(),
        })
    return pois


def snapshot_to_pois(snapshot: Optional[dict]) -> List[dict]:
    """Parsed snapshot (or None) -> scorer POIs for the PLANK leg. Pure."""
    if not isinstance(snapshot, dict):
        return []
    plans = snapshot.get("plans")
    if isinstance(plans, list):
        return plans_to_pois(plans)
    return []


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

#: menetluses-plan count in 500 m -> pipeline score (high = clear).
#: First-cut bands, MUST be recalibrated from a real snapshot on reopen.
PIPELINE_BANDS = [(0, 90), (1, 65), (3, 40), (float("inf"), 20)]


# ---------------------------------------------------------------------------
# P4-006: neighbouring detailplaneering pipeline, PLANK leg, 500 m (demo).
# ---------------------------------------------------------------------------

def dim_pipeline_plank_500m(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-006: PLANK menetluses-plan pipeline count in 500 m (high = clear).

    Per-parcel buffer join over the PLANK national snapshot with the
    Tallinn filter: counts neighbouring detailplaneeringud in stage
    "menetluses" within 500 m. Zero counts score 90 ONLY when the
    snapshot holds Tallinn plans elsewhere (measured clear); a snapshot
    with no Tallinn plan POIs at all stays NULL.
    """
    if not origin or pois is None:
        return None, ("Torustiku info puudub (EI OLE PLANK-hetktõmmist: "
                      "WFS-liidest pole, register on veebivaade)")
    if not _has_kind(pois, "plan_plank"):
        return None, ("Torustiku info puudub (EI OLE Tallinna "
                      "PLANK-hetktõmmist hetkel: tühi tõmmis ei ole puhas "
                      "otsus)")
    hits = _near(origin, pois, "plan_plank", PIPELINE_WINDOW_M)
    pipe = [(d, p) for d, p in hits if p.get("stage") == PIPELINE_STAGE]
    n = len(pipe)
    s = _band(n, PIPELINE_BANDS)
    assert s is not None
    if n == 0:
        near_txt = ("lähim Tallinna plaan %s" % _fmt_m(hits[0][0])) if hits else \
            "500 m raadiuses Tallinna plaane pole"
        return s, ("PLANK torustik (hinnang): 500 m raadiuses menetluses "
                   "Tallinna plaane 0 (%s) → skoor %d"
                   % (near_txt, s))
    d0, p0 = pipe[0]
    return s, ("PLANK torustik (hinnang): 500 m raadiuses menetluses "
               "Tallinna plaane %d (lähim %s %s) → skoor %d"
               % (n, p0.get("plan_id"), _fmt_m(d0), s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_PLANK_DIMS = (
    ("pipeline_plank_500m", "P4-006", dim_pipeline_plank_500m),
)


def score_p4_plank(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All P4 PLANK dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_PLANK_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_PLANK_DIMS}
