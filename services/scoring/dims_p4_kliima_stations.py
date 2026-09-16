"""P4 microclimate-cell dims (issue #541): Keskkonnaagentuur climate
PostgREST (kliimaandmestik) as coarse honest station cells.

Source (probed 2026-09-16, one polite GET per endpoint, labelled
one-off User-Agent, `--max-time 25/40`, raw files at /tmp/hf-probes/ --
one-off PR record, never committed):
* Station view https://keskkonnaandmed.envir.ee/f_kliima_jaam_vaatlus
  -> HTTP 200 (station x element x period rows with pikkuskraad /
  laiuskraad / korgus_merepinnast_m). Distinct roster: 25 stations
  nationwide (AJHARK01 Tallinn-Harku 59.3981N 24.6029E ... AJVORU01
  Voru). Serving Harjumaa: Tallinn-Harku (in), Pakri/Paldiski
  (59.3895N 24.0401E, in), Kuusiku (58.9732N 24.7340E, Rapla, ~8 km
  south of the border, serving S-Harjumaa); Kunda (Lääne-Viru)
  borders E-Harjumaa. Usable in/near-Harjumaa = 3 -> station cells
  (issue rule: <3 would force single-row no-map; recorded below).
* Element view .../f_kliima_element -> HTTP 200, 25 elements:
  daily DPA008/DPREC/DRH08/DRQS/DSDUR/DSND/DTAN/DTAX/DTA08/DWSX/DWS08,
  hourly PA0/PR1H/RH/SDUR1H/TA/TAN1H/TAX1H, 10-min WD10M/WD10MA/
  WSX1H/WS10M/WS10MA/WS10MX (units hPa/mm/%/MJ/m2/h/cm/°C/m/s/kraadi).
* Monthly series .../f_kliima_kuu?aasta=eq.2023&kuu=eq.12&limit=10 ->
  HTTP 200: query pattern CONFIRMED; rows carry jaam_kood, jaam_nimi,
  aasta, kuu, vaartus, element_kood (sample: Harku Dec-2023 DPREC
  43.60 mm). 30-year normals pulls are the harvest's job (annual,
  paginated) -- out of this probe's polite budget by design.

Params (this module only -- sibling batches own disjoint sets):
* P4 winter-mildness cell: 1991-2020 frost-day normals rank across
  the joined Harjumaa cells (normals, NOT nowcast).
* P4 wetness cell: 1991-2020 annual-precipitation normals rank.
  docs/p4_ilm.md (#308/#374, live Harku observations) stays the
  nowcast cousin -- distinct dims (normals vs nowcast), no
  double-score. docs/p4_kliima.md (strategy-PDF verdict) untouched.

HONESTY (AGENTS.md section 7.2): cells are nearest-station polygons
in spirit -- between-station interpolation is FORBIDDEN (no
street-level gradients, no forecasts). Ranking needs >=2 joined
cells; one cell alone cannot be ranked -> NULL with EI OLE + the
buyer check (ilmateenistus normals page + heating-bill enquiry).
Missing origin, missing indicator, or empty join -> NULL the same
way. Every scored reason names the normals window + the station.

Style mirrors services/scoring/dims_p4_kliima.py (#319/#378): pure
(origin, cells) -> (Optional[int 0..100], Estonian reason), absolute
rank bands, hermetic fixture tests. Network lives only in
fetch_climate_rows (single polite GETs, file cache, TTL); tests never
call it.

BANDS (rank across the JOINED distribution -- the code literally
bands from the station distribution, per the issue criterion):
* dense rank 0 (mildest/driest joined cell) -> 70, rank 1 -> 55,
  rank >= 2 -> 40. Two joined cells score 70/40. Ties share the
  better band.

Voronoi-vs-single-cell decision (recorded per the issue): 3 usable
stations in/near Harjumaa (Harku, Pakri, Kuusiku) -> nearest-station
cells. Normals window 1991-2020 (WMO standard, stated).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Relative rank, not absolute cutoffs: absolute frost-day cutoffs
  cannot be calibrated inside a polite probe budget (normals need
  30y x 12mo x stations of pulls); the harvest joins measured
  normals and the dim ranks them -- no hardcoded fake tertiles.
* Drier ranks better for wetness (garden season, sogginess); fewer
  frost days ranks better for winter mildness (heating bills). Both
  are buyer-direction judgments stated in the reasons ("kuivem",
  "leebem") -- never presented as comfort measurements.
* Kunda is NOT a Harjumaa cell (serves the Loksa corner at best):
  eastern Harjumaa falls to the nearest of the three cells and the
  reason names the station, so the coarseness is visible per score.

Integration (deliberately NOT done here): the annual normals harvest
(1991-2020 aggregates per station) plus listing->cell wiring inside
livability scoring and WEIGHTS rebalance stay one joint change.
"""

