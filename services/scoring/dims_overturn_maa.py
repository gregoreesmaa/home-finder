"""Overturn [Maa-amet WFS]: G3 parcels/KKIS/maardlad + G4 partials (issue #235).

G3 no-map set (p29 lot size, p68 soil, p71 easements, p75 boundaries)
FOLDS IN G4 partials by data source: p76/p229 mineral rights (maardlad
proximity as weak hinnang) + p364 ground lease (cadastre ownership form).
Seven honest per-parcel dims off the verified-open WFS endpoint
``gsavalik.envir.ee/geoserver/wfs`` (parameters3.md sections 5.3/5.4
name it as the protocol) -- full probe evidence in docs/overturn_maa.md.

VERIFIED-OPEN LAYERS (probed 2026-09-13, polite single GETs, count<=100,
contact UA, cached /tmp/hf-235-maa-wfs/, never committed):
* kataster:ky_kehtiv -- valid parcels; fields tunnus (join key), pindala
  (m2, p29), omvorm (Eraomand/Munitsipaalomand/Riigiomand observed live
  over central Tallinn, p364), siht1 (ELAMUMAA/TRANSPORDIMAA/ARIMAA/...).
* kataster:ky_omandivorm -- same parcel fields incl. omvorm (p364 leg).
* kitsendus_suunatud:kma_avalik_asjaoigus (+ the kma_avalik_* family:
  elekter/gaas/side/transport/veekogu/...) -- public KKIS restriction
  polygons; fields nimi/klass/voond_liik_id_vaartus (p71 join). The rule
  text leg is thin (reegel None in the live sample), so p71 scores a
  hit COUNT, never rule depth.
* eKataster:moodistuspunktid -- survey points; piirinael markers with
  kehtiv/kehtetu + paigaldus state (p75 weak hint: recorded, not found).
* veeveeb:mullad_boniteet -- soil polygons; mullaklass in {hea, halb},
  vintage 2017-03-03 (p68 weak class join -- fertility, not bearing).
* maaamet:maavarad_gbmv_levialad / leiukohad -- deposit areas; evidence
  already in docs/p4_maa_subsurface.md (cited, not re-pulled here out
  of politeness). p76/p229 weak hinnang only: deposits nearby, never
  this parcel's severance.

DATED NEGATIVES (verdict stays, documented in docs/overturn_maa.md):
the 03B/C/D/E remainder (p183/p184/p201/p228/p251/p254/p256/p258/p273/
p277/p331/p337/p339/p397/p400) has no joinable layer in the 1091-name
GetCapabilities search; maaamet:EHITUSGEOLOOGIA_ALA_* is a study-area
register (author/year/depth), not a parcel soil class.

HONESTY (AGENTS.md section 7.2): every scored shape here is a PER-PARCEL
JOIN (parcel record field, point-in-polygon containment, or a labelled
coarse vertex proxy) -- never a distance gradient, never interpolation,
never a heat-coloured guess. Missing parcel, missing snapshot, or a
registry-only fact stays NULL ("EI OLE") with an Estonian reason naming
the concrete check -- never a faked number. Transport errors in
fetch_cached are NEVER cached as data; HTTP 429 is a stop signal, not a
retry dare (AGENTS.md 7.2/7.4).

Style: pure offline scorers (parcel, joins...) -> (Optional[int 0..100],
Estonian reason), mirroring dims_p4_maa_subsurface.py (#248/#332).
Network lives ONLY in fetch_cached / fetch_layer (polite single-GET +
file cache + TTL); tests never touch the network. No livability/WEIGHTS/
layers integration here -- rebalancing stays one joint change across
batches (existing tests pin WEIGHTS). No dims_group03*.py, no sibling
P4 maa module, and no shared file is touched: this module only READS the
same open endpoint into its own cache.

Boundary vs sibling batches (no double-scoring, no overlap):
* P4-004 (dims_p4_maa_kataster) owns the closing-BLOCK question
  (arest/keelumarge -> notary checkpoint); p71 here owns the USE-BURDEN
  count off the public KKIS polygons. Same source family, disjoint
  questions -- the rebalance follow-up must weight only one per parcel.
* P4-054 quarry_buffer (dims_p4_maa_subsurface) owns blast/truck NOISE
  off the same leviala polygons; p76/p229 here own the RIGHTS-severance
  hint. Noise and title are disjoint questions.
* P4-016 eng_geology (dims_p4_maa_subsurface) owns the turvas/karst/alvar
  CLASS; p68 here scores only the agricultural bonitet class (weaker,
  capped lower) and names the EGT leg as still missing.
* G03 dim_lot_size (dims_group03) scores the LISTING record; p29 here
  scores the CADASTRE pindala with the same Tallinn band, so the parcel
  join fills p29 when the listing record lacks it.
* Helpers (point_in_polygon, haversine, band) are local copies, not
  imported from sibling batches: a future central hook may import this
  module alongside them, and importing any of them here would turn that
  into a cycle (same precedent as batch B3, PR #100, and #240).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Score bands are coarse first-cut judgments (challengeable, dull by
  design). p29 reuses the G03 Tallinn band [(400,45),(800,65),(1500,80)]
  so the two p29 legs cannot disagree on the same square metres.
* p68 hea->65 / halb->45: bonitet is fertility, not bearing capacity,
  so even "hea" never clears 65; the turvas/karst class (P4-016 leg)
  and a geotechnical survey stay named-missing.
* p71 0 hits->70 (weak-good ceiling: the public layer is generalised,
  kataster-module precedent), 1-2->60, 3+->40. [] means "snapshot
  searched, nothing hit"; None means "no snapshot" (NULL).
* p75 >=2 valid markers->65 / 0-1->45: RECORDED markers, never found
  ones -- the reason says "kirjas", and the on-site check stays.
  Threshold 2 is a dull minimum (a rectangle has 4 corners); challenge
  with marker-density data.
* p76 inside->50 / near(<=2 km vertex proxy)->60 / far->NULL (absence
  of a polygon proves nothing about severance). p229 inside->45 /
  outside->NULL (no near-band: severance is a deed fact, deposits
  nearby cannot even hint it from afar; the RIK extract stays named).
* p364 Eraomand->70 / Riigi/Munitsipaalomand->50 + hoonestus-check /
  unknown->NULL. Municipal/state land is OFTEN (not always) leased, so
  50 is suspicion, never a verdict; lease TERMS need the RIK extract.
* TTLs: cadastre + KKIS + survey points 30 d (parameters3.md section
  5.3: monthly cadastre update); soil bonitet + maardlad 365 d (static
  vintage layers, annual re-probe). count stays at 100/req
  (parameters3.md section 5.3 politeness cap).

Parcel record schema (one dict per listing, built from the cached
kataster:ky_kehtiv pull; every field optional, missing -> NULL leg):
* tunnus: "65301:001:0453" (katastritunnus, the join key)
* pindala: float m2 (ky_kehtiv.pindala)
* omvorm: "Eraomand" | "Riigiomand" | "Munitsipaalomand" | None
* siht1: "ELAMUMAA" | ... (rides along in reasons)
* lon/lat: parcel point for the polygon joins
* mullaklass: "hea" | "halb" | None (veeveeb:mullad_boniteet join)
* markers: int | None (count of valid eKataster boundary markers)
"""

