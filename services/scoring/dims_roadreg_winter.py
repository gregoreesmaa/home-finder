"""Measured winter-maintenance + road-attribute layer (issue #536).

The P4-018 "first pull": docs/p4_trans.md scores ``winter_road_class``
off a FIXTURE codelist ("remap on first pull") — no live source was ever
joined. This module is the first-pull candidate off the Eesti teeregister
WFS (Transport Authority, CC_BY_4.0, DAILY feed).

Polite probe (2026-09-16, custom UA, one GET each, no 429 seen):
* Public WFS GetCapabilities ->
  ``https://teeregister.mnt.ee/290424/wfs?service=WFS&version=2.0.0``
  ``&request=GetCapabilities``: HTTP 200 text/xml, 80339 B, **60 feature
  types**, all DefaultCRS EPSG:3301 (L-EST97). Road classes as separate
  types (ms:Pohimaantee/Tugimaantee/Korvalmaantee/Ramp/Muutee/...),
  segments as ms:teeosa (Teeosad), plus attribute layers.
* Winter leg CONFIRMED present: ``ms:n_seisund_talvine`` (Talvine
  seisunditase). DescribeFeatureType attributes: msGeometry,
  tee_number/tee_nimi, soidutee_nr, alguskm/loppkm, pikkus,
  algteeosa/loppteeosa (+meetrid), ``hoolklt_hoolklt_xv`` (winter
  maintenance class CODE), ``hoolklt_hoolklt_val`` (its VALUE/label),
  oid/tee_oid/teeosa_oid, alusnahtus_oid, muudetud_kpv. hooldusklass IS
  carried — no pivot to "attribute cross-check" needed (the issue's
  fallback is documented but not taken).
* Harjumaa-window hits (GetFeature resultType=hits, NATIVE EPSG:3301
  bbox 430000,6575000,600000,6630000 — WGS84 bboxes returned 0 because
  this WFS does not reproject the filter; stated, not hidden):
  ``ms:n_seisund_talvine`` numberOfFeatures="568" winter-level
  segments. (Raw files: /tmp working copies only, never committed.)
* INSPIRE WFS (``TN_teeregister``) confirmed reachable too (HTTP 200,
  116572 B, RoadLink/Road/RoadSurfaceCategory/Roadwidth/NumberOfLanes)
  but NOT harvested: the public WFS winter level is the direct P4-018
  join; the INSPIRE leg stays a named alternative.
* Tark Tee DATEX legs explicitly NOT re-probed here (registered key
  needed — dims_p4_trans dated negative stands); accident CSV owned by
  #522. This module is the *register* leg only.

Measured join (bands UNCHANGED unless evidence demands it — reviewer
call; the P4-018 fixture shape klass 1→85 … 4→30 is kept):
* ``dim_winter_road_class_measured`` reads POI kind
  ``roadwinter_p4`` (DISTINCT from dims_p4_trans ``roadclass_p4``
  fixture kind — the two never cross-score, pinned by test) within
  150 m, carrying the harvest-normalised ``maint_class``.
* Provisional remap (``remap_maintenance_class``): raw
  ``hoolklt_hoolklt_xv`` values are UNSEEN (attr names confirmed,
  value census waits on the first full pull), so only the documented
  fixture positions "1".."4" map — anything else stays NULL with an
  EI OLE remap reason (fail closed, never a default class). The
  row-for-row audit table lives in docs/roadreg_winter.md.
* Road attributes as scorer-side cross-checks: ``audit_surface_against``
  compares the register surface (``ms:n_kate`` Katted family) against
  the OSM proxy surface and returns match/mismatch/unknown with an
  Estonian note — an audit, never a score. No traffic-volume claims
  (counters are DATEX-gated), no winter-service quality scoring
  (class != ploughing punctuality — the legend must say so).

HONESTY (AGENTS.md section 7.2): NULL where no segment joins (never a
default class); reasons in Estonian with hinnang/EI OLE markers
(measured join vs. proxy). Transport errors are never cached as data.
DAILY feed → harvest at most weekly/monthly (roads change slowly;
polite automation per AGENTS.md §7). No live calls in the scoring path.

Style mirrors services/scoring/dims_p4_trans.py (#275/#349): pure
(origin, pois) -> (Optional[int 0..100], Estonian reason), local helpers
(no livability import — same cycle precedent as PRs #100/#106/#115).

Integration (deliberately NOT done here): projecting EPSG:3301 -> WGS84,
splicing POI kinds into livability, and rebalancing livability.WEIGHTS
must be one joint change across all batches. No shared files touched:
3 new files only.
"""

