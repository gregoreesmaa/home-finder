"""Tests for scripts/build/batch_outage.py (issue #729).

Hermetic: no network anywhere (live pulls are operator/pole only —
the 5-min JSON is never fetched here). Pins the double-encoded
envelope decode, the sidecar build, and the --pull requirement. The
fixture repeats the live SHAPE with the observed 2026-09-19 Tallinn
row (facts, tiny).
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_outage import (  # noqa: E402
    TTL_S,
    build_sidecar,
    decode_application_data,
    main,
)

NOW = datetime(2026, 9, 19, 15, 30, tzinfo=timezone.utc)

#: Minimal live-shaped fixture (double-encoded, like the endpoint).
FIXTURE_BODY = json.dumps(json.dumps({
    "scopes": {"p": {
        "areas": [
            {"cid": 7639, "fc": 0, "fcc": 0, "id": 454883598,
             "label": "Tallinn", "pc": 0, "pcc": 0,
             "uc": 27, "ucc": 3169},
            {"cid": 7638, "fc": 0, "fcc": 0, "id": 454746528,
             "label": "Harju maakond", "pc": 0, "pcc": 0,
             "uc": 96, "ucc": 5766},
        ],
        "dynareas": [],
        "outages": [
            {"cc": 1, "id": 1055446, "t": "u"},
            {"cc": 3, "id": 1055447, "t": "f"},
        ],
    }},
}))


def test_decode_unwraps_double_envelope():
    decoded = decode_application_data(FIXTURE_BODY)
    assert decoded is not None
    assert len(decoded["areas"]) == 2
    assert decoded["areas"][0]["label"] == "Tallinn"
    assert decoded["dynareas"] == []
    assert len(decoded["outages"]) == 2


def test_decode_rejects_garbage():
    assert decode_application_data("{not json") is None
    assert decode_application_data(json.dumps([1, 2])) is None
    assert decode_application_data(json.dumps({"scopes": {}})) is None
    assert decode_application_data(
        json.dumps(json.dumps({"scopes": {"p": {}}}))) is not None


def test_sidecar_carries_timestamp_ttl_and_tallies():
    decoded = decode_application_data(FIXTURE_BODY)
    assert decoded is not None
    sidecar = build_sidecar(decoded, now=NOW)
    assert sidecar["pulled_at"] == NOW.isoformat()
    assert sidecar["ttl_s"] == TTL_S == 300
    assert len(sidecar["areas"]) == 2
    assert sidecar["outage_tallies"] == {"u": 1, "f": 1}


def test_sidecar_refuses_table_less_payload():
    try:
        build_sidecar({"areas": [], "outages": []}, now=NOW)
    except ValueError:
        return
    raise AssertionError("tühi areas-tabel peab keelduma")


def test_main_requires_pull_flag(tmp_path):
    out = str(tmp_path / "sidecar.json")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("{}")
    rc = main(["--cache-dir", str(tmp_path), "--out", out])
    assert rc == 2  # argparse error: --pull required, never from cache
