"""P4 EHIS school-proximity dims (issue #530).

Params (this module only):
* P4-011 family-buyer proximity question, school/kindergarten/hobby slices.

LIVE FEED VERDICT (checked 2026-09-16, polite one-off round, custom UA
`home-finder-research/0.1`, single GETs, no retries; aggregates only, raw
bodies never committed):
* `http://enda.ehis.ee/avaandmed/rest/hooned` -> HTTP 200, text/xml,
  1 093 076 B. 2180 `<hoone>` rows; 739 mention Harju maakond, of which
  703 carry `<koordinaatX>/<koordinaatY>` (L-EST97 metres, x = northing
  ~6.5-6.6M, y = easting ~0.5M) + `<ehrKood>` + `<adsOid>`/`<adsAdrId>` +
  `<aadress>`: 95.1% of Harjumaa rows placeable as-is, 36 without
  coordinates stay out (counted, never invented). `peahoone` jah/ei and
  `tegevusloaAsukoht` jah/ei travel per row.
* `http://enda.ehis.ee/avaandmed/rest/oppeasutused/-/-/-/-/-/-/-/-/-/-/0/0/XML`
  -> HTTP 200, text/xml, 12 628 175 B. 5689 `<oppeasutus>` rows with
  `<koolId>`, `<tyyp>`, `<alamTyyp>`, `<staatus>` (Registreeritud 3976 /
  Suletud 2217), structured `<juriidilineAadress>` (maakond/kov/asukoht).
  NO language-of-instruction column exists (no `oppekeel`/`keel` tag
  anywhere in 12.6 MB): language slices are impossible from this bulk,
  documented here, never guessed.
* `vastuseLoomiseAeg` on both pulls reads 2026-09-16 (today): the feed is
  live, not the dated-negative of docs/p4_ehis.md (which never probed the
  buildings bulk endpoint).

Type distribution (full-file counts, pinned by tests on fixtures):
* kool 804 "pohikool voi gumnaasium" -> school slice; 405 "lasteaed" +
  238 "koolieelne lasteasutus" + 118 "lastehoid" -> kindergarten slice;
  1231 "huvikool" (incl. 444 spordikool, 173 muusika- ja kunstikool
  alamTuup) -> hobby slice. 2516 "taienduskoolitusasutus" (adult training),
  114 "kutseoppeasutus", 38 "rakenduskorgkool", 16 "ulikool", 116
  "noortelaager" (seasonal camps), 88 "filiaal", 5 "Maaramata" stay
  UNSLICED (never scored here): adult/vocational/higher education is not
  the family-buyer proximity question, and seasonal camps are not weekly
  destinations. Suletud institutions are excluded even when their type
  matches (a closed school is not a proximity amenity).
* Overlap note: huvikool/spordikool rows are SCHOOLS in the education
  register; Spordiregister venues (#531) are PHYSICAL VENUES. Distinct
  sources, distinct dim keys, no double-score of one signal.

Geocoding path: coordinates ship in the feed (L-EST97, same family as the
vtiav ujulad bulk and the #494 bathing-water precedent). This module
carries a local stdlib copy of the inverse-LCC projector from
scripts/build/batch_tervise.py (labelled ~1 m, GRS80~WGS84 datum gap
stamped, never hidden). Rows without coordinates (36/739 Harju) and rows
whose institution is Suletud or unsliced stay out with counts — an AKS/EHR
join would only add what the feed already places.

Bands (walk-graph honest proxy: straight-line haversine, so reasons say
"hinnang (linnulennult, mitte marsruut-aeg)"): nearest sliced building
<= 500 m -> 80, <= 1 km -> 65, <= 2 km -> 50, beyond -> NULL (never "bad
school", only distance; quality/capacity stays the buyer check while the
per-linnaosa table of docs/p4_ehis.md is missing). Missing origin or no
sliced POIs of that kind -> NULL with an EI OLE reason + buyer check.

Style mirrors services/scoring/livability.py and sibling batch
dims_p4_tervise.py (#289/#362): scorers are pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
nowhere in this module: the polite harvest (quarterly is plenty for
buildings) is a future adapter job; parse helpers below take XML text.

Helpers are local copies (not imported from livability, batch_tervise or
sibling batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* peahoone/teigevusloaAsukoht are NOT scored: every building of a sliced
  institution counts (a kindergarten in a shared building is still the
  kindergarten). Filtering to peahoone would drop real destinations.
* No language slices: the bulk has no language column, so Estonian- vs
  Russian-language proximity cannot be joined — stated, not worked around.
* Licensed CC BY-SA 3.0: derived-data notes attribute EHIS/Haridusministeerium
  + share-alike (see docs/p4_ehis_map.md). Quarterly harvest is plenty.

Integration (deliberately NOT done here): no livability.OVERPASS_QUERY /
livability._POI_KIND extension, no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

import math
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Proximity bands: (radius_km, score). Beyond 2 km -> NULL (distance only).
PROX_BANDS = ((0.5, 80), (1.0, 65), (2.0, 50))

#: POI kinds (caller-side contracts for harvested EHIS buildings).
SCHOOL_KIND = "ehis_school"
KINDERGARTEN_KIND = "ehis_kindergarten"
HOBBY_KIND = "ehis_hobby"

#: Institution-type -> slice. Unlisted tyyp values read as None (never guessed).
TYPE_SLICES = {
    "pohikool voi gumnaasium": "school",
    "lasteaed": "kindergarten",
    "koolieelne lasteasutus": "kindergarten",
    "lastehoid": "kindergarten",
    "huvikool": "hobby",
}

#: Only active institutions place buildings (a closed school is not proximity).
ACTIVE_STATUS = "Registreeritud"

#: Feed identity (verified 2026-09-16, HTTP 200, `vastuseLoomiseAeg` = pull day).
EHIS_HOONED_URL = "http://enda.ehis.ee/avaandmed/rest/hooned"
EHIS_OPPEASUTUSED_URL = (
    "http://enda.ehis.ee/avaandmed/rest/oppeasutused/-/-/-/-/-/-/-/-/-/-/0/0/XML"
)
EHIS_USER_AGENT = (
    "home-finder-p4-ehis-map/1.0 (Estonia open-data quarterly adapter; "
    "polite single-pull, cache-first)"
)
#: Buildings change slowly: at most one live pull per quarter, cache wins inside.
EHIS_CACHE_TTL_S = 90 * 86400
EHIS_LICENCE = "CC BY-SA 3.0 (EHIS / Haridus- ja Teadusministeerium)"


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

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
    best = None
    best_km = None
    for p in pois:
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if best_km is None or km < best_km:
            best, best_km = p, km
    return best, best_km


# ---------------------------------------------------------------------------
# L-EST97 (EPSG:3301) -> WGS84, labelled approximate (~1 m). Local copy of
# scripts/build/batch_tervise.py (stdlib inverse-LCC, Maa-amet constants).
# ---------------------------------------------------------------------------

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

#: Accuracy label stamped on reasons (reviewable, never hidden).
LEST97_ACCURACY_LABEL = (
    "L-EST97 (EPSG:3301) inverse-LCC poordumine, GRS80~WGS84 "
    "daatumi vahe ~1 m — punktid on ausad ~1 m tapsusega"
)


def lest97_to_wgs84(northing: float, easting: float) -> Tuple[float, float]:
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m (see above).

    Feed convention: <koordinaatX> is the northing (~6.4-6.6M),
    <koordinaatY> the easting (~0.37-0.74M). Raises ValueError on
    non-finite input (callers drop such rows, never fake them).
    """
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


