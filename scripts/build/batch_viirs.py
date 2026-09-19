"""VIIRS Black Marble brightness-proxy sidecar builder (issue #719).

Follow-up of the POSITIVE probe #699 (docs/probe_viirs.md,
services/scoring/probe_viirs.py): NASA GIBS serves keyless
VIIRS_Black_Marble PNG tiles (annual composite, vintage 2016 per
the WMTS caps Time dimension, default 2016-01-01). EOG direct
downloads stay login-walled (keyful) and are never touched — NO
credential workarounds, out of scope by design.

Pole-native per AGENTS.md section 9: the repo holds this code plus
hermetic tests; cadence, caches and the built grid live on the pole
(annual rebuild). Raw PNGs are /tmp- or cache-only, never
committed.

BRIGHTNESS PROXY (load-bearing honesty): GIBS serves visualization
PNGs, NOT numeric radiance — per-pixel means are a brightness
proxy, never radiometry. Every consumer (dims_viirs.py,
layers_p4_viirs.ts, docs) labels it as such; the user-visible
limitation (2016 annual composite + proxy, not measurement) is
required, not optional.

METHOD: the Tallinn metro bbox sits inside ONE z8 tile
(GoogleMapsCompatible_Level8 tops at z8 — no deeper tiles exist),
so the builder crops the bbox from the needed z8 tile(s) and
aggregates block means (default 12x8 ≈ 2.75 km cells — city-glow
gradient scale, never street-level). Nearest-pixel sampling only:
no resampling, no smoothing, no interpolation.

POLITENESS: UA home-finder-research/0.1, 30 s timeout, retry ONCE
on transient errors max (the caps round showed one transient
timeout then 200 — probe_viirs.md), HTTP 429 = stop (nothing
cached, build aborts), paced 2 s between tiles, tiny annual
budgets (1 tile for Tallinn). Transport errors never cached.

Usage:
  python3 scripts/build/batch_viirs.py --pull --build \\
      --cache-dir DIR --out grid.json [--bbox MINLON,MINLAT,MAXLON,MAXLAT]
"""

import argparse
import json
import math
import os
import struct
import sys
import time
import urllib.request
import zlib
from typing import Any, Dict, List, Optional, Tuple

#: Keyless GIBS tile template (WMTS ResourceURL, verified live
#: 2026-09-19: z8 y75 x145 over Tallinn -> 200, 55 KB PNG).
TILE_URL = ("https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
            "VIIRS_Black_Marble/default/default/"
            "GoogleMapsCompatible_Level8/{z}/{y}/{x}.png")

#: Composite vintage pinned from the caps Time dimension
#: (2012 + 2016 annuals, default 2016-01-01).
VINTAGE = "2016"

#: Default Tallinn metro crop (sits inside z8 tile (75, 145)).
BBOX_DEFAULT = (24.45, 59.32, 25.05, 59.52)

#: Default block grid over the crop (city-glow gradient scale).
COLS_DEFAULT = 12
ROWS_DEFAULT = 8

#: Identifying user agent for the polite pull.
UA = "home-finder-research/0.1"

#: Seconds between tile GETs.
PACE_S = 2.0

#: Minimum plausible tile body.
MIN_BYTES = 1024

#: Brightness-proxy ladder (tile-mean 0..255 -> darkness band).
#: Dark bog (~12) reads 90, saturated centre (255) reads 10.
#: PROXY, never radiometry (see header).
BRIGHTNESS_BANDS = (90, 70, 50, 30, 10)


def brightness_band(mean: Optional[float]) -> Optional[int]:
    """Tile/block mean -> darkness band. Pure (proxy ladder)."""
    if not isinstance(mean, (int, float)) or mean < 0:
        return None
    if mean <= 15:
        return 90
    if mean <= 40:
        return 70
    if mean <= 100:
        return 50
    if mean <= 180:
        return 30
    return 10


def lonlat_of_pixel(z: int, x: int, y: int, w: int, h: int,
                    px: int, py: int) -> Tuple[float, float]:
    """Centre of a tile pixel in WGS84. Pure (web-mercator)."""
    n = 2.0 ** z
    lon = (x + (px + 0.5) / w) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(
        math.pi * (1 - 2 * (y + (py + 0.5) / h) / n))))
    return lat, lon


