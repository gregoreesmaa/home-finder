"""Tests for services/scoring/dims_gbfs.py (issue #688).

Pins the dated-negative NULL verdict: None for every input, the
Estonian reason names the gap honestly, and the registry shape
stays graduate-ready (key + param label + fn).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dims_gbfs import GBFS_DIMS, dim_gbfs_bikes, score_gbfs  # noqa: E402


def test_null_for_tallinn_origin():
    score, reason = dim_gbfs_bikes((59.4370, 24.7450), [])
    assert score is None
    assert "EI OLE" in reason


def test_null_for_missing_origin():
    score, reason = dim_gbfs_bikes(None, None)
    assert score is None
    assert isinstance(reason, str) and len(reason) > 20


def test_reason_names_buyer_side_check():
    _, reason = dim_gbfs_bikes((58.3806, 26.7225), [])
    assert "ratas.tartu.ee" in reason
    assert "feigi" in reason


def test_registry_shape():
    assert GBFS_DIMS == (("gbfs_bikes", "P4-GBFS", dim_gbfs_bikes),)


def test_score_entry_point_is_none():
    assert score_gbfs((59.4370, 24.7450), []) == {"gbfs_bikes": None}
