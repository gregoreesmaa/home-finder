"""P4 noisemap dims (issue #526): hermetic tests.

No network: parsing runs on synthetic fixture strings, the dim runs
on synthetic snapshots, politeness constants are asserted as values,
and the live pull is env-gated (HF_LIVE_NOISEMAP=1) so the default
suite never touches the network.
Run: python3 -m pytest services/scoring/tests/test_dims_p4_noisemap.py -q
"""

import os

import pytest

import dims_p4_noisemap as noisemap
from dims_p4_noisemap import (
    LDEN_BANDS,
    LDEN_LOUD,
    LNIGHT_BANDS,
    LNIGHT_LOUD,
    NOISEMAP_CACHE_NAME,
    NOISEMAP_CACHE_TTL_S,
    NOISEMAP_CAPS_URL,
    NOISEMAP_LDEN_LAYER,
    NOISEMAP_LNIGHT_LAYER,
    NOISEMAP_WFS_BASE,
    P4_NOISEMAP_DIMS,
    PROBE_ACCESS,
    PROBE_CAPS_BYTES,
    PROBE_DATE,
    PROBE_FEES,
    PROBE_HARJU_HITS,
    PROBE_LICENCE,
    dim_noise_lden,
    fetch_wfs_capabilities,
    parse_capabilities_layers,
    parse_myaklass,
    score_p4_noisemap,
)

TALLINN = (59.4372, 24.7536)

#: Synthetic GetCapabilities fragment (invented layer sample — real
#: observed values appear only in docs/p4_noisemap.md, never ingested).
CAPS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0"
  xmlns:ows="http://www.opengis.net/ows/1.1">
