"""Skeleton regression: every remaining portal adapter imports and exposes the kv.ee anchor shape.

Each stub's parse_search_html() returns [] until its owning builder
(issues #6–#19) implements selectors + fixture + full test. These
placeholders pin the contract (SOURCE / fetch / parse / scrape) so the
stubs stay importable and pytest-collectible in the meantime.
Fully offline: no network calls.
"""

import importlib

import pytest

# module -> (expected SOURCE, owning issue)
STUBS = {
    "adapters.kinnisvara24_ee": ("kinnisvara24.ee", 7),
    "adapters.kinnisvaraweb_ee": ("kinnisvaraweb.ee", 8),
    "adapters.okidoki_ee": ("okidoki.ee", 9),
    "adapters.osta_ee": ("osta.ee", 10),
    "adapters.facebook": ("facebook", 11),
    "adapters.domus_ee": ("domus.ee", 12),
    "adapters.uusmaa_ee": ("uusmaa.ee", 13),
    "adapters.pindi_ee": ("pindi.ee", 14),
    "adapters.one_partner_ee": ("1partner.ee", 15),
    "adapters.oberhaus_ee": ("oberhaus.ee", 16),
    "adapters.arcovara_ee": ("arcovara.ee", 17),
    "adapters.lvm_ee": ("lvm.ee", 18),
    "adapters.remax_ee": ("remax.ee", 19),
}


@pytest.mark.parametrize("modname,expected", list(STUBS.items()))
def test_stub_anchor_shape(modname, expected):
    source, _issue = expected
    mod = importlib.import_module(modname)
    assert mod.SOURCE == source
    assert mod.BASE_URL.startswith("https://")
    assert callable(mod.fetch_search_html)
    assert callable(mod.parse_search_html)
    assert callable(mod.scrape)
    assert mod.parse_search_html("") == []
    assert mod.parse_search_html("<html><body>no results</body></html>") == []


def test_facebook_has_no_automated_fetch():
    mod = importlib.import_module("adapters.facebook")
    with pytest.raises(NotImplementedError):
        mod.fetch_search_html()
    with pytest.raises(NotImplementedError):
        mod.parse_pasted("Kotzebue 12, Tallinn 285000 €")
