"""P4 Maa-amet LiDAR/DEM/LoD2 dims: demo (#247) + coverage (#331).

Demo param (this ingestion's anchor):
* P4-041 Glimpse economics (piilukas view sliver) -> dim_glimpse_view

Coverage params (extend the demoed ingestion, no new plumbing beyond the
demo's per-parcel ``lidar`` artefact — said here as #331 requires):
* P4-016 Engineering geology (turvas/karst/alvar) -> dim_engineering_geology
* P4-031 Backyard weather + DIY air -> dim_backyard_weather
* P4-034 Summer overheating risk -> dim_overheat_shading
* P4-035 December darkness -> dim_darkness_shading
* P4-036 Roof income (solar/mast/ads) -> dim_roof_income
* P4-056 Enclosed-courtyard trap -> dim_courtyard_trap

OPENNESS VERDICT (probed 2026-09-13, six polite pulls, cached /tmp/hf-maa-lidar
— full evidence in docs/p4_maa_lidar.md): OPEN on both legs.
* Elevation/DEM/LiDAR download page lists per-map-sheet raw LiDAR (spring
  low-altitude, summer forestry, surface keypoints) plus whole-Estonia
  DTM/DSM/CHM GeoTIFFs and per-sheet DTM 1/5/10 m GeoTIFF+XYZ
  (last update 29.04.2026, open-data licence).
* 3D download page lists per-municipality LoD1 AND LoD2 (``hooned_lod1`` /
  ``hooned_lod2``) in citygml/gdb/obj — incl. Tallinn LoD2 CityGML.
* HEAD on the Tallinn LoD2 CityGML file URL: HTTP 200,
  ``content-type: application/zip``, 33 043 884 B, content-disposition
  filename ``hooned_lod2-Tallinn-citygml.zip`` — the bulk file endpoint
  serves, no key, no login.
* WMS ``alus`` GetCapabilities carries NO elevation/DEM/LiDAR/3D layer
  (relief-shaded basemap only) — view, never data; dated note, not a block.
* One HEAD on a whole-Estonia DTM .tif timed out (25 s, 0 bytes): transport
  non-answer, NOT a negative — the identical ``dl=1`` pattern is proven by
  the LoD2 HEAD; re-probe on bulk-job day, do not hammer.

HONESTY (AGENTS.md section 7.2): the only scored shapes in this module are
per-listing / per-parcel GEOMETRY JOINS against the caller-supplied ``lidar``
artefact (DEM stats, LoD2 enclosure/shading/view-fan/roof facets for that
parcel) — never a distance gradient, never interpolation, never a faked
area score. The bulk files are open but NOT in the snapshot, so a missing
artefact (or a missing artefact leg) stays NULL with an Estonian reason that
says "hinnang" and "EI OLE" and names the concrete check (bulk re-pull,
EHR listing fact, on-site visit) — never a faked number. Transport errors
in fetch_cached are NEVER cached as data, and HTTP 429 is a stop signal,
not a retry dare (AGENTS.md sections 7.2/7.4).

Style: pure offline scorers (listing, lidar) -> (Optional[int 0..100],
Estonian reason), mirroring sibling batch dims_p4_maa_tehingud.py (#244).
Network lives ONLY in fetch_cached (polite single-GET + file cache + TTL);
tests never touch the network. No livability/WEIGHTS/layers integration here —
rebalancing stays one joint change across batches (existing tests pin WEIGHTS).

Boundary vs sibling batches (no double-scoring, no overlap):
* P4-031/P4-034/P4-035/P4-056 also have Ilmateenistus legs owned by
  dims_p4_ilm.py (#383: Harku baseline bands, documented NULLs pointing AT
  the missing LiDAR input). This module owns ONLY the LiDAR/DEM/LoD2 legs;
  reasons cross-reference the ilm leg instead of re-scoring it.
* P4-016's EGT-map/WFS legs belong to the #235 Maa-amet overturn (untouched
  here); this module scores ONLY the coarse DEM settlement/fill screen,
  per parameters4.md ("coarse only").
* P4-036's Elering feed-in / Elektrilevi / ad-tariff legs are named as
  missing (EI OLE) in the reason; only the LoD2 roof-facet leg scores.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #331's body states it extends
  the #247 demo ingestion ("no new plumbing expected unless a param needs
  it"): the per-parcel ``lidar`` artefact dict IS the anticipated plumbing
  (calendar/geo joins cannot ride the OSM POI channel), said here as #331
  acceptance requires.
* TTL 365 d for both bulks: ~1/4 of Estonia is re-flown yearly and LoD2 is
  updated annually (Geo3D summary); the download pages show last update
  29.04.2026. Annual re-pull, quarterly re-probe of the verdict.
* Score bands are coarse first-cut judgments (challengeable, dull by design):
  view slivers >= 3 deg -> 85 / thin -> 70 / none -> 45; DEM anomaly -> 40
  else 60; frost-pocket depression -> 45 else 60; shade-cooled -> 65,
  exposed top floor capped at 40 (full sim needs EHR facts), else 55;
  darkness 35/50/65 capped (lamps need the inventory); roof kWp >= 3 -> 75 /
  >= 1.5 -> 60 / > 0 -> 50 / none -> 40 (upside-only); courtyard trapped
  (index >= 1.2) -> 35 / courtyard open -> 55 / no courtyard -> 70.
* Roof kWp rule: 8 m2 per kWp; facets count when 10-60 deg tilt and < 50%
  shaded; flat roofs count at 0.7 (racking/spacing loss).
* Enclosure index = mean surrounding wall height / courtyard width; >= 1.2
  reads as trapped (deep well holds cold + fumes + heat).
* Frost-pocket screen: parcel DEM >= 1.0 m below the surrounding median
  (cold-air pooling); settlement/fill screen: sink >= 0.5 m or roughness
  >= 1.0 m (coarse only — EGT class still required, named in the reason).

Integration (deliberately NOT done here): the annual bulk job (download
Tallinn LoD2 CityGML + covering DTM sheets, parse to per-parcel artefacts),
any livability hook, and rebalancing livability.WEIGHTS must be one joint
change across all parameter batches. No shared files touched: 3 new files
only. Never touch dims_group03*.py (#235 overturn owns the Maa-amet WFS legs).
"""

