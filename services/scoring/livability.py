"""Livability dimensions for auto-imported listings (issues A1-A10).

Replaces the blanket neutral-50 with a documented registry: each dimension
scores 0..100 (or None when its data is missing) with an Estonian reason.
Combined livability is the weight-renormalized mean over AVAILABLE dims, so
a missing source never drags the score — it just narrows the evidence. All
dims missing -> 50 + an explicit "no data" reason (now rare, never silent).

Data (polite, cached, graceful):
* Photon geocoding (komoot.io, no key) turns addresses into coordinates;
* a single Overpass QL query per listing fetches nearby schools, stops,
  parks, shops and clinics from OpenStreetMap;
* commute uses haversine to a small table of well-known city centres;
* safety uses coarse tiers from national crime reviews (ordinal positions
  corroborated across years: Ida-Viru highest, Harju second, Tartu
  elevated, islands lowest; other counties -> None, never invented).

Network lives behind `resolve()`/`fetch_*` (cached 30d, 1s politeness gap
on uncached Overpass calls); every scorer below is pure and offline-tested.
"""

import math
import time
from typing import Callable, Dict, List, Optional, Tuple

import httpx

from adapters import cached_fetch, polite_headers

Scores = List[Tuple[str, Optional[int], str]]  # (dim, score|None, reason)

GEOCODE_TTL_S = 30 * 24 * 3600
OVERPASS_TTL_S = 30 * 24 * 3600
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
PHOTON_URL = "https://photon.komoot.io/api/"
# Estonia bounding box (lon_min, lat_min, lon_max, lat_max) biases Photon.
EE_BBOX = (21.5, 57.5, 28.5, 59.7)

HEADERS = dict(polite_headers())
HEADERS["Accept"] = "application/json"

# Well-known city centres (WGS84). Only cities listed here can score the
# commute dimension; anywhere else yields None, never a guess.
CITY_CENTERS = {
    "tallinn": (59.4372, 24.7536),
    "tartu": (58.3780, 26.7290),
    "pärnu": (58.3859, 24.4989),
    "narva": (59.3777, 28.1904),
}
# Commuter towns evaluated against their centre city (labelled as such).
COMMUTE_PARENT = {
    "keila": "tallinn",
    "maardu": "tallinn",
    "saue": "tallinn",
    "elva": "tartu",
}

# Safety tiers from national crime reviews (Justiitsministeerium
# "Kuritegevus Eestis" series + OSAC Estonia reports): only ordinal
# positions corroborated across years are encoded (Ida-Viru highest,
# Harju second, Tartu elevated, islands lowest). Every other county is
# absent -> None with an honest reason, never an invented rate.
SAFETY_TIERS = {
    "Ida-Viru maakond": (30, "Ida-Virumaal kõrgeim kuritegevus (riiklikud ülevaated)"),
    "Harju maakond": (55, "Harjumaal üle keskmise kuritegevus (riiklikud ülevaated)"),
    "Tartu maakond": (62, "Tartumaal veidi üle keskmise kuritegevus (riiklikud ülevaated)"),
    "Hiiu maakond": (90, "Hiiumaal madalaim kuritegevus (riiklikud ülevaated)"),
    "Saare maakond": (88, "Saaremaal madalaim kuritegevus (riiklikud ülevaated)"),
}

# Registry weights (sum to 1; renormalized over available dims at combine).
WEIGHTS = {
    "schools": 0.20,
    "transit": 0.15,
    "services": 0.15,
    "green": 0.15,
    "commute": 0.20,
    "safety": 0.15,
}


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between (lat, lon) pairs."""
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _band(meters: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers meters; None stays None."""
    if meters is None:
        return None
    for limit, pts in bands:
        if meters <= limit:
            return pts
    return bands[-1][1]


def _nearest_m(origin: Tuple[float, float], pois: List[dict], kinds: set) -> Optional[float]:
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            d = haversine_km(origin, (p["lat"], p["lon"])) * 1000.0
            if best is None or d < best:
                best = d
    return best


