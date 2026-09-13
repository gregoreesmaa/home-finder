"""P4 EELIS dims (issues #287 demo + #360 coverage): Estonian Nature
Information System (Eesti looduse infosüsteem, EELIS) via the public
Keskkonnaagentuur WFS.

Params (this module only — sibling legs untouched):
* P4-015 Insurability: flood/theft tariff zones (demo, batch 1) —
  EELIS leg only (parameters4.md source (6): kaitsealad building
  restrictions → insurability; flood layer wired, Tallinn-empty, see
  below). PPA theft stats, insurer tariffs, Maa-amet surge layers and
  Päästeamet fire density stay OUT (sibling/future legs, said in
  docs/p4_eelis.md).
* P4-024 Country-health nuisances (coverage, batch 2) — EELIS leg
  only (source (5): rohevõrgustik tick-habitat proxy; EELIS serves no
  literal "rohevõrgustik" layer, so niidud/meadow polygons stand in
  as the coarse habitat proxy, documented below).
* P4-030 Satellite change delta (coverage, batch 3) — EELIS leg only
  (source (6): rohealade muutused; kaadamisalad/felling polygons are
  the honest served layer for the "disappearing grove" flag).
* P4-053 Odour roses by wind frequency (coverage, batch 5) — EELIS
  leg only (source (5): emission-source register; kr_puhasti +
  kr_jaakreostus stand in. Sector dim only — no wind-frequency
  measurement exists here, so it is never a rose, said plainly in
  every reason).

OPENNESS VERDICT (checked 2026-09-13, POSITIVE — evidence cached at
/tmp/eelis-open/, one-off PR record, never committed; 14 tiny
requests total, custom UA, no scrape):
* HEAD https://eelis.ee/ -> 404 (Kestrel); the app root serves no
  data, but https://keskkonnaagentuur.ee/eelis (HTTP 200) documents
  the "Avalik WMS/WFS teenus" and names the endpoint.
* GET .../geoserver/eelis/ows?service=WFS&version=2.0.0&
  request=GetCapabilities -> HTTP 200, 186 232 B, 104 feature types
  (cat I/II species + habitats withheld by design, per the KA page).
* resultType=hits over the Tallinn BBOX (lat 59.35-59.65, lon
  24.55-24.95): kr_kaitseala 33, niidud 44, kaadamisalad 1,
  kr_puhasti 33, kr_jaakreostus 38 — and kr_yleujutusohuga_ala 0
  (16 nationwide, none in Tallinn: the flood leg is wired but
  Tallinn-empty, so it scores nothing and says so).
* count=1 GeoJSON sample (srsName=EPSG:4326, 834 B): the server
  reprojects L-EST97 polygons to WGS84 itself — ingestion needs no
  coordinate math, stdlib json only.
So the live path below is real plumbing with real data:
fetch_eelis_snapshot pulls six layers as WGS84 GeoJSON (Tallinn
BBOX, one GET per layer), normalises to one snapshot file, and the
scorers join against it. Reopening checklist lives in
docs/p4_eelis.md.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components (zone/emitter name, distance,
sector, year where known); every NULL reason says "EI OLE" and
names the missing input. Transport errors are never cached as data
(a failed layer stores an empty table + layer_ok False, never a
faked empty map). A measured value from the snapshot (a labelled
row within the window; rows elsewhere for the clear bands) scores
— while a missing join (no snapshot, no rows at all, beyond
window, unlabelled row) stays NULL: absence of data is unknown,
never good. Distances are bird-flight, never routed. Zone rows
join by nearest labelled centroid within the window (point-in-
polygon stays a future-adapter job, same precedent as the P4-023
noise-zone dim in dims_p4_trans.py) — distance only gates the
join, the score comes from the LABEL alone.

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_eelis_snapshot(cache_dir): polite pull, max 1 pull / 365 d
  per cache dir (EELIS_TTL_S; parameters4.md P4-015 cadence:
  annual; the three coverage legs ride the same annual ticket —
  kaitsealad, niidud, fellings and emitter registries change on
  planning/permitting cadence, not weekly). Cache hit within TTL
  performs NO request. Otherwise one GET per layer (GeoJSON,
  WGS84, Tallinn BBOX, count=10000 cap) with an identifying UA and
  a 30 s timeout; no retries (HTTP 429 is a stop signal, 7.4).
* geojson_rows: pure offline converter over cached GeoJSON
  (Polygon/MultiPolygon exterior-ring centroid + Point support;
  malformed features skipped, never faked). rows_to_pois /
  snapshot_to_pois: pure offline readers over the normalised
  snapshot (schema documented below). Network lives ONLY in
  fetch_eelis_snapshot; scorers and tests never touch it.
* One snapshot, five tables, no new source for coverage: "flood" +
  "kaitse" feed P4-015, "habitat" feeds P4-024, "felling" feeds
  P4-030, "emitters" feeds P4-053 (this is why demo + coverage pair
  in ONE PR — #360 expects no new plumbing).

Snapshot schema (what the fetcher stores; fixtures match it):
  {"flood": [{"zone_id": str, "nimi": str, "lat": float, "lon": float}],
   "kaitse": [{"zone_id": str, "nimi": str, "tyyp": str|None,
               "lat": float, "lon": float}],
   "habitat": [{"zone_id": str, "nimi": str, "lat": float, "lon": float}],
   "felling": [{"zone_id": str, "nimi": str, "aasta": str|None,
                "lat": float, "lon": float}],
   "emitters": [{"em_id": str, "nimi": str, "liik": "puhasti"|"jaakreostus",
                 "lat": float, "lon": float}],
   "meta": {"fetched_at": iso, "layer_ok": {table: bool}}}
A missing/unparseable file parses to None (unknown), never to an
empty snapshot.

Style mirrors services/scoring/dims_p4_rb.py (#281/#355, the
honest-plumbing precedent): pure scorers (origin, pois) ->
(Optional[int 0..100], Estonian reason), local helpers (no
livability import — importing it here would turn the future
central hook into a cycle, same precedent as PRs
#100/#106/#115). There is NO staged Overpass fragment and no tag
mapping: OSM has no honest tag for EELIS zone ids or emitter
registers, so there is nothing for the live path to fetch (same
rationale as the group20a no-map batches).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because the #360 body states it
  "extends the demoed ingestion" with "no new plumbing expected":
  habitat/felling/emitter tables are same-snapshot extra tables
  (P4-024 source (5), P4-030 source (6), P4-053 source (5)), not
  new sources. Pairing rationale repeated in docs/p4_eelis.md.
* P4-015 scores the EELIS leg only: flood hit (<=300 m) -> 35
  tariff/illiquidity flag; kaitseala hit (<=500 m) -> 55 building-
  restriction drag with illiquidity flag; measured clear -> 85.
  The flood table is Tallinn-empty TODAY, so the clear band prints
  that caveat instead of claiming flood-clear. PPA/insurer/Maa-amet
  surge/Päästeamet legs are out of scope, not faked.
* P4-024 habitat proxy: EELIS serves no "rohevõrgustik" layer, so
  niidud polygons are the coarse tick-habitat proxy (<=500 m ->
  55 caution for kids/dogs; clear -> 80). Proxy, coarse cells
  only — never a species claim (cat I/II data is withheld anyway).
* P4-030 is a coarse change FLAG, not a delta measurement:
  kaadamisala within 500 m -> 45 with the felling year when the
  register carries one; measured clear -> 80. NDVI/satellite legs
  stay out.
* P4-053 is sector + distance, NEVER a rose and never a circle
  buffer: the score bands on distance (<=500 m -> 40, <=1500 m ->
  60) while the reason names the emitter, its liik and the octant
  sector of the listing seen from the emitter — plus the plain
  caveat that wind frequency is unmeasured (hinnang). No schedule
  data exists, so there is no calendar leg yet (stays NULL-aspect,
  said in docs/p4_eelis.md).
* All bands are first-cut judgments with no live calibration
  (MUST be recalibrated from a real Tallinn pull on reopen —
  docs/p4_eelis.md checklist). Unlabelled rows stay NULL: an
  unverified record is not a zone.

Integration (deliberately NOT done here): wiring the snapshot into
a listing pipeline plus rebalancing livability.WEIGHTS must be one
joint change across all batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling. No
shared files touched: 3 new files only.
"""