import datetime as _dt
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #247 acceptance criterion 2).
# ---------------------------------------------------------------------------

GEOPORTAAL_BASE = "https://geoportaal.maaruum.ee"

SOURCE_URLS = {
    # Human download pages (verified 2026-09-13: HTTP 200, open-data licence).
    "elevation_download_page": (
        GEOPORTAAL_BASE + "/eng/spatial-data/elevation-data/"
        "download-elevation-data-p664.html"
    ),
    "lod3d_download_page": (
        GEOPORTAAL_BASE + "/eng/spatial-data/geo3d/download-3d-data-p837.html"
    ),
    "licence": GEOPORTAAL_BASE + "/opendata-licence",
    # Bulk file endpoint pattern (verified 2026-09-13 via HEAD: HTTP 200,
    # application/zip, 33 043 884 B for the Tallinn LoD2 CityGML).
    "tallinn_lod2_citygml": (
        GEOPORTAAL_BASE + "/index.php?lang_id=2&plugin_act=otsing"
        "&andmetyyp=hooned_lod2&dl=1&f=hooned_lod2-Tallinn-citygml.zip"
        "&page_id=837"
    ),
}

# TTLs in days: ~1/4 of Estonia re-flown yearly, LoD2 updated annually
# (Geo3D summary); pages showed last update 29.04.2026.
TTL_DAYS = {
    "lod2_bulk": 365,  # per-municipality LoD1/LoD2 zips
    "dtm_bulk": 365,  # per-sheet DTM/DSM/CHM + whole-Estonia vintages
}

CACHE_SUBDIR = "hf-p4-maa-lidar"
USER_AGENT = (
    "home-finder-research/0.1 (polite annual bulk; "
    "GitHub gregoreesmaa/home-finder issue 247)"
)


def lod2_url(municipality: str = "Tallinn", fmt: str = "citygml") -> str:
    """Bulk file URL for one municipality LoD zip (pure URL builder)."""
    safe = "".join(c for c in municipality if c.isalnum() or c in ("-", "_"))
    return (
        GEOPORTAAL_BASE + "/index.php?lang_id=2&plugin_act=otsing"
        "&andmetyyp=hooned_lod2&dl=1&f=hooned_lod2-%s-%s.zip&page_id=837"
        % (safe, fmt)
    )


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
    Pulls urllib only (no new dependency). Bulk zips (~30 MB) are annual,
    so at most one live pull per TTL per file.
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


# ---------------------------------------------------------------------------
# Pure parsers + geometry helpers (fixture-scale; hermetically tested).
# ---------------------------------------------------------------------------

