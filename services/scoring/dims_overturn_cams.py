"""Overturn #238 (G7 CAMS / EGT-radon / KIK): coarse-raster hinnang legs.

Scope (issue #238): parameters3.md section 5.7 Group 7 no-map set
p66/p67/p137, p204/p252, p448/p471/p499. p260/p316/p401/p402 already
score as proxy dims in dims_group07c.py; p61/p62/p189/p202/p227/p257/
p409/p450 ship as exposure proxies elsewhere -- all siblings READ,
none edited. dims_group07*.py, livability.py, WEIGHTS and docs/nomap.md
are deliberately untouched here (the final docs-index PR owns nomap.md).

HUNT (2026-09-13, 9 tiny requests total, labelled one-off user-agent
`home-finder-238-hunt/1.0`, paced >= 4 s, headers + visible-text scope
read only, no scraping, no auth, no account creation; raw bodies at
/tmp/hf-cams/, never committed). Full log: docs/overturn_cams.md.
* CAMS/ADS: https://ads.atmosphere.copernicus.eu/how-to-api (HTTP 200)
  says "If you do not have an account yet, please register ... Once
  logged in, copy the code ... key: <PERSONAL-ACCESS-TOKEN>". Free
  data, but keyed per-person access -- per the issue RULE no account
  is created, so this dated negative keeps the verdict for the CAMS
  leg (official factsheet agrees: "registration is needed ... Through
  WebAPI a one-off key is needed").
* EGT radon: the radon-risk map EXISTS but as static human documents
  only -- Kliimaministeerium preliminary Rn-risk-area PDF (HEAD 200),
  the 9-sheet 1:500 000 map set per EVS 840:2003 (SSM explanatory
  text), JRC European Indoor Radon Map as a 10 km x 10 km viewer grid
  with login-gated bulk. No machine-readable per-parcel/class feed,
  so the live leg stays NULL; the coarse CLASS shape below (JRC 10 km
  grain) is proven on fixtures only.
* KIK residual pollution: kik.ee/et front (HTTP 200) is a grant-program
  news front -- zero visible-text mentions of jääkreostus / reostus /
  andmekogu / avaandmed. No open contaminated-sites DB surface is
  politely discoverable (KESE front is a JS shell, no server-rendered
  catalog). Dated negative keeps the verdict for the KIK leg.
* Documented alternate that is NOT there: parameters3.md section 5.7
  names `https://ohuseire.ee/api/v1/stations` -- the live host answers
  Symfony 404 "No route found", and the ohuseire.ee front is a
  37-visible-char JS shell ("Eesti ohukvaliteedi juhtimissusteem").
  Tallinn's 3 continuous stations stay human-page-only realtime.

What flips vs stays NULL (honest column):
* NOTHING flips live: all 8 params stay NULL without a cached extract
  (dated negatives above). The module ships honest plumbing with NO
  live data: fetch_cams_snapshot performs NO request while no gated
  result URL is supplied, and the two coarse-raster scorers score ONLY
  a cached extract -- fixture-proven shapes ready for reopen.
* p66 radon grid leg (dim_radon_grid_cams): nearest coarse cell within
  RADON_WINDOW_M scores the EVS/JRC class (korge->25, normaalne->60,
  madal->80 capped -- a regional class never proves a clean indoor
  meter reading; every scored reason says "hinnang" + "jäme" and names
  the Terviseamet measurement check). No grid / no cell in window /
  unknown klass / no origin all stay NULL ("EI OLE"): absence of a
  class is unknown, never clean.
* p204 KIK leg (dim_kik_sites_cams): nearest CONFIRMED residual-
  pollution site within KIK_WINDOW_M, bands mirroring
  dims_group07b.dim_brownsoil ([(200, 30), (500, 55), (1000, 75)] +
  (2000, 80) cap) so the confirmed-site leg reads consistently with
  the OSM brownfield proxy -- different keys, different grains, no
  double-scoring (same multi-leg precedent as P4-016 in kataster vs
  EGT). Beyond-window stays NULL, never clean: a confirmed-sites list
  is not a clean-area certificate and unmapped sites exist. Every
  scored reason says "hinnang" and cross-references p189.
* p67/p137/p252/p448/p471/p499 stay pure NULL (no extract shape at
  all): pest surveillance, machine pollen normals, species
  surveillance, harvest timing, pipe-material registry and facade
  aesthetics have no open feed -- refused near-misses documented in
  docs/overturn_cams.md (parks emit pollen; agrifield footprint with
  seasonal meaning duplicates p409; 0.13% age coverage as plumbing is
  noise). Every NULL reason says "hinnang" + "EI OLE" and names the
  concrete buyer-side check.

HONESTY (AGENTS.md section 7.2): measured values from an extract
score; missing joins stay NULL. Transport errors are never cached as
data (fetch writes the cache only after a completed read; errors
raise, 429 propagates as a stop signal, 7.4). Distances are
bird-flight, never routed. Scored reasons never contain "EI OLE"
(senscom/ookla invariant, pinned by tests).

Style mirrors dims_overturn_ehr.py (#234, the freshest overturn:
caller-supplied gated URL, TTL-stated cache, pure offline scorers,
hermetic fixture tests) and dims_p4_egt.py (#288, the honest-plumbing
precedent: local helpers, no livability import -- importing it here
would turn the future central hook into a cycle, same precedent as
PRs #100/#106/#115). Stdlib only (json + urllib, no new dependency).
There is NO staged Overpass fragment and no tag mapping: OSM has no
honest tag for CAMS ensemble cells, radon classes or KIK confirmed
sites, so there is nothing for the live path to fetch.

Judgment calls (reviewable per AGENTS.md section 7.5):
* RADON_WINDOW_M = 10 km is the JRC-grain judgment: the European
  Indoor Radon Map aggregates over 10 km x 10 km cells, so the join
  window is one cell width -- a tighter window would pretend the
  class map resolves streets it never surveyed.
* Radon bands (25/60/80, cap 80) are first-cut and MUST be
  recalibrated from real class counts on reopen; a "madal" cell
  scores 80, never 100 -- geology is not a meter reading.
* KIK bands mirror dim_brownsoil first-cut; the extra (2000, 80) cap
  band is the confirmed-site judgment (see above). Recalibrate from
  the real extract on reopen.
* fetch_cams_snapshot raises ValueError (not None) when no gated
  result URL is supplied (EHR precedent): a missing ticket is a
  caller error, while a missing JOIN stays NULL -- different layers,
  different signals.
* CAMS_TTL_S = 1 d follows the repo cron cadence (adapters poll
  daily); GRID_TTL_S = KIK_TTL_S = 180 d follows parameters3.md
  section 5.7 ("radon and brownfield layers cached with 180-day TTL").
* Re-check hook (the honest way these verdicts die): an ADS
  anonymous-tier or maintainer key, an EGT/JRC machine radon grid, or
  a KIK/EELIS contaminated-sites bulk URL appears -- re-open #238
  with the URL and propose the join. Re-check by RECHECK_AFTER.

Integration (deliberately NOT done here): feeding these dims with
ingested extracts inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches -- existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
"""

