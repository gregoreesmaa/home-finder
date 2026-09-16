"""Waste-treatment-site avoidance dim (issue #534): INSPIRE US jäätmekäitluskohad.

Source: INSPIRE (US) Eesti jäätmekäitluskohad WFS (Land and Spatial
Administration, CC0_1.0, IRREG updates, temporal coverage from 2020-10-12).
Portal: https://andmed.eesti.ee/datasets/inspire-(us)-eesti-jaatmekaitluskohad-(wfs)

Polite probe (2026-09-16, custom UA, one GET each, no 429 seen):
* GetCapabilities ->
  ``https://inspire.geoportaal.ee/geoserver/US_jaatmekaitlus/wfs``
  ``?service=WFS&version=2.0.0&request=GetCapabilities``:
  HTTP 200 application/xml, 108487 B. Title: "INSPIRE (US) - Eesti
  jäätmekäitluskohad (WFS)". Abstract: waste collection/treatment/
  processing/storage register (KKR / Keskkonnaregister feed).
* Feature type: ``US_jaatmekaitlus:US.EnvironmentalManagementFacility``,
  title "Eesti jäätmekäitluskohad", DefaultCRS EPSG:3301 (L-EST97).
* Harjumaa-window hits (GetFeature resultType=hits, lat,lon bbox
  58.9,23.5,60.0,25.6 urn:ogc:def:crs:EPSG::4326 — window slightly larger
  than Harjumaa proper): numberMatched="1301" treatment/disposal sites.
  (First attempt with lon,lat order returned 0 — WFS 2.0 uses lat,lon
  for EPSG:4326; the 1301 is the corrected retry. Raw files: /tmp working
  copies only, never committed.)
* DescribeFeatureType attributes (no flat site-type codelist — type and
  function arrive as INSPIRE codelist href+title pairs):
  inspireId localId/namespace, name, currentStatus (href/title), type
  (href/title), thematicId identifier/scheme, validFrom/validTo,
  function activity/input/output (href/title), additionalDescription, geom.
  Site-type slices below therefore read a harvest-normalised
  ``site_type`` label (scorer-only, echoed verbatim, never enumerated
  here — enumerating unseen codelist values would be fake precision).

Why buyer-relevant: living next to a waste-treatment/-transfer site means
odour, heavy-truck traffic and resale stigma (Pärnamäe, Pääsküla,
Suur-Sõjamäe surroundings). No layer prices this in today.

p54 DISTINCTION (load-bearing, pinned by test): p54 (layers_batch10c.ts)
maps waste COLLECTION points (~1531 neighbourhood containers, OSM
amenity=waste_disposal/recycling, POI kind ``wastepoint``) — a different
phenomenon and scale. This module scores treatment/disposal SITES only
(POI kind ``wastesite``); a ``wastepoint`` never scores here and a
``wastesite`` never scores there. Stated in code + legend + docs.

HONESTY (AGENTS.md section 7.2): site proximity is NOT measured odour —
every scored reason says "hinnang" and names the distance; beyond 2 km
stays NULL (never "no smell" — wind carries). Every NULL reason says
"EI OLE" plus the kohapealne vaatlus (tuul, lõhn) check. Transport
errors are never cached as data (fetch_cached stores only HTTP 200
bodies over a minimum size, else None). IRREG feed → annual re-probe,
no live calls in the scoring path.

Style mirrors services/scoring/dims_p4_trans.py (#275/#349): pure
(origin, pois) -> (Optional[int 0..100], Estonian reason), local helpers
(no livability import — importing it here would turn the future central
hook into a cycle, same precedent as PRs #100/#106/#115). No Overpass
fragment is staged: positions arrive via the WFS join, not via snapshot
tags, so there is nothing honest for the live path to fetch — stated,
not omitted by accident.

Integration (deliberately NOT done here): projecting EPSG:3301 -> WGS84,
splicing POI kind ``wastesite`` into livability, and rebalancing
livability.WEIGHTS must be one joint change across all batches —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits
would break every sibling. No shared files touched: 3 new files only.
Legend + attribution: CC0 still attributed (see docs/waste_sites.md).
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

#: GetCapabilities URL (verified 2026-09-16: HTTP 200 XML, 108487 B).
WFS_CAPABILITIES_URL = (
    "https://inspire.geoportaal.ee/geoserver/US_jaatmekaitlus/wfs"
    "?service=WFS&version=2.0.0&request=GetCapabilities"
)

#: Harvest feature type (verified 2026-09-16, DefaultCRS EPSG:3301).
WFS_TYPE_NAME = "US_jaatmekaitlus:US.EnvironmentalManagementFacility"

#: Measured 2026-09-16 via resultType=hits on the Harjumaa window
#: (lat,lon 58.9,23.5,60.0,25.6): 1301 sites. Window slightly larger
#: than Harjumaa proper — stated, not rounded into a false exactness.
HARJUMAA_WINDOW_HITS = 1301

#: IRREG feed: at most one re-probe per year per cache dir (annual
#: re-probe per the issue constraints; harvest itself is offline-first).
WFS_TTL_S = 365 * 24 * 3600

#: Identifying user agent for the polite pull (single GET, no scrape).
WASTE_UA = "home-finder waste-sites probe (annual WFS max, no scrape)"

#: Minimum plausible WFS body: the capabilities doc alone is ~108 KB, so
#: anything smaller on the capabilities URL is an error page, never data.
WFS_MIN_BYTES = 4096


def fetch_cached(url: str, cache_dir: str, filename: str,
                 ttl_s: int = WFS_TTL_S) -> Optional[str]:
    """Polite single-GET pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise
    one GET with WASTE_UA and a 30 s timeout; the body is stored only on
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
        req = urllib.request.Request(url, headers={"User-Agent": WASTE_UA})
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


