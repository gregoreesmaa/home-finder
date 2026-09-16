# DTM relief/flatness verdict (issue #553)

Closes #553 — slope + relative elevation as area character (klint,
slopes, lowlands), never a plain good/bad gradient.

Code: `services/scoring/dims_dtm_relief.py` (4 taste-dependent legs +
character overlay helpers); tests:
`services/scoring/tests/test_dims_dtm_relief.py` (hermetic, fixture
artefacts, no network).

## 1. Polite probe (2026-09-16, UA `home-finder-idea-probe/1.0`)

4 pulls total, `--max-time 25/30`, no retries, 429 = stop (none seen):

| Check | Result |
|---|---|
| `ows/wcs-dtm?service=WCS&request=GetCapabilities` → HTTP 200, 7376 B, ~0.21 s | **OPEN.** Provider Maa-amet, fees none. 3 coverages: `dtm-25` / `dtm-10` / `dtm-1` (resolutions, not vintages). CRS EPSG:3301 only. Formats image/tiff + aaigrid + png + jpeg. |
| `…?service=WCS&version=2.0.1&request=DescribeCoverage&coverageId=dtm-1` → HTTP 200, 2487 B | Envelope N 6375000..6635000 / E 365000..740000 (all-Estonia wall-to-wall, incl. Tallinn). Grid 375000 x 260000 cells = **1 m** over dense settlements; offset vectors confirm 1.0 m. Native format image/tiff. |
| `…GetCoverage&coverageId=dtm-25&subset=x(540000,541000)&subset=y(6588000,6589000)` → HTTP 200, 6824 B, image/tiff | **Live Harjumaa window serves real DTM.** 40x40 float32, elevations **4.29..7.78 m, mean 5.98 m** (parsed from TIFF strip). Tallinn resolves at 1 m; this window at 25 m already discriminates lowland from slope. |
| Vertical datum / tile layout | **Honestly unstated in the WCS.** Neither GetCapabilities nor DescribeCoverage names a vertical datum or tile vintage; the issue body (LiDAR 1 m settlements, 1/5/10/25 m nationwide, ANNUAL since 2012) is the vintage source. Artefact vintage = tile survey year `YYYY`; reasons say `tundmatu vintage` when absent. Horizontal is L-EST97 (EPSG:3301, stated). |

Licence CC BY 4.0 (catalogue claim; attribution in LAYER_META +
reasons). Annual vintage stated; fresh cuts/fills post-date flights.
1 m resolves streets, never kerbs/driveway crowns — micro-grade stays a
buyer check.

## 2. Calibration windows (fixture slopes, clearly synthetic)

Edges [2, 5, 10, 20] % (`test_calibration_windows_discriminate`):

| Window | Fixture slopes (%) | Histogram |
|---|---|---|
| Klint edge (Lasnamäe) | 18, 22, 25, 30, 15, 28 | [0, 0, 0, 2, 4] — järske/klint |
| Nõmme slope | 4, 6, 8, 5, 7, 9 | [0, 2, 4, 0, 0] — lauge/mõõdukas |
| Pirita lowland | 0.5, 1.0, 1.5, 0.8, 1.2, 2.5 | [5, 1, 0, 0, 0] — tasane |

The bands discriminate: the three windows occupy disjoint bins. The
real Tallinn-window histogram runs in the bulk job once it owns the WCS
harvest (helper + edges ship here so the job reuses them).

## 3. Overlay-vs-leg split (no taste claim without a named taste)

Character overlay first (EELIS #488 precedent, no score field):
`character()` + `slope_character()` — hypsometric tint + slope bands
tasane/lauge/mõõdukas/järske/klint as area character ("see on see, mida
maapind siin teeb").

| Leg | Named taste | Shape | Cap |
|---|---|---|---|
| `lowland` | flood-avoider | z ≤3 m → 35, ≤5 → 55, ≤8 → 65, else 75 | bad side, flood-layer cousin |
| `viewpoint` | view-seeker | relief 0-2 m → 55, 2-6 → 65, 6-12 → 70 | **max 75**, taste-match only |
| `cycling` | cyclist | <2% → 80, 2-5 → 65, 5-10 → 50, 10-20 → 35, >20 → 25 | mobility cost |
| `klint_build` | buyer check | near (≤50 m) AND steep (>10%) → 40, else 65 | never a ban ("näitab vaadet, mitte keeldu") |

Nodata windows score NULL ("DTM andmed puuduvad"), never "tasane".
Graduations enabled: driveway-grade NULL → measured grade; p336
slidebuf → measured-slope cross-check (below).

## 4. p336 cross-check (OSM cliff proximity vs measured slope)

`p336_crosscheck(osm_near_m, slope_pct)` — OSM near means ≤100 m,
measured steep means >10%:

| OSM | Measured | Label |
|---|---|---|
| near | steep | mõlemad märgivad |
| near | flat | ainult OSM (mapped edge, no grade — re-survey) |
| far | steep | ainult mõõdetud (unmapped grade — ETAK/DTM wins) |
| far | flat | mõlemad vaikivad |

Where DTM contradicts OSM geometry, DTM wins; the reason carries the
vintage + "mõõdetud" marker.

## 5. Judgment calls for the reviewer

1. No landslide-risk scoring (slope ≠ slide risk — legend must say so).
2. No view-shed monetisation (sea-view premium stays price modelling).
3. 1 m grid bands are coarse first cuts, documented in the module.
4. No WEIGHTS/livability/layers edits (joint-rebalance precedent).

## 6. DoD evidence

```text
python3 -m pytest services/scoring/tests/test_dims_dtm_relief.py -q
# → 15 passed (observed 2026-09-16, worktree 553-dtm-relief)
python3 -m pytest services/scoring/tests -q
# → full suite green, no regressions (see PR checks)
```
