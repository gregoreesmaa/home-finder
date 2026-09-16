"""P4 drainage-duty + wetness joins from maaparandus GIS WFS (issue #551).

Rural/suburban plots sit inside drainage systems: wet yards,
ditch-maintenance duty and cost, building restrictions near regulated
networks and outflows. Open-water proximity (p50) cannot see
buried/regulated networks — this is the measured layer. Split vs
neighbours: #543 (KPO kitsendused) covers restriction *zones*, this
covers drainage *infrastructure* + the duty side; p50 covers open
water; p4_maa_subsurface WFS legs cover karst/peat/groundwater.
Distinct dim keys, no double-score.

OPENNESS VERDICT (polite probes, 2026-09-16, custom UA, /tmp/hf551_*):
* GetCapabilities
  https://gsavalik.envir.ee/geoserver/pta/wfs?service=WFS&version=2.0.0&request=GetCapabilities
  -> HTTP 200, 117048 bytes. 5 layers: pta:msr_vork (reguleeriva
  vorgu alad), pta:msr_eesvool (eesvoolud), pta:msr_riigieesvoolud
  (state-maintained joint outflows), pta:kehtetu_maaparandussysteem
  (invalid systems), pta:mpy_tegevuspiirkond (co-op areas).
  Default CRS EPSG:3301 (+3857, +4326). Fees NONE,
  AccessConstraints NONE.
* LICENCE GATE PASSES: the capabilities carry a per-service licence
  note — CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
  with attribution to Kliimaministeerium as data source, unless a
  layer states its own terms. Attribution string kept below.
* DescribeFeatureType pta:msr_vork -> HTTP 200, 2342 bytes. Schema:
  shape, versioon, ms_kood (13-digit system code), ehitise_kood,
  ehitise_nimi, nahtuse_liik, nahtuse_seletus_lyhi, vihm, pind_ha,
  aasta, vork_id, ms_url (MSR register link), loomise/muutmise_aeg.
  NO explicit status/seisund/condition attribute exists, and the
  semantics of nahtuse_liik are unproven without value samples
  (out of probe budget). Per the issue contract the DUTY leg
  therefore closes as documented NULL: reasons point at the
  MSR/register check (ms_url + ms_kood) and never assert duty.
* Harjumaa count (single resultType=hits GetFeature, lat-lon axis
  order): pta:msr_vork bbox 58.9,23.9-59.7,25.4 (EPSG:4326) ->
  numberMatched="1916" regulating-network areas. (First attempt with
  lon-lat order returned 0 — axis-order artefact, corrected once.)

HONESTY (AGENTS.md 7.2): per-parcel join dims, never gradients.
Inside a regulating-network area -> capped wetness hinnang 55
(maintained = neutral-to-good drainage, derelict = risk, but status
is unproven — the reason names ms_kood + the MSR check). Inside a
kehtetu (invalid) system -> risk flag 40 (the invalid layer IS the
measured derelict proxy). Near an outflow (<=100 m) -> dampness flag
45. Outside everything -> NULL (never "dry"). Duty -> always NULL.

Style mirrors dims_p4_ata.py: pure (parcel, join) -> Score, absolute
bands, hermetic fixture tests. Network lives only in fetch_* (single
polite GETs, file cache, weekly TTL). Tests never call it.
"""

import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Weekly harvest at most (register lags <=2 h; parcels move slowly).
MSR_TTL_DAYS = 7

WFS_BASE_URL = "https://gsavalik.envir.ee/geoserver/pta/wfs"

#: Licence gate evidence (capabilities, 2026-09-16). Attribute always.
LICENCE = "CC-BY-4.0"
ATTRIBUTION = ("Allikas: Kliimaministeerium / Maa- ja Ruumiamet, "
               "maaparanduse GIS (CC BY 4.0)")

USER_AGENT = ("home-finder maaparandus ingest (polite weekly pulls, single GET, "
              "file cache; contact via GitHub home-finder)")

#: Inside-network wetness hinnang (capped: status unproven, see docstring).
INSIDE_VORK_SCORE = 55
#: Invalid (kehtetu) system containment: measured derelict proxy.
KEHTETU_SCORE = 40
#: Near-outflow dampness flag band (m) and score.
EESVOOL_BAND_M = 100.0
EESVOOL_SCORE = 45


# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated WFS pulls.
# ---------------------------------------------------------------------------

def build_capabilities_url() -> str:
    """WFS GetCapabilities URL (licence + layer list live here)."""
    return WFS_BASE_URL + "?service=WFS&version=2.0.0&request=GetCapabilities"


def build_describe_url(type_name: str) -> str:
    """DescribeFeatureType URL for one layer (schema proof)."""
    return (WFS_BASE_URL + "?service=WFS&version=2.0.0"
            "&request=DescribeFeatureType&typeNames=" + type_name)


