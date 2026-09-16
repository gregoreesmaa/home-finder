"""Flood Harju-coverage verdict (issue #518): hermetic tests.

No network: the polite probe is covered via a stubbed opener
(hits body -> count; transport error / non-200 / garbage ->
None, never a zero); legend/verdict builders run on hand-built
zone rows. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_flood_harju.py -q
"""

import urllib.request

import dims_flood_harju as H
from dims_flood_harju import (
    HARJU_BBOX,
    KNOWN_ZONES,
    RECHECK_AFTER,
    VERDICT_DATE,
    VERDICT_DIMS,
    coverage_legend,
    harju_verdict,
    probe_harju_hits,
)


def _stub_opener(body: bytes, status: int = 200):
    class _Resp:
        def __init__(self):
            self.status = status
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _open(req, timeout=None):
        assert "home-finder" in req.get_header("User-agent")
        assert "resultType=hits" in req.full_url
        assert "kr_yleujutusohuga_ala" in req.full_url
        return _Resp()

    return _open


def _boom(req, timeout=None):
    raise TimeoutError("no network in unit tests")


def test_probe_parses_harju_zero():
    body = (b'<?xml version="1.0"?><wfs:FeatureCollection '
            b'numberMatched="0" numberReturned="0">')
    assert probe_harju_hits(opener=_stub_opener(body)) == 0


def test_probe_parses_positive_count():
    body = (b'<wfs:FeatureCollection numberMatched="12" '
            b'numberReturned="0">')
    assert probe_harju_hits(opener=_stub_opener(body)) == 12


def test_probe_transport_error_is_unknown_not_zero():
    assert probe_harju_hits(opener=_boom) is None


def test_probe_non_200_is_unknown():
    body = b"Service Unavailable"
    assert probe_harju_hits(opener=_stub_opener(body, status=503)) is None


def test_probe_garbage_body_is_unknown():
    assert probe_harju_hits(opener=_stub_opener(b"<html>nope")) is None


def test_probe_is_network_free_by_default(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    # Default opener path resolves at call time; stub urlopen to
    # prove the production call goes through exactly one GET.
    calls = []

    class _Resp:
        status = 200

        def read(self):
            return b'<wfs:FeatureCollection numberMatched="0" />'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _one(req, timeout=None):
        calls.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _one)
    assert H.probe_harju_hits() == 0
    assert len(calls) == 1


def test_legend_names_sidecar_zones_and_states_harju_gap():
    zones = [{"nimi": KNOWN_ZONES[0]}, {"nimi": KNOWN_ZONES[1]}]
    legend = coverage_legend(zones)
    assert KNOWN_ZONES[0] in legend
    assert KNOWN_ZONES[1] in legend
    assert "Harjumaal" in legend
    assert "EI OLE" in legend
    assert "ausalt tühi" in legend
    assert VERDICT_DATE in legend
    assert RECHECK_AFTER in legend


def test_legend_empty_sidecar_is_honest_empty():
    legend = coverage_legend([])
    assert "EI OLE" in legend
    assert "Tallinn on ausalt tühi" in legend
    # No invented zones: a Tallinn name absent from input never appears.
    assert "Pirita" in legend  # only inside the gap sentence...
    assert "kattes: EI OLE" in legend


def test_legend_skips_unlabelled_and_fictitious_rows():
    zones = [{}, {"nimi": "   "},
             {"nimi": "Fixture laht (fiktiivne)"},
             {"nimi": KNOWN_ZONES[0]}]
    legend = coverage_legend(zones)
    assert "Fixture" not in legend
    assert "fiktiivne" not in legend.lower()
    assert KNOWN_ZONES[0] in legend


def test_legend_never_invents_unlisted_tallinn_zone():
    legend = coverage_legend([{"nimi": KNOWN_ZONES[0]}])
    assert "Tallinna laht (väljamõeldis)" not in legend
    assert "Pirita jõgi" in legend  # gap sentence only
    assert legend.count(KNOWN_ZONES[0]) == 1


def test_verdict_states_zero_harju_and_open_coastal_family():
    text = harju_verdict()
    assert "#518" in text
    assert "numberMatched=0" in text
    assert "EI leiutata" in text
    assert "LAHTINE" in text
    assert RECHECK_AFTER in text


def test_harju_bbox_covers_pirita_and_coast():
    lat0, lon0, lat1, lon1 = HARJU_BBOX
    # Pirita river mouth + Tallinn bay sit inside the window.
    assert lat0 <= 59.45 <= lat1 and lon0 <= 24.83 <= lon1
    assert VERDICT_DIMS == ("flood_harju_verdict",)
