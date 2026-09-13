# parameters4.md — Brainstormed data-source backlog (batches 1–5)

> Status: IDEA BACKLOG, not a spec. Companion to `parameters3.md` (the 500-param
> engineering catalog) and `docs/layers.md` (94 map layers + 406 scorer dims).
> Every entry below was brainstormed Sept 2026 across five turns: (1) high-leverage
> gaps, (2) long tail, (3) operational/time-aware outside-box, (4) Sutherlandesque
> psycho-logic spike, (5) deeper cuts. Promotion path per `AGENTS.md` §1: open one
> GitHub `idea` issue per item, verify openness first, dated negative keeps verdict.
> Already-covered (do NOT re-propose): 17 portal adapters, EHR bulk (#234), Maa-amet
> WFS (#235), PLANK/TPR (#236), muinas (#237), CAMS/EGT/KIK (#238), KAUR/EFAS (#239),
> KOV p317 hunt (#240), MARU/Stat/ECB (#241), EMTA/KOV tax (#242), B10C masters (#230),
> e-Äriregister entity (#232), Ametlikud Teadaanded probate (#233).

Conventions (from `AGENTS.md` §7): honest shape per idea is one of `per-listing dim`
| `per-parcel join` | `KOV/precinct choropleth` | `hex aggregate` | `calendar dim`
(time-varying, never a gradient). NULL stays NULL with Estonian reason. Polite,
cached, TTL-stated pulls. No personal data, no scraped dumps, fixtures only.

## Batch 1 — high-leverage gaps (turn 1)

- `P4-001` Price history + days-on-market per ad. Buy Q: stale/desperate/overpriced
  vs steal? Source: own adapter store (`first_seen`, price drops). Shape: per-listing
  dim. Extends G1.
  Sources (Tallinn): (1) own 17-adapter store, Tallinn-filtered `first_seen`/price-drop
  history (kv.ee, city24.ee, kinnisvara24.ee snapshots, polite daily); (2) kv.ee Tallinn
  kuulutuste hinna- ja kuvamisajalugu (page badges/snapshots); (3) city24.ee Tallinn
  price-change markers; (4) kinnisvara24.ee Tallinn kuulutuse statistika/views history;
  (5) Maa-amet tehingud Tallinn medians as fair-price anchor (quarterly bulk);
  (6) Statamet KK11 Tallinn korterite mediaanhinnad. TTL: own store daily, bulk quarterly.
- `P4-002` Closed-deal micro-comps (same building/street €/m²). Buy Q: fair price?
  Source: Maa-amet tehingud + Stat HH01/KK11 (quarterly bulk). Shape: per-address
  median join, never gradient. Extends G16 (finer than #241 KOV medians).
  Sources (Tallinn): (1) Maa-amet tehingute andmebaas, Tallinn address/street filter
  (päring + quarterly bulk); (2) Maa-amet kinnisvaraturu ülevaated (Tallinn section);
  (3) Statamet HH01/KK11 Tallinn tables; (4) KV.ee + city24.ee Tallinn asking-price
  medians per asum (ask-vs-close gap); (5) Land Board offer-vs-close gap publication,
  area-type table. TTL: quarterly.
- `P4-003` Rent reality + Airbnb density dual. Buy Q: yield? nuisance? Source: KV üüri
  medians per linnaosa + Inside-Airbnb-style density. Shape: per-listing context dim
  + hex nuisance hinnang. Extends G16/G20.
  Sources (Tallinn): (1) KV.ee üüri medians per Tallinna linnaosa/asum; (2) city24.ee
  Tallinn üüripakkumised; (3) Statamet üüri statistika (Tallinn); (4) Inside-Airbnb-style
  Tallinn density (verify openness/ToS first, else AirDNA-style, label hinnang);
  (5) Tallinna Linnavalitsus lühiajalise üüri kaebused (where published);
  (6) REL2021 1 km grid Tallinn (üürikorterite osakaal/vakants). TTL: monthly/quarterly.
- `P4-004` Kinnistusregistri süva: keelumärge/hüpoteek summary + notary checkpoint.
  Buy Q: can this deal close? Source: RIK flows (verify openness). Shape: per-listing
  dim, weak-good capped. Extends G4.
  Sources (Tallinn): (1) RIK e-Kinnistusraamat, Tallinn parcel päring (tasuline, verify
  bulk openness); (2) notar.ee checkpoint guidance (closing feasibility);
  (3) Ametlikud Teadaanded (keelumärked/arestid, Tallinn filter);
  (4) kohtutäiturite register (active täitemenetlus, Tallinn properties);
  (5) Maa-amet KKIS kitsenduste kaart, Tallinn parcels;
  (6) EMTA maksuvõlg per entity (verify openness). Shape stays weak-good capped.
- `P4-005` Ehitusluba/kasutusluba existence per unit/extension. Buy Q: bankable?
  Source: EHR permits (complements #234). Shape: per-listing binary dim. Extends G2.
  Sources (Tallinn): (1) EHR/E-ehitus avaandmed + API (ehitusluba/kasutusluba per
  ehitis, Tallinn filter); (2) Tallinna Linnaplaneerimise Amet ehituslubade menetlused
  (tallinn.ee citizen desk); (3) TPR detailplaneeringu elluviimise load;
  (4) EHR energiamärgis per Tallinn building (bankability cross-check);
  (5) Muinsuskaitseamet päring for Vanalinna/miljööväärtus areas;
  (6) own adapter listing-vs-EHR cross-check (zero vendor). TTL: weekly bulk.
- `P4-006` Neighbouring detailplaneering pipeline (500 m buffer, `menetluses` stage).
  Buy Q: will sun/view die in 2 yrs? Source: PLANK/TPR neighbouring parcels
  (complements #236 this-parcel zoning). Shape: per-parcel buffer join. Extends G5.
  Sources (Tallinn): (1) Tallinna planeeringute register (TPR), neighbouring parcels in
  `menetluses` stage + 500 m buffer; (2) PLANK national WFS, Tallinn filter;
  (3) Tallinna üldplaneering 2035 lähtematerjalid + teemaplaneeringud;
  (4) detailplaneeringute avalikud väljapanekud (tallinn.ee menetlused);
  (5) Maa-amet kataster neighbour-parcel lookup for buffer geometry;
  (6) Rail Baltica/tram-corridor reservations (Tallinn sections). TTL: weekly.
- `P4-007` KÜ loan + remondifond + kütte €/m² from majandusaasta aruanded. Buy Q:
  cheap flat, huge bill? Source: Äriregister bulk (new fields vs #232). Shape:
  per-listing dims. Extends G17.
  Sources (Tallinn): (1) e-Äriregister KÜ majandusaasta aruanded, Tallinn KÜ filter
  (XBRL bulk: laen, remondifond, kütte €/m² — new fields vs #232); (2) KÜ dokumendid
  (haldus/remondifondi otsused); (3) Creditinfo/Krediidiinfo KÜ maksehäired (verify
  openness); (4) EIS renoveerimislaenu garantiid per Tallinn building;
  (5) Tallinna Kommunaalamet KÜ toetused; (6) listing-text NLP (remondifond/haldus)
  from own adapters. TTL: annual + quarterly refresh.
- `P4-008` Kaugkütte tariff zone + operator + water/sewer tariff. Buy Q: January bill?
  Source: Utilitas/Adven/local katlamaja + water utilities. Shape: per-address table
  join. Extends G10.
  Sources (Tallinn): (1) Utilitas Tallinn kaugkütte tariif + võrgupiirkonna kaart;
  (2) Adven Eesti / Tallinna Küte local katlamaja tariffs;
  (3) Konkurentsiamet kooskõlastatud soojuse piirhinnad (Tallinn);
  (4) Tallinna Vesi vee- ja kanalisatsioonitariif + ÜVK kaart (tallinnavesi.ee);
  (5) Elektrilevi võrgutasud/hinnakiri (Tallinn); (6) KÜ aruannete actual kütte €/m²
  cross-check. TTL: tariff-change driven, re-pull on Konkurentsiamet decisions.
- `P4-009` Power/internet reliability at address: Elektrilevi outage history (SAIDI per
  feeder) + TTJA broadband address check + Ookla fallback. Buy Q: dark + offline?
  Shape: per-address dim + coarse raster hinnang. Extends G10 (above #230 masters).
  Sources (Tallinn): (1) Elektrilevi katkestuste kaart/ajalugu, Tallinn feeder (SAIDI
  per feeder); (2) Elering elektrisüsteemi avaandmed; (3) TTJA sideamet broadband
  address check (netikaart, Tallinn addresses); (4) Telia/Elisa/Tele2 levikaardid
  Tallinn (verify ToS, cache); (5) Ookla Speedtest Open Data Tallinn tiles (fallback);
  (6) OpenCellID Tallinn mast density (feeds #230 masters). TTL: monthly.
- `P4-010` KredEx/EIS renovation-grant status + queue. Buy Q: renovated or 5-figure
  bill coming? Source: EIS/KredEx (open bulk, verify). Shape: per-building dim.
  Extends G2/G17.
  Sources (Tallinn): (1) EIS (ex-KredEx) renoveerimistoetuste register + järjekord,
  Tallinn buildings; (2) EHR energia-klass + renoveerimisload per Tallinn building;
  (3) Tallinna Kommunaalamet KÜ renoveerimistoetused; (4) EIS renoveerimislaenu
  käendus per building; (5) e-Äriregister KÜ aruanded (kogutud fond vs 5-figure bill);
  (6) Tallinna kliimakava renoveerimiseesmärgid per linnaosa. TTL: quarterly.
- `P4-011` Lasteaia queue length + perearst nimistu open/closed. Buy Q: can family
  use services? Source: KOV queues + Tervisekassa lists. Shape: per-KOV/linnaosa
  table. Extends G15/G11.
  Sources (Tallinn): (1) Tallinna Haridusamet lasteaia järjekorra statistika per
  linnaosa/asum; (2) HaridusSilm/EHIS Tallinn school capacity + teeninduspiirkonnad;
  (3) Tervisekassa perearstide nimistud Tallinn (avatud/suletud);
  (4) Tallinna Sotsiaal- ja Tervishoiuamet teenuste kaardid;
  (5) REL2021 0–6 age Tallinn 1 km grid (demand pressure);
  (6) Tallinna koolivõrgu arengukava (open/close plans). TTL: quarterly/annual.
- `P4-012` Traffic-accident blackspots + Päästeamet drive-time. Buy Q: is this
  crossing safe? Source: Transpordiamet points (finer than G14 county tables).
  Shape: point-buffer join. Extends G14.
  Sources (Tallinn): (1) Transpordiamet liiklusõnnetuste punktid, Tallinn filter
  (finer than G14 county tables); (2) Transpordiamet avaandmed + Tark Tee incidents;
  (3) Päästeamet sündmuste statistika + komando drive-time (Põhja-Tallinn, Lasnamäe,
  Nõmme komando); (4) Tallinna Transport liikluskorraldus + ohutud kooliteed;
  (5) PPA Tallinn liiklusjärelevalve stats; (6) OSM zebra/speed-bump inventory Tallinn
  (honest proxy). TTL: monthly/annual.
- `P4-013` Parking regime: tasulise parkimise tsoon + courtyard ratio. Buy Q: where
  do I park daily? Source: Tallinn parking open data + cadastre. Shape: per-parcel
  join. Extends G18/G3.
  Sources (Tallinn): (1) Tallinna parkimiskorralduse tasuliste alade kaart
  (Kesklinn/Vanalinn zones, tallinn.ee + Parkimine.ee); (2) Tallinna Transpordiamet
  parkimistsoonide määrused + elaniku loa tsoonid; (3) Maa-amet kataster hooviala
  ratio per Tallinn parcel; (4) EHR parkimiskohtade arv (new Tallinn builds);
  (5) OSM parking polygons Tallinn; (6) parking-app zone polygons (verify ToS, cache
  politely). TTL: on regulation change + annual.
- `P4-014` Rail Baltica / tram-extension construction phase (nuisance now, premium
  later). Buy Q: dust 2 yrs, value later? Source: project timetables. Shape:
  calendar dim with expiry. Extends G5/G12.
  Sources (Tallinn): (1) Rail Baltica Estonia (RB Rail) Ülemiste terminali
  ehitusgraafik; (2) Tallinna tram extensions (Vanasadama tramm, Pelguranna/Liivalaia
  plans) timetables; (3) Tallinna transpordi arengukava + üldplaneering 2035;
  (4) EHR ehitusload corridor-adjacent Tallinn parcels; (5) tallinn.ee tee
  sulgemised/ehitusplatside teated; (6) Elron ajutised sõiduplaanid (Tallinn).
  TTL: monthly, expiry-dated.
- `P4-015` Insurability: flood/theft tariff zones. Buy Q: insurable affordably?
  Source: insurer zones (verify openness). Shape: zone join, illiquidity flag.
  Extends G8/G16.
  Sources (Tallinn): (1) Keskkonnaagentuur flood zones, Tallinn (T10–T1000, storm
  surge); (2) PPA Tallinn varguste statistika per linnaosa (tariff proxy);
  (3) insurer tariff zones Tallinn — PZU/ERGO/If (verify openness first, else
  illiquidity flag only); (4) Maa-amet põhjavesi/storm-surge Tallinn layers;
  (5) Päästeamet Tallinn tulekahjude tihedus; (6) EELIS kaitsealad (building
  restrictions → insurability). TTL: annual.

## Batch 2 — long tail (turn 2)

- `P4-016` EGT engineering geology: turvas/karst/alvar, kandevõime, põhjavee
  kaitseala. Buy Q: foundation cost / septic feasible? Shape: per-parcel class join,
  coarse only (today only p183 groundwater proxy). Extends G3.
  Sources (Tallinn): (1) EGT (Eesti Geoloogiateenistus) insenergeoloogia kaardid —
  turvas/karst/alvar Tallinn (Lasnamäe paekivi, Pääsküla raba serv); (2) Maa-amet
  geoloogia WFS (maardlad/aluspõhi); (3) Keskkonnaagentuur põhjavee kaitseala Tallinn;
  (4) EHR vai/Geotehnilised aruanded per Tallinn new build (where public);
  (5) Tallinna ÜVK + sademevee kaardid (septic feasibility cross-check);
  (6) Maa-amet LiDAR DEM Tallinn (settlement/fill detection). TTL: annual bulk.
- `P4-017` Drinking-water quality + sewer reality (central vs puurkaev/omapuhasti,
  liitumiskohustus). Buy Q: 5-figure connection? Source: Terviseamet + KOV ÜVK
  plans. Shape: per-parcel join. Extends G7/G10.
  Sources (Tallinn): (1) Terviseamet joogivee kvaliteedi seire, Tallinn proovid;
  (2) Tallinna Vesi ÜVK kaardid (central vs puurkaev/omapuhasti, liitumiskohustus);
  (3) Tallinna Keskkonna- ja Kommunaalamet ÜVK arengukava (Nõmme/Pirita/Merivälja
  liitumispiirkonnad); (4) Keskkonnaamet vee-erikasutusload Tallinn;
  (5) EHR veevarustuse/kanalisatsiooni liik per Tallinn building;
  (6) Maa-amet põhjavee kaitseala (puurkaevu piirangud). TTL: annual.
- `P4-018` Snow/road maintenance class (teeregister + talihooldus tasemed, autumn
  refresh). Buy Q: winter trap? Shape: per-parcel road-class join. Extends G3/G12.
  Sources (Tallinn): (1) Transpordiamet teeregister, Tallinn street classes;
  (2) Tallinna Keskkonna- ja Kommunaalamet talihoolduse tasemed + hoolduspiirkondade
  kaart (autumn refresh); (3) tallinn.ee lumekoristuse teated + lumeladestuspaigad;
  (4) Tark Tee Tallinn teeolud; (5) Tallinna Transport talvine bussiliiklus (bus-cut
  cross-check); (6) OSM winter_service tags Tallinn (honest proxy). TTL: autumn.
- `P4-019` KOV fiscal health: võlakoormus, investments, maamaks trend. Buy Q: tax
  hike/service cut coming? Source: KOV eelarved + Statamet (forward of #242).
  Shape: per-KOV table, annual. Extends G16.
  Sources (Tallinn): (1) Tallinna linna eelarve + eelarvestrateegia (võlakoormus,
  investeeringud, tallinn.ee); (2) Rahandusministeerium KOV finantsandmed (Tallinn);
  (3) Statamet KOV finantsnäitajad; (4) EMTA maamaksu laekumine Tallinn + maamaksu
  määrade ajalugu (forward of #242); (5) Tallinna arengukava investeeringute tabel;
  (6) Riigikontroll KOV auditid (Tallinn where available). TTL: annual.
- `P4-020` Enforcement layer: pankrot/täitemenetlus + active kohtutäitur proceedings
  on property/developer. Buy Q: frozen deal? Shape: per-entity dim, weak-good
  capped like #233. Extends G4.
  Sources (Tallinn): (1) Ametlikud Teadaanded pankrotiteated, Tallinn entities;
  (2) kohtutäiturite register (active täitemenetlus, Tallinn property/developer);
  (3) e-Äriregister maksehäired/aruandevõlad (Tallinn developers);
  (4) Creditinfo/Krediidiinfo Tallinn developer scores (verify openness);
  (5) kohtute infosüsteem (published decisions, property/developer filter);
  (6) Maa-amet kitsendused (arest/keelumärge) per Tallinn parcel. Weak-good capped.
- `P4-021` Developer + broker track record: EHR ehitaja history, Tarbijakaitse
  complaints, cross-portal broker stats. Buy Q: trust seller? Shape: per-entity dim,
  feeds §6 anti-fraud. Extends G1/G17.
  Sources (Tallinn): (1) EHR ehitaja history per Tallinn developer (completions,
  load vs kasutusluba); (2) TTJA (Tarbijakaitse) kaebused Tallinn developers/brokers;
  (3) own cross-portal broker stats Tallinn (17 adapters: relist rate, DOM, price
  cuts); (4) e-Äriregister Tallinn developer age/turnover/aruanded;
  (5) Ametlikud Teadaanded developer notices; (6) Maa-amet tehingud per-developer
  Tallinn project resale performance. TTL: quarterly.
- `P4-022` Listing photo forensics: cross-portal duplicates + daylight sanity.
  Buy Q: relist/defect-hiding? Source: own 17-adapter store, zero vendor. Shape:
  per-listing dim. Extends G1.
  Sources (Tallinn): (1) own 17-adapter store Tallinn image-hash index (kv.ee,
  city24.ee, kinnisvara24.ee duplicates/relist detection, zero vendor);
  (2) listing EXIF/daylight sanity from own snapshots (Kalamaja vs Lasnamäe light
  check); (3) Maa-amet aerial photo Tallinn vintages (facade change cross-check);
  (4) EHR floorplan/room-count vs photo room-count mismatch flag;
  (5) Mapillary Tallinn sequences per street (facade truth, date-stamped).
  TTL: snapshot-driven, daily dedup.
- `P4-023` Airport + military noise: Tallinna müratsoonid (EANS) + harjutusväljad
  (Tapa/Sirgala/Soodla). Buy Q: legal insulation/resale hit? Shape: zone join, never
  walk-gradient (G9 covers roads only). Extends G9.
  Sources (Tallinn): (1) Tallinna strategic noise maps (END 2002/49/EC, Transpordiamet
  + Tallinna Keskkonnaamet); (2) EANS Tallinna lennu müra tsoonid (Lasnamäe/Pirita/
  Kesklinn approach); (3) Kaitsevägi harjutusalade teated (Tapa/Sirgala/Soodla —
  Tallinn kuuluvus); (4) Tallinna Sadam laeva/helikopteri müra teated;
  (5) Keskkonnaagentuur õhuseire Tallinn stations (Ämari rattle cross-check);
  (6) EHR insulation requirements per Tallinn noise-zone building. Never
  walk-gradient; zone join only.
- `P4-024` Country-health nuisances: tick risk, allergens beyond p260, PRIA
  spray-drift + farm odour buffers. Buy Q: kids/dogs safe? Shape: coarse hinnang
  cells. Extends G7.
  Sources (Tallinn): (1) Terviseamet puukentsefaliidi/puukborrelioosi Tallinn
  stats (Stroomi/Pirita/Nõmme green edges); (2) Keskkonnaagentuur õietolmu seire
  Tallinn (allergeenid beyond p260); (3) PRIA põllumassiivid Tallinn fringe
  (Harku/Lasnamäe edge spray-drift buffers); (4) Tallinna Keskkonnaamet farm-odour
  kaebused (Paljassaare/loomapidamine); (5) EELIS rohevõrgustik Tallinn (tick
  habitat proxy); (6) Terviseamet suplusvee kvaliteet (Pirita/Stroomi/Kakumäe).
  Coarse hinnang cells only.
- `P4-025` Micro-liquidity: REL2021 1 km age + ränne/vakants per KOV/linnaosa +
  school open/close plans. Buy Q: sellable in 10 yrs? Shape: per-KOV choropleth like
  #241. Extends G16/G20.
  Sources (Tallinn): (1) REL2021 1 km grid Tallinn (age mix, rände saldo, vakants);
  (2) Statamet ränne per Tallinna linnaosa; (3) KV.ee/city24 Tallinn kuulutuste
  DOM medians per asum (liquidity proxy); (4) Maa-amet tehingute arv per Tallinn
  asum (turnover); (5) Tallinna Haridusamet school open/close plans per linnaosa;
  (6) Tallinna arengukava rahvastikuprognoos per linnaosa. Per-KOV/linnaosa
  choropleth like #241.
## Batch 3 — operational exhaust / time-aware (turn 3)

- `P4-026` Municipal fix-it responsiveness: light faults, potholes, snow complaints,
  graffiti removal lag (abilliin/e-teenused where open). Buy Q: who fixes things?
  Shape: hex responsiveness rate, NULL where unpublished. Extends G17/G20.
  Sources (Tallinn): (1) Tallinna abiliin/e-teenused fix-it reports (valgustus,
  augud, lumi, grafiti — where open); (2) Tallinna Keskkonna- ja Kommunaalamet
  heakorra teated + removal lag; (3) Tallinna Munitsipaalpolitsei/korteriühistute
  kaebuste statistika per linnaosa; (4) Tark Tee Tallinn incidents response times;
  (5) OSM fixme/edit freshness Tallinn (meta-signal cross-check);
  (6) KÜ aruanded (trepikoja hoolduskulu Tallinn). NULL where unpublished.
- `P4-027` Grocery slots + ride-price probes: Barbora/Selver windows + Wolt/Bolt
  polygons 8am vs 10pm, one commute-hour ride probe/district/week cached. Buy Q:
  food + car-free life at night? Shape: district bands + per-listing context. G13.
  Sources (Tallinn): (1) Barbora/Selver e-poe delivery windows per Tallinn district
  (polite probe, cache); (2) Wolt/Bolt Food coverage polygons 8am vs 10pm Tallinn;
  (3) Bolt ride-price one-commute-hour probe per district/week (cached, polite);
  (4) Tallinna öötransport (ööbussid) coverage; (5) OSM shops/supermarkets Tallinn
  opening_hours (Selver/Maxima/Rimi/Konsum); (6) Omniva/SmartPOST/DPD parcel points
  Tallinn. ToS-checked, cached.
- `P4-028` Listing demand exhaust: views/day, photo count, update history, broker
  response lag from own store. Buy Q: stale vs steal? Shape: per-listing dim. G1.
  Sources (Tallinn): (1) own 17-adapter store Tallinn exhaust (views/day, photo
  count, update history, broker response lag); (2) kv.ee/city24/kinnisvara24 Tallinn
  vaatamiste/salvesta counters (polite snapshots); (3) broker reply-time probes
  Tallinn (rate-limited, cached); (4) P4-001 DOM history join (stale-vs-steal);
  (5) P4-022 relist flag join; (6) Maa-amet ask-vs-close gap per Tallinn asum
  (demand calibration). Zero vendor.
- `P4-029` Street-imagery block observer: Mapillary/KartaView CV for facade, litter,
  wrecks, sidewalks, date-stamped. Buy Q: eye-level street? Shape: per-listing dim
  with photo date. Extends G18/G20.
  Sources (Tallinn): (1) Mapillary Tallinn sequences (facade, litter, wrecks,
  sidewalks, date-stamped); (2) KartaView Tallinn coverage (gap-fill);
  (3) Maa-amet aerial + street-level vintages Tallinn; (4) Tallinna veebikaart
  orthophoto history per street; (5) OSM sidewalk/surface tags Tallinn
  (ground-truth cross-check); (6) own listing-photo date sanity (P4-022 join).
  Per-listing dim with photo date.
- `P4-030` Satellite change delta: Sentinel-2 NDVI/construction year delta. Buy Q:
  disappearing grove, new neighbour, dump? Shape: coarse change flag. Extends G18.
  Sources (Tallinn): (1) Copernicus Sentinel-2 NDVI year-delta Tallinn tiles;
  (2) Maa-amet aerial vintages Tallinn (construction/roheala change);
  (3) Tallinna Keskkonnaamet raieload/hooldusraie teated per linnaosa;
  (4) EHR ehitusload (new-neighbour cross-check); (5) Tallinna jäätmejaamade/
  ebaseaduslike prügilate teated (dump flag); (6) EELIS rohealade muutused Tallinn.
  Coarse flag only.
- `P4-031` Backyard weather + DIY air: personal stations + sensor.community density
  for frost pockets, wind tunnels. Buy Q: heating/balcony truth? Shape: coarse
  hinnang with sensor-count reason. Extends G8.
  Sources (Tallinn): (1) sensor.community DIY sensors Tallinn density (frost/wind
  pockets); (2) Tallinna smart-city sensor pilot data (where open, e.g. Tehnopol
  pre-test network); (3) Keskkonnaagentuur Ilmateenistus Tallinn-Harku station
  baseline; (4) EHR kütte liik per Tallinn building (heating-truth join);
  (5) Maa-amet LiDAR DEM Tallinn (cold-air drainage/frost pockets);
  (6) OSM shelter/exposure tags Tallinn balconies. sensor-count reason attached.
- `P4-032` Activity heat as usage proxy: aggregated evening foot/bike activity
  (counts only, no individuals). Buy Q: lived-in evening street? Shape: hex usage
  hinnang, labelled usage-not-safety. Extends G11/G20.
  Sources (Tallinn): (1) aggregated evening foot/bike counters Tallinn (counts
  only, no individuals — e.g. city mobility project MPD aggregates where open);
  (2) Tallinna rattaloendurid (bike counters); (3) Elron/TLT evening ridership
  per Tallinn stop (usage proxy); (4) OSM leisure/amenity evening-hours density
  Tallinn; (5) Tallinna valgustatud teede kaart (lit-street usage proxy);
  (6) PPA/Päästeamet explicitly NOT used (usage-not-safety label). Hex hinnang.
- `P4-033` Seasonal nuisance calendar: cruise days, Lauluväljak/Pirita events, bells,
  hunting season, exercise weeks, snow-dump trucking. Buy Q: when loud? Shape:
  calendar dims with dates, never gradient. Extends G9/G20.
  Sources (Tallinn): (1) Tallinna Sadam cruise schedule (Vanasadam traffic days);
  (2) Lauluväljak/Pirita event calendars (Tallinn Culture programme);
  (3) Tallinna kirikute kellad + ürituste müra load (Kesklinn/Vanalinn);
  (4) Keskkonnamet jahiteated Tallinn fringe (Pirita/Nõmme hunting season);
  (5) Kaitsevägi õppuste teated (Tallinn-audible weeks);
  (6) Tallinna lumeladestus + talihoolduse veograafik (snow-dump trucking).
  Calendar dims with dates.
- `P4-034` Summer overheating risk: S/W top floor + no through-draft + cooling-degree
  trend. Buy Q: August sauna flat? Shape: per-listing physics sim, capped. G18/G2.
  Sources (Tallinn): (1) EHR orientation/floor/glazing per Tallinn listing (S/W top
  floor inputs); (2) Maa-amet LiDAR/LoD2 Tallinn (shading/through-draft geometry);
  (3) Ilmateenistus Tallinn cooling-degree trend (Harku station);
  (4) EHR jahutuse/ventilatsiooni liik per building; (5) listing-text NLP
  (läbiv tuulutus, konditsioneer) from own adapters; (6) KÜ aruanded (katuse/soojustuse
  seis). Capped physics sim.
- `P4-035` December darkness: lamp inventory × VIIRS × sun hours. Buy Q: cave in
  December? Shape: per-listing dim. Extends G18.
  Sources (Tallinn): (1) Tallinna tänavavalgustuse inventory/kaart per street;
  (2) NOAA VIIRS radiance Tallinn tiles; (3) Ilmateenistus Tallinn sun-hours
  December baseline; (4) Maa-amet LiDAR/DEM Tallinn (courtyard shading);
  (5) EHR orientation/floor/window-area per listing; (6) OSM lit=yes tags Tallinn
  (honest proxy). Per-listing dim.
- `P4-036` Roof income: solar feed-in (Elering rules), mast-rent possibility, gable
  ad walls. Buy Q: yield kicker? Shape: per-building upside dim. Extends G10/G18.
  Sources (Tallinn): (1) Elering päikese feed-in rules + mikrotootja tingimused
  (Tallinn connections); (2) Elektrilevi liitumiskaart Tallinn (roof export
  feasibility); (3) Maa-amet LiDAR/LoD2 Tallinn roof facets (PVLib shading inputs);
  (4) Tallinna reklaamimaks + välireklaami load (gable ad-wall yield);
  (5) EHR katuse tüüp/pindala per Tallinn building; (6) Utilitas kaugkütte
  tagastustemperatuuri boonused (Tallinn where applicable). Upside-only dim.
- `P4-037` Policy exposure: automaks + future congestion/car-free expansion by commute
  dependence. Buy Q: expensive by decree? Shape: per-listing exposure band. G16.
  Sources (Tallinn): (1) EMTA automaksu kalkulaator + CO2 bands per listing car
  dependence; (2) Tallinna tasulise parkimise + autovaba ala laienemisplaanid
  (Kesklinn/Vanalinn); (3) Tallinna ummikumaksu arutelud/otsused (tallinn.ee);
  (4) TLT/Peatus.ee commute alternatives per Tallinn address (exposure offset);
  (5) Transpordiamet liikluspiirangute teated Tallinn; (6) Rahandusministeerium
  automaksu laekumine Tallinn (policy calibration). Exposure band.
- `P4-038` Bargaining margin: Land Board offer-vs-close gap per area type. Buy Q:
  opening bid? Shape: area-type table feeding steal sort. Extends G16.
  Sources (Tallinn): (1) Maa-amet tehingud offer-vs-close gap per Tallinn area type
  (Land Board publication); (2) KV.ee/city24 Tallinn asking vs P4-002 micro-comp
  residuals; (3) Statamet KK11 Tallinn quarterly medians (gap calibration);
  (4) own adapter price-drop distribution Tallinn per asum; (5) Tallinn bank collateral survey aggregates (verify openness);
  (6) notariaalsete tehingute Tallinn
  mahud (market-heat adjustment). Feeds steal sort.
- `P4-039` Civic capital: precinct turnout + OSM edit freshness as meta-signal.
  Buy Q: maintained commons? Shape: precinct/hex choropleth, Group-20 taste-match
  only, never ethnic/wealth proxy. Extends G20.
  Sources (Tallinn): (1) valimiskomisjoni turnout per Tallinna valimisjaoskond;
  (2) OSM edit freshness Tallinn hex (maintained-commons meta-signal);
  (3) Tallinna kaasava eelarve participation per linnaosa; (4) Tallinna
  heakorrakampaaniate (Teeme Ära) participation per asum; (5) KÜ aruanded Tallinn
  (remondifondi kogumine = commons care); (6) Tallinna raamatukogude/noortekeskuste
  külastus per linnaosa (civic use). Taste-match only, never ethnic/wealth proxy.
## Batch 4 — Sutherlandesque psycho-logic spike (turn 4)

- `P4-040` Last 200 m arrival sequence (peak-end rule). Buy Q: 23:00 November walk
  home? Proxy: street-imagery arrival + lamp + lit-window density. Shape: per-listing
  dim with photo date. Extends G20/G18.
  Sources (Tallinn): (1) Mapillary Tallinn arrival sequences per street (last-200 m
  walk, date-stamped); (2) Tallinna valgustatud teede + lit-window density proxy
  (November 23:00 check); (3) OSM footway/lighting/surface Tallinn per approach;
  (4) Päästeamet/PPA explicitly NOT used (arrival feel ≠ safety claim);
  (5) Maa-amet aerial Tallinn (enclosure/green arrival); (6) own listing-photo
  arrival sanity (P4-022 join). Peak-end framing documented.
- `P4-041` Glimpse economics (`piilukas`, not `vaade`): sea/Old Town/spire sliver via
  LiDAR/LoD2 fan. Buy Q: 80% joy, 20% price? Shape: per-listing view class.
  Arbitrage vs no-view pricing. Extends G18.
  Sources (Tallinn): (1) Maa-amet LiDAR/LoD2 Tallinn view-fan (sea/Old Town/spire
  sliver: Pirita tee, Kalamaja, Lasnamäe pank); (2) EHR floor/height per Tallinn
  listing (glimpse inputs); (3) Muinsuskaitseamet Vanalinna vaatekoridorid
  (protected-view constraints); (4) Tallinna üldplaneering vaatekohtade register;
  (5) own adapter price residuals Tallinn (piilukas premium vs no-view);
  (6) Maa-amet aerial vintages (future-view blockage: P4-006 join). View class.
- `P4-042` Smell/dawn-chorus map: bakeries/roasters + lilac vs smoke/rubbish, odour
  complaints. Buy Q: memory anchor? Shape: coarse hinnang cells, never doorway
  precision. Extends G7/G11.
  Sources (Tallinn): (1) OSM bakeries/roasters Tallinn (Kalamaja/Põhjala, Rotermann)
  + lilac/green anchors (Kadriorg, Hirvepark dawn-chorus spots); (2) Tallinna
  Keskkonnaamet odour complaints (smoke/rubbish/prügimajad); (3) Keskkonnaagentuur
  Tallinn air stations (smoke-episode cross-check); (4) Tallinna Haljasala inventory
  (blossom/mädanenud lehed seasonality); (5) Päästeamet chimney-smoke teated Nõmme/
  Merivälja heating season; (6) e-Äriregister Tallinn food-producer addresses
  (brewery/fish-smoke anchors). Coarse hinnang, never doorway precision.
- `P4-043` Number-13 / name arbitrage: floor/house 13 + unsexy-street discount vs
  prestige premium, from tehingud residuals. Buy Q: discount for unbothered? Shape:
  per-listing steal flag, taste-match. Extends G16/G20.
  Sources (Tallinn): (1) Maa-amet tehingud residuals Tallinn (floor/house-13 +
  unsexy-street discount vs prestige premium: e.g. Mustamäe vs Kadriorg spread);
  (2) own adapter DOM/price-cut stats per Tallinn street prestige band;
  (3) Statamet KK11 per Tallinn linnaosa (prestige baseline); (4) EHR floor data
  Tallinn (13th-floor identification); (5) Tallinna asumite hinnakihid (KV.ee/city24
  medians); (6) REL2021 Tallinn education/occupation mix (prestige controls, never
  worth judgement). Taste-match flag.
- `P4-044` Herd of picky people: REL2021 occupation mix (architects/chefs/lens jobs)
  at 1 km, aggregated. Buy Q: leading gentrification? Shape: grid taste-match, never
  worth judgement. Extends G20.
  Sources (Tallinn): (1) REL2021 occupation mix Tallinn 1 km grid (architects/chefs/
  lens jobs, aggregated); (2) e-Äriregister creative-sector employer addresses
  Tallinn (Telliskivi/Paavli/Noblessner clusters); (3) EHIS/HaridusSilm Tallinn
  art/music school density (leading-indicator cross-check); (4) OSM atelier/galerii/
  specialty-coffee Tallinn density (taste-match, never worth judgement);
  (5) Tallinna loomemajanduse statistika per linnaosa; (6) Maa-amet tehingute
  gentrification-front tracking per Tallinn asum. Grid taste-match.
- `P4-045` Third places + keeper effect: sauna/pub/library evening hours +
  long-tenure independents. Buy Q: belong, not just sleep? Shape: per-listing
  context dim. Extends G11/G20.
  Sources (Tallinn): (1) OSM sauna/pub/library Tallinn + opening_hours evening
  filter (Telliskivi, Pelgulinn, Kalamaja third places); (2) Tallinna
  Keskraamatukogu + haruraamatukogude lahtiolekuajad per linnaosa;
  (3) e-Äriregister long-tenure independents Tallinn (keeper effect: >10 yr
  same-address cafés/workshops); (4) Tallinna kultuurikalender evening events
  per asum; (5) TLT/Peatus.ee evening access per third place;
  (6) REL2021 Tallinn evening-population grid (belonging demand). Context dim.
- `P4-046` Dread removal (loss aversion): fireplace+heat, well+city water, 2nd exit
  road, draining ground floor. Buy Q: what can't strand me? Shape: per-listing
  redundancy dims. Extends G2/G3/G10.
  Sources (Tallinn): (1) EHR kütte liik + kamina/ahju olemasolu per Tallinn building
  (fireplace+heat redundancy); (2) Tallinna Vesi ÜVK + puurkaevu load (well+city
  water, Nõmme/Pirita); (3) Transpordiamet teeregister 2nd-exit check per Tallinn
  fringe parcel; (4) Keskkonnaagentuur flood/groundwater Tallinn (draining ground
  floor); (5) Elektrilevi/Elering backup-feed info Tallinn (where published);
  (6) listing-text NLP (kamin, kaev, varuväljapääs) from own adapters. Dread-removal
  framing documented.
- `P4-047` Small horrors: seagulls, leaf-blowers Sun 8am, 4am plow burial, moped/
  fireworks alleys. Buy Q: 2-week dealbreaker? Shape: calendar dims. Extends G9/G20.
  Sources (Tallinn): (1) Tallinna Keskkonnaamet mürakaebused (kajakad Kesklinn/
  Vanasadam, lehepuhurid, mopeedid); (2) Tallinna talihoolduse veograafik per street
  (4am plow-burial); (3) Tallinna ilutulestiku load + jaanipäeva/uusaasta calendar;
  (4) Transpordiamet/Päästeamet Tallinn event-traffic teated (fireworks alleys);
  (5) OSM leisure=noise spots Tallinn (honest proxy); (6) KÜ kaebuste logid (where
  open, hex only). Calendar dims.
- `P4-048` Small delights: breakfast sun, bench view <3 min, mushroom/swim/gym/ice
  <15 min, allotment queue length (queues = true demand). Buy Q: daily joy? Shape:
  per-listing dims + queue tables. Extends G11/G18/G20.
  Sources (Tallinn): (1) OSM hommikupäikese orientation (EHR orientation per
  listing, breakfast-sun check); (2) Tallinna pinkide/vaatekohtade register (<3 min
  bench view: Kadriorg, Hirvepark, Pirita promenaad); (3) RMK seenemetsad + Pirita/
  Stroomi ujulad + Tallinna spordikeskuste (gym/ice) <15 min isochrones;
  (4) Tallinna linnaaiad/aiandusühistute järjekorrad (Lillepi, Pelgu — queues =
  true demand); (5) Tallinna rohealade kava (swim/gym/ice access);
  (6) Peatus.ee/TLT <15 min access per delight. Queue tables annual.
- `P4-049` Taxi/guest test: findability, name pronounceability, Sat 19:00 guest
  parking, entrance tidiness. Buy Q: pride + resale? Shape: per-listing usability
  dim. Extends G12/G20.
  Sources (Tallinn): (1) Ads/DSM findability probe per Tallinn address (Takso/Bolt
  search hit-rate, cached); (2) kohanimeregister (name pronounceability: e.g.
  Õismäe vs Kadriorg guest test); (3) Tallinna parkimisloa külalisparkimise reeglid
  per zone (Sat 19:00 guest parking); (4) TLT/Peatus.ee guest-arrival time per
  address; (5) listing-photo entrance tidiness (P4-022/P4-029 join);
  (6) OSM entrance/wheelchair tags Tallinn (usability cross-check). Pride+resale
  framing documented.
## Batch 5 — deeper cuts (turn 5)

- `P4-050` Permit glut vs completions per micro-area (load vs kasutusluba). Buy Q:
  buying into falling prices? Shape: pipeline count, quarterly. Extends G2/G16.
  Sources (Tallinn): (1) EHR ehitusload per Tallinn micro-area (load pipeline);
  (2) EHR kasutusload per Tallinn micro-area (completions); (3) TPR detailplaneeringu
  elluviimise mahud Tallinn (forward pipeline); (4) Tallinna ehitusstatistika per
  linnaosa (quarterly); (5) Maa-amet tehingute hinnad per Tallinn asum (falling-price
  join); (6) Statamet elamuehituse statistika Tallinn. Quarterly count.
- `P4-051` Zero-consumption stairwells (aggregated empty-investor units, hex/KOV
  only, never addresses). Buy Q: dead stairwell, no repair fund? Shape: hex
  governance-risk flag. Extends G10/G17.
  Sources (Tallinn): (1) Elektrilevi aggregated zero-consumption meters per Tallinn
  hex/KOV (investor-empty proxy, hex only, never addresses); (2) Tallinna Vesi
  aggregated zero-flow connections per hex (cross-check); (3) REL2021 vakants per
  Tallinn 1 km grid; (4) e-Äriregister KÜ aruanded (kogumata remondifond = dead
  stairwell signal); (5) KV.ee/city24 long-DOM clusters per Tallinn hex;
  (6) Statamet rahvastikuregister tühjad eluruumid Tallinn. Hex flag, privacy-safe.
- `P4-052` Turnover wave per building from tehingud (problem vs gentrifying — both
  readings in reason). Buy Q: why does everyone leave/storm in? Shape: per-building
  dim. Extends G16.
  Sources (Tallinn): (1) Maa-amet tehingud turnover wave per Tallinn building
  (problem vs gentrifying — both readings in reason); (2) KV.ee/city24 relist
  frequency per Tallinn building (own store); (3) REL2021 sisse/väljaränne per
  Tallinn 1 km grid; (4) e-Äriregister KÜ aruanded (remondifondi dünaamika per
  building); (5) Tallinna school-catchment changes per asum (demand-shift reading);
  (6) EHR renoveerimisload per building (storm-in reading). Both readings in reason.
- `P4-053` Odour roses by wind frequency (Paljassaare, asphalt, brewery, fish smoke).
  Buy Q: 15 downwind days? Shape: sector + calendar dim, not circle buffer. G7.
  Sources (Tallinn): (1) Ilmateenistus Tallinn-Harku wind rose (sector frequency);
  (2) Keskkonnaagentuur Tallinn air stations (Paljassaare/asfaldi/õlle/kalasuitsu
  episode validation); (3) Tallinna Keskkonnaamet odour complaints per sector;
  (4) e-Äriregister emitter addresses Tallinn (Paljassaare reoveepuhasti, asfaldi-
  tehas, pruulikoda, kalasuits); (5) EELIS emission-source register Tallinn;
  (6) Tallinna Sadam harbour-odour teated (sector cross-check). Sector + calendar,
  never circle buffer.
- `P4-054` Quarry blast + truck season (paekivi near Maardu/Harku). Buy Q: Tuesday
  7am? Shape: timetable + buffer dim. Extends G3/G9.
  Sources (Tallinn): (1) Maa-amet maardlate register (paekivi quarries: Maardu/Harku
  fringe affecting Pirita/Lasnamäe edge); (2) Keskkonnamet kaevandamisload +
  lõhkamiste ajagraafik; (3) Transpordiamet raskeveokite marsruudid Tallinn fringe;
  (4) Tallinna Keskkonnaamet mürakaebused (blast/truck season);
  (5) EGT geoloogia kaardid (quarry proximity); (6) Tark Tee truck-traffic Tallinn
  fringe. Timetable + buffer.
- `P4-055` Harbour/air timetable nuisances: foghorns, icebreakers, Ämari rattle,
  Männiku weekend pops. Buy Q: schedulable noise? Shape: calendar dims. Extends G9.
  Sources (Tallinn): (1) Tallinna Sadam laevagraafik (foghorns, icebreakers —
  Vanasadam/Pirita); (2) EANS Tallinna lennuinfo (Ämari rattle corridors);
  (3) Kaitsevägi Männiku harjutusväljaku laskmisteated (weekend pops, Nõmme edge);
  (4) Veeteede Amet jäämurde teated Tallinn Bay; (5) Tallinna Keskkonnaamet
  mürakaebused (schedulable-noise validation); (6) Elron Tallinna
  raudteemüra ööaknad (maintenance windows). Calendar dims.
- `P4-056` Enclosed-courtyard trap via LiDAR enclosure index (cold + fumes + heat
  held). Buy Q: microclimate pocket? Shape: per-parcel morphology join. Extends G18.
  Sources (Tallinn): (1) Maa-amet LiDAR/LoD2 Tallinn enclosure index (Kesklinn/
  Vanalinn courtyards: külm + heitgaasid + kuumus); (2) EHR hooviala/ehitusaluse
  pinna suhe per Tallinn parcel; (3) Tallinna haljastus inventory (courtyard green
  deficit); (4) Keskkonnaagentuur Tallinn air stations (fume-hold validation);
  (5) Ilmateenistus Tallinn wind data (ventilation proxy);
  (6) Maa-amet aerial vintages (courtyard infill change). Per-parcel join.
- `P4-057` Heat-pump hum corridors (suburban outdoor units vs bedroom windows).
  Buy Q: neighbour hum? Shape: weak hinnang from heating-type change. Extends G10.
  Sources (Tallinn): (1) EHR kütte liigi muutused per Tallinn suburban building
  (õhksoojuspump uptake: Nõmme/Pirita/Merivälja); (2) Tallinna Keskkonnaamet
  mürakaebused (heat-pump hum corridors); (3) EHR ehitusload (väliseadmete
  placement); (4) Maa-amet aerial vintages (outdoor-unit spotting, coarse only);
  (5) listing-text NLP (soojuspump) from own adapters; (6) KÜ aruanded (heating
  capex notes per Tallinn KÜ). Weak hinnang only.
- `P4-058` Falling-ice roofs + coastal cliff retreat (sidewalk liability, Türisalu/
  Paldiski shoreline change). Buy Q: winter liability / eroding edge? Shape:
  per-parcel dims with dates. Extends G2/G3/G8.
  Sources (Tallinn): (1) Tallinna Keskkonna- ja Kommunaalamet jääpurikate/lume
  eemaldamise kohustused + hoiatused per street; (2) Päästeamet Tallinn ice-fall
  incidents (sidewalk liability); (3) EHR katuse tüüp/kalle per Tallinn building
  (falling-ice risk); (4) Maa-amet shoreline change (Kakumäe/Pirita cliff retreat);
  (5) Keskkonnaagentuur storm-surge Tallinn
  (erosion edge); (6) KÜ aruanded (katusehoolduse kulud). Dims with dates.
- `P4-059` Wood-burning restriction zones (tahkekütte piirangud). Buy Q: stranded
  stove asset? Shape: per-parcel rule join. Extends G2/G7.
  Sources (Tallinn): (1) Tallinna tahkekütte piirangualad (Keskkonnaamet +
  Tallinna Keskkonnaamet notices, Kesklinn/Vanalinn priority); (2) EHR kütte liik
  per Tallinn building (stove asset inventory); (3) Keskkonnaagentuur Tallinn air
  stations (smoke-episode enforcement areas); (4) Päästeamet korstnapühkimise/
  küttekollete teated Tallinn; (5) Tallinna kliimakava heating-transition zones;
  (6) listing-text NLP (ahi/kamin/puuküte) from own adapters. Rule join.
- `P4-060` Stormwater fee zones + renovation-subsidy queue position. Buy Q: future
  bill vs subsidy? Shape: zone table + queue dim. Extends G10/G17.
  Sources (Tallinn): (1) Tallinna Vesi sademevee tasu piirkonnad + hinnakiri;
  (2) Tallinna ÜVK sademevee ärajuhtimise tsoonid per parcel;
  (3) EIS renoveerimistoetuste järjekord, Tallinn queue position (P4-010 join);
  (4) Tallinna Kommunaalamet sademevee/soodustuste teated; (5) Maa-amet
  vett mitteläbilaskva pinna kiht Tallinn (fee-base proxy); (6) KÜ aruanded
  (sademevee kulu rida). Zone table + queue dim.
- `P4-061` Last-shop/pharmacy/ATM + bus-cut tracker per settlement (closures +
  Peatus diffs). Buy Q: liquidity spiral outside Tallinn/Tartu? Shape: settlement
  checklist, annual. Extends G11/G12/G16.
  Sources (Tallinn): (1) Peatus.ee GTFS diffs per Tallinn fringe stop (bus-cut
  tracker: Harku/Maardu/Saue directions); (2) TLT liinimuudatuste teated Tallinn;
  (3) Elron sõiduplaanimuudatused Tallinn fringe stations (Lilleküla/Kitseküla/
  Ülemiste); (4) OSM shop/pharmacy/ATM Tallinn fringe + opening_hours closures;
  (5) Tallinna äärealade teenuste kava (Pirita/Merivälja/Mähe last-shop watch);
  (6) Statamet rahvastik + Maa-amet tehingud per fringe settlement (spiral check).
  Tallinn-fringe reading of a national tracker.
- `P4-062` Rat complaints + ice-fall warnings aggregated (waste discipline + roof
  neglect, hex only). Buy Q: neglected block? Shape: hex operational flags. G7/G17.
  Sources (Tallinn): (1) Tallinna Keskkonnaamet näriliste/rotikaebused per hex
  (waste-discipline proxy, hex only); (2) Tallinna heakorra jäätmeveo rikkumiste
  teated per linnaosa; (3) Päästeamet Tallinn ice-fall warnings per hex (roof
  neglect); (4) Tallinna abiliin/e-teenused fix-it lag per hex (P4-026 join);
  (5) KÜ aruanded (prügiveo/hoolduse kulud per Tallinn KÜ); (6) OSM
  waste-disposal tags Tallinn (coverage cross-check). Hex flags, never addresses.

## Non-goals (explicitly excluded)

Court-decision mining on neighbours, sanctions scraping of private sellers,
social-media sentiment on blocks, individual mobile tracking, review-rating truth
(volume as activity proxy is allowed; rating as quality proof is not). All violate
public-repo / no-personal-data hygiene or polite-automation rules.

## Counts

62 ideas: batch 1 (15: `P4-001`–`P4-015`), batch 2 (10: `P4-016`–`P4-025`), batch 3
(14: `P4-026`–`P4-039`), batch 4 (10: `P4-040`–`P4-049`), batch 5 (13: `P4-050`–
`P4-062`). Recommended first funds: `P4-001` history/DOM, `P4-007` KÜ loan,
`P4-006` neighbouring-plan buffer; wildest payoffs: `P4-026` fix-it rate, `P4-029`
block observer, `P4-033` nuisance calendar.