import datetime as _dt
import math
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Hunt/verdict date (2026-09-13) -- the day the polite WFS probes ran.
VERDICT_DATE = "2026-09-13"

#: Re-check the dated negatives (03B/C/D/E layer search + soil vintage +
#: KKIS rule-text leg) no later than this date.
RECHECK_AFTER = "2027-03-13"

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (issue #235 acceptance criterion 1).
# ---------------------------------------------------------------------------

WFS_BASE = "https://gsavalik.envir.ee/geoserver/wfs"

#: Verified-open layers (2026-09-13 evidence in docs/overturn_maa.md).
OVERTURN_LAYERS = {
    # G3 parcel legs (p29 area, p364 ownership, p75 marker join key).
    "parcels": "kataster:ky_kehtiv",
    "ownership": "kataster:ky_omandivorm",
    # G3 KKIS leg (p71 use-burden count; one family member shown, the
    # kma_avalik_* / kpo_avalik_* / kmakitsendused families share it).
    "kkis_asjaoigus": "kitsendus_suunatud:kma_avalik_asjaoigus",
    # G3 survey leg (p75 recorded-marker hint).
    "survey_points": "eKataster:moodistuspunktid",
    # G3 soil leg (p68 weak bonitet class, vintage 2017-03-03).
    "soil_boniteet": "veeveeb:mullad_boniteet",
    # G4 mineral legs (p76/p229 weak hinnang; schemas verified in
    # docs/p4_maa_subsurface.md, cited here out of politeness).
    "maardla_leviala": "maaamet:maavarad_gbmv_levialad",
    "maardla_leiukoht": "maaamet:maavarad_gbmv_leiukohad",
}

#: TTLs in days: cadastre family monthly (parameters3.md section 5.3),
#: static vintage layers annually.
TTL_DAYS = {
    "cadastre": 30,   # parcels, ownership, survey points
    "kkis": 30,       # public restriction polygons publish monthly-ish
    "static": 365,    # soil bonitet (2017 vintage), maardlad
}

CACHE_SUBDIR = "hf-overturn-maa"
USER_AGENT = (
    "home-finder-research/0.1 (polite Maa-amet WFS overturn harvest; "
    "GitHub gregoreesmaa/home-finder issue 235)"
)
MAX_FEATURES_PER_REQ = 100  # parameters3.md section 5.3 politeness cap
MINERAL_NEAR_KM = 2.0  # coarse near-band for the p76 weak hinnang


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


def layer_url(join_name: str, bbox: Optional[Tuple[float, float, float,
                                                  float]] = None) -> str:
    """WFS GetFeature URL for a verified OVERTURN_LAYERS entry (EPSG:4326).

    bbox is (minlon, minlat, maxlon, maxlat); count stays at the
    politeness cap -- callers page, never raise it.
    """
    layer = OVERTURN_LAYERS[join_name]
    url = (WFS_BASE + "?service=WFS&version=2.0.0&request=GetFeature"
           "&outputFormat=application/json&srsName=EPSG:4326"
           "&count=%d&typeName=%s" % (MAX_FEATURES_PER_REQ, layer))
    if bbox is not None:
        url += "&bbox=%s,%s,%s,%s,EPSG:4326" % bbox
    return url


def fetch_layer(join_name: str, cache_dir: str,
                bbox: Optional[Tuple[float, float, float, float]] = None,
                ttl_days: int = 30) -> str:
    """Fetch one OVERTURN_LAYERS entry into the cache. Returns the path."""
    safe = join_name + ("_%s_%s_%s_%s" % bbox if bbox else "") + ".geojson"
    return fetch_cached(layer_url(join_name, bbox), cache_dir, safe,
                        ttl_days)


def parse_describe_featuretype_fields(dft_xml: str) -> List[str]:
    """Field names from a cached WFS DescribeFeatureType document (pure).

    Used to re-verify the parcel/KKIS/soil field contract (tunnus,
    pindala, omvorm, mullaklass, ...) before any bulk pull; hermetically
    tested on fixture XML.
    """
    try:
        root = ET.fromstring(dft_xml)
    except ET.ParseError as exc:
        raise ValueError("DescribeFeatureType ei parsinud: %s" % exc)
    fields: List[str] = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]
        if tag == "element" and el.get("name"):
            fields.append(el.get("name"))
    return fields


