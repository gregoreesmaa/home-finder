"""P4 KOTKAS air-emission avoidance dim (issue #533).

Source side for the "hooviõhk" buyer question (open issue #524 owns the
station side; P4-042 already names Keskkonnaagentuur stations as source
(3)): stations measure ambient air at a few points, these emission points
show WHERE it comes from. Complements — never duplicates — #524. Split-
slice contract: the P4-042 chimney-smoke leg stays scored where it lives
(dims_p4_paaste dim_smoke_chorus, #276/#350), named in reasons by pointer,
never rescored here. Group 7 air proxies (p61/p62) stay fallback cousins;
p4_kesk dims untouched (distinct keys, no double-scoring).

LIVE FEED VERDICT (checked 2026-09-16, polite one-off round, custom UA
`home-finder-research/0.1`, single GETs, no retries; aggregates only):
* GetCapabilities -> HTTP 200. Title "INSPIRE (PF) - Eesti heiteallikad
  õhku (WFS)", publisher Maa- ja Ruumiamet, CC0 (cleanest of the slate).
  One feature type: `PF_heiteallikad:PF.ProductionInstallation`.
* DescribeFeatureType -> HTTP 200. Attributes: inspireId localId/namespace/
  versionId, name, thematicId identifier+scheme, status (void), geom.
  NO pollutant/fuel/capacity columns anywhere: subtype slices are
  impossible, documented here, never invented.
* GetFeature resultType=hits (typeNames, the WFS 2.0 plural — `typeName`
  400s) -> numberMatched="8220" Estonia-wide; with
  srsName=EPSG:4326 + Harjumaa bbox 58.9,23.7,59.7,25.6 -> 2804 hits.
  Well above the <10-point no-map branch: the avoidance proxy ships.
* GetFeature count=1 outputFormat=json -> sample "Katlamaja"
  (Heiteallikas-HEIT0000008, KOTKAS register), geometry Point in native
  EPSG:3301 metres [616911.00, 6538107.99], `gml_description` "Last
  update: 2026-07-13" (fresh, IRREG feed). Status is void/unpopulated.

Geocoding path: coordinates ship natively (EPSG:3301, same L-EST97 family
as #494/#530/#531). This module carries the local stdlib inverse-LCC
copy (labelled ~1 m). The parse helper reads native-CRS GeoJSON (the
adapter may alternatively request srsName=EPSG:4326 — stated, not wired).

Dim (honest avoidance PROXY, hinnang — stack proximity is not measured
exposure, never "clean air"): nearest source <= 500 m -> 35, <= 1 km ->
50, <= 2 km -> 65, beyond -> NULL with EI OLE + Keskkonnaagentuur station
check (#524). Missing origin or no source POIs -> NULL with EI OLE.

Style mirrors sibling dims_p4_sportreg.py (#531): pure offline-tested
(origin, pois) -> (Optional[int], Estonian reason); no network here (the
annual harvest is a future adapter job; the reader takes GeoJSON text).
Helpers are local copies (no livability/sibling imports — cycle guard,
batch B3 PR #100 precedent).

Judgment calls (reviewable per AGENTS.md §7.5): bands invert the usual
scale on purpose (near = low score = avoid); reasons name the nearest
source (name + KOTKAS id) so the buyer can check what it is; CC0 data is
still attributed (Maa-amet/KOTKAS) in legend + docs. No KOTKAS login
flows, no permit-text NLP.

Integration (deliberately NOT done here): no livability hook, no WEIGHTS
change — existing tests pin set(WEIGHTS) exactly. Rebalancing stays one
joint change across all batches.
"""

import json
import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]

#: Avoidance bands: (radius_km, score). Near scores LOW (avoid); beyond
#: 2 km -> NULL (never "clean air").
AVOID_BANDS = ((0.5, 35), (1.0, 50), (2.0, 65))

#: POI kind (caller-side contract for harvested KOTKAS points).
EMISSION_KIND = "emission_source"

