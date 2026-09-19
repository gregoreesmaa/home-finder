"""Tests for services/scoring/dims_harno.py (issue #687).

Pins the static-pending NULL verdict: None for every input, the
Estonian reason names the gap honestly, and the registry shape
stays graduate-ready (key + param label + fn).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dims_harno import HARNO_DIMS, dim_harno_quality, score_harno  # noqa: E402


def test_null_for_tallinn_origin():
    score, reason = dim_harno_quality((59.4370, 24.7450), [])
    assert score is None
    assert "EI OLE" in reason


def test_null_for_missing_origin():
    score, reason = dim_harno_quality(None, None)
    assert score is None
    assert isinstance(reason, str) and len(reason) > 20


def test_reason_names_buyer_side_check():
    _, reason = dim_harno_quality((58.3806, 26.7225), [])
    assert "Haridussilm" in reason
    assert "feigi" in reason


def test_registry_shape():
    assert HARNO_DIMS == (("harno_quality", "P4-harno", dim_harno_quality),)


def test_score_entry_point_is_none():
    assert score_harno((59.4370, 24.7450), []) == {"harno_quality": None}
