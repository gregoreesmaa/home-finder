"""Overturn #239 (G8 KAUR/EFAS flood polygons): per-parcel flood-zone join.

Scope (issue #239): parameters3.md section 5.8 Group 8 no-map set
(p46/p112/p117, p118/p182, p371/p372, p377/p378/p429; p69/p255/p333/
p334/p336/p447 already ship as proxies in dims_group08a-d and are
NOT repeated here). Honest output is a per-parcel flood-ZONE join
(choropleth: inside a named KAUR zone polygon vs outside/unknown),
never a walk-gradient; it must not re-skin p50 drainage or p334
surge-street proximity.

Verification (dated probes, 2026-09-13, polite: 8 tiny requests with
a labelled one-off User-Agent, paced >= 5 s, capabilities/storefront
scope only, no scraping, no auth attempts, no XHR probing; raw
bodies at /tmp/hf-239/ for the PR record, never committed):

* GET gsavalik.envir.ee/geoserver/eelis/wfs GetCapabilities ->
  HTTP 200, 186 232 B: exactly ONE flood layer in the 104-name
  list, eelis:kr_yleujutusohuga_ala ("KKR Üleujutusohuga ala").
  No T10/T50/T100/T1000 feature type exists on the open WFS.
* DescribeFeatureType -> schema: shape + sys_id + versioon + id +
  nimi + kr_kood + vveekogu/sveekogu + tyyp. NO return-period or
  hazard-band attribute: every row carries the single constant
  tyyp "Suurte üleujutusaladega siseveekogu".
* GetFeature resultType=hits -> numberMatched=16 nationally.
* GetFeature count=2 sample -> gml:Polygon geometry in EPSG:3301
  (L-EST97); rows name water-body objects ("Mullutu-Suurlaht kogu
  kalda ulatuses", "Suur-Emajõgi koos vanajõgedega kogu ulatuses").
* Tallinn-window BBOX hits (24.4,59.2,25.5,59.7 EPSG:4326) ->
  numberMatched=0: the open polygon register has ZERO Tallinn
  coverage.
* EFAS/GloFAS old hosts (efas.eu, globalfloods.eu) -> HTTP 301 to
  the CEMS-Floods React SPA shells (european-flood. / global-flood.
  emergency.copernicus.eu, 4034 B each, visible text only
  "CEMS-Floods React", JS-only): forecast grids and downloads live
  behind the registration-gated EFAS-IS app -- no anonymous
  per-parcel bulk verified at storefront level (polite stop).

What flipped vs stayed NULL (dated verdict 2026-09-13):

* p112 (flood history/elevation) gains the honest JOIN SHAPE:
  dim_floodzone_p112 scores FLOOD_ZONE_SCORE inside a named KAUR
  zone polygon (reason says "hinnang" and names the zone nimi +
  kr_kood) and stays NULL outside every joined polygon (EI OLE:
  the register carries no T-bands and zero Tallinn polygons --
  outside is unknown, never "dry"). Proven on fixtures only;
  production Tallinn joins are empty until a T-band polygon feed
  appears in-snapshot.
* p46/p117/p118/p182/p371/p372/p377/p378/p429 stay NULL with
  dated EI OLE reasons: a composite incident index needs a
  register/KOV table; sea-rise needs a DEM plus a projection
  curve; drought/frost need a soil survey; prevailing wind is a
  uniform regional SW flow (direction is not goodness, never a
  gradient); burn scars need EFFIS perimeters; buyouts need a
  payout register; intrusion needs a well-salinity series; creep
  needs a zone time series -- one single-version object register
  answers none of them.

Relationship to siblings (READ, not edited -- see issue):

* dims_p4_kaur.py (#285/#359) owns the parameters4 P4-015 flood-zone
  insurability leg (KAUR zone join on fixtures, `_kaur`-suffixed
  keys, `kaur_zone_p4` POIs). This module scores the parameters3
  G8 p112 zone join with distinct `_overturn_flood` keys and
  `flood_zone_overturn` POIs -- no shared helper, no shared band.
* dims_group08a-d (#167-#170) own the G8 proxies and their NULLs
  and are untouched; livability.py, WEIGHTS and docs/nomap.md are
  untouched too (existing tests pin set(WEIGHTS) exactly; the final
  docs-index PR owns nomap.md).

Style mirrors dims_overturn_p317.py (#240, the closest sibling:
same dated-verdict overturn shape): pure scorers (origin, pois) ->
(Optional[int 0..100], Estonian reason), local helpers (no sibling
imports -- a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle,
batch B3 / PR #100 precedent). Network lives ONLY in
fetch_flood_snapshot; tests never touch it with a remote URL.

Judgment calls (reviewable per AGENTS.md section 7.5):

* Constant inside-zone score (FLOOD_ZONE_SCORE = 25), no distance
  decay: membership in a named ministerial flood-object polygon is
  a choropleth fact, not a gradient -- depth inside the polygon
  changes nothing (pinned: two interior points score alike).
* Outside every polygon stays NULL, never "dry/clear": the layer
  is an object register (16 water bodies, zero Tallinn polygons),
  not a hazard model -- absence of a polygon is unknown, never
  good (OTA PR #131 precedent).
* Fetch defaults to the Tallinn-window BBOX (FLOOD_BBOX_TALLINN):
  the national pull is multi-MB (2 sample features = 712 kB), so
  the polite default pulls only the market window; the bbox is a
  parameter, not a hidden assumption. srsName EPSG:4326 is always
  requested so stored rings are lat/lon (WFS 2.0 axis order).
* Annual TTL (FLOOD_TTL_S = 365 d): parameters3.md section 5.8
  says "Annual flood hazard model sync"; zones move on planning
  cycles, not weekly (AGENTS.md section 7.4 convergence).
* EFAS stays a dated negative, not a fetch target: EFAS_URL /
  GLOFAS_URL are provenance constants (the verified new CEMS
  addresses), never requested by code.

Integration (deliberately NOT done here): wiring the snapshot into
a listing pipeline plus rebalancing livability.WEIGHTS must be one
joint change across all batches -- existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
"""