def wfs_typenames(caps_xml: str) -> List[str]:
    """Layer typeNames from a cached WFS GetCapabilities document (pure).

    Used for the dated-negative layer search (03B/C/D/E remainder):
    no soil-class / water-table / geothermal layer among the names pins
    the negative without a single extra request.
    """
    return re.findall(r"<Name>([^<]+)</Name>", caps_xml or "")


# ---------------------------------------------------------------------------
# Pure join core (local copies per the no-cycle precedent in the docstring).
# ---------------------------------------------------------------------------

def point_in_polygon(lon: float, lat: float,
                     ring: List[List[float]]) -> bool:
    """Ray-casting containment. Degenerate rings (< 3 distinct points) match
    nothing -- a broken polygon must not flag a parcel."""
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
    """Haversine to the nearest polygon vertex (coarse p76 proxy).

    Overstates true edge distance, so it can only under-flag -- documented
    as "jame hinnang" at the call site. None when no vertices exist.
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


def _band(value: float, bands: List[Tuple[float, int]]) -> Optional[int]:
    """First-band step scale (local copy of the livability helper)."""
    for edge, score in bands:
        if value <= edge:
            return score
    return bands[-1][1] if bands else None


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


#: Tallinn house-plot band shared with G03 dim_lot_size, so the two p29
#: legs cannot disagree on the same square metres.
LOT_BAND = [(400, 45), (800, 65), (1500, 80)]


def parcel_id(parcel: Optional[dict]) -> Optional[str]:
    """Katastritunnus when the parcel join is honest, else None."""
    if not isinstance(parcel, dict):
        return None
    kid = parcel.get("tunnus")
    if kid is None:
        return None
    key = " ".join(str(kid).strip().split())
    return key or None


def parcel_point(parcel: dict) -> Optional[Tuple[float, float]]:
    """(lon, lat) when numeric, else None (polygon joins need a point)."""
    try:
        lon = float(parcel.get("lon"))
        lat = float(parcel.get("lat"))
    except (TypeError, ValueError):
        return None
    return lon, lat


def normalise_omvorm(raw: object) -> Optional[str]:
    """Canonical ownership form or None on unknown values (never coerce)."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().split())
    if key in ("Eraomand", "Riigiomand", "Munitsipaalomand"):
        return key
    return None