import io
import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Hunt date (2026-09-13) -- the day the nine polite checks above ran.
VERDICT_DATE = "2026-09-13"

#: Re-check the four discovery surfaces (ADS anonymous tier, EGT/JRC
#: machine radon grid, KIK/EELIS sites bulk, ohuseire machine API) no
#: later than this date.
RECHECK_AFTER = "2027-03-13"

# ---------------------------------------------------------------------------
# Ingestion contract: source identity, politeness, cache.
# ---------------------------------------------------------------------------

#: Provenance constants -- kept as documentation, NOT fetch targets
#: without a caller-supplied gated URL (dated negatives, see docstring).
ADS_HOWTO_URL = "https://ads.atmosphere.copernicus.eu/how-to-api"
ADS_DATASET_URL = ("https://ads.atmosphere.copernicus.eu/datasets/"
                   "cams-europe-air-quality-forecasts")
EGT_RADON_PDF_URL = ("https://kliimaministeerium.ee/sites/default/files/"
                     "documents/2021-07/Esialgne%20radooniriski%20"
                     "levilate%20kaart.pdf")
JRC_RADON_URL = ("https://remon.jrc.ec.europa.eu/About/"
                 "Atlas-of-Natural-Radiation/Digital-Atlas/"
                 "Indoor-radon-AM/Indoor-radon-concentration")

