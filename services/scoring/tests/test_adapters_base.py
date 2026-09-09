"""Regression: shared adapter interface (normalize, dedup, cache, contract)."""

import os
import time

import adapters
import adapters.city24_ee as city24
import adapters.kv_ee as kv_ee
from adapters import (
    adapter_contract_check,
    address_key,
    cached_fetch,
    dedup_listings,
    normalize_listing,
)


def test_both_adapters_satisfy_contract():
    assert adapter_contract_check(kv_ee) == []
    assert adapter_contract_check(city24) == []
    assert kv_ee.ROBOTS_URL.endswith("/robots.txt")
    assert city24.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in kv_ee.HEADERS["User-Agent"]
    assert "home-finder" in city24.HEADERS["User-Agent"]


def test_normalize_fills_canonical_defaults():
    rec = normalize_listing({"id": "x-1", "source": "kv.ee", "source_url": "https://kv.ee"})
    assert rec["address"]
    assert rec["rooms"] is None
    assert rec["area_m2"] is None


def test_address_key_ignores_case_and_punctuation():
    assert address_key("Kotzebue 12, Tallinn") == address_key("  kotzebue 12 tallinn! ")
    assert address_key("Tähe 45, Tartu") != address_key("Mere pst 7, Pärnu")


def test_dedup_drops_cross_portal_overlap_first_wins():
    kv_row = {
        "id": "kv-1", "source": "kv.ee", "source_url": "https://kv.ee/a",
        "address": "Kotzebue 12, Tallinn", "price": 285000,
    }
    city_row = {
        "id": "city24-9", "source": "city24.ee", "source_url": "https://www.city24.ee/b",
        "address": "kotzebue 12 Tallinn", "price": 285000,  # same flat, other portal
    }
    other = {
        "id": "city24-8", "source": "city24.ee", "source_url": "https://www.city24.ee/c",
        "address": "Mere pst 7, Pärnu", "price": 198000,
    }
    merged = dedup_listings([kv_row], [city_row, other])
    assert [r["id"] for r in merged] == ["kv-1", "city24-8"]


def test_dedup_keeps_same_address_when_price_differs():
    a = {"id": "kv-1", "source": "kv.ee", "source_url": "u",
         "address": "Kotzebue 12, Tallinn", "price": 285000}
    b = {"id": "city24-9", "source": "city24.ee", "source_url": "v",
         "address": "Kotzebue 12, Tallinn", "price": 279000}
    assert len(dedup_listings([a], [b])) == 2


def test_cached_fetch_hits_disk_and_respects_ttl(tmp_path):
    calls = []

    def fetch():
        calls.append(1)
        return "<html>fresh</html>"

    out1 = cached_fetch("probe", "q", 1, fetch, str(tmp_path), 3600)
    out2 = cached_fetch("probe", "q", 1, fetch, str(tmp_path), 3600)
    assert (out1, out2) == ("<html>fresh</html>", "<html>fresh</html>")
    assert len(calls) == 1  # second call served from disk

    out3 = cached_fetch("probe", "q", 1, fetch, str(tmp_path), -1)  # expired TTL
    assert out3 == "<html>fresh</html>" and len(calls) == 2


def test_cache_files_land_in_cache_dir(tmp_path):
    cached_fetch("probe", "", 1, lambda: "<html>x</html>", str(tmp_path), 3600)
    assert os.listdir(str(tmp_path))


def test_adapters_package_exports():
    assert adapters.DEFAULT_TTL_S == 24 * 3600
    assert set(adapters.REQUIRED_KEYS) == {"id", "source", "source_url", "address", "price"}


def test_chrome_extra_args_drops_sandbox_only_as_root(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert adapters.chrome_extra_args() == ["--no-sandbox"]
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    assert adapters.chrome_extra_args() == []