def tile_xy(z: int, lat: float, lon: float) -> Tuple[int, int]:
    """WGS84 -> tile coords. Pure."""
    n = 2.0 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def tile_range_for_bbox(z: int, bbox: Tuple[float, float, float, float]
                        ) -> List[Tuple[int, int, int]]:
    """Tiles covering a bbox (minlon, minlat, maxlon, maxlat). Pure."""
    minlon, minlat, maxlon, maxlat = bbox
    x0, y0 = tile_xy(z, maxlat, minlon)
    x1, y1 = tile_xy(z, minlat, maxlon)
    return [(z, x, y) for x in range(min(x0, x1), max(x0, x1) + 1)
            for y in range(min(y0, y1), max(y0, y1) + 1)]


def decode_png_means(body: bytes) -> Tuple[int, int, List[float]]:
    """8-bit PNG body -> (w, h, per-pixel RGB/gray means). Pure stdlib.

    Handles colour types 0 (gray), 2 (RGB), 4 (gray+alpha), 6
    (RGBA) with filter types 0-4. Anything else raises ValueError
    (never a half-decoded gradient).
    """
    if body[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, w, h, ctype, bitd, idat = 8, 0, 0, 0, 0, b""
    while pos + 8 <= len(body):
        (ln,) = struct.unpack(">I", body[pos:pos + 4])
        typ = body[pos + 4:pos + 8]
        data = body[pos + 8:pos + 8 + ln]
        if len(data) < ln:
            raise ValueError("truncated PNG")
        if typ == b"IHDR":
            w, h, bitd, ctype = struct.unpack(">IIBB", data[:10])
        elif typ == b"IDAT":
            idat += data
        elif typ == b"IEND":
            break
        pos += 12 + ln
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
    if not w or not h or bitd != 8 or channels is None:
        raise ValueError("unsupported PNG (need 8-bit gray/RGB)")
    try:
        raw = zlib.decompress(idat)
    except zlib.error as exc:
        raise ValueError("bad IDAT") from exc
    stride = w * channels
    means: List[float] = []
    prev = bytearray(stride)
    p = 0
    for _ in range(h):
        if p >= len(raw):
            raise ValueError("short scanlines")
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if len(line) < stride:
            raise ValueError("short scanline")
        if f == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        elif f != 0:
            raise ValueError("unknown filter %d" % f)
        for i in range(0, stride, channels):
            if channels >= 3:
                means.append((line[i] + line[i + 1] + line[i + 2]) / 3.0)
            else:
                means.append(float(line[i]))
        prev = line
    return w, h, means


def fetch_tile(z: int, x: int, y: int, cache_dir: str) -> Optional[str]:
    """Polite keyless fetch of one GIBS tile. Path or None.

    30 s timeout, retry ONCE on transient errors max; HTTP 429 is a
    stop signal (nothing stored). Transport errors never cached.
    Scorers never call this.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, "viirs_%d_%d_%d.png" % (z, y, x))
    if os.path.exists(dest) and os.path.getsize(dest) >= MIN_BYTES:
        return dest
    url = TILE_URL.format(z=z, y=y, x=x)
    last: Optional[Exception] = None
    for _ in range(2):  # initial + exactly one retry
        try:
            req = urllib.request.Request(
                url, method="GET",
                headers={"User-Agent": UA, "Accept": "image/png"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if getattr(resp, "status", 200) != 200:
                    return None  # 429 and friends: stop, cache nothing
                body = resp.read()
            if len(body) < MIN_BYTES:
                return None
            decode_png_means(body)  # validate before caching
            with open(dest, "wb") as fh:
                fh.write(body)
            return dest
        except Exception as exc:  # noqa: BLE001 — politeness boundary
            last = exc
            time.sleep(PACE_S)
    return None


def build_grid(tiles: Dict[Tuple[int, int, int], Tuple[int, int, List[float]]],
               bbox: Tuple[float, float, float, float],
               cols: int, rows: int) -> List[dict]:
    """Decoded tiles -> block-mean cells over the bbox. Pure.

    Nearest-pixel sampling only: each pixel lands in exactly one
    block; blocks with zero pixels are dropped (never interpolated).
    Cells carry centroid lat/lon + mean brightness.
    """
    minlon, minlat, maxlon, maxlat = bbox
    sums = [[0.0] * cols for _ in range(rows)]
    counts = [[0] * cols for _ in range(rows)]
    for (z, x, y), (w, h, means) in tiles.items():
        for py in range(h):
            for px in range(w):
                lat, lon = lonlat_of_pixel(z, x, y, w, h, px, py)
                if not (minlon <= lon <= maxlon
                        and minlat <= lat <= maxlat):
                    continue
                col = min(cols - 1, int((lon - minlon)
                                       / (maxlon - minlon) * cols))
                row = min(rows - 1, int((maxlat - lat)
                                       / (maxlat - minlat) * rows))
                sums[row][col] += means[py * w + px]
                counts[row][col] += 1
    cells = []
    for r in range(rows):
        for c in range(cols):
            if not counts[r][c]:
                continue
            cells.append({
                "lat": maxlat - (r + 0.5) / rows * (maxlat - minlat),
                "lon": minlon + (c + 0.5) / cols * (maxlon - minlon),
                "mean": round(sums[r][c] / counts[r][c], 1),
            })
    cells.sort(key=lambda cell: (cell["lat"], cell["lon"]))
    return cells


def _parse_bbox(text: str) -> Tuple[float, float, float, float]:
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox needs 4 numbers")
    return parts[0], parts[1], parts[2], parts[3]


def _load_tile(path: str) -> Optional[Tuple[int, int, List[float]]]:
    try:
        with open(path, "rb") as fh:
            return decode_png_means(fh.read())
    except (OSError, ValueError):
        return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="VIIRS brightness sidecar.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out", default=None,
                    help="Grid JSON destination (pole built/ path).")
    ap.add_argument("--bbox", default=",".join(str(v) for v in BBOX_DEFAULT))
    ap.add_argument("--cols", type=int, default=COLS_DEFAULT)
    ap.add_argument("--rows", type=int, default=ROWS_DEFAULT)
    ap.add_argument("--zoom", type=int, default=8,
                    help="GIBS matrix tops at z8 (no deeper tiles).")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True
    try:
        bbox = _parse_bbox(args.bbox)
    except ValueError:
        print("error: vigane --bbox (oodatud MINLON,MINLAT,MAXLON,MAXLAT).",
              file=sys.stderr)
        return 2

    if args.zoom > 8:
        print("error: keeldun - GIBS GoogleMapsCompatible_Level8 "
              "lõpeb z8-ga (sügavamaid plaate pole); ära feigi "
              "resolutsiooni.", file=sys.stderr)
        return 2

    needed = tile_range_for_bbox(args.zoom, bbox)
    if args.pull:
        for i, (z, x, y) in enumerate(needed):
            if i:
                time.sleep(PACE_S)
            if fetch_tile(z, x, y, args.cache_dir) is None:
                print("error: plaadi %d/%d/%d päring ebaõnnestus või "
                      "jäi vahele (transport/viga või 429-stopp) - "
                      "midagi uut ei puhvritatud." % (z, y, x),
                      file=sys.stderr)
                return 1
        print("ok: %d VIIRS-plaati puhvritatud (%s)"
              % (len(needed), args.cache_dir))
    if args.build:
        tiles: Dict[Any, Any] = {}
        for (z, x, y) in needed:
            path = os.path.join(args.cache_dir,
                                "viirs_%d_%d_%d.png" % (z, y, x))
            decoded = _load_tile(path)
            if decoded is None:
                print("error: puhvritatud plaati %d/%d/%d pole - "
                      "käivita --pull." % (z, y, x), file=sys.stderr)
                return 1
            tiles[(z, x, y)] = decoded
        cells = build_grid(tiles, bbox, args.cols, args.rows)
        grid = {"vintage": VINTAGE,
                "source": "NASA GIBS VIIRS_Black_Marble annual "
                          "composite (best/default) — BRIGHTNESS PROXY, "
                          "mitte radiomeetria",
                "bbox": list(bbox),
                "cells": cells,
                "counts": {"total": len(cells)}}
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(grid, fh, ensure_ascii=False)
        print(json.dumps(grid["counts"], ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
