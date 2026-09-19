"""Documented-blocked formula test for the February analytic (#702).

Blocked on #683 (TarkTee DATEX winter severity): without measured
per-area winter severity the February formula in
docs/analytic_february.md has no real inputs, so this test is honestly
skipped — not faked. Unblock condition: #683 closed with winter
severity data available; then implement
services/scoring/dims_february.py and un-skip this test, pinning the
formula (winter severity x heating vulnerability x snow-clearing
priority) on fixtures.
"""

import pytest


@pytest.mark.skip(reason="blocked on #683 winter severity data")
def test_february_score():
    pass
