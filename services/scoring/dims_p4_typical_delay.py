"""P4 typical traffic-delay dims (issue #557): rush-hour table, live out.

Buyer question: "how bad is the jam on my commute at 8:15" -
answered as TYPICAL delay, not live traffic. The map path is a
frozen snapshot; a live-jam layer cannot exist here by
construction (and a buyer needs the Tuesday pattern, not this
Tuesday). Live-jam map: non-goal, stated up front. No live polling
in the map/scorer path (harvested typical tables only); never
present typical as live (legend + reasons carry "tavaline, mitte
reaalajas").

THREE-FEED PROBE (2026-09-16, docs + one polite capability check
each, no key requests beyond published self-serve):
1. Tark Tee DATEX II: GATED (reuses the inspected p4_trans
   evidence, dims_p4_trans.py docstring, probed 2026-09-13:
   tarktee.ee root is a 66 KB driver-app shell with zero
   api/datex/avaandmed/download/wfs/rest links; legacy ArcGIS host
   moved; DATEX II SRTI hazard feeds need a registered key per
   public consumer notes). No keyless machine-readable feed, and no
   typical-speed series exposed keyless - incident/restriction legs
   stay NULL. Not re-probed: 3 days old, re-hammering is impolite.
2. TomTom / HERE traffic APIs: KEY-GATED (docs half probed
   2026-09-16: TomTom Traffic API docs confirm real-time traffic
   products + historical/traffic-stats analytics behind an API key;
   typical speeds live in the keyed products, not in a keyless
   feed). Capability check needs a self-serve key - out of scope
   ("no key requests"), so no endpoint was touched. Key from env
   only (Mapillary/OpenCellID precedent) if ever pursued; quotas
   enforced in code.
3. Tallinn real-time bus positions vs GTFS schedule: KEYLESS ANGLE
   PROVEN (fresh capability check 2026-09-16: catalogue
   ``andmed.eesti.ee/api/datasets/slug/
   uhistranspordivahendite-asukohad-reaalajas`` -> HTTP 200 JSON,
   5994 B, access PUBLIC, accrual CONT, org Tallinna
   Linnavalitsus). The file ``https://transport.tallinn.ee/gps.txt``
   carries type/line/WGS84 position/speed/heading/vehicle every ~5
   s (WGS84, keyless). Buses sit in the same jams; scheduled
   headways (GTFS, owned by the p11/p17 commute dims) give the
   baseline for free. What is NOT proven: a sampled typical-delay
   table - building it needs a sampler cron (polite 60 s+ cadence
   harvest -> corridor x hour aggregation), which is deferred work,
   not this issue.

OUTCOME: documented partial-open (keyless proxy source confirmed,
table-building sampler deferred) + the delay-table schema below,
fixture-proven, with the NULL-missing rule pinned. Static OSM road
class + maxspeed legs stand as the fallback cousins (load, never
delay). No incident feed (accidents owned by #522).

DELAY-TABLE SCHEMA (reviewer calls, documented): corridor grain =
named commute corridors (not per-segment: per-segment tables would
re-identify bus runs and overfit); hour bands = hommikune tipp
7-9 / keskpäev 10-15 / õhtune tipp 16-18 / muu (off-peak); NO
school-holiday split yet (no calendar join - single table,
documented limitation); factor = typical travel time / free-flow
time (>= 1.0). Missing hour/corridor -> NULL (never a free-flow
assumption).

Ingestion (stdlib only, offline-first, mirrors dims_p4_trans.py):
fetch Helsinki-style sampler hooks live ONLY in fetch_gps_snapshot
(documented for the future cron; single GET, 60 s timeout,
min-size guard, 429 = stop, transport errors never cached).
parse_gps_txt reads a cached gps.txt snapshot; aggregate_snapshots
folds snapshots into the corridor x hour table. Scorers and tests
never touch the network.
"""

