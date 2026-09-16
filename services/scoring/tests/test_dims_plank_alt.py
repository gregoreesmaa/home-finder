"""PLANK/TPR alternative-source verdict (issue #519): hermetic tests.

No network: the polite capabilities read is covered via a stubbed
opener (layer list -> names; transport error / non-200 / nameless
body -> None, never an empty service); the marker scan and the
empty-UX copy run on hand-built inputs. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_plank_alt.py -q
"""

import urllib.request

import dims_plank_alt as P
from dims_plank_alt import (
    AKS_SERVED_FAMILIES,
    AKS_WMS_URL,
    RECHECK_AFTER,
    VERDICT_DATE,
    VERDICT_DIMS,
    empty_ux_copy,
    has_planning_layer,
    null_verdict,
    probe_aks_capabilities,
)

# Family sample mirroring the real 2026-09-16 AKS document
# (address + cadastre + POI names only, zero planning names).
AKS_SAMPLE = ["HARIDUS", "ads_aadr", "ads_ky", "knr_ehitised",
              "knr_maakate", "poi_paastekomando", "poi_parkla",
              "TRANSPORT", "WMS"]

CAP_XML = ("<WMS_Capabilities><Capability><Layer>"
           "<Name>ads_aadr</Name><Name>knr_ehitised</Name>"
           "<Name>poi_parkla</Name></Layer></Capability>"
           "</WMS_Capabilities>").encode("utf-8")


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
        assert "GetCapabilities" in req.full_url
        assert req.full_url.startswith(AKS_WMS_URL)
        return _Resp()

    return _open


def _boom(req, timeout=None):
    raise TimeoutError("no network in unit tests")


def test_probe_returns_sorted_names():
    assert probe_aks_capabilities(opener=_stub_opener(CAP_XML)) == [
        "ads_aadr", "knr_ehitised", "poi_parkla"]


def test_probe_transport_error_is_unknown():
    assert probe_aks_capabilities(opener=_boom) is None


def test_probe_non_200_is_unknown():
    assert probe_aks_capabilities(
        opener=_stub_opener(b"Service Unavailable", status=503)) is None


def test_probe_nameless_body_is_unknown_not_empty_service():
    assert probe_aks_capabilities(
        opener=_stub_opener(b"<html>no layers here")) is None


def test_probe_single_get(monkeypatch):
    calls = []

    class _Resp:
        status = 200

        def read(self):
            return CAP_XML

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _one(req, timeout=None):
        calls.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _one)
    assert P.probe_aks_capabilities() == [
        "ads_aadr", "knr_ehitised", "poi_parkla"]
    assert len(calls) == 1


def test_real_aks_sample_has_no_planning_layer():
    assert not has_planning_layer(AKS_SAMPLE)


def test_markers_catch_unenumerated_variants():
    assert has_planning_layer(["KETERINA_detailplaan"])  # typo variant
    assert has_planning_layer(["TallinnaKehtivadPlaneeringud"])
    assert has_planning_layer(["PLANK_WFS2"])
    assert has_planning_layer(["tpr_register"])
    assert has_planning_layer(["sihtotstarbed_wfs"])


def test_marker_scan_unknown_input_is_false():
    assert not has_planning_layer(None)
    assert not has_planning_layer("planeeringud")
    assert not has_planning_layer([])


def test_empty_ux_explains_missing_and_why():
    copy = empty_ux_copy()
    assert "PLANK" in copy["body"]
    assert "TPR" in copy["body"]
    assert "Maa-amet" in copy["body"] or "MAA-amet" in copy["body"]
    assert "EI OLE" in copy["body"]
    assert VERDICT_DATE in copy["body"]
    assert VERDICT_DATE in copy["source"]
    assert RECHECK_AFTER in copy["source"]
    assert "tasulisse registrisse" in copy["body"]


def test_empty_ux_ships_zero_polygons():
    copy = empty_ux_copy()
    assert copy["polygons"] == ""
    assert "title" in copy and copy["title"]


def test_null_verdict_accepts_null_and_names_next_step():
    text = null_verdict()
    assert "#519" in text
    assert "EI leiutata" in text
    assert "E-ehituse" in text
    assert "Katerina" in text
    assert RECHECK_AFTER in text
    assert AKS_SERVED_FAMILIES[0].startswith("ads_")
    assert VERDICT_DIMS == ("plank_alt_verdict",)