import datetime
import json
import math
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Public EELIS WFS (verified 2026-09-13: GetCapabilities HTTP 200,
#: 104 feature types; cat I/II species withheld by design).
EELIS_WFS_URL = "https://gsavalik.envir.ee/geoserver/eelis/ows"

#: Human documentation page for the public WMS/WFS service.
EELIS_INDEX_URL = "https://keskkonnaagentuur.ee/eelis"

#: WFS layer per snapshot table (verified Tallinn counts 2026-09-13
#: in parentheses; flood is wired but Tallinn-empty).
LAYER_FLOOD = "eelis:kr_yleujutusohuga_ala"   # 0 in Tallinn (16 nationwide)
LAYER_KAITSE = "eelis:kr_kaitseala"           # 33 in Tallinn
LAYER_HABITAT = "eelis:niidud"                # 44 in Tallinn
LAYER_FELLING = "eelis:kaadamisalad"          # 1 in Tallinn
LAYER_PUHASTI = "eelis:kr_puhasti"            # 33 in Tallinn
LAYER_JAAK = "eelis:kr_jaakreostus"           # 38 in Tallinn

#: (table, layer, id-field) pull plan — one GET per row.
PULL_PLAN = (
    ("flood", LAYER_FLOOD, "id"),
    ("kaitse", LAYER_KAITSE, "id"),
    ("habitat", LAYER_HABITAT, "id"),
    ("felling", LAYER_FELLING, "id"),
    ("emitters", LAYER_PUHASTI, "sys_id"),
    ("emitters", LAYER_JAAK, "sys_id"),
)

#: Tallinn BBOX (lat_min, lon_min, lat_max, lon_max) used by every
#: pull — the same window the openness counts were verified in.
TALLINN_BBOX = (59.35, 24.55, 59.65, 24.95)

#: Max one pull per 365 d per cache dir (parameters4.md P4-015 TTL:
#: annual; coverage legs ride the same annual ticket). Stated TTL.
EELIS_TTL_S = 365 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "eelis-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, 6 small GETs).
EELIS_UA = "home-finder EELIS openness-check (max 6 small GETs/365d, no scrape)"

#: Per-layer feature cap (Tallinn counts are <100/layer; the cap only
#: guards against a nationwide accident).
PULL_COUNT = 10000


def _layer_url(layer: str) -> str:
    """WFS GetFeature URL: WGS84 GeoJSON over the Tallinn BBOX."""
    lat0, lon0, lat1, lon1 = TALLINN_BBOX
    qs = urllib.parse.urlencode({
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer,
        "bbox": "%s,%s,%s,%s,urn:ogc:def:crs:EPSG::4326"
                % (lat0, lon0, lat1, lon1),
        "count": PULL_COUNT,
        "outputFormat": "application/json",
        "srsName": "urn:ogc:def:crs:EPSG::4326",
    })
    return EELIS_WFS_URL + "?" + qs


def _ring_centroid(ring) -> Optional[Tuple[float, float]]:
    """Mean of an exterior ring's [lon, lat] pairs (WGS84)."""
    try:
        pts = [(float(p[0]), float(p[1])) for p in ring
               if isinstance(p, (list, tuple)) and len(p) >= 2
               and not isinstance(p[0], bool)]
    except (TypeError, ValueError):
        return None
    pts = [(lo, la) for lo, la in pts
           if math.isfinite(lo) and math.isfinite(la)]
    if not pts:
        return None
    return (sum(la for _, la in pts) / len(pts),
            sum(lo for lo, _ in pts) / len(pts))


def geojson_rows(collection: dict, id_field: str = "id",
                 extra: Optional[dict] = None,
                 id_key: str = "zone_id") -> List[dict]:
    """Pure converter: WFS GeoJSON FeatureCollection -> snapshot rows.

    Polygon/MultiPolygon features contribute their exterior-ring
    centroid; Point features their coordinates. Features without a
    usable geometry or name are skipped, never faked. ``extra`` tags
    constant per-layer fields (e.g. emitter liik); ``id_key`` names
    the snapshot id field ("em_id" for the emitter table).
    """
    if not isinstance(collection, dict):
        return []
    feats = collection.get("features")
    if not isinstance(feats, list):
        return []
    rows = []
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties")
        geom = feat.get("geometry")
        if not isinstance(props, dict) or not isinstance(geom, dict):
            continue
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        ll = None
        if gtype == "Point" and isinstance(coords, (list, tuple)) \
                and len(coords) >= 2:
            try:
                lon, lat = float(coords[0]), float(coords[1])
            except (TypeError, ValueError):
                continue
            if isinstance(coords[0], bool) or not (
                    math.isfinite(lat) and math.isfinite(lon)):
                continue
            ll = (lat, lon)
        elif gtype == "Polygon" and isinstance(coords, list) and coords:
            ll = _ring_centroid(coords[0])
        elif gtype == "MultiPolygon" and isinstance(coords, list) \
                and coords and isinstance(coords[0], list) and coords[0]:
            ll = _ring_centroid(coords[0][0])
        if ll is None:
            continue
        ident = props.get(id_field)
        if ident is None:
            ident = props.get("sys_id", "tundmatu")
        nimi = props.get("nimi") or props.get("nimetus") or "tundmatu"
        row = {id_key: str(ident), "nimi": str(nimi),
               "lat": ll[0], "lon": ll[1]}
        for key in ("tyyp", "aasta", "kr_kood"):
            if props.get(key) is not None:
                row[key] = str(props.get(key))
        if extra:
            row.update(extra)
        rows.append(row)
    return rows


def fetch_eelis_snapshot(cache_dir: str,
                         ttl_s: int = EELIS_TTL_S,
                         ) -> Optional[str]:
    """Polite EELIS snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made.
    Otherwise one GET per PULL_PLAN row (WGS84 GeoJSON, Tallinn BBOX)
    with EELIS_UA and a 30 s timeout; a failed layer stores an empty
    table + layer_ok False (transport errors are never data). No
    retries — HTTP 429/errors are a stop signal. When NO layer
    succeeds, nothing is cached and None is returned. Scorers never
    call this; tests cover the cache-hit and stubbed-pull paths,
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
    tables: Dict[str, list] = {"flood": [], "kaitse": [], "habitat": [],
                               "felling": [], "emitters": []}
    layer_ok: Dict[str, bool] = {}
    any_ok = False
    for table, layer, id_field in PULL_PLAN:
        rows: List[dict] = []
        ok = False
        try:
            req = urllib.request.Request(_layer_url(layer),
                                         headers={"User-Agent": EELIS_UA,
                                                  "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = getattr(resp, "status", 200)
                ctype = resp.headers.get("Content-Type", "")
                if status != 200 or "json" not in ctype:
                    raise ValueError("bad transport: %s/%s" % (status, ctype))
                body = resp.read()
            try:
                collection = json.loads(body)
            except ValueError:
                raise ValueError("non-JSON body")
            extra = None
            id_key = "zone_id"
            if table == "emitters":
                extra = {"liik": ("puhasti" if layer == LAYER_PUHASTI
                                  else "jaakreostus")}
                id_key = "em_id"
            rows = geojson_rows(collection, id_field, extra, id_key)
            ok = True
            any_ok = True
        except Exception:
            ok = False
        if table == "emitters":
            tables["emitters"].extend(rows)
            layer_ok[layer] = ok
        else:
            tables[table] = rows
            layer_ok[layer] = ok
    if not any_ok:
        return None
    snapshot = dict(tables)
    snapshot["meta"] = {
        "fetched_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
        "layer_ok": layer_ok,
    }
    try:
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, ensure_ascii=False)
    except OSError:
        return None
    return dest


# ---------------------------------------------------------------------------
# Offline readers over the cached snapshot (pure; fixtures match schema).
# ---------------------------------------------------------------------------

def parse_eelis_snapshot(path: str) -> Optional[dict]:
    """Read a cached EELIS snapshot file. Offline, stdlib.

    Returns the five tables (missing tables read as []) plus meta, or
    None when the file is missing/unparseable (unknown, never an empty
    snapshot — scorers must not read "no file" as "no zones").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    out: Dict[str, object] = {}
    for table in ("flood", "kaitse", "habitat", "felling", "emitters"):
        rows = raw.get(table)
        out[table] = ([r for r in rows if isinstance(r, dict)]
                      if isinstance(rows, list) else [])
    meta = raw.get("meta")
    out["meta"] = meta if isinstance(meta, dict) else {}
    return out


def _finite_latlon(row: dict) -> Optional[Tuple[float, float]]:
    """(lat, lon) when both are finite non-bool numbers, else None."""
    try:
        lat = row["lat"]
        lon = row["lon"]
        if isinstance(lat, bool) or isinstance(lon, bool):
            return None
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError, KeyError):
        return None
    if math.isfinite(lat) and math.isfinite(lon):
        return lat, lon
    return None


