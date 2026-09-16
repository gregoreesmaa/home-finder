"""Hermetic tests for scripts/build/batch_fixit.py (issue #623).

Covers ONLY the pure sidecar projection — the network pull
(fetch_annateada_snapshot) is never called here (AGENTS.md section
7.6). Parser/builder behavior is pinned in test_dims_p4_fixit.py
(reused, never re-tested here).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_fixit import build_sidecar  # noqa: E402


def test_sidecar_projects_wire_shape_only(tmp_path):
    pins = [
        {"lat": 59.4374, "lon": 24.7454, "handled": 1, "ts": 1758000000,
         "category": "Heakord", "msg": "Someone specific did X",
         "photo": "http://example.com/p.jpg", "region": "Tallinn",
         "kind": "annateada_pin_p4"},
        {"lat": 59.44, "lon": 24.75, "handled": 0, "ts": 1758000100,
         "category": "Muu", "msg": "y", "photo": "", "region": "Tallinn",
         "kind": "annateada_pin_p4"},
    ]
    pins.append({"lat": 59.45, "lon": 24.76, "handled": 0, "ts": None,
                 "category": "Muu", "msg": "z", "photo": "",
                 "region": "Tallinn", "kind": "annateada_pin_p4"})
    doc = build_sidecar(pins, "2026-09-17T00:00:00Z", "2026-09-17",
                        str(tmp_path))
    # Timeless pins fail closed (dropped + counted, never shipped).
    assert doc["counts"] == {"total": 2, "handled": 1, "unhandled": 1,
                             "dropped_timeless": 1}
    assert doc["window_days"] == 19
    assert doc["points"] == [
        {"lat": 59.4374, "lon": 24.7454, "handled": True, "ts": 1758000000},
        {"lat": 59.44, "lon": 24.75, "handled": False, "ts": 1758000100},
    ]
    # Report text, categories, photos, regions never reach the wire.
    blob = json.dumps(doc, ensure_ascii=False)
    assert "Someone specific" not in blob
    assert "Heakord" not in blob
    assert "example.com" not in blob
    assert '"category"' not in blob and '"msg"' not in blob
    assert '"photo"' not in blob and '"region"' not in blob
