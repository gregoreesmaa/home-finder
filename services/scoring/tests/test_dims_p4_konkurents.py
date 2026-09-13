"""P4 Konkurentsiamet demo dim (issue #262): hermetic tests.

No network: fetch_konkurents_xlsx is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus fixture-fed parse
tests). The dim is tested on fixture cap records transcribed from the
live 08.09.2026 XLSX vintage through the per-address join shape:
joined record -> bands, missing record -> NULL with Estonian honesty
markers.
"""

import os

import dims_p4_konkurents as konkurents
from dims_p4_konkurents import (
    KONKURENTS_TTL_S,
    P4_KONKURENTS_DIMS,
    cache_is_fresh,
    dim_heat_price_cap,
    index_by_cap,
    parse_konkurents_caps,
    score_p4_konkurents,
)

# ---------------------------------------------------------------------------
# Fixtures: transcribed KA cap snapshot layout (semicolon, BOM, sparse
# columns, comma decimals) plus canonical joined cap records. zone_key
# doubles as the per-address join key (slugged from the XLSX
# võrgupiirkond). Tallinn row transcribed from the live
# 08.09.2026 vintage (Utilitas Tallinn AS / 77.82 / 7-3/2024-090);
# Adavere row shows pending uue-hinna columns (F-H in the XLSX). No
# personal data anywhere (AGENTS.md section 5 — per-võrgupiirkond
# caps, fixtures only).
# ---------------------------------------------------------------------------

FIXTURE_CSV = (
    "\ufeffzone_key;company;network_area;cap_eur_mwh;decision_no;decided;"
    "new_decision_no;new_cap_eur_mwh;vintage\n"
    "tallinna-vorgupiirkond;Utilitas Tallinn AS;Tallinna võrgupiirkond;"
    "77,82;7-3/2024-090;27.12.2024;;;08.09.2026\n"
    "adavere-vorgupiirkond;Adven Eesti AS;Adavere võrgupiirkond;83,15;"
    "7-3/2025-0068H;28.10.2025;7-3/2026-0106H;86,79;08.09.2026\n"
    "katlamaja-test;Katlamaja OÜ;Testi võrgupiirkond;;7-3/2026-001;;;"
    "08.09.2026\n"
)

KEHTIV_CAP = {
    "zone_key": "tallinna-vorgupiirkond",
    "company": "Utilitas Tallinn AS",
    "network_area": "Tallinna võrgupiirkond",
    "cap_eur_mwh": 77.82,
    "decision_no": "7-3/2024-090",
    "decided": "27.12.2024",
    "new_decision_no": None,
    "new_cap_eur_mwh": None,
    "vintage": "08.09.2026",
}

PENDING_CAP = {
    "zone_key": "adavere-vorgupiirkond",
    "company": "Adven Eesti AS",
    "network_area": "Adavere võrgupiirkond",
    "cap_eur_mwh": 83.15,
    "decision_no": "7-3/2025-0068H",
    "decided": "28.10.2025",
    "new_decision_no": "7-3/2026-0106H",
    "new_cap_eur_mwh": 86.79,
    "vintage": "08.09.2026",
}

ALL_FNS = [fn for _, _, fn in P4_KONKURENTS_DIMS]

EXPECTED_KEYS = ["heat_price_cap"]
EXPECTED_PNUMS = ["P4-008"]


# ---------------------------------------------------------------------------
# Ingestion: parse + join + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_handles_bom_semicolons_and_comma_decimals():
    recs = parse_konkurents_caps(FIXTURE_CSV)
    assert len(recs) == 3
    first = recs[0]
    assert first["zone_key"] == "tallinna-vorgupiirkond"
    assert first["company"] == "Utilitas Tallinn AS"
    assert first["network_area"] == "Tallinna võrgupiirkond"
    assert first["cap_eur_mwh"] == 77.82  # comma decimal parsed
    assert first["decision_no"] == "7-3/2024-090"
    assert first["decided"] == "27.12.2024"
    assert first["new_decision_no"] is None
    assert first["new_cap_eur_mwh"] is None
    assert first["vintage"] == "08.09.2026"
    # Pending row: uue-hinna columns transcribed.
    assert recs[1]["new_decision_no"] == "7-3/2026-0106H"
    assert recs[1]["new_cap_eur_mwh"] == 86.79
    # Sparse row: empty cells become None, never guesses.
    assert recs[2]["cap_eur_mwh"] is None
    assert recs[2]["decision_no"] == "7-3/2026-001"
    assert recs[2]["decided"] is None


def test_parse_skips_rows_without_join_key():
    csv_text = ("zone_key;company;cap_eur_mwh\n"
                ";Utilitas Tallinn AS;77.82\n"
                "tallinna-vorgupiirkond;Utilitas Tallinn AS;77.82\n")
    recs = parse_konkurents_caps(csv_text)
    assert [r["zone_key"] for r in recs] == ["tallinna-vorgupiirkond"]


def test_parse_never_guesses_unknown_tokens_or_caps():
    csv_text = ("zone_key;company;cap_eur_mwh;decision_no;"
                "new_cap_eur_mwh\n"
                "X;Kosmos OÜ;tasuta;ootel;võib-olla\n")
    recs = parse_konkurents_caps(csv_text)
    assert recs[0]["company"] == "Kosmos OÜ"  # open-ended, kept as-is
    assert recs[0]["cap_eur_mwh"] is None  # "tasuta" is not zero heat
    assert recs[0]["new_cap_eur_mwh"] is None
    assert recs[0]["decision_no"] == "ootel"  # kept, scored as weak