import csv
import io
import math
import os
import time
import urllib.request
import zipfile
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Keyless bus-position snapshot (verified 2026-09-16 via the
#: catalogue metadata: access PUBLIC, accrual CONT, ~5 s updates).
GPS_SNAPSHOT_URL = "https://transport.tallinn.ee/gps.txt"

#: Sampler cadence guard: the future cron harvests at most this
#: often (polite 60 s+ cadence against a 5 s file).
SAMPLER_MIN_INTERVAL_S = 60

#: Identifying user agent for the polite sampler pull.
DELAY_UA = "home-finder delay sampler (60s+ cadence, typical tables only)"

#: Minimum plausible gps.txt body (a few dozen vehicle lines).
GPS_MIN_BYTES = 512

#: Hour bands (reviewer call): morning peak / midday / evening
#: peak / off-peak. No school-holiday split (documented).
HOUR_BANDS = (
    ("hommikune tipp", 7, 9),
    ("keskpäev", 10, 15),
    ("õhtune tipp", 16, 18),
    ("muu", -1, -1),  # off-peak catch-all
)

#: Typical-delay factor bands -> score (high = flows well).
#: Labelled "tavaline, mitte reaalajas" in every reason.
DELAY_BANDS = [(1.1, 75), (1.3, 60), (1.6, 45), (float("inf"), 30)]

#: Corridor join window (listing -> corridor representative point).
CORRIDOR_WINDOW_M = 500.0

#: Minimum snapshots backing a table cell (thin cells stay NULL).
TABLE_MIN_SAMPLES = 20


def hour_band(hour: int) -> str:
    """Hour (0-23) -> band label, per HOUR_BANDS. Pure."""
    for label, start, end in HOUR_BANDS:
        if start < 0:
            continue  # off-peak catch-all handled below
        if start <= hour <= end:
            return label
    return "muu"


def fetch_gps_snapshot(cache_dir: str, filename: str,
                       min_interval_s: int = SAMPLER_MIN_INTERVAL_S
                       ) -> Optional[str]:
    """Polite single snapshot pull for the future sampler cron.

    Fresh cache within min_interval_s: NO request. Otherwise one
    GET with DELAY_UA; stored only on HTTP 200 over GPS_MIN_BYTES.
    429/errors -> None (stop signal, never cached). Scorers and
    tests never call this.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < min_interval_s):
            return dest
    except OSError:
        return None
    try:
        req = urllib.request.Request(GPS_SNAPSHOT_URL,
                                     headers={"User-Agent": DELAY_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < GPS_MIN_BYTES:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers: gps.txt snapshot -> corridor x hour table. Pure.
# ---------------------------------------------------------------------------

def parse_gps_txt(path: str) -> List[dict]:
    """Parse a cached gps.txt snapshot. Offline.

    Live fields (CORRECTED 2026-09-17 against the real feed -- the
    catalogue description had lat/lon swapped and the #557 fixture
    copied it, so the old parser read ZERO live rows):
    vehicle type (1 trolley / 2 bus / 3 tram / 7 night bus),
    line number, LONGITUDE x1e6, LATITUDE x1e6, speed km/h (EMPTY on
    every row observed 2026-09-17 -- speeds are NOT in this feed),
    heading degrees, vehicle number, "Z" flag, route variant,
    destination. Example live row:
    ``2,1,24841420,59519450,,240,1009,Z,33,Viimsi`` = bus 1 to Viimsi
    at (24.841420, 59.519450). Returns [{vtype, line, lat, lon,
    speed, vehicle}]; garbage lines are skipped, never faked. Trams
    (3) are kept with a flag - they do not sit in road jams
    (documented, excluded at aggregation).
    """
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.strip().split(",")
            if len(parts) < 7:
                continue
            try:
                vtype = int(parts[0].strip())
            except (ValueError, AttributeError):
                continue
            if vtype not in (1, 2, 3, 7):
                continue
    # X-GIS-style axis trap: parts[2] is LONGITUDE (x), parts[3]
    # is LATITUDE (y) -- verified on live rows (bus 1 to Viimsi at
    # 24.84/59.51, bus 23 to Kadaka at 24.75/59.43).
            try:
                lon = int(parts[2].strip()) / 1e6
                lat = int(parts[3].strip()) / 1e6
            except (ValueError, AttributeError):
                continue
            if not (math.isfinite(lat) and math.isfinite(lon)
                    and 57.0 <= lat <= 61.0 and 20.0 <= lon <= 29.0):
                continue
            speed_raw = parts[4].strip() if len(parts) > 4 else ""
            try:
                speed = float(speed_raw) if speed_raw else None
            except ValueError:
                speed = None
            if speed is not None and not (math.isfinite(speed)
                                          and 0.0 <= speed <= 120.0):
                speed = None
            out.append({"vtype": vtype, "line": parts[1].strip(),
                        "lat": lat, "lon": lon, "speed": speed,
                        "vehicle": parts[6].strip() if len(parts) > 6
                        else ""})
    return out


def aggregate_snapshots(samples: List[dict],
                        corridor_of) -> Dict[Tuple[str, str], dict]:
    """Bus samples -> {(corridor, hour_band): delay cell}. Pure.

    ``corridor_of(lat, lon)`` maps a position to a corridor name (or
    None when off-corridor). Road vehicles only (vtype 1/2/7 -
    trams run on rails, not in jams). Speeds aggregate to a median
    per cell with a sample count; the delay FACTOR itself is fixed
    when the cell joins free-flow baselines (out of scope here -
    cells carry ``median_speed`` + ``n``; factor joins separately).
    Cells with n < TABLE_MIN_SAMPLES are dropped (thin cells stay
    NULL downstream).
    """
    buckets: Dict[Tuple[str, str], list] = {}
    for s in samples:
        if not isinstance(s, dict) or s.get("vtype") not in (1, 2, 7):
            continue
        try:
            lat = float(s["lat"])
            lon = float(s["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(s.get("lat"), bool) or isinstance(s.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        speed = s.get("speed")
        if not isinstance(speed, (int, float)) or isinstance(speed, bool):
            continue
        speed = float(speed)
        if not (math.isfinite(speed) and speed > 0.0):
            continue
        hour = s.get("hour")
        try:
            hour = int(hour)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not 0 <= hour <= 23:
            continue
        try:
            corridor = corridor_of(lat, lon)
        except Exception:
            continue
        if not corridor:
            continue
        buckets.setdefault((corridor, hour_band(hour)), []).append(speed)
    table = {}
    for key, speeds in buckets.items():
        if len(speeds) < TABLE_MIN_SAMPLES:
            continue
        speeds = sorted(speeds)
        mid = len(speeds) // 2
        median = (speeds[mid] if len(speeds) % 2
                  else (speeds[mid - 1] + speeds[mid]) / 2.0)
        table[key] = {"median_speed": median, "n": len(speeds)}
    return table


# ---------------------------------------------------------------------------
# Scorer legs over the harvested typical-delay table.
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


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _joined_cell(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]],
                 hour: Optional[int]) -> Tuple[Optional[dict], Optional[str]]:
    """Nearest delay cell for the corridor+hour. Missing -> NULL.

    Missing hour/corridor stays NULL - never a free-flow assumption.
    """
    if not origin or pois is None:
        return None, ("Tavalise ummiku info puudub (EI OLE koridor-tunni "
                      "viivitusliidestust hetktõmmes: Tark Tee võtmeta, "
                      "TomTom/HERE võtmega, bussisampler käivitamata)")
    if hour is None or isinstance(hour, bool):
        return None, ("Kellaaeg puudub - tavaviivitust ei saa lugeda (EI OLE "
                      "tunni liidestust, mitte vaba liiklus)")
    try:
        hour = int(hour)
    except (TypeError, ValueError):
        return None, ("Kellaaeg vigane - tavaviivitust ei saa lugeda (EI OLE "
                      "tunni liidestust, mitte vaba liiklus)")
    if not 0 <= hour <= 23:
        return None, ("Kellaaeg vigane - tavaviivitust ei saa lugeda (EI OLE "
                      "tunni liidestust, mitte vaba liiklus)")
    band = hour_band(hour)
    best = None
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != "delaycell_p4":
            continue
        if p.get("hour_band") != band:
            continue
        try:
            lat = float(p["lat"])
            lon = float(p["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(p.get("lat"), bool) or isinstance(p.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if best is None or d < best[0]:
            best = (d, p)
    if best is None or best[0] > CORRIDOR_WINDOW_M:
        return None, ("Läheduses pole %s koridori tavaviivituse kirjet - "
                      "hinnangut pole (EI OLE koridoriliidestust, mitte "
                      "mõõdetud vaba tee)" % band)
    _, poi = best
    factor = poi.get("factor")
    if isinstance(factor, bool):
        return None, ("Viivituskirje vigane - hinnangut pole (EI OLE "
                      "loetavat viivitusliidestust)")
    try:
        factor = float(factor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, ("Viivituskirje vigane - hinnangut pole (EI OLE "
                      "loetavat viivitusliidestust)")
    if not (math.isfinite(factor) and factor >= 1.0):
        return None, ("Viivituskirje vigane - hinnangut pole (EI OLE "
                      "loetavat viivitusliidestust)")
    n = poi.get("n", TABLE_MIN_SAMPLES)
    if isinstance(n, bool):
        return None, ("Viivituskirje vigane - hinnangut pole (EI OLE "
                      "loetavat viivitusliidestust)")
    try:
        n = int(n)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, ("Viivituskirje vigane - hinnangut pole (EI OLE "
                      "loetavat viivitusliidestust)")
    if n < TABLE_MIN_SAMPLES:
        return None, ("Viivituskirje liiga hõre (%d proovi) - hinnangut "
                      "pole (EI OLE piisavat viivitusliidestust)" % n)
    cell = dict(poi)
    cell["factor"] = factor
    cell["n"] = n
    return cell, None


def dim_commute_delay(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]],
                      hour: Optional[int] = None) -> Score:
    """Typical-delay leg: corridor x hour factor band (high = flows).

    Typical, NOT live: the factor is harvested from bus-position
    samples (or a keyed typical-speed series once available), never
    polled in the scorer path. Missing hour/corridor -> NULL (never
    free-flow assumption).
    """
    cell, null = _joined_cell(origin, pois, hour)
    if cell is None:
        assert null is not None
        return None, null
    factor = cell["factor"]
    s = _band(factor, DELAY_BANDS)
    assert s is not None
    return s, ("Tavalise ummiku hinnang (%s, koridor %s: tavategur x%.2f, "
               "%d proovi) -> skoor %d (tavaline, mitte reaalajas)"
               % (cell.get("hour_band"), cell.get("corridor"),
                  factor, cell["n"], s))


#: Named commute corridors as representative SEGMENTS (lon/lat
#: endpoints, 3 decimals ~ 100 m). Endpoints are public geography
#: (squares, stations, district centres); segments are JOIN geometry,
#: not a road survey -- corridor_of() matches within
#: CORRIDOR_WINDOW_M. GTFS validation counts (weekday stops near each
#: segment) ride the sidecar stats, not these coordinates.
#: Corridor = (name, polyline [(lon, lat), ...], label). The 8 legacy
#: street corridors are 2-point polylines (straight A-B strips, #629);
#: production builds use load_shape_corridors() (all GTFS trip shapes,
#: road-following, #667). Callers pass corridors= explicitly; None
#: means the legacy 8 (hermetic tests, GTFS-less fallback).
CORRIDORS = (
    ("Pärnu mnt", ((24.742, 59.434), (24.685, 59.389)),
     "Vabaduse väljak-Nõmme keskus"),
    ("Tartu mnt", ((24.753, 59.436), (24.798, 59.424)),
     "Viru-Ülemiste"),
    ("Narva mnt", ((24.754, 59.438), (24.817, 59.466)),
     "Viru-Pirita"),
    ("Paldiski mnt", ((24.737, 59.441), (24.671, 59.412)),
     "Balti jaam-Õismäe"),
    ("Ehitajate tee", ((24.732, 59.427), (24.710, 59.406)),
     "Mustamäe-Kadaka"),
    ("Laagna tee", ((24.800, 59.425), (24.860, 59.445)),
     "Ülemiste-Laagna"),
    ("Peterburi tee", ((24.805, 59.423), (24.884, 59.433)),
     "Ülemiste-Väo"),
    ("Sõpruse pst", ((24.715, 59.428), (24.700, 59.410)),
     "Kristiine-Mustamäe"),
)

#: Ribbon half-width (m) for road-following map strips (#667). Narrower
#: than the legacy 500 m join window: the dense shape web would wash
#: the county solid at full window width.
RIBBON_HALF_M = 150.0

#: Consecutive-fix window for vehicle-tracked segments (the cron
#: pulls at 60 s+ cadence; wider gaps are not one segment).
TRACK_MIN_DT_S = 30.0
TRACK_MAX_DT_S = 900.0

#: Plausible urban-bus segment speeds (stops + traffic); outside is
#: GPS jitter or a layover, never a jam measurement.
TRACK_MIN_KMH = 3.0
TRACK_MAX_KMH = 80.0


def _seg_dist_m(lat, lon, a, b):
    """Point to segment AB in metres (equirectangular, fine <1 km)."""
    r = 6371000.0
    lam, phi = math.radians(lon), math.radians(lat)
    ax, ay = math.radians(a[0]), math.radians(a[1])
    bx, by = math.radians(b[0]), math.radians(b[1])
    mx = math.cos((ay + by) / 2)
    px, py = (lam - ax) * mx, phi - ay
    dx, dy = (bx - ax) * mx, by - ay
    seg2 = dx * dx + dy * dy
    t = (px * dx + py * dy) / seg2 if seg2 > 0 else 0.0
    t = max(0.0, min(1.0, t))
    return r * math.hypot(px - dx * t, py - dy * t)


def _poly_bbox(poly):
    """(minlon, minlat, maxlon, maxlat) of a polyline (pure)."""
    lons = [p[0] for p in poly]
    lats = [p[1] for p in poly]
    return (min(lons), min(lats), max(lons), max(lats))


def build_corridor_index(corridors=None):
    """Precomputed join index: ((name, poly, bbox, label), ...). Pure.

    corridor_of scans bboxes per query; recomputing them per query
    costs a full polyline walk each time (the 196-shape web stalled
    builds: ~1 s/stop). Build once per web, pass the index wherever a
    corridors web goes -- every join entry point accepts both shapes.
    """
    if corridors is None:
        corridors = CORRIDORS
    return tuple((name, poly, _poly_bbox(poly), label)
                 for name, poly, label in corridors
                 if poly and len(poly) >= 2)


#: Import-time index of the legacy 8 (tiny polys, no I/O, hermetic).
_LEGACY_INDEX = build_corridor_index(CORRIDORS)


def _as_index(corridors):
    """Plain web or prebuilt index -> index (never recomputed twice)."""
    if corridors is None:
        return _LEGACY_INDEX
    if len(corridors) == 0:
        return ()
    first = corridors[0]
    if (len(first) == 4 and isinstance(first[2], tuple)
            and len(first[2]) == 4
            and all(isinstance(v, float) for v in first[2])):
        return corridors
    return build_corridor_index(corridors)


def _poly_dist_m(lat, lon, poly):
    """Nearest distance (m) from a point to a polyline (pure).

    Min over consecutive-vertex segments (equirectangular, fine <1 km
    per leg -- GTFS shape legs are metres apart).
    """
    best = None
    for a, b in zip(poly, poly[1:]):
        d = _seg_dist_m(lat, lon, a, b)
        if best is None or d < best:
            best = d
    return best


def corridor_of(lat, lon, corridors=None):
    """Nearest corridor within CORRIDOR_WINDOW_M (None when off). Pure.

    corridors = ((name, polyline, label), ...) or a prebuilt
    build_corridor_index(); None means CORRIDORS. Per-corridor bbox
    prefilter (window-expanded, precomputed) keeps the 196-shape web
    cheap: only nearby polylines pay the per-leg distance.
    """
    index = _as_index(corridors)
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None
    if isinstance(lat, bool) or isinstance(lon, bool):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    pad_lat = CORRIDOR_WINDOW_M / 111320.0
    pad_lon = CORRIDOR_WINDOW_M / (111320.0 * max(math.cos(
        math.radians(lat)), 0.2))
    best = None
    for name, poly, bbox, _label in index:
        x0, y0, x1, y1 = bbox
        if lon < x0 - pad_lon or lon > x1 + pad_lon:
            continue
        if lat < y0 - pad_lat or lat > y1 + pad_lat:
            continue
        d = _poly_dist_m(lat, lon, poly)
        if d is None:
            continue
        if best is None or d < best[0]:
            best = (d, name)
    if best is None or best[0] > CORRIDOR_WINDOW_M:
        return None
    return best[1]


def corridor_midpoint(name, corridors=None):
    """Representative map point of a corridor (middle vertex). Pure."""
    for cname, poly, _rest in ((e[0], e[1], e[2:]) for e in
                               _as_index(corridors)):
        if cname == name and poly and len(poly) >= 2:
            mid = poly[len(poly) // 2]
            return (mid[0], mid[1])
    return None


def load_shape_corridors(zip_path):
    """GTFS shapes.txt + trips/routes -> corridor web (offline, pure-ish).

    One corridor per shape_id: name "short · headsign" (deduped with
    " (2)" suffixes), polyline in trip order, label = route long name.
    Shapes with <2 points and rows with bad coords are dropped (never
    faked). Raises on unreadable zip (callers fall back to CORRIDORS).
    """
    with zipfile.ZipFile(zip_path) as zf:
        def _rows(name):
            with zf.open(name) as fh:
                return list(csv.DictReader(
                    io.TextIOWrapper(fh, encoding="utf-8-sig")))
        shapes = _rows("shapes.txt")
        trips = _rows("trips.txt")
        routes = _rows("routes.txt")
    route_by_id = {r.get("route_id"): r for r in routes
                   if isinstance(r, dict)}
    pts = {}
    for row in shapes:
        try:
            sid = row["shape_id"]
            pt = (float(row["shape_pt_lon"]), float(row["shape_pt_lat"]))
            seq = int(row["shape_pt_sequence"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (math.isfinite(pt[0]) and math.isfinite(pt[1])):
            continue
        pts.setdefault(sid, []).append((seq, pt))
    headsign = {}
    route_of = {}
    for t in trips:
        sid = t.get("shape_id")
        if not sid or sid in headsign:
            continue
        headsign[sid] = (t.get("trip_headsign") or "").strip()
        route_of[sid] = t.get("route_id")
    out = []
    used = set()
    for sid in sorted(pts):
        poly = [pt for _, pt in sorted(pts[sid])]
        if len(poly) < 2:
            continue
        route = route_by_id.get(route_of.get(sid), {})
        short = (route.get("route_short_name") or "").strip()
        head = headsign.get(sid, "")
        base = ("%s · %s" % (short, head)).strip(" ·") or sid
        name, k = base, 2
        while name in used:
            name = "%s (%d)" % (base, k)
            k += 1
        used.add(name)
        out.append((name, tuple(poly),
                    (route.get("route_long_name") or "").strip()))
    return tuple(out)


def strip_ribbon(polyline, half_m=RIBBON_HALF_M):
    """Polyline -> closed road-following ribbon ring (display only).

    Per-vertex perpendicular offsets (equirectangular metres, labelled
    approx like _seg_dist_m): left chain out, right chain back, closed.
    Degenerate input (<2 distinct points) reads [] (never faked).
    """
    pts = [(float(x), float(y)) for x, y in polyline or []]
    if len(pts) < 2:
        return []
    if pts[0] == pts[-1] and len(pts) > 2:
        pts = pts[:-1]
    n = len(pts)
    normals = []
    for i in range(n):
        mx = max(math.cos(math.radians(pts[i][1])), 0.2)
        acc = [0.0, 0.0]
        for j in (i - 1, i):
            if 0 <= j < n - 1:
                dx = (pts[j + 1][0] - pts[j][0]) * mx
                dy = pts[j + 1][1] - pts[j][1]
                leng = math.hypot(dx, dy) or 1e-12
                acc[0] += -dy / leng
                acc[1] += dx / leng
        leng = math.hypot(*acc)
        if leng < 1e-9:
            normals.append(None)
        else:
            dlat = half_m / 6371000.0 * 180.0 / math.pi
            normals.append((acc[0] / leng * dlat / mx,
                            acc[1] / leng * dlat))
    left, right = [], []
    for (x, y), normal in zip(pts, normals):
        if normal is None:
            continue
        ox, oy = normal
        left.append([x + ox, y + oy])
        right.append([x - ox, y - oy])
    if len(left) < 2:
        return []
    ring = left + right[::-1]
    ring.append([ring[0][0], ring[0][1]])
    return ring


def _utc_hour(t):
    """Epoch -> UTC hour (deterministic fallback, TZ-independent)."""
    return int(t // 3600 % 24)


def tallinn_hour(t):
    """Epoch -> Europe/Tallinn host-local hour (cron hosts run
    TZ=Europe/Tallinn -- host requirement, documented in the sampler
    and .github/workflows notes; DST-correct via the host libc)."""
    return time.localtime(t).tm_hour


def track_segments(fixes, hour_of=None, corridors=None):
    """Timestamped fixes -> vehicle segment speeds. Pure.

    ``fixes``: [{vehicle, t (epoch s), lat, lon}] for road vehicles
    (vtype 1/2/7 -- filter BEFORE calling). ``hour_of`` maps the
    segment-midpoint epoch to a 0-23 hour -- pass tallinn_hour on
    Europe/Tallinn cron hosts, _utc_hour (default) in tests and
    UTC-stamped pipelines. ``corridors`` is the corridor web
    (None = legacy CORRIDORS). Consecutive same-vehicle fixes with dt in
    [TRACK_MIN_DT_S, TRACK_MAX_DT_S] and speed in
    [TRACK_MIN_KMH, TRACK_MAX_KMH] yield {vehicle, t (midpoint),
    hour, lat, lon (midpoint), speed_kmh, corridor}. Jitter, layovers
    and teleporting fixes are dropped, never smoothed.
    """
    by_vehicle = {}
    for f in fixes:
        if not isinstance(f, dict):
            continue
        v = f.get("vehicle")
        if not v or not isinstance(v, str):
            continue
        try:
            t = float(f["t"])
            lat = float(f["lat"])
            lon = float(f["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(f.get("t"), bool):
            continue
        if not (math.isfinite(t) and math.isfinite(lat)
                and math.isfinite(lon)):
            continue
        by_vehicle.setdefault(v, []).append((t, lat, lon))
    if hour_of is None:
        hour_of = _utc_hour
    out = []
    for v, pts in by_vehicle.items():
        pts.sort()
        for (t0, la0, lo0), (t1, la1, lo1) in zip(pts, pts[1:]):
            dt = t1 - t0
            if not (TRACK_MIN_DT_S <= dt <= TRACK_MAX_DT_S):
                continue
            dist = _haversine_m((la0, lo0), la1, lo1)
            kmh = dist / dt * 3.6
            if not (TRACK_MIN_KMH <= kmh <= TRACK_MAX_KMH):
                continue
            mlat, mlon = (la0 + la1) / 2.0, (lo0 + lo1) / 2.0
            corridor = corridor_of(mlat, mlon, corridors)
            if not corridor:
                continue
            hour = hour_of((t0 + t1) / 2.0)
            out.append({"vehicle": v, "t": (t0 + t1) / 2.0,
                        "hour": hour, "lat": mlat, "lon": mlon,
                        "speed_kmh": kmh, "corridor": corridor})
    return out


def _median(sorted_vals):
    mid = len(sorted_vals) // 2
    return (sorted_vals[mid] if len(sorted_vals) % 2
            else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0)


def coverage_report(segments, corridors=None, thin_reason=None):
    """Tracked segments -> per-(corridor, MAP band) counts. Pure.

    Returns {"n": {(corridor, band): n}, "thin": [(corridor, band)
    with n < TABLE_MIN_SAMPLES], "thin_reason": thin_reason}. Every
    web corridor x every MAP band is listed (zero where unmeasured --
    absence is the signal, never hidden). thin_reason is an OPERATOR
    slot: None means no documented reason (undocumented gap --
    investigate, never assume); the cron operator stamps the reason
    (pole README / run log) when the gap is understood (e.g. night
    buses skip a corridor, so its muu baseline can never fill).
    """
    names = [name for name, _poly, _bbox, _label
             in _as_index(corridors if corridors is not None
                          else build_corridor_index())]
    n = {(c, b): 0 for c in names for b in MAP_BANDS}
    for s in segments:
        if not isinstance(s, dict):
            continue
        corridor = s.get("corridor")
        hour = s.get("hour")
        if not corridor or not isinstance(corridor, str):
            continue
        try:
            hour = int(hour)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if not 0 <= hour <= 23:
            continue
        key = (corridor, hour_band(hour))
        if key in n:
            n[key] += 1
    thin = sorted([k for k, v in n.items() if v < TABLE_MIN_SAMPLES])
    return {"n": n, "thin": thin, "thin_reason": thin_reason}


def build_delay_table(segments):
    """Segments -> {(corridor, hour_band): delay cell}. Pure.

    Free-flow baseline per corridor = its off-peak ("muu") median;
    corridors without one stay factor-NULL (never a free-flow
    assumption). factor = free / typical, clamped >= 1.0. Cells with
    n < TABLE_MIN_SAMPLES are dropped (thin cells stay NULL
    downstream). No school-holiday split (documented limitation).
    """
    buckets = {}
    for s in segments:
        if not isinstance(s, dict):
            continue
        corridor = s.get("corridor")
        speed = s.get("speed_kmh")
        hour = s.get("hour")
        if not corridor or not isinstance(corridor, str):
            continue
        try:
            speed = float(speed)  # type: ignore[arg-type]
            hour = int(hour)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if isinstance(s.get("speed_kmh"), bool):
            continue
        if not (math.isfinite(speed) and speed > 0.0):
            continue
        if not 0 <= hour <= 23:
            continue
        buckets.setdefault((corridor, hour_band(hour)), []).append(speed)
    medians = {k: _median(sorted(v)) for k, v in buckets.items()
               if len(v) >= TABLE_MIN_SAMPLES}
    free = {}
    for (corridor, band), med in medians.items():
        if band == "muu":
            free[corridor] = med
    table = {}
    for (corridor, band), med in medians.items():
        if band == "muu" or corridor not in free or med <= 0:
            continue
        factor = max(1.0, free[corridor] / med)
        n = len(buckets[(corridor, band)])
        table[(corridor, band)] = {"median_speed": med,
                                   "free_speed": free[corridor],
                                   "factor": factor, "n": n}
    return table


#: Hour bands painted as map layers (plus the worst-of-peaks rollup).
MAP_BANDS = ("hommikune tipp", "keskpäev", "õhtune tipp", "muu")
WORST_BAND = "worst"


def muu_baselines(segments):
    """Off-peak baseline medians per corridor (the free-flow anchor).

    Returns {corridor: {"median": x, "n": n}} for "muu" buckets with
    n >= TABLE_MIN_SAMPLES; thinner baselines are dropped (their
    corridors stay factor-NULL everywhere). Pure.
    """
    buckets = {}
    for s in segments:
        if not isinstance(s, dict):
            continue
        corridor = s.get("corridor")
        speed = s.get("speed_kmh")
        hour = s.get("hour")
        if not corridor or not isinstance(corridor, str):
            continue
        try:
            speed = float(speed)  # type: ignore[arg-type]
            hour = int(hour)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if isinstance(s.get("speed_kmh"), bool):
            continue
        if not (math.isfinite(speed) and speed > 0.0):
            continue
        if not 0 <= hour <= 23 or hour_band(hour) != "muu":
            continue
        buckets.setdefault(corridor, []).append(speed)
    return {c: {"median": _median(sorted(v)), "n": len(v)}
            for c, v in buckets.items() if len(v) >= TABLE_MIN_SAMPLES}


def table_to_pois(table, corridors=None):
    """Delay table -> delaycell_p4 POIs for the scorer join. Pure."""
    pois = []
    for (corridor, band), cell in table.items():
        mid = corridor_midpoint(corridor, corridors)
        if mid is None:
            continue
        pois.append({"kind": "delaycell_p4", "corridor": corridor,
                     "hour_band": band, "lat": mid[1], "lon": mid[0],
                     "factor": cell["factor"], "n": cell["n"]})
    return pois


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_DELAY_DIMS = (
    ("commute_delay", "P4-delay", dim_commute_delay),
)


def score_p4_delay(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]],
                   hour: Optional[int] = None) -> Dict[str, Optional[int]]:
    """P4 typical-delay leg for one listing (entry point for follow-up)."""
    return {key: fn(origin, pois, hour)[0] for key, _, fn in P4_DELAY_DIMS}
