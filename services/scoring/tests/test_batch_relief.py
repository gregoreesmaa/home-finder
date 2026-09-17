"""Hermetic tests for scripts/build/batch_relief.py (issue #619).

No network, no snapshot files: inline minimal TIFF fixtures only.
"""

import base64
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_relief import (  # noqa: E402
    build_sidecar,
    grid_stats,
    main,
    quantize_dm,
    read_float32_grid,
)

from array import array  # noqa: E402


def tiny_tiff(values, cols=2, rows=2):
    """Minimal single-strip float32 LE TIFF."""
    data = struct.pack("<%df" % len(values), *values)
    n = 9
    header = b"II" + struct.pack("<HI", 42, 8)
    entries = b""
    off = 8 + 2 + n * 12 + 4
    def entry(tag, typ, cnt, val):
        return struct.pack("<HHI4s", tag, typ, cnt, struct.pack("<I", val))
    entries += entry(256, 3, 1, cols)
    entries += entry(257, 3, 1, rows)
    entries += entry(258, 3, 1, 32)
    entries += entry(259, 3, 1, 1)
    entries += entry(262, 3, 1, 1)
    entries += entry(273, 4, 1, off)
    entries += entry(277, 3, 1, 1)
    entries += entry(339, 3, 1, 3)
    entries += entry(278, 3, 1, rows)
    return header + struct.pack("<H", n) + entries + struct.pack("<I", 0) + data


def write_tmp(tmp_path, name, data):
    p = str(tmp_path / name)
    with open(p, "wb") as fh:
        fh.write(data)
    return p


def test_reads_float32_grid(tmp_path):
    p = write_tmp(tmp_path, "t.tif", tiny_tiff([1.0, 2.0, 3.0, 4.0]))
    cols, rows, grid = read_float32_grid(p)
    assert (cols, rows) == (2, 2)
    assert list(grid) == [1.0, 2.0, 3.0, 4.0]


def test_refuses_non_float(tmp_path):
    p = write_tmp(tmp_path, "t.tif", b"not a tiff")
    try:
        read_float32_grid(p)
    except ValueError:
        return
    raise AssertionError("non-TIFF must raise, never guess")


def test_quantize_keeps_missing():
    vals, missing = quantize_dm(array("f", [10.05, float("nan"), 9999.0, -100.0]))
    assert vals[0] == 101  # decimetres, rounded
    assert vals[1:] == [-32768, -32768, -32768]
    assert missing == 3


def test_stats_cover_valid_only():
    s = grid_stats(array("f", [10.0, 20.0, 30.0, float("nan")]))
    assert s["n"] == 3
    assert s["min"] == 10.0
    assert s["max"] == 30.0


def test_sidecar_roundtrip():
    doc = build_sidecar(2, 2, (23.0, 58.0, 24.0, 59.0), array("f", [1.0, 2.0, 3.0, 4.0]), "2026-09-17")
    assert doc["cols"] == 2
    assert doc["unit"] == "dm"
    raw = base64.b64decode(doc["data"])
    assert list(struct.unpack("<4h", raw)) == [10, 20, 30, 40]
    assert "Maa-amet" in doc["source"]


def test_missing_input_writes_nothing(tmp_path, capsys):
    rc = main(["--tif", str(tmp_path / "nope.tif"), "--snap", str(tmp_path / "snap")])
    assert rc == 1
    assert not os.path.exists(str(tmp_path / "snap" / "relief" / "relief-tint.json"))
    assert "NOTHING" in capsys.readouterr().out
