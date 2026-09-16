# P4 maavara-extract note — active extraction + exploration proximity (#545)

> Shipped layer for issue #545. Checked 2026-09-16. Scorers live in
> `services/scoring/dims_p4_maavara_extract.py`, pinned by
> `services/scoring/tests/test_dims_p4_maavara_extract.py`.

## Verdict

**OPEN (CC BY 4.0) — both dims score from joined polygons.** The
Maa-amet `maardlad` WFS carries permit-grade extraction + exploration
types with the status/expiry attributes the join needs, proven on live
bytes + one live sample row. Attribution Maa- ja Ruumiamet CC BY 4.0.

## Same-or-different vs the subsurface-joined layers: DIFFERENT

| | `dims_p4_maa_subsurface` (#248/#332) | THIS module (#545) |
|---|---|---|
| Service | Keskkonnaagentuur WFS (`gsavalik.envir.ee/geoserver/wfs`) | Maa-amet MapServer WFS (`teenus.maaamet.ee/ows/maardlad`) |
| Types | `maavarad_gbmv_levialad` / `leiukohad` / `perspektiivalad` | `maeeraldis_aktiivne` / `maeeraldis_taotletav` (+ `_tm_` peat variants), `Aktiivne_uuringuala` / `Taotletav_uuringuala` |
| Semantics | mineral distribution / find sites / prospective areas (occurrence mapping) | permitted extraction (permit no/expiry/operator) + licensed exploration (legal acts) |
| Dim | `quarry_buffer` (deposit buffer) | `extraction_proximity` + `exploration_watch` |

Different services, different type names, different legal semantics —
the two legs the subsurface list does NOT name. Not a duplicate.

## Openness evidence (one polite round, 2026-09-16, no scraping, no auth)

5 single GETs total, 2 s pacing, `--max-time 30`, labelled one-off
user-agent `home-finder openness-check (one-off, few pages max, no
scrape)`. Raw bodies: `/tmp/hf-probes/` (one-off PR record, not
committed).

| Check | Observed | Meaning |
|---|---|---|
| `ows/maardlad?…GetCapabilities` → HTTP 200, 97 KB | 70 types: `maeeraldis_aktiivne/taotletav(_tm_)`, `Aktiivne/Taotletav_uuringuala`, per-mineral deposits + `*_levi`/`*_persp`, `maardlapiir`, `varud_*`, `ta_*`; CRS EPSG:3301/4326 | Extraction + exploration families enumerated |
| `…DescribeFeatureType` (both headline types) → HTTP 200, 4.4 KB | extraction: `ME_ID/KOOD/NIMETUS/LOA_NUMBER/LOA_ALGUS/LOA_LOPP/KAEVANDAJA/PINDALA/ERALD_VARU/STAATUS/ME_OLEK/MAAVARA`; exploration: `U_ALA_ID/NIMI/MAARDLA/MAAVARAD/LOA_NR/LOA_ALGUS/LOA_LOPP/U_ALA_OLEK/STAATUS` | Status + permit-expiry attributes proven at schema level |
| `…GetFeature maxfeatures=1` (GML — MapServer has no JSON) → HTTP 200 | `Koguva dolokivikarjäär`, ME_OLEK `aktiivne`, STAATUS `K`, LOA `L.MK/327053`, LOA_LOPP `20401216`, KAEVANDAJA `Muhu Vallavalitsus` | Active-permit join proven on live bytes |
| Harjumaa-window hits (L-EST97 bbox, counts only) | `maeeraldis_aktiivne` 198, `Aktiivne_uuringuala` 31, `maeeraldis_taotletav` 78 | Live discrimination in the buyer area |
| CRS caveat | sample vertices are L-EST97 metres DESPITE `srsname=EPSG:4326` | projection L-EST97 → WGS84 is an explicit upstream step |

## Honest shapes (polygons only, never gradients)

| Leg | Dim key | Bands | Outside → |
|---|---|---|---|
| Active extraction | `extraction_proximity` | inside active permit → 25; ≤ 2 km coarse vertex band (jäme) → 45 | NULL (never "no quarry") |
| Exploration | `exploration_watch` | inside live area → dated flag 55 (exploration ≠ permit, never a quarry penalty) | NULL |

Active = `ME_OLEK == "aktiivne"` + permit not expired (`LOA_LOPP`
YYYYMMDD); unknown/expired never scores as a quarry. `taotletav`
(applied-for) extraction is exploration-grade watch, never active.
No blast timetables (buyer check), no reserve economics.

## Judgment calls (for the reviewer)

1. Near-band reuses the subsurface coarse convention (vertex-haversine
   can only under-flag, labelled `jäme`).
2. Single-letter STAATUS values beyond the live sample (`K`) are not
   trusted alone — activity requires `ME_OLEK == "aktiivne"`.
3. Exploration inactive-marker list is provisional (schema + one sample
   pulled); unknown olek keeps the WEAK flag only, stated in code.
4. No shared-file edits: 3 new files only. Subsurface files untouched.

## Reopening checklist

1. Confirm the wider STAATUS/`U_ALA_OLEK` codelists against cached rows.
2. L-EST97 → WGS84 projection on the first full pull (GDAL/Maa-amet
   converter); fixtures already carry WGS84.
3. P4-054 truck leg (`dims_p4_trans`) stays the traffic cousin.

## Graduation: map overlay (issue #614, 2026-09-17)

Closes #614. One layer (`quarry`, `paramLabel P4-maavara`,
`paramIds []` — parameters4 namespace): active extraction permits
(avoidance red) + exploration watch areas (caution yellow, dated
permit carried) as a class choropleth; outside every polygon NULL
(never quarry-free). The <= 2 km near-band (45) is scorer-side only —
no buffered fills (fake precision refused), the legend says so.

