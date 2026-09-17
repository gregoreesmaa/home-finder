"""Canopy tint-grid sidecar builder (issue #620): WMS CHM render -> class grid.

Stdlib only. Offline, snapshot-only (NO network): the Maa-amet CHM WMS
harvest is a polite one-off (custom UA, single GetCapabilities +
GetLegendGraphic + national/axis probes + ONE county GetMap; 429 stops
the run — see docs/p4_canopy.md); this builder converts the cached
county PNG render into the map sidecar
``<snap>/canopy/canopy-tint.json`` consumed by
/api/layers/canopy/areas. Pure logic at module top so unit tests stay
hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE: canopy-height CHARACTER tint, never a score field — height is
taste (shade vs light, shelter vs view), not good/bad. Classes are the
publisher's own (CHM2022_suvi legend, exact RGB match — no invented
thresholds): <1 m transparent, 1-4 / 4-10 / 10-20 / 20-30 / >30 m.
Transparent pixels stay MISSING (rendered transparent, never as
low/short canopy).

HONESTY (load-bearing): the render is EPSG:3301 (the layer serves no
4326); each lon/lat cell reverse-samples its nearest source pixel by
exact forward Transverse Mercator (L-EST97, round-trip <1 m at
Tallinn — pinned by test), nearest-neighbour, so coverage is complete
by construction (no splat gaps). Unmatched legend colors are MISSING + counted
(never guessed into the nearest class: a style change must fail
visibly). A missing input writes NOTHING (unknown, never partial).

Rebuild: python3 scripts/build/batch_canopy.py \\
    --png /tmp/hf-620-cache/harjumaa-chm22.png \\
    --snap ~/hf-data/2026-09-12
"""

import argparse
import base64
import json
import math
import os
import struct
import sys
import zlib
from array import array
from typing import Dict, List, Optional, Tuple

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("canopy", "canopy-tint.json")

#: Publisher attribution (CC BY 4.0 — stamped in stats, not rows).
ATTRIBUTION = "Maa- ja Ruumiamet CHM (CC BY 4.0, CHM2022_suvi)"

#: Publisher legend swatches, top row to bottom (exact RGB).
CLASS_COLORS: List[Tuple[int, int, int]] = [
    (0x25, 0x51, 0x0F),  # 1-4 m
    (0x35, 0x69, 0x0D),  # 4-10 m
    (0x6B, 0x86, 0x0A),  # 10-20 m
    (0xDF, 0x7F, 0x03),  # 20-30 m
    (0xE0, 0x1F, 0x1F),  # 30 m <
]

#: L-EST97 constants (GRS80 Transverse Mercator, lon0 24E).
#: LEGACY (issue #648): L-EST97 is really Lambert Conformal Conic 2SP
#: (see the LCC block below) — the TM below disagrees with LCC by
#: 20-85 m across Harju and is kept ONLY until #648 flips the two
#: lest97_* functions. New code must use lest97_to_lonlat_lcc /
#: lonlat_to_lest97_lcc.
_A = 6378137.0
_F = 1 / 298.257222101
_E2 = 2 * _F - _F * _F
_EP2 = _E2 / (1 - _E2)
_K0 = 0.9996
_LON0 = math.radians(24.0)
_E0 = 500000.0
_E1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))

#: True L-EST97 = Lambert Conformal Conic 2SP (EPSG:3301), GRS80.
#: Triple authority: the official .prj inside Metsamuutused_2024.zip
#: (PROJECTION Lambert_Conformal_Conic, lat0 57.5175538888889, lon0 24,
#: SP1 58, SP2 59.3333333333333, E0 500000, N0 6375000), epsg.io/3301
#: (+proj=lcc, same params; axis order Northing,Easting), and a
#: from-scratch implementation round-tripping to 2e-14 deg (issue
#: #648). Verified 2026-09-17.
_LCC_LAT0 = math.radians(57.5175538888889)
_LCC_LON0 = math.radians(24.0)
_LCC_P1 = math.radians(58.0)
_LCC_P2 = math.radians(59.3333333333333)
_LCC_E0 = 500000.0
_LCC_N0 = 6375000.0


