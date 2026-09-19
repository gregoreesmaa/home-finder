# Kihiandmete allikate audit: hetktõmmis vs pool (issue #762)

> Audit date: 2026-09-19. Guard test: `apps/web/lib/layers_source.test.ts`
> (pere-tsensus 103 + 6 + 6 + 46 + 12 = 173 — uus kiht deklareerib
> oma pere või test ebaõnnestub).

## Otsus: brauseri-otseseid live-sõltuvusi POLE

Mõõdetud, mitte väidetud:

* Brauser räägib ainult sama-päritolu `/api/layers/*`-iga
  (`fetchLayerPoints` — suhteline URL, `fetchImpl` süstitav testides).
  Otsing `fetch("http|fetch('http|fetch(`http` (välja arvatud
  `/api/`, localhost, testid) üle `apps/web` — 0 tabamust.
* `overpassQueryFor` on definitsioon + testid + dok-kommentaarid;
  produktsioonis pole ühtegi kutsujat (välja arvatud definitsioon
  `lib/layers.ts`-s).
* `lib/server/overpass.ts` ja `lib/server/fileCache.ts` on surnud
  importideta (ainult tsbuildinfo viitab) — `[layer]`-marsruut neid
  ei kasuta (marsruudi kommentaar).
* Serveri-live kolmanda-osapoole kõnesid pole üheski API-marsruudis
  (otsing `fetch("http|urlopen|https://` üle `apps/web/app/api` —
  ainult näidised/skeemid/testid).

## Teeninduspered (kõik 173 kihti)

| Pere | Kihte | Allikas | Värskus |
|---|---|---|---|
| generic-snapshot-file | 103 | `osm/derived-<kiht>.json` hetktõmmisest (+walk-rasterid) | `ageMs` = nüüd − 2026-09-12 (vintage-capped) |
| dedicated-snapshot | 46 | Eraldi ehitatud sidecar hetktõmmisest (registerid/aastavõtud) | Oma vintage (`*_VINTAGE`) `ageMs`-s |
| operator-cache | 6 | Operaatori git-ignored puhver: outage (5 min), sheds (7 d), incidents (6 h) | Faili mtime / `X-Pole-Built-At` → `ageMs` |
| pole-live | 6 | Pooli `/v1/datex-*` elustabelid (voo TTL-id) | `X-Pole-Built-At` → `ageMs` |
| silly-demo | 12 | Demo-varu PÄRISEGA kaardistatud punktidega (sildistatud) | Demo (vanust pole — disain) |

## Mõõdetud teenindus (dev, hetktõmmis 2026-09-12, 173 kihti)

* 143 × `snapshot` (punktidega), 3 × `empty` (asumedia, medre_gp,
  medre_clinic — aus-tühjad disainiga), 27 × `500 → demo` (sildistatud).
* 27 demo-selgitus: datex ×6 (pooli tunnel dev-is maas — #763
  stub-pooliga verifitseeritud elusaks), senscom/ookla ×2/paaste/harno
  (operaatori sidecar dev-is puudub), gbfs/skis (allikas puudub —
  vaata pooli otsuseid), silly ×12 (demo disainiga), outage
  (hetkeseis-sidecar dev-is puudub — poolil täidab 5 min cron).
* Kõik vastused kannavad `ageMs`-i (või null demo/tühja puhul) —
  värskus-päis on iga kihi juures olemas.

## DEMO-varu staatused

* `#711` silly ×12: demo disainiga (päris punktid, sildistatud) — jääb.
* `#729` outage: enam pole demo — juhtmestatud #763-s (operaatori
  hetkeseis-sidecar, 5 min TTL).
* Ülejäänud 500-d on faili-puudumise demod (sildistatud, kunagi
  vaikne null).

## Pooli otsused (#762 AC)

* `pole/bin/run-skis.sh` LISATUD (ehitaja `--out` lisatud +
  testitud): talvine käsisamm operaatori `state/skis-status.json`
  teaviku pealt `built/skis/table.json`-iks. Croni teadlikult POLE
  (hooajaväline cron ei käi — docs/p4_skis.md); `pole/api.py`
  `skis/table.json` oli juba eksponeeritud.
