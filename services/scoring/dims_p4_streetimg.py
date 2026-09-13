"""P4 crowdsourced street imagery dims: demo (#303) + coverage (#372).

Demo param (this ingestion's anchor):
* P4-029 Street-imagery block observer (eye-level street reading, photo date)

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-022 Listing photo forensics (street-frame facade-truth leg)
* P4-040 Last-200 m arrival sequence (peak-end arrival feel, photo date)

OPENNESS VERDICT (probed 2026-09-13, single polite fetches with a contact
UA, >= 4 s pacing, bodies cached under /tmp/hf-p4-streetimg/ — full
evidence in docs/p4_streetimg.md):
* Mapillary developer docs (API v4): OPEN (HTTP 200, 156 271 B). An
  "Image Radius Search" (lat/lng, radius default/max 50 m, limit
  default 1/max 100, "best" by proximity+recency+360 preference) fits
  the per-listing pull exactly; entity APIs rate-limited at 60 000/min
  per app (orders above our cadence).
* Mapillary Terms of Use (effective 2024-02-15): OPEN-CONDITIONAL
  (HTTP 200, 135 225 B). Other users' content is CC BY-SA unless
  indicated otherwise; scraping/data-mining is NOT approved — pulls go
  through the token API, never page scraping.
* Token gate verified first-hand: an unauthenticated Graph GET returns
  {"error":{"message":"Invalid OAuth 2.0 Access Token",...,"code":190}}
  — the endpoint is live and an OAuth 2.0 client/user token is required
  (free app registration; token from env at pull time, NEVER committed).
* DATED PARTIAL-NEGATIVE (verdict kept, gap-fill not wired): KartaView.
  Docs redirect to a JS-only SPA shell (kartaview.org/doc, HTTP 200 yet
  2 159 B of "Loading KartaView...") and the V3 API surface was cut back
  in June 2024. The schema accepts kartaview-sourced frames so gap-fill
  lands without code changes; no KartaView pull is attempted until its
  endpoint is re-verified.

HONESTY (AGENTS.md section 7.2): scored shapes are per-listing dims with
a photo date — never a gradient, never interpolation, never a heat-map
guess. Every NULL reason says "hinnang" (estimate) and "EI OLE" and
names the concrete check (walk the block / wait for a frame / ask the
broker) — never a faked number. Scored reasons say "hinnang", carry the
frame date (or "kuupäevata" with a cap), and name the source. Transport
errors in fetch_mapillary are NEVER cached as data, and HTTP 429 is a
stop signal, not a retry dare (AGENTS.md sections 7.2/7.4).

Style: pure offline scorers (listing, streetimg, today) ->
(Optional[int 0..100], Estonian reason), mirroring
dims_p4_maa_aerial.py (#246/#330). Network lives ONLY in fetch_cached /
fetch_mapillary (polite single-GET + file cache + TTL); tests never
touch the network. Helpers are local copies (not imported from
livability or sibling batches): a future central hook may import this
module alongside them, and importing any of them here would turn that
into a cycle (same precedent as batch B3, PR #100). No
livability/WEIGHTS/layers integration here — rebalancing stays one
joint change across batches (existing tests pin WEIGHTS).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR because issue #372's body states it
  extends the #303 demo ingestion ("no new plumbing expected") — same
  precedent as #384 (#244 demo + #328 coverage) and #246/#330.
* Overlaps are legs, not edits (sibling files UNTOUCHED): dims_p4_osm
  scores P4-029/P4-040 as mapped walkability proxies (footway/sidewalk/
  lit tags) while this module scores date-stamped eye-level frames;
  dims_p4_maa_aerial scores P4-022/P4-029 off aerial vintages while this
  module's facade leg is eye-level; dims_p4_own_store keeps P4-029/P4-040
  NULLs that name this source as missing — this module provides it. The
  weight-rebalance follow-up merges the legs; nothing here double-pushes
  the sort on its own.
* TTL 30 d for imagery (coverage grows continuously; matches the
  Overpass POI-cache precedent), 365 d for the terms/docs re-verify.
* Freshness bar 730 d (2 y): a clean older frame caps at 60, an undated
  frame at 65 — a facade from before the last renovation cycle is not
  evidence. Date-stamp comes from captured_at (ms epoch -> YYYY-MM-DD).
* P4-040 without a frame inside the last-200 m window stays NULL even
  when farther frames exist: the window IS the param. Arrival feel is
  never a safety claim — PPA/Paasteamet signals are excluded and the
  reasons state the exclusion (peak-end framing documented).

Street-image record schema (one dict per listing, built from the cached
radius-search pulls + adapter store + OSM cross-check; every field
optional, missing -> leg stays out, never defaulted):
* images: [{image_id, captured_at "YYYY-MM-DD"|None, creator,
  distance_m|None, source "mapillary"|"kartaview", quality_score|None,
  thumb_url|None}] (parse_image_search builds these minus distance_m,
  which the caller adds with its own haversine — the API fields carry
  no per-image coordinates)
* facade_ok: True/False/None (eye-level facade verdict for the frame)
* street_issues: list[str] (facade/litter/wrecks/sidewalk findings)
* sidewalk_ok: True/False/None (OSM ground-truth cross-check join)
* arrival_frames: [{same shape}] (last-200 m approach frames, dated)
* arrival_lit_ok / arrival_footway_ok: True/False/None (lamp-density +
  footway/surface approach legs; safety registers explicitly excluded)
* duplicate_hashes: int|None; exif_daylight_ok: True/False/None
  (own-store joins copied in, never re-fetched here)
"""