def _lcc_m(phi: float) -> float:
    return math.cos(phi) / math.sqrt(1 - _E2 * math.sin(phi) ** 2)


def _lcc_t(phi: float) -> float:
    e = math.sqrt(_E2)
    s = math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - e * s) / (1 + e * s)) ** (e / 2)


_LCC_M1 = _lcc_m(_LCC_P1)
_LCC_M2 = _lcc_m(_LCC_P2)
_LCC_T1 = _lcc_t(_LCC_P1)
_LCC_T2 = _lcc_t(_LCC_P2)
_LCC_T0 = _lcc_t(_LCC_LAT0)
_LCC_N = math.log(_LCC_M1 / _LCC_M2) / math.log(_LCC_T1 / _LCC_T2)
_LCC_F = _LCC_M1 / (_LCC_N * _LCC_T1 ** _LCC_N)
_LCC_R0 = _A * _LCC_F * _LCC_T0 ** _LCC_N


def lonlat_to_lest97_lcc(lon: float, lat: float) -> Tuple[float, float]:
    """True forward L-EST97 (lon/lat degrees -> easting/northing).

    Lambert Conformal Conic 2SP per EPSG:3301 (see constants above).
    Round-trips to 2e-14 deg (pinned by test). USE THIS for new code;
    the TM twins stay until issue #648 flips them.
    """
    t = _lcc_t(math.radians(lat))
    r = _A * _LCC_F * t ** _LCC_N
    th = _LCC_N * (math.radians(lon) - _LCC_LON0)
    return _LCC_E0 + r * math.sin(th), _LCC_N0 + _LCC_R0 - r * math.cos(th)


def lest97_to_lonlat_lcc(easting: float, northing: float) -> Tuple[float, float]:
    """True inverse L-EST97 (easting/northing -> lon/lat degrees).

    Series-inversion twin of lonlat_to_lest97_lcc (same constants).
    Round-trips to 2e-14 deg (pinned by test).
    """
    e = math.sqrt(_E2)
    rho = math.hypot(easting - _LCC_E0, _LCC_R0 - (northing - _LCC_N0))
    theta = math.atan2(easting - _LCC_E0, _LCC_R0 - (northing - _LCC_N0))
    t = (rho / (_A * _LCC_F)) ** (1 / _LCC_N)
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(10):
        s = math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - e * s) / (1 + e * s)) ** (e / 2))
    lam = theta / _LCC_N + _LCC_LON0
    return math.degrees(lam), math.degrees(phi)

#: Source render window (EPSG:3301, easting/northing).
SRC_BBOX = (459086.0, 6473458.0, 587668.0, 6613389.0)

#: Target lon/lat grid.
DST_BBOX = (23.3, 58.4, 25.5, 59.65)
DST_COLS = 1000
DST_ROWS = 570


