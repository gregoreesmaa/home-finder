"""P4 Ametlikud Teadaanded demo + coverage dims (issues #254, #335): tests.

Hermetic: fetch_notice_xml is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus the pure
build_notice_url shape test). Every dim is tested on fixture AT
records through the per-entity join shape: joined notices -> bands,
missing record/slice -> NULL with Estonian honesty markers.

Fixtures mirror the real teadaanne XML layout observed 2026-09-13
but every person, company, and number is SYNTHETIC — never a real
pull (repo hygiene: fixtures only, no scraped dumps).
"""

import os
from datetime import date

import dims_p4_ata as ata
from dims_p4_ata import (
    ATA_TTL_DAYS,
    P4_ATA_DIMS,
    P4_ATA_LINK_DIMS,
    build_notice_url,
    cache_is_fresh,
    dim_cadastre,
    dim_developer_track,
    dim_enforcement,
    dim_felling,
    dim_kinnistus_checkpoint,
    dim_quarry,
    dim_zoning,
    is_archived,
    land_family,
    mentions_tallinn,
    parse_kpv,
    parse_notice_xml,
    score_p4_ata,
    score_p4_ata_link,
)

TODAY = date(2026, 9, 13)

# ---------------------------------------------------------------------------
# Fixtures: real-shape AT XML (synthetic entities) + joined records.
# ---------------------------------------------------------------------------

FIXTURE_XML_PANKROT = """<?xml version='1.0' encoding='UTF-8'?>
<at:teadaanne xmlns:at="http://www.ametlikudteadaanded.ee/xsd/2014-06-01/teadaanne.xsd">
  <version>1</version>
  <teate_number>9900111</teate_number>
  <id>9900222</id>
  <url>https://www.ametlikudteadaanded.ee/ee/kohtutaitur/nadide-kohtutaitur/pankrot/2026/9/1/9900111</url>
  <liik>
    <kood>25</kood>
    <nimi>Pankrotimenetluses kinnisasja enampakkumise teade</nimi>
  </liik>
  <mall>
    <kood>26</kood>
    <nimi>Pankroti enampakkumise teade (PankrS)</nimi>
  </mall>
  <andmeandja>
    <kood>10000001</kood>
    <nimi>Näidiko Kohtutäitur</nimi>
  </andmeandja>
  <puudutatud_isik>
    <liik>
      <kood>J</kood>
      <nimi>Juriidiline isik</nimi>
    </liik>
    <kood>12345678</kood>
    <koodi_riik>EST</koodi_riik>
    <nimi>OÜ NÄIDISARENDAJA</nimi>
    <eesnimi></eesnimi>
  </puudutatud_isik>
  <avaldamise_kpv>01.09.2026</avaldamise_kpv>
  <arhiveerimise_kpv>01.09.2027</arhiveerimise_kpv>
  <kinnitatud_sisu>&lt;div class="announcement-body"&gt;Vara asub Tallinn,
  HARJUMAA, Näidise tn 1. Alghind 100000 eurot.&lt;/div&gt;</kinnitatud_sisu>
  <sisendid>
    <sisendirida>
      <nimi>alghind</nimi>
      <tyyp>text1</tyyp>
      <vaartus>100000</vaartus>
      <objekti_id></objekti_id>
    </sisendirida>
  </sisendid>
  <sisendid>
    <sisendirida>
      <nimi>teine-sisend</nimi>
      <tyyp>text1</tyyp>
      <vaartus>100000</vaartus>
      <objekti_id></objekti_id>
    </sisendirida>
  </sisendid>
</at:teadaanne>
"""

FIXTURE_XML_SPARSE = """<?xml version='1.0' encoding='UTF-8'?>
<teadaanne>
  <teate_number>9900333</teate_number>
  <liik>
    <kood>18</kood>
    <nimi>Vara arestimise teade</nimi>
  </liik>
</teadaanne>
"""


