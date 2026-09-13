"""P4 own-snapshot per-asum medians (issue #495): hermetic tests.

No network: the kernel is pure dict-folding (exact `asum` keys +
prices), so all tests run on fixture dicts. Thick groups pin exact
medians; thin groups pin None + Estonian honesty markers (hinnang +
EI OLE + MIN_N + buyer check) on every input including the empty
store. The verdict itself (no `asum` key in adapter records) is
pinned by asserting keyless rows never join — not even on a
free-text "Kalamaja" address mention (identity-join-or-NULL, #485
precedent).
"""

import os
import re

import dims_p4_own_asum as own
from dims_p4_own_asum import (
    MIN_N,
    describe_asum,
    describe_store,
    group_by_asum,
)


def row(asum, price, area, **over):
    base = {"asum": asum, "price": price, "area_m2": area}
    base.update(over)
    return base


KALAMAJA_5 = [
    row("Kalamaja", 250000, 55.0),   # 4545.45
    row("Kalamaja", 260000, 55.0),   # 4727.27
    row("Kalamaja", 240000, 60.0),   # 4000.00
    row("Kalamaja", 300000, 62.0),   # 4838.71
    row("Kalamaja", 200000, 50.0),   # 4000.00
]


def test_min_n_is_five_land_board_publication_bar():
    assert MIN_N == 5
    assert own.MIN_N == 5


def test_min_n_parity_with_ts_layer():
    """ASUMEDIA_MIN_N drift pin (statkov #485 precedent: parse, fail on drift)."""
    ts = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                      "apps", "web", "lib", "layers_asumedia.ts")
    src = open(ts, encoding="utf-8").read()
    m = re.search(r"export const ASUMEDIA_MIN_N\s*=\s*(\d+)", src)
    assert m is not None, "ASUMEDIA_MIN_N missing in layers_asumedia.ts"
    assert int(m.group(1)) == MIN_N


def test_thick_group_pins_exact_median_odd():
    median, reason = describe_asum("Kalamaja", [4000.0, 4000.0, 4545.45,
                                               4727.27, 4838.71])
    assert median == 4545.45
    assert "hinnang" in reason
    assert "5 oma snapshotti" in reason


def test_thick_group_even_count_averages_middle_pair():
    median, _reason = describe_asum(
        "Kalamaja", [4000.0, 4000.0, 4545.45, 4727.27, 4838.71, 5000.0],
        min_n=5)
    assert median == (4545.45 + 4727.27) / 2


def test_thin_group_stays_null_with_n_labeled():
    median, reason = describe_asum("Kalamaja", [4545.45, 4727.27])
    assert median is None
    assert "EI OLE" in reason
    assert "2 snapshotti" in reason
    assert str(MIN_N) in reason


def test_single_snapshot_never_sets_a_median():
    median, reason = describe_asum("Kalamaja", [4545.45])
    assert median is None
    assert "EI OLE" in reason


def test_empty_store_describes_nothing():
    assert describe_store([]) == {}


def test_keyless_rows_never_join_even_on_free_text_mention():
    """No `asum` key, no join — a Kalamaja substring is not an exact key."""
    rows = [
        {"address": "Tallinn, Kalamaja, Soo 12-7", "price": 250000,
         "area_m2": 55.0},
        {"address": "Kotzebue 12, Tallinn", "price": 285000,
         "area_m2": 68.0},
    ]
    groups, skipped = group_by_asum(rows)
    assert groups == {}
    assert skipped == 2
    assert describe_store(rows) == {}


def test_blank_asum_key_never_joins():
    groups, skipped = group_by_asum(
        [row("   ", 250000, 55.0), row(None, 250000, 55.0)])
    assert groups == {}
    assert skipped == 2


def test_priceless_rows_skipped_and_counted():
    groups, skipped = group_by_asum(
        KALAMAJA_5 + [row("Kalamaja", None, 55.0),
                      row("Kalamaja", 250000, None),
                      row("Kalamaja", 0, 55.0),
                      row("Kalamaja", -100, 55.0)])
    assert len(groups["Kalamaja"]) == 5
    assert skipped == 4


def test_price_per_m2_wins_when_present():
    groups, _ = group_by_asum(
        [row("Pelgulinn", 999999, 10.0, price_per_m2=4200.0)])
    assert groups == {"Pelgulinn": [4200.0]}


def test_store_describes_thick_and_thin_asums_together():
    store = describe_store(
        KALAMAJA_5 + [row("Pelgulinn", 200000, 50.0)])
    assert sorted(store) == ["Kalamaja", "Pelgulinn"]
    assert store["Kalamaja"][0] == 250000 / 55.0
    assert store["Pelgulinn"][0] is None
    assert "EI OLE" in store["Pelgulinn"][1]


def test_null_reasons_name_buyer_check_not_guarantee():
    _median, reason = describe_asum("Kalamaja", [1.0, 2.0])
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