import os
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Hunt date (2026-09-13) -- the day the eight polite checks above ran.
VERDICT_DATE = "2026-09-13"

#: Re-check the WFS layer list (T-band polygons?) and the CEMS download
#: gating no later than this date (6-month cadence, #240 precedent).
RECHECK_AFTER = "2027-03-13"

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Verified open WFS base (2026-09-13: GetCapabilities HTTP 200).
WFS_BASE = "https://gsavalik.envir.ee/geoserver/eelis/wfs"

#: The single open flood polygon layer (object register, 16 features
#: nationally, zero Tallinn polygons -- see docstring).
FLOOD_LAYER = "eelis:kr_yleujutusohuga_ala"

#: EFAS / GloFAS new CEMS addresses (verified 301 targets 2026-09-13):
#: registration-gated SPA shells, kept as provenance constants -- NOT
#: fetch targets (dated negative on the EFAS bulk, see docstring).
EFAS_URL = "https://european-flood.emergency.copernicus.eu/"
GLOFAS_URL = "https://global-flood.emergency.copernicus.eu/"

#: Max one download per 365 d per cache dir (parameters3.md section 5.8:
#: "Annual flood hazard model sync"). Stated TTL.
FLOOD_TTL_S = 365 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "flood-snapshot.gml"

#: Default pull window: the Tallinn market bbox (lon_min,lat_min,
#: lon_max,lat_max, EPSG:4326). Keeps the polite pull small -- the
#: national layer is multi-MB. A parameter, not a hidden assumption.
FLOOD_BBOX_TALLINN = (24.4, 59.2, 25.5, 59.7)

#: Identifying user agent for the polite pull (no scrape, single GET).
FLOOD_UA = ("home-finder KAUR-EFAS flood-zone ingest (max 1 req/365d "
            "per cache dir, BBOX-filtered, no scrape)")

