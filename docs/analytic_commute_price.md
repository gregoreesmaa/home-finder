# Analytic: commute-adjusted price (€ per saved commute-minute) — documented-blocked (issue #700)

Olek: **blokeeritud** — selles failis on ainult valem + sisendid + blokeerija.
Piir: ühtegi skoori ei tarnita, ühtegi feik-hinnet ei arvutata.

## Mida see mõõdaks (kui andmed oleksid)

Kui palju maksab ostja iga säästetud pendelminuti eest — hinnakõlblikkuse
dimensioon, mida ükski portaal ei näita: kas kesklinna kalli korteri
lühike töölesõit on minutite hinnas odavam kui äärelinna odava korteri
pikk sõit.

## Valem (€/säästetud-minut)

Võrdle kahte piirkonda X (keskne, kallim, lühem sõit) ja Y (perifeerne,
odavam, pikem sõit) fikseeritud võrdluskorteri korral:

- `P_X`, `P_Y` — piirkonna mediaanhind võrdluskorteri eest (€, Maa-ameti
  tehingud; täpne korteritüüp ja amortisatsioonimudel fikseeritakse
  implementeerimisel, mitte siin).
- `C_X`, `C_Y` — piirkonna kaalutud keskmine tipptunni autosõit
  töökohtade sõlmpunktidesse (min, ühesuunaline; #669 maatriks).
- `Δ€/kuu` — kuise eluasemekulu vahe (hinnavahe × annuiteeditegur).
- `Δmin/kuu` — kuus säästetud pendelminutid: `(C_Y − C_X) × 2 × 22`.

Valem:

```
E = Δ€/kuu / Δmin/kuu   (€ säästetud pendelminuti kohta kuus)
```

Suurem E = kallimalt ostetud minut (halvem diil pendelraha mõttes);
negatiivne E (X nii odavam kui kiirem) = domineeriv diil.

## Sisendid

1. TomTom autosõidu-maatriks (#669): 196 ala × 5 töökoha sõlmpunkti
   (kesklinn, Ülemiste, Mustamäe, sadam, lennujaam),
   tipptund vs tipuväline, `traffic=true`. — PUUDUB, blokeerija.
2. Maa-ameti tehinguhinnad piirkonna mediaanina (€/m² või võrdluskorter).
   — olemas põhimõtteliselt, seotakse implementeerimisel.

## Blokeerija + avamistingimus

- Blokeerija: **#669** (TomTom car-commute matrix) — ilma alade
  tipptunni-minutiteta on `C_X`, `C_Y` tundmatud ja valemit ei saa
  toita pärisandmetega.
- Avamistingimus: #669 suletud + `tomtom/commute-matrix.json`
  (või ToS-iga kooskõlas olev lühiajaline vahemälu) sisaldab
  piirkonniti tipptunni/tipuvälise minuteid 5 sõlmpunkti; siis:
  implementeeri `services/scoring/dims_commute_price.py` päris
  arvutusega ja eemalda `test_analytic_commute_price.py` skip-märgis
  (test fikseerib ülaloleva valemi fiktiivandmetel).