def parse_dtm_xyz(text: str) -> dict:
    """Parse whitespace ``x y z`` rows to elevation stats (pure).

    Malformed rows are skipped (never crash the bulk job on one bad row).
    Empty input yields n=0 with None stats (dims NULL it, never zero-fill).
    """
    zs: List[float] = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            zs.append(float(parts[2].replace(",", ".")))
        except ValueError:
            continue
    if not zs:
        return {"n": 0, "min_m": None, "mean_m": None, "max_m": None}
    return {"n": len(zs), "min_m": min(zs),
            "mean_m": sum(zs) / len(zs), "max_m": max(zs)}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def parse_lod2_summary(citygml_text: str) -> dict:
    """Summarise a (fixture-scale) CityGML payload to building stats (pure).

    Counts ``Building`` features and collects ``measuredHeight`` /
    ``storeysAboveGround`` values. Raises ValueError on unparseable XML
    (transport garbage is never a record — same rule as dims_p4_ilm).
    """
    try:
        root = ET.fromstring(citygml_text)
    except ET.ParseError as exc:
        raise ValueError("CityGML ei parsinud: %s" % exc)
    n = 0
    heights: List[float] = []
    storeys: List[int] = []
    for el in root.iter():
        name = _local(el.tag)
        if name == "Building":
            n += 1
        elif name == "measuredHeight" and (el.text or "").strip():
            try:
                heights.append(float(el.text.strip().replace(",", ".")))
            except ValueError:
                continue
        elif name == "storeysAboveGround" and (el.text or "").strip():
            try:
                storeys.append(int(float(el.text.strip().replace(",", "."))))
            except ValueError:
                continue
    return {"n_buildings": n, "heights_m": heights, "storeys": storeys}


def enclosure_index(wall_h_m: Optional[float],
                    courtyard_w_m: Optional[float]) -> Optional[float]:
    """Courtyard enclosure index = wall height / courtyard width (pure).

    >= ENCLOSURE_TRAPPED (1.2) reads as a trapped well. None on bad input
    (dims NULL it — never divide by zero into a score).
    """
    if wall_h_m is None or courtyard_w_m is None:
        return None
    try:
        h, w = float(wall_h_m), float(courtyard_w_m)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h < 0:
        return None
    return h / w


ENCLOSURE_TRAPPED = 1.2  # h/w at/above which a courtyard reads as trapped
KWP_M2_PER_KWP = 8.0  # roof area per kWp (coarse rule of thumb)


def usable_roof_kwp(facets: Optional[List[dict]],
                    flat_m2: Optional[float] = None,
                    flat_shaded: Optional[float] = None) -> Tuple[float, float]:
    """Usable roof area (m2) + kWp estimate from LoD2 roof facets (pure).

    A pitched facet counts when 10-60 deg tilt and < 50% shaded; flat roofs
    count at 0.7 (racking/spacing loss) under the same shading bar.
    """
    usable = 0.0
    for f in facets or []:
        try:
            area = float(f.get("area_m2") or 0)
            tilt = float(f.get("tilt_deg"))
            shaded = float(f.get("shaded_share", 0) or 0)
        except (TypeError, ValueError, AttributeError):
            continue
        if area <= 0 or not 10.0 <= tilt <= 60.0 or shaded >= 0.5:
            continue
        usable += area
    try:
        flat = float(flat_m2 or 0)
        fsh = float(flat_shaded if flat_shaded is not None else 0)
    except (TypeError, ValueError):
        flat, fsh = 0.0, 0.0
    if flat > 0 and fsh < 0.5:
        usable += 0.7 * flat
    return usable, usable / KWP_M2_PER_KWP


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _lidar_leg(lidar: Optional[dict], leg: str) -> Optional[dict]:
    if not isinstance(lidar, dict):
        return None
    sub = lidar.get(leg)
    return sub if isinstance(sub, dict) else None


# ---------------------------------------------------------------------------
# Demo dim: P4-041 glimpse economics (issue #247).
# ---------------------------------------------------------------------------

#: View-sliver bands (degrees of sea/Old Town/spire sliver in the fan).
GLIMPSE_WIDE_DEG = 3.0  # at/above: piilukas premium candidate