def _notice(liik="Pankroti väljakuulutamise teade", archived=False,
            notice_id="9900111", **extra):
    rec = {
        "notice_id": notice_id,
        "url": "https://www.ametlikudteadaanded.ee/ee/x/%s" % notice_id,
        "liik_kood": "25",
        "liik_nimi": liik,
        "mall_nimi": None,
        "andmeandja": "Näidiko Kohtutäitur",
        "puudutatud_nimi": "OÜ Näidisarendaja",
        "puudutatud_kood": None,
        "avaldatud": "01.09.2026",
        "arhiveeritud": "01.09.2027" if not archived else "01.01.2020",
        "archived": archived,
        "sisu": "Vara asub Tallinn, Näidise tn 1.",
    }
    rec.update(extra)
    return rec


CLEAN_ATA = {"entity": "OÜ Näidisarendaja", "tallinn": True, "notices": []}

ALL_FNS = [fn for _, _, fn in P4_ATA_DIMS]

EXPECTED_KEYS = ["enforcement", "kinnistus_checkpoint", "developer_track"]
EXPECTED_PNUMS = ["P4-020", "P4-004", "P4-021"]


# ---------------------------------------------------------------------------
# Ingestion: parse + URL shape + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_full_shape_pankrot_xml():
    rec = parse_notice_xml(FIXTURE_XML_PANKROT, today=TODAY)
    assert rec["notice_id"] == "9900111"
    assert rec["liik_nimi"] == \
        "Pankrotimenetluses kinnisasja enampakkumise teade"
    assert rec["liik_kood"] == "25"
    assert rec["andmeandja"] == "Näidiko Kohtutäitur"
    assert rec["puudutatud_nimi"] == "OÜ NÄIDISARENDAJA"
    assert rec["avaldatud"] == "01.09.2026"
    assert rec["archived"] is False  # archive date in the future
    assert rec["sisu"] is not None and "Tallinn" in rec["sisu"]
    assert "<div" not in rec["sisu"]  # escaped HTML stripped
    assert mentions_tallinn(rec) is True


def test_parse_sparse_xml_missing_is_none():
    rec = parse_notice_xml(FIXTURE_XML_SPARSE, today=TODAY)
    assert rec["notice_id"] == "9900333"
    assert rec["liik_nimi"] == "Vara arestimise teade"
    assert rec["andmeandja"] is None
    assert rec["puudutatud_nimi"] is None
    assert rec["avaldatud"] is None
    assert rec["sisu"] is None
    assert rec["archived"] is None  # unknown currency, never guessed
    assert mentions_tallinn(rec) is False


def test_parse_kpv_and_archived_helpers():
    assert parse_kpv("13.06.2019") == date(2019, 6, 13)
    assert parse_kpv("") is None
    assert parse_kpv("pole-kuupäev") is None
    assert parse_kpv(None) is None
    assert is_archived("01.09.2027", today=TODAY) is False
    assert is_archived("01.01.2020", today=TODAY) is True
    assert is_archived(None, today=TODAY) is None
    assert is_archived("katki", today=TODAY) is None


def test_build_notice_url_matches_documented_scheme():
    url = build_notice_url("eesti-advokatuur", "advokatuur",
                           "advokaadi-kutsetegevuse-peatamine",
                           2019, 6, 13, 1483034)
    assert url == ("https://www.ametlikudteadaanded.ee/ee/eesti-advokatuur/"
                   "advokatuur/advokaadi-kutsetegevuse-peatamine/"
                   "2019/6/13/1483034/xml")


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert ATA_TTL_DAYS == 1  # daily pulls per docs/p4_ata.md
    missing = os.path.join(str(tmp_path), "ata-x.xml")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "ata-x.xml"
    p.write_text("<teadaanne/>", encoding="utf-8")
    assert cache_is_fresh(str(p), ttl_days=1) is True
    aged = 2 * 86400.0
    assert cache_is_fresh(str(p), ttl_days=1,
                          now=os.path.getmtime(str(p)) + aged) is False