# ---------------------------------------------------------------------------
# Pure offline readers (hermetic; parse harvested XML text, no network).
# ---------------------------------------------------------------------------

def _text(el: Optional[ET.Element], tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def type_slice(tyyp: Optional[str], staatus: Optional[str]) -> Optional[str]:
    """Map an institution (tyyp, staatus) to its proximity slice (pure).

    Only Registreeritud institutions slice; Suletud and unlisted types
    read as None (never guessed, never scored).
    """
    if staatus != ACTIVE_STATUS:
        return None
    if not isinstance(tyyp, str):
        return None
    return TYPE_SLICES.get(tyyp.strip().lower().replace("õ", "o").replace("ü", "u")
                           .replace("ö", "o").replace("ä", "a"))


def parse_oppeasutused_xml(text: str) -> Dict[str, dict]:
    """Parse the institutions bulk into {koolId: {tyyp, slice, status}} (pure)."""
    root = ET.fromstring(text)
    out: Dict[str, dict] = {}
    for node in root.iter("oppeasutus"):
        kid = _text(node, "koolId")
        if not kid:
            continue
        tyyp = _text(node, "tyyp")
        staatus = _text(node, "staatus")
        out[kid] = {"tyyp": tyyp, "status": staatus,
                    "slice": type_slice(tyyp, staatus)}
    return out


_SLICE_KINDS = {"school": SCHOOL_KIND, "kindergarten": KINDERGARTEN_KIND,
                "hobby": HOBBY_KIND}


def parse_hooned_xml(text: str, type_by_id: Dict[str, dict]) -> Tuple[List[dict], dict]:
    """Parse the buildings bulk into scorer POIs (pure).

    Joins each <hoone> to its institution slice via <oppeasutusId> (the
    <kool> wrapper carries it). Rows without coordinates, with unknown /
    Suletud institutions, or with unsliced types are dropped with counts —
    never invented coordinates, never guessed slices. Returns
    (pois, stats).
    """
    root = ET.fromstring(text)
    pois: List[dict] = []
    stats = {"rows": 0, "placed": 0, "dropped_no_xy": 0,
             "dropped_closed": 0, "dropped_other_type": 0}
    for kool in root.iter("kool"):
        kid = _text(kool, "oppeasutusId")
        info = type_by_id.get(kid, {})
        sl = info.get("slice")
        for home in kool.findall("./hooned/hoone"):
            stats["rows"] += 1
            if sl not in _SLICE_KINDS:
                if info.get("status") and info.get("status") != ACTIVE_STATUS:
                    stats["dropped_closed"] += 1
                else:
                    stats["dropped_other_type"] += 1
                continue
            x_raw = _text(home, "koordinaatX").replace(",", ".")
            y_raw = _text(home, "koordinaatY").replace(",", ".")
            try:
                lat, lon = lest97_to_wgs84(float(x_raw), float(y_raw))
            except (ValueError, TypeError):
                stats["dropped_no_xy"] += 1
                continue
            pois.append({
                "kind": _SLICE_KINDS[sl],
                "lat": lat, "lon": lon,
                "name": _text(home, "nimetus") or info.get("name", ""),
                "ehr": _text(home, "ehrKood"),
                "ads": _text(home, "adsAdrId"),
                "address": _text(home, "aadress"),
            })
            stats["placed"] += 1
    return pois, stats


# ---------------------------------------------------------------------------
# Scorers: measured register proximity bands, NULL beyond 2 km.
# ---------------------------------------------------------------------------

def _band_score(km: float) -> Optional[int]:
    for radius, pts in PROX_BANDS:
        if km <= radius:
            return pts
    return None


def _slice_dim(kind: str, label: str, check: str,
               origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    mine = _pois_of(pois, kind)
    if not origin:
        return None, ("%s teadmata (EI OLE hinnangut): aadress puudub — "
                      "EHIS-e registri hoonete kaugus selgub aadressi "
                      "puhvrist, mitte tühjalt" % label)
    if not mine:
        return None, ("%s teadmata (EI OLE hinnangut): hetktõmmises pole "
                      "uhtki %s hoonet — %s; kaugemal kui 2 km pole "
                      "samuti hinne, ainult kaugus (kvaliteet ja järjekord "
                      "selguvad ostja kontrollist, ära feigi)"
                      % (label, label.lower(), check))
    nearest, km = _nearest(origin, mine)
    assert nearest is not None and km is not None
    score = _band_score(km)
    if score is None:
        return None, ("%s kaugemal kui 2 km (EI OLE hinnet, ainult kaugus): "
                      "lähim mõõdetud EHIS-e hoone %s on %.1f km "
                      "linnulennult (hinnang, mitte marsruut) — kvaliteet "
                      "ega mahutavus ei ole kauguse hinne, kontrolli "
                      "kohapeal" % (label, nearest.get("name") or "teadmata", km))
    return score, ("%s: lähim mõõdetud EHIS-e hoone %s on %.1f km "
                   "linnulennult (hinnang, mitte marsruut-aeg) — kauguse, "
                   "mitte kvaliteedi hinne; järjekord/mahutavus selgub "
                   "ostja kontrollist" % (label, nearest.get("name") or "teadmata", km))


def dim_school_proximity(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-011 school slice: nearest põhikool/gümnaasium building bands."""
    return _slice_dim(SCHOOL_KIND, "Lähim kool",
                      "kontrolli teeninduspiirkonda kooli kodulehelt", origin, pois)


def dim_kindergarten_proximity(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-011 kindergarten slice: nearest lasteaed/lastehoid building bands."""
    return _slice_dim(KINDERGARTEN_KIND, "Lähim lasteaed",
                      "kontrolli järjekorda Haridusameti iseteenindusest",
                      origin, pois)


def dim_hobby_proximity(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-011 hobby-school slice: nearest huvikool building bands."""
    return _slice_dim(HOBBY_KIND, "Lähim huvikool",
                      "kontrolli ringide vabu kohti huvikooli kodulehelt",
                      origin, pois)


P4_EHIS_MAP_DIMS = (
    ("school_proximity", "P4-011", dim_school_proximity),
    ("kindergarten_proximity", "P4-011", dim_kindergarten_proximity),
    ("hobby_proximity", "P4-011", dim_hobby_proximity),
)


def score_p4_ehis_map(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All three P4 EHIS proximity dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_EHIS_MAP_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_EHIS_MAP_DIMS}