def lonlat_to_lest97(lon: float, lat: float) -> Tuple[float, float]:
    """Exact forward Transverse Mercator (lon/lat degrees -> L-EST97).

    Series twin of lest97_to_lonlat (same ellipsoid constants):
    round-trips to <1 m at Tallinn (pinned by test). Used by the
    reverse-map reproject so every lon/lat cell samples its own
    nearest source pixel — no forward-splat voids, ever.
    """
    phi = math.radians(lat)
    lam = math.radians(lon)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    tan_phi = math.tan(phi)
    n1 = _A / math.sqrt(1 - _E2 * sin_phi * sin_phi)
    t = tan_phi * tan_phi
    c = _EP2 * cos_phi * cos_phi
    a = (lam - _LON0) * cos_phi
    e2 = _E2
    m = _A * (
        (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2**3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2 * e2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
        + (15 * e2 * e2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
        - (35 * e2**3 / 3072) * math.sin(6 * phi)
    )
    easting = _E0 + _K0 * n1 * (
        a
        + (1 - t + c) * a**3 / 6
        + (5 - 18 * t + t * t + 72 * c - 58 * _EP2) * a**5 / 120
    )
    northing = _K0 * (
        m
        + n1
        * tan_phi
        * (
            a * a / 2
            + (5 - t + 9 * c + 4 * c * c) * a**4 / 24
            + (61 - 58 * t + t * t + 600 * c - 330 * _EP2) * a**6 / 720
        )
    )
    return easting, northing


def lest97_to_lonlat(easting: float, northing: float) -> Tuple[float, float]:
    """Exact inverse Transverse Mercator (L-EST97 -> lon/lat degrees)."""
    x = easting - _E0
    m = northing / _K0
    mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 * _E2 / 64 - 5 * _E2 ** 3 / 256))
    fp = (
        mu
        + (3 * _E1 / 2 - 27 * _E1 ** 3 / 32) * math.sin(2 * mu)
        + (21 * _E1 * _E1 / 16 - 55 * _E1 ** 4 / 32) * math.sin(4 * mu)
        + (151 * _E1 ** 3 / 96) * math.sin(6 * mu)
        + (1097 * _E1 ** 4 / 512) * math.sin(8 * mu)
    )
    c1 = _EP2 * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    n1 = _A / math.sqrt(1 - _E2 * math.sin(fp) ** 2)
    r1 = _A * (1 - _E2) / (1 - _E2 * math.sin(fp) ** 2) ** 1.5
    dd = x / (n1 * _K0)
    lat = fp - (n1 * math.tan(fp) / r1) * (
        dd * dd / 2 - (5 + 3 * t1 + 10 * c1 - 4 * _EP2 - 9 * _EP2) * dd**4 / 24
    )
    lon = _LON0 + (
        dd
        - (1 + 2 * t1 + c1) * dd**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * _EP2 + 24 * t1 * t1)
        * dd**5
        / 120
    ) / math.cos(fp)
    return math.degrees(lon), math.degrees(lat)