def _nearest(origin: Tuple[float, float], kind: str,
             pois: List[dict]) -> Optional[Tuple[float, dict]]:
    """(distance_m, poi) of the nearest well-formed POI of kind, else None.

    Only the exact kind matches: p54 collection points (``wastepoint``)
    never satisfy a ``wastesite`` query — the p54 distinction.
    """
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


#: Nearest treatment/disposal site within this window scores; beyond it
#: stays NULL (unknown, never "no smell").
WASTE_WINDOW_M = 2000.0

#: Distance -> avoidance score (high = farther = better). Site proximity
#: is an avoidance proxy (hinnang), never measured odour.
WASTE_BANDS = [(500.0, 35), (1000.0, 55), (2000.0, 70)]


def _site_type(poi: dict) -> Optional[str]:
    """Harvest-normalised site-type label, echoed verbatim when sane."""
    v = poi.get("site_type")
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    return s[:80]


def dim_waste_site(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """Waste-site avoidance proxy (high = farther from treatment sites).

    Nearest ``wastesite`` POI (INSPIRE US jäätmekäitluskohad join,
    projected WFS positions): <=500 m -> 35, <=1 km -> 55, <=2 km -> 70.
    Beyond 2 km (or no join) stays NULL with an EI OLE reason plus the
    kohapealne vaatlus (tuul, lõhn) check — never "no smell". A known
    harvest ``site_type`` label is named in the reason (scorer-only
    slice); unknown type still scores off distance alone. p54
    ``wastepoint`` collection points never match this kind.
    """
    if not origin or pois is None:
        return None, ("Jäätmekäituskoha info puudub (EI OLE INSPIRE US "
                      "jäätmekäitluskohad-liidestust hetktõmmes: WFS pole "
                      "liidestatud)")
    hit = _nearest(origin, "wastesite", pois)
    if hit is None or hit[0] > WASTE_WINDOW_M:
        return None, ("Lähim jäätmekäitluskoht üle ~2 km või liidestamata - "
                      "see pole lõhna-hinnang (EI OLE: kaugus pole mõõdetud "
                      "lõhn; kontrolli kohapealsel vaatlusel tuul ja lõhn)")
    dist_m, poi = hit
    s = _band(dist_m, WASTE_BANDS)
    assert s is not None
    st = _site_type(poi)
    tail = ("; käitluskoha liik: %s" % st) if st else ""
    return s, ("Jäätmekäituskoha läheduse hinnang: lähim käitluskoht %s%s "
               "-> skoor %d (hinnang, mitte mõõdetud lõhn)"
               % (_fmt_m(dist_m), tail, s))


#: Dim key owned by this module (new buyer signal outside the 500-param
#: registry — the future central hook owns parameters3 numbering).
WASTE_SITES_DIM = "waste_site"