<ows:ServiceIdentification>
<ows:Title>Mürakaardi rakenduse kaardikihid</ows:Title>
<ows:Fees>Teenuse kasutamisel tasusid ei rakendu</ows:Fees>
<ows:AccessConstraints>NONE</ows:AccessConstraints>
</ows:ServiceIdentification>
<FeatureTypeList>
<FeatureType><Name>ms:myra22_strat_sum_oopaev</Name><Title>Summa Lden</Title>
<DefaultCRS>urn:ogc:def:crs:EPSG::3301</DefaultCRS></FeatureType>
<FeatureType><Name>ms:myra22_strat_sum_oo</Name><Title>Summa Lnight</Title>
<DefaultCRS>urn:ogc:def:crs:EPSG::3301</DefaultCRS></FeatureType>
</FeatureTypeList>
</wfs:WFS_Capabilities>
"""


def _noise(lden=None, lnight=None):
    snap = {"fetched": "2026-09-16", "source": "sünteetiline"}
    if lden is not None:
        snap["lden_db"] = lden
    if lnight is not None:
        snap["lnight_db"] = lnight
    return snap


# ---------------------------------------------------------------------------
# Provisional band legs.
# ---------------------------------------------------------------------------

def test_lden_bands_at_boundaries():
    assert dim_noise_lden(TALLINN, None, _noise(lden=45.0))[0] == 85
    assert dim_noise_lden(TALLINN, None, _noise(lden=45.1))[0] == 65
    assert dim_noise_lden(TALLINN, None, _noise(lden=55.0))[0] == 65
    assert dim_noise_lden(TALLINN, None, _noise(lden=65.0))[0] == 40
    assert dim_noise_lden(TALLINN, None, _noise(lden=65.1))[0] == 20


def test_lnight_bands_shifted_5db():
    assert dim_noise_lden(TALLINN, None, _noise(lnight=40.0))[0] == 85
    assert dim_noise_lden(TALLINN, None, _noise(lnight=50.0))[0] == 65
    assert dim_noise_lden(TALLINN, None, _noise(lnight=60.0))[0] == 40
    assert dim_noise_lden(TALLINN, None, _noise(lnight=60.1))[0] == 20


def test_binding_leg_wins_quiet_day_loud_night():
    v, reason = dim_noise_lden(TALLINN, None, _noise(lden=42.0, lnight=58.0))
    assert v == 40  # Lnight leg binds, not the 85 Lden leg
    assert "Lnight" in reason and "siduv" in reason
    assert "esialgsed bändid" in reason  # provisional, said aloud


def test_quiet_night_loud_day_binds_day():
    v, reason = dim_noise_lden(TALLINN, None, _noise(lden=70.0, lnight=38.0))
    assert v == 20 and "Lden" in reason


def test_single_leg_scores_that_leg():
    assert dim_noise_lden(TALLINN, None, _noise(lden=50.0))[0] == 65
    assert dim_noise_lden(TALLINN, None, _noise(lnight=50.0))[0] == 65


def test_garbage_legs_are_ignored_not_guessed():
    v, _ = dim_noise_lden(TALLINN, None, _noise(lden=50.0, lnight="valju"))
    assert v == 65
    v2, reason2 = dim_noise_lden(TALLINN, None,
                                 _noise(lden="tundmatu", lnight=None))
    assert v2 is None and "EI OLE" in reason2


# ---------------------------------------------------------------------------
# No-map NULL contract.
# ---------------------------------------------------------------------------

def test_no_origin_is_none():
    v, reason = dim_noise_lden(None, None, _noise(lden=50.0))
    assert v is None and "EI OLE" in reason and "aadress" in reason


def test_no_rows_is_none_with_verdict_markers():
    for snap in (None, {}, {"fetched": "2026-09-16"}):
        v, reason = dim_noise_lden(TALLINN, None, snap)
        assert v is None, snap
        assert "hinnang" in reason and "EI OLE" in reason
        assert "litsents" in reason  # licence gap named
        assert "xgis" in reason  # buyer-side check named


# ---------------------------------------------------------------------------
# MYRAKLASS adapter seam (confirmed domain 2026-09-17 — see module docstring).
# ---------------------------------------------------------------------------

def test_parse_myaklass_confirmed_domain():
    # Real WFS values (2026-09-17): plain 5 dB lower bounds.
    assert parse_myaklass("45") == 49.9
    assert parse_myaklass("50") == 54.9
    assert parse_myaklass("55") == 59.9
    assert parse_myaklass("65") == 69.9


def test_parse_myaklass_legacy_fallback():
    assert parse_myaklass("55-59") == 59.0
    assert parse_myaklass("55-59 dB") == 59.0
    assert parse_myaklass("55–59") == 59.0  # en dash tolerated
    assert parse_myaklass(">65") == 99.0
    assert parse_myaklass("<45") == 44.9


def test_parse_myaklass_fail_closed():
    assert parse_myaklass(None) is None
    assert parse_myaklass("") is None
    assert parse_myaklass("tundmatu") is None
    assert parse_myaklass("55-") is None


# ---------------------------------------------------------------------------
# Capabilities verdict record.
# ---------------------------------------------------------------------------

def test_parse_capabilities_layers():
    rec = parse_capabilities_layers(CAPS_FIXTURE)
    assert rec["title"] == "Mürakaardi rakenduse kaardikihid"
    assert rec["layers"] == ["ms:myra22_strat_sum_oo",
                             "ms:myra22_strat_sum_oopaev"]
    assert rec["n_layers"] == 2
    assert rec["crs"] == "urn:ogc:def:crs:EPSG::3301"
    assert "Maa- ja Ruumiamet" in rec["source"]


def test_parse_capabilities_empty_is_negative_not_error():
    rec = parse_capabilities_layers("<html>tühi leht</html>")
    assert rec == {"title": "", "layers": [], "n_layers": 0, "crs": "",
                   "source": rec["source"]}
    assert parse_capabilities_layers("")["layers"] == []


# ---------------------------------------------------------------------------
# Registry, rollup, constants, politeness, live gate.
# ---------------------------------------------------------------------------

def test_band_constants_pinned():
    assert LDEN_BANDS == ((45.0, 85), (55.0, 65), (65.0, 40))
    assert LDEN_LOUD == 20
    assert LNIGHT_BANDS == ((40.0, 85), (50.0, 65), (60.0, 40))
    assert LNIGHT_LOUD == 20


def test_probe_record_pinned():
    assert PROBE_DATE == "2026-09-16"
    assert PROBE_CAPS_BYTES == 69922
    assert PROBE_HARJU_HITS == 4705
    assert PROBE_FEES == "Teenuse kasutamisel tasusid ei rakendu"
    assert PROBE_ACCESS == "NONE"
    assert "omaniku otsus 2026-09-17" in PROBE_LICENCE


def test_all_none_reasons_carry_honesty_markers():
    for snap in (None, {}, {"fetched": "2026-09-16"}):
        _, reason = dim_noise_lden(TALLINN, None, snap)
        assert "hinnang" in reason and "EI OLE" in reason
        assert "garanteeritud" not in reason and "mõõdetud" not in reason


def test_registry_and_rollup_shape():
    assert [k for k, _, _ in P4_NOISEMAP_DIMS] == ["noise_lden"]
    dims, reasons = score_p4_noisemap(TALLINN, None, _noise(lden=70.0))
    assert dims == {"noise_lden": 20} and len(reasons) == 1
    empty, no_reasons = score_p4_noisemap(TALLINN, None, None)
    assert empty == {"noise_lden": None} and no_reasons == []
    assert noisemap.P4_NOISEMAP_DIMS is P4_NOISEMAP_DIMS


def test_politeness_contract_as_values():
    assert NOISEMAP_WFS_BASE == "https://teenus.maaamet.ee/ows/myrakaart"
    assert NOISEMAP_CAPS_URL.startswith(NOISEMAP_WFS_BASE)
    assert NOISEMAP_LDEN_LAYER == "ms:myra22_strat_sum_oopaev"
    assert NOISEMAP_LNIGHT_LAYER == "ms:myra22_strat_sum_oo"
    assert NOISEMAP_CACHE_TTL_S == 180 * 86400  # 5-year maps: slow re-check
    assert "home-finder" in noisemap.NOISEMAP_USER_AGENT
    assert NOISEMAP_CACHE_NAME.endswith(".xml")


@pytest.mark.skipif(not os.environ.get("HF_LIVE_NOISEMAP"),
                    reason="live network only with HF_LIVE_NOISEMAP=1")
def test_live_capabilities_pull_explicit_flag_only(tmp_path):
    xml, provenance = fetch_wfs_capabilities(cache_dir=str(tmp_path))
    assert "Mürakaardi" in xml
    assert provenance in ("live", "cache")