import math
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Keyless PostgREST (verified 2026-09-16).
CLIMATE_BASE_URL = "https://keskkonnaandmed.envir.ee"
STATION_VIEW = "f_kliima_jaam_vaatlus"
ELEMENT_VIEW = "f_kliima_element"
MONTHLY_VIEW = "f_kliima_kuu"

#: CONT feed -> annual harvest (normals move slowly, issue constraint).
CLIMATE_TTL_DAYS = 365

#: CC BY 4.0: attribute the Environment Agency wherever scores surface.
CLIMATE_ATTRIBUTION = "Keskkonnaagentuur (kliimaandmestik), CC BY 4.0"

#: WMO normals window (stated, fixed).
NORMALS_START = 1991
NORMALS_END = 2020

USER_AGENT = ("home-finder climate normals ingest (polite annual pulls, "
              "single GETs, file cache; contact via GitHub home-finder)")


def _cache_path(cache_dir: str, params: str) -> str:
    """Cache file for one PostgREST query (flat dir, no subdirs)."""
    safe = "".join(c if (c.isalnum() or c in "-_.=") else "_"
                   for c in params)
    return os.path.join(cache_dir, "kliima-%s.json" % safe[-100:])


def cache_is_fresh(path: str, ttl_days: int = CLIMATE_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def build_climate_url(view: str, params: Dict[str, str]) -> str:
    """One PostgREST URL from a view + equality params."""
    query = urllib.parse.urlencode(params)
    return "%s/%s?%s" % (CLIMATE_BASE_URL, view, query)


def fetch_climate_rows(view: str, params: Dict[str, str],
                       cache_dir: str = "/tmp/hf-cache",
                       ttl_days: int = CLIMATE_TTL_DAYS) -> str:
    """Fetch one PostgREST slice politely (single GET, cached, TTL).

    Returns the local path. Transport errors RAISE (never cached as
    data); HTTP 429 propagates (stop signal, stale cache untouched).
    """
    os.makedirs(cache_dir, exist_ok=True)
    url = build_climate_url(view, params)
    path = _cache_path(cache_dir, view + "?" + urllib.parse.urlencode(params))
    if cache_is_fresh(path, ttl_days):
        return path
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    with open(path, "wb") as f:
        f.write(body)
    return path


#: Usable stations in/near Harjumaa (probed coords 2026-09-16). Cells
#: are nearest-station; eastern Harjumaa falls to the nearest of the
#: three and the reason names it (coarseness visible per score).
HARJUMAA_STATIONS: Dict[str, Dict[str, object]] = {
    "AJHARK01": {"name": "Tallinn-Harku", "lat": 59.398122,
                 "lon": 24.602870},
    "AJPAKR01": {"name": "Pakri", "lat": 59.3895, "lon": 24.0401},
    "AJKUUS01": {"name": "Kuusiku", "lat": 58.9732, "lon": 24.7340},
}


def _haversine_km(lat1: float, lon1: float,
                  lat2: float, lon2: float) -> float:
    """Great-circle km (local copy -- no sibling imports, no cycles)."""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    hav = (math.sin(dphi / 2.0) ** 2
           + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    return 2.0 * radius * math.asin(math.sqrt(hav))


def nearest_station(
        origin: Optional[Tuple[float, float]]) -> Optional[str]:
    """Nearest Harjumaa-cell station code for (lat, lon) / None."""
    if origin is None:
        return None
    lat, lon = origin
    best: Optional[str] = None
    best_km = float("inf")
    for code, station in HARJUMAA_STATIONS.items():
        dist = _haversine_km(lat, lon, float(station["lat"]),
                             float(station["lon"]))
        if dist < best_km:
            best, best_km = code, dist
    return best


def _dense_rank(value: float, others: List[float],
                reverse: bool = False) -> int:
    """Dense rank of value among others (ties share the better band)."""
    ordered = sorted(set(others), reverse=reverse)
    return ordered.index(value)


def _rank_dim(origin: Optional[Tuple[float, float]],
              cells: Optional[Dict[str, Dict[str, float]]],
              indicator: str, below: str, expos: str) -> Score:
    """Shared rank machinery: best joined cell 70 / next 55 / rest 40.

    `below` names the buyer direction ("leebem"/"kuivem"); `expos`
    is the unit-bearing value label for the reason.
    """
    station = nearest_station(origin)
    joined = {code: rec for code, rec in (cells or {}).items()
              if rec.get(indicator) is not None}
    if station is None or station not in joined or len(joined) < 2:
        return None, ("Mikrokliima raku hinnangut pole (EI OLE "
                      "selle koha jaama %d-%d normatiivkirjet -- "
                      "jaam teadmata/geokodeerimata voi liitunud rakke "
                      "vahem kui kaks, uhe raku pohjal ei saa järjestada): "
                      "kontrolli ilmateenistuse kliimanorme ja küsi "
                      "küttearveid/aiahooaega" % (NORMALS_START, NORMALS_END))
    mine = joined[station][indicator]
    rank = _dense_rank(mine, [rec[indicator] for rec in joined.values()])
    name = HARJUMAA_STATIONS[station]["name"]
    if len(joined) == 2:
        band = 70 if rank == 0 else 40  # no middle with two cells
    else:
        band = 70 if rank == 0 else (55 if rank == 1 else 40)
    word = ("kõige %s" % below) if rank == 0 else (
        "keskmine" if rank == 1 else "karmim")
    return band, ("Mikrokliima rakk %s (%s %d-%d normatiiv): %s "
                  "liitunud rakkudest (%s); jämekärgeline jaamarakk, "
                  "vahepealset interpolatsiooni pole" % (
                      name, expos, NORMALS_START, NORMALS_END, word, below))


def dim_winter_mildness(
        origin: Optional[Tuple[float, float]],
        cells: Optional[Dict[str, Dict[str, float]]]) -> Score:
    """P4 winter leg: fewer 1991-2020 frost days ranks better."""
    return _rank_dim(origin, cells, "frost_days", "leebem talv",
                     "külmapäevad")


def dim_wetness(origin: Optional[Tuple[float, float]],
                cells: Optional[Dict[str, Dict[str, float]]]) -> Score:
    """P4 wetness leg: less 1991-2020 precipitation ranks better."""
    return _rank_dim(origin, cells, "precip_mm", "kuivem",
                     "aastasademed mm")


#: Registry for UI/API wiring on integration: param -> (title, fn).
P4_KLIIMA_STATIONS_DIMS: Dict[str, Tuple[str, object]] = {
    "winter_mildness": ("Talve leebus (kliimajaam)", dim_winter_mildness),
    "wetness": ("Niiskus (kliimajaam)", dim_wetness),
}


def score_p4_kliima_stations(
        origin: Optional[Tuple[float, float]],
        cells: Optional[Dict[str, Dict[str, float]]],
) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All P4-kliima-station dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in P4_KLIIMA_STATIONS_DIMS.items():
        v, reason = fn(origin, cells)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
