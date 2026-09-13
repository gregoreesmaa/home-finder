"""Overturn for G4 p361/p369 with free e-Ariregister bulk (issue #232): tests.

Hermetic: fetch_arireg_bulk_snapshot is never called against the
network here (its contract - polite single GETs, file cache, TTL,
transport errors never cached - is covered via the cache-hit path
and a stubbed opener serving in-memory zips). Every dim is tested
on fixture entity records through the join shape: joined rows ->
bands, missing record/slice -> NULL with Estonian honesty
markers.

Fixtures mirror the real RIK open-data layouts observed
2026-09-13 (Lihtandmed ';'-CSV header; Osanikud JSON company
objects with osanikud[] + osapandid_tingimuslikud_voorandamised[])
but every company, registry code, and person detail is
SYNTHETIC - never a real pull (repo hygiene: fixtures only, no
scraped dumps, no personal data).
"""

import io
import json
import os
import urllib.request
import zipfile

import dims_overturn_arireg as overturn
from dims_overturn_arireg import (
    ARIREG_TTL_S,
    FORM_AS,
    FORM_FIE,
    FORM_KU,
    FORM_OU,
    OVERTURN_ARIREG_DIMS,
    RECHECK_AFTER,
    VERDICT_DATE,
    dim_coop_approval,
    dim_trust_llc_transfer,
    fetch_arireg_bulk_snapshot,
    index_by_registry_code,
    iter_osanikud_companies,
    join_entity,
    parse_lihtandmed_csv,
    parse_osanikud_json,
    score_overturn_arireg,
)

OU = "Osa\xfching"
KU = "Korteri\xfchistu"
FIE = "F\xfc\u00fcsilisest isikust ettev\xf5tja"
TU = "T\xe4is\xfching"
MTU = "Mittetulundus\xfching"

CSV_HEADER = ("nimi;ariregistri_kood;ettevotja_oiguslik_vorm;"
              "ettevotja_oigusliku_vormi_alaliik;kmkr_nr;"
              "ettevotja_staatus;ettevotja_staatus_tekstina;"
              "ettevotja_esmakande_kpv;ettevotja_aadress;"
              "asukoht_ettevotja_aadressis;asukoha_ehak_kood;"
              "asukoha_ehak_tekstina;indeks_ettevotja_aadressis;"
              "ads_adr_id;ads_ads_oid;ads_normaliseeritud_taisaadress;"
              "teabesysteemi_link")


def _csv_row(code="81234567", name="N\xe4idis O\xdc",
             form=OU, status="R", addr="Tallinn"):
    return ("%s;%s;%s;;EE100000001;%s;Registrisse kantud;01.02.2020;"
            "%s;;0298;;10111;;;;https://ariregister.rik.ee/est/company/%s"
            % (name, code, form, status, addr, code))


def _write_zip(path, member, data: bytes):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, data)


def _sh(typ="F", own="L", pct=100.0):
    # Joined-entity shareholder shape (what join_entity carries;
    # raw Osanikud rows are built inline in the parser tests).
    return {"type": typ, "role": "OSAN",
            "ownership": own, "percent": pct}


def _entity(code="81234567", name="N\xe4idis O\xdc", form=OU,
            status="R", shareholders=None, pledges=False,
            holders_joined=True):
    basic = {"registry_code": code, "name": name, "legal_form": form,
             "form_subtype": None, "status": status,
             "status_text": "Registrisse kantud", "first_entry": None,
             "address": None, "ehak": None}
    holders = ({"registry_code": code, "name": name,
                "shareholders": list(shareholders or []),
                "pledges_present": pledges}
               if holders_joined else None)
    return join_entity(basic, holders)


def _ou_entity(n, **over):
    return _entity(shareholders=[_sh() for _ in range(n)], **over)


# ---------------------------------------------------------------------------
# Readers: real-schema fixtures, malformed rows skipped, None on no file.
# ---------------------------------------------------------------------------

def test_parse_lihtandmed_csv_reads_real_header(tmp_path):
    data = "\n".join([CSV_HEADER, _csv_row(), _csv_row("81234568")])
    zp = str(tmp_path / "liht.zip")
    _write_zip(zp, "ettevotja_rekvisiidid__lihtandmed.csv",
               ("\ufeff" + data).encode("utf-8"))
    snap = parse_lihtandmed_csv(zp)
    assert snap is not None
    by_code = index_by_registry_code(snap["companies"])
    assert by_code["81234567"]["legal_form"] == OU
    assert by_code["81234567"]["status"] == "R"
    assert by_code["81234568"]["name"] == "N\xe4idis O\xdc"


