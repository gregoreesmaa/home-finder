"""Fixture tests for scripts/build/batch_medre.py (issue #609, Step 1).

Hermetic: synthetic medre nimistud + companies XML only, never network.
Step 1 ships the register extract with linkage_rate 0 (no ADS join
owned yet) — points stay [] BY HONESTY (paaste #493 precedent).
"""

import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from batch_medre import build_sidecar

FIX_NIMISTUD = """<nimistud>
  <nimistu><kood>N123</kood><perearst>Test Arst</perearst>
    <teeninduspiirkonnad><teeninduspiirkond><nimi>Kesklinn</nimi></teeninduspiirkond></teeninduspiirkonnad>
    <vastuvott><kohad>
      <koht><adr_id>12345</adr_id><adr_kood>7840123</adr_kood><adr_tekst>Harju maakond, Tallinn, Endla tn 4</adr_tekst></koht>
      <koht><adr_id>12346</adr_id><adr_kood>7840124</adr_kood><adr_tekst>Harju maakond, Tallinn, Sõle tn 1</adr_tekst></koht>
    </kohad></vastuvott></nimistu>
  <nimistu><kood>N124</kood><perearst>Teine Arst</perearst>
    <vastuvott><kohad>
      <koht><adr_id>99999</adr_id><adr_kood>1234567</adr_kood><adr_tekst>Tartu maakond, Tartu, Kooli tn 1</adr_tekst></koht>
    </kohad></vastuvott></nimistu>
</nimistud>"""

FIX_COMPANIES = """<asutused>
  <asutus><nimi>Test Kliinik</nimi><registrikood>10000001</registrikood>
    <aadress>Harju maakond, Tallinn, Narva mnt 1</aadress>
    <tegevusload><tegevusluba><loaliik_nimi>Üldarstiabi</loaliik_nimi>
      <tegevusloa_number>L123</tegevusloa_number>
      <tegevuskohad><tegevuskoht><aadress>Harju maakond, Tallinn, Narva mnt 1</aadress>
        <teenused><teenus><nimi>Perearstiabi</nimi></teenus></teenused>
      </tegevuskoht></tegevuskohad>
    </tegevusluba></tegevusload></asutus>
  <asutus><nimi>Eri Kliinik</nimi><registrikood>10000002</registrikood>
    <aadress>Harju maakond, Tallinn, Ravi tn 1</aadress>
    <tegevusload><tegevusluba><loaliik_nimi>Eriarstiabi</loaliik_nimi>
      <tegevusloa_number>L124</tegevusloa_number>
      <tegevuskohad><tegevuskoht><aadress>Harju maakond, Tallinn, Ravi tn 1</aadress>
      </tegevuskoht></tegevuskohad>
    </tegevusluba></tegevusload></asutus>
</asutused>"""


def test_step1_sidecar_reports_zero_linkage(tmp_path):
    out = build_sidecar(ET.fromstring(FIX_NIMISTUD),
                        ET.fromstring(FIX_COMPANIES), str(tmp_path))
    assert out["vintage"] == "2026-09-16"
    # Register tallies travel; nothing places without the ADS join.
    assert out["register"]["nimistu"] == 2
    assert out["register"]["harju_kohad"] == 2
    assert out["register"]["uldarstiabi_kohad"] == 1
    assert out["linkage_rate"] == 0
    assert out["points"] == []
    assert out["counts"] == {"gp": 0, "clinic": 0, "total": 0}


def test_other_licences_counted_never_scored(tmp_path):
    out = build_sidecar(ET.fromstring(FIX_NIMISTUD),
                        ET.fromstring(FIX_COMPANIES), str(tmp_path))
    assert out["register"]["other_licences"] == 1
