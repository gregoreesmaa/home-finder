"""Overturn dim for p362 probate delays (issue #233): tests.

Hermetic: fetch_probate_window is never called here (its contract --
single polite GET, file cache, TTL, transport errors raise -- is
covered via the pure cache_is_fresh helper plus the pure URL-builder
shape tests). The dim is tested on fixture AT probate-list XML
through the per-estate join shape: joined windows -> bands, missing
record/slice -> NULL with Estonian honesty markers.

Fixtures mirror the real parimisteated list layout observed
2026-09-13 but every person, notary, and number is SYNTHETIC --
never a real pull (repo hygiene: fixtures only, no scraped dumps,
no personal data).
"""

import os
from datetime import date

import dims_overturn_ata as overturn
from dims_overturn_ata import (
    ATA_PROBATE_TTL_DAYS,
    OVERTURN_ATA_DIMS,
    PROBATE_RESULT_CAP,
    RECHECK_AFTER,
    VERDICT_DATE,
    build_probate_list_url,
    build_probate_notice_url,
    cache_is_fresh,
    dim_probate_delay_overturn,
    is_archived,
    is_notary_publisher,
    needs_split,
    parse_kpv,
    parse_probate_list,
    score_overturn_ata,
)

TODAY = date(2026, 9, 13)

# ---------------------------------------------------------------------------
# Fixtures: real-shape AT probate LIST XML (synthetic entities).
# ---------------------------------------------------------------------------

FIXTURE_LIST_XML = """<?xml version='1.0' encoding='UTF-8'?>
<at:teadaanded xmlns:at="http://www.ametlikudteadaanded.ee/xsd/2014-06-01/teadaanne.xsd">
  <at:teadaanne>
    <version>1</version>
    <teate_number>9901001</teate_number>
    <id>9901101</id>
    <url>https://www.ametlikudteadaanded.ee/ee/Notar%20N%C3%A4idis/parimisteated/parimismenetluse-algatamine/2026/9/1/9901001</url>
    <liik>
      <kood>31</kood>
      <nimi>Pärimismenetluse algatamise teade</nimi>
    </liik>
    <andmeandja>
      <kood>10000991</kood>
      <nimi>Notar Näidis</nimi>
    </andmeandja>
    <puudutatud_isik>
      <liik>
        <kood>F</kood>
        <nimi>Füüsiline isik</nimi>
      </liik>
      <kood>EESNIDIS991</kood>
      <nimi>Näidisperekond</nimi>
      <eesnimi>Näide</eesnimi>
    </puudutatud_isik>
    <avaldamise_kpv>01.09.2026</avaldamise_kpv>
    <arhiveerimise_kpv>01.03.2027</arhiveerimise_kpv>
    <kinnitatud_sisu>&lt;div class="announcement-body"&gt;Pärimismenetlus
    algatatud. Avaldaja: Notar Näidis, Näidise tn 1, Tallinn.&lt;/div&gt;</kinnitatud_sisu>
    <sisendid>
      <sisendirida>
        <nimi>parandaja_surmakuupaev</nimi>
        <tyyp>date</tyyp>
        <vaartus>15.08.2026</vaartus>
        <objekti_id></objekti_id>
      </sisendirida>
      <sisendirida>
        <nimi>toestamise_tahtpaev</nimi>
        <tyyp>date</tyyp>
        <vaartus>01.12.2026</vaartus>
        <objekti_id></objekti_id>
      </sisendirida>
      <sisendirida>
        <nimi>parandaja_endine_nimi</nimi>
        <tyyp>text1</tyyp>
        <vaartus>Näidisperekond</vaartus>
        <objekti_id></objekti_id>
      </sisendirida>
    </sisendid>
  </at:teadaanne>
  <at:teadaanne>
    <version>1</version>
    <teate_number>9901002</teate_number>
    <id>9901102</id>
    <url>https://www.ametlikudteadaanded.ee/ee/Notar%20N%C3%A4idis/parimisteated/parimismenetluse-algatamine/2026/8/4/9901002</url>
    <liik>
      <kood>31</kood>
      <nimi>Pärimismenetluse algatamise teade</nimi>
    </liik>
    <andmeandja>
      <kood>10000991</kood>
      <nimi>Notar Näidis</nimi>
    </andmeandja>
    <avaldamise_kpv>04.08.2026</avaldamise_kpv>
    <arhiveerimise_kpv>04.08.2026</arhiveerimise_kpv>
    <kinnitatud_sisu>&lt;div&gt;Arhiveeritud menetlus.&lt;/div&gt;</kinnitatud_sisu>
  </at:teadaanne>
  <at:teadaanne>
    <version>1</version>
    <teate_number>9901003</teate_number>
    <liik>
      <kood>99</kood>
      <nimi>Muu teadaanne</nimi>
    </liik>
  </at:teadaanne>
</at:teadaanded>
"""

