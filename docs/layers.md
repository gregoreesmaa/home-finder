# Parameter layers — how every parameters3.md parameter is implemented

`parameters3.md` catalogs **500 parameters** (§5, 20 groups; §8 verification
index). This document is the implementation registry: **every one of the 500
is implemented on `main`**, either as a map layer or as a documented
no-map verdict with a scorer dimension. No parameter is guessed, faked, or
left without an owner.

Live maps: `/layers` (dev: `npm run dev --workspace @home-finder/web`).
Data: local snapshot `2026-09-12` (`~/hf-data/2026-09-12`). No live
Overpass/API calls in the map path.

## 1. The three implementation kinds

Every parameter gets exactly one verdict, following AGENTS.md §7 (Evidence
before claims, Honest systems over fake precision, Zero synthetic guessing):

| Kind | Meaning | Where |
|---|---|---|
| **Map layer** | Green = good, red = bad, measured along the real Harjumaa footpath network (or an honestly-labelled Euclidean/proxy kernel). Scores absolute 0–100. | `apps/web/lib/layers*.ts` (`paramIds`), raster masters in the snapshot |
| **Honest proxy** (`hinnang`) | A map layer where the title, legend and source say it is a proximity/estimate proxy — never measured registry data. Used where no registry data exists in the snapshot but an OSM signal honestly discriminates. | Same registry, `(hinnang)`/`(proksi, hinnang)` titles |
| **Documented no-map** | No gradient map ships (OTA PR #131 precedent: a map that cannot honestly discriminate misleads). The verdict file documents WHY with snapshot evidence, points at the nearest shipped map if one exists, and the parameter ships as a **scorer dim**: a pure hermetic function `(origin, pois) -> (score | None, Estonian reason)` in `services/scoring/dims_*.py`. Per-deal, per-parcel, legal, macro-series, forensic and subjective params live here — they describe a deal, a parcel, a person or a workbench, not a place. | `GROUP*_NO_MAP` verdicts + `dims_*.py` |

Batch convention (see `apps/web/lib/layers_group03b.ts`, issue #152): each
batch is self-contained — one `layers_group*.ts` verdict registry, one
`dims_*.py` scorer module, one test file per side, **zero shared-file
edits** (`*_HOOK` marker states the no-wiring contract). Reasons are in
Estonian; NULL dims carry `hinnang` + `EI OLE` markers pinned by tests.

## 2. Counts (machine-verified)

```
owned: 500
missing: 0 []
```

Audit command (run from repo root; `origin/main` or any commit):

```bash
python3 -c "
import subprocess, re
files = subprocess.run(['git','ls-tree','-r','--name-only','origin/main',
  '--','apps/web/lib/'], capture_output=True, text=True).stdout.splitlines()
ts = [f for f in files if f.endswith('.ts') and '.test.' not in f]
owned = set()
for f in ts:
    c = subprocess.run(['git','show','origin/main:'+f],
      capture_output=True, text=True).stdout
    for m in re.findall(r'ALL_PARAMS\s*=\s*\[([^\]]*)\]', c):
        owned |= {int(n) for n in re.findall(r'\d+', m) if 1 <= int(n) <= 500}
    for m in re.findall(r'PARAM_IDS[^=]*=\s*\{([^}]*)\}', c):
        owned |= {int(n) for n in re.findall(r':\s*(\d+)', m) if 1 <= int(n) <= 500}
    for m in re.findall(r'paramIds:\s*\[([^\]]*)\]', c):
        owned |= {int(n) for n in re.findall(r'\d+', m) if 1 <= int(n) <= 500}
pys = subprocess.run(['git','ls-tree','-r','--name-only','origin/main',
  '--','services/scoring/'], capture_output=True, text=True).stdout.splitlines()
for f in [f for f in pys if f.endswith('.py') and '/tests/' not in f and 'dims_' in f]:
    c = subprocess.run(['git','show','origin/main:'+f],
      capture_output=True, text=True).stdout
    owned |= {int(m) for m in
      re.findall(r'^[\s*#\"\']*[\*\-]\s*p(\d{1,3})\b', c, re.M) if 1 <= int(m) <= 500}
print('owned:', len(owned))
print('missing:', sorted(set(range(1, 501)) - owned))
"
```

Split (same method, `paramIds` values only): **98 map-layer params**,
**402 documented no-map + scorer dim**. Map layers never render unknown as
zero: null encodes 255 and renders red (red = bad *or* honestly-unknown).

## 3. Group reconciliation (parameters3.md §5 → implementation)

| Group | Params | Map layers (paramIds) | No-map + dims | Batch files |
|---|---|---|---|---|
| 1 Listing portals (40) | 40 | — | 40: per-listing facts, no area signal | `layers_group01a/b` + `dims_group01a/b` (#202, #203) |
| 2 EHR registry (9) | 9 | 196 | 21, 30, 33, 35, 48, 79, 154, 495 | `layers_group02/02b` + `dims_group02/02b` (#136, #137) |
| 3 Cadastre (22) | 22 | 50, 332, 340 | 19 incl. 29, 68, 71, 75 | `layers_group03/03b/03c/03d/03e` (#151–#155) |
| 4 Title/legal (17) | 17 | 364 (p364 ships twice — dims_overturn_maa scorer hint stands; maaparcel kataster omandivorm-class overlay, polygons only, outside stays unknown) | 16: per-parcel registry facts | `layers_group04` + `dims_group04` (#204) + `layers_maaparcel`/`batch_maaparcel_kataster` (#235, #491) |
| 5 Plans (27) | 27 | 42, 44, 47, 106, 146, 223, 224, 225, 230, 381, 485 (p47 ships as harvest-gated `planktpr` fills — honestly empty live, see `docs/p4_planktpr.md` #492) | 16 | `layers_group05a–05f` (#161–#166) + `layers_planktpr` (#492) |
| 6 Heritage (12) | 12 | 72, 352, 353, 356 | 8 | `layers_group06/06b` (#138, #139) |
| 7 Env health (20) | 20 | 61, 62, 189, 202, 227, 257, 409, 450 | 12 | `layers_group07/07b/07c/07d` (#140–#143) |
| 8 Climate/flood (16) | 16 | 69, 112, 255, 333, 334, 336, 447 (p112 ships twice — g08a OSM no-map verdict stands; floodzone KAUR zone-join overlay, polygons only) | 10 (incl. p112-outside: the join stays NULL outside every polygon) | `layers_group08a–08d` (#167–#170) + `layers_flood`/`dims_overturn_flood`/`batch_flood_kaur` (#239, #487) |
| 9 Noise (8) | 8 | 16, 138, 162, 234, 301, 408, 445, 493 (proxies) | — | `layers_group09` + `layers_genv` (#104, #124) |
| 10 Utilities (18) | 18 | 215, 51, 53, 54 | 14 incl. 262, 265 (dims; p51 ships twice — fiber + mobile — on one param) | `layers_group10rest` + `layers_batch10c` + `dims_group10/10b/10c/10rest` (#105, #107, #121, #171, #230) |
| 11 OSM amenities (24) | 24 | 23: 14, 19, 20, 84, 86–89, 101–103, 108, 124, 169, 190, 313, 338, 346, 419, 442, 462, 466, 470 | 317 (no-map) | `layers.ts` core + `layers_batch1` + `layers_group11c/d` + dims (#98, #134, #135) |
| 12 Transit (5) | 5 | 15, 125, 343 (p15 ships three times — transit + gtfsstops + busmesh — on one param) | 11, 17 (commute dims, no layer) | core + `layers_batch4` + `layers_gtfsstops` + `layers_busmesh` + `dims_group12`/`dims_batch6`/`dims_p4_gtfsstops`/`dims_p4_busmesh` (#99, #126, #133, #483, #764, #769) |
| 13 Logistics (5) | 5 | 141, 220, 270, 282, 342 | — (all five ship; 220/270 via batch6 mobility proxies) | `layers_batch4/6` + `dims_group13` (#99, #126, #133) |
| 14 Safety (5) | 5 | 13, 78, 315, 335, 467 (proxies) | — | `layers_batch5` (#102) |
| 15 Education (5) | 5 | 12, 123, 130, 314, 386 | — | core + `layers_group15` + `layers_batch6` (#116, #133) |
| 16 Macro/finance (44) | 44 | — | 44: market-wide series / deal facts, not place-varying | `layers_group16a/b` + `dims_group16a/b` (#205, #206) |
| 17 HOA (22) | 22 | 187, 245, 311, 312, 469 | 17 incl. p3, p4 | `layers_group17a/b/c/rest` (#177, #178, #196, #207) |
| 18 Spatial sim (29) | 29 | 7: 34, 63, 181, 305, 405, 468, 479 | 22 (scorer dims: solar/shade/traffic/vegetation proxies + no-map verdicts) | `layers_group18resta/b/c` + `layers_genv` + `dims_group18*` (#113, #122–#124, #172, #173, #197) |
| 19 Inspection (134) | 134 | — | 134: forensic facts needing presence/meters | `layers_group19a–19d` + `dims_group19a–19d` (#208–#211) |
| 20 Subjective (38) | 38 | — | 38: buyer-profile inputs, never area scores | `layers_group20a/b` + `dims_group20a/b` (#212, #213) |
| **Total** | **500** | **98** | **402** | batch files per-group above |

## 4. P4 buyer params (parameters4.md P4-001–P4-062) — scorer dims, honest shapes

The 62 buyer-question params (`parameters4.md`) are scorer dims, not
§3 map layers, and duplicate no §3 layer: each is owned by exactly one verdict note
(shipped map-proxy exceptions include P4-029 `blockwalk` + P4-035 `darkness`, #480 — OSM
mapped proxies, honestly labelled)
(`docs/p4_*.md`, 84 notes — several params draw on multiple sources)
with a pinned hermetic scorer module
(`services/scoring/dims_p4_*.py`, 84 modules, doc↔module 1:1;
11 more `docs/overturn_*.md` + `dims_overturn_*.py` hunts re-tested
§3-style NULLs against live feeds — see `docs/nomap.md` §5 for the
full per-source index). Honest shapes, all
`(origin, pois) -> (score | None, Estonian reason)`, NULL-safe:

- **Exact joins** (never gradients, never interpolation): area-table
  joins (Stat PX-Web asula/linnaosa/KOV; REL2021 asula fallback —
  the 1 km grid bulk is a dated negative, so grid joins stay NULL),
  per-parcel joins (kataster/KKIS/TPR/parking-zone; Maa-amet WFS
  classes; EELIS/KAUR zones gated by distance, the LABEL scores),
  per-record joins (EHR/EIS per `ehr_code`, KÜ docs per `ku_code`,
  AT/taiteur per joined entity rows only, PPA linnaosa tertiles off
  the open CSVs).
- **Capped proxies** (`hinnang`, never measured): OSM tag-density
  proxies (12, capped), Ookla tile download (cap 85, SCORES),
  sensor.community density (cap 80, SCORES), Kaitsevägi
  membership/calendar gates, P4-051 arrears flag, dated-notice
  calendar dims (flat 45/50 while in effect), own-store computed legs
  (P4-001/022/028/046).
- **Documented NULLs** (49 notes fully, 6 more partially): gated
  (OpenCellID key, VIIRS login, RIK paid extracts, EHR/EIS anonymous
  bulk), human-pages-only (budgets, audits, timetables, tariffs
  without per-address feeds), or no honest signal (bank surveys,
  insurer zones, ringkond-grain turnout). Every NULL reason carries
  `EI OLE` + the buyer-side check; `EI OLE` never appears in a proxy
  reason (pinned by tests, e.g. `dims_p4_osm`, `dims_p4_senscom`).

Overturn flips that graduated NULL→join dims (Maa-amet parcels,
MARU per-KOV choropleths, EHR per-code, AT probate, flood zone
membership) stay scorer-side — no raster follows (OTA PR #131
precedent).

## 5. P4-slice overlays on /layers (Group A layer issues, #479+)

POSITIVE-verdict P4 slices with point data gain a thin overlay on
`/layers` — sensor points + the scorer's honest kernel, no parameters3
id, no raster master (the points-splat kernel IS the field):

| Overlay | Slice | Points | Kernel | Files |
|---|---|---|---|---|
| `senscom` (P4-031, #484) | sensor.community DIY-air density | Tallinn extract (`sensor-community-tallinn.json`, cached, never live) | hard ≤500 m witness bands 60/70/80 (== scorer) | `lib/layers_p4_senscom.ts` + `lib/server/senscom.ts` |
| `ookla_fixed` + `ookla_mobile` (P4-009, #489) | Ookla quarterly tile download (2026-Q1 re-verified live: HEADs 200 + bounded Tallinn range-reads, 971 fixed / 555 mobile qualifying tiles) | Tallinn extract (`ookla-tallinn-2026Q1.json`, cached, never live) | nearest qualifying tile (≥5 tests) ≤1 km → bands 35/55/75/capped-85 (== scorer) | `lib/layers_p4_ookla.ts` + `lib/server/ookla.ts` |
| `accblack` (P4-012, #490, reopen #522) | Transpordiamet casualty-accident blackspots, measured slice | monthly `lo_2011_2026.csv` (12342189 B, pulled 2026-09-16) projected with the ported L-EST97 transform (~1 m): **8197 Tallinn points** in the snapshot sidecar (`accblack/accblack-points.json`); 1 mislabeled out-of-window row excluded, 92 coordless rows NULL (all counted) | 300 m avoid window (== scorer `BLACKSPOT_WINDOW_M`) | `lib/layers_accblack.ts` + `scripts/build/batch_accblack.py` |
| `asumedia` (own snapshots, #495) | Per-asum asking medians from the own 17-adapter store | **dated negative, empty on purpose**: 2026-09-14 tally — 30 fixture records, 0 with an `asum` key, 0/84 asums at MIN_N=5 (no asum column, no vendored polygons); thin asums stay NULL, no bands calibrated | inert cover σ 0.5 (never evaluated; unknown everywhere until the reopen lands real per-asum N) | `lib/layers_asumedia.ts` + `services/scoring/dims_p4_own_asum.py` |

| `eeliskaitse` (P4-015, #488) | EELIS kaitsealad (building-restriction drag) | polygons only (`eelis/eelis-areas.json`, kind `kaitse`) | none — zone-membership choropleth (inside vs teadmata) | `lib/layers_eelis.ts` + `scripts/build/batch_eelis_poly.py` |
| `eelisniit` (P4-024, #488) | EELIS niidud (coarse tick-habitat proxy) | polygons only (same sidecar, kind `niit`) | none — zone-membership choropleth (inside vs teadmata) | same as above |
| `eelisraie` (P4-030, #488) | EELIS kaadamisalad (coarse change flag) | polygons only (same sidecar, kind `raie`) | none — zone-membership choropleth (inside vs teadmata) | same as above |
| `paaste` (P4-012, #493) | Päästeamet komando coverage (dated-negative feed → honest-empty) | NO point feed (kontaktipuu addresses w/o coords, 2026-09-13; zero fallback points, never invented) | hard ≤5 km flat-60 cover (== scorer station leg; dormant: all-NaN) | `lib/layers_paaste.ts` |
| `sport_hall` + `sport_field` + `sport_pool` (P4-048, #607) | Spordiregister venues + Terviseamet ujulad (family-buyer slices) | yearly bulks (spordiehitised.json 4157 rows + ujulad.xml 226 rows, pulled 2026-09-16): **1110 Harjumaa points** in the snapshot sidecar (`sport/sport-points.json`: hall 335 / field 630 / pool 145); 239 unsliced + 118 outside-county + 7 coordless dropped, all counted | nearest sliced venue ≤500 m → 80, ≤1 km → 65, ≤2 km → 50 (== scorer PROX_BANDS) | `lib/layers_p4_sport.ts` + `scripts/build/batch_sport.py` |
| `ehis_school` + `ehis_kindergarten` + `ehis_hobby` (P4-011, #608) | EHIS school buildings (register cousin of OSM schools) | quarterly bulks (hooned 2180 rows + oppeasutused 5689 rows, pulled 2026-09-16): **618 Harjumaa points** in the snapshot sidecar (`ehis/ehis-points.json`: school 239 / kindergarten 369 / hobby 10); 1179 other-county + 355 closed/unsliced + 28 coordless dropped, all counted | nearest sliced building ≤500 m → 80, ≤1 km → 65, ≤2 km → 50 (== scorer PROX_BANDS, dbands kernel reused) | `lib/layers_p4_ehis.ts` + `scripts/build/batch_ehis.py` |
| `medre_gp` + `medre_clinic` (P4-011 GP half, #609) | TEHIK medre GP lists + providers (Step-1 honest-empty — no ADS join owned) | DAILY bulks (nimistud 782 rows + companies 1571 rows, pulled 2026-09-16): register tallies only (378 Harju kohad, 537 Üldarstiabi kohad), linkage_rate 0, **0 points** in the snapshot sidecar (`medre/medre-points.json`); EI OLE legend, no-data render | dormant dbands kernel, same band table as scorer (all-NaN until Step 2) | `lib/layers_p4_medre.ts` + `scripts/build/batch_medre.py` |
| `ohuseire` (P4-031, #610) | Keskkonnaagentuur official air stations (thin as-is, 3 stations) | keyless PostgREST air slice (90 rows, pulled 2026-09-16): **3 Tallinn stations** in the snapshot sidecar (`ohuseire/ohuseire-points.json`: Rahu / Liivalaia / Õismäe); 39 skipped + 48 coordless, all counted | flat district band: station within 2 km → 60 (scorer 2+ → 70 lives scorer-side) | `lib/layers_p4_ohuseire.ts` + `scripts/build/batch_ohuseire.py` |
| `kliima_frost` + `kliima_wet` (P4 station legs, #611) | Keskkonnaagentuur climate normals 1991-2020 (3 Harjumaa station cells, CC BY 4.0) | ANNUAL PostgREST pulls (f_kliima_paev DTAN + f_kliima_kuu DPREC, pulled 2026-09-16): frost Harku 128.6 (55) / Pakri 106.5 (70) / Kuusiku 146.5 (40); wet Harku 699.9 (70) / Kuusiku 730.1 (40) / Pakri NULL (22/30 complete years); committed `KLIIMA_CELLS` in `lib/layers_kliima.ts` | nearest ranked cell ≤70 km takes its rank band (== scorer `_rank_dim`; qbands kernel reused, no smoothing — midpoints take nearest, Pakri wet renders unknown) | `lib/layers_kliima.ts` + `scripts/build/batch_kliima.py` |
| `poi_library` + `poi_post` + `poi_pharmacy` (P4 long-tail, #612) | Maa- ja Ruumiamet huvipunktid long-tail (open spatial-data licence, monthly vahekiht) | type-bounded WFS pulls + Harju CQL (pulled 2026-09-16): **847 Harjumaa points** in the snapshot sidecar (`poi/poi-points.json`: library 124 / post 536 incl. 521 pakiautomaat / pharmacy 187); 0 dropped, all counted | nearest sliced POI ≤300 m → 85, ≤600 m → 70, ≤1 km → 55 (== scorer _score_dist, dbands kernel reused) | `lib/layers_p4_poi.ts` + `scripts/build/batch_poi.py` |
| `fixit` (P4 kaebused, #623) | annateada.ee report pins (rolling ~19 d window, no licence page — public by publication) | daily ask POST, Tallinn bbox (pulled 2026-09-17): **300 pins** in the snapshot sidecar (`fixit/fixit-points.json`: 173 Tallinn + 127 neighbours, 120 handled / 180 unhandled, 0 timeless dropped; lat/lon/handled/ts only) | markers ONLY, no field (pins measure reporting, not quality — new `pins` kernel, all-NaN direct); serve-time expiry (ts within 19 d) degrades stale sidecars to honestly-empty | `lib/layers_p4_fixit.ts` + `scripts/build/batch_fixit.py` |
| `seveso` (P4 ohualad, #613) | Päästeamet ohtlike ettevõtete register (CC BY-NC-ND 4.0, weekly CSV — polygons-only, attributed, NO re-interpolated raster: ND forbids derivatives) | weekly danger-CSV pull (pulled 2026-09-16): **235 danger polygons** in the snapshot sidecar (`seveso/seveso-areas.json`: 95 Harju; heat 182 / toxic 40 / overpressure 13; 0 skipped; zone_id/nimi/danger/danger_label/aadress only) | inside-by-type fills (toxic 20 / heat+pressure 35 == scorer DANGER_SCORES, worst wins), outside NULL (never safe — unregistered hazard is not ruled out); missing sidecar renders honestly-empty | `lib/layers_p4_seveso.ts` + `scripts/build/batch_seveso.py` |
| `stateland` (P4 riigimaa, #615) | KATRI + maaoksjon WFS (CC BY 4.0, state adjacency + dated auction flags, polygons-only, attributed) | Harju-window GetFeature (pulled 2026-09-17): **11083 polygons** in the snapshot sidecar (`stateland/stateland-areas.json`: 11068 state parcels + 15 active auctions, 0 skipped, ~10 MB; zone_id/nimi/cls + tunnus/valitseja or deadline/purpose/url) | inside state 60 / auction warning-flag 40 (== scorer legs, capped hinnang), forest leg unobserved in harvest (scorer-side); outside NULL (never state-free); expired auctions never flag; missing sidecar renders honestly-empty | `lib/layers_p4_stateland.ts` + `scripts/build/batch_stateland.py` |
| `quarry` (P4 maavara, #614) | Maa-amet maardlad WFS (CC BY 4.0, active permits + exploration watch, polygons-only, attributed) | Harjumaa L-EST97 window GetFeature (pulled 2026-09-17): **182 polygons** in the snapshot sidecar (`quarry/quarry-areas.json`: 154 live-permit extraction + 28 exploration; 14 expired-permit rows refused, 0 skipped; zone_id/nimi/cls/loa/loa_lopp/operaator only) | inside active 25 / exploration watch-flag 55 (== scorer legs, worst wins), near-band ≤2 km → 45 scorer-side only (no buffered fills); outside NULL (never quarry-free); missing sidecar renders honestly-empty | `lib/layers_p4_quarry.ts` + `scripts/build/batch_quarry.py` |
| `maaparandus` (P4 kuivendus, #616) | Kliimaministeeriumi maaparanduse GIS WFS (CC BY 4.0, network/invalid/outflow, polygons-only, attributed) | Harju-window GetFeature (pulled 2026-09-17): **4296 shapes** in the snapshot sidecar (`maaparandus/maaparandus-areas.json`: 1916 network + 785 invalid polygons + 1595 outflow centerlines, 0 skipped, ~8 MB; zone_id/nimi/cls/ms_kood/ms_url only) | inside network 55 (condition unproven — MSR check) / invalid 40 / outflow-near ≤100 m → 45 scorer-side only (no buffered fills); outside NULL (never dry); duty refused; missing sidecar renders honestly-empty | `lib/layers_p4_maaparandus.ts` + `scripts/build/batch_maaparandus.py` |
| `soil` (P4 muld, #617) | Maa-amet mullastiku kaart WFS `SO_pinnas:SO.SoilBody` (CC BY 4.0, memoir seletuskiri §V + lisa 3, polygons-only, attributed) | VIEWPORT proxy, no sidecar (full Harjumaa harvest ~600 MB / 86474 polygons unshippable): grid-snapped annual disk cache, >5000-contour views refused with zoom-in note; urban-centroid + veeala + undecoded contours dropped and counted (Saku probe: family decode verified live) | inside-by-family fills (saviliiv 85 … turvas 25 == scorer SOIL_BANDS, rähkne folds to paepealne 50), outside NULL (never good ground — unmapped is not good); urban/water/undecoded EI MAALI; missing cache pulls once politely | `lib/layers_p4_soil.ts` + `lib/server/soil.ts` (no batch script — viewport WFS) |
| `etak` (P4 ETAK, #618) | Maa-ameti ETAK WFS (CC BY 4.0, maakate/hüdro wetland+water+yard, relief gated OUT — licence unstated, polygons-only, attributed) | NO sidecar by decision (52k Harjumaa polygons, ~114 MB raw — uncommittable): viewport WFS proxy `/api/layers/etak/areas?bbox=…` (grid-snapped 0.05° annual disk cache under `<snapshot>/etak`, polite lon-lat GetFeature per theme, cap 5000/viewport; verified 2026-09-16: e_306 8824 / e_202 15474 / e_203 1332 / e_302 26024; zone_id/theme/cls/score/label/name/vintage only; ETAK wins over OSM on conflict) | inside wetland 25/35/30 (raba/madalsoo wettest, soovik mid) / water 30 (type carried, edge unmoved) / yard 45/70/60 (era/tootmis impervious, haljas green, == scorer legs, map paints classes never numbers); outside NULL (never dry land); relief never queried; over-wide views + outages render honestly-empty with a note | `lib/layers_p4_etak.ts` + `lib/server/etak.ts` (no batch script — soil precedent, proxy-only) |
| `relief` (P4 reljeef, #619) | Maa-ameti DTM WCS `dtm-10` (CC BY 4.0, 10 m EH2000, taste-only, attributed) | ONE harvest GetCoverage (2026-09-17): **1000x570 tint grid** in the snapshot sidecar (`relief/relief-tint.json`: 570k/570k valid, 0–112 m p50 20 m, ~1.5 MB; klint 41–45 / Nõmme 27–52 / Pirita 0–6 — toon ERISTAB; sea cells read 0.0, tint as lowland, never watermasked) | taste-only hypsometric tint (moss→sand→tan→pale rock, NOT green/red — never a score); NO scorer legs (tint first, capped taste legs second); missing sidecar renders honestly-empty | `lib/layers_p4_relief.ts` + `scripts/build/batch_relief.py` |
| `canopy` (P4 võra, #620) | Maa- ja Ruumiamet CHM WMS `CHM2022_suvi` (CC BY 4.0, 2022 summer flight, taste-only, attributed) | ONE harvest GetMap (2026-09-17): **1000x570 class grid** in the snapshot sidecar (`canopy/canopy-tint.json`: 243477/570k canopy cells, 10-20 m dominant 47 %, >30 m 4 cells, unmatched 0, ~0.8 MB; EPSG:3301 render reverse-sampled to lon/lat by exact forward LCC, true L-EST97 #648) | taste-only class tint (publisher greens + amber/red, <1 m transparent = missing, never short canopy — never a score); NO scorer legs (tint first, capped taste legs second); missing sidecar renders honestly-empty | `lib/layers_p4_canopy.ts` + `scripts/build/batch_canopy.py` |
| `buildings` (P4 hooned, #621) | Maa- ja Ruumiamet 3D hoonete LoD1 CityGML (CC BY 4.0, 2025 ALS, taste-only, attributed) | Polite county harvest (2026-09-17, 16 Harju zips, no 429): **1000x570 class grid** in the snapshot sidecar (`buildings/buildings-tint.json`: 198 541 buildings, 100 % measuredHeight, 6-12 m dominant; 33k/570k cells, ~0.8 MB; roof-plane rings only, even-odd courtyards, centroid splat, max-wins; window wider than relief/canopy by design — contains Loksa) | taste-only height tint (stone→indigo OUR bins, NOT green/red — never a score; LoD1 flat roofs overstate parapet shade, capped hinnang); NO scorer legs (tint first, capped taste legs second); missing sidecar renders honestly-empty | `lib/layers_p4_buildings.ts` + `scripts/build/batch_buildings.py` |
| `density` (P4 asustus, #622) | Maa- ja Ruumiamet INSPIRE PD 1x1 km WFS (CC0, Statistikaamet, taste-only, attributed) | ONE Harju GetFeature (2026-09-17, no 429): **8210 squares** in the snapshot sidecar (`density/density-areas.json`, ~1.7 MB; 2024 vintage definitive — maintained series, NOT the census-2021 bulk; 0 dropped; bands 5166/1136/1397/378/96/37; class 0 = empty OR masked <4) | taste-only exact-square fills (bone→plum OUR bins, NOT green/red — never a score; squares painted EXACTLY, never interpolated; outside NULL, never rural); NO scorer legs (fills first, capped taste legs second; masked-zero scores None); missing sidecar renders honestly-empty | `lib/layers_p4_density.ts` + `scripts/build/batch_density.py` |

Overlay layers carry `paramIds: []` + `paramLabel` (e.g. `P4-031`):
parameters3 p31 is Structural integrity (inspection no-map) and must
never gain a map by accident. §3 counts are untouched by overlays
(still 98 map-layer params / 402 no-map + scorer dim after p47
graduated in #492 — overlays visualize P4 slices, not parameters3
params).

Polygon overlays (`eeliskaitse`/`eelisniit`/`eelisraie`, #488) paint
EELIS zone fills with no score field at all (zero points, null
raster — `fallbackPoints: []`, the points route answers
honestly-empty): outside every polygon stays NULL (teadmata, never
clear), the scorer's per-parcel join (`dims_p4_eelis.py`) is untouched,
and the flood table + emitter register stay out (flood owned by #487,
emitters are a point register with no honest polygon — see
`docs/p4_eelis.md`).

