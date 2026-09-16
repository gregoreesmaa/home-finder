"""Maa-amet kataster Tallinn tile harvest (issue #520): bbox-paginated WFS.

Stdlib only. Polite bbox-tiled pull of ``kataster:ky_kehtiv`` parcels
over the Tallinn city bbox into per-tile raw GeoJSON caches plus one
merged ``kk_ky_tallinn_merged.json`` that the existing
``batch_maaparcel_kataster.py --parcels`` rebuild consumes unchanged.
Pure planning/merging logic at module top so unit tests stay hermetic;
network lives ONLY in the fetch helpers below.

WHY TILES (issue #520): the #491 map sample was a polite
count-capped pull (``count <= 100``) over one Kesklinn window, so
coverage ends where the sample ends. The register has no openly
offered cadastre vector-tile endpoint (public-search negative
2026-09-16, see docs/parcel-tiling.md — WMS is raster-only,
minu.kataster.ee is login-walled), so city coverage comes from many
small polite bbox windows instead of one big pull.

URL SHAPE (verified, not guessed): GetFeature URLs reuse the
production scorer contract byte-for-byte
(services/scoring/dims_overturn_maa.py::layer_url — WFS 2.0.0,
``outputFormat=application/json``, ``srsName=EPSG:4326``,
``count=100``, ``bbox=minlon,minlat,maxlon,maxlat,EPSG:4326``).

POLITENESS (AGENTS.md 7.4, parameters3.md 5.3): one GET per tile,
``count <= 100`` always, paced >= 3 s (PARCEL_PACE_S), identifying UA,
fresh raw-tile cache wins (no request), HTTP 429 STOPS the whole run
immediately (no retry, partial manifest kept), transport errors and
unparseable bodies are never cached as data. Dense tiles subdivide
recursively (never raise ``count``): sparse Tallinn tiles finish in
one GET, dense old-town tiles split down to MIN_TILE_DEG. A tile that
is STILL full at the minimum span is flagged ``truncated`` in the
manifest (honest partial, never silent).

SCOPE: parcels only. KKIS touch counts stay on the #491 window until
a KKIS tiling follow-up lands — a merged rebuild therefore carries
``kkis: None`` (unknown, never zero) outside the old window, and the
legend keeps reading outside-harvest as teadmata (never blank-as-zero).

Usage:
  python3 scripts/build/harvest_maaparcel_tiles.py --probe \\
      --cache-dir /tmp/hf-520-parcel        # 1 GET: validate URL shape
  python3 scripts/build/harvest_maaparcel_tiles.py \\
      --cache-dir ~/hf-data/parcel-tiles    # full tiled harvest (paced)
  python3 scripts/build/harvest_maaparcel_tiles.py --merge-only \\
      --cache-dir ~/hf-data/parcel-tiles    # rebuild merged file offline
"""

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Verified open WFS base (docs/overturn_maa.md 2026-09-13: 200,
#: 1091 layers, no auth, no key).
WFS_BASE = "https://gsavalik.envir.ee/geoserver/wfs"

#: Parcel register typename (field contract verified 2026-09-13:
#: tunnus, pindala, omvorm, siht1/2/3, l_aadress, ...).
PARCEL_TYPENAME = "kataster:ky_kehtiv"

#: Tallinn city bbox [minlon, minlat, maxlon, maxlat] (the #235/#491 bbox).
TALLINN_BBOX = [24.5, 59.35, 24.9, 59.5]

#: Tile size in degrees (~1.1 km E-W x ~1.1 km N-S at Tallinn latitude).
TILE_W_DEG = 0.02
TILE_H_DEG = 0.01

#: Minimum tile span: denser than this stays flagged truncated (honest).
MIN_TILE_DEG = 0.0025

#: parameters3.md 5.3 politeness cap — NEVER raised (dense tiles split).
COUNT_PER_TILE = 100

#: Seconds between harvest GETs (the >= 3 s #235/#491 precedent).
PARCEL_PACE_S = 3

#: Identifying user agent for the polite pull (paced tile GETs, no scrape).
PARCEL_TILES_UA = (
    "home-finder-520-parcel-tiles/1.0 "
    "(bbox-tiled WFS harvest, paced >=3s, 429=stop; "
    "GitHub gregoreesmaa/home-finder issue 520)"
)

#: Parcel registers change slowly (#235 re-check 2027-03-13): at most one
#: harvest per 180 d per cache dir; fresh raw tiles are never re-pulled.
PARCEL_TILES_TTL_S = 180 * 24 * 3600

#: Minimum plausible per-tile GeoJSON body (an empty FeatureCollection
#: is ~50 B; anything smaller is an error page, never data).
TILE_MIN_BYTES = 100

#: Raw per-tile cache glob inside the cache dir (filenames derive from
#: the tile bbox via _tile_path, so resume finds them deterministically).
TILE_GLOB = "tile_*.geojson"

#: Merged output consumable by batch_maaparcel_kataster.py --parcels.
MERGED_FILENAME = "kk_ky_tallinn_merged.json"

#: Harvest manifest (honest coverage record, see harvest()).
MANIFEST_FILENAME = "harvest_manifest.json"

#: Sentinel: the server asked us to stop (HTTP 429). Never data, never
#: retried — the run aborts and the partial manifest says stopped.
STOP = object()

BBox = List[float]


def _headers() -> dict:
    return {"User-Agent": PARCEL_TILES_UA}


# ---------------------------------------------------------------------------
# Pure tile planning + URL + merge logic (hermetically tested).
# ---------------------------------------------------------------------------

def plan_tiles(bbox: BBox, tile_w: float = TILE_W_DEG,
               tile_h: float = TILE_H_DEG) -> List[BBox]:
    """Cover bbox with small windows (edge tiles clamped, never gapped).

    Counts come from ceil (epsilon-snapped against float dust), edges
    from linspace: the last row/column ends exactly on the bbox edge so
    coverage is gapless, overlap-free, and degenerate-free.
    """
    minlon, minlat, maxlon, maxlat = bbox
    ncols = max(1, int(math.ceil((maxlon - minlon) / tile_w - 1e-9)))
    nrows = max(1, int(math.ceil((maxlat - minlat) / tile_h - 1e-9)))
    lons = [minlon + (maxlon - minlon) * i / ncols for i in range(ncols + 1)]
    lats = [minlat + (maxlat - minlat) * j / nrows for j in range(nrows + 1)]
    lons[-1], lats[-1] = maxlon, maxlat  # exact edge, never float dust
    return [[lons[i], lats[j], lons[i + 1], lats[j + 1]]
            for j in range(nrows) for i in range(ncols)]


def subdivide(bbox: BBox) -> List[BBox]:
    """Split one tile into 4 children (midpoint split, exact cover)."""
    minlon, minlat, maxlon, maxlat = bbox
    midlon, midlat = (minlon + maxlon) / 2, (minlat + maxlat) / 2
    return [[minlon, minlat, midlon, midlat],
            [midlon, minlat, maxlon, midlat],
            [minlon, midlat, midlon, maxlat],
            [midlon, midlat, maxlon, maxlat]]


def tile_url(bbox: BBox,
             typename: str = PARCEL_TYPENAME,
             count: int = COUNT_PER_TILE) -> str:
    """One polite GetFeature URL (scorer contract, EPSG:4326 GeoJSON)."""
    minlon, minlat, maxlon, maxlat = bbox
    return (WFS_BASE + "?service=WFS&version=2.0.0&request=GetFeature"
            "&outputFormat=application/json&srsName=EPSG:4326"
            "&count=%d&typeName=%s"
            "&bbox=%s,%s,%s,%s,EPSG:4326"
            % (count, typename, minlon, minlat, maxlon, maxlat))


def count_features(payload: bytes) -> Optional[int]:
    """GeoJSON body -> feature count, or None when unparseable (never data)."""
    try:
        doc = json.loads(payload)
    except ValueError:
        return None
    feats = doc.get("features") if isinstance(doc, dict) else None
    return len(feats) if isinstance(feats, list) else None


def valid_tile_body(payload: bytes) -> bool:
    """A 200 body is data only when it parses with a features list."""
    return (len(payload) >= TILE_MIN_BYTES
            and count_features(payload) is not None)


def _tunnus(feat: dict) -> Optional[str]:
    try:
        props = feat.get("properties")
    except AttributeError:
        return None
    if not isinstance(props, dict):
        return None
    tunnus = props.get("tunnus")
    return tunnus if isinstance(tunnus, str) and tunnus else None


def merge_features(docs: List[dict]) -> Tuple[List[dict], dict]:
    """Tile docs -> (deduped features, stats). Pure, offline.

    Dedupe key is the register ``tunnus`` (tiles are overlap-free, but
    subdivision re-covers parents, so duplicates are expected, never an
    error). Features without a tunnus are kept (the sidecar builder
    skips them, never fakes them) and counted.
    """
    seen = set()
    merged: List[dict] = []
    stats = {"tiles": len(docs), "features": 0, "parcels": 0,
             "duplicates": 0, "untunnused": 0}
    for doc in docs:
        feats = doc.get("features") if isinstance(doc, dict) else None
        if not isinstance(feats, list):
            continue
        for feat in feats:
            if not isinstance(feat, dict):
                continue
            stats["features"] += 1
            tunnus = _tunnus(feat)
            if tunnus is None:
                stats["untunnused"] += 1
                merged.append(feat)
                continue
            if tunnus in seen:
                stats["duplicates"] += 1
                continue
            seen.add(tunnus)
            merged.append(feat)
    stats["parcels"] = len(seen)
    return merged, stats


# ---------------------------------------------------------------------------
# Network (one polite GET per tile; 429 = stop). Tests stub _fetch.
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout_s: int = 30):
    """One GET: body bytes on HTTP 200, STOP on 429, else None.

    No retries. Transport errors are never data.
    """
    try:
        req = urllib.request.Request(url, headers=_headers())
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if getattr(resp, "status", 200) != 200:
                return None
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return STOP
        return None
    except Exception:
        return None