def test_parse_dot_decimals_and_rejects_negative_caps():
    csv_text = ("zone_key;cap_eur_mwh;new_cap_eur_mwh\n"
                "A;99.5;\n"
                "B;-10;\n")
    recs = parse_konkurents_caps(csv_text)
    assert recs[0]["cap_eur_mwh"] == 99.5
    assert recs[1]["cap_eur_mwh"] is None  # a cap cannot be negative


def test_index_by_cap_keeps_first_row_per_key():
    recs = parse_konkurents_caps(FIXTURE_CSV)
    index = index_by_cap(recs)
    assert set(index) == {"tallinna-vorgupiirkond",
                          "adavere-vorgupiirkond", "katlamaja-test"}
    assert index["tallinna-vorgupiirkond"]["cap_eur_mwh"] == 77.82
    doubled = index_by_cap(recs + [dict(recs[0], cap_eur_mwh=1.0)])
    assert doubled["tallinna-vorgupiirkond"]["cap_eur_mwh"] == 77.82


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert KONKURENTS_TTL_S == 30 * 86400  # monthly per docs
    missing = os.path.join(str(tmp_path), "konkurents-x.xlsx")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "konkurents-x.xlsx"
    p.write_bytes(b"PK fake-xlsx")
    assert cache_is_fresh(str(p), ttl_s=KONKURENTS_TTL_S) is True
    aged = 31 * 86400.0
    assert cache_is_fresh(str(p), ttl_s=KONKURENTS_TTL_S,
                          now=os.path.getmtime(str(p)) + aged) is False


# ---------------------------------------------------------------------------
# NULL contracts: missing slice is always NULL with Estonian markers.
# ---------------------------------------------------------------------------

def test_dim_null_without_zone_and_names_checks():
    v, reason = dim_heat_price_cap(None)
    assert v is None
    assert "EI OLE" in reason
    assert "KÜ" in reason and "Konkurentsiamet" in reason


def test_dim_accepts_missing_listing_side():
    for zone in (KEHTIV_CAP, PENDING_CAP, {}):
        v, reason = dim_heat_price_cap(zone)  # listing=None never crashes
        assert isinstance(reason, str) and reason
        assert v is None or isinstance(v, int)


def test_non_dict_input_is_null_not_crash():
    v, reason = dim_heat_price_cap("Utilitas Tallinn AS")
    assert v is None
    assert "EI OLE" in reason


def test_joined_but_empty_record_is_null_not_scored():
    v, reason = dim_heat_price_cap({"zone_key": "X"})
    assert v is None
    assert "tühi" in reason and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Demo P4-008 bands (cap groundedness, never cheapness).
# ---------------------------------------------------------------------------

def test_kehtiv_cap_scores_groundedness_capped():
    v, reason = dim_heat_price_cap(KEHTIV_CAP)
    assert v == 55
    assert "Utilitas Tallinn AS" in reason and "77.82" in reason
    assert "7-3/2024-090" in reason
    assert "registriandmed" in reason and "mitte hinnang" in reason
    assert "ülempiir 55" in reason
    assert "käibemaksuta" in reason and "KÜ aruannet" in reason


def test_pending_new_price_scores_weak_signal():
    v, reason = dim_heat_price_cap(PENDING_CAP)
    assert v == 40
    assert "muutmisel" in reason
    assert "ülempiir 40" in reason
    assert "86.79" in reason or "7-3/2026-0106H" in reason


def test_decision_known_cap_missing_scores_weak_not_null():
    zone = {"zone_key": "katlamaja-test", "company": "Katlamaja OÜ",
            "network_area": "Testi võrgupiirkond", "cap_eur_mwh": None,
            "decision_no": "7-3/2026-001", "decided": None,
            "new_decision_no": None, "new_cap_eur_mwh": None,
            "vintage": "08.09.2026"}
    v, reason = dim_heat_price_cap(zone)
    assert v == 40 and "ülempiir 40" in reason


def test_cap_known_decision_missing_scores_weak_not_scored():
    zone = dict(KEHTIV_CAP, decision_no=None)
    v, reason = dim_heat_price_cap(zone)
    assert v == 40 and "ülempiir 40" in reason


def test_never_zero_never_hundred():
    for zone in (KEHTIV_CAP, PENDING_CAP, {"zone_key": "X"}):
        v, _ = dim_heat_price_cap(zone)
        assert v != 0 and v != 100


# ---------------------------------------------------------------------------
# Registry + aggregator (single param, single dim).
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_KONKURENTS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_KONKURENTS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_KONKURENTS_DIMS}) == 1
    assert score_p4_konkurents(KEHTIV_CAP) == {"heat_price_cap": 55}
    assert score_p4_konkurents(PENDING_CAP) == {"heat_price_cap": 40}
    assert score_p4_konkurents(None) == {"heat_price_cap": None}
    assert konkurents.P4_KONKURENTS_DIMS is P4_KONKURENTS_DIMS