FIXTURE_SINGLE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<teadaanne>
  <teate_number>9902001</teate_number>
  <liik>
    <kood>31</kood>
    <nimi>Pärimismenetluse algatamise teade</nimi>
  </liik>
  <andmeandja>
    <nimi>Notar Üksik</nimi>
  </andmeandja>
  <avaldamise_kpv>10.09.2026</avaldamise_kpv>
  <arhiveerimise_kpv>10.03.2027</arhiveerimise_kpv>
</teadaanne>
"""


def _window(notices):
    return {"notices": notices}


def _parsed():
    return parse_probate_list(FIXTURE_LIST_XML, today=TODAY)


# ---------------------------------------------------------------------------
# URL builders: the documented URI-query shape (never fetched here).
# ---------------------------------------------------------------------------

def test_list_url_defaults_to_wildcard_probate_month_xml():
    assert (build_probate_list_url() ==
            "https://www.ametlikudteadaanded.ee/ee/-/parimisteated/"
            "parimismenetluse-algatamine/2026/9/xml")


def test_list_url_day_split_and_publisher_quoting():
    assert (build_probate_list_url(day=3) ==
            "https://www.ametlikudteadaanded.ee/ee/-/parimisteated/"
            "parimismenetluse-algatamine/2026/9/3/xml")
    assert (build_probate_list_url(publisher="Notar Näidis") ==
            "https://www.ametlikudteadaanded.ee/ee/Notar%20N%C3%A4idis/"
            "parimisteated/parimismenetluse-algatamine/2026/9/xml")


def test_notice_url_shape():
    assert (build_probate_notice_url("Notar Näidis", "parimisteated",
                                     "parimismenetluse-algatamine",
                                     2026, 9, 1, 9901001) ==
            "https://www.ametlikudteadaanded.ee/ee/Notar%20N%C3%A4idis/"
            "parimisteated/parimismenetluse-algatamine/2026/9/1/"
            "9901001/xml")


def test_needs_split_fires_only_at_the_documented_cap():
    assert PROBATE_RESULT_CAP == 1000
    assert needs_split(417) is False
    assert needs_split(999) is False
    assert needs_split(1000) is True
    assert needs_split(2500) is True


def test_window_ttl_is_weekly_and_cache_helper_is_pure(tmp_path):
    assert ATA_PROBATE_TTL_DAYS == 7
    missing = os.path.join(str(tmp_path), "nope.xml")
    assert cache_is_fresh(missing) is False
    fresh = os.path.join(str(tmp_path), "fresh.xml")
    with open(fresh, "w", encoding="utf-8") as f:
        f.write("<x/>")
    assert cache_is_fresh(fresh, ttl_days=7) is True
    assert cache_is_fresh(fresh, ttl_days=7, now=1e12) is False


# ---------------------------------------------------------------------------
# Parsing: real-shape list envelope, sparse records, dates.
# ---------------------------------------------------------------------------

def test_parse_list_reads_all_notices_with_currency():
    notices = _parsed()
    assert len(notices) == 3
    first, second, third = notices
    assert first["notice_id"] == "9901001"
    assert first["liik_nimi"] == "Pärimismenetluse algatamise teade"
    assert first["andmeandja"] == "Notar Näidis"
    assert first["avaldatud"] == "01.09.2026"
    assert first["archived"] is False
    assert second["archived"] is True
    assert third["archived"] is None
    assert is_notary_publisher(first) is True
    assert is_notary_publisher({"andmeandja": None}) is False


def test_parse_list_keeps_estate_join_inputs_runtime_only():
    first = _parsed()[0]
    assert first["parandaja"] == {
        "parandaja_surmakuupaev": "15.08.2026",
        "toestamise_tahtpaev": "01.12.2026",
        "parandaja_endine_nimi": "Näidisperekond",
    }
    assert "puudutatud" not in " ".join(first.keys())
    assert _parsed()[1]["parandaja"] is None


def test_parse_sparse_record_stays_none_safe():
    third = _parsed()[2]
    assert third["liik_nimi"] == "Muu teadaanne"
    assert third["andmeandja"] is None
    assert third["avaldatud"] is None
    assert third["sisu"] is None


def test_parse_single_notice_document():
    notices = parse_probate_list(FIXTURE_SINGLE_XML, today=TODAY)
    assert len(notices) == 1
    assert notices[0]["notice_id"] == "9902001"
    assert notices[0]["archived"] is False


def test_parse_kpv_and_archive_currency():
    assert parse_kpv("01.09.2026") == date(2026, 9, 1)
    assert parse_kpv("not-a-date") is None
    assert parse_kpv(None) is None
    assert parse_kpv("2026-09-01") is None
    assert is_archived("01.03.2027", today=TODAY) is False
    assert is_archived("04.08.2026", today=TODAY) is True
    assert is_archived(None, today=TODAY) is None
    assert is_archived("garbage", today=TODAY) is None


# ---------------------------------------------------------------------------
# Dim bands: scored-or-None over joined windows.
# ---------------------------------------------------------------------------

def test_active_initiation_is_strong_bad_never_zero():
    v, reason = dim_probate_delay_overturn(_window(_parsed()))
    assert v == 20
    assert v != 0
    assert "Pärimismenetluse algatamise teade" in reason
    assert "9901001" in reason
    assert "avaldaja: notar" in reason
    assert "mitte hinnang" in reason
    assert "notar kinnitab" in reason


def test_archived_only_scores_mid_with_count():
    notices = [n for n in _parsed() if n["archived"] is True]
    assert len(notices) == 1
    v, reason = dim_probate_delay_overturn(_window(notices))
    assert v == 60
    assert "1" in reason
    assert "mitte hinnang" in reason


def test_clean_window_is_weak_good_capped_never_proof():
    v, reason = dim_probate_delay_overturn(_window([]))
    assert v == 75
    assert v != 100
    assert "ülempiir 75" in reason
    assert "EI OLE puhta tiitli tõend" in reason
    assert "notar kinnitab" in reason


def test_missing_record_and_missing_list_stay_null_with_notary_check():
    for probate in (None, {}, {"notices": None}, {"nope": []}):
        v, reason = dim_probate_delay_overturn(probate)
        assert v is None
        assert "EI OLE" in reason
        assert "notar" in reason.lower()


def test_non_probate_only_window_is_drift_null():
    notices = [n for n in _parsed() if n["liik_nimi"] == "Muu teadaanne"]
    v, reason = dim_probate_delay_overturn(_window(notices))
    assert v is None
    assert "EI OLE" in reason
    assert "notar" in reason.lower()


def test_unknown_currency_stays_null():
    # Hand-built: probate type, archive date missing -> unknown currency.
    rec = {"notice_id": "9903001",
           "liik_nimi": "Pärimismenetluse algatamise teade",
           "andmeandja": "Notar Näidis",
           "avaldatud": "05.09.2026",
           "archived": None}
    v, reason = dim_probate_delay_overturn(_window([rec]))
    assert v is None
    assert "arhiivikuupäev" in reason
    assert "EI OLE" in reason


def test_mixed_window_answers_p362_from_the_probate_subset():
    # An active non-probate notice (other AT slices live in dims_p4_ata)
    # neither scores p362 nor blocks the probate answer.
    arest = {"notice_id": "9904001", "liik_nimi": "Vara arestimise teade",
             "andmeandja": "Kohtutäitur Näidis", "archived": False}
    archived_probate = [n for n in _parsed() if n["archived"] is True][0]
    v, _ = dim_probate_delay_overturn(_window([arest, archived_probate]))
    assert v == 60
    active_probate = [n for n in _parsed() if n["archived"] is False][0]
    v, _ = dim_probate_delay_overturn(_window([arest, active_probate]))
    assert v == 20


def test_reasons_never_echo_person_names_or_codes():
    seen = set()
    for notices in ([_parsed()[0]], [_parsed()[1]], [_parsed()[2]],
                    [], _parsed()):
        _, reason = dim_probate_delay_overturn(_window(notices))
        seen.add(reason)
    for probate in (None, {}, {"notices": None}):
        _, reason = dim_probate_delay_overturn(probate)
        seen.add(reason)
    for reason in seen:
        # Synthetic publisher + deceased names, person code, and
        # parandaja estate dates stay runtime-only.
        assert "Näidis" not in reason
        assert "EESNIDIS991" not in reason
        assert "15.08.2026" not in reason
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


# ---------------------------------------------------------------------------
# Registry + dated verdict.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_the_single_dim():
    assert [k for k, _, _ in OVERTURN_ATA_DIMS] == ["probate_delay_overturn"]
    assert [p for _, p, _ in OVERTURN_ATA_DIMS] == ["p362"]
    assert len({fn for _, _, fn in OVERTURN_ATA_DIMS}) == 1
    assert score_overturn_ata(_window([])) == {"probate_delay_overturn": 75}
    assert score_overturn_ata(_window(_parsed())) == {
        "probate_delay_overturn": 20}
    assert score_overturn_ata(None) == {"probate_delay_overturn": None}
    assert score_overturn_ata(None, {"id": "x"}) == {
        "probate_delay_overturn": None}
    assert overturn.OVERTURN_ATA_DIMS is OVERTURN_ATA_DIMS


def test_verdict_is_dated_with_recheck_note():
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2027-03-13"
    assert RECHECK_AFTER > VERDICT_DATE