def dim_glimpse_view(listing: dict, lidar: Optional[dict]) -> Score:
    """P4-041: sea/Old Town/spire sliver class from the LoD2 view-fan.

    Scores the LiDAR/LoD2 leg only: a measured sliver is real geometry, so
    it scores; the piilukas-vs-no-view PRICE premium needs the tehingud leg
    (P4-002 micro-comp) and is named as missing, never faked. NULL when the
    view-fan artefact or the listing floor (EHR fact) is absent.
    """
    floor = listing.get("floor")
    if not isinstance(floor, int) or floor < 0:
        return None, ("Korrust kuulutuses/EHR-is EI OLE — piiluka-hinnang "
                      "puudub: vaatelehtri arvutus vajab vaatleja kõrgust, "
                      "kontrolli kuulutuse korrust, ära feigi")
    fan = _lidar_leg(lidar, "view_fan")
    if fan is None:
        return None, ("LoD2 vaatelehtri artefakti (Maa-ameti 3D-laadimine, "
                      "Tallinna CityGML) EI OLE — piiluka-hinnang puudub: "
                      "mere/vanalinna piilukas selgub krundi lehvikust, mitte "
                      "kaardivärvist")
    try:
        sea = float(fan.get("sea_sliver_deg") or 0)
        old = float(fan.get("oldtown_sliver_deg") or 0)
    except (TypeError, ValueError):
        return None, ("Vaatelehtri kraadid on vigased — piiluka-hinnangut EI "
                      "OLE (artefakti viga)")
    sliver = max(sea, old)
    if sliver >= GLIMPSE_WIDE_DEG:
        score = 85
        word = "lai piilukas"
    elif sliver > 0:
        score = 70
        word = "kitsas piilukas"
    else:
        score = 45
        word = "vaateta (võrdlusbaas)"
    return score, ("%s: mere lehvik %.1f°, vanalinna lehvik %.1f° (%d. korrus, "
                   "LoD2-hinnang): piiluka-hinnang %d/100 (hinnalisa vs "
                   "vaateta korterite jalga EI OLE — võrdle P4-002 "
                   "mikro-võrdlusega)" % (word, sea, old, floor, score))


# ---------------------------------------------------------------------------
# Coverage dims: the 6 remaining params off this source (issue #331).
# ---------------------------------------------------------------------------

def dim_engineering_geology(listing: dict, lidar: Optional[dict]) -> Score:
    """P4-016: coarse DEM settlement/fill screen (LiDAR leg only).

    Flags suspicious ground (sink or rough micro-relief = possible fill /
    settlement); quiet ground scores a neutral 60 — the turvas/karst/alvar
    CLASS still needs the EGT map (#235 overturn leg), named never faked.
    """
    _ = listing
    dem = _lidar_leg(lidar, "dem")
    if dem is None:
        return None, ("Krundi DEM-sõela (Maa-ameti kõrgusmudeli laadimine) EI "
                      "OLE — pinnase-hinnang puudub: vajumi/täite kahtlus "
                      "selgub DEM-ist, turvas/karst/alvar klass EGT kaardilt")
    try:
        sink = float(dem.get("sink_m") or 0)
        rough = float(dem.get("roughness_m") or 0)
    except (TypeError, ValueError):
        return None, ("DEM-statistika on vigane — pinnase-hinnangut EI OLE "
                      "(artefakti viga)")
    if sink >= 0.5 or rough >= 1.0:
        return 40, ("DEM-anomaalia (vajum %.1f m, karedus %.1f m): täite/ "
                    "vajumikahtluse hinnang 40/100 — EGT insenergeoloogia "
                    "klassi (turvas/karst/alvar) EI OLE, küsi geoloogilist "
                    "kaarti/uuringut" % (sink, rough))
    return 60, ("Rahulik DEM (vajum %.1f m, karedus %.1f m): jäme "
                "sõela-hinnang 60/100 — pinnaseklassi (turvas/karst/alvar) "
                "jalga EI OLE, EGT kaart kontrollib" % (sink, rough))


