"""EELIS real-data verdict (issue #517): hermetic tests.

No network: every test runs on hand-built zone rows. The module
itself performs no requests (the pull lives in dims_p4_eelis), so
there is nothing to stub -- the suite proves the install gate is
network-free by construction (pure functions only).
Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_eelis_realdata.py -q
"""

import dims_eelis_realdata as R
from dims_eelis_realdata import (
    RECHECK_AFTER,
    SOURCE_LABEL,
    VERDICT_DATE,
    VERDICT_DIMS,
    VERDICT_LAYERS,
    coverage_note,
    installable_sidecar,
    is_fictitious,
    scrub_fictitious,
    verdict_summary,
)

REAL_KAITSE = {"zone_id": "K1", "nimi": "Pirita jõeoru maastikukaitseala",
               "lat": 59.45, "lon": 24.83}
REAL_NIIT = {"zone_id": "N1", "nimi": "Lillepi niit", "lat": 59.44,
             "lon": 24.76}
REAL_RAIE = {"zone_id": "R1", "nimi": "Metsaalune raieala 2024",
             "lat": 59.43, "lon": 24.75}

# The exact builder-snapshot fiction (issue #517 evidence).
FICTION_SNAPSHOT = [
    {"zone_id": "F1", "nimi": "Pirita joeoru maastikukaitseala (fiktiivne)"},
    {"zone_id": "F2", "nimi": "Fixture niit (fiktiivne)"},
    {"zone_id": "F3", "nimi": "Fixture raie (fiktiivne)"},
]


def test_marks_all_three_snapshot_zones_fictitious():
    assert all(is_fictitious(z) for z in FICTION_SNAPSHOT)


def test_real_register_names_pass():
    assert not is_fictitious(REAL_KAITSE)
    assert not is_fictitious(REAL_NIIT)
    assert not is_fictitious(REAL_RAIE)


def test_unenumerated_variant_still_caught():
    # Mixed case + bare marker, never listed verbatim in the issue.
    assert is_fictitious({"nimi": "Testala ( FIKTIIVNE )"})
    assert is_fictitious({"name": "FIXTURE-meadow copy"})
    assert is_fictitious({"nimi": "Demo kaitseala"})
    assert is_fictitious({"nimi": "Näidis-raie"})


def test_non_dict_row_fails_closed():
    assert is_fictitious(None)
    assert is_fictitious("Pirita jõeoru maastikukaitseala")
    assert is_fictitious(42)


def test_scrub_drops_fiction_keeps_real():
    zones = [REAL_KAITSE, FICTION_SNAPSHOT[0], REAL_NIIT,
             FICTION_SNAPSHOT[1], REAL_RAIE, FICTION_SNAPSHOT[2]]
    clean, dropped = scrub_fictitious(zones)
    assert dropped == 3
    assert clean == [REAL_KAITSE, REAL_NIIT, REAL_RAIE]


def test_scrub_empty_is_clean():
    clean, dropped = scrub_fictitious([])
    assert (clean, dropped) == ([], 0)


def test_scrub_unknown_input_fails_closed():
    clean, dropped = scrub_fictitious(None)
    assert clean == []
    ok, _ = installable_sidecar(None)
    assert not ok


def test_install_refuses_fiction():
    ok, reason = installable_sidecar(FICTION_SNAPSHOT)
    assert not ok
    assert "EI OLE" in reason
    assert "fiktiiv" in reason
    assert VERDICT_DATE in reason


def test_install_refuses_mixed_candidate():
    ok, reason = installable_sidecar([REAL_KAITSE, FICTION_SNAPSHOT[0]])
    assert not ok
    assert "EI OLE" in reason


def test_install_honest_empty():
    ok, reason = installable_sidecar([])
    assert not ok
    assert "EI OLE" in reason
    assert "tühjaks" in reason


def test_install_accepts_clean_real():
    ok, reason = installable_sidecar([REAL_KAITSE, REAL_NIIT, REAL_RAIE])
    assert ok
    assert "3 tõelist tsooni" in reason
    assert VERDICT_DATE in reason


def test_coverage_note_names_all_layers_with_dates():
    note = coverage_note()
    for _, wfs, n, _ in VERDICT_LAYERS:
        assert wfs in note
        assert str(n) in note
    assert VERDICT_DATE in note
    assert RECHECK_AFTER in note


def test_verdict_summary_states_real_harvest_and_fiction_refusal():
    text = verdict_summary()
    assert "#517" in text
    assert "33+44+1" in text
    assert "EI paigaldata" in text
    assert RECHECK_AFTER in text


def test_registry_surface_is_verdict_only():
    assert VERDICT_DIMS == ("eelis_realdata_verdict",)
    assert SOURCE_LABEL.startswith("Keskkonnaagentuuri EELIS WFS")
    assert VERDICT_DATE in SOURCE_LABEL
