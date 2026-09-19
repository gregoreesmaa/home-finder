"""Hermetic unit tests for the joint livability x price score (#701).

No network, no snapshot: pure dicts only. Run from repo root:
  python3 -m pytest services/scoring/tests/test_joint_score.py -q

NOTE on imports: the brief snippet shows
`from services.scoring.dims_joint_score import joint_score`, but the
repo suite has no __init__.py packages — conftest puts
services/scoring on sys.path, so every existing test imports the
top-level module name (e.g. `import dims_group09`). This test follows
the repo convention so it runs under `npm run test:python`.
"""

from dims_joint_score import LIV_WEIGHT, PRICE_WEIGHT, joint_score

import app


def test_joint_ranks_best_flat_not_best_halves():
    best_liv = {"liv": 90, "price": 40}
    best_price = {"liv": 40, "price": 90}
    balanced = {"liv": 75, "price": 75}
    assert joint_score(balanced) > joint_score(best_liv)
    assert joint_score(balanced) > joint_score(best_price)


def test_joint_matches_canonical_combined_score():
    """Parity: joint on normalized halves == app.combined_score on raw inputs."""
    for liv, discount in ((88, 10), (64, 18), (95, -9), (50, 0)):
        price100 = app.deal_norm(discount) * 100.0
        assert joint_score({"liv": liv, "price": price100}) == app.combined_score(
            liv, discount
        )


def test_joint_clamps_halves():
    assert joint_score({"liv": 999, "price": 999}) == 100
    assert joint_score({"liv": -5, "price": -5}) == 0


def test_weights_mirror_canonical_contract():
    assert (LIV_WEIGHT, PRICE_WEIGHT) == (0.6, 0.4)
