"""Soil/garden suitability scorer (issue #535): Maa-amet mullastiku kaart WFS.

Overturns docs/nomap.md section G3 ("p68 soil — no soil DB"): this WFS IS
the soil DB whose absence was verified. Source:
* INSPIRE SO WFS ``https://inspire.geoportaal.ee/geoserver/SO_pinnas/wfs``
  (``?service=WFS&version=2.0.0&request=GetCapabilities``), 1:10 000 soil
  contours with codes (šifrid). Publisher: Land and Spatial
  Administration. Licence CC_BY_4.0 (attributed here + in the legend).
* Memoir: ``geoportaal.maaamet.ee/docs/muld/mullakaardi_seletuskiri.pdf``
  (Vabariigi digitaalse suuremõõtkavalise mullastiku kaardi seletuskiri,
  Tallinn 2001, 46 pdf pages).
* Update: IRREG. Coverage: almost all Estonia EXCEPT cities, water
  bodies and soil-less islets (publisher caveat — measured below).

Polite probe (2026-09-16, custom UA, one GET each, no 429 seen):
* GetCapabilities: HTTP 200 application/xml, 106411 B.
* Feature type: ``SO_pinnas:SO.SoilBody``, title "Eesti mullastiku
  kaart", DefaultCRS EPSG:3301 (L-EST97).
* DescribeFeatureType attributes: inspireId localId/namespace,
  ``soilBodyLabel`` (the soil-code šifr), beginLifespanVersion,
  isDescribedBy (nil), geom. There are NO texture/humus/stoniness
  COLUMNS in the WFS — texture is decoded from the šifr via the memoir
  legend (lisa 3), never read as a column. The offline harvest step
  writes the decoded ``family`` onto each POI; this scorer never parses
  raw šifrid (parsing them here would fake legend knowledge).
* Hits (resultType=hits, lat,lon bboxes): Harjumaa window
  (58.9,23.5,60.0,25.6) numberMatched="86474" — dense rural coverage,
  discriminating. Tallinn bbox (59.35,24.55,59.50,24.95)
  numberMatched="2226" — NONZERO: fringe polygons spill into the bbox,
  so "the map is EMPTY in Tallinn" is true at the Kesklinn-parcel level
  but false as a bbox claim. Stated as measured: the NULL-in-cities
  rule below is a conservative design choice (city soil is disturbed
  fill; 1:10 000 precision breaks at parcel edges), NOT a "no polygons"
  claim. (Raw files: /tmp working copies only, never committed.)

Class -> band mapping (reviewer-readable, transcribed from the memoir):
seletuskiri §V Tabel 1 "Muldade klassifikatsioon mehaanilise koostise
järgi" (pdf lk 9, Kačinski classification by physical clay < 0.01 mm):
liivad l (0-10% savi), saviliivad sl (10-20%), liivsavid ls1/ls2
(20-40%), savid s (40-85%+); turvas/glei/paepealsed/rähksed per the
mapping-unit diagnostics (lisa 1) and legend (lisa 3, pdf lk 46).
Suitability bands are the author's STATED mapping (hinnang — foundation
+ garden judgment for detached-house/garden-plot buyers outside the
city: Viimsi, Harku, Saku, Kiili), not the memoir's verdict:
* saviliiv sl -> 85 (balanced: drains yet holds water, kindel alus)
* liiv l/pl/tl -> 70 (free-draining, droughty garden, vajumis-kindel)
* liivsavi ls -> 65 (workable, drainage care at parcel edges)
* leede L -> 55 (acidic forest sand, lubjamist vajav)
* paepealne/rähkne Kh/Kr -> 50 (thin on limestone, foundation cost)
* savi s -> 40 (shrink-swell, poor drainage — kuivendus vajalik)
* glei G -> 30 (waterlogged — kuivenduseta ei sobi)
* turvas T -> 25 (compressible, settlement risk — vaiad/süvendi vajadus)
Unknown/absent family stays NULL (never guessed). No agronomic-yield
claims (suitability hinnang only, per the issue constraints).

HONESTY (AGENTS.md section 7.2): per-parcel join scorer, never a
walk-graph raster (rural-parcel phenomenon; OTA PR #131). NULL inside
cities/water (honestly unknown, never zero) + EI OLE + mullakaardi
check. 1:10 000 scale caveat in the legend (parcel-edge precision
limits). Transport errors are never cached as data. IRREG feed ->
annual re-probe, no live calls in the scoring path.

Style mirrors services/scoring/dims_group07d.py (#143): pure
(origin, pois) -> (Optional[int 0..100], Estonian reason), absolute
scales, hermetic fixture tests. Local helpers (no livability import —
same cycle precedent as PRs #100/#106/#115). No Overpass fragment:
positions arrive via the WFS join, not snapshot tags — stated, not
omitted.

Integration (deliberately NOT done here): projecting EPSG:3301 -> WGS84
(L-EST97 metres, same caveat as dims_p4_trans), splicing POI kind
``soil_parcel`` into livability, and rebalancing livability.WEIGHTS must
be one joint change across all batches. No shared files touched:
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

#: GetCapabilities URL (verified 2026-09-16: HTTP 200 XML, 106411 B).
WFS_CAPABILITIES_URL = (
    "https://inspire.geoportaal.ee/geoserver/SO_pinnas/wfs"
    "?service=WFS&version=2.0.0&request=GetCapabilities"
)

#: Harvest feature type (verified 2026-09-16, DefaultCRS EPSG:3301).
WFS_TYPE_NAME = "SO_pinnas:SO.SoilBody"

#: Measured 2026-09-16 via resultType=hits: Harjumaa window (lat,lon
#: 58.9,23.5,60.0,25.6) 86474 polygons; Tallinn bbox
#: (59.35,24.55,59.50,24.95) 2226 intersecting fringe polygons.
HARJUMAA_WINDOW_HITS = 86474
TALLINN_BBOX_HITS = 2226

#: Memoir citation for the class table (single polite PDF GET 2026-09-16:
#: HTTP 200 application/pdf, 843914 B, 46 pages).
MEMOIR_CITE = ("Maa-amet, mullakaardi seletuskiri (Tallinn 2001), "
               "§V Tabel 1 (pdf lk 9); legend lisa 3 (pdf lk 46)")

#: IRREG feed: at most one re-probe per year per cache dir.
WFS_TTL_S = 365 * 24 * 3600

#: Identifying user agent for the polite pull (single GET, no scrape).
SOIL_UA = "home-finder soil-map probe (annual WFS max, no scrape)"

#: Minimum plausible WFS body: the capabilities doc alone is ~106 KB.
WFS_MIN_BYTES = 4096


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = WFS_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with SOIL_UA and a 30 s timeout; the body is stored only on
    HTTP 200 with at least WFS_MIN_BYTES bytes, else None is returned
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
        req = urllib.request.Request(url, headers={"User-Agent": SOIL_UA})
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
# Class -> band mapping (stated suitability hinnang, memoir-calibrated).
# ---------------------------------------------------------------------------

#: Harvest-decoded soil family -> suitability score (high = better
#: foundation/garden ground). Families are written by the offline harvest
#: step from the soilBodyLabel šifr via the memoir legend — the scorer
#: never parses raw codes. See the module docstring for the memoir
#: citation and the per-family judgment.
SOIL_BANDS = {
    "saviliiv": 85,
    "liiv": 70,
    "liivsavi": 65,
    "leede": 55,
    "paepealne": 50,
    "savi": 40,
    "glei": 30,
    "turvas": 25,
}

#: Per-parcel join window: the nearest soil_parcel within 300 m carries
#: the parcel's ground. Beyond it stays NULL (unknown, never zero).
SOIL_WINDOW_M = 300.0


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


def _family(poi: dict) -> Optional[str]:
    """Harvest-decoded soil family: exact table match only, else None."""
    v = poi.get("family")
    return v if isinstance(v, str) and v in SOIL_BANDS else None


def dim_soil_suitability(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """Soil foundation/garden suitability (high = kinder ground).

    Per-parcel join over the mullakaardi WFS (projected positions): the
    nearest ``soil_parcel`` within 300 m carries its harvest-decoded
    ``family`` (raw ``code`` named in the reason). Urban-flagged joins
    (city mask applied offline at harvest) and missing/unknown families
    stay NULL with an EI OLE reason + mullakaardi check — a Kesklinn
    parcel scores None, never 0. Beyond the window stays NULL (unknown,
    never zero). Every scored reason says "hinnang" (1:10 000 scale,
    parcel-edge precision limits).
    """
    if not origin or pois is None:
        return None, ("Mullastiku info puudub (EI OLE mullakaardi "
                      "liidestust hetktõmmes: SO WFS pole liidestatud)")
    hit = _nearest(origin, "soil_parcel", pois)
    if hit is None or hit[0] > SOIL_WINDOW_M:
        return None, ("Läheduses pole mullakontuuri liidestust - hinnangut "
                      "pole (EI OLE liidestatud mullakaarti, mitte null-muld; "
                      "kontrolli mullakaardilt)")
    dist_m, poi = hit
    if poi.get("urban") is True:
        return None, ("Asum on linnas / tehispinnasel - mullakaart siin ei "
                      "kehti (EI OLE hinnangut: linnamuld on täitepinnas; "
                      "kontrolli kohapeal)")
    fam = _family(poi)
    if fam is None:
        return None, ("Mullakontuur %s, aga mullaperet pole dekodeeritud - "
                      "sobivust ei saa lugeda (EI OLE legendiliidestust)"
                      % _fmt_m(dist_m))
    s = SOIL_BANDS[fam]
    code = poi.get("code")
    tail = (" (šifr %s)" % str(code).strip()[:24]) if code else ""
    return s, ("Mulla sobivuse hinnang: %s%s, lähim kontuur %s -> skoor %d "
               "(hinnang, 1:10 000; servatäpsus piiratud)"
               % (fam, tail, _fmt_m(dist_m), s))


#: Dim key owned by this module (G3 cadastre family; the future central
#: hook owns parameters3 numbering).
SOIL_DIM = "soil_suitability"
