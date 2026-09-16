"""P4 DTM relief/flatness layer — slope + relative elevation (issue #553).

Harjumaa is not flat where it matters: the Lasnamäe limestone klint
(sea-view premium on top, geotechnical complexity at the edge),
Nõmme–Mustamäe slopes (cycling/walking effort, winter slipperiness),
Pirita river valley + coastal lowlands (dampness, flood-adjacent),
Merivälja dunes. Slope + relative elevation decide views, cycling
effort, lowland dampness and build complexity street by street.

OPENNESS VERDICT (polite probes, 2026-09-16, custom UA, /tmp/hf553_*):
* WCS GetCapabilities
  https://teenus.maaamet.ee/ows/wcs-dtm?service=WCS&request=GetCapabilities
  -> HTTP 200, 7376 bytes. Provider Maa-amet, WCS 2.0.1, Fees none,
  AccessConstraints none. Coverages: dtm-25, dtm-10, dtm-1 (no dtm-5
  advertised — the issue's "1/5/10/25 m" list overstates the service).
* DescribeCoverage dtm-1 -> HTTP 200, 2487 bytes. Grid EPSG:3301
  (L-EST97), 1 m offsets, nationwide envelope N 6375000–6635000 /
  E 365000–740000, native GeoTIFF float32. NO vertical datum stated
  (Estonian heights are conventionally EH2000/BK77 — UNVERIFIED, never
  asserted; heights enter only as relative differences + slope).
* One small Harjumaa window (issue allowance): GetCoverage dtm-1
  SUBSET=y(6591000,6591200)&SUBSET=x(543800,544200) (400x200 m,
  Lasnamäe klint edge) -> HTTP 200, 320664 bytes, valid float32
  GeoTIFF — but ALL 80000 cells read exactly 0.00 (no voids). Either
  dtm-1 is void there (0-filled) or the window misses the coverage
  patch: downtown-adjacent land cannot be uniformly 0 m. CAUTION
  recorded: slope bands below are PROVISIONAL until the harvest PR
  validates windows against dtm-10/dtm-25 + tile layout. No second
  pull per the probe budget.

HONESTY (AGENTS.md 7.2 — the framing IS the issue): flatness is
taste-dependent, so a plain good/bad gradient would be fake
precision. Required shape, implemented here:
* Character overlay first (EELIS #488 precedent): classify_character
  paints slope/relief character with NO score field.
* Taste-dependent scorer legs only, each capped, each labelled with
  its named taste (cyclist / view-seeker / flood-avoider).
* No landslide-risk scoring (slope != slide risk — every steep
  reason says so). No view-shed monetisation (sea-view premium stays
  price modelling, not this layer).
* Graduations enabled: driveway-grade NULL -> measured grade
  (dim_driveway_grade consumes the joined slope); p336 slidebuf ->
  measured-slope cross-check (p336_agreement logs OSM-vs-DTM
  agreement for review; live agreement unmeasured).
* 1 m grid resolves streets, not kerbs/driveway crowns — micro-grade
  stays a buyer check; annual vintage stated in reasons (fresh
  cuts/fills post-date the flights).

Style mirrors dims_p4_maaparandus.py (#551): pure (parcel, join) ->
Score, Estonian reasons, hermetic fixtures. Network lives only in
fetch_* (single polite GETs, file cache). Tests never call it.
"""

import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: DTM harvest moves at annual-vintage pace; cache a month.
DTM_TTL_DAYS = 30

WCS_BASE_URL = "https://teenus.maaamet.ee/ows/wcs-dtm"

#: Coverages advertised 2026-09-16 (note: no dtm-5). CRS EPSG:3301.
COVERAGES = ("dtm-25", "dtm-10", "dtm-1")
NATIVE_CRS = "EPSG:3301"

LICENCE = "CC-BY-4.0"
ATTRIBUTION = ("Allikas: Maa- ja Ruumiamet, Eesti maapinna kõrgusmudel "
               "DTM (CC BY 4.0, aastane seis)")

USER_AGENT = ("home-finder relief ingest (polite pulls, single GET, "
              "file cache; contact via GitHub home-finder)")

#: PROVISIONAL slope bands (degrees) — pending harvest-PR validation
#: against real histograms (see module docstring zero-window caution).
SLOPE_FLAT = 2.0
SLOPE_CYCLE = 5.0
SLOPE_STEEP = 10.0
SLOPE_KLINT = 20.0

#: PROVISIONAL relative-elevation poles (m, parcel vs 500 m ring mean).
REL_LOWLAND_M = 2.0
REL_VIEW_M = 15.0


# ---------------------------------------------------------------------------
# Ingestion: polite, cached WCS pulls.
# ---------------------------------------------------------------------------