def build_hits_url(type_name: str, bbox_latlon: Tuple[float, float, float, float]) -> str:
    """resultType=hits count URL (no geometry downloaded).

    bbox_latlon is (lat0, lon0, lat1, lon1): WFS 2.0 with
    urn:ogc:def:crs:EPSG::4326 expects LAT-LON axis order.
    """
    lat0, lon0, lat1, lon1 = bbox_latlon
    return (WFS_BASE_URL + "?service=WFS&version=2.0.0&request=GetFeature"
            "&typeNames=" + type_name + "&resultType=hits"
            "&srsName=urn:ogc:def:crs:EPSG::4326"
            "&bbox=%s,%s,%s,%s,urn:ogc:def:crs:EPSG::4326"
            % (lat0, lon0, lat1, lon1))


def _cache_path(cache_dir: str, url: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in url)
    return os.path.join(cache_dir, "maaparandus-%s.xml" % safe[-120:])


def cache_is_fresh(path: str, ttl_days: int = MSR_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_wfs_xml(url: str, cache_dir: str = "/tmp/hf-cache",
                  ttl_days: int = MSR_TTL_DAYS) -> str:
    """Fetch one WFS document politely (single GET, cached, TTL-stated).

    Transport errors RAISE (never cached as data); HTTP 429 propagates
    (stop signal, AGENTS.md 7.4).
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, url)
    if cache_is_fresh(path, ttl_days):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


# ---------------------------------------------------------------------------
# Pure scoring on joined per-parcel records.
# ---------------------------------------------------------------------------

def dim_drainage_duty(origin: Optional[Tuple[float, float]],
                      join: Optional[dict]) -> Score:
    """Maintenance-duty leg: documented NULL (no status semantics proven).

    join: None, or {"ms_kood" (str|None), "ms_url" (str|None)}.
    """
    if join and join.get("ms_kood"):
        return (None, "Hoolduskohustus teadmata (hinnang EI OLE): krunt "
                "asub reguleeritud võrgus %s — kohustus selgub "
                "maaparandussüsteemide registrist (MSR), mitte kaardilt."
                % join["ms_kood"])
    return (None, "Hoolduskohustus teadmata (hinnang EI OLE): "
            "maaparandusliidest ei ole liidetud — kontrolli MSR-registrit.")


def dim_network_wetness(origin: Optional[Tuple[float, float]],
                        join: Optional[dict]) -> Score:
    """Wetness hinnang from regulating-network containment.

    join: None, or {"inside_vork" (bool), "ms_kood" (str|None),
    "inside_kehtetu" (bool), "distance_eesvool_m" (float|None)}.
    Invalid-system containment wins over the neutral inside band;
    near-outflow flag applies when outside the network.
    """
    if join is None:
        return (None, "Kuivendusvõrgu seos puudub (hinnang EI OLE): "
                "maaparanduse WFS-väljavõtet ei ole liidetud.")
    if join.get("inside_kehtetu"):
        return (KEHTETU_SCORE, "Krunt kehtetus maaparandussüsteemis "
                "(hinnang, risk): korrastamata võrk — niiskus- ja "
                "hooldusrisk, kontrolli MSR-registrist.")
    if join.get("inside_vork"):
        code = join.get("ms_kood") or "teadmata kood"
        return (INSIDE_VORK_SCORE, "Krunt reguleeritud võrgus %s "
                "(hinnang): hooldatud süsteem on neutraalne kuni hea "
                "kuivendus, räämas süsteem on risk — seisund teadmata, "
                "kontrolli MSR-registrist." % code)
    dist = join.get("distance_eesvool_m")
    if dist is not None and dist <= EESVOOL_BAND_M:
        return (EESVOOL_SCORE, "Eesvool %dm kaugusel (hinnang): "
                "niiskuselipuke — lähedus ei ole märg krunt." % int(dist))
    return (None, "Võrgust väljas (hinnang EI OLE): kuivendussüsteemi "
            "ega eesvoolu lähedust ei ole — see ei ole kuivuse tõend.")


P4_MAAPARANDUS_DIMS = {
    "drainage_duty": ("Kuivendus-kohustus (NULL)", dim_drainage_duty),
    "network_wetness": ("Võrguniiskus (hinnang)", dim_network_wetness),
}

P4_MAAPARANDUS_PARAM_IDS = {"drainage_duty": 551, "network_wetness": 551}


def score_p4_maaparandus(origin: Optional[Tuple[float, float]],
                         join: Optional[dict]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Roll up the maaparandus dims; NULL dims contribute no reasons."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    wet, wet_reason = dim_network_wetness(origin, join)
    dims["network_wetness"] = wet
    if wet is not None:
        reasons.append(wet_reason)
    dims["drainage_duty"] = None
    return dims, reasons
