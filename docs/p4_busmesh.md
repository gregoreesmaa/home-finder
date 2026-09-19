# Granulaarne bussivõrk: GTFS shapes × stops ristumisarvutuse teostatavus (issue #764)

> Verdict date: 2026-09-19. Kood: `services/scoring/dims_p4_busmesh.py`
> (puhas offline-tuletus, ainus tõeallikas); jooksutaja:
> `scripts/build/batch_busmesh_probe.py --zip <snapshot-gtfs.zip>`;
> testid: `services/scoring/tests/test_dims_p4_busmesh.py` (hermeetiline,
> võrku pole).

## Verdict: POSITIIVNE → ulatusega build-issue

GTFS static shapes + stops annavad usaldusväärse ristumisarvutuse.
Järel-töö (sõlmede sidecar + kiht + ümberistumis-skoor) on omaette
build-issue — see probe ei ehita kihti ega skoorijat.

## Meetod (korratav, /tmp-only, skreipimist pole)

Kohalik snapshot-vintage `gtfs/tallinn-gtfs-2026-09-11.zip` loeti
kohapeal (/as-is, võrgupäringuid polnud vaja — vintage oli snapshotis
olemas). Kolmapäevase (Wednesday) teenuse marsruutide `shapes.txt`
polüliinid projitseeriti lokaalsetesse meetritesse; eri marsruutide
lõikude omavahelised lõikumised klasterdati 60 m raadiuses sõlmedeks;
peatused valideeriti 100 m raadiuses (peatus ei defineeri sõlme —
geomeetria defineerib, peatus kinnitab kasutatavust).

## Mõõdetud (kontrollitud nii /tmp-prototüübi kui committitud
## mooduliga — identsed arvud)

| Näitaja | Väärtus |
|---|---|
| Peatusi / marsruute / reise (vintage) | 1120 / 80 / 20 081 |
| Erinevaid shape'e (kõik kolmapäevareisid shape'iga) | 196 |
| Toor-ristumised (eri marsruutide paarid) | 253 396 |
| Klasterdatud sõlmed (60 m) | 1922 |
| Sõlmed ≥3 marsruudiga | 1317 |
| Tipphubid (marsruute sõlmes) | 30 / 29 / 25 / 22 (kesklinn, oodatud) |
| Sõlmed ≤100 m peatusest | 1215 (63%) |
| Peatused ≤100 m sõlmest | 921 / 1120 (82%) |
| Sõlmede haare | ~19,5 km × 17,6 km (Tallinna metroo-009 ala) |

Marsruutide-arvu jaotus sõlmedes: 2 marsruuti 605, 3 marsruuti 314,
4 marsruuti 215, … 10+ marsruuti 148 — pikk saba suurte
ümberistumishubideni välja.

## Hoiatused ehitajale (need lähevad build-issue acceptance-kriteeriumitesse)

1. **Koridoriketid.** 253 tuh toor-ristumist → 1922 sõlme tähendab, et
   ühist koridori sõitvad marsruudid toodavad ristumiste KETTE, mitte
   üksikuid punkte. Build peab ketid kokku tõmbama (identne
   marsruudikomplekt piki koridori) või peatustele snappima — iga keti
   lüli eraldi plotituna oleks müra.
2. **37% sõlmedest on peatusteta 100 m raadiuses.** Need on geomeetria,
   mitte kasutatavad ümberistumised — build plotib ainult
   peatusega sõlmi (707 peatusteta sõlme jäävad diagnostikaks).
3. **199 peatust on sõlmedest eemal.** Liiniotsad ja haruliinid —
   ümberistumis-skoor peab nende jaoks ausalt "üksikteenus" ütlema,
   mitte naabersõlme laenama.
4. **Kolmapäeva-vintage.** Nädalavahetuse-võrk on hõredam; skoorija
   peab akna (WD/SA/SU) vintage'st uuesti tuletama, mitte kolmapäeva
   sõlmi nädalavahetusele kopeerima (sama reegel mis p125-s).

## Kordamise kontroll (re-verify kuupäev)

Uue GTFS-vintage'iga: jooksuta probe-runner, võrdle sõlmede arvu
(±20% oodatud sesoonsuse piires) ja peatus-katvust (≥75%).
Peatus.ee national GTFS on endiselt suletud (vt `docs/p4_gtfsstops.md`)
— regionaalset võrku see probe ei hinda.

## Reopening (millal verdict aegub)

* TLT avaldab uue snapshot-vintage → arvud uuenevad, meetod sama.
* Peatus.ee avab national GTFSi → korra väljaspool linna-vintage't.
* Elron avaldab masin-sõiduplaani → raudtee-sõlmed eraldi hinnanguna.
