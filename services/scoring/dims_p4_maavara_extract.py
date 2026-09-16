"""P4 maavara-extract dims (issue #545): active extraction + exploration proximity.

Two per-parcel zone-membership scorer dims (polygons only, never gradients):

* ``extraction_proximity`` -- ACTIVE extraction area (mäeeraldis):
  inside -> 25; coarse near-band (<= 2 km, vertex-haversine, labelled
  "jäme") -> 45; outside -> NULL.
* ``exploration_watch`` -- exploration area (uuringuala): inside -> dated
  watch-flag 55 (NEVER a full penalty -- exploration != permit); outside
  -> NULL.

SAME-OR-DIFFERENT VERDICT vs ``dims_p4_maa_subsurface`` (#248/#332):
DIFFERENT -- proven below. The subsurface module joins
``maaamet:maavarad_gbmv_levialad`` / ``leiukohad`` /
``perspektiivalad`` on the Keskkonnaagentuur WFS
(``gsavalik.envir.ee/geoserver/wfs``): mineral DISTRIBUTION areas, find
sites, prospective areas. THIS module joins ``ms:maeeraldis_aktiivne`` /
``ms:maeeraldis_taotletav`` (+ ``_tm_`` peat variants) and
``ms:Aktiivne_uuringuala`` / ``ms:Taotletav_uuringuala`` on the Maa-amet
MapServer WFS (``teenus.maaamet.ee/ows/maardlad``): permitted EXTRACTION
areas (with permit number/expiry/operator) and licensed EXPLORATION
areas. Different services, different type names, different legal
semantics (permit acts vs occurrence mapping) -- the two legs the
subsurface list does NOT name. No duplicate close.

OPENNESS VERDICT (probed 2026-09-16, polite one-off round, custom UA
``home-finder openness-check (one-off, few pages max, no scrape)``,
single GETs with 2 s pacing, ``--max-time 30``; raw bodies kept at
/tmp/hf-probes/, never committed):

* ``teenus.maaamet.ee/ows/maardlad`` GetCapabilities -> HTTP 200
  (97 KB): 70 types -- extraction: ``ms:maeeraldis_aktiivne``,
  ``ms:maeeraldis_taotletav``, ``ms:maeeraldis_tm_aktiivne``,
  ``ms:maeeraldis_tm_taotletav``; exploration: ``ms:Aktiivne_uuringuala``,
  ``ms:Taotletav_uuringuala``; plus per-mineral deposits (``Liiv``,
  ``Lubjakivi``, ``Kruus``, ``Turvas``...), ``*_levi`` distribution and
  ``*_persp`` prospective layers, ``maardlapiir``, reserve (``varud_*``)
  and recultivation (``ta_*``) slices. CRS EPSG:3301 + EPSG:4326.
  Licence CC BY 4.0 (issue-stated; attribution below).
* DescribeFeatureType (both headline types) -> HTTP 200 (4.4 KB):
  extraction attrs ``ME_ID``, ``ME_KOOD``, ``NIMETUS``, ``LOA_NUMBER``,
  ``LOA_ALGUS``, ``LOA_VALJAS``, ``KAEVANDAJA`` (operator), ``PINDALA``,
  ``ERALD_VARU``, ``KAS_EESM``, ``LOA_LOPP`` (permit expiry, YYYYMMDD),
  ``REKULT``, ``STAATUS``, ``ME_OLEK``, ``MAAVARA``; exploration attrs
  ``U_ALA_ID``, ``U_ALA_NIMI``, ``MAARDLA``, ``MAAVARAD``, ``LOA_NR``,
  ``LOA_ALGUS``, ``LOA_LOPP``, ``U_ALA_OLEK``, ``STAATUS``.
* ONE live sample row (maxfeatures=1, GML -- MapServer has no JSON
  output): ``Koguva dolokivikarjäär``, ME_OLEK ``aktiivne``, STAATUS
  ``K``, LOA_NUMBER ``L.MK/327053``, LOA_LOPP ``20401216``,
  KAEVANDAJA ``Muhu Vallavalitsus`` -- the active-permit join is proven
  on live bytes. CRS CAVEAT: the sample envelope/vertices are L-EST97
  metres (6 497 xxx / 447 xxx) DESPITE ``srsname=EPSG:4326`` -- the
  service ignores the reprojection ask. Projection L-EST97 -> WGS84 is an
  explicit upstream step (same caveat as the trans accident CSV);
  fixtures carry WGS84 directly.
* Harjumaa-window hits (L-EST97 bbox, resultType=hits -- counts only, no
  rows): ``maeeraldis_aktiivne`` = 198, ``Aktiivne_uuringuala`` = 31,
  ``maeeraldis_taotletav`` = 78 (an EPSG:4326 bbox returned 0 -- the
  native-CRS proof above explains why).

ATTRIBUTION: Maa- ja Ruumiamet (Land and Spatial Administration),
licence CC BY 4.0. Daily feed.

HONESTY (AGENTS.md section 7.2): outside every extraction/exploration
polygon stays NULL (never "no quarry"). Only permit-ACTIVE extraction
scores (``ME_OLEK == "aktiivne"`` AND permit not expired); unknown or
expired status NEVER scores as a quarry. Exploration NEVER scores as a
quarry (flag 55 max, dated, with the Keskkonnaamet/KOTKAS + kohapealne
blast-day check). Every scored reason prints its components (area name,
operator/permit, status); every NULL reason says "EI OLE". Transport
errors are never cached as data: this module makes NO network calls at
all (pinned by test via source inspection).

EXPIRY HANDLING: ``LOA_LOPP`` ``YYYYMMDD``; parseable past date ->
treated as inactive (skipped); missing/unparseable -> treated as UNKNOWN
and skipped for extraction (never score unknown as active), while
exploration keeps its weak watch-flag ONLY when no explicit inactive
marker is present (see ``_INACTIVE_MARKERS`` -- provisional, values
beyond the live sample are unprobed).

Style mirrors services/scoring/dims_p4_maa_subsurface.py (#248/#332):
pure offline scorers over caller-supplied polygons ([[lon, lat], ...] in
EPSG:4326), local helpers (no livability import -- that would turn the
future central hook into a cycle). P4-054 quarry-truck leg in
``dims_p4_trans`` stays the traffic cousin (distinct keys). No blast
timetables (no schedule dataset exists -- stays buyer check), no
deposit-reserve economics (dimensions/reserves are context, not scores).
No shared-file edits: 3 new files only.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Near-band (<= 2 km) reuses the subsurface coarse convention
  (nearest-VERTEX haversine, labelled "jäme"): it can only overstate the
  distance (under-flag), never invent quiet.
* ``taotletav`` (applied-for) extraction counts as exploration-grade
  watch, never as active extraction -- an application is not a permit.
* Single-letter STAATUS values beyond the live sample (``K``) are NOT
  trusted alone: activity requires ``ME_OLEK == "aktiivne"``.

Integration (deliberately NOT done here): WEIGHTS/livability/layers
rebalancing stays one joint change across all batches (existing tests pin
set(WEIGHTS) exactly).
"""

