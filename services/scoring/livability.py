"""Livability dimensions for auto-imported listings (issues A1-A10, #73-#75).

Replaces the blanket neutral-50 with a documented registry: each dimension
scores 0..100 (or None when its data is missing) with an Estonian reason.
Combined livability is the weight-renormalized mean over AVAILABLE dims, so
a missing source never drags the score — it just narrows the evidence. All
dims missing -> 50 + an explicit "no data" reason (now rare, never silent).

Data (polite, cached, graceful):
* Photon geocoding (komoot.io, no key) turns addresses into coordinates;
* a single Overpass QL query per listing fetches nearby schools, stops
  (bus + rail stations), parks, water, shops and clinics from OpenStreetMap;
* connect estimates travel TIME (per mode, labelled estimates) to the city
  centre, the nearest station and the nearest shop — bird-flight distances
  converted with documented average speeds, never presented as measured;
* urban scores the calm-countryside <-> busy-city axis from POI density so
  buyers can weight it themselves (#74);
* safety uses coarse tiers from national crime reviews (ordinal positions
  corroborated across years: Ida-Viru highest, Harju second, Tartu
  elevated, islands lowest; other counties -> None, never invented).

Considered and dismissed (#73 — no open/consistent source, so excluded
rather than faked): street noise levels, air/light quality (dim_air stays
a stub), parking (OSM coverage is city-skewed and would punish the
countryside unfairly), building energy rating (no open registry), crime
below county level (no open data), school QUALITY vs proximity (no open
results data). Revisit when a source exists.

Network lives behind `resolve()`/`fetch_*` (cached 30d, 1s politeness gap
on uncached Overpass calls); every scorer below is pure and offline-tested.
"""

import math
import re
import time
from typing import Callable, Dict, List, Optional, Tuple

import httpx

from adapters import cached_fetch, polite_headers

Scores = List[Tuple[str, Optional[int], str]]  # (dim, score|None, reason)

GEOCODE_TTL_S = 30 * 24 * 3600
OVERPASS_TTL_S = 30 * 24 * 3600
# Public mirrors tried in order; per-IP throttling/outages hit mirrors
# independently, so failover beats retrying one host.
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
OVERPASS_URL = OVERPASS_URLS[0]
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
# NOTE (A9): light / air quality has no open data source yet. It is an
# explicit stub (dim_air, always None) and stays out of WEIGHTS until
# sourced — no fake precision. urban defaults near-neutral: it is a taste
# axis buyers adjust themselves (#74), not a generic good.
WEIGHTS = {
    "schools": 0.18,
    "transit": 0.12,
    "services": 0.12,
    "green": 0.10,
    "water": 0.08,
    "rail": 0.07,
    "urban": 0.03,
    "safety": 0.15,
    "connect": 0.15,
}


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between (lat, lon) pairs."""
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
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


# Estimated travel speeds (km/h, Estonian averages). Times derived from
# bird-flight distance with these speeds are labelled estimates (#75) —
# the pipeline has no routing engine, so no measured times are claimed.
SPEED_WALK_KMH = 4.5
SPEED_BIKE_KMH = 15.0
SPEED_CAR_KMH = 35.0
SPEED_TRAIN_KMH = 55.0
TRAIN_ACCESS_MIN = 10.0  # walk to the station + waiting, estimated


def _minutes(km: float, kmh: float, extra: float = 0.0) -> float:
    """Bird-flight km -> estimated travel minutes at the given speed."""
    return km / kmh * 60.0 + extra


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


def dim_water(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """#73: sea / lake proximity (OSM natural=beach|water)."""
    if not origin or pois is None:
        return None, "Veekogude info puudub"
    m = _nearest_m(origin, pois, {"beach", "water"})
    if m is None:
        return 20, "Meri/järv üle 2 km"
    s = _band(m, [(500, 100), (1000, 75), (2000, 50)])
    return s, "Lähim meri/järv %s" % _fmt_m(m)