import datetime as _dt
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #303 acceptance criterion 2).
# ---------------------------------------------------------------------------

#: Graph API root for per-listing metadata pulls (token-gated, OPEN 2026-09-13).
MAPILLARY_GRAPH_ROOT = "https://graph.mapillary.com"

#: Metadata fields requested per frame (documented API v4 image fields).
MAPILLARY_FIELDS = (
    "id,captured_at,creator_username,quality_score,thumb_1024_url"
)

#: Radius-search ceilings from the 2026-04-02 "Image Radius Search"
#: changelog entry (radius default/max 50 m, limit default 1/max 100).
RADIUS_MAX_M = 50
LIMIT_MAX = 100

SOURCE_URLS = {
    # API v4 surfaces, auth rules, rate limits (OPEN 2026-09-13).
    "mapillary_dev": (
        "https://www.mapillary.com/developer/api-documentation"
    ),
    # CC BY-SA imagery grant + no-scraping rule (OPEN 2026-09-13).
    "mapillary_terms": "https://www.mapillary.com/terms",
    # JS-only SPA shell (DATED PARTIAL-NEGATIVE 2026-09-13, not wired).
    "kartaview_doc": "https://kartaview.org/doc",
}

# TTLs in days: imagery re-pulls monthly (coverage grows continuously),
# terms/docs re-verified annually.
TTL_DAYS = {
    "mapillary_images": 30,
    "terms_reverify": 365,
}

CACHE_SUBDIR = "hf-p4-streetimg"
USER_AGENT = (
    "home-finder-research/0.1 (polite per-listing pulls; "
    "GitHub gregoreesmaa/home-finder issue 303)"
)

#: Frame sources accepted in the schema (KartaView = gap-fill, see verdict).
KNOWN_SOURCES = ("mapillary", "kartaview")


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