def test_parse_lihtandmed_csv_skips_bad_rows(tmp_path):
    data = "\n".join([CSV_HEADER, _csv_row(),
                      "katkine;;;;;;;",
                      _csv_row("  ", name="T\xfchjake")])
    zp = str(tmp_path / "liht.zip")
    _write_zip(zp, "m.csv", data.encode("utf-8"))
    snap = parse_lihtandmed_csv(zp)
    assert snap is not None
    assert [c["registry_code"] for c in snap["companies"]] == ["81234567"]


def test_parse_lihtandmed_csv_none_on_missing_or_garbage(tmp_path):
    assert parse_lihtandmed_csv(str(tmp_path / "nope.zip")) is None
    bad = str(tmp_path / "bad.zip")
    with open(bad, "wb") as fh:
        fh.write(b"not a zip")
    assert parse_lihtandmed_csv(bad) is None


def _holders_doc(companies):
    return json.dumps(companies, ensure_ascii=False)


def test_parse_osanikud_json_reads_real_keys(tmp_path):
    doc = _holders_doc([{
        "ariregistri_kood": 81234567, "nimi": "N\xe4idis O\xdc",
        "osanikud": [{"isiku_tyyp": "F", "isiku_roll": "OSAN",
                      "osaluse_omandiliik": "L",
                      "osaluse_protsent": "100.00", "kirje_id": 1}],
        "osapandid_tingimuslikud_voorandamised": []}])
    zp = str(tmp_path / "os.zip")
    _write_zip(zp, "ettevotja_rekvisiidid__osanikud.json",
               doc.encode("utf-8"))
    snap = parse_osanikud_json(zp)
    assert snap is not None
    assert len(snap["holders"]) == 1
    rec = snap["holders"][0]
    assert rec["registry_code"] == "81234567"
    assert rec["shareholders"] == [{"type": "F", "role": "OSAN",
                                    "ownership": "L", "percent": 100.0}]
    assert rec["pledges_present"] is False


def test_parse_osanikud_json_marks_pledges_and_skips_bad(tmp_path):
    doc = _holders_doc([
        {"ariregistri_kood": "81234567", "nimi": "A",
         "osanikud": [], "osapandid_tingimuslikud_voorandamised": [{"x": 1}]},
        {"nimi": "no code", "osanikud": []},
        {"ariregistri_kood": "81234569", "nimi": "B",
         "osanikud": [{"isiku_tyyp": "J", "isiku_roll": "O",
                       "osaluse_omandiliik": "Y",
                       "osaluse_protsent": "50,00"}],
         "osapandid_tingimuslikud_voorandamised": []}])
    zp = str(tmp_path / "os.zip")
    _write_zip(zp, "m.json", doc.encode("utf-8"))
    snap = parse_osanikud_json(zp)
    assert snap is not None
    assert len(snap["holders"]) == 2
    assert snap["holders"][0]["pledges_present"] is True
    assert snap["holders"][0]["shareholders"] == []
    assert snap["holders"][1]["shareholders"][0]["percent"] == 50.0


def test_parse_osanikud_json_limit_and_none(tmp_path):
    doc = _holders_doc([{"ariregistri_kood": str(80000000 + i),
                         "nimi": "N%d" % i, "osanikud": [],
                         "osapandid_tingimuslikud_voorandamised": []}
                        for i in range(5)])
    zp = str(tmp_path / "os.zip")
    _write_zip(zp, "m.json", doc.encode("utf-8"))
    assert len(parse_osanikud_json(zp, limit=2)["holders"]) == 2
    assert parse_osanikud_json(str(tmp_path / "nope.zip")) is None


def test_iter_osanikud_companies_split_chunk_parity():
    doc = _holders_doc([
        {"ariregistri_kood": 1, "nimi": "T\xf5\xf5stuse \xd5\xdc",
         "osanikud": [{"isiku_tyyp": "F", "s": "a}b\\c\"d"}],
         "osapandid_tingimuslikud_voorandamised": []},
        {"ariregistri_kood": 2, "nimi": "B", "osanikud": [],
         "osapandid_tingimuslikud_voorandamised": []}])

    class Chunks(io.StringIO):
        def __init__(self, s, n):
            super().__init__(s)
            self._n = n

        def read(self, size=-1):
            return super().read(self._n)

    whole = list(iter_osanikud_companies(io.StringIO(doc)))
    split = list(iter_osanikud_companies(Chunks(doc, 7)))
    assert len(whole) == 2 == len(split)
    assert [json.loads(r)["ariregistri_kood"] for r in split] == [1, 2]
    assert json.loads(split[0])["nimi"] == "T\xf5\xf5stuse \xd5\xdc"


def test_join_entity_partial_snapshot_is_honest():
    basic = {"registry_code": "81234567", "name": "N", "legal_form": OU,
             "status": "R"}
    assert join_entity(None, None) is None
    ent = join_entity(basic, None)
    assert ent["shareholders"] == []
    assert ent["pledges_present"] is False
    assert ent["holders_joined"] is False


