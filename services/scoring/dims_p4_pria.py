"""P4 PRIA field-block dims (issue #299, single-param demo, no coverage issue).

Demo (#299): PRIA pollumassiivid (field blocks) for P4-024 end-to-end
in Tallinn — openness dig plus the honest-shape spray-drift leg.
Single param: P4-024 Country-health nuisances, PRIA slice (batch 2:
Harku/Lasnamäe fringe spray-drift buffers). Honest shape now SCORED:
coarse hinnang cells off joined WFS block polygons (distance bands,
never per-parcel precision, never 0/100 on this leg alone).

OPENNESS DIG (2026-09-16, AGENTS.md section 7.7 — the 2026-09-13
verdict found PRIA's daily-bulk claim pointing at a JS-shell
catalogue and stopped). Polite evidence, 10 tiny reads total
(labelled one-off user-agent `home-finder pria dig (issue #299,
one-off, tiny reads, no scrape)`, 2-4 s pacing, `--max-time
25-90`, headers + visible-text + bundle-static + API-JSON scope
only, no scraping, no auth, no form driving, no retries — HTTP
429/errors are a stop signal; none hit). Raw bodies kept at
/tmp/hf-dig-pria/ (one-off PR record, never committed):
* GET andmed.eesti.ee/api/3/action/package_search?q=pria ->
  HTTP 404 (not CKAN — custom Teabevärav app; tried once).
* GET andmed.eesti.ee/dataset?q=pria (shell, 75 497 B) + its
  bundles main-APERHQ4S.js (55 B stub) + main-CenoT8FQ.js
  (1 274 241 B): same-origin JSON API at /api/datasets/search
  (GET, params lang/page/limit/search/...), basePath "/api".
* GET /api/datasets/search?lang=et&page=1&limit=5&search=pria ->
  HTTP 200: exactly 1 dataset — "PRIA kodulehe statistikamoodul"
  (subsidy/animal web stats, NOT field blocks).
* GET ...&search=pollumassiiv -> HTTP 200: 2 hits — "Pollumassiivide
  register" + "Mullastiku kaardid ja pollumassiivid (WMS)".
* GET /api/datasets/slug/pollumassiivide-register -> HTTP 200:
  PUBLIC, accrualPeriodicity DAILY, controller PRIA; citations name
  the view/download services at kls.pria.ee/geoserver/pria_avalik
  (WMS view + WFS download) — the catalogue's own urlBroken flags
  on all three kls.pria.ee links are STALE (verified live below).
* GET kls.pria.ee/geoserver/pria_avalik/wfs?SERVICE=WFS&
  REQUEST=GetCapabilities -> HTTP 200 (99 655 B): WFS 2.0.0,
  GetFeature + GetPropertyValue advertised; layers include
  pria_avalik:pria_massiivid ("PRIA Pollumassiivid", default CRS
  EPSG:3301, WGS84 bbox all-Estonia), pria_pollud, pria_plk(_alad),
  pria_maastikuelemendid, pria_mesilad, pria_ehitised.
* GET kls.pria.ee/kaart/ (shell, 54 913 B) + js/app.min.js?11
  (98 799 B): map config injects wms_url
  "https://kls.pria.ee/geoserver/avk/wms" (prefix "avk:", layers
  avk:avk_massiivid etc., tiled WMS 1.1.1 — view-only tiles) and
  per-parcel search routes (#otsi=massiivid/<11-digit-nr>).
  Interactive per-parcel lookup confirmed — enumerating it would be
  scraping human publications, not polling a feed (refused,
  AGENTS.md section 5). The WFS above is the pollable bulk instead.
* WFS GetFeature validation pulls (the demo ingestion, bounded
  Tallinn BBOX, outputFormat GeoJSON):
  - lon,lat-order bbox -> HTTP 200 but totalFeatures=0 (axis-order
    lesson, documented in one line: this server wants lon,lat);
  - lon,lat bbox over the wide fringe -> HTTP 200 but >8 MB
    (aborted by the size guard — full-vertex polygons are heavy,
    hence the tight BBOX + propertyName slimming below);
  - tight Tallinn+fringe bbox (24.55,59.35,24.95,59.52) with
    propertyName slimming -> HTTP 200, 1 463 119 B, 429 blocks:
    Rae/Harku/Saue/Viimsi/Joelahtme/Kiili vald + 1 block inside
    Tallinn; mostly Pusi rohumaa, some Pollukultuurid (the
    spray-relevant class). Feature schema: MultiPolygon geometry
    (GeoJSON lon-first — verified: first points ~[24.46, 59.26]),
    properties {xy_id (block number), pindala (ha),
    massiivi_maakasutus, kultuur/kultuur2 (crop!), maakond, vald,
    viimase_muutmise_aeg (sample 2025-09-12 — fresh,
    last-two-years claim window confirmed live)}.

So the single dim is SCORED: distance from the listing origin to
the nearest joined block polygon (coarse spray-drift buffer
bands). Reasons say "hinnang" (estimate) and name the block
(number/vald/landuse/crop) plus the buyer-side checks — never a
faked per-parcel score. Crop is RECORDED, never scored (spray
intensity per crop is uncalibrated — documented, not solved).

SIBLING OVERLAP (read first, not edited): the other P4-024 legs
stay where they live and are named here, never re-scored — the
Keskkonnaagentuur oietolmu slice (dims_p4_kaur dim_tervis_kaur,
SCORED pollen bands), the EELIS rohevorgustik habitat-proxy slice
(dims_p4_eelis dim_maaloodus_eelis, SCORED coarse cells), the
Terviseamet tick-stat + suplusvee slice (dims_p4_tervise
dim_country_health_nuisances, NULL) and the Kommunaalamet
farm-odour-kaebuste slice (dims_p4_komun dim_farm_odour_cells,
NULL). This module owns ONLY the PRIA pollumassiiv leg.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_pria_snapshot(cache_dir): polite pull, max 1 download /
  24 h per cache dir (PRIA_TTL_S; accrualPeriodicity DAILY per the
  catalogue record above). Cache hit within TTL performs NO
  request. Otherwise ONE bounded WFS GetFeature (tight Tallinn
  BBOX, propertyName-slimmed, GeoJSON) with PRIA_UA and a 60 s
  timeout; the body is stored only on HTTP 200 with JSON content
  under MAX_BYTES, else None is returned and nothing is cached
  (transport errors are never data). No retries — HTTP 429/errors
  are a stop signal. The scorer never calls this; tests cover the
  cache-hit and transport-error paths with a stubbed opener, never
  the network.
* parse_pria_snapshot / nearest_block: pure offline readers over
  the cached FeatureCollection. Geometries are validated to
  Estonian lon/lat ranges (lon 21-29, lat 57-61 — the verified
  lon-first order); malformed features are skipped, never faked; a
  missing/unparseable file parses to None (unknown), never to an
  empty blockscape. Distance is equirectangular metres (coarse by
  design — sub-metre precision would be fake); inside any outer
  ring counts as 0 m (holes ignored, documented).

Style mirrors services/scoring/dims_p4_bikes.py (#309): pure
scorer (origin, snapshot) -> (Optional[int 0..100], Estonian
reason), local helpers (no livability import — importing it here
would turn the future central hook into a cycle, same precedent as
PRs #100/#106/#115). Higher = clearer fit (livability convention:
100 is best); block-adjacent scores LOW (caution), never 0; clear
scores HIGH, never 100 (the leg is partial by construction).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #299 states 0 remaining
  params for this source — one dim, one module, the 3 re-opened
  files edited, no shared-file edits.
* Tight BBOX, not all-Estonia: the full layer is tens of MB of
  vertices; the demo scope is the Tallinn fringe (issue body:
  Harku/Lasnamäe fringe). BBOX constant is stated, not hidden.
* propertyName slimming is validated (the tight pull used it), not
  assumed — a server rename degrades to None (honest NULL).
* Outer rings only, holes ignored, equirectangular metres: coarse
  on purpose (issue body: "coarse hinnang cells"). Band edges
  (50/200 m) are first-cut judgments, MUST be recalibrated from
  spray-drift literature on reopen.
* Crop recorded, never scored; permanent grassland vs crops both
  join (drift sources differ, distance does not).

Integration (deliberately NOT done here): wiring the snapshot into
a listing pipeline plus rebalancing livability.WEIGHTS must be one
joint change across all batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling. No
shared files touched.
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Keyless PRIA download service (WFS 2.0.0, GetCapabilities
#: verified live 2026-09-16; the national catalogue's urlBroken
#: flags on it are stale).
PRIA_WFS = "https://kls.pria.ee/geoserver/pria_avalik/wfs"

#: Field-block layer ("PRIA Pollumassiivid").
PRIA_LAYER = "pria_avalik:pria_massiivid"

#: Tight Tallinn+fringe BBOX (lon,lat order — validated 2026-09-16:
#: lat,lon order returns totalFeatures=0 on this server). Covers
#: Tallinn + Harku/Viimsi/Maardu/Rae fringe (the demo scope).
PRIA_BBOX = (24.55, 59.35, 24.95, 59.52)

#: Slimmed attributes (validated via propertyName 2026-09-16;
#: geometry always rides along).
PRIA_PROPS = ("xy_id,pindala,massiivi_maakasutus,kultuur,"
              "maakond,vald,viimase_muutmise_aeg")

#: Max one download per 24 h per cache dir (accrualPeriodicity
#: DAILY per the catalogue record "Pollumassiivide register").
PRIA_TTL_S = 24 * 3600

#: Transport guard: bodies past this are refused, never cached.
MAX_BYTES = 8 * 1024 * 1024

#: Snapshot filename inside the cache dir (raw WFS GeoJSON, what
#: the server sent — parsing never mutates the cache).
CACHE_FILENAME = "pria-massiivid.json"

#: Identifying user agent for the polite pull (no scrape, 1 req/day).
PRIA_UA = ("home-finder P4-024 pria pull "
           "(max 1 req/24h, Tallinn BBOX, no scrape)")


def _wfs_url() -> str:
    params = urllib.parse.urlencode({
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "version": "2.0.0",
        "typeNames": PRIA_LAYER,
        "srsName": "urn:ogc:def:crs:EPSG::4326",
        "bbox": "%s,%s,%s,%s,EPSG:4326" % PRIA_BBOX,
        "outputFormat": "application/json",
        "propertyName": PRIA_PROPS,
    })
    return PRIA_WFS + "?" + params


def fetch_pria_snapshot(cache_dir: str,
                        ttl_s: int = PRIA_TTL_S) -> Optional[str]:
    """Polite field-block pull with a stated TTL. Path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise ONE bounded WFS GetFeature with PRIA_UA and a 60 s
    timeout; the body is stored only on HTTP 200 with JSON content
    under MAX_BYTES, else None is returned and nothing is cached
    (transport errors are never data). No retries — HTTP 429/errors
    are a stop signal. The scorer never calls this; tests cover the
    cache-hit and transport-error paths with a stubbed opener,
    never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    try:
        req = urllib.request.Request(_wfs_url(),
                                     headers={"User-Agent": PRIA_UA,
                                              "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "json" not in ctype:
                return None
            body = resp.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return None
        try:
            json.loads(body)
        except ValueError:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached snapshot (pure; fixtures match schema).
# ---------------------------------------------------------------------------

def _valid_lonlat(pt) -> bool:
    """Estonian-range lon/lat pair (the verified lon-first order)."""
    return (isinstance(pt, (list, tuple)) and len(pt) == 2
            and all(isinstance(v, (int, float))
                    and not isinstance(v, bool) for v in pt)
            and 21.0 <= pt[0] <= 29.0 and 57.0 <= pt[1] <= 61.0)


def _outer_rings(geom) -> List[list]:
    """MultiPolygon geometry -> validated outer rings (holes dropped).

    Coarse by design (issue: "coarse hinnang cells"): holes are
    rare in claim blocks and far below the 50 m band edge.
    """
    if not isinstance(geom, dict):
        return []
    if geom.get("type") != "MultiPolygon":
        return []
    polys = geom.get("coordinates")
    if not isinstance(polys, list):
        return []
    rings = []
    for poly in polys:
        if not isinstance(poly, list) or not poly:
            continue
        outer = poly[0]
        if (isinstance(outer, list) and len(outer) >= 4
                and all(_valid_lonlat(p) for p in outer)):
            rings.append([[float(p[0]), float(p[1])] for p in outer])
    return rings


def parse_pria_snapshot(path: str) -> Optional[dict]:
    """Read a cached WFS FeatureCollection. Offline, stdlib.

    Returns {"fetched_at" (file mtime), "count", "blocks":
    [{id, area_ha, landuse, crop, county, parish, modified,
    polys:[outer rings]}]} with malformed features skipped (never
    faked), or None when the file is missing/unparseable (unknown),
    never an empty blockscape.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    feats = raw.get("features")
    if not isinstance(feats, list):
        return None
    blocks = []
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties")
        if not isinstance(props, dict):
            continue
        rings = _outer_rings(feat.get("geometry"))
        if not rings:
            continue
        bid = props.get("xy_id")
        blocks.append({
            "id": str(bid) if bid is not None else "?",
            "area_ha": props.get("pindala"),
            "landuse": props.get("massiivi_maakasutus") or "?",
            "crop": props.get("kultuur") or props.get("kultuur2") or "?",
            "county": props.get("maakond") or "?",
            "parish": props.get("vald") or "?",
            "modified": props.get("viimase_muutmise_aeg") or "?",
            "polys": rings,
        })
    if not blocks:
        return None  # parsed but coverless: unknown, never clear
    try:
        fetched_at = int(os.path.getmtime(path))
    except OSError:
        return None
    total = raw.get("totalFeatures")
    return {
        "fetched_at": fetched_at,
        "count": total if isinstance(total, int) else len(blocks),
        "blocks": blocks,
    }


def _seg_m(a, b, p) -> float:
    """Equirectangular metres from point p to segment a-b (coarse)."""
    kx = 111320.0 * math.cos(math.radians((a[1] + b[1]) / 2.0))
    ky = 110540.0
    ax, ay = a[0] * kx, a[1] * ky
    bx, by = b[0] * kx, b[1] * ky
    px, py = p[0] * kx, p[1] * ky
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy)
                     / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _point_in_ring(ring, p) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        if ((a[1] > p[1]) != (b[1] > p[1])
                and p[0] < (b[0] - a[0]) * (p[1] - a[1])
                / (b[1] - a[1] + 1e-300) + a[0]):
            inside = not inside
    return inside


def _dist_to_block_m(origin: Tuple[float, float], block: dict) -> float:
    """Metres from origin to the block (0.0 when inside)."""
    best: Optional[float] = None
    for ring in block["polys"]:
        if _point_in_ring(ring, origin):
            return 0.0
        for i in range(len(ring)):
            d = _seg_m(ring[i], ring[(i + 1) % len(ring)], origin)
            if best is None or d < best:
                best = d
    return best if best is not None else float("inf")


def nearest_block(origin: Tuple[float, float],
                  snapshot: Optional[dict]) -> Optional[Tuple[float, dict]]:
    """Parsed snapshot -> (metres, block) of the nearest block, or None.

    Origin is (lat, lon) (repo convention); rings are lon-first
    (verified live order) — converted once here. None means unknown
    (no snapshot, no blocks) — never clear.
    """
    if not isinstance(snapshot, dict):
        return None
    blocks = snapshot.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return None
    lonlat = (float(origin[1]), float(origin[0]))
    best = None
    for block in blocks:
        if not isinstance(block, dict) or not block.get("polys"):
            continue
        d = _dist_to_block_m(lonlat, block)
        if best is None or d < best[0]:
            best = (d, block)
    return best


def _in_snapshot_bbox(olat: float, olon: float) -> bool:
    """Origin inside the pulled Tallinn-fringe BBOX (lat/lon args)."""
    lon0, lat0, lon1, lat1 = PRIA_BBOX
    return lon0 <= olon <= lon1 and lat0 <= olat <= lat1


# ---------------------------------------------------------------------------
# P4-024: PRIA spray-drift buffer (demo, scored coarse cells).
# ---------------------------------------------------------------------------

#: Metres to the nearest block -> caution-fit score (high = clear,
#: buyer-favourable; adjacent scores LOW, never 0 — drift hints at
#: caution, never a verdict — and clear never 100: the leg is
#: partial by construction). First-cut bands, MUST be recalibrated
#: from spray-drift literature on reopen.
BUFFER_BANDS = [(50, 30), (200, 55), (float("inf"), 80)]


def _band(value: float, bands: List[Tuple[float, int]]) -> int:
    """First score whose threshold covers the value."""
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def dim_pollupuhver_pria(origin: Optional[Tuple[float, float]],
                         snapshot: Optional[dict]) -> Score:
    """P4-024: coarse spray-drift hinnang off joined WFS blocks.

    A missing origin or a missing/coverless snapshot stays NULL
    with an Estonian EI OLE reason (unknown is never clear); a
    joined snapshot scores the distance bands above. Crop is named,
    never scored.
    """
    if origin is None:
        return None, ("Põllupõhine pritsimispuhver PRIA-st (Tallinna-äärne "
                      "jäme hinnang) puudub (EI OLE asukohta: kuulutusel "
                      "pole koordinaati, millega põllumassiivide "
                      "hetktõmmist siduda — vaata kohapealsel vaatlusel "
                      "pritsimisriba / rohelist serva / farmilõhna ning "
                      "küsi KÜ-lt ja naabritelt pritsimisgraafikut, "
                      "ära feigi)")
    if (not isinstance(origin, (list, tuple)) or len(origin) != 2
            or any(not isinstance(v, (int, float))
                   or isinstance(v, bool) for v in origin)):
        return None, ("Põllupõhine pritsimispuhver PRIA-st (Tallinna-äärne "
                      "jäme hinnang) puudub (EI OLE kehtivat asukohta — "
                      "vaata kohapealsel vaatlusel pritsimisriba / "
                      "rohelist serva / farmilõhna, ära feigi)")
    olat, olon = float(origin[0]), float(origin[1])
    if not _in_snapshot_bbox(olat, olon):
        return None, ("Põllupõhine pritsimispuhver PRIA-st (Tallinna-äärne "
                      "jäme hinnang WFS-hetktõmmise pealt) puudub (EI OLE "
                      "katvust: asukoht jääb tõmmatud Tallinna-äärse "
                      "kaadrist välja — kaugel olev lähim plokk ei ütle "
                      "kohalike põldude kohta midagi, vaata kohapealsel "
                      "vaatlusel pritsimisriba / rohelist serva / "
                      "farmilõhna, ära feigi)")
    found = nearest_block((olat, olon), snapshot)
    if found is None:
        return None, ("Põllupõhine pritsimispuhver PRIA-st (Tallinna-äärne "
                      "jäme hinnang WFS-hetktõmmise pealt) on teadmata "
                      "(EI OLE põllumassiivide hetktõmmist: allikat pole "
                      "tõmmatud või on fail loetamatu — puhverdatavat "
                      "hetktõmmist pole, vaata kohapealsel vaatlusel "
                      "pritsimisriba / rohelist serva / farmilõhna ning "
                      "küsi KÜ-lt ja naabritelt pritsimisgraafikut, "
                      "võrdle õietolmu-legi dims_p4_kaur-ist "
                      "(dim_tervis_kaur) ja elupaiga-legi dims_p4_eelis-ist "
                      "(dim_maaloodus_eelis) ning puugi/suplusvee-legi "
                      "dims_p4_tervise-st (dim_country_health_nuisances) ja "
                      "farmilõhna-legi dims_p4_komun-ist "
                      "(dim_farm_odour_cells), ära feigi)")
    dist_m, block = found
    s = _band(dist_m, BUFFER_BANDS)
    fetched = snapshot.get("fetched_at")
    day = (datetime.fromtimestamp(fetched, tz=timezone.utc).strftime(
        "%Y-%m-%d") if isinstance(fetched, int) else "?")
    if dist_m <= 50:
        return s, ("Põllupõhise pritsimispuhver-hinnangu järgi (jäme "
                   "Tallinna-äärne rakk, PRIA WFS-hetktõmmis %s): lähim "
                   "massiiv nr %s (%s, %s) on %s kaugusel — plokk külgneb, "
                   "pritsimis-ettevaatus lastele ja koertele → skoor %d "
                   "(kultuur %s on kirjas, mitte hinnatud; võrdle "
                   "dims_p4_kaur dim_tervis_kaur'i ja dims_p4_eelis "
                   "dim_maaloodus_eelis't, ära feigi)"
                   % (day, block["id"], block["landuse"], block["parish"],
                      _fmt_m(dist_m), s, block["crop"]))
    if dist_m <= 200:
        return s, ("Põllupõhise pritsimispuhver-hinnangu järgi (jäme "
                   "Tallinna-äärne rakk, PRIA WFS-hetktõmmis %s): lähim "
                   "massiiv nr %s (%s, %s) on %s kaugusel — triivihoidla "
                   "lähiala, tuulega ettevaatus → skoor %d (kultuur %s on "
                   "kirjas, mitte hinnatud; võrdle dims_p4_kaur "
                   "dim_tervis_kaur'i ja dims_p4_eelis "
                   "dim_maaloodus_eelis't, ära feigi)"
                   % (day, block["id"], block["landuse"], block["parish"],
                      _fmt_m(dist_m), s, block["crop"]))
    return s, ("Põllupõhise pritsimispuhver-hinnangu järgi (jäme "
               "Tallinna-äärne rakk, PRIA WFS-hetktõmmis %s): lähim "
               "massiiv nr %s (%s, %s) on %s kaugusel — puhver selge, "
               "otsest triivimärki pole → skoor %d (osaline jalg, mitte "
               "garantii; õietolm dims_p4_kaur'is, elupaik "
               "dims_p4_eelis'is, ära feigi)"
               % (day, block["id"], block["landuse"], block["parish"],
                  _fmt_m(dist_m), s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_PRIA_DIMS = (
    ("pollupuhver_pria", "P4-024", dim_pollupuhver_pria),
)


def score_p4_pria(origin: Optional[Tuple[float, float]],
                  snapshot: Optional[dict]
                  ) -> Dict[str, Optional[int]]:
    """The P4 PRIA dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_PRIA_DIMS). None by
    design when the origin or the snapshot is missing."""
    return {key: fn(origin, snapshot)[0] for key, _, fn in P4_PRIA_DIMS}