* Harvest (polite one-off, 2026-09-17, UA `home-finder-research/0.1`,
  paced ≥ 3 s, `--max-time` 30/60, no 429): WFS 1.0.0 GetFeature
  `ms:maeeraldis_aktiivne` (467 KB, **168 features**, all
  `ME_OLEK=aktiivne`) + `ms:Aktiivne_uuringuala` (67 KB, **28
  features**, all `U_ALA_OLEK=aktiivne`) in the Harjumaa L-EST97 window
  (easting 370000–600000, northing 6540000–6610000 — frame anchored on
  the Seveso probe's 98 Harju enterprise coordinates). Raw GML kept at
  `/tmp/hf-614-cache` (PR record, not committed); MapServer ignores
  `resultType=hits` (returns an empty collection — full pull instead).
* Polygon sidecar: `scripts/build/batch_quarry.py --extract
  <cached GML> --explore <cached GML> --snap <snap>` →
  `<snap>/quarry/quarry-areas.json` (zone_id/nimi/cls/loa/loa_lopp/
  operaator + GeoJSON [lon, lat] outer rings + prefilter box).
  Offline, stdlib-only; only live permits join (parseable-future
  `LOA_LOPP` — **14 expired-permit rows refused**, all with past dates,
  e.g. Rabivere 20250703, Tondi-Väo III 20250105); `taotletav`
  refused (application ≠ permit). Rebuild: **182 zones, 0 skipped**
  (154 active + 28 exploration). Window spillover kept honestly:
  3 Hiiumaa quarries + 2 regional exploration areas at true location
  (off-frame in Tallinn view, never clipped — clipping would fake
  absence).
* No raster master by decision (`QUARRY_NO_RASTER`,
  `QUARRY_NO_METRO`): polygons ARE the field — the points endpoint
  answers honestly-empty, windows serve county.
* Wiring: `QUARRY-HOOK (#614)` blocks in layers.ts (import/union/DECAY/
  LAYERS/TAGS/bonusSpecFor/fetchWindow skip), overlays.ts (marker
  `#431407` + legend), outlines.ts (`applyQuarryPolygons`
  match-expression fills + slot), server/snapshot.ts
  (`loadQuarryAreas` + raster/metro absent names), route.ts
  (honestly-empty points branch), new `/api/layers/quarry/areas`,
  page.tsx (fetch/paint/status `Maa-ameti karjäärid ja uuringualad · N
  polügooni (väljaspool = teadmata, mitte kaevandusvaba)`),
  ValueHeatMap (`quarryAreas` prop). Registry now 124 layers.
* Scorer parity: `QUARRY_CLASS_SCORE` mirrors the scorer legs (active
  inside 25 / exploration watch-flag 55); the map paints class fills,
  never numbers.

DoD evidence: `vitest` (new `layers_p4_quarry.test.ts` + painter tests
in `outlines.test.ts` + `test_batch_quarry.py`), full suites green,
typecheck clean — pasted in the PR. Screenshot: `/layers?layer=quarry`
Männiku/Väo fills.
