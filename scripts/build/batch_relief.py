"""Relief tint-grid sidecar builder (issue #619): cached WCS DTM GeoTIFF -> map grid.

Stdlib only. Offline, snapshot-only (NO network): the Maa-amet DTM WCS
pull is a polite one-off harvest (custom UA, single GetCapabilities +
single DescribeCoverage + one small Saku probe + ONE Harjumaa
GetCoverage at 1000x570, 429 stops the run — see docs/p4_relief.md);
this builder converts the already-cached county GeoTIFF
(float32 EH2000 heights, EPSG:4326 window lon 23.3-25.5 lat 58.4-59.65
resampled server-side by WCS) into the map sidecar
``<snap>/relief/relief-tint.json`` consumed by
/api/layers/relief/areas. Pure logic at module top so unit tests stay
hermetic; the sidecar write runs only via the documented rebuild
command.

SCOPE: hypsometric CHARACTER tint, never a score field — relief is
scenery, not good/bad (flatness is taste-dependent: a cyclist's green
is a view-seeker's red). Heights are stored verbatim as decimetre
int16 (NaN/out-of-range stay missing, rendered transparent); the
client paints a fixed hypsometric LUT with a taste-only legend
("maitse, mitte hinne"). Sea cells read 0.0 in the DTM: they tint as
lowland (honest — the DTM does not mark water, and we never invent a
watermask).

HONESTY (load-bearing): cells outside [-50, 500] m or NaN are MISSING
(never faked, never clamped into the tint); a missing input file
writes NOTHING and reports ok=False (unknown, never a partial grid
presented as complete). Grid geometry (cols/rows/bbox) is stamped from
the TIFF tags, never assumed.

Rebuild: python3 scripts/build/batch_relief.py \\
    --tif /tmp/hf-619-cache/harjumaa-dtm10.tif \\
    --snap ~/hf-data/2026-09-12
"""

import argparse
import base64
import json
import math
import os
import struct
import sys
from array import array
from typing import Dict, List, Optional, Tuple

#: Sidecar filename inside the snapshot dir.
SIDECAR_PATH = os.path.join("relief", "relief-tint.json")

#: Publisher attribution (CC BY 4.0 — stamped in stats, not rows).
ATTRIBUTION = "Maa-ameti DTM (CC BY 4.0, dtm-10)"

#: Plausible EH2000 height range for Harjumaa (m). Outside -> missing.
H_MIN = -50.0
H_MAX = 500.0


def _u16(d: bytes, o: int) -> int:
    return struct.unpack("<H", d[o : o + 2])[0]


def _u32(d: bytes, o: int) -> int:
    return struct.unpack("<I", d[o : o + 4])[0]


def read_float32_grid(path: str) -> Tuple[int, int, array]:
    """Read a single-band float32 TIFF into (cols, rows, values).

    Raises ValueError on anything unexpected (never guessed): the
    harvest contract is uncompressed single-strip-or-multi-strip
    float32, and anything else is a loud failure, not a silent
    misread.
    """
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:2] != b"II" or _u16(d, 2) != 42:
        raise ValueError("not a little-endian TIFF")
    off = _u32(d, 4)
    n = _u16(d, off)
    info = {}
    for i in range(n):
        t = d[off + 2 + i * 12 : off + 2 + (i + 1) * 12]
        tag, typ, cnt, val = struct.unpack("<HHI4s", t)
        info[tag] = (typ, cnt, _u32(d, off + 2 + i * 12 + 8))
    width = info[256][2]
    height = info[257][2]
    if info[258][2] != 32 or info[259][2] != 1 or info[339][2] != 3:
        raise ValueError("need uncompressed 32-bit float samples")
    nstrip = info[273][1]
    if nstrip == 1:
        # Single strip: the offset is inline in the tag value itself.
        offs = (info[273][2],)
    else:
        o_off = info[273][2]
        offs = struct.unpack("<%dI" % nstrip, d[o_off : o_off + 4 * nstrip])
    rps_tag = info.get(278)
    rps = rps_tag[2] if rps_tag else height
    grid: array = array("f")
    for k, o in enumerate(offs):
        rows_here = min(rps, height - k * rps)
        grid.frombytes(d[o : o + width * rows_here * 4])
    if len(grid) != width * height:
        raise ValueError("strip layout does not cover the grid")
    return width, height, grid


def quantize_dm(grid: array) -> Tuple[List[int], int]:
    """Quantize heights to decimetres; missing -> -32768. Returns
    (values, missing_count). NaN and out-of-range stay missing: the
    tint renders them transparent, never as lowland."""
    out: List[int] = []
    missing = 0
    for z in grid:
        if z != z or not (H_MIN <= z <= H_MAX):
            out.append(-32768)
            missing += 1
        else:
            out.append(int(round(z * 10)))
    return out, missing


def grid_stats(grid: array) -> Dict[str, float]:
    """Honest histogram over valid cells only (for the docs table)."""
    zs = sorted(z for z in grid if z == z and H_MIN <= z <= H_MAX)
    if not zs:
        return {"n": 0}
    def q(p: float) -> float:
        return zs[int(p * (len(zs) - 1))]
    return {
        "n": len(zs),
        "min": zs[0],
        "p1": q(0.01),
        "p5": q(0.05),
        "p25": q(0.25),
        "p50": q(0.50),
        "p75": q(0.75),
        "p95": q(0.95),
        "p99": q(0.99),
        "max": zs[-1],
    }


def build_sidecar(
    cols: int,
    rows: int,
    bbox: Tuple[float, float, float, float],
    grid: array,
    vintage: str,
) -> Dict:
    """Assemble the sidecar doc (JSON-serializable)."""
    qvals, missing = quantize_dm(grid)
    raw = struct.pack("<%dh" % len(qvals), *qvals)
    return {
        "vintage": vintage,
        "source": ATTRIBUTION,
        "cols": cols,
        "rows": rows,
        "bbox": {
            "minlon": bbox[0],
            "minlat": bbox[1],
            "maxlon": bbox[2],
            "maxlat": bbox[3],
        },
        "unit": "dm",
        "encoding": "base64-int16-le",
        "missing_sentinel": -32768,
        "missing": missing,
        "stats": grid_stats(grid),
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
    ap = argparse.ArgumentParser(description="Build the relief tint-grid sidecar.")
    ap.add_argument("--tif", required=True, help="Cached WCS DTM GeoTIFF.")
    ap.add_argument("--snap", required=True, help="Snapshot dir.")
    ap.add_argument("--vintage", default="2026-09-17", help="Harvest date.")
    ap.add_argument(
        "--bbox",
        default="23.3,58.4,25.5,59.65",
        help="minlon,minlat,maxlon,maxlat of the WCS window.",
    )
    args = ap.parse_args(argv)
    if not os.path.exists(args.tif):
        print("missing input %s: wrote NOTHING (unknown, never partial)" % args.tif)
        return 1
    try:
        cols, rows, grid = read_float32_grid(args.tif)
    except (ValueError, struct.error, OSError) as exc:
        print("unreadable input %s (%s): wrote NOTHING" % (args.tif, exc))
        return 1
    bbox = tuple(float(v) for v in args.bbox.split(","))
    doc = build_sidecar(cols, rows, bbox, grid, args.vintage)
    dest = write_sidecar(args.snap, doc)
    print(
        "ok=True %s cols=%d rows=%d missing=%d p50=%.1f max=%.1f"
        % (dest, cols, rows, doc["missing"], doc["stats"].get("p50", float("nan")), doc["stats"].get("max", float("nan")))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