def dim_backyard_weather(listing: dict, lidar: Optional[dict]) -> Score:
    """P4-031: LiDAR cold-air drainage leg (frost-pocket screen).

    A parcel sitting >= 1 m below its surroundings pools cold air (real
    terrain physics, coarse); anything finer needs the DIY sensor density
    (sensor.community) the snapshot lacks — named, never faked. The Harku
    city baseline lives in dims_p4_ilm.py, not here.
    """
    _ = listing
    dem = _lidar_leg(lidar, "dem")
    if dem is None:
        return None, ("Krundi DEM-sõela (külmaõhu nõo kontroll) EI OLE — hoovi "
                      "mikrokliima-hinnang puudub: Harku linnabaas on "
                      "dims_p4_ilm jalas, DIY-andurite tihedust "
                      "(sensor.community) hetktõmmises pole — loe andureid "
                      "kohapeal")
    try:
        parcel = float(dem["parcel_m"])
        surr = float(dem["surround_median_m"])
    except (TypeError, ValueError, KeyError):
        return None, ("DEM-kõrgused (krunt/ümbrus) puuduvad — hoovi "
                      "külmakoti-hinnangut EI OLE (artefakti viga)")
    dip = surr - parcel
    if dip >= 1.0:
        return 45, ("Krunt %.1f m ümbrusest madalamal (DEM-hinnang): külmakoti "
                    "kahtlus 45/100 — kütte/rõdu tõde selgub DIY-andurite "
                    "tihedusest, mida EI OLE" % dip)
    return 60, ("Krunt ümbruse tasemel (DEM-vahe %+.1f m, hinnang): külmakoti "
                "signaali EI OLE 60/100 — tuulekoridori kontrolli kohapeal, "
                "andurijalga EI OLE" % -dip)


def dim_overheat_shading(listing: dict, lidar: Optional[dict]) -> Score:
    """P4-034: LoD2 shading/through-draft geometry leg (capped).

    Deep LoD2 shade genuinely cools (scores up); an exposed top floor scores
    down but NEVER below 40 on geometry alone — the S/W-glazing sim needs EHR
    orientation/floor facts plus the Harku July band (dims_p4_ilm leg).
    """
    shading = _lidar_leg(lidar, "shading")
    if shading is None:
        return None, ("LoD2 varju-artefakti (naaberhoonete vari/läbiv tuulutus) "
                      "EI OLE — kuumenemis-hinnang puudub: juuli baasjoon on "
                      "dims_p4_ilm jalas, S/W suund ja korrus selguvad "
                      "kuulutusest/EHR-ist")
    try:
        sky = float(shading["open_sky"])
    except (TypeError, ValueError, KeyError):
        return None, ("Varju avataeva-osakaal puudub — kuumenemis-hinnangut EI "
                      "OLE (artefakti viga)")
    south = bool(shading.get("south_open"))
    top = bool(listing.get("top_floor"))
    if sky < 0.35:
        return 65, ("Sügav LoD2-vari (avataevas %.0f%%, hinnang): varju "
                    "jahutuse-hinnang 65/100 — S/W-akende simulatsiooni jalga "
                    "EI OLE" % (sky * 100.0))
    if top and south:
        return 40, ("Avatud lõuna/taevas (avataevas %.0f%%) ülemisel korrusel: "
                    "kuumenemisrisk 40/100 (hinnang, geomeetria-jalg üksi — "
                    "EHR-orientatsiooni simulatsiooni EI OLE)" % (sky * 100.0))
    return 55, ("Keskmine LoD2-vari (avataevas %.0f%%, hinnang): kuumenemise "
                "hinnang 55/100 — korruse/suuna täpsustust EI OLE" % (sky * 100.0))


def dim_darkness_shading(listing: dict, lidar: Optional[dict]) -> Score:
    """P4-035: LoD2 courtyard-shading leg (capped).

    Less sky = darker December courtyard (real geometry); capped at 65 —
    lamps need the street-light inventory and the Harku December band lives
    in dims_p4_ilm.py, both named, never faked.
    """
    _ = listing
    shading = _lidar_leg(lidar, "shading")
    if shading is None:
        return None, ("LoD2 varju-artefakti (hoovi varju kontroll) EI OLE — "
                      "pimeduse-hinnang puudub: detsembri baasjoon on "
                      "dims_p4_ilm jalas, tänavavalgustuse inventuuri EI OLE")
    try:
        sky = float(shading["open_sky"])
    except (TypeError, ValueError, KeyError):
        return None, ("Varju avataeva-osakaal puudub — pimeduse-hinnangut EI "
                      "OLE (artefakti viga)")
    if sky < 0.3:
        score = 35
    elif sky < 0.6:
        score = 50
    else:
        score = 65
    return score, ("LoD2 avataevas %.0f%% (hoovi varju-hinnang): detsembri "
                   "pimeduse-hinnang %d/100 (valgustite/inventuuri jalga EI "
                   "OLE — kontrolli tänavavalgustus ja akende suund)"
                   % (sky * 100.0, score))


