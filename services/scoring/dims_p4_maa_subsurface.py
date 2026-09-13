"""P4 Maa-amet subsurface dims: demo (#248) + coverage (#332).

Demo param (this ingestion's anchor):
* P4-016 EGT engineering geology (turvas/karst/alvar) -> dim_engineering_geology

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-017 Drinking-water quality + sewer reality -> dim_water_sewer
* P4-054 Quarry blast + truck season (paekivi near Maardu/Harku)
  -> dim_quarry_buffer

OPENNESS VERDICT (probed 2026-09-13, single polite fetches, cached
/tmp/hf-p4-maa-subsurface/ — full evidence in docs/p4_maa_subsurface.md):
* EGT ruumiandmed page: HTTP 200 — geology spatial data offered "teenuste
  ja allalaaditavate failidena" under a data licence with a scale-class
  caveat (respect the source map scale). Supports the coarse-only shape.
* EGT geoportaal Avamus: HTTP 200 ("Avamus - EGT Geoportaal") — open viewer.
* Maa-amet X-GIS2 maardlate viewer: HTTP 200 ("X-GIS 2.0 [maardlad]").
* Keskkonnaagentuur WFS (gsavalik.envir.ee/geoserver/wfs, the endpoint
  parameters3.md names): GetCapabilities HTTP 200, 1 345 735 B, 1091 named
  layers — incl. maaamet:geol_hydrogeoloogia_allikadkarstivormid_karstivali
  (karst), etak:e_307_turbavali_a (peat), maaamet:geol_hydrogeoloogia_
  pohjaveekaitstus_pvkhinnang (groundwater protection),
  maaamet:geol_puurkaevud_wfs (wells), maaamet:maavarad_gbmv_levialad /
  leiukohad / perspektiivalad (deposits). DescribeFeatureType HTTP 200 for
  karstivali and levialad (open schemas, no auth).
* Maavarade register: state database (EGT since 2025); public viewing via
  the Maa-amet deposit map app; submission web-interface needs user rights,
  X-tee service needs legal-entity membership. Blast timetables
  (Keskkonnaamet load schedules) are NOT an open feed — named EI OLE.
* Tallinna Vesi liitumine page: HTTP 200 — per-parcel connection reality is
  a manual iseteenindus technical-conditions request (2 weeks), not an open
  per-parcel feed. Missing connection facts stay NULL with the check named.
* Terviseamet joogivesi page: HTTP 200 — central water "hästi kontrollitud"
  (~85% of residents), private wells "ametlikke andmeid ei ole"; a public
  quality database exists. Quality leg: central monitored, private unknown.

HONESTY (AGENTS.md section 7.2): the only scored shapes here are
per-parcel CLASS JOINS (point-in-polygon over cached WFS polygons), coarse
only — never a distance gradient, never interpolation, never a
heat-coloured guess. Missing join data stays NULL ("EI OLE ...") with an
Estonian reason naming the concrete check (EGT geoportaal/WFS layer,
Tallinna Vesi technical conditions, Terviseamet database) — never a faked
number. Transport errors in fetch_cached are NEVER cached as data, and
HTTP 429 is a stop signal, not a retry dare (AGENTS.md sections 7.2/7.4).

Style: pure offline scorers (parcel, quarries) -> (Optional[int 0..100],
Estonian reason), mirroring dims_p4_maa_tehingud.py (#244/#328). Network
lives ONLY in fetch_cached / fetch_layer (polite single-GET + file cache
+ TTL); tests never touch the network. No livability/WEIGHTS/layers
integration here — rebalancing stays one joint change across batches
(existing tests pin WEIGHTS). No shared-file edits: issue #235 owns the
Maa-amet WFS for parameters3 params; this module only READS the same open
endpoint into its own cache and adds no group/shared changes.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #332's body states it
  extends the #248 demo ingestion ("no new plumbing expected") — splitting
  would leave the demo unreviewable against its coverage contract
  (same precedent as tehingud #244/#328, PR #384).
* Coarse-only bands: national geology layers are small-scale compilations
  (EGT licence scale caveat), so a clean parcel scores 70, never 100 —
  layer absence is not proven good soil.
* P4-054 beyond-buffer stays NULL, not "quiet": leviala is a mineral
  DISTRIBUTION area, not an active mine, and the blast-timetable leg is
  missing — absence of a polygon proves nothing about Tuesday 7am.
* P4-054 near-band (<= 2 km) uses nearest-VERTEX haversine as a coarse
  proxy, labelled "jame" in the reason: true edge distance would need
  PostGIS; the vertex proxy can only overstate the distance (under-flag),
  never invent quiet.
* P4-017 private-well quality is unknown by construction (Terviseamet:
  "ametlikke andmeid ei ole") — wells cap at 45 with the EI OLE note even
  when the connection facts are complete.
* TTL 365 d (annual bulk) per parameters4.md P4-016; WFS pulls use
  count=100 (max 100 features/req per parameters3.md section 5.3).
"""