import datetime as _dt
import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# Contract constants.
# ---------------------------------------------------------------------------

#: Inside an active extraction area (dust/blast/truck exposure today).
EXTRACTION_INSIDE = 25

#: Coarse near-band for active extraction (vertex-haversine, "jäme").
EXTRACTION_NEAR_KM = 2.0
EXTRACTION_NEAR = 45

#: Inside an exploration area: dated watch-flag, NEVER a quarry penalty.
EXPLORATION_WATCH = 55

#: Active-extraction marker (live bytes: Koguva ME_OLEK "aktiivne").
ACTIVE_OLEK = "aktiivne"

#: Explicit inactive markers for exploration (PROVISIONAL -- only the
#: schema + one extraction sample were pulled; anything unlisted is
#: treated as unknown and keeps the weak watch-flag, stated in code).
_INACTIVE_MARKERS = ("lõppenud", "kehtetu", "tühistatud", "lõpetatud",
                     "inactive", "expired")


# ---------------------------------------------------------------------------
# Local pure helpers (subsurface-shaped; local to avoid import cycles).
# ---------------------------------------------------------------------------

def point_in_polygon(lon: float, lat: float,
                     ring: List[List[float]]) -> bool:
    """Ray-casting containment. Degenerate rings match nothing."""
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
    """Great-circle distance in km (spherical earth -- coarse by design)."""
    rad = math.pi / 180.0
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = (math.sin(dlat / 2.0) ** 2
         + math.cos(lat1 * rad) * math.cos(lat2 * rad)
         * math.sin(dlon / 2.0) ** 2)
    return 2.0 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def nearest_vertex_km(lon: float, lat: float,
                      polygons: List[List[List[float]]]) -> Optional[float]:
    """Haversine to the nearest polygon vertex (coarse proxy -- overstates
    true edge distance, so it can only under-flag). None when empty."""
    best: Optional[float] = None
    for ring in polygons or []:
        for p in ring or []:
            if not (isinstance(p, (list, tuple)) and len(p) >= 2):
                continue
            try:
                d = haversine_km(lon, lat, float(p[0]), float(p[1]))
            except (TypeError, ValueError):
                continue
            if best is None or d < best:
                best = d
    return best