def build_capabilities_url() -> str:
    """WCS GetCapabilities URL (coverage list lives here)."""
    return WCS_BASE_URL + "?service=WCS&request=GetCapabilities"


def build_describe_url(coverage_id: str) -> str:
    """DescribeCoverage URL (grid/CRS proof for one coverage)."""
    return (WCS_BASE_URL + "?service=WCS&version=2.0.1"
            "&request=DescribeCoverage&coverageId=" + coverage_id)


def build_window_url(coverage_id: str,
                     north0: float, north1: float,
                     east0: float, east1: float) -> str:
    """Small GetCoverage window URL (EPSG:3301, axisLabels y x).

    Northings go in SUBSET=y(...), eastings in SUBSET=x(...).
    Keep windows tiny (a few hundred metres): one window per probe.
    """
    return (WCS_BASE_URL + "?service=WCS&version=2.0.1&request=GetCoverage"
            "&coverageId=" + coverage_id + "&format=image%2Ftiff"
            + "&SUBSET=y(%s,%s)&SUBSET=x(%s,%s)"
            % (north0, north1, east0, east1))


def _cache_path(cache_dir: str, url: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in url)
    return os.path.join(cache_dir, "relief-%s.tif" % safe[-120:])


def cache_is_fresh(path: str, ttl_days: int = DTM_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_window_tiff(url: str, cache_dir: str = "/tmp/hf-cache",
                      ttl_days: int = DTM_TTL_DAYS) -> bytes:
    """Fetch one small WCS window politely (single GET, cached).

    Transport errors RAISE (never cached as data); HTTP 429 propagates
    (stop signal, AGENTS.md 7.4).
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, url)
    if cache_is_fresh(path, ttl_days):
        with open(path, "rb") as fh:
            return fh.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        blob = resp.read()
    with open(path, "wb") as fh:
        fh.write(blob)
    return blob


# ---------------------------------------------------------------------------
# Pure character + taste-capped scoring on joined records.
# ---------------------------------------------------------------------------

def classify_character(slope_deg: float, rel_elev_m: float) -> str:
    """Area character label — NEVER a score (EELIS #488 precedent).

    join fields: slope_deg (parcel median 1 m slope), rel_elev_m
    (parcel median minus 500 m ring mean, same vintage).
    """
    if slope_deg >= SLOPE_KLINT and rel_elev_m >= REL_VIEW_M:
        return "klindiserv"
    if slope_deg >= SLOPE_STEEP:
        return "järsak"
    if slope_deg >= SLOPE_CYCLE:
        return "nõlv"
    if rel_elev_m <= -REL_LOWLAND_M:
        return "madalik"
    if rel_elev_m >= REL_VIEW_M:
        return "kõrgendik"
    if slope_deg >= SLOPE_FLAT:
        return "laanõlv"
    return "tasane"


def _need(join: Optional[dict]) -> Optional[str]:
    if join is None:
        return ("Kõrgusmudeli seos puudub (hinnang EI OLE): "
                "DTM-väljavõtet ei ole liidetud.")
    if join.get("slope_deg") is None or join.get("rel_elev_m") is None:
        return ("Kõrgusmudeli seos poolik (hinnang EI OLE): "
                "kalle või suhteline kõrgus puudub.")
    return None


def _tag(join: dict) -> str:
    return " (DTM %s, %s)" % (join.get("coverage_id", "teadmata kate"),
                              join.get("vintage", "teadmata seis"))


def dim_lowland_dampness(origin: Optional[Tuple[float, float]],
                         join: Optional[dict]) -> Score:
    """Lowland-dampness flag — the flood-avoider's taste (bad side, capped).

    Provisional: flat + low relative elevation -> 45 with a
    flood-layer-cousin pointer. Never 0 (DTM says damp, not doomed).
    """
    missing = _need(join)
    if missing:
        return None, missing
    assert join is not None
    if (join["rel_elev_m"] <= -REL_LOWLAND_M
            and join["slope_deg"] < SLOPE_FLAT):
        return (45, "Madalikuala iseloom (%s, hinnang)%s: niiskus- ja "
                "suurveerisk — kontrolli üleujutuskihte; kalle ei ole "
                "libisemisrisk." % (classify_character(join["slope_deg"],
                                                       join["rel_elev_m"]),
                                    _tag(join)))
    return (None, "Madalikumärki ei ole (hinnang EI OLE)%s." % _tag(join))


def dim_viewpoint(origin: Optional[Tuple[float, float]],
                  join: Optional[dict]) -> Score:
    """Viewpoint-elevation leg — the view-seeker's taste (capped match)."""
    missing = _need(join)
    if missing:
        return None, missing
    assert join is not None
    if join["rel_elev_m"] >= REL_VIEW_M:
        return (65, "Kõrgendiku iseloom (%s, vaateotsija roheline, "
                "hinnang)%s: kõrgusmudel näitab vaadet, mitte keeldu — "
                "merevaate hind jääb hinnamodelleerimisse."
                % (classify_character(join["slope_deg"],
                                      join["rel_elev_m"]), _tag(join)))
    return (None, "Vaatekõrgust ei ole (hinnang EI OLE)%s." % _tag(join))


def dim_cycling_effort(origin: Optional[Tuple[float, float]],
                       join: Optional[dict]) -> Score:
    """Cycling-effort leg — the cyclist's taste (mobility cost, capped)."""
    missing = _need(join)
    if missing:
        return None, missing
    assert join is not None
    slope = join["slope_deg"]
    if slope >= SLOPE_STEEP:
        return (45, "Järsak (%s, ratturi punane, hinnang)%s: talvine "
                "libedus ja sõidupingutus — mikroprofiil jääb "
                "ostja kontrolliks." % (classify_character(
                    slope, join["rel_elev_m"]), _tag(join)))
    if slope >= SLOPE_CYCLE:
        return (60, "Nõlv (%s, ratturi kollane, hinnang)%s."
                % (classify_character(slope, join["rel_elev_m"]),
                   _tag(join)))
    return (None, "Rattasõidukallet ei ole (hinnang EI OLE)%s."
            % _tag(join))


def dim_klint_edge(origin: Optional[Tuple[float, float]],
                   join: Optional[dict]) -> Score:
    """Klint-edge build-complexity flag — geotechnical buyer check.

    Never a ban ("mudel näitab kuju, mitte keeldu"); never slide risk.
    """
    missing = _need(join)
    if missing:
        return None, missing
    assert join is not None
    near = join.get("dist_klint_m") is not None and join["dist_klint_m"] <= 200
    shape = (join["slope_deg"] >= SLOPE_KLINT
             and join["rel_elev_m"] >= REL_VIEW_M)
    if near or shape:
        return (50, "Klindiserva iseloom (hinnang)%s: ehitusgeoloogiline "
                "lisakontroll serva lähedal — mudel näitab kuju, mitte "
                "keeldu; kalle ei ole libisemisrisk." % _tag(join))
    return (None, "Klindiserva märki ei ole (hinnang EI OLE)%s."
            % _tag(join))


def dim_driveway_grade(origin: Optional[Tuple[float, float]],
                       join: Optional[dict]) -> Score:
    """Driveway grade from measured slope (graduates the documented NULL).

    1 m grid resolves streets, not kerbs/driveway crowns — steep stays
    a buyer check, never a verdict.
    """
    missing = _need(join)
    if missing:
        return None, missing
    assert join is not None
    slope = join["slope_deg"]
    if slope >= SLOPE_STEEP:
        return (50, "Mõõdetud kalle %.0f° (hinnang)%s: järsk juurdepääs "
                "võimalik — äärekivi/kraav jääb ostja kontrolliks."
                % (slope, _tag(join)))
    if slope >= SLOPE_CYCLE:
        return (65, "Mõõdetud kalle %.0f° (hinnang)%s."
                % (slope, _tag(join)))
    return (None, "Mõõdetud kalle %.1f° — sissesõidumärki ei ole "
            "(hinnang EI OLE)%s." % (slope, _tag(join)))


def p336_agreement(osm_cliff_near: bool, slope_deg: Optional[float]) -> str:
    """OSM cliff-proximity (p336 slidebuf) vs measured slope, for review.

    Returns kokkulangevus / lahknevus / hindamata — a log label, never
    a score. Live agreement rate is unmeasured (harvest PR).
    """
    if slope_deg is None:
        return "hindamata"
    steep = slope_deg >= SLOPE_KLINT
    if osm_cliff_near == steep:
        return "kokkulangevus"
    return "lahknevus"


P4_RELIEF_DIMS = {
    "lowland_dampness": ("Madaliku-niiskus (maitse)", dim_lowland_dampness),
    "viewpoint": ("Vaatekõrgus (maitse)", dim_viewpoint),
    "cycling_effort": ("Rattakalle (maitse)", dim_cycling_effort),
    "klint_edge": ("Klindiserv (kontroll)", dim_klint_edge),
    "driveway_grade": ("Sissesõidukalle (mõõdetud)", dim_driveway_grade),
}

P4_RELIEF_PARAM_IDS = {"lowland_dampness": 553, "viewpoint": 553,
                       "cycling_effort": 553, "klint_edge": 553,
                       "driveway_grade": 553}


def score_p4_relief(origin: Optional[Tuple[float, float]],
                    join: Optional[dict]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Roll up the relief dims; NULL dims contribute no reasons."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for key in P4_RELIEF_DIMS:
        value, reason = P4_RELIEF_DIMS[key][1](origin, join)
        dims[key] = value
        if value is not None:
            reasons.append(reason)
    return dims, reasons