# ---------------------------------------------------------------------------
# Fetch: cache-hit performs no request; transport errors never cached.
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, body: bytes, ctype="application/zip"):
        self._body = body
        self.headers = {"Content-Type": ctype}
        self.status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *a):
        return self._body


def _boom(req, timeout=None):
    raise AssertionError("network touched in hermetic test")


def test_fetch_cache_hit_returns_paths_without_request(tmp_path):
    for fn in ("arireg-lihtandmed.csv.zip", "arireg-osanikud.json.zip"):
        with open(os.path.join(str(tmp_path), fn), "wb") as fh:
            fh.write(b"PK\x03\x04cached")
    real = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        got = fetch_arireg_bulk_snapshot(str(tmp_path))
    finally:
        urllib.request.urlopen = real
    assert got is not None
    assert set(got) == {"lihtandmed", "osanikud"}


def test_fetch_stores_only_zip_and_skips_errors(tmp_path):
    real = urllib.request.urlopen

    def fake(req, timeout=None):
        url = req.full_url
        if "lihtandmed" in url:
            with io.BytesIO() as buf:
                with zipfile.ZipFile(buf, "w") as zf:
                    zf.writestr("m.csv", CSV_HEADER + "\n")
                return _FakeResp(buf.getvalue())
        if "osanikud" in url:
            return _FakeResp(b"<html>no</html>", ctype="text/html")
        raise IOError("down")

    urllib.request.urlopen = fake
    try:
        got = fetch_arireg_bulk_snapshot(str(tmp_path), ttl_s=0)
    finally:
        urllib.request.urlopen = real
    assert got is not None and set(got) == {"lihtandmed"}
    assert parse_lihtandmed_csv(got["lihtandmed"]) == {"companies": []}


def test_fetch_all_errors_returns_none(tmp_path):
    real = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        assert fetch_arireg_bulk_snapshot(
            str(tmp_path), ttl_s=0,
            base_url="http://127.0.0.1:9") is None
    finally:
        urllib.request.urlopen = real


# ---------------------------------------------------------------------------
# p361: status blocks, OÜ shape bands, paid-fact NULLs.
# ---------------------------------------------------------------------------

def test_p361_status_blocks_override_shape():
    v, reason = dim_trust_llc_transfer(_ou_entity(1, status="N"))
    assert v == 10
    assert "hinnang" in reason and "pankrotis" in reason
    v, reason = dim_trust_llc_transfer(_ou_entity(1, status="L"))
    assert v == 20
    assert "hinnang" in reason and "likvideerimisel" in reason


def test_p361_ou_shape_bands():
    assert dim_trust_llc_transfer(_ou_entity(1))[0] == 75
    assert dim_trust_llc_transfer(_ou_entity(2))[0] == 65
    assert dim_trust_llc_transfer(_ou_entity(3))[0] == 55
    assert dim_trust_llc_transfer(_ou_entity(4))[0] == 55
    assert dim_trust_llc_transfer(_ou_entity(9))[0] == 45


def test_p361_joint_and_corp_haircuts_and_floor():
    v, reason = dim_trust_llc_transfer(
        _entity(shareholders=[_sh(own="Y"), _sh()]))
    assert v == 55  # 65 - 10 joint
    assert "\u00fchis/kaasomand" in reason
    v, reason = dim_trust_llc_transfer(
        _entity(shareholders=[_sh(typ="J"), _sh()]))
    assert v == 60  # 65 - 5 layered
    assert "juriidilisest isikust osanik" in reason
    v, _ = dim_trust_llc_transfer(
        _entity(shareholders=[_sh(typ="J", own="K") for _ in range(9)]))
    assert v >= 25  # floor holds


def test_p361_pledge_caps_shape():
    v, reason = dim_trust_llc_transfer(_ou_entity(1, pledges=True))
    assert v == 40
    assert "osapant" in reason


def test_p361_fie_flat_capped():
    v, reason = dim_trust_llc_transfer(_entity(form=FIE, status="R"))
    assert v == 70
    assert "hinnang" in reason and "\u00fclempiir 70" in reason


def test_p361_scored_reasons_carry_honesty_markers():
    for ent in (_ou_entity(1), _entity(form=FIE, status="R"),
                _ou_entity(1, status="L")):
        _, reason = dim_trust_llc_transfer(ent)
        assert "hinnang" in reason
        assert "EI OLE" not in reason
        assert "m\xf5\xf5detud" not in reason
        assert "garanteeritud" not in reason
        assert "notari" in reason