import datetime as _dt
import math
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #248 acceptance criterion 2).
# ---------------------------------------------------------------------------

WFS_BASE = "https://gsavalik.envir.ee/geoserver/wfs"

# Verified-open layers (2026-09-13 GetCapabilities evidence in
# docs/p4_maa_subsurface.md). Keys are short join names, values are WFS
# typeNames consumed by fetch_layer.
SUBSURFACE_LAYERS = {
    # P4-016 legs.
    "karst": "maaamet:geol_hydrogeoloogia_allikadkarstivormid_karstivali",
    "turvas": "etak:e_307_turbavali_a",
    "sooala": "maaamet:geol_hydrogeoloogia_pinnakattekaardilt_sooalad",
    "pohjaveekaitse": (
        "maaamet:geol_hydrogeoloogia_pohjaveekaitstus_pvkhinnang"
    ),
    "puurkaev": "maaamet:geol_puurkaevud_wfs",
    # P4-054 legs (deposit distribution / find sites / prospective areas).
    "maardla_leviala": "maaamet:maavarad_gbmv_levialad",
    "maardla_leiukoht": "maaamet:maavarad_gbmv_leiukohad",
}

# TTLs in days: annual bulk per parameters4.md P4-016.
TTL_DAYS = {
    "subsurface_bulk": 365,
}

CACHE_SUBDIR = "hf-p4-maa-subsurface"
USER_AGENT = (
    "home-finder-research/0.1 (polite annual bulk; "
    "GitHub gregoreesmaa/home-finder issues 248/332)"
)
MAX_FEATURES_PER_REQ = 100  # parameters3.md section 5.3 politeness cap
QUARRY_NEAR_KM = 2.0  # coarse near-band for the P4-054 buffer leg


def cache_path(cache_dir: str, name: str) -> str:
    """Cache file location for a named fetch (flat files, no dumps committed)."""
    return os.path.join(cache_dir, CACHE_SUBDIR, name)


def is_fresh(path: str, ttl_days: int,
             now: Optional[_dt.datetime] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        mtime = _dt.datetime.fromtimestamp(
            os.path.getmtime(path), tz=_dt.timezone.utc)
    except OSError:
        return False
    at = now or _dt.datetime.now(tz=_dt.timezone.utc)
    return (at - mtime) <= _dt.timedelta(days=ttl_days)


def fetch_cached(url: str, cache_dir: str, name: str, ttl_days: int,
                 timeout_s: int = 25) -> str:
    """Polite single-GET with file cache. Returns the cache path.

    Fresh cache wins (no request). Transport errors are raised and NEVER
    written as data; HTTP 429 raises immediately (stop signal, no retry).
    Pulls urllib only (no new dependency).
    """
    import urllib.request

    dest = cache_path(cache_dir, name)
    if is_fresh(dest, ttl_days):
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 429:
                raise RuntimeError("HTTP 429 — stop, do not retry: " + url)
            body = resp.read()
    except Exception:
        raise
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, dest)
    return dest


def layer_url(layer: str, bbox: Optional[Tuple[float, float, float,
                                               float]] = None) -> str:
    """WFS GetFeature URL for a verified layer (EPSG:4326 GeoJSON).

    bbox is (minlon, minlat, maxlon, maxlat); count stays at the
    politeness cap — callers page, never raise it.
    """
    url = (WFS_BASE + "?service=WFS&version=2.0.0&request=GetFeature"
           "&outputFormat=application/json&srsName=EPSG:4326"
           "&count=%d&typeName=%s" % (MAX_FEATURES_PER_REQ, layer))
    if bbox is not None:
        url += "&bbox=%s,%s,%s,%s,EPSG:4326" % bbox
    return url


def fetch_layer(join_name: str, cache_dir: str,
                bbox: Optional[Tuple[float, float, float, float]] = None,
                ttl_days: int = 365) -> str:
    """Fetch one SUBSURFACE_LAYERS entry into the cache. Returns the path."""
    layer = SUBSURFACE_LAYERS[join_name]
    safe = join_name + ("_%s_%s_%s_%s" % bbox if bbox else "") + ".geojson"
    return fetch_cached(layer_url(layer, bbox), cache_dir, safe, ttl_days)