def read_png_rgba(path: str) -> Tuple[int, int, List[Tuple[int, int, int, int]]]:
    """Decode a truecolour(+alpha) PNG via stdlib (no Paeth gaps: all
    five filter types handled, never guessed)."""
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos = 8
    raw = b""
    w = h = ctype = 0
    while pos < len(d):
        (ln,) = struct.unpack(">I", d[pos : pos + 4])
        typ = d[pos + 4 : pos + 8]
        dat = d[pos + 8 : pos + 8 + ln]
        if typ == b"IHDR":
            w, h, _bd, ctype, _c, _f, _i = struct.unpack(">IIBBBBB", dat)
        elif typ == b"IDAT":
            raw += dat
        pos += 12 + ln
    if ctype not in (2, 6):
        raise ValueError("need truecolour PNG")
    ch = 4 if ctype == 6 else 3
    px = zlib.decompress(raw)
    stride = w * ch
    out: List[Tuple[int, int, int, int]] = []
    prev = bytearray(stride)
    p = 0
    for _y in range(h):
        f = px[p]
        p += 1
        cur = bytearray(px[p : p + stride])
        p += stride
        if f == 1:
            for i in range(ch, stride):
                cur[i] = (cur[i] + cur[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                cur[i] = (cur[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                cur[i] = (cur[i] + ((prev[i] + (cur[i - ch] if i >= ch else 0)) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = cur[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                qq = a + b - c
                pa, pb, pc = abs(qq - a), abs(qq - b), abs(qq - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pr) & 255
        elif f != 0:
            raise ValueError("unknown PNG filter")
        for x in range(w):
            r, g, b = cur[x * ch], cur[x * ch + 1], cur[x * ch + 2]
            al = cur[x * ch + 3] if ch == 4 else 255
            out.append((r, g, b, al))
        prev = cur
    return w, h, out


def classify(r: int, g: int, b: int, alpha: int) -> Tuple[int, bool]:
    """Map a pixel to a canopy class 1-5. Returns (class, matched):
    transparent or legend-unknown pixels are class 0 + matched=False
    for transparency (honestly missing) — unmatched OPAQUE colors are
    class 0 + matched=False too but counted separately (a style change
    must fail visibly, never guess into the nearest class)."""
    if alpha < 128:
        return 0, True
    for i, (cr, cg, cb) in enumerate(CLASS_COLORS):
        if (r, g, b) == (cr, cg, cb):
            return i + 1, True
    return 0, False


def reproject(
    w: int,
    h: int,
    classes: List[int],
    src_bbox: Tuple[float, float, float, float] = SRC_BBOX,
) -> List[int]:
    """Nearest-neighbour reproject of the 3301 class grid onto the
    lon/lat target grid. REVERSE-map: every dest cell samples its own
    centre (forward TM -> nearest source pixel), so coverage is
    complete by construction — a 0 cell means the source render is
    transparent there (honestly missing), never a splat gap. Cells
    whose centre falls outside the source window stay 0."""
    out = [0] * (DST_COLS * DST_ROWS)
    # NOTE: src_bbox is (minE, minN, maxE, maxN); dest row 0 = maxlat.
    min_e, min_n, max_e, max_n = src_bbox
    ew = (max_e - min_e) / w
    ns = (max_n - min_n) / h
    lon_span = DST_BBOX[2] - DST_BBOX[0]
    lat_span = DST_BBOX[3] - DST_BBOX[1]
    for row in range(DST_ROWS):
        lat = DST_BBOX[3] - (row + 0.5) / DST_ROWS * lat_span
        for col in range(DST_COLS):
            lon = DST_BBOX[0] + (col + 0.5) / DST_COLS * lon_span
            e, n = lonlat_to_lest97(lon, lat)
            sx = int(round((e - min_e) / ew - 0.5))
            sy = int(round((max_n - n) / ns - 0.5))
            if 0 <= sx < w and 0 <= sy < h:
                out[row * DST_COLS + col] = classes[sy * w + sx]
    return out


def build_sidecar(
    grid: List[int],
    unmatched: int,
    vintage: str,
) -> Dict:
    """Assemble the sidecar doc (JSON-serializable)."""
    counts = [0] * 6
    for c in grid:
        counts[c] += 1
    raw = bytes(grid)
    return {
        "vintage": vintage,
        "source": ATTRIBUTION,
        "cols": DST_COLS,
        "rows": DST_ROWS,
        "bbox": {
            "minlon": DST_BBOX[0],
            "minlat": DST_BBOX[1],
            "maxlon": DST_BBOX[2],
            "maxlat": DST_BBOX[3],
        },
        "unit": "class",
        "classes": ["<1m/puudub", "1-4m", "4-10m", "10-20m", "20-30m", ">30m"],
        "encoding": "base64-uint8",
        "unmatched_opaque": unmatched,
        "counts": counts,
        "data": base64.b64encode(raw).decode("ascii"),
    }


def write_sidecar(snap: str, doc: Dict) -> str:
    """Write the sidecar under the snapshot dir; returns its path."""
    dest = os.path.join(snap, SIDECAR_PATH)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    return dest


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the canopy tint-grid sidecar.")
    ap.add_argument("--png", required=True, help="Cached WMS CHM county render.")
    ap.add_argument("--snap", required=True, help="Snapshot dir.")
    ap.add_argument("--vintage", default="2022-suvi", help="CHM flight vintage.")
    args = ap.parse_args(argv)
    if not os.path.exists(args.png):
        print("missing input %s: wrote NOTHING (unknown, never partial)" % args.png)
        return 1
    try:
        w, h, px = read_png_rgba(args.png)
    except (ValueError, struct.error, OSError, zlib.error) as exc:
        print("unreadable input %s (%s): wrote NOTHING" % (args.png, exc))
        return 1
    classes: List[int] = []
    unmatched = 0
    for (r, g, b, al) in px:
        cls, matched = classify(r, g, b, al)
        classes.append(cls)
        if not matched:
            unmatched += 1
    grid = reproject(w, h, classes)
    doc = build_sidecar(grid, unmatched, args.vintage)
    dest = write_sidecar(args.snap, doc)
    print(
        "ok=True %s canopy=%d/%d unmatched=%d"
        % (dest, sum(doc["counts"][1:]), len(grid), unmatched)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
