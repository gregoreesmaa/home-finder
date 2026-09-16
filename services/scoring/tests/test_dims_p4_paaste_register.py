"""P4 paaste static-register check (issue #523): hermetic tests.

No network: fetch_register_snapshot is never called for a live pull
here (its contract — polite monthly pulls, file cache, TTL,
transport errors raise — is covered via the pure cache_is_fresh
helper plus a cache-hit fetch test that performs no GET). Parsing,
the no-geometry invariant, and the improved NULL message run on a
fully synthetic Nuxt-payload fixture.
"""

import dims_p4_paaste_register as reg
from dims_p4_paaste_register import (
    GEOMETRY_TOKENS,
    PAASTE_REGISTER_TTL_S,
    cache_is_fresh,
    dim_station_register,
    fetch_register_snapshot,
    parse_register_payload,
    tallinn_extract,
)

#: Synthetic kontakt-payload fixture (models the OBSERVED 2026-09-16
#: field shape only: __NUXT_JSONP__ wrapper, \u002F-escaped unit
#: paths, one street address, zero coordinate tokens). Never ingested.
SYNTH_PAYLOAD = (
    '__NUXT_JSONP__("/et/kontaktid/pohja_paastekeskus",'
    '(function(M){M[0]={slug:"pohja",nimetus:"Päästetöö büroo"};'
    'M[1]={slug:"harju",nimetus:"Päästeamet\\u002FPõhja päästekeskus"};}'
    '("unit-path", "Päästeamet\\u002FPõhja päästekeskus",'
    ' "Päästetöö büroo",'
    ' "üldkontaktid: Testi tn 3, Tallinn", "Testi tn 3", "Tallinn")));'
)


def test_parse_finds_units_and_address_without_geometry():
    snap = parse_register_payload(SYNTH_PAYLOAD)
    assert snap["n_units"] >= 2
    assert snap["n_addresses"] >= 1
    assert snap["has_geometry"] is False
    assert "Testi tn 3" in snap["addresses"]


def test_no_geometry_tokens_in_fixture_payload():
    lowered = SYNTH_PAYLOAD.lower()
    for tok in GEOMETRY_TOKENS:
        assert tok not in lowered


def test_empty_payload_reads_as_empty_register_never_error():
    snap = parse_register_payload("")
    assert snap["units"] == []
    assert snap["addresses"] == []
    assert snap["has_geometry"] is False


def test_extract_carries_fetch_date_and_counts():
    snap = tallinn_extract(parse_register_payload(SYNTH_PAYLOAD),
                           fetched="2026-09-16")
    assert snap["fetched"] == "2026-09-16"
    assert snap["n_units"] >= 2
    assert snap["has_geometry"] is False


def test_dim_null_without_snapshot_names_buyer_check():
    score, reason = dim_station_register((59.437, 24.753), [], None)
    assert score is None
    assert "EI OLE" in reason
    assert "hinnang" in reason
    assert "rescue.ee" in reason


def test_dim_null_with_snapshot_is_improved_message():
    snap = tallinn_extract(parse_register_payload(SYNTH_PAYLOAD),
                           fetched="2026-09-16")
    score, reason = dim_station_register((59.437, 24.753), [], snap)
    assert score is None
    assert "EI OLE" in reason
    assert "0 koordinaati" in reason
    assert "aadress ei ole punkt" in reason
    assert "2026-09-16" in reason
    assert "Tark Tee" in reason


def test_dim_never_scores_even_without_origin():
    snap = tallinn_extract(parse_register_payload(SYNTH_PAYLOAD),
                           fetched="2026-09-16")
    score, _reason = dim_station_register(None, [], snap)
    assert score is None


def test_ttl_is_monthly_paaste_cadence():
    assert PAASTE_REGISTER_TTL_S == 30 * 86400


def test_fetch_cache_hit_performs_no_request(tmp_path):
    from dims_p4_paaste_register import _cache_path
    for index in range(4):
        dest = _cache_path(str(tmp_path), index)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(SYNTH_PAYLOAD)
    body, provenance = fetch_register_snapshot(cache_dir=str(tmp_path))
    assert provenance == "cache"
    assert body.count("__NUXT_JSONP__") == 4
    assert cache_is_fresh(_cache_path(str(tmp_path), 0)) is True


def test_cache_is_fresh_false_when_missing(tmp_path):
    assert cache_is_fresh(str(tmp_path / "nope.js")) is False


def test_module_touches_no_shared_files():
    import inspect
    src = inspect.getsource(reg)
    assert "import livability" not in src
    assert "import dims_p4_paaste" not in src
    assert "from dims_p4_paaste import" not in src
    assert "WEIGHTS =" not in src
    assert "WEIGHTS[" not in src