def test_p361_paid_fact_nulls_name_the_missing_register():
    v, reason = dim_trust_llc_transfer(_entity(form=FORM_AS, status="R"))
    assert v is None
    assert "EI OLE" in reason and "v\xe4\xe4rtpaberikeskuse" in reason
    v, reason = dim_trust_llc_transfer(_entity(form=TU, status="R"))
    assert v is None
    assert "EI OLE" in reason and "kaardile kantud isikute" in reason
    v, reason = dim_trust_llc_transfer(_entity(form=MTU, status="R"))
    assert v is None
    assert "EI OLE" in reason and "notari" in reason
    v, reason = dim_trust_llc_transfer(
        _entity(form=FORM_KU, status="R"))
    assert v is None
    assert "p369" in reason


def test_p361_unresolvable_stays_none_with_check_reason():
    for ent in (None, {}, {"name": "X"}, _entity(status=None),
                _entity(form=None, status="R"),
                _entity(shareholders=[], holders_joined=True),
                _entity(holders_joined=False)):
        v, reason = dim_trust_llc_transfer(ent)
        assert v is None
        assert "EI OLE" in reason
    _, reason = dim_trust_llc_transfer(None)
    assert "ariregister.rik.ee" in reason
    _, reason = dim_trust_llc_transfer(_entity(holders_joined=False))
    assert "puudumine ei ole puhtus" in reason


# ---------------------------------------------------------------------------
# p369: always NULL, KÜ echo proves the wiring.
# ---------------------------------------------------------------------------

def test_p369_always_none_for_every_input():
    ku = _entity(form=KU, status="R",
                 name="N\xe4idis K\xdc 12345678")
    for ent in (None, {}, ku,
                _entity(form=KU, status="L"),
                _entity(form=KU, status="N"),
                _entity(form=OU, status="R")):
        v, _ = dim_coop_approval(ent)
        assert v is None


def test_p369_echoes_joined_ku_identity():
    _, reason = dim_coop_approval(
        _entity(code="80123456", name="N\xe4idis K\xdc",
                form=KU, status="R"))
    assert "EI OLE" in reason
    assert "80123456" in reason
    assert "N\xe4idis K\xdc" in reason
    assert "p\xf5hikirja" in reason
    assert "kirjalikku" in reason
    assert "m\xf5\xf5detud" not in reason
    assert "garanteeritud" not in reason


def test_p369_distresses_and_non_ku_reasons():
    _, reason = dim_coop_approval(_entity(form=KU, status="L"))
    assert "likvideerimisel" in reason and "EI OLE" in reason
    _, reason = dim_coop_approval(_entity(form=KU, status="N"))
    assert "pankrotis" in reason and "EI OLE" in reason
    _, reason = dim_coop_approval(_entity(form=OU, status="R"))
    assert "25 648" in reason
    _, reason = dim_coop_approval(None)
    assert "ariregister.rik.ee" in reason


# ---------------------------------------------------------------------------
# Registry, aggregator, verdict dates.
# ---------------------------------------------------------------------------

def test_constants_pin_ttl_and_verdict_dates():
    assert ARIREG_TTL_S == 7 * 24 * 3600
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2027-03-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_form_constants_match_live_dump_spellings():
    # Exact ettevotja_oiguslik_vorm values from the 2026-09-13
    # Lihtandmed dump (377 730 rows) - a misspelled constant
    # silently NULLs a whole legal form (caught FIE here pre-PR).
    assert FORM_OU == "Osaühing"
    assert FORM_AS == "Aktsiaselts"
    assert FORM_KU == "Korteriühistu"
    assert FORM_FIE == "Füüsilisest isikust ettevõtja"
    assert overturn.FORM_PARTNERSHIPS == ("Täisühing", "Usaldusühing")
    assert (overturn.STATUS_REGISTERED, overturn.STATUS_LIQUIDATION,
            overturn.STATUS_BANKRUPT) == ("R", "L", "N")


def test_registry_and_aggregator_cover_both_dims():
    assert [k for k, _, _ in OVERTURN_ARIREG_DIMS] == [
        "trust_llc_transfer", "coop_approval"]
    assert [p for _, p, _ in OVERTURN_ARIREG_DIMS] == ["p361", "p369"]
    assert len({fn for _, _, fn in OVERTURN_ARIREG_DIMS}) == 2
    ent = _ou_entity(1)
    assert score_overturn_arireg(ent) == {
        "trust_llc_transfer": 75, "coop_approval": None}
    assert score_overturn_arireg(None) == {
        "trust_llc_transfer": None, "coop_approval": None}
    assert overturn.OVERTURN_ARIREG_DIMS is OVERTURN_ARIREG_DIMS
    assert FORM_OU == OU and FORM_KU == KU and FORM_FIE == FIE
    assert FORM_AS == "Aktsiaselts"