def parse_loa_lopp(raw: object) -> Optional[_dt.date]:
    """Parse permit-expiry ``LOA_LOPP`` (``YYYYMMDD``) to a date.

    Missing/unparseable -> None (callers treat that as unknown, which for
    EXTRACTION means skip -- never score unknown as active).
    """
    if isinstance(raw, bool):
        return None
    try:
        text = str(raw).strip()
    except Exception:
        return None
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return _dt.date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _is_active_extraction(attrs: dict,
                          today: _dt.date) -> bool:
    """Active-permit rule: ME_OLEK == "aktiivne" AND permit not expired.

    Unknown olek, missing olek, or expired/unparseable LOA_LOPP with no
    active marker -> False (never score unknown as a quarry).
    """
    olek = str((attrs or {}).get("ME_OLEK", "")
               or (attrs or {}).get("olek", "")).strip().lower()
    if olek != ACTIVE_OLEK:
        return False
    expiry = parse_loa_lopp((attrs or {}).get("LOA_LOPP"))
    if expiry is not None and expiry < today:
        return False
    if expiry is None and (attrs or {}).get("LOA_LOPP") not in (None, ""):
        return False  # unparseable expiry on an "active" row: distrust
    return True


def _is_live_exploration(attrs: dict, today: _dt.date) -> bool:
    """Live-exploration rule: no explicit inactive marker AND permit not
    expired. Unknown olek keeps the WEAK watch-flag (stated); an expired
    LOA_LOPP drops it."""
    blob = " ".join(str((attrs or {}).get(k, "")) for k in (
        "U_ALA_OLEK", "STAATUS", "olek", "staatus")).lower()
    if any(marker in blob for marker in _INACTIVE_MARKERS):
        return False
    expiry = parse_loa_lopp((attrs or {}).get("LOA_LOPP"))
    if expiry is not None and expiry < today:
        return False
    return True


NO_TIMETABLE = ("lõhkamiste ajagraafiku jalga EI OLE "
                "(Keskkonnaameti load ei ole avaandmed)")


# ---------------------------------------------------------------------------
# Dim 1: active extraction proximity (today-leg: dust, blast days, trucks).
#
# extractions: [{"polygons": [rings], "NIMETUS": str, "ME_OLEK": str,
#   "STAATUS": str, "LOA_LOPP": str, "LOA_NUMBER": str,
#   "KAEVANDAJA": str, "MAAVARA": str}]
# ---------------------------------------------------------------------------

def dim_extraction_proximity(parcel: Optional[dict],
                             extractions: Optional[List[dict]],
                             today: Optional[_dt.date] = None) -> Score:
    """Active-extraction reading: inside -> 25, coarse near-band -> 45,
    anything further -> NULL (a missing polygon is not proof of quiet)."""
    now = today or _dt.date.today()
    parcel = parcel or {}
    lon, lat = parcel.get("lon"), parcel.get("lat")
    if not isinstance(lon, (int, float)) \
            or not isinstance(lat, (int, float)):
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "kaevandus-puhvrit ei saa arvutada -- täienda "
                      "koordinaat, ära feigi")
    if not extractions:
        return None, ("Mäeeraldiste kihti (maeeraldis_aktiivne) EI OLE "
                      "laetud (hinnang puudub): puhver vajab maardlate "
                      "liidestust -- tõsta puhver, ära feigi")
    live = [e for e in extractions
            if _is_active_extraction((e or {}).get("attrs", e), now)]
    if not live:
        return None, ("Aktiivset mäeeraldist EI OLE teada (hinnang "
                      "puudub): kas kiht on tühi või load on aegunud/"
                      "tundmatud -- aegunud/tundmatut karjääriks EI OLE "
                      "loetud; kontrolli maardlate kaardirakendusest, "
                      "ära feigi")
    for ext in live:
        polys = (ext or {}).get("polygons") or []
        if any(point_in_polygon(lon, lat, ring) for ring in polys):
            attrs = (ext or {}).get("attrs", ext)
            return EXTRACTION_INSIDE, (
                "Krunt aktiivses mäeeraldises '%s' (luba %s, kaevandaja "
                "%s): karjääri-mühina hinnang 25/100; %s; kohapealne "
                "lõhkamispäevade kontroll + Keskkonnaamet/KOTKAS"
                % (attrs.get("NIMETUS", "?"),
                   attrs.get("LOA_NUMBER", "?"),
                   attrs.get("KAEVANDAJA", "?"), NO_TIMETABLE))
    best: Optional[float] = None
    best_name = "?"
    for ext in live:
        d = nearest_vertex_km(lon, lat, (ext or {}).get("polygons") or [])
        if d is not None and (best is None or d < best):
            attrs = (ext or {}).get("attrs", ext)
            best, best_name = d, attrs.get("NIMETUS", "?")
    if best is not None and best <= EXTRACTION_NEAR_KM:
        return EXTRACTION_NEAR, ("Lähim aktiivne mäeraldis '%s' %.1f km "
                                 "(jäme tipp-kauguse hinnang): "
                                 "veohooaja-mühina hinnang 45/100; %s; "
                                 "allikas Maa- ja Ruumiamet CC BY 4.0"
                                 % (best_name, best, NO_TIMETABLE))
    return None, ("Aktiivsete mäeraldiste puhvrit (<= %.0f km) EI OLE "
                  "(hinnang puudub): kaugus ei tõesta vaikust -- "
                  "müra-hinnang puudub, ära feigi" % EXTRACTION_NEAR_KM)