#: Inside a named KAUR flood-object polygon (first-cut judgment: named
#: ministerial flood objects flood seriously; MUST be recalibrated
#: once T-band polygons with return periods appear in-snapshot).
#: Never 0 and never 100: one object register never prices risk.
FLOOD_ZONE_SCORE = 25


def _getfeature_url(bbox: Optional[Tuple[float, float, float, float]]) -> str:
    """WFS GetFeature URL for the flood layer (EPSG:4326 rings)."""
    url = (WFS_BASE + "?service=WFS&version=2.0.0&request=GetFeature"
           "&typeName=" + FLOOD_LAYER
           + "&srsName=urn:ogc:def:crs:EPSG::4326")
    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        url += ("&bbox=%s,%s,%s,%s,urn:ogc:def:crs:EPSG::4326"
                % (lon_min, lat_min, lon_max, lat_max))
    return url


def fetch_flood_snapshot(
        cache_dir: str,
        bbox: Optional[Tuple[float, float, float, float]] = FLOOD_BBOX_TALLINN,
        ttl_s: int = FLOOD_TTL_S,
) -> Optional[str]:
    """Polite KAUR flood-polygon pull with a stated TTL. Returns path/None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise one GET of the BBOX-filtered GetFeature URL with FLOOD_UA
    and a 30 s timeout; the body is stored only on HTTP 200 with XML
    content, else None is returned and nothing is cached (transport
    errors are never data). No retries -- HTTP 429/errors are a stop
    signal (AGENTS.md section 7.4). Scorers never call this; tests
    cover the cache-hit and error paths with a stubbed opener, never
    the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    try:
        req = urllib.request.Request(_getfeature_url(bbox),
                                     headers={"User-Agent": FLOOD_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "xml" not in ctype:
                return None
            body = resp.read()
        try:
            ET.fromstring(body)
        except ET.ParseError:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached GML snapshot (pure; fixtures match).
# ---------------------------------------------------------------------------

_NS = {
    "eelis": "http://kemit.ee/eelis/avaandmed",
    "gml": "http://www.opengis.net/gml/3.2",
}

#: POI kind for joined flood-zone polygons (distinct from dims_p4_kaur's
#: `kaur_zone_p4` -- different pipeline, see docstring).
FLOOD_POI_KIND = "flood_zone_overturn"


def _parse_ring(pos_text: str) -> Optional[List[Tuple[float, float]]]:
    """posList (WFS 2.0 EPSG:4326 axis order: lat lon) -> ring or None."""
    try:
        nums = [float(t) for t in pos_text.split()]
    except ValueError:
        return None
    if len(nums) < 8 or len(nums) % 2:
        return None
    ring = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    if any(not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0)
           for la, lo in ring):
        return None
    return ring


def parse_flood_snapshot(path: str) -> Optional[List[dict]]:
    """Read a cached flood GML snapshot into zone records. Offline.

    Returns [{zone_id, nimi, veekogu, tyyp, poly}] with malformed rows
    skipped (never faked), or None when the file is missing/unparseable
    (unknown, never an empty zone list -- scorers must not read "no
    file" as "no flood zones").
    """
    try:
        with open(path, "rb") as fh:
            root = ET.fromstring(fh.read())
    except (OSError, ET.ParseError):
        return None
    zones = []
    for feat in root.findall("eelis:" + FLOOD_LAYER.split(":")[1], _NS):
        def _text(tag: str) -> Optional[str]:
            el = feat.find("eelis:" + tag, _NS)
            if el is None or el.text is None:
                return None
            s = el.text.strip()
            return s if s else None
        pos = feat.find("eelis:shape/gml:Polygon/gml:exterior/"
                        "gml:LinearRing/gml:posList", _NS)
        if pos is None or pos.text is None:
            continue
        ring = _parse_ring(pos.text)
        if ring is None:
            continue
        sys_id = _text("sys_id")
        kr_kood = _text("kr_kood")
        veekogu = _text("vveekogu") or _text("sveekogu")
        zones.append({
            "zone_id": kr_kood or (("sys:%s" % sys_id) if sys_id else None)
            or "tundmatu",
            "nimi": _text("nimi") or "tundmatu",
            "veekogu": veekogu or "tundmatu",
            "tyyp": _text("tyyp") or "tundmatu",
            "poly": ring,
        })
    return zones


def zones_to_pois(zones: Optional[List[dict]]) -> List[dict]:
    """Zone records -> scorer POIs. None (unknown file) -> [] (no join)."""
    pois = []
    for row in zones or []:
        if not isinstance(row, dict):
            continue
        poly = row.get("poly")
        if (not isinstance(poly, list) or len(poly) < 4
                or any(not (isinstance(pt, (list, tuple)) and len(pt) == 2)
                       for pt in poly)):
            continue
        pois.append({
            "kind": FLOOD_POI_KIND,
            "zone_id": str(row.get("zone_id") or "tundmatu"),
            "nimi": str(row.get("nimi") or "tundmatu"),
            "veekogu": str(row.get("veekogu") or "tundmatu"),
            "tyyp": str(row.get("tyyp") or "tundmatu"),
            "poly": [(float(la), float(lo)) for la, lo in poly],
        })
    return pois


# ---------------------------------------------------------------------------
# Local pure helpers (no sibling imports -- see docstring).
# ---------------------------------------------------------------------------

def _point_in_ring(lat: float, lon: float,
                   ring: List[Tuple[float, float]]) -> bool:
    """Ray casting over (lon=x, lat=y). Pure."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i][0], ring[i][1]
        yj, xj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            xhit = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < xhit:
                inside = not inside
        j = i
    return inside


def _joined_zone(origin: Tuple[float, float],
                 pois: List[dict]) -> Optional[dict]:
    """First well-formed flood-zone POI whose polygon holds origin."""
    try:
        lat = float(origin[0])
        lon = float(origin[1])
    except (TypeError, ValueError, IndexError):
        return None
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != FLOOD_POI_KIND:
            continue
        poly = p.get("poly")
        if not isinstance(poly, list) or len(poly) < 4:
            continue
        try:
            if _point_in_ring(lat, lon, [(float(a), float(b))
                                         for a, b in poly]):
                return p
        except (TypeError, ValueError):
            continue
    return None


# ---------------------------------------------------------------------------
# p112: per-parcel flood-ZONE join (choropleth, never a gradient).
# ---------------------------------------------------------------------------

def dim_floodzone_p112(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p112: NULL outside every joined polygon; zone score inside one."""
    if not origin or pois is None:
        return None, ("Üleujutustsooni liide puudub (EI OLE hinnangut): "
                      "KAUR üleujutusohuga-alade kihti pole liidetud -- "
                      "kontrolli krundi asukohta KAUR/EELIS kaardilt, "
                      "ära feigi kuiva hinnangut")
    hit = _joined_zone(origin, pois)
    if hit is None:
        return None, ("Üleujutustsooni kirjet EI OLE (hinnangut ei anta): "
                      "liidetud KAUR polügoonides (16 veekogu, Tallinnas "
                      "polügoone pole) krunt ei asu -- väljaspool on "
                      "teadmata, mitte kuiv; kontrolli KAUR/EELIS kaardilt")
    return (FLOOD_ZONE_SCORE,
            "Krunt KAUR üleujutusohuga alas (hinnang, tsooniliide, "
            "mitte drenaaži-/tänavaproksi): %s (%s) -- kontrolli "
            "kindlustatavust ja korruseplaani" % (hit["nimi"],
                                                  hit["zone_id"]))


# ---------------------------------------------------------------------------
# Dated-negative NULLs: one single-version object register answers none
# of these (OTA PR #131 precedent). Each reason names the missing input
# + buyer-side check; the verdict date lives in VERDICT_DATE above and
# the full probe log in docs/overturn_flood.md.
# ---------------------------------------------------------------------------

def dim_envrisk_p46(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p46: NULL -- composite incident index needs a register/KOV table."""
    _ = (origin, pois)
    return None, ("Keskkonnariskide koondindeks teadmata (EI OLE "
                  "hinnangut): üleujutusobjektide register ei ole "
                  "intsidendiregister -- küsi KOV keskkonnainfot")


def dim_searise_p117(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p117: NULL -- sea-rise needs a DEM plus a projection curve."""
    _ = (origin, pois)
    return None, ("Merepinna tõusu projektsioon teadmata (EI OLE "
                  "hinnangut): siseveekogude objektiregister ei kanna "
                  "DEM-i ega CMEMS/IPCC kõverat -- rannajoone kaugus "
                  "pole projektsioon")


def dim_drought_p118(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p118: NULL -- drought tolerance needs a soil survey."""
    _ = (origin, pois)
    return None, ("Põuakindlus teadmata (EI OLE hinnangut): "
                  "mullakaart/KOV mulla-uuring puudub -- "
                  "üleujutusregister mulla veemahutavust ei mõõda")


def dim_winddir_p182(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p182: NULL -- prevailing wind is uniform, direction is not goodness."""
    _ = (origin, pois)
    return None, ("Valitsev tuulesuund kaardil pole (EI OLE hinnangut): "
                  "Harjumaal ühtlane edelavool -- hoone orientatsiooni "
                  "kontrolli kohapeal")


def dim_burnscar_p371(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p371: NULL -- burn scars need fire perimeters."""
    _ = (origin, pois)
    return None, ("Põlengujärgne varingurisk teadmata (EI OLE "
                  "hinnangut): hetktõmmises pole EFFIS põlemisalasid "
                  "-- küsi päästeamet/Keskkonnaagentuur")


def dim_buyout_p372(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p372: NULL -- buyout history needs a payout register."""
    _ = (origin, pois)
    return None, ("Üleujutushüvitiste ajalugu teadmata (EI OLE "
                  "hinnangut): kindlustus/KOV väljamaksete registrit "
                  "pole -- kindlustuskontor pole ajalugu")


def dim_frost_p377(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p377: NULL -- frost-heave risk needs a geotechnical survey."""
    _ = (origin, pois)
    return None, ("Külmakergeoht teadmata (EI OLE hinnangut): "
                  "pinnase-uuring puudub -- telli geotehniline "
                  "inspektsioon")


def dim_saltwater_p378(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p378: NULL -- saltwater intrusion needs well-salinity data."""
    _ = (origin, pois)
    return None, ("Soolase vee sissetung teadmata (EI OLE hinnangut): "
                  "kaevuvee analüüs/KOV hüdrogeoloogia puudub")


def dim_floodcreep_p429(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p429: NULL -- zone creep needs a zone time series."""
    _ = (origin, pois)
    return None, ("Üleujutustsooni laienemine teadmata (EI OLE "
                  "hinnangut): kiht on ühe versiooni objektiregister, "
                  "tsoonide ajalugu puudub")


#: Registry for UI/API wiring on integration: (dim key, param id, fn).
OVERTURN_FLOOD_DIMS = (
    ("envrisk_overturn_flood", 46, dim_envrisk_p46),
    ("floodzone_overturn_flood", 112, dim_floodzone_p112),
    ("searise_overturn_flood", 117, dim_searise_p117),
    ("drought_overturn_flood", 118, dim_drought_p118),
    ("winddir_overturn_flood", 182, dim_winddir_p182),
    ("burnscar_overturn_flood", 371, dim_burnscar_p371),
    ("buyout_overturn_flood", 372, dim_buyout_p372),
    ("frost_overturn_flood", 377, dim_frost_p377),
    ("saltwater_overturn_flood", 378, dim_saltwater_p378),
    ("floodcreep_overturn_flood", 429, dim_floodcreep_p429),
)


def score_overturn_flood(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]
                         ) -> Dict[str, Optional[int]]:
    """All overturn-#239 dims at once (entry point for the
    weight-rebalance follow-up; keys match OVERTURN_FLOOD_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in OVERTURN_FLOOD_DIMS}