def normalise_mullaklass(raw: object) -> Optional[str]:
    """Canonical soil bonitet class or None on unknown values."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    if key in ("hea", "halb"):
        return key
    return None


# ---------------------------------------------------------------------------
# G3 dims off the parcel join (issue #235: parcels unlock p29/p71/p75;
# soil/DEM unlock p68 calibration).
# ---------------------------------------------------------------------------

def dim_lot_size_parcel(parcel: Optional[dict]) -> Score:
    """p29: lot-size goodness from the cadastre pindala (per-parcel join).

    Same Tallinn band as G03 dim_lot_size (listing record), so the two
    p29 legs agree on the same square metres; this leg fills p29 when
    the listing record lacks it, with the cadastre source in the reason.
    NULL when the parcel join or pindala is missing/invalid.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): krundi "
                      "pindala vajab katastri join'i (ky_kehtiv.pindala) "
                      "— tee Maainfo/KKIS päring aadressi järgi, ära feigi")
    assert isinstance(parcel, dict)
    area = parcel.get("pindala")
    if not isinstance(area, (int, float)) or area <= 0:
        return None, ("Katastriüksuse %s pindala EI OLE (hinnang puudub): "
                      "ky_kehtiv kirje ilma pindalata — kontrolli "
                      "kinnistusraamatust/kuulutusest, ära feigi" % kid)
    score = _band(float(area), LOT_BAND)
    assert score is not None
    siht = parcel.get("siht1")
    siht_txt = ("; sihtotstarve %s" % siht) if siht else ""
    return score, ("Katastriüksuse %s pindala %d m²%s (katastri-hinnang): "
                   "krundi suuruse hinnang %d/100 (Tallinna majakruntide "
                   "mediaan ~700 m²)" % (kid, round(area), siht_txt, score))