# ---------------------------------------------------------------------------
# NULL contracts: missing record / scope / list is always NULL.
# ---------------------------------------------------------------------------

def test_all_dims_null_without_record_and_name_source():
    for fn in ALL_FNS:
        v, reason = fn(None)
        assert v is None, fn.__name__
        assert "Teadaann" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_all_dims_accept_missing_listing_side():
    for fn in ALL_FNS:
        ata_rec = {"entity": "OÜ Näidisarendaja", "tallinn": True,
                   "notices": []}
        v, reason = fn(ata_rec)  # listing=None must never crash
        assert isinstance(reason, str) and reason, fn.__name__
        assert v is None or isinstance(v, int)


def test_tallinn_gate_nulls_non_tallinn_joins():
    rec = {"entity": "OÜ Näidisarendaja", "tallinn": False,
           "notices": [_notice()]}
    for fn in ALL_FNS:
        v, reason = fn(rec)
        assert v is None, fn.__name__
        assert "Tallinn" in reason, fn.__name__


def test_missing_notice_list_is_null_not_clean():
    for fn in ALL_FNS:
        v, reason = fn({"entity": "OÜ Näidisarendaja", "tallinn": True})
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_scored_reasons_trace_to_notices():
    scored = [
        (dim_enforcement, {"tallinn": True,
                           "notices": [_notice()]}, None),
        (dim_kinnistus_checkpoint, {"tallinn": True, "notices": [
            _notice(liik="Vara arestimise teade")]}, None),
        (dim_developer_track, {"entity": "OÜ Näidisarendaja",
                               "tallinn": True,
                               "notices": [_notice()]}, None),
    ]
    for fn, rec, listing in scored:
        v, reason = fn(rec, listing)
        assert isinstance(v, int), fn.__name__
        assert 0 <= v <= 100, fn.__name__
        assert "Teadaann" in reason, fn.__name__


# ---------------------------------------------------------------------------
# P4-020 demo bands.
# ---------------------------------------------------------------------------

def test_p4020_active_enforcement_is_strong_bad():
    for liik in ("Pankroti väljakuulutamise teade",
                 "Kohtutäituri täitemenetluse teade",
                 "Vara arestimise teade"):
        v, reason = dim_enforcement(
            {"tallinn": True, "notices": [_notice(liik=liik)]})
        assert v == 15, liik
        assert "külmutatud" in reason, liik


def test_p4020_auction_is_caution_not_bad():
    v, reason = dim_enforcement(
        {"tallinn": True,
         "notices": [_notice(liik="Kinnisasja enampakkumise teade")]})
    assert v == 45
    assert "sundmüügi" in reason


def test_p4020_unknown_type_and_currency_stay_null():
    v, reason = dim_enforcement(
        {"tallinn": True,
         "notices": [_notice(liik="Mingi muu teade nr 7")]})
    assert v is None and "Tundmatu" in reason
    v, reason = dim_enforcement(
        {"tallinn": True,
         "notices": [_notice(archived=None, arhiveeritud=None)]})
    assert v is None and "kehtivus teadmata" in reason


def test_p4020_archived_only_and_clean():
    v, reason = dim_enforcement(
        {"tallinn": True, "notices": [_notice(archived=True)]})
    assert v == 55 and "arhiveeritud" in reason
    v, reason = dim_enforcement(CLEAN_ATA)
    assert v == 75
    assert "EI OLE puhta tiitli" in reason  # capped, never proof


# ---------------------------------------------------------------------------
# P4-004 coverage bands.
# ---------------------------------------------------------------------------

def test_p4004_active_restriction_points_to_notary():
    v, reason = dim_kinnistus_checkpoint(
        {"tallinn": True,
         "notices": [_notice(liik="Keelumärke seadmise teade")]})
    assert v == 20
    assert "notar" in reason
    v, reason = dim_kinnistus_checkpoint(
        {"tallinn": True,
         "notices": [_notice(liik="Kinnisasja enampakkumise teade")]})
    assert v == 50 and "notar" in reason