import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Harvest contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Public WFS GetCapabilities (verified 2026-09-16: HTTP 200, 80339 B,
#: 60 feature types, all EPSG:3301).
WFS_CAPABILITIES_URL = (
    "https://teeregister.mnt.ee/290424/wfs"
    "?service=WFS&version=2.0.0&request=GetCapabilities"
)

#: INSPIRE alternative (verified 2026-09-16: HTTP 200, 116572 B) — named
#: alternative only, NOT the harvest target (see docstring).
WFS_INSPIRE_URL = (
    "https://inspire.geoportaal.ee/geoserver/TN_teeregister/wfs"
    "?service=WFS&version=2.0.0&request=GetCapabilities"
)

#: Winter-level feature type (Talvine seisunditase, verified 2026-09-16).
WFS_WINTER_TYPE = "ms:n_seisund_talvine"

#: Winter-class code + value attributes (verified via DescribeFeatureType
#: 2026-09-16; VALUE CENSUS still pending first full pull).
WFS_WINTER_CODE_ATTR = "hoolklt_hoolklt_xv"
WFS_WINTER_VALUE_ATTR = "hoolklt_hoolklt_val"

#: Measured 2026-09-16 via resultType=hits on the native EPSG:3301
#: Harjumaa bbox (430000,6575000,600000,6630000): 568 winter segments.
HARJUMAA_WINTER_HITS = 568

#: DAILY portal feed, but roads change slowly: harvest at most weekly
#: (polite automation; the issue caps it at weekly/monthly).
WFS_TTL_S = 7 * 24 * 3600

#: Identifying user agent for the polite pull (single GET, no scrape).
ROADREG_UA = "home-finder roadreg probe (weekly WFS max, no scrape)"

#: Minimum plausible WFS body: the capabilities doc alone is ~80 KB.
WFS_MIN_BYTES = 4096


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = WFS_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with ROADREG_UA and a 30 s timeout; the body is stored only
    on HTTP 200 with at least WFS_MIN_BYTES bytes, else None is returned
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
        req = urllib.request.Request(url, headers={"User-Agent": ROADREG_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < WFS_MIN_BYTES:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


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


#: P4-018 join window (same street-level window as the fixture dim).
WINTER_WINDOW_M = 150.0

#: P4-018 band shape (UNCHANGED from the fixture dim — reviewer call per
#: the issue; high = better winter maintenance).
WINTER_BANDS = {"1": 85, "2": 65, "3": 45, "4": 30}


def remap_maintenance_class(raw: object) -> Optional[str]:
    """Provisional hooldusklass remap: documented positions only.

    The WFS code attribute (``hoolklt_hoolklt_xv``) value census waits on
    the first full pull, so only the fixture-documented positions
    "1".."4" map for now — anything else returns None (fail closed: the
    scorer stays NULL with an EI OLE remap reason instead of guessing).
    Whitespace-tolerant; bool/int inputs are NOT coerced (an int 1 is a
    type error at harvest, never silently a class).
    """
    if isinstance(raw, bool):
        return None
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    return s if s in WINTER_BANDS else None


def dim_winter_road_class_measured(origin: Optional[Tuple[float, float]],
                                   pois: Optional[List[dict]]) -> Score:
    """P4-018 measured join (high = better plowed street).

    Nearest ``roadwinter_p4`` POI (teeregister Talvine seisunditase join,
    projected positions) within 150 m carries the harvest-normalised
    ``maint_class``. Bands match the fixture dim exactly (1→85, 2→65,
    3→45, 4→30); unknown classes stay NULL with an EI OLE remap reason.
    No segment join stays NULL (never a default class). Fixture-kind
    ``roadclass_p4`` POIs never match here (and vice versa) — the old
    and new codelists audit against each other, never mix.
    """
    if not origin or pois is None:
        return None, ("Talvise hooldusklassi info puudub (EI OLE "
                      "teeregistri talvise seisunditaseme liidestust "
                      "hetktõmmes)")
    hit = _nearest(origin, "roadwinter_p4", pois)
    if hit is None or hit[0] > WINTER_WINDOW_M:
        return None, ("Läheduses pole teeregistri talvise taseme lõiku - "
                      "hinnangut pole (EI OLE liidestatud teeregistrit, "
                      "mitte mõõdetud hooldamata tee)")
    dist_m, poi = hit
    cls = remap_maintenance_class(poi.get("maint_class"))
    if cls is None:
        return None, ("Teeregistri lõik %s, aga hooldusklass puudub või "
                      "pole kaardistatud (EI OLE klassi ümberpaigutust "
                      "esmasest väljavõttest)" % _fmt_m(dist_m))
    return WINTER_BANDS[cls], ("Talvise hoolduse mõõdetud hinnang "
                               "(teeregister): lõik %s, hooldusklass %s "
                               "-> skoor %d"
                               % (_fmt_m(dist_m), cls, WINTER_BANDS[cls]))


# ---------------------------------------------------------------------------
# Road-attribute cross-check (audit, never a score).
# ---------------------------------------------------------------------------

def audit_surface_against(register_surface: object,
                          osm_surface: object) -> Tuple[str, str]:
    """Register-vs-OSM surface honesty audit (match/mismatch/unknown).

    Compares the teeregister ``n_kate`` (Katted) surface against the OSM
    road-class proxy surface for the same street. Returns (verdict,
    Estonian note): "match" (proxy honest), "mismatch" (proxy needs a
    revisit — the register wins), "unknown" (either side missing — never
    a verdict). Pure; no scoring, no traffic-volume claims.
    """
    def _norm(v: object) -> Optional[str]:
        if not isinstance(v, str) or isinstance(v, bool):
            return None
        s = v.strip().lower()
        return s or None

    reg = _norm(register_surface)
    osm = _norm(osm_surface)
    if reg is None or osm is None:
        return ("unknown",
                "Katte võrdlus EI OLE võimalik: register=%s, OSM=%s "
                "(puuduv pool, mitte hinnang)"
                % (reg or "puudub", osm or "puudub"))
    if reg == osm:
        return ("match",
                "Kate klapib (register=%s, OSM=%s): proksi aus" % (reg, osm))
    return ("mismatch",
            "Kate ei klapi (register=%s, OSM=%s): OSM proksi vajab "
            "ülevaatust, register jääb peale" % (reg, osm))


#: Dim key owned by this module (P4-018 measured leg; the fixture slice
#: key ``winter_road_class`` stays owned by dims_p4_trans).
ROADREG_WINTER_DIM = "winter_road_class_measured"