# ---------------------------------------------------------------------------
# Pure join core: polygons -> per-parcel class flags (hermetically tested).
# Rings are [[lon, lat], ...] in EPSG:4326. No distance gradients here —
# containment only; the one coarse buffer (P4-054) is vertex-haversine and
# labelled "jame" at the call site.
# ---------------------------------------------------------------------------

def point_in_polygon(lon: float, lat: float,
                     ring: List[List[float]]) -> bool:
    """Ray-casting containment. Degenerate rings (< 3 distinct points) match
    nothing — a broken polygon must not flag a parcel."""
    pts = [(p[0], p[1]) for p in ring
           if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 3:
        return False
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            xinters = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < xinters:
                inside = not inside
    return inside


def haversine_km(lon1: float, lat1: float, lon2: float,
                 lat2: float) -> float:
    """Great-circle distance in km (spherical earth — coarse by design)."""
    rad = math.pi / 180.0
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = (math.sin(dlat / 2.0) ** 2
         + math.cos(lat1 * rad) * math.cos(lat2 * rad)
         * math.sin(dlon / 2.0) ** 2)
    return 2.0 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def parse_geojson_features(doc: dict) -> List[dict]:
    """Flatten a WFS GeoJSON FeatureCollection to join fixtures.

    Returns [{"attrs": {...}, "polygons": [rings]}] for Polygon /
    MultiPolygon features only; anything else (points, broken geometry)
    is skipped, never coerced — a non-polygon must not flag a parcel.
    """
    out: List[dict] = []
    for feat in (doc or {}).get("features", []) or []:
        geom = (feat or {}).get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon" and isinstance(coords, list):
            rings = [r for r in coords if isinstance(r, list)]
        elif gtype == "MultiPolygon" and isinstance(coords, list):
            rings = [r for poly in coords if isinstance(poly, list)
                     for r in poly if isinstance(r, list)]
        else:
            continue
        if not rings:
            continue
        attrs = (feat or {}).get("properties") or {}
        out.append({"attrs": dict(attrs), "polygons": rings})
    return out


def join_parcel_flags(lon: float, lat: float,
                      layers: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
    """Per-parcel class join: layer name -> matched feature attrs.

    Exact polygon containment per layer; a parcel outside every polygon
    maps to {} (the scorers turn that into NULL, never into "quiet").
    """
    matched: Dict[str, List[dict]] = {}
    for name, feats in (layers or {}).items():
        hits = [f.get("attrs", {}) for f in feats or []
                if any(point_in_polygon(lon, lat, ring)
                       for ring in (f.get("polygons") or []))]
        if hits:
            matched[name] = hits
    return matched


def nearest_vertex_km(lon: float, lat: float,
                      polygons: List[List[List[float]]]) -> Optional[float]:
    """Haversine to the nearest polygon vertex (coarse P4-054 proxy).

    Overstates true edge distance, so it can only under-flag — documented
    as "jame hinnang" wherever it is used. None when no vertices exist.
    """
    best: Optional[float] = None
    for ring in polygons or []:
        for p in ring or []:
            if not (isinstance(p, (list, tuple)) and len(p) >= 2):
                continue
            d = haversine_km(lon, lat, p[0], p[1])
            if best is None or d < best:
                best = d
    return best


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


# ---------------------------------------------------------------------------
# Demo dim: P4-016 EGT engineering geology (issue #248).
#
# Parcel keys (the per-parcel join result; all Optional bools):
#   karst — inside/near a karstivali polygon (Lasnamäe paekivi risk)
#   turvas — inside a turbavali/sooala polygon (Pääsküla raba serv: vajumine)
#   alvar — thin soil on limestone (blasting/shallow-rock cost)
#   kaitseala — inside a põhjaveekaitse polygon (septic restriction risk)
# ---------------------------------------------------------------------------

def dim_engineering_geology(parcel: dict) -> Score:
    """P4-016: foundation-cost / septic-feasibility reading from joined
    subsurface classes. Coarse bands only; all-unknown stays NULL."""
    parcel = parcel or {}
    karst = parcel.get("karst")
    turvas = parcel.get("turvas")
    alvar = parcel.get("alvar")
    kaitseala = parcel.get("kaitseala")
    for key, val in (("karst", karst), ("turvas", turvas),
                     ("alvar", alvar), ("kaitseala", kaitseala)):
        if val is not None and not isinstance(val, bool):
            return None, ("Aluspinnase lipp '%s' on tundmatu väärtusega "
                          "(%r) — hinnangut EI OLE: liidestus peab andma "
                          "jah/ei, ära feigi" % (key, val))
    if karst is None and turvas is None and alvar is None \
            and kaitseala is None:
        return None, ("Aluspinnase klasse (karst/turvas/alvar/kaitseala) "
                      "krundi kohta EI OLE (hinnang puudub): geoloogia-kihi "
                      "liidestus puudub — kontrolli EGT geoportaali Avamust "
                      "või küsi geoloogilt, ära feigi")
    if karst is True and turvas is True:
        score, word = 20, "karst + turvas (varieeruv kandevõime + vajumine)"
    elif karst is True:
        score, word = 30, "karst (varieeruv kandevõime, uuring kohustuslik)"
    elif turvas is True:
        score, word = 35, "turvas/sooala (vajumine, vaiad tõenäolised)"
    elif alvar is True:
        score, word = 55, "alvar/õhuke pinnas paekivil (kaljutöö võimalik)"
    else:
        score, word = 70, "kaardistatud riske EI OLE (jäme hinnang)"
    note = ""
    if kaitseala is True:
        score = min(score, 50)
        note = "; põhjaveekaitseala: omapuhasti võib olla piiratud"
    return _clamp(score), ("Vundamendi-hinnang %d/100 (%s%s): aluskaardi "
                           "mõõtkavaklassi tõttu jäme hinnang, mitte "
                           "geotehniline uuring" % (score, word, note))


# ---------------------------------------------------------------------------
# Coverage dim: P4-017 drinking-water quality + sewer reality (issue #332).
#
# Parcel keys: vesi ('central'/'puurkaev'/'salvkaev'/None),
#   kanal ('central'/'omapuhasti'/None), liitumiskohustus (bool),
#   kaitseala_piirang (bool — puurkaevu piirang kaitsealal),
#   kvaliteet ('hea'/'halb'/None — Terviseameti seire jalg).
# ---------------------------------------------------------------------------

def dim_water_sewer(parcel: dict) -> Score:
    """P4-017: 5-figure-connection reading from joined UVK facts.

    Central/central is calm; wells and on-site treatment pull the score
    down; a connection duty on an unconnected parcel caps it (the bill is
    coming). One missing leg stays NULL — half an UVK truth misleads.
    """
    parcel = parcel or {}
    vesi = parcel.get("vesi")
    kanal = parcel.get("kanal")
    if vesi is None and kanal is None:
        return None, ("Vee- ja kanalisatsiooniühenduse andmeid krundi kohta "
                      "EI OLE (hinnang puudub): ÜVK-liidestus puudub — "
                      "kontrolli Tallinna Vee iseteenindusest tehnilised "
                      "tingimused või EHR-i, ära feigi")
    if vesi is None or kanal is None:
        missing = "vesi" if vesi is None else "kanal"
        return None, ("ÜVK-tõde on poolik (%s-legi EI OLE, hinnang puudub): "
                      "üks toru ei määra ühenduse hinda — täienda "
                      "liidestust, ära feigi" % missing)
    if vesi not in ("central", "puurkaev", "salvkaev") or kanal not in (
            "central", "omapuhasti"):
        return None, ("ÜVK-liik on tundmatu väärtusega (vesi=%r, kanal=%r) "
                      "— hinnangut EI OLE: liidestus peab andma teadaolevad "
                      "liigid, ära feigi" % (vesi, kanal))
    for key in ("liitumiskohustus", "kaitseala_piirang"):
        if parcel.get(key) is not None \
                and not isinstance(parcel.get(key), bool):
            return None, ("ÜVK-lipp '%s' on tundmatu väärtusega — hinnangut "
                          "EI OLE, ära feigi" % key)
    if parcel.get("kvaliteet") not in ("hea", "halb", None):
        return None, ("Veekvaliteedi lipp on tundmatu väärtusega — hinnangut "
                      "EI OLE, ära feigi")
    if vesi == "central" and kanal == "central":
        score, word = 85, "tsentraalne vesi + kanal (ühenduskulu puudub)"
    elif vesi == "central":
        score, word = 60, "tsentraalne vesi, omapuhasti (hoolduskulu)"
    elif kanal == "central":
        score, word = 55, "puurkaev/salvkaev + tsentraalne kanal (oma vee risk)"
    else:
        score, word = 45, "puurkaev/salvkaev + omapuhasti (oma vee risk)"
    caps = []
    if parcel.get("kaitseala_piirang") is True:
        score = min(score, 30)
        caps.append("kaitseala-piirang (kaevu-/puhasti luba kahtlane)")
    if parcel.get("liitumiskohustus") is True and not (
            vesi == "central" and kanal == "central"):
        score = min(score, 40)
        caps.append("liitumiskohustus (5-kohaline arve tulemas)")
    if parcel.get("kvaliteet") == "halb":
        score = min(score, 35)
        caps.append("seire: kvaliteet halb (Terviseamet)")
    note = ""
    if vesi in ("puurkaev", "salvkaev") and parcel.get("kvaliteet") is None:
        note = "; erakaevu kvaliteedi kohta ametlikke andmeid EI OLE"
    if caps:
        note = "; " + ", ".join(caps) + note
    return _clamp(score), ("Vee-kanalisatsiooni hinnang %d/100 (%s%s)"
                           % (score, word, note))


# ---------------------------------------------------------------------------
# Coverage dim: P4-054 quarry blast + truck season (issue #332).
#
# quarries: [{"nimi": str, "polygons": [rings]}] from the
# maavarad_gbmv_levialad join (Maardu/Harku paekivi affecting Pirita /
# Lasnamäe edge). The blast-timetable leg (Keskkonnamet load schedules)
# is not an open feed, so every scored reason says so.
# ---------------------------------------------------------------------------

def dim_quarry_buffer(parcel: dict, quarries: List[dict]) -> Score:
    """P4-054: Tuesday-7am reading from the deposit buffer leg.

    Scores ONLY proven proximity (inside -> 25, coarse near-band -> 45);
    anything further stays NULL — a missing polygon is not proof of quiet.
    """
    parcel = parcel or {}
    lon, lat = parcel.get("lon"), parcel.get("lat")
    if not isinstance(lon, (int, float)) \
            or not isinstance(lat, (int, float)):
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "karjääri-puhvrit ei saa arvutada — täienda "
                      "koordinaat, ära feigi")
    if not quarries:
        return None, ("Maardlate kihti (levialad) EI OLE laetud (hinnang "
                      "puudub): puhver vajab maavarad_gbmv_levialad "
                      "liidestust — tõsta puhver, ära feigi")
    NO_TIMETABLE = ("lõhkamiste ajagraafiku jalga EI OLE "
                    "(Keskkonnaameti load ei ole avaandmed)")
    for q in quarries:
        polys = (q or {}).get("polygons") or []
        if any(point_in_polygon(lon, lat, ring) for ring in polys):
            return 25, ("Krunt '%s' levialas: karjäärimühina hinnang "
                        "25/100 (jäme puhver; %s)"
                        % ((q or {}).get("nimi", "?"), NO_TIMETABLE))
    best: Optional[float] = None
    best_name = "?"
    for q in quarries:
        d = nearest_vertex_km(lon, lat, (q or {}).get("polygons") or [])
        if d is not None and (best is None or d < best):
            best, best_name = d, (q or {}).get("nimi", "?")
    if best is not None and best <= QUARRY_NEAR_KM:
        return 45, ("Lähim teadaolev maardla '%s' %.1f km (jäme "
                    "tipp-kauguse hinnang): veohooaja-mühina hinnang "
                    "45/100; %s" % (best_name, best, NO_TIMETABLE))
    return None, ("Teadaolevate maardlate puhvrit (<= %.0f km) EI OLE "
                  "(hinnang puudub): kaugus ei tõesta vaikust — "
                  "müra-hinnang puudub" % QUARRY_NEAR_KM)


P4_MAA_SUBSURFACE_DIMS = (
    ("eng_geology", "P4-016", dim_engineering_geology),
    ("water_sewer", "P4-017", dim_water_sewer),
    ("quarry_buffer", "P4-054", dim_quarry_buffer),
)


def score_p4_maa_subsurface(parcel: dict,
                            quarries: Optional[List[dict]] = None) -> Dict[
                                str, Optional[int]]:
    """All three Maa-subsurface dims for one parcel (keys match the registry).
    quarries feeds only the P4-054 buffer leg."""
    parcel = parcel or {}
    quarries = quarries or []
    return {
        "eng_geology": dim_engineering_geology(parcel)[0],
        "water_sewer": dim_water_sewer(parcel)[0],
        "quarry_buffer": dim_quarry_buffer(parcel, quarries)[0],
    }