def _count_within_m(origin: Tuple[float, float], pois: List[dict], kinds: set, radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if haversine_km(origin, (p["lat"], p["lon"])) * 1000.0 <= radius_m:
                n += 1
    return n


def dim_schools(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """A2: schools / childcare proximity (OSM amenity=school|kindergarten)."""
    if not origin or pois is None:
        return None, "Koolide info puudub"
    m = _nearest_m(origin, pois, {"school", "kindergarten"})
    if m is None:
        return 15, "Lähim kool/Lasteaed üle 2,5 km"
    s = _band(m, [(300, 100), (600, 85), (1000, 70), (1500, 50), (2500, 30)])
    return s, "Lähim kool/lasteaed %s" % _fmt_m(m)


def dim_transit(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """A3: public-transit access (OSM stops within 500 m)."""
    if not origin or pois is None:
        return None, "Ühistranspordi info puudub"
    n = _count_within_m(origin, pois, {"bus_stop"}, 500)
    if n >= 5:
        return 100, "Bussipeatused 500 m raadiuses: %d" % n
    if n >= 3:
        return 80, "Bussipeatused 500 m raadiuses: %d" % n
    if n >= 1:
        return 60, "Lähim peatus 500 m raadiuses"
    m = _nearest_m(origin, pois, {"bus_stop"})
    if m is not None and m <= 1000:
        return 35, "Lähim peatus %s" % _fmt_m(m)
    return 15, "Peatus üle 1 km kaugusel"


def dim_green(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """A4: green space / recreation (OSM parks, forests, beaches)."""
    if not origin or pois is None:
        return None, "Haljasalade info puudub"
    m = _nearest_m(origin, pois, {"park", "forest", "beach"})
    if m is None:
        return 20, "Park/mets/rand üle 1,5 km"
    s = _band(m, [(400, 100), (800, 80), (1200, 60)])
    return s, "Lähim park/mets/rand %s" % _fmt_m(m)


def dim_services(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """A7: daily services (supermarket, pharmacy, clinic)."""
    if not origin or pois is None:
        return None, "Teenuste info puudub"
    m = _nearest_m(origin, pois, {"supermarket", "convenience", "pharmacy", "clinic"})
    if m is None:
        return 20, "Pood/apteek/kliinik üle 1,5 km"
    s = _band(m, [(400, 100), (800, 80), (1200, 60)])
    return s, "Lähim pood/apteek/kliinik %s" % _fmt_m(m)


def commute_target(address: str) -> Optional[Tuple[str, Tuple[float, float]]]:
    """(City label, centre) for the commute dim, or None when unknown."""
    text = (address or "").lower()
    for key, centre in CITY_CENTERS.items():
        if key in text:
            return key.capitalize(), centre
    for town, parent in COMMUTE_PARENT.items():
        if town in text:
            return "%s keskus" % parent.capitalize(), CITY_CENTERS[parent]
    return None


def dim_commute(origin: Optional[Tuple[float, float]], address: str) -> Tuple[Optional[int], str]:
    """A8: straight-line distance to the city centre (labelled as such)."""
    if not origin:
        return None, "Kauguse info puudub"
    target = commute_target(address)
    if target is None:
        return None, "Linnakeskus teadmata – kaugust ei hinda"
    label, centre = target
    km = haversine_km(origin, centre)
    s = _band(km * 1000.0, [(3000, 100), (6000, 85), (12000, 70), (20000, 55), (35000, 40)])
    return s, "%s ~%s km (linnulennult)" % (label, _fmt_km(km))


def dim_safety(county: str) -> Tuple[Optional[int], str]:
    """A6: coarse county safety tier (sourced ordinals only)."""
    if county in SAFETY_TIERS:
        return SAFETY_TIERS[county]
    return None, "Maakonna turvastatistika puudub"


def combine(dims: Dict[str, Optional[int]]) -> Optional[int]:
    """Weight-renormalized mean over available dims; None when all missing."""
    num, den = 0.0, 0.0
    for name, w in WEIGHTS.items():
        v = dims.get(name)
        if v is not None:
            num += w * v
            den += w
    if den <= 0:
        return None
    return int(round(num / den))


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _fmt_km(km: float) -> str:
    s = "%.1f" % km
    return s.replace(".", ",")


OVERPASS_QUERY = """[out:json][timeout:25];
(
  node["amenity"~"school|kindergarten|pharmacy|clinic|doctors"](around:1500,{lat},{lon});
  node["highway"="bus_stop"](around:1500,{lat},{lon});
  node["railway"="tram_stop"](around:1500,{lat},{lon});
  node["leisure"~"park|garden|playground"](around:1500,{lat},{lon});
  node["natural"~"wood|beach"](around:1500,{lat},{lon});
  node["landuse"~"forest|grass|meadow"](around:1500,{lat},{lon});
  node["shop"~"supermarket|convenience"](around:1500,{lat},{lon});
  way["amenity"~"school|kindergarten|pharmacy|clinic|doctors"](around:1500,{lat},{lon});
  way["leisure"~"park|garden|playground"](around:1500,{lat},{lon});
  way["natural"~"wood|beach"](around:1500,{lat},{lon});
  way["landuse"~"forest|grass|meadow"](around:1500,{lat},{lon});
  way["shop"~"supermarket|convenience"](around:1500,{lat},{lon});
);
out center 200;"""

_POI_KIND = [
    ("amenity", {"school": "school", "kindergarten": "kindergarten", "pharmacy": "pharmacy",
                 "clinic": "clinic", "doctors": "clinic"}),
    ("highway", {"bus_stop": "bus_stop"}),
    ("railway", {"tram_stop": "bus_stop"}),
    ("leisure", {"park": "park", "garden": "park", "playground": "park"}),
    ("natural", {"wood": "forest", "beach": "beach"}),
    ("landuse", {"forest": "forest", "grass": "park", "meadow": "park"}),
    ("shop", {"supermarket": "supermarket", "convenience": "convenience"}),
]


def parse_overpass(payload: dict) -> List[dict]:
    """Overpass JSON -> [{kind, lat, lon}]. Pure; unknown tags skipped."""
    out: List[dict] = []
    for el in (payload or {}).get("elements", []):
        tags = el.get("tags", {})
        kind = None
        for tagkey, mapping in _POI_KIND:
            val = tags.get(tagkey, "").split(";")[0]
            if val in mapping:
                kind = mapping[val]
                break
        if kind is None:
            continue
        lat, lon = el.get("lat"), el.get("lon")
        if lat is None and isinstance(el.get("center"), dict):
            lat, lon = el["center"].get("lat"), el["center"].get("lon")
        if lat is None or lon is None:
            continue
        out.append({"kind": kind, "lat": float(lat), "lon": float(lon)})
    return out


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def fetch_geocode_photon(address: str, timeout: float = 20.0) -> Optional[Tuple[float, float]]:
    """Photon: address -> (lat, lon). None when nothing found."""
    params = {
        "q": address,
        "limit": "1",
        "lang": "et",
        "bbox": "%s,%s,%s,%s" % EE_BBOX,
    }
    resp = httpx.get(PHOTON_URL, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    feats = resp.json().get("features", [])
    if not feats:
        return None
    lon, lat = feats[0]["geometry"]["coordinates"][:2]
    return float(lat), float(lon)


def fetch_geocode_nominatim(address: str, timeout: float = 20.0) -> Optional[Tuple[float, float]]:
    """Nominatim fallback (countrycodes=ee + Estonia viewbox). None when empty."""
    params = {
        "q": address,
        "format": "jsonv2",
        "limit": "1",
        "countrycodes": "ee",
        "viewbox": "%s,%s,%s,%s" % (EE_BBOX[0], EE_BBOX[3], EE_BBOX[2], EE_BBOX[1]),
        "bounded": "1",
    }
    resp = httpx.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    hits = resp.json()
    if not hits:
        return None
    time.sleep(1.2)  # Nominatim usage policy: max 1 req/s
    return float(hits[0]["lat"]), float(hits[0]["lon"])


def fetch_geocode(address: str, timeout: float = 20.0) -> Optional[Tuple[float, float]]:
    """address -> (lat, lon): Photon first, Nominatim fallback. None if both miss."""
    try:
        # Short primary timeout: the fallback covers slow/dead Photon, and
        # every success is cached for 30d anyway.
        return fetch_geocode_photon(address, timeout=4.0)
    except httpx.HTTPError:
        return fetch_geocode_nominatim(address, timeout)


def fetch_pois(lat: float, lon: float, timeout: float = 30.0) -> Optional[List[dict]]:
    """One Overpass query for all POI kinds. None on transport error."""
    try:
        resp = httpx.post(
            OVERPASS_URL,
            data={"data": OVERPASS_QUERY.format(lat=lat, lon=lon)},
            headers=HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
        pois = parse_overpass(resp.json())
    except httpx.HTTPError:
        return None
    time.sleep(1.2)  # Overpass usage policy: polite gap after uncached calls
    return pois


def resolve(address: str, cache_dir: Optional[str] = None) -> Optional[dict]:
    """address -> {"lat","lon","pois"} using 30d caches. None when unresolvable."""
    if not address:
        return None
    try:
        loc = cached_fetch(
            "liv_geocode", address, 1,
            lambda: _dump_loc(fetch_geocode(address)),
            cache_dir, GEOCODE_TTL_S,
        )
        lat, lon = _load_loc(loc)
    except (httpx.HTTPError, ValueError):
        return None
    if lat is None:
        return None
    key = "%.4f,%.4f" % (lat, lon)
    try:
        raw = cached_fetch(
            "liv_pois", key, 1,
            lambda: _dump_pois(fetch_pois(lat, lon)),
            cache_dir, OVERPASS_TTL_S,
        )
        pois = _load_pois(raw)
    except httpx.HTTPError:
        pois = None
    return {"lat": lat, "lon": lon, "pois": pois}


def _dump_loc(loc: Optional[Tuple[float, float]]) -> str:
    return "" if loc is None else "%.6f,%.6f" % loc


def _load_loc(raw: str) -> Tuple[Optional[float], Optional[float]]:
    parts = (raw or "").strip().split(",")
    if len(parts) != 2:
        return None, None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None, None


def _dump_pois(pois: Optional[List[dict]]) -> str:
    import json as _json

    return _json.dumps(pois)


def _load_pois(raw: str) -> Optional[List[dict]]:
    import json as _json

    try:
        val = _json.loads(raw or "null")
    except ValueError:
        return None
    return val if isinstance(val, list) else None


def enrich_row(address: str, county: str, cache_dir: Optional[str] = None,
               resolver: Optional[Callable[[str], Optional[dict]]] = None,
               geo: Optional[dict] = None) -> Tuple[int, List[str]]:
    """(livability, reasons) for one listing. resolver injects fakes in tests.

    Pass pre-resolved `geo` to avoid resolving twice (ingest stashes the
    coordinates on the row for the map); otherwise resolves here.
    """
    if geo is None:
        geo = (resolver or (lambda a: resolve(a, cache_dir)))(address)
    origin = (geo["lat"], geo["lon"]) if geo else None
    pois = geo.get("pois") if geo else None
    dims: Dict[str, Optional[int]] = {}
    scored: Scores = []
    for name, fn in (
        ("schools", lambda: dim_schools(origin, pois)),
        ("transit", lambda: dim_transit(origin, pois)),
        ("green", lambda: dim_green(origin, pois)),
        ("services", lambda: dim_services(origin, pois)),
        ("commute", lambda: dim_commute(origin, address or "")),
    ):
        v, reason = fn()
        dims[name] = v
        if v is not None:
            scored.append((name, v, reason))
    safety_v, safety_r = dim_safety(county or "")
    dims["safety"] = safety_v
    if safety_v is not None:
        scored.append(("safety", safety_v, safety_r))
    total = combine(dims)
    if total is None:
        return 50, ["Elamiskvaliteet arvutamata – asukoha andmed puuduvad"]
    reasons = [r for _, _, r in scored]
    return total, reasons