def dim_rail(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """#73: train station access (OSM railway=station|halt, 2 km window)."""
    if not origin or pois is None:
        return None, "Rongiühenduse info puudub"
    m = _nearest_m(origin, pois, {"rail_station"})
    if m is None:
        return 20, "Rongipeatus üle 2 km"
    s = _band(m, [(800, 100), (1500, 80), (2000, 60)])
    return s, "Lähim rongipeatus %s" % _fmt_m(m)


def dim_urban(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]]) -> Tuple[Optional[int], str]:
    """#73/#74: calm-countryside (0) <-> busy-city (100) axis from POI density.

    A taste axis, not a generic good: it defaults near-neutral in WEIGHTS so
    buyers weight it themselves.
    """
    if not origin or pois is None:
        return None, "Asustuse info puudub"
    n = sum(1 for p in pois if p.get("lat") is not None)
    s = _band(n, [(0, 10), (5, 25), (15, 40), (30, 60), (60, 80)])
    return s, "Elu-olu tihedus: %d huvipunkti 1,5 km raadiuses" % n


def dim_connect(origin: Optional[Tuple[float, float]], pois: Optional[List[dict]],
               address: str) -> Tuple[Optional[int], str]:
    """#75: is the listing well-connected? Best of the travel-time options.

    Options cover the generic question across targets: city centre by car,
    station (walk + estimated train leg), shop on foot/bike. Distances are
    bird-flight converted with the documented average speeds above — every
    time is a labelled estimate, never a measured route (no routing engine
    in the pipeline).
    """
    if not origin:
        return None, "Ühenduse info puudub"
    opts: List[Tuple[str, float]] = []  # (label, estimated minutes)
    target = commute_target(address or "")
    if target is not None:
        label, centre = target
        km = haversine_km(origin, centre)
        opts.append(("%s autoga" % label, _minutes(km, SPEED_CAR_KMH)))
    if pois is not None:
        st = _nearest_m(origin, pois, {"rail_station"})
        if st is not None:
            opts.append(("rong (peatus +%d min)" % int(TRAIN_ACCESS_MIN),
                         _minutes(st / 1000.0, SPEED_WALK_KMH, TRAIN_ACCESS_MIN)))
        shop = _nearest_m(origin, pois, {"supermarket", "convenience"})
        if shop is not None:
            km = shop / 1000.0
            if km <= 1.2:
                opts.append(("pood jalgsi", _minutes(km, SPEED_WALK_KMH)))
            else:
                opts.append(("pood rattaga", _minutes(km, SPEED_BIKE_KMH)))
    if not opts:
        return 15, "Keskus, rong ja pood kaugel või teadmata"
    scored = [
        (label, mins, _band(mins, [(10, 100), (20, 85), (30, 70),
                                   (45, 55), (60, 40), (float("inf"), 25)]))
        for label, mins in opts
    ]
    best = max(scored, key=lambda t: t[2] or 0)
    bits = ["%s ~%d min" % (label, int(round(mins))) for label, mins, _ in scored]
    return best[2], "Ühendus (hinnang): %s" % " · ".join(bits)


def dim_air() -> Tuple[Optional[int], str]:
    """A9: light / air quality — honest stub until a source exists."""
    return None, "Valgus/õhk: andmed puuduvad"


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


OVERPASS_QUERY = """[out:json][timeout:25];
(
  node["amenity"~"school|kindergarten|pharmacy|clinic|doctors"](around:1500,{lat},{lon});
  node["highway"="bus_stop"](around:1500,{lat},{lon});
  node["railway"~"tram_stop|station|halt"](around:2000,{lat},{lon});
  node["leisure"~"park|garden|playground"](around:1500,{lat},{lon});
  node["natural"~"wood|beach|water"](around:1500,{lat},{lon});
  node["landuse"~"forest|grass|meadow"](around:1500,{lat},{lon});
  node["shop"~"supermarket|convenience"](around:1500,{lat},{lon});
  way["amenity"~"school|kindergarten|pharmacy|clinic|doctors"](around:1500,{lat},{lon});
  way["railway"~"station|halt"](around:2000,{lat},{lon});
  way["leisure"~"park|garden|playground"](around:1500,{lat},{lon});
  way["natural"~"wood|beach|water"](around:1500,{lat},{lon});
  way["landuse"~"forest|grass|meadow"](around:1500,{lat},{lon});
  way["shop"~"supermarket|convenience"](around:1500,{lat},{lon});
);
out center 200;"""

