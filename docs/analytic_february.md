# Analytic: February test (winter severity × heating × snow priority) — documented-blocked (issue #702)

Olek: **blokeeritud** — selles failis on ainult valem + sisendid + blokeerija.
Piir: ühtegi skoori ei tarnita, ühtegi feik-hinnet ei arvutata.

## Mida see mõõdaks (kui andmed oleksid)

Piirkonna veebruari-tõrksuse skoor: kui karm on talv konkreetses
piirkonnas (mõõdetud teeilm), kui haavatav on hoone küte külma suhtes
ja kui kiiresti lumi eest ära koristatakse. Ostja küsimus: "kas siin
veebruaris elada saab, kui auto on lume all ja radiaator jahtub?"

## Valem (veebruari-skoor)

Piirkonna A skoor kolmest tegurist (võrdsed kaalud esialgne ettepanek;
kaalud kalibreeritakse pärisandmetel implementeerimisel, mitte siin):

- `W_A` — talvekarmus (0..1): TarkTee DATEX talvise raskusastme
  normaliseeritud sagedus/raskus piirkonnas (libedad teed, piirangud;
  #683). Kõrgem = karmim talv = halvem.
- `H_A` — kütte-haavatavus (0..1): EHR-i kütteviiside osakaal
  (nt otsene elekter/ahi ilma varuta = haavatavam kui kaugküte).
  Kõrgem = haavatavam = halvem.
- `S_A` — lumekoristuse prioriteet (0..1): lükkamise järjekord/
  tase piirkonnas (linna prioriteedid). Kõrgem = kiirem koristus = parem.

Valem:

```
veebruar_A = 100 − 100 × (w_W × W_A + w_H × H_A + w_S × (1 − S_A)),
w_W = w_H = w_S = 1/3 (esialgne; kalibreeritakse)
```

100 = karm talv + haavatav küte + aeglane koristus ei karista;
0 = halvim kombinatsioon. Skaala suund (kõrgem = parem veebruar)
fikseeritakse koos testiga avamisel.

## Sisendid

1. Talvekarmus: TarkTee DATEX II (#683) — restrictions + SRTI
   temporarySlipperyRoad, jaamade mõõdetud teeilm. — PUUDUB, blokeerija
   (suvi 2026: SRTI tühi ausalt-hooajaväliselt; talveandmeid pole veel
   korjatud).
2. Kütteviis: EHR (olemas / täiendamisel teistes taskides).
3. Lumekoristuse prioriteet: linna prioriteedid (seotakse
   implementeerimisel).

## Blokeerija + avamistingimus

- Blokeerija: **#683** (TarkTee DATEX talvine raskusaste) — ilma
  mõõdetud talvekarmuseta on `W_A` tundmatu ja valemit ei saa toita
  pärisandmetega.
- Avamistingimus: #683 suletud + DATEX-i talvise raskusastme andmed
  (restrictions/SRTI + jaamade teeilm) piirkonniti saadaval; siis:
  implementeeri `services/scoring/dims_february.py` päris arvutusega
  ja eemalda `test_analytic_february.py` skip-märgis (test fikseerib
  ülaloleva valemi fiktiivandmetel).