def _rows_to_pois(rows: List[dict], kind: str,
                  id_key: str) -> List[dict]:
    """Snapshot rows -> scorer POIs. Rows without coords stay out (never
    faked); label fields pass through for the scorers to read."""
    pois = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        poi = {"kind": kind, "lat": lat, "lon": lon,
               id_key: str(row.get(id_key) or "tundmatu"),
               "nimi": str(row.get("nimi") or "tundmatu")}
        for key in ("tyyp", "aasta", "kr_kood", "liik"):
            if row.get(key) is not None:
                poi[key] = str(row.get(key))
        pois.append(poi)
    return pois


def snapshot_to_pois(snapshot: Optional[dict]) -> List[dict]:
    """Parsed snapshot (or None) -> scorer POIs for all four dims. Pure."""
    if not isinstance(snapshot, dict):
        return []
    pois: List[dict] = []
    for table, kind, id_key in (
            ("flood", "eelis_flood_p4", "zone_id"),
            ("kaitse", "eelis_kaitse_p4", "zone_id"),
            ("habitat", "eelis_habitat_p4", "zone_id"),
            ("felling", "eelis_felling_p4", "zone_id"),
            ("emitters", "eelis_emitter_p4", "em_id")):
        rows = snapshot.get(table)
        if isinstance(rows, list):
            pois.extend(_rows_to_pois(rows, kind, id_key))
    return pois


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; local to avoid import cycles).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _near(origin: Tuple[float, float], pois: List[dict], kind: str,
          window_m: float) -> List[Tuple[float, dict]]:
    """[(distance_m, poi)] of well-formed POIs of kind within window. Pure."""
    hits = []
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        try:
            lat = p["lat"]
            lon = p["lon"]
            if isinstance(lat, bool) or isinstance(lon, bool):
                continue
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError, KeyError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if d <= window_m:
            hits.append((d, p))
    hits.sort(key=lambda h: h[0])
    return hits