def dim_soil_boniteet(parcel: Optional[dict]) -> Score:
    """p68: weak soil-class hint from the bonitet join (capped).

    Agricultural fertility, NOT bearing capacity: hea caps at 65, halb
    reads 45 with a survey pointer. The turvas/karst class (P4-016 EGT
    leg) and a geotechnical survey stay named-missing. NULL when the
    parcel join or the bonitet class is missing/unknown; outside every
    bonitet polygon is unknown soil, never "good soil".
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): pinnaseklass "
                      "vajab katastri join'i + mullakaardi liidestust — "
                      "tee Maainfo päring, ära feigi")
    assert isinstance(parcel, dict)
    if parcel.get("mullaklass") is None:
        return None, ("Mullaklassi katastriüksuse %s kohta EI OLE (hinnang "
                      "puudub): boniteedipolügoonide liidestus puudub või "
                      "krunt jääb kaartidest välja — Maa-ameti mullakaart / "
                      "geoloogiauuring kontrollib, ära feigi" % kid)
    klass = normalise_mullaklass(parcel.get("mullaklass"))
    if klass is None:
        return None, ("Mullaklass '%s' on tundmatu väärtus — pinnase- "
                      "hinnangut EI OLE: paranda mullakaardi liidestus"
                      % parcel.get("mullaklass"))
    if klass == "halb":
        return 45, ("Mullaklass 'halb' (2017 boniteet, viljakus — mitte "
                    "kandevõime, hinnang): vajumis/täiendava vundamendi "
                    "kahtlus 45/100 — turvas/karst-klassi (P4-016 EGT jalg) "
                    "EI OLE, küsi geotehnilist uuringut")
    return 65, ("Mullaklass 'hea' (2017 boniteet, viljakus — mitte "
                "kandevõime, hinnang): jäme mulla-hinnang 65/100 "
                "(nõrk-hea lagi — kandevõimeklassi ja geotehnilise uuringu "
                "jalga EI OLE)")


def dim_easement_burden(parcel: Optional[dict],
                        kkis_hits: Optional[List[dict]]) -> Score:
    """p71: servitude use-burden count off the public KKIS polygons.

    0 hits in a searched snapshot -> 70 (weak-good ceiling: the public
    layer is generalised, owner-login detail hidden -- kataster-module
    precedent); 1-2 -> 60; 3+ -> 40. The rule-text leg is thin (reegel
    None in the live sample), so this counts burden, never rule depth.
    NULL when the parcel join is missing or no KKIS snapshot was
    searched ([] is "searched, clean"; None is "not searched").
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): servituutide "
                      "join vajab katastriüksust — tee Maainfo/KKIS päring, "
                      "ära feigi")
    if kkis_hits is None:
        return None, ("KKIS hetktõmmist katastriüksuse %s kohta EI OLE "
                      "(hinnang puudub): avalike kitsenduskihtide "
                      "(kma_avalik_*) liidestus puudub — kontrolli "
                      "ostueelses õigusauditis, ära feigi" % kid)
    n = len([h for h in kkis_hits if isinstance(h, dict)])
    if n == 0:
        return 70, ("Katastriüksuse %s avalikes kitsenduskihtides tabamusi "
                    "EI OLE: koormatuse-hinnang 70/100 (nõrk-hea lagi — "
                    "avalik kiht on üldistatud, täisdetail vajab "
                    "omaniku-rolli sisselogimist või notarit)" % kid)
    names = ", ".join(str(h.get("nimi") or h.get("klass") or "?")
                      for h in kkis_hits[:3] if isinstance(h, dict))
    if n >= 3:
        return 40, ("Katastriüksusel %s %d kitsendust avalikes kihtides "
                    "(%s): kasutuspiirangu-hinnang 40/100 — servituutide "
                    "sisu kontrolli õigusauditis (reegliteksti jalga EI OLE)"
                    % (kid, n, names))
    return 60, ("Katastriüksusel %s %d kitsendust avalikes kihtides (%s): "
                "kasutuspiirangu-hinnang 60/100 — sisu kontrolli "
                "õigusauditis" % (kid, n, names))


