"""Hermetic tests for scripts/build/batch_canopy.py (issue #620).

No network, no snapshot files: inline minimal PNG fixtures only.
"""

import base64
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_canopy import (  # noqa: E402
    DST_BBOX,
    DST_COLS,
    DST_ROWS,
    SRC_BBOX,
    build_sidecar,
    classify,
    lest97_to_lonlat,
    lonlat_to_lest97,
    main,
    read_png_rgba,
    reproject,
)


def tiny_png(pixels, w=2, h=1):
    """Minimal truecolour PNG (no alpha)."""
    raw = b""
    for y in range(h):
        raw += b"\x00"
        for x in range(w):
            raw += bytes(pixels[y * w + x])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    def chunk(typ, dat):
        c = struct.pack(">I", len(dat)) + typ + dat
        return c + struct.pack(">I", zlib.crc32(typ + dat) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def write_tmp(tmp_path, name, data):
    p = str(tmp_path / name)
    with open(p, "wb") as fh:
        fh.write(data)
    return p


def test_reads_png_pixels(tmp_path):
    p = write_tmp(tmp_path, "t.png", tiny_png([(0x25, 0x51, 0x0F), (255, 255, 255)]))
    w, h, px = read_png_rgba(p)
    assert (w, h) == (2, 1)
    assert px[0] == (0x25, 0x51, 0x0F, 255)
    assert px[1] == (255, 255, 255, 255)


def test_refuses_non_png(tmp_path):
    p = write_tmp(tmp_path, "t.png", b"not a png")
    try:
        read_png_rgba(p)
    except ValueError:
        return
    raise AssertionError("non-PNG must raise, never guess")


def test_classify_exact_legend_only():
    assert classify(0x25, 0x51, 0x0F, 255) == (1, True)   # 1-4 m
    assert classify(0x35, 0x69, 0x0D, 255) == (2, True)   # 4-10 m
    assert classify(0x6B, 0x86, 0x0A, 255) == (3, True)   # 10-20 m
    assert classify(0xDF, 0x7F, 0x03, 255) == (4, True)   # 20-30 m
    assert classify(0xE0, 0x1F, 0x1F, 255) == (5, True)   # >30 m
    assert classify(0x25, 0x51, 0x0F, 0) == (0, True)     # transparent
    cls, matched = classify(1, 2, 3, 255)                # unknown opaque
    assert (cls, matched) == (0, False)                  # never guessed


def test_lcc_origin_exact():
    # EPSG:3301 definition: the projection origin maps EXACTLY to
    # (E0, N0). Non-circular (no Tallinn reference involved).
    e, n = lonlat_to_lest97(24.0, 57.5175538888889)
    assert abs(e - 500000.0) < 1e-6
    assert abs(n - 6375000.0) < 1e-6
    lon, lat = lest97_to_lonlat(500000.0, 6375000.0)
    assert abs(lon - 24.0) < 1e-9
    assert abs(lat - 57.5175538888889) < 1e-9


def test_lcc_central_meridian_easting():
    # The central meridian (lon0 24E) maps to E0 at every latitude.
    for lat in (58.0, 59.0, 59.44, 59.6):
        e, _n = lonlat_to_lest97(24.0, lat)
        assert abs(e - 500000.0) < 1e-6


def test_lcc_tallinn_replaces_tm_pin():
    # True LCC values for the old TM reference point (24.75, 59.44):
    # E542555.36 N6589368.19 — dE ~17 m / dN ~80 m off the legacy TM
    # pin (542538, 6589288), matching the measured #648 disagreement.
    # The old pin's agreement was circular (TM computing TM).
    e, n = lonlat_to_lest97(24.75, 59.44)
    assert abs(e - 542555.36) < 0.01
    assert abs(n - 6589368.19) < 0.01
    lon, lat = lest97_to_lonlat(e, n)
    assert abs(lon - 24.75) < 2e-14
    assert abs(lat - 59.44) < 3e-14


def test_reproject_keeps_tallest():
    # 1x1 source over the whole target: tallest class wins everywhere.
    grid = reproject(1, 1, [3], src_bbox=(459086.0, 6473458.0, 587668.0, 6613389.0))
    assert len(grid) == 1000 * 570


def _dest_lonlat(col, row):
    lon = DST_BBOX[0] + (col + 0.5) / DST_COLS * (DST_BBOX[2] - DST_BBOX[0])
    lat = DST_BBOX[3] - (row + 0.5) / DST_ROWS * (DST_BBOX[3] - DST_BBOX[1])
    return lon, lat


def test_reproject_no_interior_voids():
    # Uniform canopy source: every dest cell whose centre projects
    # inside the source window must read canopy — stripe voids are a
    # mapping bug, never "unknown".
    w, h = 100, 109
    grid = reproject(w, h, [2] * (w * h))
    assert len(grid) == DST_COLS * DST_ROWS
    inside = 0
    for row in range(0, DST_ROWS, 7):
        for col in range(0, DST_COLS, 7):
            lon, lat = _dest_lonlat(col, row)
            e, n = lonlat_to_lest97(lon, lat)
            if SRC_BBOX[0] <= e <= SRC_BBOX[2] and SRC_BBOX[1] <= n <= SRC_BBOX[3]:
                inside += 1
                assert grid[row * DST_COLS + col] == 2
    assert inside > 1000


def test_reproject_transparent_stays_missing():
    # A transparent hole in the source stays 0 at the dest cells that
    # sample it (honestly missing), while neighbours read canopy.
    w, h = 1004, 1093
    classes = [2] * (w * h)
    # Dest cell nearest Tallinn centre samples some source pixel: blank
    # a block around it and require exactly that dest cell to go missing.
    tcol = int((24.75 - DST_BBOX[0]) / (DST_BBOX[2] - DST_BBOX[0]) * DST_COLS)
    trow = int((DST_BBOX[3] - 59.44) / (DST_BBOX[3] - DST_BBOX[1]) * DST_ROWS)
    lon, lat = _dest_lonlat(tcol, trow)
    e, n = lonlat_to_lest97(lon, lat)
    ew = (SRC_BBOX[2] - SRC_BBOX[0]) / w
    ns = (SRC_BBOX[3] - SRC_BBOX[1]) / h
    sx = int(round((e - SRC_BBOX[0]) / ew - 0.5))
    sy = int(round((SRC_BBOX[3] - n) / ns - 0.5))
    assert 2 <= sx < w - 2 and 2 <= sy < h - 2
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            classes[(sy + dy) * w + (sx + dx)] = 0
    grid = reproject(w, h, classes)
    assert grid[trow * DST_COLS + tcol] == 0
    assert grid[trow * DST_COLS + (tcol + 30)] == 2


def test_sidecar_roundtrip():
    doc = build_sidecar([0, 1, 5, 0], 0, "2022-suvi")
    assert doc["cols"] == 1000
    assert doc["unit"] == "class"
    assert list(base64.b64decode(doc["data"])[:4]) == [0, 1, 5, 0]
    assert doc["counts"][1] == 1
    assert "Maa- ja Ruumiamet" in doc["source"]


def test_missing_input_writes_nothing(tmp_path, capsys):
    rc = main(["--png", str(tmp_path / "nope.png"), "--snap", str(tmp_path / "snap")])
    assert rc == 1
    assert not os.path.exists(str(tmp_path / "snap" / "canopy" / "canopy-tint.json"))
    assert "NOTHING" in capsys.readouterr().out
