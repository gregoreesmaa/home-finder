"""Tests for scripts/build/batch_viirs.py (issue #719).

Hermetic: urlopen is stubbed and PNG fixtures are generated
in-test (stdlib zlib) — no network anywhere. Pins the stdlib PNG
decoder, the block-mean grid build, the polite-fetch contract
(timeout + retry-once-max, 429 = stop, nothing cached on failure),
and the brightness bands.
"""

import json
import os
import struct
import sys
import urllib.error
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_viirs import (  # noqa: E402
    BRIGHTNESS_BANDS,
    brightness_band,
    build_grid,
    decode_png_means,
    fetch_tile,
    lonlat_of_pixel,
    main,
    tile_range_for_bbox,
)


def _crc(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + chunk_type + data + _crc(chunk_type, data)


def make_png(w, h, rows):
    """Minimal 8-bit RGB non-interlaced PNG from filter-0 rows."""
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw))
            + _chunk(b"IEND", b""))


def test_decode_rgb_means():
    png = make_png(2, 1, [[255, 255, 255, 0, 0, 0]])
    w, h, means = decode_png_means(png)
    assert (w, h) == (2, 1)
    assert means == [255.0, 0.0]


def test_decode_gray_means():
    raw = b"\x00\x0b\x2d"
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 0, 0, 0, 0))
           + _chunk(b"IDAT", zlib.compress(raw))
           + _chunk(b"IEND", b""))
    w, h, means = decode_png_means(png)
    assert means == [11.0, 45.0]


def test_decode_rejects_garbage():
    try:
        decode_png_means(b"not a png")
        assert False, "must raise"
    except ValueError:
        pass


def test_pixel_georef_matches_spot_check():
    # Independent oracle: the /tmp spot-check script located Tallinn
    # centre (59.437, 24.745) at pixel (153, 35) of tile (8,145,75).
    lat, lon = lonlat_of_pixel(8, 145, 75, 256, 256, 153, 35)
    assert abs(lat - 59.437) < 0.01
    assert abs(lon - 24.745) < 0.01


def test_tile_range_covers_tallinn_bbox():
    tiles = tile_range_for_bbox(8, (24.45, 59.32, 25.05, 59.52))
    assert tiles == [(8, 145, 75)]  # single z8 tile holds the metro bbox


def test_build_grid_block_means():
    # 4x2 fake z0 world tile: 2x1 blocks split bright/dark halves.
    means = [10.0, 10.0, 200.0, 200.0,
             10.0, 10.0, 200.0, 200.0]
    cells = build_grid({(0, 0, 0): (4, 2, means)},
                       (-180.0, -85.0, 180.0, 85.0), 2, 1)
    assert len(cells) == 2
    assert cells[0]["mean"] == 10.0
    assert cells[1]["mean"] == 200.0
    for c in cells:
        assert -85.0 <= c["lat"] <= 85.0 and -180.0 <= c["lon"] <= 180.0


def test_brightness_bands():
    assert brightness_band(255.0) == 10   # saturated city glow
    assert brightness_band(11.6) == 90    # dark bog
    assert brightness_band(None) is None
    assert BRIGHTNESS_BANDS == (90, 70, 50, 30, 10)


class _Resp:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_429_is_stop_and_caches_nothing(monkeypatch, tmp_path):
    import urllib.request

    def _fake(req, timeout=30):
        return _Resp(b"{}", status=429)

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    assert fetch_tile(8, 75, 145, str(tmp_path)) is None
    assert list(tmp_path.iterdir()) == []


def test_retry_once_then_gives_up(monkeypatch, tmp_path):
    import urllib.request
    calls = []

    def _fake(req, timeout=30):
        calls.append(1)
        raise TimeoutError("slow")

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    assert fetch_tile(8, 75, 145, str(tmp_path)) is None
    assert len(calls) == 2  # initial + exactly one retry, never more


def test_main_build_from_cached_tile(tmp_path, capsys):
    # 4x1 fake tile (8,145,75): pixel centres lon 24.55–25.60,
    # lat 59.16 — all inside the test bbox, left half bright.
    tile = tmp_path / "viirs_8_75_145.png"
    tile.write_bytes(make_png(
        4, 1, [[255, 255, 255, 250, 250, 250, 5, 5, 5, 0, 0, 0]]))
    out = tmp_path / "grid.json"
    rc = main(["--build", "--cache-dir", str(tmp_path),
               "--bbox", "24.0,59.0,25.2,59.3",
               "--cols", "2", "--rows", "1",
               "--out", str(out)])
    assert rc == 0
    grid = json.loads(out.read_text(encoding="utf-8"))
    assert grid["counts"]["total"] == 2
    assert grid["vintage"] == "2016"
    assert grid["cells"][0]["mean"] > grid["cells"][1]["mean"]
    printed = json.loads(capsys.readouterr().out)
    assert printed["total"] == 2
