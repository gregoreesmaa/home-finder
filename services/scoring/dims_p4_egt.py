"""P4 EGT dims (issues #288 demo + #361 coverage): EGT engineering geology.

Params (this module only — sibling legs untouched):
* P4-016 Engineering geology, EGT-map-class leg (demo, batch 2 —
  parameters4.md P4-016 source (1): EGT insenergeoloogia kaardid,
  turvas/karst/alvar Tallinn)
* P4-054 Quarry blast + truck season, EGT-deposit leg (coverage,
  batch 5 — parameters4.md P4-054 source (5): EGT geoloogia kaardid,
  quarry proximity, Maardu/Harku paekivi fringe)

OPENNESS VERDICT (checked 2026-09-13, dated mixed verdict per #288
acceptance — a dated negative on the bulk endpoint keeps the verdict):
EGT publishes as human pages + viewer + downloads, but NO open
machine-readable bulk endpoint for per-parcel engineering-geology
classes. Polite evidence, 5 tiny requests total (custom UA, ≥3 s
pacing, headers + two front pages + one 404 sub-URL, no scrape):
* HEAD https://www.egt.ee/ -> HTTP 200 (Drupal, Cloudflare)
* GET https://www.egt.ee/ (145 109 B front page): "Ruumiandmed ja
  kaardid", "Teenused", "allalaadimiseks", geoportaal links; map
  rendering points at teenus.maaamet.ee OWS WMS — no EGT bulk API
* HEAD https://gis.egt.ee/geoportaal/ -> HTTP 200
* GET https://gis.egt.ee/geoportaal/ -> HTTP 200, 21 195 B,
  "<title>Avamus - EGT Geoportaal</title>" (open viewer; shell page
  holds no WFS/WMS/ArcGIS/download tokens)
* GET https://www.egt.ee/et/ruumiandmed-ja-kaardid -> HTTP 404
  (offering known via #248 evidence: ruumiandmed "teenuste ja
  allalaaditavate failidena" under a data licence with a
  scale-class caveat — downloads, not a per-parcel API)
Raw headers/pages cached at /tmp/egt-open/ (one-off PR record, never
committed). So the live path below is honest plumbing with NO live
data: fetch_egt_snapshot performs NO request while EGT_BULK_URL is
None, scorers stay NULL with an Estonian EI OLE reason, and the
scored shapes are proven on fixtures only.
Reopening checklist lives in docs/p4_egt.md.

SCOPE GUARDS (do NOT touch):
* dims_p4_maa_subsurface.py owns the WFS per-parcel class-join legs
  of P4-016 (karst/turvas/alvar/kaitseala containment) and the
  P4-054 deposit-polygon buffer leg (#248/#332, merged PR #394) —
  untouched. This module scores ONLY the EGT-map legs with
  `_egt`-suffixed dim keys (same multi-leg precedent as P4-037 in
  park vs cityplans, and P4-006 in kataster vs tpr vs rb).
* Overturn issue #238 owns the EGT radon-risk map (parameters3 G7);
  "Looduslik radoonirisk" is an EGT activity but radon is NOT scored
  here. dims_group07*.py and every shared/group file untouched:
  3 new files only.

HONESTY (AGENTS.md section 7.2): every scored dim says "hinnang"
(estimate) and prints its components; every NULL reason says
"EI OLE" and names the missing input. Transport errors are never
cached as data (fetch_egt_snapshot stores a body only on HTTP 200
with JSON content, else returns None). A measured value from the
snapshot (a class/quarry row in the window) scores — while a missing
join (no snapshot, no row in the window, unknown klass label) stays
NULL: absence of data is unknown, never good. Distances are
bird-flight, never routed; every scored reason says "jäme"
(coarse — EGT licence scale caveat).

Ingestion (demoed end-to-end, stdlib only, offline-first):
* fetch_egt_snapshot(cache_dir): polite pull, max 1 download / 365 d
  per cache dir (EGT_TTL_S; parameters4.md P4-016 cadence: annual
  bulk; the P4-054 EGT leg rides the same annual ticket — deposit
  data changes on survey/register milestones, not weekly). Cache
  hit within TTL performs NO request. While no open bulk endpoint
  exists (EGT_BULK_URL is None) it performs no request at all and
  returns the fresh-cache path or None. Single GET with an
  identifying UA once a bulk URL is known, no retries (HTTP 429 is
  a stop signal, 7.4).
* parse_egt_snapshot / classes_to_pois / quarries_to_pois /
  snapshot_to_pois: pure offline readers over the cached JSON
  snapshot (schema documented below). Network lives ONLY in
  fetch_egt_snapshot; scorers and tests never touch it.
* One snapshot, two tables, no new source for coverage: "classes"
  feeds P4-016, "quarries" feeds P4-054 (this is why demo +
  coverage pair in ONE PR — #361 expects no new plumbing).

Snapshot schema (what a future adapter would store; fixtures match it):
  {"classes": [{"class_id": str, "name": str,
                "klass": "turvas"|"karst"|"alvar"|"kandev",
                "lat": float, "lon": float}],
   "quarries": [{"quarry_id": str, "name": str,
                 "lat": float, "lon": float}]}
Malformed rows are skipped, never faked; a missing/unparseable file
parses to None (unknown), never to an empty snapshot. Unknown klass
labels are kept by the reader but fail closed to NULL in the scorer:
an unverified label is not a soil class.

Style mirrors services/scoring/dims_p4_rb.py (#281/#355, the honest-
plumbing precedent): pure scorers (origin, pois) -> (Optional[int
0..100], Estonian reason), local helpers (no livability import —
importing it here would turn the future central hook into a cycle,
same precedent as PRs #100/#106/#115). There is NO staged Overpass
fragment and no tag mapping: OSM has no honest tag for EGT map-sheet
classes or quarry blast seasons, so there is nothing for the live
path to fetch (same rationale as the group20a no-map batches).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because the #361 body states it
  "extends the demoed ingestion" with "no new plumbing expected":
  the quarries table is a same-snapshot second table (P4-054
  source (5): "EGT geoloogia kaardid (quarry proximity)"), not a
  second source.
* Bands mirror dims_p4_maa_subsurface.dim_engineering_geology /
  dim_quarry_buffer (karst 30, turvas 35, alvar 55, mapped-clean 70
  capped; quarry <=500 m -> 25, <=2 km -> 45) so the two legs of
  each param read consistently; they are first-cut and MUST be
  recalibrated from real EGT classes on reopen (docs/p4_egt.md
  checklist). A clean EGT class scores 70, never 100 — layer
  absence at map scale is not proven good soil.
* CLASS_WINDOW_M 500 m is the coarse-map judgment: EGT layers are
  small-scale compilations (licence scale caveat), so the EGT leg
  is a neighbourhood-scale hinnang, while the exact per-parcel
  containment join stays the WFS leg in subsurface — no
  double-scoring (different keys, different grains).
* P4-054 beyond-2 km stays NULL, not "quiet": an EGT deposit point
  is a mineral occurrence, not an active mine, and the blast
  timetable leg (Keskkonnamet load schedules) is not an open feed
  (dated negative carried from #248) — absence of a point proves
  nothing about Tuesday 7am.
* Sibling-leg split (no double-scoring): P4-016 WFS containment
  legs stay in dims_p4_maa_subsurface.dim_engineering_geology;
  P4-054 polygon-buffer legs stay in
  dims_p4_maa_subsurface.dim_quarry_buffer; radon stays with #238.
  This module scores ONLY the EGT-map legs with _egt-suffixed keys.

Integration (deliberately NOT done here): wiring the snapshot into a
listing pipeline plus rebalancing livability.WEIGHTS must be one joint
change across all batches — existing tests pin set(WEIGHTS) exactly,
so per-batch WEIGHTS edits would break every sibling. No shared files
touched: 3 new files only.
"""

