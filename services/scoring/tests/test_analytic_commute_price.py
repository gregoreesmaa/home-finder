"""Documented-blocked formula test for the commute-adjusted price analytic (#700).

Blocked on #669 (TomTom car-commute matrix): without per-area rush-hour
minutes the euros-per-saved-minute formula in
docs/analytic_commute_price.md has no real inputs, so this test is
honestly skipped — not faked. Unblock condition: #669 closed with a
commute matrix available; then implement
services/scoring/dims_commute_price.py and un-skip this test, pinning
the formula E = monthly-housing-cost-delta / monthly-minutes-saved on
fixtures.
"""

import pytest


@pytest.mark.skip(reason="blocked on #669 car-commute matrix data")
def test_euros_per_saved_minute():
    pass
