"""Group 1 listing-portal dims, batch B (issue #203): hermetic tests.

No network: all twenty scorers are NULL dims (no snapshot area signal
for listing-interior/NLP facts), so tests assert None + Estonian
buyer-check reasons over fixture inputs only.
"""

import dims_group01b as g01b
from dims_group01b import GROUP01B_DIMS, score_group01b

TALLINN = (59.4372, 24.7536)

POIS = [{"kind": "parking", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]


def _fns():
    return [(key, pnum, fn) for key, pnum, fn in GROUP01B_DIMS]


def test_registry_covers_exactly_the_twenty_g1b_params():
    assert [p for _, p, _ in _fns()] == [
        "p121", "p129", "p140", "p180", "p191", "p192", "p193", "p194",
        "p195", "p198", "p200", "p268", "p285", "p286", "p288", "p289",
        "p290", "p300", "p412", "p489",
    ]
    assert [k for k, _, _ in _fns()] == [
        "multigen", "nanny_quarters", "cosmetic_palette", "hidden_space",
        "radiant_floor", "spa_recovery", "acoustic_theater",
        "climate_storage", "scullery", "motor_court", "culinary_suite",
        "server_closet", "indoor_outdoor", "bulk_pantry", "pet_quarantine",
        "hobby_mess", "micro_spaces", "flip_indicators", "package_theft",
        "staging_illusions",
    ]
    assert g01b.GROUP01B_DIMS is GROUP01B_DIMS


def test_every_dim_is_none_with_honest_estonian_reason():
    for key, _, fn in _fns():
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None)]:
            v, reason = fn(origin, pois)
            assert v is None, key
            assert "EI OLE" in reason, key
            assert "hinnang" in reason, key


def test_rejected_proxy_reasons_name_what_was_not_used():
    by_key = {k: fn for k, _, fn in _fns()}
    _, motor_reason = by_key["motor_court"](TALLINN, POIS)
    assert "parkla" in motor_reason or "parkimistihedus" in motor_reason
    _, theft_reason = by_key["package_theft"](TALLINN, POIS)
    assert "pakiautomaadi" in theft_reason
    _, flip_reason = by_key["flip_indicators"](TALLINN, POIS)
    assert "Maa-ameti" in flip_reason
    _, staging_reason = by_key["staging_illusions"](TALLINN, POIS)
    assert "fotofakt" in staging_reason or "fotod" in staging_reason


def test_aggregator_returns_all_none_dict():
    out = score_group01b(TALLINN, POIS)
    assert set(out) == {k for k, _, _ in _fns()}
    assert all(v is None for v in out.values())
    assert len(out) == 20
    assert score_group01b(None, None) == out