import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Human status pages (verified 2026-09-13: both HTTP 200, see module
#: docstring). The viewer is open; neither serves a per-parcel bulk feed.
EGT_INDEX_URL = "https://www.egt.ee/"
EGT_GEOIPORTAAL_URL = "https://gis.egt.ee/geoportaal/"

#: Open bulk endpoint: NONE found 2026-09-13 (dated mixed verdict, see
#: module docstring). Stays None until the reopening checklist in
#: docs/p4_egt.md names a verified bulk URL; while None, fetch performs
#: no requests.
EGT_BULK_URL: Optional[str] = None

#: Max one download per 365 d per cache dir (parameters4.md P4-016:
#: annual bulk; the P4-054 EGT leg rides the same annual ticket).
#: Stated TTL.
EGT_TTL_S = 365 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "egt-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
EGT_UA = "home-finder EGT openness-check (max 1 req/365d, no scrape)"

#: EGT engineering-geology map classes counted by the P4-016 EGT leg
#: (parameters4.md P4-016: turvas/karst/alvar, kandevoime).
KLASS_TURVAS = "turvas"
KLASS_KARST = "karst"
KLASS_ALVAR = "alvar"
KLASS_KANDEV = "kandev"


def fetch_egt_snapshot(cache_dir: str,
                       ttl_s: int = EGT_TTL_S,
                       bulk_url: Optional[str] = EGT_BULK_URL,
                       ) -> Optional[str]:
    """Polite EGT snapshot pull with a stated TTL. Returns path or None.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated verdict stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with EGT_UA and a 30 s
    timeout; the body is stored only on HTTP 200 with JSON content, else
    None is returned and nothing is cached (transport errors are never
    data). No retries — HTTP 429/errors are a stop signal. Scorers never
    call this; tests cover the cache-hit and no-endpoint paths with a
    stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    if bulk_url is None:
        return None
    try:
        req = urllib.request.Request(bulk_url, headers={"User-Agent": EGT_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "json" not in ctype:
                return None
            body = resp.read()
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

def parse_egt_snapshot(path: str) -> Optional[dict]:
    """Read a cached EGT snapshot file. Offline, stdlib.

    Returns {"classes": [...], "quarries": [...]} with malformed rows
    skipped, or None when the file is missing/unparseable (unknown,
    never an empty snapshot — scorers must not read "no file" as
    "good soil").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    classes = raw.get("classes") if isinstance(raw.get("classes"), list) else []
    quarries = (raw.get("quarries")
                if isinstance(raw.get("quarries"), list) else [])
    return {"classes": [r for r in classes if isinstance(r, dict)],
            "quarries": [r for r in quarries if isinstance(r, dict)]}


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


def classes_to_pois(classes: List[dict]) -> List[dict]:
    """Class rows -> scorer POIs. Rows without coords stay out (never
    faked); klass strings are normalised to lowercase, unknown labels
    kept for the scorer to fail closed on (never mapped to a class)."""
    pois = []
    for row in classes:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        klass = row.get("klass")
        pois.append({
            "kind": "egt_class_p4",
            "lat": lat, "lon": lon,
            "class_id": str(row.get("class_id") or "tundmatu"),
            "name": str(row.get("name") or "tundmatu"),
            "klass": (str(klass).strip().lower()
                      if klass is not None else None),
        })
    return pois


def quarries_to_pois(quarries: List[dict]) -> List[dict]:
    """Quarry rows -> scorer POIs. Rows without coords stay out."""
    pois = []
    for row in quarries:
        if not isinstance(row, dict):
            continue
        ll = _finite_latlon(row)
        if ll is None:
            continue
        lat, lon = ll
        pois.append({
            "kind": "egt_quarry_p4",
            "lat": lat, "lon": lon,
            "quarry_id": str(row.get("quarry_id") or "tundmatu"),
            "name": str(row.get("name") or "tundmatu"),
        })
    return pois


def snapshot_to_pois(snapshot: Optional[dict]) -> List[dict]:
    """Parsed snapshot (or None) -> scorer POIs for both dims. Pure."""
    if not isinstance(snapshot, dict):
        return []
    classes = snapshot.get("classes")
    quarries = snapshot.get("quarries")
    pois: List[dict] = []
    if isinstance(classes, list):
        pois.extend(classes_to_pois(classes))
    if isinstance(quarries, list):
        pois.extend(quarries_to_pois(quarries))
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


# ---------------------------------------------------------------------------
# Windows + bands (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: P4-016 EGT-map-class window: coarse map scale, neighbourhood grain
#: (the exact per-parcel containment join stays the WFS leg).
CLASS_WINDOW_M = 500.0
#: P4-054 EGT-quarry doorstep: blast + truck season at the doorstep.
QUARRY_NEAR_M = 500.0
#: P4-054 EGT-quarry coarse band (mirrors the subsurface <= 2 km leg).
QUARRY_FAR_M = 2000.0

#: Map class -> score (high = cheap foundations). First-cut bands
#: mirroring dims_p4_maa_subsurface.dim_engineering_geology; MUST be
#: recalibrated from real EGT classes on reopen.
KLASS_SCORES = {
    KLASS_KARST: 30,
    KLASS_TURVAS: 35,
    KLASS_ALVAR: 55,
    KLASS_KANDEV: 70,
}
#: Nearest EGT quarry distance -> Tuesday-7am score (high = calm).
QUARRY_NEAR_SCORE = 25
QUARRY_FAR_SCORE = 45

#: Blast-timetable leg is not an open feed (dated negative carried
#: from #248): named in every P4-054 reason, never faked.
NO_TIMETABLE = ("lõhkamiste ajagraafiku jalga EI OLE "
                "(Keskkonnaameti load ei ole avaandmed)")


# ---------------------------------------------------------------------------
# P4-016: engineering geology, EGT-map-class leg (demo).
# ---------------------------------------------------------------------------

def dim_pinnas_klass_egt(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-016: nearest EGT engineering-geology map class within 500 m.

    Coarse neighbourhood-scale hinnang (high = cheap foundations):
    karst -> 30, turvas -> 35, alvar -> 55, mapped kandev -> 70
    (capped — map scale never proves good soil). Beyond-window is
    unknown, never good; an unknown klass label stays NULL.
    """
    if not origin or pois is None:
        return None, ("Pinnaseklassi info puudub (EI OLE EGT-hetktõmmist: "
                      "masinloetavat insenergeoloogia-kihti pole, allikad on "
                      "geoportaali Avamus ja allalaaditavad failid)")
    if not _has_kind(pois, "egt_class_p4"):
        return None, ("Pinnaseklassi info puudub (EI OLE klassi-"
                      "EGT-hetktõmmist hetkel: tühi tõmmis ei ole hea "
                      "pinnase otsus)")
    hits = _near(origin, pois, "egt_class_p4", CLASS_WINDOW_M)
    if not hits:
        return None, ("Pinnaseklassi info puudub (EI OLE EGT-klassi 500 m "
                      "aknas — akna taga on teadmata, mitte hea pinnas; "
                      "täpne krundiliidestus on Maa-ameti WFS-legis)")
    d0, c0 = hits[0]
    klass = c0.get("klass")
    score = KLASS_SCORES.get(klass) if isinstance(klass, str) else None
    if score is None:
        return None, ("Pinnaseklassi info puudub (EI OLE kinnitatud klassi: "
                      "kaart %s %s on märgitud '%s' — kontrollimata silt "
                      "ei ole pinnaseklass)" % (c0.get("class_id"),
                                                _fmt_m(d0), klass))
    if klass == KLASS_KARST:
        why = "karst (varieeruv kandevõime, uuring kohustuslik)"
    elif klass == KLASS_TURVAS:
        why = "turvas (vajumine, vaiad tõenäolised)"
    elif klass == KLASS_ALVAR:
        why = "alvar/õhuke pinnas paekivil (kaljutöö võimalik)"
    else:
        why = "kaardistatud kandev (jäme hinnang, mõõtkavaklass!)"
    return score, ("EGT insenergeoloogia klass (hinnang, jäme, 500 m aken): "
                   "kaart %s '%s' %s, klass '%s' (%s) → skoor %d"
                   % (c0.get("class_id"), c0.get("name"), _fmt_m(d0),
                      klass, why, score))


# ---------------------------------------------------------------------------
# P4-054: quarry blast + truck season, EGT-deposit leg (coverage).
# ---------------------------------------------------------------------------

def dim_karjaar_egt(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-054: nearest EGT quarry/deposit within 2 km (high = calm).

    Only the EGT-deposit leg: <=500 m scores 25 (blast + truck season
    at the doorstep), 500 m–2 km scores 45 (coarse), beyond stays NULL
    (unknown, never quiet). Sibling polygon-buffer legs untouched.
    """
    if not origin or pois is None:
        return None, ("Karjääriinfo puudub (EI OLE EGT-hetktõmmist: "
                      "masinloetavat maardlakihti pole, allikad on "
                      "maardlate kaardirakendus ja geoportaal)")
    if not _has_kind(pois, "egt_quarry_p4"):
        return None, ("Karjääriinfo puudub (EI OLE karjääri-"
                      "EGT-hetktõmmist hetkel: tühi tõmmis ei ole vaikne "
                      "otsus)")
    hits = _near(origin, pois, "egt_quarry_p4", QUARRY_FAR_M)
    if not hits:
        return None, ("Karjääriinfo puudub (EI OLE EGT-maardlat 2 km "
                      "aknas — akna taga on teadmata, mitte vaikus; %s)"
                      % NO_TIMETABLE)
    d0, q0 = hits[0]
    if d0 <= QUARRY_NEAR_M:
        return QUARRY_NEAR_SCORE, (
            "EGT maardla (hinnang): %s otse lähedal (%s) — lõhkamine + "
            "raskevedu hooajal; %s → skoor %d"
            % (q0.get("name"), _fmt_m(d0), NO_TIMETABLE,
               QUARRY_NEAR_SCORE))
    return QUARRY_FAR_SCORE, (
        "EGT maardla (hinnang, jäme): lähim %s %s (2 km aknas) — "
        "kaevandamismõju võimalik; %s → skoor %d"
        % (q0.get("name"), _fmt_m(d0), NO_TIMETABLE, QUARRY_FAR_SCORE))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_EGT_DIMS = (
    ("pinnas_klass_egt", "P4-016", dim_pinnas_klass_egt),
    ("karjaar_egt", "P4-054", dim_karjaar_egt),
)


def score_p4_egt(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 EGT dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_EGT_DIMS}