_POI_KIND = [
    ("amenity", {"school": "school", "kindergarten": "kindergarten", "pharmacy": "pharmacy",
                 "clinic": "clinic", "doctors": "clinic"}),
    ("highway", {"bus_stop": "bus_stop"}),
    ("railway", {"tram_stop": "bus_stop", "station": "rail_station",
                 "halt": "rail_station"}),
    ("leisure", {"park": "park", "garden": "park", "playground": "park"}),
    ("natural", {"wood": "forest", "beach": "beach", "water": "water"}),
    ("landuse", {"forest": "forest", "grass": "park", "meadow": "park"}),
    ("shop", {"supermarket": "supermarket", "convenience": "convenience"}),
]

# --- HOOK batch3-group11 (#95, Group 11 OSM dims p169/p346/p419/p466/p470) ---
# New-module plumbing only: fetch + parse the Group 11 tags so the data
# flows. Scorers/tests live in dims_group11.py. WEIGHTS/combine/enrich_row
# are deliberately untouched (pinned by tests; rebalancing is central).
from dims_group11 import GROUP11_POI_KIND, GROUP11_QUERY_LINES  # noqa: E402

_POI_KIND = _POI_KIND + GROUP11_POI_KIND
OVERPASS_QUERY = OVERPASS_QUERY.replace(
    ");\nout center 200;", GROUP11_QUERY_LINES + ");\nout center 200;"
)
# --- END HOOK batch3-group11 ---


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
    """Photon: address -> (lat, lon). None when nothing found.

    Full string first, then the simplified variants (#81: portal strings
    carry apartment suffixes and descriptive junk that only fail whole).
    Variant misses are cheap single queries, cached 30d under the address.
    """
    for i, query in enumerate(simplify_address(address)):
        params = {
            "q": query,
            "limit": "1",
            # NOTE: Photon supports only default/de/en/fr; "et" 400s every call.
            "lang": "default",
            "bbox": "%s,%s,%s,%s" % EE_BBOX,
        }
        resp = httpx.get(PHOTON_URL, params=params, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        feats = resp.json().get("features", [])
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"][:2]
            return float(lat), float(lon)
        if i < len(simplify_address(address)) - 1:
            time.sleep(0.5)  # bulk imports must not hammer free geocoders
    return None


def _de_apartment(seg: str) -> str:
    """Strip apartment suffixes: "Astangu tn 68-19" -> "Astangu tn 68"."""
    return re.sub(r"(\d+)[/\-]\d+[\-\d/]*", r"\1", seg)


_CITY_HINT = re.compile(
    r"linn|alev|küla|tallinn|tartu|pärnu|narva|kohtu|viljandi|rakvere|"
    r"maardu|kuressaare|valga|võru|jõhvi|haapsalu|keila|paide|elva|tapa|"
    r"saue|maakond|vald",
    re.I,
)


def simplify_address(address: str) -> List[str]:
    """Full address first, then progressively simpler candidates (#81).

    Portal addresses carry apartment suffixes ("68-19"), descriptive junk
    ("Harku järve lähedal") or missing numbers ("Tähetorni tn ,"); later
    candidates normalize those away down to street + settlement. Order
    preserved, duplicates dropped.
    """
    segs = [s.strip() for s in (address or "").split(",") if s.strip()]
    if len(segs) < 2:
        return segs
    norm = [_de_apartment(s) for s in segs]
    street = next((s for s in norm if re.search(r"\d", s)), norm[0])
    city = next((s for s in norm if _CITY_HINT.search(s)), norm[-1])
    out = [
        address.strip(),
        ", ".join(norm),
        "%s, %s" % (street, city),
        street,
        norm[-1],
    ]
    seen, deduped = set(), []
    for cand in out:
        if cand not in seen:
            seen.add(cand)
            deduped.append(cand)
    return deduped


def fetch_geocode_nominatim(address: str, timeout: float = 20.0) -> Optional[Tuple[float, float]]:
    """Nominatim fallback (countrycodes=ee + Estonia viewbox). None when empty.

    Retries through 429s with backoff instead of burning the address as a
    miss; transport errors still propagate (resolve() maps them to null dims,
    never to cached negatives). Tries simplified "street, city" candidates
    after the full hierarchy misses.
    """
    base = {
        "format": "jsonv2",
        "limit": "1",
        "countrycodes": "ee",
        "viewbox": "%s,%s,%s,%s" % (EE_BBOX[0], EE_BBOX[3], EE_BBOX[2], EE_BBOX[1]),
        "bounded": "1",
    }
    backoff = 15.0
    for query in simplify_address(address):
        params = dict(base, q=query)
        for attempt in range(3):
            resp = httpx.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=timeout)
            time.sleep(1.5)  # Nominatim usage policy: max 1 req/s
            if resp.status_code == 429 and attempt < 2:
                time.sleep(backoff)
                backoff *= 4
                continue
            resp.raise_for_status()
            backoff = 15.0
            hits = resp.json()
            if hits:
                return float(hits[0]["lat"]), float(hits[0]["lon"])
            break
    return None


