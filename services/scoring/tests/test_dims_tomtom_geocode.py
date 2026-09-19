"""Tests for services/scoring/dims_tomtom_geocode.py (issue #675).

Hermetic and pure: normalization, hashing, splitting, and coord
checks - no network, no key. The live-cache behavior (zero re-calls)
is pinned in test_batch_tomtom_geocode.py via urlopen call counts.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from dims_tomtom_geocode import (  # noqa: E402
    address_hash,
    has_coords,
    normalize_address,
    split_street,
)


def test_normalize_collapses_variants_to_one_hash():
    assert normalize_address("Tartu mnt 25, Tallinn") == \
        normalize_address("tartu  mnt 25 tallinn!")
    assert address_hash("Tartu mnt 25, Tallinn") == \
        address_hash("tartu mnt 25 tallinn")
    assert address_hash("Tartu mnt 25, Tallinn") != \
        address_hash("Tartu mnt 26, Tallinn")
    assert len(address_hash("x")) == 64  # sha256 hex


def test_split_street_best_effort():
    street, muni = split_street("Tartu mnt 25, Tallinn")
    assert street == "Tartu mnt 25"
    assert muni == "Tallinn"
    street, muni = split_street("Narva mnt 1")
    assert muni == "Tallinn"  # default when unnamed


def test_has_coords_honest():
    assert has_coords({"lat": 59.437, "lon": 24.753}) is True
    assert has_coords({"lat": None, "lon": None}) is False
    assert has_coords({"lat": True, "lon": 24.7}) is False
    assert has_coords({"lat": float("nan"), "lon": 24.7}) is False
    assert has_coords({}) is False


def test_quota_and_ttl_constants():
    import dims_tomtom_geocode as d
    assert d.GEOCODE_MAX_CALLS == 100  # trickle: coord-less only
    assert d.GEOCODE_TTL_S == 30 * 24 * 3600  # geocodes are named
    # Results (ToS 11.4): TTL-bounded cache, never permanent