#: Feed identity (verified 2026-09-16, all HTTP 200).
EMISSIONS_WFS_URL = "https://inspire.geoportaal.ee/geoserver/PF_heiteallikad/wfs"
EMISSIONS_TYPENAME = "PF_heiteallikad:PF.ProductionInstallation"
EMISSIONS_USER_AGENT = (
    "home-finder-p4-emissions/1.0 (Estonia open-data annual adapter; "
    "polite single-pull, cache-first)"
)
#: IRREG feed, fresh 2026-07-13: at most one live pull per year.
EMISSIONS_CACHE_TTL_S = 365 * 86400
EMISSIONS_LICENCE = "CC0 1.0 (Maa- ja Ruumiamet / KOTKAS, attribution kept)"


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points (pure)."""
    r = 6371.0
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dla = math.radians(b[0] - a[0])
    dlo = math.radians(b[1] - a[1])
    h = (math.sin(dla / 2.0) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2.0) ** 2)
    return 2.0 * r * math.asin(min(1.0, math.sqrt(h)))


def _pois_of(pois: Optional[List[dict]], kind: str) -> List[dict]:
    out = []
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        if p.get("lat") is None or p.get("lon") is None:
            continue
        out.append(p)
    return out


def _nearest(origin: Tuple[float, float],
             pois: List[dict]) -> Tuple[Optional[dict], Optional[float]]:
    best, best_km = None, None
    for p in pois:
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if best_km is None or km < best_km:
            best, best_km = p, km
    return best, best_km


_LEST_A = 6378137.0
_LEST_F = 1 / 298.257222101
_LEST_E2 = 2 * _LEST_F - _LEST_F * _LEST_F
_LEST_E = math.sqrt(_LEST_E2)
_LEST_PHI0 = math.radians(57.5175539305556)
_LEST_LAM0 = math.radians(24.0)
_LEST_PHI1 = math.radians(59.3333333333333)
_LEST_PHI2 = math.radians(58.0)
_LEST_E0 = 500000.0
_LEST_N0 = 6375000.0


def _lest_m(phi: float) -> float:
    return math.cos(phi) / math.sqrt(1 - _LEST_E2 * math.sin(phi) ** 2)


def _lest_t(phi: float) -> float:
    s = _LEST_E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - s) / (1 + s)) ** (_LEST_E / 2)


_LEST_M1, _LEST_M2 = _lest_m(_LEST_PHI1), _lest_m(_LEST_PHI2)
_LEST_T1, _LEST_T2 = _lest_t(_LEST_PHI1), _lest_t(_LEST_PHI2)
_LEST_T0 = _lest_t(_LEST_PHI0)
_LEST_N = ((math.log(_LEST_M1) - math.log(_LEST_M2))
           / (math.log(_LEST_T1) - math.log(_LEST_T2)))
_LEST_FF = _LEST_M1 / (_LEST_N * _LEST_T1 ** _LEST_N)
_LEST_RHO0 = _LEST_A * _LEST_FF * _LEST_T0 ** _LEST_N


def lest97_to_wgs84(northing: float, easting: float) -> Tuple[float, float]:
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m. Local copy of
    scripts/build/batch_tervise.py. Raises ValueError on non-finite input
    (callers drop such features, never fake them)."""
    if not (math.isfinite(northing) and math.isfinite(easting)):
        raise ValueError("non-finite L-EST97 coordinate")
    rho = math.copysign(
        math.hypot(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0)),
        _LEST_N)
    theta = math.atan2(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0))
    t = (rho / (_LEST_A * _LEST_FF)) ** (1 / _LEST_N)
    lam = theta / _LEST_N + _LEST_LAM0
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(20):
        s = _LEST_E * math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - s) / (1 + s)) ** (_LEST_E / 2))
    return math.degrees(phi), math.degrees(lam)


def parse_production_installations_geojson(text: str) -> Tuple[List[dict], dict]:
    """Parse native-CRS (EPSG:3301) WFS GeoJSON into scorer POIs (pure).

    GeoJSON positions are [easting, northing] metres, projected via the
    local converter. Features without usable geometry are dropped with
    counts. Returns (pois, stats).
    """
    coll = json.loads(text)
    pois: List[dict] = []
    stats = {"rows": 0, "placed": 0, "dropped_no_xy": 0}
    feats = coll.get("features", []) if isinstance(coll, dict) else []
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        stats["rows"] += 1
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        props = feat.get("properties") or {}
        try:
            easting, northing = float(coords[0]), float(coords[1])
            lat, lon = lest97_to_wgs84(northing, easting)
        except (TypeError, ValueError, IndexError):
            stats["dropped_no_xy"] += 1
            continue
        pois.append({
            "kind": EMISSION_KIND, "lat": lat, "lon": lon,
            "name": props.get("name") or "",
            "kotkas_id": props.get("thematicid_thematicidentifier_identifier") or "",
        })
        stats["placed"] += 1
    return pois, stats


def _band_score(km: float) -> Optional[int]:
    for radius, pts in AVOID_BANDS:
        if km <= radius:
            return pts
    return None


def dim_emission_avoidance(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4 heiteallikad avoidance proxy: nearer source -> lower score."""
    mine = _pois_of(pois, EMISSION_KIND)
    if not origin:
        return None, ("Heiteallikate kaugus teadmata (EI OLE hinnangut): "
                      "aadress puudub — KOTKAS-e heiteallikate kaugus selgub "
                      "aadressi puhvrist, mitte tühjalt")
    if not mine:
        return None, ("Heiteallikate kaugus teadmata (EI OLE hinnangut): "
                      "hetktõmmises pole uhtki KOTKAS-e heiteallikat — "
                      "kontrolli tööstusparke kaardilt ja Keskkonnaagentuuri "
                      "õhuseire jaama (issue #524) lähimalt alalt")
    nearest, km = _nearest(origin, mine)
    assert nearest is not None and km is not None
    src = nearest.get("name") or "nimetu allikas"
    if nearest.get("kotkas_id"):
        src = "%s (KOTKAS %s)" % (src, nearest["kotkas_id"])
    score = _band_score(km)
    if score is None:
        return None, ("Lähim teadaolev heiteallikas %s on %.1f km kaugusel "
                      "(EI OLE puhta õhu hinnet — kaugus ei mõõda kokkupuudet): "
                      "tegelik õhukvaliteet selgub Keskkonnaagentuuri "
                      "õhuseire jaamast (#524), lõhn kohapealsel jalutuskäigul"
                      % (src, km))
    return score, ("Heiteallika-vältimise hinnang (mitte mõõdetud kokkupuude): "
                   "lähim teadaolev allikas %s on %.1f km linnulennult — "
                   "korsten/lõhn/tolm selgub Keskkonnaagentuuri jaamast "
                   "(#524) ja kohapealsel vaatlusel, ära feigi" % (src, km))


P4_EMISSIONS_DIMS = (
    ("emission_avoidance", "P4-042", dim_emission_avoidance),
)


def score_p4_emissions(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 emissions avoidance dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_EMISSIONS_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_EMISSIONS_DIMS}