def fetch_geocode(address: str, timeout: float = 20.0) -> Optional[Tuple[float, float]]:
    """address -> (lat, lon): Photon first, Nominatim fallback.

    None if both miss. The fallback runs on Photon MISSES too (#81: before,
    only transport errors fell through, so brittle strings never reached
    the variant-tolerant Nominatim path); every answer caches 30d.
    """
    try:
        # Short primary timeout: the fallback covers slow/dead Photon, and
        # every success is cached for 30d anyway.
        hit = fetch_geocode_photon(address, timeout=4.0)
        time.sleep(0.5)  # bulk imports must not hammer free geocoders
        if hit is not None:
            return hit
    except httpx.HTTPError as e:
        if getattr(getattr(e, "response", None), "status_code", None) == 429:
            time.sleep(60.0)  # Photon throttle: back off before the fallback
    return fetch_geocode_nominatim(address, timeout)


def fetch_pois(lat: float, lon: float, timeout: float = 75.0) -> Optional[List[dict]]:
    """One Overpass query for all POI kinds.

    Transport errors propagate (resolve() maps them to null dims without
    caching); only real answers are cached.
    """
    last: Optional[httpx.HTTPError] = None
    # Per-mirror cap: a hanging mirror must not eat the whole budget while
    # healthier ones wait behind it.
    each = min(timeout, 25.0)
    for mirror in OVERPASS_URLS:
        try:
            resp = httpx.post(
                mirror,
                data={"data": OVERPASS_QUERY.format(lat=lat, lon=lon)},
                headers=HEADERS,
                timeout=each,
            )
            resp.raise_for_status()
            pois = parse_overpass(resp.json())
            time.sleep(1.2)  # Overpass usage policy: polite gap after calls
            return pois
        except httpx.HTTPError as e:
            last = e
            continue
    raise last if last is not None else RuntimeError("no Overpass mirror answered")


class _Transient(Exception):
    """Transport failure: must never be cached as a negative result."""


def _strict_geocode(address: str) -> Optional[Tuple[float, float]]:
    try:
        return fetch_geocode(address)
    except httpx.HTTPError as e:
        raise _Transient(str(e))


def resolve(address: str, cache_dir: Optional[str] = None) -> Optional[dict]:
    """address -> {"lat","lon","pois"} using 30d caches. None when unresolvable."""
    if not address:
        return None
    try:
        loc = cached_fetch(
            # v6: v5 ran mid-throttle (Photon+Nominatim 429s), so its ""
            # negatives are suspect; the bump re-resolves at a polite pace.
            "liv_geocode6", address, 1,
            lambda: _dump_loc(_strict_geocode(address)),
            cache_dir, GEOCODE_TTL_S,
        )
        lat, lon = _load_loc(loc)
    except (_Transient, httpx.HTTPError, ValueError):
        return None
    if lat is None:
        return None
    key = "%.4f,%.4f" % (lat, lon)
    try:
        raw = cached_fetch(
            # v3: v2 holds "null" entries written by the pre-fix version that
            # swallowed transport errors; "null" is never a real answer.
            "liv_pois3", key, 1,
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
               geo: Optional[dict] = None) -> Tuple[int, List[str], Dict[str, Optional[int]]]:
    """(livability, reasons, dims) for one listing. resolver injects fakes.

    `dims` maps every WEIGHTS key to its score (None when missing) so the UI
    can re-weight per buyer taste (#74); combined livability stays the
    weight-renormalized default mean. Pass pre-resolved `geo` to avoid
    resolving twice (ingest stashes the coordinates on the row for the map);
    otherwise resolves here.
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
        ("water", lambda: dim_water(origin, pois)),
        ("rail", lambda: dim_rail(origin, pois)),
        ("urban", lambda: dim_urban(origin, pois)),
        ("connect", lambda: dim_connect(origin, pois, address or "")),
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
        return 50, ["Elamiskvaliteet arvutamata – asukoha andmed puuduvad"], dims
    reasons = [r for _, _, r in scored]
    return total, reasons, dims