def _tile_path(cache_dir: str, tile: BBox) -> str:
    """Deterministic raw-tile filename from the tile bbox (resume-safe).

    Subdivision children re-derive the same filename on every run, so a
    resumed harvest finds fresh child caches instead of re-pulling them.
    """
    key = "_".join("%.6f" % v for v in tile)
    return os.path.join(cache_dir, "tile_%s.geojson" % key)


def _fresh(path: str, ttl_s: int) -> bool:
    try:
        return (os.path.exists(path)
                and time.time() - os.path.getmtime(path) < ttl_s)
    except OSError:
        return False


def harvest(cache_dir: str,
            bbox: BBox = TALLINN_BBOX,
            ttl_s: int = PARCEL_TILES_TTL_S,
            fetcher: Callable[[str], object] = _fetch,
            sleeper: Callable[[float], None] = time.sleep) -> dict:
    """Tiled harvest into cache_dir (resume-safe, 429 stops, never fakes).

    Returns the manifest dict (also written to MANIFEST_FILENAME):
    per-tile status (cached / pulled / error / truncated), parcel
    totals after merge, and a ``stopped`` flag when the server sent 429.
    The merged file is written only when at least one tile holds data.
    """
    os.makedirs(cache_dir, exist_ok=True)
    # Resolved raw files accumulate in cached_paths for the merge below.
    queue: List[BBox] = plan_tiles(bbox)
    tiles: List[dict] = []
    cached_paths: List[str] = []
    stopped = False
    pulled = 0
    while queue:
        tile = queue.pop(0)
        path = _tile_path(cache_dir, tile)
        if _fresh(path, ttl_s):
            tiles.append({"bbox": tile, "status": "cached", "features": None})
            cached_paths.append(path)
            continue
        sleeper(PARCEL_PACE_S)
        body = fetcher(tile_url(tile))
        if body is STOP:
            tiles.append({"bbox": tile, "status": "stopped", "features": None})
            stopped = True
            break
        if not isinstance(body, (bytes, bytearray)) or not valid_tile_body(bytes(body)):
            tiles.append({"bbox": tile, "status": "error", "features": None})
            continue
        n = count_features(bytes(body))
        assert n is not None
        w = tile[2] - tile[0]
        h = tile[3] - tile[1]
        if n >= COUNT_PER_TILE and min(w, h) > MIN_TILE_DEG:
            queue.extend(subdivide(tile))
            tiles.append({"bbox": tile, "status": "subdivided", "features": n})
            continue
        with open(path, "wb") as fh:
            fh.write(bytes(body))
        pulled += 1
        cached_paths.append(path)
        tiles.append({"bbox": tile, "status": "pulled", "features": n,
                      "truncated": bool(n >= COUNT_PER_TILE)})
    manifest = {
        "provenance": ("Maa-amet WFS %s bbox-tiled Tallinn harvest "
                       "(issue #520; polite: count<=%d, paced>=%ds, "
                       "429=stop)" % (PARCEL_TYPENAME, COUNT_PER_TILE,
                                      PARCEL_PACE_S)),
        "wfs": WFS_BASE,
        "typename": PARCEL_TYPENAME,
        "bbox": list(bbox),
        "stopped": stopped,
        "tiles_planned": len(plan_tiles(bbox)),
        "tiles": tiles,
        "pulled": pulled,
    }
    docs = []
    for p in cached_paths:
        try:
            with open(p, encoding="utf-8") as fh:
                docs.append(json.load(fh))
        except (OSError, ValueError):
            continue
    merged, stats = merge_features(docs)
    manifest["merge"] = stats
    if merged:
        with open(os.path.join(cache_dir, MERGED_FILENAME), "w",
                  encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": merged}, fh,
                      ensure_ascii=False)
    with open(os.path.join(cache_dir, MANIFEST_FILENAME), "w",
              encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print("tiles=%d pulled=%d parcels=%d stopped=%s -> %s"
          % (len(tiles), pulled, stats["parcels"], stopped, cache_dir))
    return manifest


def merge_only(cache_dir: str) -> dict:
    """Offline rebuild of the merged file from cached tiles (no network)."""
    import glob
    docs = []
    for path in sorted(glob.glob(os.path.join(cache_dir, TILE_GLOB))):
        try:
            with open(path, encoding="utf-8") as fh:
                docs.append(json.load(fh))
        except (OSError, ValueError):
            continue
    merged, stats = merge_features(docs)
    if merged:
        with open(os.path.join(cache_dir, MERGED_FILENAME), "w",
                  encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": merged}, fh,
                      ensure_ascii=False)
    print("tiles=%d parcels=%d duplicates=%d untunnused=%d"
          % (len(docs), stats["parcels"], stats["duplicates"],
             stats["untunnused"]))
    return stats


def probe(fetcher: Callable[[str], object] = _fetch) -> dict:
    """One tiny GET (count=1, Kesklinn window): validate the URL shape.

    Returns observed bytes / content sniff / feature count — the
    maintainer runs this before a full harvest; a changed shape here
    means STOP, not a blind city-wide run.
    """
    window = [24.74, 59.428, 24.76, 59.438]
    url = tile_url(window, count=1)
    body = fetcher(url)
    if body is STOP:
        return {"url": url, "observed": "HTTP-429-STOP"}
    if not isinstance(body, (bytes, bytearray)):
        return {"url": url, "observed": "no-200"}
    payload = bytes(body)
    return {"url": url, "bytes": len(payload),
            "features": count_features(payload),
            "valid": valid_tile_body(payload)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--probe", action="store_true",
                    help="single count=1 GET to validate the URL shape")
    ap.add_argument("--merge-only", action="store_true",
                    help="offline merged rebuild from cached tiles")
    args = ap.parse_args(argv)
    if args.probe or not args.cache_dir:
        print(json.dumps(probe(), ensure_ascii=False, indent=2))
        return 0
    if args.merge_only:
        merge_only(args.cache_dir)
        return 0
    m = harvest(args.cache_dir)
    return 1 if m["stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