def dim_boundary_markers(parcel: Optional[dict]) -> Score:
    """p75: recorded-marker hint from the survey-point join (capped).

    >=2 valid (kehtiv, kehtetu None) piirinael markers on record -> 65;
    0-1 -> 45. RECORDED, never found: markers get destroyed/overbuilt,
    so the reason says "kirjas" and the on-site/surveyor check stays.
    NULL when the parcel join or the marker count is missing.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): piirimärkide "
                      "join vajab katastriüksust — tee Maainfo päring, "
                      "ära feigi")
    assert isinstance(parcel, dict)
    markers = parcel.get("markers")
    if not isinstance(markers, int) or markers < 0:
        return None, ("Piirimärkide arvu katastriüksuse %s kohta EI OLE "
                      "(hinnang puudub): eKatastri mõõdistuspunktide "
                      "liidestus puudub — kontrolli piirimärke kohapeal "
                      "või kutsu mõõdistaja, ära feigi" % kid)
    if markers >= 2:
        return 65, ("Katastriüksusel %s %d kehtivat piirimärki kirjas "
                    "(eKatastri-hinnang): piiride-hinnang 65/100 (nõrk "
                    "vihje — kirjas, mitte leitud; taastamist vajava märgi "
                    "jalga EI OLE, kontrolli kohapeal)" % (kid, markers))
    return 45, ("Katastriüksusel %s kirjas piirimärke %d (eKatastri-hinnang): "
                "piirivaidluse kahtlus 45/100 — piiride selgus vajab "
                "mõõdistaja kontrolli" % (kid, markers))


# ---------------------------------------------------------------------------
# G4 partials folded in by data source (issue #235): p76/p229 mineral
# rights as maardlad weak hinnang, p364 ground lease as ownership hint.
# ---------------------------------------------------------------------------

def dim_mineral_rights_hint(parcel: Optional[dict],
                            quarries: List[dict]) -> Score:
    """p76: mineral/water/timber-rights encumbrance hint (soft-capped).

    Inside a maavarad leviala polygon -> 50 (kaevandamisõiguse kitsenduse
    kahtlus); coarse near-band (<= 2 km vertex proxy, labelled jame) ->
    60; further out -> NULL (no polygon proves nothing about severance).
    Deposits nearby, never this parcel's severance -- the RIK extract
    stays named. Soft cap 60: this leg can only warn, never clear.
    """
    parcel = parcel or {}
    pt = parcel_point(parcel)
    kid = parcel_id(parcel) or "?"
    if pt is None:
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "maardlate-puhvrit ei saa arvutada — täienda "
                      "koordinaat, ära feigi")
    if not quarries:
        return None, ("Maardlate kihti (levialad) EI OLE laetud (hinnang "
                      "puudub): puhver vajab maavarad_gbmv_levialad "
                      "liidestust — tõsta puhver, ära feigi")
    lon, lat = pt
    for q in quarries:
        polys = (q or {}).get("polygons") or []
        if any(point_in_polygon(lon, lat, ring) for ring in polys):
            return 50, ("Krunt '%s' maardla levialas (katastriüksus %s): "
                        "kaevandamisõiguse-kitsenduse kahtlus 50/100 (nõrk "
                        "hinnang — leiukoha lähedus, mitte selle krundi "
                        "lahutamine; RIK väljavõtte jalga EI OLE)"
                        % ((q or {}).get("nimi", "?"), kid))
    best: Optional[float] = None
    best_name = "?"
    for q in quarries:
        d = nearest_vertex_km(lon, lat, (q or {}).get("polygons") or [])
        if d is not None and (best is None or d < best):
            best, best_name = d, (q or {}).get("nimi", "?")
    if best is not None and best <= MINERAL_NEAR_KM:
        return 60, ("Lähim teadaolev maardla '%s' %.1f km (jäme "
                    "tipp-kauguse hinnang, krunt %s): õiguste-hinnang "
                    "60/100 (pehme lagi — kaugus ei tõesta vaikust ega "
                    "lahutamist, RIK väljavõtet kontrolli)"
                    % (best_name, best, kid))
    return None, ("Teadaolevate maardlate puhvrit (<= %.0f km) EI OLE "
                  "(hinnang puudub): kaugus ei tõesta õiguste puhtust — "
                  "lahutamiskahtluse hinnang puudub" % MINERAL_NEAR_KM)


def dim_mineral_severance_hint(parcel: Optional[dict],
                               quarries: List[dict]) -> Score:
    """p229: severance-SUSPICION hint only (stricter than p76).

    Severance (split estate) is a deed fact the polygons cannot see: only
    proven INSIDE a leviala scores (45, suspicion -- the deed still needs
    the RIK extract); everything outside stays NULL, with NO near-band
    (deposits nearby cannot hint severance from afar). Disjoint from p76
    by construction: p76 warns on nearness, p229 suspects only overlap.
    """
    parcel = parcel or {}
    pt = parcel_point(parcel)
    kid = parcel_id(parcel) or "?"
    if pt is None:
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "lahutamiskahtlust ei saa arvutada — täienda "
                      "koordinaat, ära feigi")
    if not quarries:
        return None, ("Maardlate kihti (levialad) EI OLE laetud (hinnang "
                      "puudub): kahtlus vajab maavarad_gbmv_levialad "
                      "liidestust — tõsta puhver, ära feigi")
    lon, lat = pt
    for q in quarries:
        polys = (q or {}).get("polygons") or []
        if any(point_in_polygon(lon, lat, ring) for ring in polys):
            return 45, ("Krunt '%s' maardla levialas (katastriüksus %s): "
                        "õiguste lahutamise KAHTLUS 45/100 — lahutamine ise "
                        "on kinnistusraamatu fakt (RIK väljavõtte jalga "
                        "EI OLE), kaevandaja võib nõuda osa kasutusest"
                        % ((q or {}).get("nimi", "?"), kid))
    return None, ("Krunt väljas teadaolevast levialast (katastriüksus %s): "
                  "lahutamiskahtluse hinnangut EI OLE — polügoonist väljas "
                  "ei tõesta lahutamatust (kahtlus puudub, mitte puhtus)"
                  % kid)


def dim_ground_lease_hint(parcel: Optional[dict]) -> Score:
    """p364: ground-lease suspicion from the cadastre ownership form.

    Eraomand -> 70 weak-good (hoonestusoiguse kahtlust EI OLE nahal);
    Riigi/Munitsipaalomand -> 50 + hoonestus-check (municipal/state land
    is OFTEN, not always, leased -- suspicion, never a verdict); unknown
    omvorm -> NULL. Lease TERMS always need the RIK extract, so even
    Eraomand caps at 70.
    """
    kid = parcel_id(parcel)
    if kid is None:
        return None, ("Katastritunnust EI OLE (hinnang puudub): omandivorm "
                      "vajab katastri join'i (ky_kehtiv.omvorm) — tee "
                      "Maainfo päring, ära feigi")
    assert isinstance(parcel, dict)
    if parcel.get("omvorm") is None:
        return None, ("Omandivormi katastriüksuse %s kohta EI OLE (hinnang "
                      "puudub): ky_kehtiv kirje ilma omvormita — "
                      "hoonestusõiguse kahtlust ei saa hinnata, kontrolli "
                      "kinnistusraamatust" % kid)
    form = normalise_omvorm(parcel.get("omvorm"))
    if form is None:
        return None, ("Omandivorm '%s' on tundmatu väärtus — rendi- "
                      "hinnangut EI OLE: paranda katastri liidestus"
                      % parcel.get("omvorm"))
    if form == "Eraomand":
        return 70, ("Katastriüksus %s eraomandis (katastri-hinnang): "
                    "hoonestusõiguse kahtlust EI OLE näha 70/100 (nõrk-hea "
                    "lagi — renditingimuste (kestus/tasu) jalga EI OLE, "
                    "RIK väljavõtet kontrolli)" % kid)
    return 50, ("Katastriüksus %s %s (katastri-hinnang): hoonestusõiguse/ "
                "üürilepingu kahtlus 50/100 — riigi/omavalitsuse maal "
                "on hoonestusõigus tavaline, aga mitte kindel; "
                "renditingimusi (kestus, tasu, pikendamine) EI OLE, "
                "kontrolli RIK väljavõttest" % (kid, form.lower()))


OVERTURN_MAA_DIMS = (
    ("lot_size_parcel", "p29", dim_lot_size_parcel),
    ("soil_boniteet", "p68", dim_soil_boniteet),
    ("easement_burden", "p71", dim_easement_burden),
    ("boundary_markers", "p75", dim_boundary_markers),
    ("mineral_rights_hint", "p76", dim_mineral_rights_hint),
    ("mineral_severance_hint", "p229", dim_mineral_severance_hint),
    ("ground_lease_hint", "p364", dim_ground_lease_hint),
)

OVERTURN_MAA_PARAM_IDS = {
    "lot_size_parcel": 29,
    "soil_boniteet": 68,
    "easement_burden": 71,
    "boundary_markers": 75,
    "mineral_rights_hint": 76,
    "mineral_severance_hint": 229,
    "ground_lease_hint": 364,
}


def score_overturn_maa(parcel: Optional[dict],
                       kkis_hits: Optional[List[dict]] = None,
                       quarries: Optional[List[dict]] = None) -> Dict[
                           str, Optional[int]]:
    """All 7 Maa-overturn dims for one parcel (keys match the registry).

    kkis_hits=None means "no KKIS snapshot" (p71 NULL), not "no hits" --
    pass [] for an honestly searched-clean parcel. quarries feeds only
    the p76/p229 mineral legs.
    """
    parcel = parcel if isinstance(parcel, dict) else None
    quarries = quarries or []
    out: Dict[str, Optional[int]] = {}
    out["lot_size_parcel"] = dim_lot_size_parcel(parcel)[0]
    out["soil_boniteet"] = dim_soil_boniteet(parcel)[0]
    out["easement_burden"] = dim_easement_burden(parcel, kkis_hits)[0]
    out["boundary_markers"] = dim_boundary_markers(parcel)[0]
    out["mineral_rights_hint"] = dim_mineral_rights_hint(parcel, quarries)[0]
    out["mineral_severance_hint"] = dim_mineral_severance_hint(
        parcel, quarries)[0]
    out["ground_lease_hint"] = dim_ground_lease_hint(parcel)[0]
    return out