def dim_roof_income(listing: dict, lidar: Optional[dict]) -> Score:
    """P4-036: LoD2 roof-facet upside leg (genuinely scores).

    Usable facet area -> kWp is the param's core geometry (PVLib shading
    inputs in parameters4.md); the Elering feed-in tariff, Elektrilevi export
    feasibility and gable-ad yield are named as missing (EI OLE), so the dim
    is upside-only and never a yield promise.
    """
    _ = listing
    roof = _lidar_leg(lidar, "roof")
    if roof is None:
        return None, ("LoD2 katuse-artefakti (tahvlid/kalded/varjud) EI OLE — "
                      "katusetulu-hinnang puudub: Eleringi mikrotootja reeglite "
                      "ja reklaamitariifi jalga EI OLE niikuinii")
    usable, kwp = usable_roof_kwp(roof.get("facets"),
                                  roof.get("flat_m2"),
                                  roof.get("flat_shaded_share"))
    if kwp >= 3.0:
        score = 75
    elif kwp >= 1.5:
        score = 60
    elif kwp > 0:
        score = 50
    else:
        return 40, ("Kasutatavat katusepinda EI OLE (LoD2-hinnang): "
                    "katusetulu-ülespoole jalga pole 40/100 — masti/reklaami "
                    "võimalust EI OLE hinnatud")
    return score, ("Kasutatav katus %.0f m² (~%.1f kWp, LoD2-hinnang): "
                   "katusetulu ülespoole-hinnang %d/100 (Eleringi "
                   "tagasiostu-tariifi jalga EI OLE — tootluslubadust pole)"
                   % (usable, kwp, score))


def dim_courtyard_trap(listing: dict, lidar: Optional[dict]) -> Score:
    """P4-056: LiDAR enclosure-index leg (genuinely scores).

    A walled well (index >= 1.2) holds cold + fumes + heat (real morphology);
    the fume-hold validation (air stations) and wind ventilation proxy live
    outside this leg (dims_p4_ilm calm-share context) — named, never faked.
    """
    _ = listing
    enc = _lidar_leg(lidar, "enclosure")
    if enc is None:
        return None, ("LiDAR-kinnisuse artefakti (hoovi indeks) EI OLE — hoovi "
                      "lõksu-hinnang puudub: Harku tuulevaikuse proksi on "
                      "dims_p4_ilm jalas, hoovi kuju kontrolli aerofotolt")
    if not enc.get("courtyard"):
        return 70, ("Avatud krunt (suletud hoovi EI OLE, LoD2-hinnang): lõksu- "
                    "hinnang 70/100 — mikrokliimataskut pole")
    try:
        index = float(enc["index"])
    except (TypeError, ValueError, KeyError):
        return None, ("Kinnisuse indeks puudub — hoovi lõksu-hinnangut EI OLE "
                      "(artefakti viga)")
    if index >= ENCLOSURE_TRAPPED:
        return 35, ("Suletud hoov, indeks %.1f (LoD2-hinnang): külma + "
                    "heitgaaside + kuumuse lõksu-hinnang 35/100 (õhujaama "
                    "valideerimist EI OLE)" % index)
    return 55, ("Poolavatud hoov, indeks %.1f (LoD2-hinnang): lõksu-hinnang "
                "55/100 — tuulutusvaru kontrolli kohapeal" % index)


# ---------------------------------------------------------------------------
# Registry + aggregator (entry point for the weight-rebalance follow-up).
# ---------------------------------------------------------------------------

P4_MAA_LIDAR_DIMS = (
    ("glimpse_view", "P4-041", dim_glimpse_view),
    ("eng_geology", "P4-016", dim_engineering_geology),
    ("backyard_weather", "P4-031", dim_backyard_weather),
    ("overheat_shading", "P4-034", dim_overheat_shading),
    ("darkness_shading", "P4-035", dim_darkness_shading),
    ("roof_income", "P4-036", dim_roof_income),
    ("courtyard_trap", "P4-056", dim_courtyard_trap),
)


def score_p4_maa_lidar(listing: dict,
                       lidar: Optional[dict]) -> Dict[str, Optional[int]]:
    """All 7 P4 Maa-LiDAR dims for one listing (keys match registry)."""
    return {key: fn(listing, lidar)[0] for key, _, fn in P4_MAA_LIDAR_DIMS}