CAMS_USER_AGENT = (
    "home-finder-cams-overturn/1.0 (Estonia open-data adapter; "
    "polite single-pull, cache-first)"
)

#: Adapter polls daily (repo cron cadence, AGENTS.md section 5); the
#: CAMS ensemble itself refreshes faster server-side.
CAMS_TTL_S = 86400
#: parameters3.md section 5.7: radon and brownfield layers cache 180 d.
GRID_TTL_S = 15552000
KIK_TTL_S = 15552000


def _cache_path(cache_dir: str, name: str) -> str:
    return os.path.join(cache_dir, name + ".json")


def cache_is_fresh(path: str, ttl_s: int) -> bool:
    """True when a cache file exists and is younger than ttl_s."""
    try:
        return time.time() - os.path.getmtime(path) < ttl_s
    except OSError:
        return False


def fetch_cams_snapshot(cache_dir: str, name: str,
                        result_url: Optional[str] = None,
                        ttl_s: int = CAMS_TTL_S) -> str:
    """Fetch one key-gated CAMS result politely (single GET, cached).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. `result_url` is the gated result URL
    placed by the maintainer -- no anonymous ADS bulk URL is verified
    (dated negative 2026-09-13: account + personal token required, no
    account is created), so an empty url raises ValueError instead of
    guessing an endpoint or scripting the cdsapi task workflow.
    Transport errors RAISE (never cached as data, AGENTS.md 7.2);
    HTTP 429 propagates (stop signal, 7.4) leaving any stale cache
    untouched.
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, name)
    if cache_is_fresh(path, ttl_s):
        with io.open(path, encoding="utf-8") as f:
            return f.read()
    if not result_url:
        raise ValueError(
            "CAMS result URL puudub: anonüümset ADS-hulgilaadimise "
            "URL-i pole kinnitatud (dated negative 2026-09-13: ADS "
            "vajab kontot + personaalset votit, kontot ei looda) -- "
            "anna ette värava tulemuse URL või kasuta vahemälu")
    req = urllib.request.Request(  # noqa: S310 -- caller-supplied URL
        result_url, headers={"User-Agent": CAMS_USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        body = resp.read()
    text = body.decode("utf-8")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------------------
# Local helpers (no livability import -- cycle precedent, see docstring).
# ---------------------------------------------------------------------------

def _haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Bird-flight metres between (lat, lon) pairs. Never routed."""
    r = 6371000.0
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def _band(value: Optional[float],
          bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value (livability._band)."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _fmt_m(m: float) -> str:
    if m < 1000:
        return "%d m" % round(m)
    return "%.1f km" % (m / 1000.0)


def _nearest_cell_m(origin: Tuple[float, float],
                    cells: List[dict]) -> Optional[Tuple[float, dict]]:
    """Nearest well-formed cell to origin, else None. Pure."""
    best: Optional[Tuple[float, dict]] = None
    for cell in cells:
        try:
            lat = float(cell["lat"])
            lon = float(cell["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        m = _haversine_m(origin, (lat, lon))
        if best is None or m < best[0]:
            best = (m, cell)
    return best


# ---------------------------------------------------------------------------
# Snapshot schemas (what a future adapter would store; fixtures match).
# Radon grid: {"cells": [{"cell_id": str, "klass":
#   "korge"|"normaalne"|"madal", "lat": float, "lon": float}]}
# KIK sites: {"sites": [{"site_id": str, "name": str,
#   "lat": float, "lon": float}]}
# ---------------------------------------------------------------------------

#: EVS 840:2003 / JRC-grain radon classes the scorer understands.
#: Unknown labels are kept by the reader but fail closed to NULL in
#: the scorer: an unverified label is not a radon class.
RADON_KLASSID = ("korge", "normaalne", "madal")

#: One JRC cell width: the class map never surveyed streets.
RADON_WINDOW_M = 10000

#: Confirmed-site join window: a site record is a point, not a plume
#: model -- beyond 2 km its silence proves nothing either way.
KIK_WINDOW_M = 2000


def parse_radon_grid(text: str) -> Optional[Dict[str, list]]:
    """Parse a cached radon-class grid. Malformed -> None (unknown)."""
    try:
        doc = json.loads(text)
        cells = doc["cells"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if not isinstance(cells, list):
        return None
    return {"cells": cells}


def parse_kik_sites(text: str) -> Optional[List[dict]]:
    """Parse a cached KIK confirmed-sites extract. Malformed -> None."""
    try:
        doc = json.loads(text)
        sites = doc["sites"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if not isinstance(sites, list):
        return None
    return sites


# ---------------------------------------------------------------------------
# p66: coarse radon-class grid hinnang (JRC 10 km grain, EVS classes).
# ---------------------------------------------------------------------------

#: First-cut bands -- MUST be recalibrated from real class counts on
#: reopen. Capped at 80: a regional class never proves a clean indoor
#: meter reading.
RADON_BANDS = {"korge": 25, "normaalne": 60, "madal": 80}


def dim_radon_grid_cams(origin: Optional[Tuple[float, float]],
                        cells: Optional[List[dict]]) -> Score:
    """p66: radon hinnang from the nearest coarse class cell."""
    if not origin or cells is None:
        return None, ("Radooniruudu info puudub (EI OLE masinloetavat "
                      "radooniklassi voogu): EGT radoonikaart on "
                      "1:500 000 paberilehtede komplekt ja JRC 10 km "
                      "ruudustiku hulgilaadimine on suletud -- telli "
                      "Terviseameti mõõtmine ja kontrolli hoone "
                      "radoonitõkkeid kohapeal, ära feigi olematut "
                      "radooninumbrit")
    hit = _nearest_cell_m(origin, cells)
    if hit is None:
        return None, ("Radooniruudu info puudub (EI OLE liituvat "
                      "klassi akna sees): vahemälus pole korras "
                      "koordinaatidega rakke -- telli Terviseameti "
                      "mõõtmine, ära feigi")
    m, cell = hit
    if m > RADON_WINDOW_M:
        return None, ("Radooniruudu info puudub (EI OLE klassi %s "
                      "raadiuses): jäme ruudustik ei lahenda tänavaid "
                      "-- telli Terviseameti mõõtmine, ära feigi"
                      % _fmt_m(RADON_WINDOW_M))
    klass = cell.get("klass")
    if klass not in RADON_BANDS:
        return None, ("Radooniruudu info puudub (EI OLE kinnitatud "
                      "klassimärgendit): tundmatu markeering ei ole "
                      "radooniklass -- ära feigi")
    assert klass in RADON_KLASSID
    return (RADON_BANDS[klass],
            "Radoonihinnang (jäme, %s klass %s, %s): piirkondlik "
            "hinnang, mitte toamõõtmine -- madal klass ei tõesta "
            "puhast siseõhku, telli Terviseameti mõõtmine"
            % (cell.get("cell_id", "?"), klass, _fmt_m(m)))


# ---------------------------------------------------------------------------
# p204: confirmed residual-pollution site proximity (KIK extract leg).
# ---------------------------------------------------------------------------

#: First-cut bands mirroring dims_group07b.dim_brownsoil plus the
#: (2000, 80) cap band -- MUST be recalibrated from the real extract
#: on reopen. Capped at 80: the extract lists confirmed sites, never
#: clean-area certificates, and unmapped sites exist.
KIK_BANDS = [(200, 30), (500, 55), (1000, 75), (2000, 80)]


def dim_kik_sites_cams(origin: Optional[Tuple[float, float]],
                       kik: Optional[List[dict]]) -> Score:
    """p204: ohtlike ainete hinnang lähimast kinnitatud saastekohast."""
    if not origin or kik is None:
        return None, ("Saastekohtade info puudub (EI OLE masinloetavat "
                      "KIK jääkreostuse voogu): KIK esileht on toetus- "
                      "uudiste vaade ilma reostus- või avaandmete "
                      "pinnata ja Seveso-/ohuregister hetktõmmises "
                      "puudub -- küsi Keskkonnaametist kinnistu "
                      "jääkreostuse ajalugu ja saastunud pinnase uuringuid, "
                      "ära feigi olematut ohutusnumbrit")
    best: Optional[Tuple[float, dict]] = None
    for site in kik:
        try:
            lat = float(site["lat"])
            lon = float(site["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        m = _haversine_m(origin, (lat, lon))
        if best is None or m < best[0]:
            best = (m, site)
    if best is None:
        return None, ("Saastekohtade info puudub (EI OLE liituvaid "
                      "koordinaatidega objekte): vahemälu kirjed on "
                      "tühjad või katkised -- küsi Keskkonnaametist, "
                      "ära feigi")
    m, site = best
    if m > KIK_WINDOW_M:
        return None, ("Saastekohtade info puudub (EI OLE kinnitatud "
                      "kohta %s raadiuses): nimekiri ei ole puhta ala "
                      "tunnistus ja kaardistamata kohad loevad edasi "
                      "-- küsi Keskkonnaametist, ära feigi"
                      % _fmt_m(KIK_WINDOW_M))
    s = _band(m, KIK_BANDS)
    assert s is not None
    return (s, "Saastehinnang (jäme, KIK %s, %s): kinnitatud koha "
               "kaugus, mitte pinnaseproov -- p189 pruunvälja proksi "
               "hindab kaardistatud tootmismaad, see jalg hindab "
               "kinnitatud jääkreostust"
            % (site.get("site_id", "?"), _fmt_m(m)))


# ---------------------------------------------------------------------------
# p67/p137/p252/p448/p471/p499: documented no-map NULLs (OTA PR #131
# precedent). No open feed carries these signals even in principle at
# the checked surfaces, so they stay NULL -- never faked. Refused
# near-misses (documented in docs/overturn_cams.md): p137 must NOT
# reuse mapped green (parks EMIT pollen); p448 must NOT reuse the
# p409 agrifield footprint with seasonal meaning (that would duplicate
# p409's map as fake harvest timing); p471 must NOT reuse building age
# (644/509656 = 0,13% age tags, zero pipe tags -- noise presented as
# plumbing); p499 is a facade-aesthetics judgment with no data at all.
# ---------------------------------------------------------------------------

def dim_pests_cams(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p67: kahjuritel/metsloomadel pole avatud seirevoogu -- alati None."""
    _ = (origin, pois)
    return None, ("Kahjurite/metsloomade info puudub (EI OLE "
                  "kahjuriseire voogu, hinnangut pole): küsi müüjalt/ "
                  "haldurilt näriliste- ja putukatõrje ajalugu ning "
                  "vaata hoone ümbrus kohapeal üle, ära feigi olematut "
                  "seirenumbrit")


def dim_allergens_cams(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p137: allergeenidel pole masinloetavat seirevoogu -- alati None."""
    _ = (origin, pois)
    return None, ("Allergeenide info puudub (EI OLE masinloetavat "
                  "õietolmuvoogu, hinnangut pole): aerobioloogiline "
                  "seire ilmub õhuseire lehel inimloetavana ning haljas "
                  "loeks vastupidi -- pargid eritavad õietolmu; jälgi "
                  "õietolmuhoiatusi ja vali elukohta raviarsti "
                  "soovituste järgi, ära feigi olematut "
                  "allergeeninumbrit")


def dim_invasive_cams(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p252: invasiivtaimedel pole avatud liigiseiret -- alati None."""
    _ = (origin, pois)
    return None, ("Invasiivtaimede info puudub (EI OLE liigiseire voogu, "
                  "hinnangut pole): haljas loeks mõttetult -- enamik "
                  "kaardistatud puid on pärismaised või istutatud; "
                  "vaata krunt kohapeal üle ja küsi Keskkonnaameti "
                  "võõrliikide infot, ära feigi olematut liiginumbrit")


def dim_harvest_cams(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """p448: lõikusan hooaja ajastus on teadmata -- alati None."""
    _ = (origin, pois)
    return None, ("Lõikusaja info puudub (EI OLE hooaja ajastuse voogu, "
                  "hinnangut pole): p409 põllumajandusmaa proksi katab "
                  "ruumi, hooaega ei mõõda ükski voog -- ruumilise "
                  "proksi hooajaline koopia dubleeriks p409 kaarti "
                  "libeda täpsusega; küsi talunikelt lõikusegraafikut "
                  "ja külasta kohta lõikusajal, ära feigi olematut "
                  "hooajanumbrit")


def dim_leadpipes_cams(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """p471: torumaterjal on kaardistamata -- alati None."""
    _ = (origin, pois)
    return None, ("Torustiku info puudub (EI OLE torumaterjali voogu, "
                  "hinnangut pole): hoone vanusemärge katab 0,13% "
                  "hoonetest ja torumaterjali märgetel on null -- "
                  "vanuseproksi oleks müra torustikuna; küsi "
                  "veefirmalt/ühistult liitumispunkti torumaterjali "
                  "ja telli veeproov, ära feigi olematut torunumbrit")


def dim_radon_aesth_cams(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p499: radoonitõrje esteetika on fassaadihinnang -- alati None."""
    _ = (origin, pois)
    return None, ("Radoonitõrje esteetika mõõtmata (EI OLE fassaadi- "
                  "hinnangu voogu, hinnangut pole): torud ja tuulutus "
                  "selguvad maja seinalt, mitte ühestki registrist -- "
                  "ka radoonitasemed (p66) on klassihinnang, mitte "
                  "mõõtmine; vaata fassaad kohapeal üle ja küsi "
                  "Terviseameti mõõtmist, ära feigi olematut "
                  "esteetikanumbrit")


#: Dim key -> parameters3.md number (no-map dims included: they are
#: scored -- as NULL by default, as hinnang off a cached extract for
#: p66/p204 -- by score_overturn_cams below).
OVERTURN_CAMS_PARAM_IDS = {
    "radoon_ruut_cams": 66,
    "saaste_kik_cams": 204,
    "kahjur_seire_cams": 67,
    "allergeen_seire_cams": 137,
    "invasiiv_seire_cams": 252,
    "loikus_seire_cams": 448,
    "pliitoru_seire_cams": 471,
    "radoon_fassaad_cams": 499,
}

OVERTURN_CAMS_DIMS = (
    ("radoon_ruut_cams", "p66", dim_radon_grid_cams),
    ("saaste_kik_cams", "p204", dim_kik_sites_cams),
    ("kahjur_seire_cams", "p67", dim_pests_cams),
    ("allergeen_seire_cams", "p137", dim_allergens_cams),
    ("invasiiv_seire_cams", "p252", dim_invasive_cams),
    ("loikus_seire_cams", "p448", dim_harvest_cams),
    ("pliitoru_seire_cams", "p471", dim_leadpipes_cams),
    ("radoon_fassaad_cams", "p499", dim_radon_aesth_cams),
)

#: Dims whose snapshot travels explicitly (the demoed ingestion
#: product); the pure-NULL legs take (origin, pois) like the p317
#: precedent.
_EXTRACT_KEYS = ("radoon_ruut_cams", "saaste_kik_cams")


def score_overturn_cams(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]] = None,
                        cells: Optional[List[dict]] = None,
                        kik: Optional[List[dict]] = None
                        ) -> Dict[str, Optional[int]]:
    """Score the eight #238 overturn dims for one listing (entry point
    for the weight-rebalance follow-up; keys match OVERTURN_CAMS_DIMS).
    Without cached extracts every dim is None."""
    extracts = {"radoon_ruut_cams": cells, "saaste_kik_cams": kik}
    out: Dict[str, Optional[int]] = {}
    for key, _, fn in OVERTURN_CAMS_DIMS:
        if key in extracts:
            out[key] = fn(origin, extracts[key])[0]  # type: ignore[arg-type]
        else:
            out[key] = fn(origin, pois)[0]  # type: ignore[arg-type]
    return out