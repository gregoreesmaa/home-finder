"""Terviseamet bathing-water builder tests (issue #494): hermetic tests.

No network, no snapshot, no /tmp harvest: readers run on tiny inline
fixture XML, the L-EST97 projection pins the Pirita beach control point
plus a pyproj-agreement probe constant, and the TS drift guard parses
the checked-in layers_tervise.ts.
"""

import math
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_tervise as G

SITES_XML = """<?xml version="1.0"?>
<supluskohad><supluskoht><id>119</id><nimetus>Pirita rand</nimetus>\
<supluskoha_grupi_id></supluskoha_grupi_id><tyyp>avalik veekogu</tyyp>\
<aadress>Pirita, Tallinn</aadress>\
<koordinaadid><koordinaat><x>6593003.741</x><y>547104.133</y></koordinaat></koordinaadid>\
<veekogu_nimi>Tallinna laht</veekogu_nimi><veekogu_tyyp>meri</veekogu_tyyp>\
<viimane_proovivott>24.08.2026</viimane_proovivott>\
<veekvaliteet>v&#xE4;ga hea</veekvaliteet>\
</supluskoht><supluskoht><id>999</id><nimetus>Koordinaadita rand</nimetus>\
<supluskoha_grupi_id></supluskoha_grupi_id><tyyp>supluskoht</tyyp>\
<aadress>Teadmata</aadress><koordinaadid></koordinaadid>\
<veekogu_nimi>Tiik</veekogu_nimi><veekogu_tyyp>siseveekogu</veekogu_tyyp>\
<veekvaliteet></veekvaliteet>\
</supluskoht></supluskohad>"""

SAMPLES_XML = """<?xml version="1.0"?>
<supluskoha_veeproovid><proovivott><id>1</id><supluskoht_id>119</supluskoht_id>\
<supluskoht>Pirita rand</supluskoht><proovivotu_aeg>24.08.2026 00:00</proovivotu_aeg>\
<katseprotokollid><katseprotokoll><katseprotokolli_number>TA1</katseprotokolli_number>\
<hinnang>vastab n&#xF5;uetele</hinnang></katseprotokoll></katseprotokollid></proovivott>\
<proovivott><id>2</id><supluskoht_id>119</supluskoht_id>\
<supluskoht>Pirita rand</supluskoht><proovivotu_aeg>10.06.2026 00:00</proovivotu_aeg>\
<katseprotokollid><katseprotokoll><katseprotokolli_number>TA0</katseprotokolli_number>\
<hinnang>ei vasta n&#xF5;uetele</hinnang></katseprotokoll></katseprotokollid></proovivott>\
</supluskoha_veeproovid>"""


def test_parse_supluskohad_reads_register_shape():
    sites = G.parse_supluskohad_xml(SITES_XML)
    assert len(sites) == 2
    pirita = sites[0]
    assert pirita["id"] == "119"
    assert pirita["name"] == "Pirita rand"
    assert pirita["quality_now"] == "v\u00e4ga hea"
    assert pirita["last_sample"] == "24.08.2026"
    # Coordless site keeps empty strings (build drops it, never fakes it).
    assert sites[1]["x"] == "" and sites[1]["y"] == ""


def test_lest97_projection_lands_on_pirita_beach():
    # Control point: the live Pirita rand register coordinate must land
    # on Pirita beach (~59.4722, 24.8310 — pyproj oracle 2026-09-14).
    lat, lon = G.lest97_to_wgs84(6593003.741, 547104.133)
    assert abs(lat - 59.4722) < 0.002
    assert abs(lon - 24.8310) < 0.002


def test_lest97_projection_rejects_nonfinite():
    with pytest.raises(ValueError):
        G.lest97_to_wgs84(float("nan"), 547104.133)


def test_latest_sample_prefers_dated_pass_over_older_fail():
    samples = G.parse_veeproovid_xml(SAMPLES_XML)
    assert len(samples) == 2
    latest = G.latest_sample_by_site(samples)
    # 24.08.2026 pass outranks the 10.06.2026 fail.
    assert latest["119"] == {"date": "24.08.2026", "ok": True}


def test_quality_band_class_first_sample_caps_on_failure():
    band, reason = G.quality_band("2026 - V\u00e4ga hea", "v\u00e4ga hea",
                                  {"date": "24.08.2026", "ok": True})
    assert band == 80 and "24.08.2026" in reason
    # Fresh failure caps a very-good class at 30 with its date.
    band, reason = G.quality_band("2026 - V\u00e4ga hea", "v\u00e4ga hea",
                                  {"date": "25.08.2026", "ok": False})
    assert band == 30 and "25.08.2026" in reason
    # No signal at all stays NULL (never a faked middle).
    assert G.quality_band("", "", None) == (
        None, "kvaliteet teadmata (proovid + klass puuduvad)")
    # Passing sample without a class is a 70, not an 80.
    band, _ = G.quality_band("", "", {"date": "01.07.2026", "ok": True})
    assert band == 70


def test_build_drops_coordless_sites_and_counts_them():
    sites = G.parse_supluskohad_xml(SITES_XML)
    samples = G.parse_veeproovid_xml(SAMPLES_XML)
    extract = G.build_extract(sites, samples, "fixture")
    assert extract["stats"] == {"sites": 2, "plotted": 1,
                                "dropped_no_coord": 1, "quality_null": 0,
                                "duplicate_coords": 0}
    (pt,) = extract["points"]
    assert pt["id"] == "119" and pt["q"] == 80
    assert extract["transform"] == G.LEST97_ACCURACY_LABEL


def test_ts_probe_matches_py_probe():
    # Drift guard: the TS module pins the same live-feed probe values as
    # this builder (harvest 2026-09-14: 211 sites, 758 x 2026 samples,
    # 793 x 2025 samples, 205 plotted, 6 coordless).
    assert G.TERVISE_SITES_URL.endswith("supluskohad.xml")
    assert sorted(G.TERVISE_SAMPLES_URLS) == [2025, 2026]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "apps", "web", "lib", "layers_tervise.ts")
    src = open(path, encoding="utf-8").read()
    for token in ["211", "758", "793", "205"]:
        assert token in src, token
    m = re.search(r"TERVISE_PROBE = \{(.*?)\} as const", src, re.S)
    assert m is not None