def _get(url: str, timeout_s: int = 25) -> bytes:
    """Single polite GET with the contact UA (urllib only, no new dependency)."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        if resp.status == 429:
            raise RuntimeError("HTTP 429 — stop, do not retry: " + url)
        return resp.read()


def fetch_cached(url: str, cache_dir: str, name: str, ttl_days: int,
                 timeout_s: int = 25) -> str:
    """Polite single-GET with file cache. Returns the cache path.

    Fresh cache wins (no request). Transport errors are raised and NEVER
    written as data; HTTP 429 raises immediately (stop signal, no retry).
    """
    dest = cache_path(cache_dir, name)
    if is_fresh(dest, ttl_days):
        return dest
    body = _get(url, timeout_s)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, dest)
    return dest


def build_radius_search_url(lat: float, lon: float,
                            radius_m: int = 50, limit: int = 10) -> str:
    """Per-listing Image Radius Search URL (no token in it — added at fetch).

    Radius clamps to 1..50 m and limit to 1..100 per the API ceilings;
    one request per listing per run, "best" (proximity+recency+360)
    ranking done server-side.
    """
    r = max(1, min(int(radius_m), RADIUS_MAX_M))
    lim = max(1, min(int(limit), LIMIT_MAX))
    return ("%s/images?lat=%.6f&lng=%.6f&radius=%d&limit=%d&fields=%s"
            % (MAPILLARY_GRAPH_ROOT, float(lat), float(lon),
               r, lim, MAPILLARY_FIELDS))


def fetch_mapillary(url: str, token: str, cache_dir: str, name: str,
                    ttl_days: int = 30, timeout_s: int = 25) -> str:
    """Token-gated Mapillary pull with file cache. Returns the cache path.

    The token arrives per call (env at pull time, NEVER committed or
    logged); the cached body keeps no credential. Otherwise the same
    politeness contract as fetch_cached.
    """
    dest = cache_path(cache_dir, name)
    if is_fresh(dest, ttl_days):
        return dest
    sep = "&" if "?" in url else "?"
    body = _get(url + sep + "access_token=" + token, timeout_s)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, dest)
    return dest


def _ms_to_datestr(value: object) -> Optional[str]:
    """Mapillary captured_at (ms epoch) -> "YYYY-MM-DD" (None when bad)."""
    if isinstance(value, bool):
        return None
    try:
        ms = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    try:
        return _dt.datetime.fromtimestamp(
            ms / 1000.0, tz=_dt.timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def parse_image_search(payload: object) -> List[dict]:
    """Image records from a cached radius-search body (pure, no network).

    Accepts the Graph {"data": [...]} shape; entries without an id are
    skipped (never defaulted). distance_m is left for the caller — the
    requested fields carry no per-image coordinates.
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    records: List[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        image_id = item.get("id")
        if not image_id:
            continue
        quality = item.get("quality_score")
        records.append({
            "image_id": str(image_id),
            "captured_at": _ms_to_datestr(item.get("captured_at")),
            "creator": item.get("creator_username"),
            "distance_m": None,
            "source": "mapillary",
            "quality_score": (quality if isinstance(quality, (int, float))
                              and not isinstance(quality, bool) else None),
            "thumb_url": item.get("thumb_1024_url"),
        })
    return records


def _photo_age_days(date_s: Optional[str],
                    today: Optional[str] = None) -> Optional[int]:
    if not date_s:
        return None
    try:
        seen = _dt.date.fromisoformat(str(date_s))
    except ValueError:
        return None
    now = _dt.date.fromisoformat(str(today)) if today else _dt.date.today()
    return (now - seen).days


def _nearest_frame(frames: object) -> Optional[dict]:
    """Frame with the smallest known distance_m (distanceless sorts last)."""
    best: Optional[dict] = None
    best_d: Optional[float] = None
    if not isinstance(frames, list):
        return None
    for item in frames:
        if not isinstance(item, dict):
            continue
        dist = item.get("distance_m")
        known = (isinstance(dist, (int, float))
                 and not isinstance(dist, bool))
        d = float(dist) if known else None
        if best is None or (d is not None
                             and (best_d is None or d < best_d)):
            best, best_d = item, d
    return best


def _src_word(source: object) -> str:
    if source == "mapillary":
        return "Mapillary"
    if source == "kartaview":
        return "KartaView"
    return "tänava"


#: Freshness bar in days: older clean frames cap at 60 (a facade from
#: before the last renovation cycle is not evidence).
STALE_DAYS = 730


# ---------------------------------------------------------------------------
# Demo dim: P4-029 street-imagery block observer (issue #303).
# ---------------------------------------------------------------------------

def dim_streetimg_block(listing: dict, streetimg: dict,
                        today: Optional[str] = None) -> Score:
    """P4-029: eye-level street reading off the nearest date-stamped frame.

    Issues or a bad facade -> 40; sidewalk-only doubt -> 55; clean but
    stale (> 2 y) -> 60; clean but undated -> 65; fresh clean -> 75.
    No frame at all stays NULL (never a street verdict off zero frames).
    """
    _ = listing
    images = streetimg.get("images") if isinstance(streetimg, dict) else None
    frame = _nearest_frame(images)
    if frame is None:
        return None, ("Tänavakaadrit (Mapillary/KartaView date-stamped "
                      "seeria) EI OLE — silmakõrguse hinnang puudub: jaluta "
                      "kvartal läbi / oota kaadrit, ära feigi")
    src = _src_word(frame.get("source"))
    date_s = frame.get("captured_at")
    date_txt = date_s or "kuupäevata"
    facade_ok = streetimg.get("facade_ok")
    issues = streetimg.get("street_issues") or []
    sidewalk_ok = streetimg.get("sidewalk_ok")
    if issues or facade_ok is False:
        problems = (", ".join(issues) if issues else "fassaad kahtlane")
        return 40, ("Tänavavaatluse hinnang 40/100 (%s; %s kaader %s): "
                    "fassaadi/prahi/vraki/kõnnitee mure — vaata kohapeal üle"
                    % (problems, src, date_txt))
    if sidewalk_ok is False:
        return 55, ("Tänavavaatluse hinnang 55/100: kõnnitee-kahtlus (OSM "
                    "ristkontroll), muu puhas — %s kaader %s"
                    % (src, date_txt))
    age = _photo_age_days(date_s, today)
    if age is not None and age > STALE_DAYS:
        return 60, ("Tänavavaatluse hinnang 60/100 (vananenud foto, %d p "
                    "vana — lagi): puhas, aga kaader vajab uuendust"
                    % age)
    if age is None:
        return 65, ("Tänavavaatluse hinnang 65/100 (foto kuupäevata — "
                    "lagi): puhas, aga date-stamp puudub — %s kaader"
                    % src)
    return 75, ("Tänavavaatluse hinnang 75/100: fassaad ja umbrus puhtad "
                "(%s kaader %s)" % (src, date_s))


# ---------------------------------------------------------------------------
# Coverage dims: the 2 remaining params off this source (issue #372).
# ---------------------------------------------------------------------------

def dim_streetimg_photo_forensics(listing: dict, streetimg: dict,
                                 today: Optional[str] = None) -> Score:
    """P4-022: relist/defect-hiding check with the street-frame facade leg.

    Four legs, each optional: eye-level facade truth (date-stamped frame),
    own-store image-hash duplicates, EXIF/daylight sanity, photo-vs-EHR
    room-count mismatch. 2+ flags -> 30, 1 flag -> 55, clean with >= 1
    leg -> 80. No leg at all stays NULL (never clean off zero evidence).
    """
    _ = today
    images = streetimg.get("images") if isinstance(streetimg, dict) else None
    frame = _nearest_frame(images)
    facade_ok = streetimg.get("facade_ok")
    issues = streetimg.get("street_issues") or []
    dup = streetimg.get("duplicate_hashes")
    daylight = listing.get("exif_daylight_ok",
                           streetimg.get("exif_daylight_ok"))
    photo_n = listing.get("photo_room_count")
    ehr_n = listing.get("ehr_room_count")

    legs = 0
    flags: List[str] = []
    street_txt = ""
    if frame is not None:
        legs += 1
        date_txt = frame.get("captured_at") or "kuupäevata"
        street_txt = ("%s fassaaditõde %s"
                      % (_src_word(frame.get("source")), date_txt))
        if facade_ok is False or issues:
            problems = (", ".join(issues) if issues
                        else "fassaad kahtlane")
            flags.append("tänavakaader näitab: %s" % problems)
    if isinstance(dup, int) and not isinstance(dup, bool) and dup >= 0:
        legs += 1
        if dup >= 1:
            flags.append("ristportaali duplikaat/relist (%d)" % dup)
    if isinstance(daylight, bool):
        legs += 1
        if not daylight:
            flags.append("päevavalguse kahtlus (EXIF/hetktõmmise kontroll)")
    if isinstance(photo_n, int) and isinstance(ehr_n, int):
        legs += 1
        if photo_n != ehr_n:
            flags.append("tubade arvu lõhe (%d fotol vs %d EHR-is)"
                         % (photo_n, ehr_n))
    if legs == 0:
        return None, ("Fototõe jalgu (tänavakaader + adapteri pildiladu) "
                      "EI OLE — relist/varjatud defekti hinnang puudub: "
                      "kogu fototõed adapterist ja kohapeal, ära feigi")
    if len(flags) >= 2:
        return 30, ("Fotokontrolli hinnang 30/100: %s — võimalik "
                    "relist/varjatud defekt, küsimus maaklerile"
                    % "; ".join(flags))
    if len(flags) == 1:
        return 55, ("Fotokontrolli hinnang 55/100: %s — üksik "
                    "hoiatussignaal, kontrolli üle" % flags[0])
    clean = ("%s; " % street_txt if street_txt else "")
    return 80, ("Fotokontrolli hinnang 80/100: %d jalga puhtad (%sduplikaate/"
                "päevavalguse viga/tubade lõhe/fassaadimuutust pole)"
                % (legs, clean))


def dim_streetimg_arrival(listing: dict, streetimg: dict,
                          today: Optional[str] = None) -> Score:
    """P4-040: last-200 m arrival feel off date-stamped approach frames.

    Bad lamp/footway legs -> 45; clean fresh -> 70; clean stale or
    undated -> 60. No frame inside the 200 m window stays NULL even when
    farther frames exist (the window IS the param). Peak-end framing;
    arrival feel is never a safety claim (PPA/Päästeamet excluded).
    """
    _ = listing
    frames = (streetimg.get("arrival_frames")
              if isinstance(streetimg, dict) else None)
    anchor = _nearest_frame(frames)
    if anchor is None:
        return None, ("Saabumis-hinnang puudub (EI OLE saabumisseeriat): "
                      "viimase 200 m tunne eeldab Mapillary date-stamped "
                      "seeriaid + valgusjalga — kõnni marsruut novembriõhtul "
                      "läbi, ära feigi")
    dist = anchor.get("distance_m")
    if not (isinstance(dist, (int, float))
            and not isinstance(dist, bool)):
        return None, ("Saabumis-hinnang puudub (EI OLE kaugusega kaadrit): "
                      "lähimal kaadril kaugusemärge puudub, viimase 200 m "
                      "akent ei saa kinnitada — täienda kaugused, ära feigi")
    if dist > 200:
        return None, ("Saabumis-hinnang puudub (EI OLE 200 m akna kaadrit): "
                      "lähim kaader %.0f m kaugusel — viimase 200 m tunnet "
                      "see ei kata, kogu saabumine kohapeal" % dist)
    src = _src_word(anchor.get("source"))
    date_s = anchor.get("captured_at")
    date_txt = date_s or "kuupäevata"
    lit_ok = streetimg.get("arrival_lit_ok")
    footway_ok = streetimg.get("arrival_footway_ok")
    tail = ("tipu-lõpu reegel: viimased meetrid kaaluvad; saabumistunne, "
            "mitte ohutusväide (PPA/Päästeametit ei kasutata)")
    if lit_ok is False or footway_ok is False:
        weak = ("pime lõik" if lit_ok is False else "kõnnitee/jalgtee lünk")
        return 45, ("Saabumis-hinnang 45/100 (%s; %s kaader %s): %s — "
                    "kõnni marsruut novembriõhtul läbi" % (weak, src,
                                                           date_txt, tail))
    age = _photo_age_days(date_s, today)
    if age is not None and age > STALE_DAYS:
        return 60, ("Saabumis-hinnang 60/100 (vananenud foto, %d p vana — "
                    "lagi): korras saabumine, aga kaader vajab uuendust; %s"
                    % (age, tail))
    if age is None:
        return 60, ("Saabumis-hinnang 60/100 (foto kuupäevata — lagi): "
                    "korras saabumine, aga date-stamp puudub; %s" % tail)
    return 70, ("Saabumis-hinnang 70/100: korras saabumine (%s kaader %s); "
                "%s" % (src, date_s, tail))


# ---------------------------------------------------------------------------
# Registry + aggregator (entry point for the weight-rebalance follow-up).
# ---------------------------------------------------------------------------

P4_STREETIMG_DIMS = (
    ("block_observer", "P4-029", dim_streetimg_block),
    ("photo_forensics", "P4-022", dim_streetimg_photo_forensics),
    ("arrival_sequence", "P4-040", dim_streetimg_arrival),
)


def score_p4_streetimg(listing: dict, streetimg: dict,
                       today: Optional[str] = None
                       ) -> Dict[str, Optional[int]]:
    """All 3 P4 street-imagery dims for one listing (keys match registry)."""
    return {key: fn(listing, streetimg, today)[0]
            for key, _pnum, fn in P4_STREETIMG_DIMS}