# ---------------------------------------------------------------------------
# Dim 2: exploration watch-flag (3-year-leg: the quarry of 3 years hence).
#
# explorations: [{"polygons": [rings], "U_ALA_NIMI": str,
#   "U_ALA_OLEK": str, "STAATUS": str, "LOA_LOPP": str, "LOA_NR": str}]
# ---------------------------------------------------------------------------

def dim_exploration_watch(parcel: Optional[dict],
                          explorations: Optional[List[dict]],
                          today: Optional[_dt.date] = None) -> Score:
    """Exploration-area watch: inside a live area -> dated flag 55 (never
    a quarry penalty -- exploration != permit); outside -> NULL."""
    now = today or _dt.date.today()
    parcel = parcel or {}
    lon, lat = parcel.get("lon"), parcel.get("lat")
    if not isinstance(lon, (int, float)) \
            or not isinstance(lat, (int, float)):
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "uuringuala-liidetust ei saa arvutada -- täienda "
                      "koordinaat, ära feigi")
    if not explorations:
        return None, ("Uuringualade kihti (Aktiivne_uuringuala) EI OLE "
                      "laetud (hinnang puudub): valve vajab maardlate "
                      "liidestust -- kontrolli maardlate "
                      "kaardirakendusest, ära feigi")
    for exp in explorations:
        polys = (exp or {}).get("polygons") or []
        if not any(point_in_polygon(lon, lat, ring) for ring in polys):
            continue
        attrs = (exp or {}).get("attrs", exp)
        if not _is_live_exploration(attrs, now):
            continue
        return EXPLORATION_WATCH, (
            "Krunt uuringualal '%s' (luba %s, %s): valve-hinnang "
            "55/100, dateeritud -- uuring EI OLE kaevandusluba "
            "(täis-mõju EI OLE hinnatud); kontrolli Keskkonnaamet/"
            "KOTKAS menetlusi + kohapealset seisu, ära feigi"
            % (attrs.get("U_ALA_NIMI", attrs.get("NIMETUS", "?")),
               attrs.get("LOA_NR", attrs.get("LOA_NUMBER", "?")),
               attrs.get("MAAVARA", attrs.get("MAAVARAD", "?"))))
    return None, ("Elujõulist uuringuala krundil EI OLE teada (hinnang "
                  "puudub): väljaspool uuringualasid jääb teadmata, "
                  "mitte karjäärivabaks -- kontrolli maardlate "
                  "kaardirakendusest, ära feigi")


P4_MAAVARA_EXTRACT_DIMS = (
    ("extraction_proximity", dim_extraction_proximity),
    ("exploration_watch", dim_exploration_watch),
)


def score_p4_maavara_extract(parcel: Optional[dict],
                             extractions: Optional[List[dict]] = None,
                             explorations: Optional[List[dict]] = None,
                             today: Optional[_dt.date] = None) -> Dict[
                                 str, Optional[int]]:
    """Both P4 maavara-extract dims for one parcel (entry point for the
    weight-rebalance follow-up)."""
    return {
        "extraction_proximity": dim_extraction_proximity(
            parcel, extractions, today)[0],
        "exploration_watch": dim_exploration_watch(
            parcel, explorations, today)[0],
    }