* GBFS: wrapperit POLE (2026-09-19 verdict: verifitseeritud
  võtmeta voogu pole — docs/p4_gbfs.md). Wrapper lisatakse alles
  elusa re-verifitseerimise järel.
* Võtmega TomTomi tõmbed (sheds/incidents/flow/matrix) jäävad
  operaatori-pooleks verdictitega (SHORT-TERM CACHE ONLY — salvestatud
  tabeleid pole); pooli croni neid ei lisata.

## Lisa: kõik 173 kihti (pere + dev-mõõtmine)

| kiht | pere | mõõdetud (dev, 2026-09-12 hetktõmmis) |
|---|---|---|
| parks | generic-snapshot-file | snapshot (4109) |
| transit | generic-snapshot-file | snapshot (5831) |
| schools | generic-snapshot-file | snapshot (779) |
| walkability | generic-snapshot-file | snapshot (0) |
| pedinfra | generic-snapshot-file | snapshot (0) |
| cycling | generic-snapshot-file | snapshot (0) |
| grocery | generic-snapshot-file | snapshot (558) |
| healthcare | generic-snapshot-file | snapshot (295) |
| pets | generic-snapshot-file | snapshot (213) |
| community | generic-snapshot-file | snapshot (179) |
| culture | generic-snapshot-file | snapshot (229) |
| nightlife | generic-snapshot-file | snapshot (251) |
| libraries | generic-snapshot-file | snapshot (68) |
| brownsoil | generic-snapshot-file | snapshot (228) |
| oiltank | generic-snapshot-file | snapshot (943) |
| agriland | generic-snapshot-file | snapshot (1363) |
| agrifield | generic-snapshot-file | snapshot (1510) |
| wildcorr | generic-snapshot-file | snapshot (1683) |
| vectorhabitat | generic-snapshot-file | snapshot (10731) |
| industprox | generic-snapshot-file | snapshot (107) |
| odorsrc | generic-snapshot-file | snapshot (226) |
| safety | generic-snapshot-file | snapshot (0) |
| emergency | generic-snapshot-file | snapshot (0) |
| hydrants | generic-snapshot-file | snapshot (0) |
| evac | generic-snapshot-file | snapshot (0) |
| dispatch | generic-snapshot-file | snapshot (0) |
| mailbox | generic-snapshot-file | snapshot (104) |
| postal | generic-snapshot-file | snapshot (382) |
| alley | generic-snapshot-file | snapshot (58) |
| trailprivacy | generic-snapshot-file | snapshot (17456) |
| plaster | generic-snapshot-file | snapshot (3217) |
| antiques | generic-snapshot-file | snapshot (8) |
| woodfire | generic-snapshot-file | snapshot (1506) |
| schoolbus | generic-snapshot-file | snapshot (270) |
| recspecial | generic-snapshot-file | snapshot (440) |
| medspecial | generic-snapshot-file | snapshot (110) |
| worship | generic-snapshot-file | snapshot (167) |
| forage | generic-snapshot-file | snapshot (13143) |
| droneclear | generic-snapshot-file | snapshot (42) |
| droneviab | generic-snapshot-file | snapshot (42) |
| rentbleed | generic-snapshot-file | snapshot (72) |
| heritage | generic-snapshot-file | snapshot (577) |
| liftproxy | generic-snapshot-file | snapshot (4220) |
| drainage | generic-snapshot-file | snapshot (766) |
| moorage | generic-snapshot-file | snapshot (121) |
| shoredist | generic-snapshot-file | snapshot (728) |
| wildfire | generic-snapshot-file | snapshot (1705) |
| vernalpool | generic-snapshot-file | snapshot (47) |
| surgeroad | generic-snapshot-file | snapshot (1067) |
| slidebuf | generic-snapshot-file | snapshot (1382) |
| windtunnel | generic-snapshot-file | snapshot (1454) |
| saltspray | generic-snapshot-file | snapshot (565) |
| gardens | generic-snapshot-file | snapshot (214) |
| buildout | generic-snapshot-file | snapshot (271) |
| strsat | generic-snapshot-file | snapshot (449) |
| ehitus | generic-snapshot-file | snapshot (421) |
| korterstock | generic-snapshot-file | snapshot (6393) |
| commbleed | generic-snapshot-file | snapshot (1424) |
| windsolar | generic-snapshot-file | snapshot (101) |
| viewshed | generic-snapshot-file | snapshot (64) |
| equestrian | generic-snapshot-file | snapshot (189) |
| upcycle | generic-snapshot-file | snapshot (107) |
| skyview | generic-snapshot-file | snapshot (875) |
| dayopen | generic-snapshot-file | snapshot (1456) |
| glassglare | generic-snapshot-file | snapshot (471) |
| fishbowl | generic-snapshot-file | snapshot (1191) |
| mossrisk | generic-snapshot-file | snapshot (832) |
| daylight | generic-snapshot-file | snapshot (1094) |
| compost | generic-snapshot-file | snapshot (80) |
| gritbin | generic-snapshot-file | snapshot (30) |
| leafdrop | generic-snapshot-file | snapshot (156) |
| lawncare | generic-snapshot-file | snapshot (1428) |
| privroad | generic-snapshot-file | snapshot (1260) |
| water | generic-snapshot-file | snapshot (120) |
| waste | generic-snapshot-file | snapshot (1399) |
| fiber | generic-snapshot-file | snapshot (4885) |
| mobile | generic-snapshot-file | snapshot (2655) |
| dailyshop | generic-snapshot-file | snapshot (394) |
| activity | generic-snapshot-file | snapshot (1619) |
| herd | generic-snapshot-file | snapshot (129) |
| thirdplace | generic-snapshot-file | snapshot (1091) |
| taxidoor | generic-snapshot-file | snapshot (3869) |
| lastshop | generic-snapshot-file | snapshot (718) |
| gtfsstops | generic-snapshot-file | snapshot (1207) |
| busmesh | generic-snapshot-file | snapshot (437) |
| busmesh-sat | generic-snapshot-file | snapshot (426) |
| busmesh-sun | generic-snapshot-file | snapshot (423) |
| shed-15-peak | operator-cache | snapshot (0) |
| shed-15-offpeak | operator-cache | snapshot (0) |
| shed-30-peak | operator-cache | snapshot (0) |
| shed-30-offpeak | operator-cache | snapshot (0) |
| datex-restrictions | pole-live | 500→demo (HTTP Error 500) |
| datex-srti | pole-live | 500→demo (HTTP Error 500) |
| datex-weather | pole-live | 500→demo (HTTP Error 500) |
| datex-counters | pole-live | 500→demo (HTTP Error 500) |
| datex-cameras | pole-live | 500→demo (HTTP Error 500) |
| datex-truckpark | pole-live | 500→demo (HTTP Error 500) |
| incidents | operator-cache | snapshot (2) |
| roadsafety | generic-snapshot-file | snapshot (1388) |
| senscom | dedicated-snapshot | 500→demo (HTTP Error 500) |
| kovmigr | generic-snapshot-file | snapshot (0) |
| kovehit | generic-snapshot-file | snapshot (0) |
| kovfisc | generic-snapshot-file | snapshot (0) |
| parking | generic-snapshot-file | snapshot (734) |
| kovkasv | generic-snapshot-file | snapshot (0) |
| kovkaive | generic-snapshot-file | snapshot (0) |
| kovedas | generic-snapshot-file | snapshot (0) |
| kovkiirus | generic-snapshot-file | snapshot (0) |
| floodzone | dedicated-snapshot | snapshot (0) |
| blockwalk | generic-snapshot-file | snapshot (1192) |
| darkness | generic-snapshot-file | snapshot (1372) |
| ookla_fixed | dedicated-snapshot | 500→demo (HTTP Error 500) |
| ookla_mobile | dedicated-snapshot | 500→demo (HTTP Error 500) |
| accblack | dedicated-snapshot | snapshot (8122) |
| maaparcel | dedicated-snapshot | snapshot (0) |
| eeliskaitse | dedicated-snapshot | snapshot (0) |
| eelisniit | dedicated-snapshot | snapshot (0) |
| eelisraie | dedicated-snapshot | snapshot (0) |
| planktpr | generic-snapshot-file | 500→demo (HTTP Error 500) |
| tervise | dedicated-snapshot | snapshot (6) |
| asumedia | dedicated-snapshot | empty (0) |
| paaste | generic-snapshot-file | 500→demo (HTTP Error 500) |
| gbfs | generic-snapshot-file | 500→demo (HTTP Error 500) |
| skis | generic-snapshot-file | 500→demo (HTTP Error 500) |
| harno | generic-snapshot-file | 500→demo (HTTP Error 500) |
| viirs | dedicated-snapshot | snapshot (48) |
| sport_hall | dedicated-snapshot | snapshot (253) |
| sport_field | dedicated-snapshot | snapshot (345) |
| sport_pool | dedicated-snapshot | snapshot (107) |
| ehis_school | dedicated-snapshot | snapshot (142) |
| ehis_kindergarten | dedicated-snapshot | snapshot (269) |
| ehis_hobby | dedicated-snapshot | snapshot (9) |
| medre_gp | dedicated-snapshot | empty (0) |
| medre_clinic | dedicated-snapshot | empty (0) |
| ohuseire | dedicated-snapshot | snapshot (3) |
| kliima_frost | dedicated-snapshot | snapshot (1) |
| kliima_wet | dedicated-snapshot | snapshot (1) |
| poi_library | dedicated-snapshot | snapshot (68) |
| poi_post | dedicated-snapshot | snapshot (374) |
| poi_pharmacy | dedicated-snapshot | snapshot (136) |
| fixit | dedicated-snapshot | snapshot (186) |
| seveso | dedicated-snapshot | snapshot (0) |
| stateland | dedicated-snapshot | snapshot (0) |
| quarry | dedicated-snapshot | snapshot (0) |
| maaparandus | dedicated-snapshot | snapshot (0) |
| soil | dedicated-snapshot | snapshot (0) |
| etak | dedicated-snapshot | snapshot (0) |
| relief | dedicated-snapshot | snapshot (0) |
| canopy | dedicated-snapshot | snapshot (0) |
| buildings | dedicated-snapshot | snapshot (0) |
| density | dedicated-snapshot | snapshot (0) |
| forest | dedicated-snapshot | snapshot (0) |
| noise | dedicated-snapshot | snapshot (0) |
| harbour | dedicated-snapshot | snapshot (15) |
| kpo | dedicated-snapshot | snapshot (0) |
| delay-morning | dedicated-snapshot | snapshot (0) |
| delay-midday | dedicated-snapshot | snapshot (0) |
| delay-evening | dedicated-snapshot | snapshot (0) |
| delay-offpeak | dedicated-snapshot | snapshot (0) |
| delay-worst | dedicated-snapshot | snapshot (0) |
| kirikukellad | silly-demo | 500→demo (HTTP Error 500) |
| kajakad | silly-demo | 500→demo (HTTP Error 500) |
| manguvaljakud | silly-demo | 500→demo (HTTP Error 500) |
| koertepargid | silly-demo | 500→demo (HTTP Error 500) |
| saunad | silly-demo | 500→demo (HTTP Error 500) |
| talisuplus | silly-demo | 500→demo (HTTP Error 500) |
| tanavasport | silly-demo | 500→demo (HTTP Error 500) |
| vesi | silly-demo | 500→demo (HTTP Error 500) |
| wc | silly-demo | 500→demo (HTTP Error 500) |
| aed | silly-demo | 500→demo (HTTP Error 500) |
| raamatukapid | silly-demo | 500→demo (HTTP Error 500) |
| kalmistu | silly-demo | 500→demo (HTTP Error 500) |
| outage | operator-cache | 500→demo (HTTP Error 500) |