def _has_kind(pois: List[dict], kind: str) -> bool:
    """True when the snapshot holds at least one well-formed POI of kind."""
    return bool(_near((0.0, 0.0), pois, kind, 20_000_000.0))


#: Octant sectors (listing seen from the zone/emitter), for the
#: sector-shaped P4-053 reason. Bearing 0 deg = listing due north.
SECTORS = ("põhja", "kirde", "ida", "kagu",
           "lõuna", "edela", "lääne", "loode")


def _sector(origin: Tuple[float, float], lat: float, lon: float) -> str:
    """Octant sector of the listing as seen from the source point."""
    dy = (origin[0] - lat) * 111320.0
    dx = (origin[1] - lon) * 111320.0 * math.cos(math.radians(lat))
    bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
    return SECTORS[int((bearing + 22.5) // 45) % 8]


# ---------------------------------------------------------------------------
# Windows + bands (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: P4-015 flood-tariff window (flood tariff zones bite at the parcel).
FLOOD_WINDOW_M = 300.0
#: P4-015 building-restriction window (kaitseala piirangud carry to
#: the neighbouring parcels).
KAITSE_WINDOW_M = 500.0
#: P4-015 measured-clear score (high = insurable without a flag).
INS_CLEAR_SCORE = 85
#: P4-015 flood-hit score (tariff + illiquidity flag).
FLOOD_SCORE = 35
#: P4-015 kaitseala-hit score (restriction drag + illiquidity flag).
KAITSE_SCORE = 55

#: P4-024 coarse habitat-cell window (tick-habitat proxy, cells only).
HABITAT_WINDOW_M = 500.0
#: P4-024 near-habitat caution score (high = calm for kids/dogs).
HABITAT_NEAR_SCORE = 55
#: P4-024 measured-clear score.
HABITAT_CLEAR_SCORE = 80

#: P4-030 change-flag window (grove loss / new neighbour visibility).
FELLING_WINDOW_M = 500.0
#: P4-030 recent-green-loss flag score (high = unchanged).
FELLING_SCORE = 45
#: P4-030 measured-clear score.
FELLING_CLEAR_SCORE = 80

#: P4-053 emitter sector window (odour carries past the doorstep).
EMITTER_WINDOW_M = 1500.0
#: P4-053 doorstep distance (same-street emitter).
EMITTER_NEAR_M = 500.0
#: P4-053 near-emitter score / in-sector score (high = calm air).
EMITTER_NEAR_SCORE = 40
EMITTER_FAR_SCORE = 60
#: P4-053 measured-clear score.
EMITTER_CLEAR_SCORE = 80


# ---------------------------------------------------------------------------
# P4-015: insurability, EELIS leg (demo).
# ---------------------------------------------------------------------------

def dim_kindlustus_eelis(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-015: EELIS flood/restriction zone join (high = insurable).

    Flood-tariff hit (<=300 m) scores 35 with the tariff/illiquidity
    flag; kaitseala building-restriction hit (<=500 m) scores 55 with
    the illiquidity flag; measured clear (labelled rows elsewhere,
    none near) scores 85. The flood layer is Tallinn-empty today, so
    the clear reason prints that caveat instead of claiming
    flood-clear. Only this leg — PPA/insurer/surge/Päästeamet legs
    stay out.
    """
    if not origin or pois is None:
        return None, ("Kindlustatavuse info puudub (EI OLE EELIS-"
                      "hetktõmmist: masinloetavat tsoonikihti pole, "
                      "allikas on Keskkonnaagentuuri WFS)")
    flood_hits = _near(origin, pois, "eelis_flood_p4", FLOOD_WINDOW_M)
    if flood_hits:
        d0, z0 = flood_hits[0]
        return FLOOD_SCORE, (
            "Kindlustatavuse hinnang (EELIS tsooniliidestus): üleujutus-"
            "ohuala '%s' %s — tariifitsoon + illikviidsuse lipp "
            "(ehituspiirang/edasimüük) → skoor %d"
            % (z0.get("nimi"), _fmt_m(d0), FLOOD_SCORE))
    kaitse_hits = _near(origin, pois, "eelis_kaitse_p4", KAITSE_WINDOW_M)
    if kaitse_hits:
        d0, z0 = kaitse_hits[0]
        return KAITSE_SCORE, (
            "Kindlustatavuse hinnang (EELIS tsooniliidestus): kaitseala "
            "'%s' %s — ehituspiirangud (kindlustatavus/edasimüük) + "
            "illikviidsuse lipp → skoor %d"
            % (z0.get("nimi"), _fmt_m(d0), KAITSE_SCORE))
    if not _has_kind(pois, "eelis_kaitse_p4"):
        return None, ("Kindlustatavuse info puudub (EI OLE EELIS "
                      "tsoonikirjeid hetktõmmises: tühi tõmmis ei ole "
                      "kindlustatav otsus)")
    if _has_kind(pois, "eelis_flood_p4"):
        return INS_CLEAR_SCORE, (
            "Kindlustatavuse hinnang (EELIS tsooniliidestus): lähikonnas "
            "üleujutusohuala ega kaitseala pole (tõmmises on tsoone "
            "mujal) → skoor %d" % INS_CLEAR_SCORE)
    return INS_CLEAR_SCORE, (
        "Kindlustatavuse hinnang (EELIS tsooniliidestus): lähikonnas "
        "kaitseala pole (tõmmises on kaitsealasid mujal); "
        "üleujutuskihis Tallinna kirjeid pole (EI OLE üleujutus-"
        "liidestust Tallinnas) → skoor %d" % INS_CLEAR_SCORE)


# ---------------------------------------------------------------------------
# P4-024: country-health nuisances, EELIS habitat leg (coverage).
# ---------------------------------------------------------------------------

def dim_maaloodus_eelis(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-024: coarse tick-habitat cell (high = calm for kids/dogs).

    Only the EELIS habitat leg: the nearest niidud-proxy cell within
    500 m scores 55 (puugi-elupaiga lähedus, caution); measured clear
    (cells elsewhere, none near) scores 80. No snapshot link is
    unknown (NULL), never calm. Terviseamet/PRIA/complaint legs stay
    out.
    """
    if not origin or pois is None:
        return None, ("Maa-tervise info puudub (EI OLE EELIS elupaiga-"
                      "hetktõmmist: masinloetavat rohevõrgustikku pole, "
                      "allikas on Keskkonnaagentuuri WFS)")
    if not _has_kind(pois, "eelis_habitat_p4"):
        return None, ("Maa-tervise info puudub (EI OLE EELIS elupaiga-"
                      "kirjeid hetktõmmises: tühi tõmmis ei ole rahulik "
                      "otsus)")
    hits = _near(origin, pois, "eelis_habitat_p4", HABITAT_WINDOW_M)
    if not hits:
        return HABITAT_CLEAR_SCORE, (
            "Maa-tervise hinnang (jäme elupaiga-ruudustik): 500 m "
            "raadiuses puugi-elupaiga rakku pole (tõmmises on rakke "
            "mujal) → skoor %d" % HABITAT_CLEAR_SCORE)
    d0, h0 = hits[0]
    return HABITAT_NEAR_SCORE, (
        "Maa-tervise hinnang (jäme elupaiga-ruudustik, mitte liigiväide): "
        "niidu-elupaik '%s' %s — puugi/elupaiga lähedus, lapsed/koerad "
        "ettevaatust → skoor %d"
        % (h0.get("nimi"), _fmt_m(d0), HABITAT_NEAR_SCORE))


# ---------------------------------------------------------------------------
# P4-030: satellite change delta, EELIS felling leg (coverage).
# ---------------------------------------------------------------------------

def dim_rohemuutus_eelis(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-030: coarse green-loss flag (high = unchanged).

    Only the EELIS felling leg: a kaadamisala within 500 m scores 45
    (hiljutine raie — disappearing grove), with the register year
    when known; measured clear (fellings elsewhere, none near)
    scores 80. No felling link is unknown (NULL), never unchanged.
    NDVI/satellite/raieloa legs stay out.
    """
    if not origin or pois is None:
        return None, ("Rohemuutuse info puudub (EI OLE EELIS raie-"
                      "hetktõmmist: masinloetavat muutusekihti pole, "
                      "allikas on Keskkonnaagentuuri WFS)")
    if not _has_kind(pois, "eelis_felling_p4"):
        return None, ("Rohemuutuse info puudub (EI OLE EELIS raie-"
                      "kirjeid hetktõmmises: tühi tõmmis ei ole "
                      "muutumatu otsus)")
    hits = _near(origin, pois, "eelis_felling_p4", FELLING_WINDOW_M)
    if not hits:
        return FELLING_CLEAR_SCORE, (
            "Rohemuutuse hinnang (jäme muutuse-lipp): 500 m raadiuses "
            "registreeritud raiet pole (tõmmises on raieid mujal) → "
            "skoor %d" % FELLING_CLEAR_SCORE)
    d0, f0 = hits[0]
    aasta = f0.get("aasta")
    aasta_txt = ("aastal %s" % aasta) if aasta else \
        "teadmata aastaga (EI OLE registriaastat)"
    return FELLING_SCORE, (
        "Rohemuutuse hinnang (jäme muutuse-lipp, mitte satelliidimõõt): "
        "raieala '%s' %s, %s — kaduv salu/uus naaber võimalik → skoor %d"
        % (f0.get("nimi"), _fmt_m(d0), aasta_txt, FELLING_SCORE))


# ---------------------------------------------------------------------------
# P4-053: odour sector, EELIS emitter leg (coverage).
# ---------------------------------------------------------------------------

def dim_lohnasektor_eelis(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-053: emitter sector + distance (high = calm air).

    Only the EELIS emitter leg, sector-shaped and NEVER a circle
    buffer or a rose: the nearest puhasti/jaakreostus within 1500 m
    scores 40 at the doorstep (<=500 m) or 60 in-sector, and the
    reason names the emitter, its liik, the octant sector of the
    listing seen from the emitter, and the distance — plus the plain
    caveat that wind frequency is unmeasured. Measured clear
    (emitters elsewhere, none near) scores 80. No emitter link is
    unknown (NULL), never clean air. No schedule data exists, so
    there is no calendar leg yet.
    """
    if not origin or pois is None:
        return None, ("Lõhnaallika info puudub (EI OLE EELIS heite-"
                      "hetktõmmist: masinloetavat heiteregistrit pole, "
                      "allikas on Keskkonnaagentuuri WFS)")
    if not _has_kind(pois, "eelis_emitter_p4"):
        return None, ("Lõhnaallika info puudub (EI OLE EELIS heite-"
                      "kirjeid hetktõmmises: tühi tõmmis ei ole puhas "
                      "otsus)")
    hits = _near(origin, pois, "eelis_emitter_p4", EMITTER_WINDOW_M)
    if not hits:
        return EMITTER_CLEAR_SCORE, (
            "Lõhnasektori hinnang (allikas + ilmakaar, mitte tuuleroos): "
            "1,5 km raadiuses heiteallikat pole (tõmmises on allikaid "
            "mujal) → skoor %d" % EMITTER_CLEAR_SCORE)
    d0, e0 = hits[0]
    sector = _sector(origin, float(e0["lat"]), float(e0["lon"]))
    if d0 <= EMITTER_NEAR_M:
        return EMITTER_NEAR_SCORE, (
            "Lõhnasektori hinnang (allikas + ilmakaar, mitte tuuleroos): "
            "%s '%s' otse lähedal (%s, kuulutuse suund allika suhtes %s) "
            "— tuule sagedust mõõtmata (hinnang) → skoor %d"
            % (e0.get("liik"), e0.get("nimi"), _fmt_m(d0), sector,
               EMITTER_NEAR_SCORE))
    return EMITTER_FAR_SCORE, (
        "Lõhnasektori hinnang (allikas + ilmakaar, mitte tuuleroos): "
        "lähim %s '%s' %s (kuulutuse suund allika suhtes %s) — tuule "
        "sagedust mõõtmata (hinnang) → skoor %d"
        % (e0.get("liik"), e0.get("nimi"), _fmt_m(d0), sector,
           EMITTER_FAR_SCORE))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_EELIS_DIMS = (
    ("kindlustus_eelis", "P4-015", dim_kindlustus_eelis),
    ("maaloodus_eelis", "P4-024", dim_maaloodus_eelis),
    ("rohemuutus_eelis", "P4-030", dim_rohemuutus_eelis),
    ("lohnasektor_eelis", "P4-053", dim_lohnasektor_eelis),
)


def score_p4_eelis(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 EELIS dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_EELIS_DIMS}
