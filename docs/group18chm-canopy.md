# G18 CHM canopy-height upgrade verdict (issue #546)

Closes #546 — measured tree/shade legs from the Maa-amet CHM model.

Code: `services/scoring/dims_group18chm.py` (3 upgrade dims);
tests: `services/scoring/tests/test_dims_group18chm.py` (hermetic,
fixture artefacts, no network).

## 1. Polite probe (2026-09-16, UA `home-finder-idea-probe/1.0`)

Single GetCapabilities pull (no GetMap sample — capabilities alone
answer the acceptance questions; the bbox sample belongs to the bulk
job, not to a second probe):

| Check | Result |
|---|---|
| URL | `https://teenus.maaamet.ee/ows/wms-chm?service=WMS&request=GetCapabilities` |
| Result | **OPEN.** HTTP 200, 46 107 B, ~0.17 s. No 429, no key. |
| Service title | `Maa- ja Ruumiamet Taimkatte kõrgusmudel (Canopy Height Model) - CHM` |
| Vintage layers | **25**: `CHM2008-11`, `CHM2012_kevad/suvi`, `CHM2013_kevad/suvi`, `CHM2014`, `CHM2015_kevad/suvi`, `CHM2017`, `CHM2017_suvi`, `CHM2018–2024 kevad/suvi` each, + aggregate `CHM`. 2016 absent (stated gap, matches catalogue). Newest: **CHM2024_suvi**. |
| CRS | EPSG:3301 (all layers). Bbox `minx 6.3e+06 … maxy 830000` = all-Estonia wall-to-wall. |
| Formats | image/png + image/jpeg via GetMap. |
| Licence | CC BY 4.0 (catalogue claim; attribution in LAYER_META + reasons). |

Tallinn coverage: wall-to-wall bbox includes Tallinn incl. urban parks
and private gardens (4 m raster since 2017 — gardens resolve; pre-2017
10 m does not — vintage note in every reason). Resolution/vintage for a
Harjumaa window and the GetMap class-value sample are deferred to the
annual bulk job (one probe budget spent; no hammering per AGENTS.md).

## 2. Cap/band re-derivation table (old proxy → new measured)

| Leg | Old proxy (dims_group18veg) | New measured (this module) | Evidence |
|---|---|---|---|
| p65 fall zone | flat 25 m cap, count bands at 200 m | radius = measured h, **cap 40 m**; bands on CHM class breaks 1/4/10/20/30 m | CHM classes 1–4/4–10/10–20/20–30/>30 m, 0.5 m steps, max assumed 50 m (issue body). 40 m = >30 m class + margin; taller cells hit the floor (15). |
| p395 leaf burden | deciduous count ≤150 m, worst at ≥6 | measured h ≤100 m + deciduous proxy; worst at >20 m decid | Height replaces count (one 25 m decid crown out-sheds six saplings). Unknown leaf → 55, never worst (height ≠ species). |
| p479 shade/moss | geometry cross-check bands from 20 m | measured h ≤25 m; <4 m → 85, >30 m → 20 | 4 m = CHM resolution floor (sub-cell shrubs are noise); 30 m = top class edge. |

Where CHM contradicts OSM geometry, CHM wins; reasons carry the
vintage + "mõõdetud" marker so the reviewer sees which leg won.

## 3. Pre/post discrimination (fixture window, clearly labelled synthetic)

`histogram()` + `test_upgrade_discriminates_on_fixture_window`: 12-lot
window, edges [4, 10, 20, 30] — old flat-25 m proxy bins all 12 into one
bin `[0,0,0,12,0]`; measured metres spread `[2,3,4,2,1]` across five
bins and four score bands. Synthetic illustration only — the real
Tallinn-window histogram runs in the bulk job once it owns the WMS
harvest (helper + edges ship here so the job reuses them).

## 4. Judgment calls for the reviewer

1. Nodata windows score the honest fallback (fall 80 "katet pole",
   leaf 90, shade 85) — absence of CHM cover is thin mapping, never
   "no trees" (p52 floor precedent).
2. Unknown vintages score but say "tundmatu vintage" — years never mix
   silently (annual TTL).
3. No WEIGHTS/livability/layers edits (joint-rebalance precedent).

## 5. DoD evidence

```text
python3 -m pytest services/scoring/tests/test_dims_group18chm.py -q
# → 12 passed (observed 2026-09-16, worktree 546-chm-canopy)
python3 -m pytest services/scoring/tests -q
# → full suite green, no regressions (see PR checks)
```