def test_p4004_archived_unknown_and_clean():
    v, reason = dim_kinnistus_checkpoint(
        {"tallinn": True,
         "notices": [_notice(liik="Vara arestimise teade",
                             archived=True)]})
    assert v == 60 and "notar" in reason
    v, reason = dim_kinnistus_checkpoint(
        {"tallinn": True,
         "notices": [_notice(liik="Mingi muu teade nr 7")]})
    assert v is None and "Tundmatu" in reason
    v, reason = dim_kinnistus_checkpoint(
        {"tallinn": True, "notices": []})
    assert v == 75 and "notar" in reason
    assert "EI OLE puhta tiitli" in reason


# ---------------------------------------------------------------------------
# P4-021 coverage bands (AT developer-notice slice; EHR slice separate).
# ---------------------------------------------------------------------------

def test_p4021_missing_entity_is_null():
    v, reason = dim_developer_track({"tallinn": True, "notices": []})
    assert v is None and "EI OLE" in reason


def test_p4021_active_developer_case_is_strong_bad():
    v, reason = dim_developer_track(
        {"entity": "OÜ Näidisarendaja", "tallinn": True,
         "notices": [_notice()]})
    assert v == 20
    assert "TTJA" in reason
    v, reason = dim_developer_track(
        {"entity": "OÜ Näidisarendaja", "tallinn": True,
         "notices": [_notice(liik="Vara arestimise teade")]})
    assert v == 45


def test_p4021_archived_unknown_and_clean_capped():
    v, reason = dim_developer_track(
        {"entity": "OÜ Näidisarendaja", "tallinn": True,
         "notices": [_notice(archived=True)]})
    assert v == 60 and "TTJA" in reason
    v, reason = dim_developer_track(
        {"entity": "OÜ Näidisarendaja", "tallinn": True,
         "notices": [_notice(liik="Mingi muu teade nr 7")]})
    assert v is None and "Tundmatu" in reason
    v, reason = dim_developer_track(
        {"entity": "OÜ Näidisarendaja", "tallinn": True, "notices": []})
    assert v == 75
    assert "ülempiir 75" in reason  # capped, never "trusted seller"


# ---------------------------------------------------------------------------
# Registry + aggregator cover all 3.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_all_3():
    assert [k for k, _, _ in P4_ATA_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_ATA_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_ATA_DIMS}) == 3
    out = score_p4_ata({"entity": "OÜ Näidisarendaja", "tallinn": True,
                        "notices": [_notice()]})
    assert set(out) == set(EXPECTED_KEYS)
    assert out["enforcement"] == 15
    assert out["kinnistus_checkpoint"] == 20
    assert out["developer_track"] == 20
    assert score_p4_ata(None) == {k: None for k in EXPECTED_KEYS}
    assert ata.P4_ATA_DIMS is P4_ATA_DIMS


# ---------------------------------------------------------------------------
# Issue #628: parcel-linked land dims (linkage before flags).
# ---------------------------------------------------------------------------

def _land_notice(liik, tunnused=(), archived=False, notice_id="9900444"):
    return _notice(liik=liik, archived=archived, notice_id=notice_id,
                   tunnused=list(tunnused))


LINK_KEYS = ["quarry", "zoning", "cadastre", "felling"]


def test_land_family_stems():
    assert land_family({"liik_nimi": "Kaevandamisloa andmise teade"}) == "quarry"
    assert land_family({"liik_nimi": "Detailplaneeringu algatamine"}) == "zoning"
    assert land_family({"liik_nimi": "Kinnistusraamatu kanne"}) == "cadastre"
    assert land_family({"liik_nimi": "Metsateatis raieks"}) == "felling"
    assert land_family({"liik_nimi": "Pankroti väljakuulutamine"}) is None
    assert land_family({}) is None


def test_link_dims_flag_on_tunnus_match():
    listing = {"tunnus": "78401:107:0760"}
    ata_q = {"tallinn": True, "notices": [
        _land_notice("Kaevandamisloa andmise teade",
                     ["78401:107:0760"])]}
    v, reason = dim_quarry(ata_q, listing)
    assert v == 35
    assert "78401:107:0760" in reason and "seos" in reason
    ata_z = {"tallinn": True, "notices": [
        _land_notice("Detailplaneeringu kehtestamine",
                     ["78401:107:0760"])]}
    assert dim_zoning(ata_z, listing)[0] == 55
    ata_c = {"tallinn": True, "notices": [
        _land_notice("Kinnistusraamatu kanne", ["78401:107:0760"])]}
    assert dim_cadastre(ata_c, listing)[0] == 60


def test_link_dims_clean_caps_at_70():
    listing = {"tunnus": "78401:107:0760"}
    # Family notice present but linked to ANOTHER parcel: weak-good.
    ata_o = {"tallinn": True, "notices": [
        _land_notice("Kaevandamisloa andmise teade",
                     ["78401:107:0799"])]}
    v, reason = dim_quarry(ata_o, listing)
    assert v == 70
    assert "ülempiir 70" in reason
    # Empty window: also capped 70, never 100.
    ata_e = {"tallinn": True, "notices": []}
    assert dim_zoning(ata_e, listing)[0] == 70
    assert dim_cadastre(ata_e, listing)[0] == 70


def test_link_dims_null_without_tunnus():
    # Linkage before flags: no parcel tunnus on the listing -> NULL,
    # even with an active family notice in the window.
    ata_q = {"tallinn": True, "notices": [
        _land_notice("Kaevandamisloa andmise teade",
                     ["78401:107:0760"])]}
    v, reason = dim_quarry(ata_q, {})
    assert v is None and "EI OLE hinnangut" in reason
    assert dim_zoning(ata_q, None)[0] is None


def test_archived_family_notice_does_not_flag():
    listing = {"tunnus": "78401:107:0760"}
    ata_q = {"tallinn": True, "notices": [
        _land_notice("Kaevandamisloa andmise teade",
                     ["78401:107:0760"], archived=True)]}
    assert dim_quarry(ata_q, listing)[0] == 70


def test_felling_always_null():
    listing = {"tunnus": "78401:107:0760"}
    ata_f = {"tallinn": True, "notices": [
        _land_notice("Metsateatis raieks", ["78401:107:0760"])]}
    v, reason = dim_felling(ata_f, listing)
    assert v is None and "Metsaregister" in reason
    v, _reason = dim_felling({"tallinn": True, "notices": []}, listing)
    assert v is None
    assert dim_felling(None, listing)[0] is None


def test_link_registry_and_aggregator_cover_all_4():
    assert [k for k, _, _ in P4_ATA_LINK_DIMS] == LINK_KEYS
    assert len({fn for _, _, fn in P4_ATA_LINK_DIMS}) == 4
    listing = {"tunnus": "78401:107:0760"}
    ata_all = {"tallinn": True, "notices": [
        _land_notice("Kaevandamisloa andmise teade",
                     ["78401:107:0760"], notice_id="1"),
        _land_notice("Detailplaneeringu kehtestamine",
                     ["78401:107:0760"], notice_id="2"),
        _land_notice("Kinnistusraamatu kanne", ["78401:107:0760"],
                     notice_id="3"),
        _land_notice("Metsateatis raieks", ["78401:107:0760"],
                     notice_id="4"),
    ]}
    out = score_p4_ata_link(ata_all, listing)
    assert out == {"quarry": 35, "zoning": 55, "cadastre": 60,
                   "felling": None}
    assert score_p4_ata_link(None, listing) == {k: None for k in LINK_KEYS}
    assert ata.P4_ATA_LINK_DIMS is P4_ATA_LINK_DIMS
