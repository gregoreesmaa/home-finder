# Noise layers #131: vibration (p234) vs low-frequency noise (p408)

Branch `131-noise-vibration-lowspec`. Buyer review asked three things:
(1) are vibration/lowspec duplicates — merge or keep?
(2) wind farms are missing — add them;
(3) what else mapped is missing, and is there an official noise map to
calibrate against? All numbers below are measured 2026-09-12 from the
local snapshot (`~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf`,
osmium 1.19.1) — no network at runtime, no network in tests.

## 1. Merge-or-keep verdict: KEEP both, sharpen the split

Current masters (`vibration-walk-raster.json` vs `lowspec-walk-raster.json`,
3 098 123 county cells @ 75 m):

| metric | value |
|---|---|
| Pearson r, full county | **0.9832** |
| Pearson r, Tallinn window (24.55–24.95, 59.35–59.50) | **0.9836** |
| mean \|diff\| | 3.17 pts |
| cells differing >10 pts | 5.82% (~180k cells) |
| cells differing >20 pts | 0.24% |
| max diff | 96 |
| lowspec-red while vibration-calm (low<50 & vib≥70) | 1 996 cells (0.06%) |

The buyer is right that they look similar (r = 0.983): vibration
sources (rail + heavy roads) are a subset of lowspec sources, so the
maps share every corridor. They still differ systematically, not just
at edges: lowspec's longer half (500 m vs 300 m) shifts the whole
mid-ramp ~10 pts darker (Tallinn-window score-90+ cells: 11 246 vib vs
2 484 low), and probes separate (Viru 49/36, Viimsi 78/68, Lasnamäe
20/13 — vib/low).

Keep rationale: different claimed physics (ground-borne 300 m vs
airborne heavy spectrum 500 m), different param ids feeding different
buyer weights (p234 vs p408, plus sibling p301), and this branch grows
the split by construction — the four new source classes below join
lowspec ONLY, vibration stays rail + heavy roads. Merging would delete
a real gradient distinction to fix a legend problem; the honest fix is
the sharper source split plus the cross-referencing source strings.

## 2. New sources added (lowspec only)

osmium counts are TRUE tagged objects (fileinfo node counts include
member nodes pulled in for way/relation completeness — verified via
OPL/export, see module docstring):

| class | snapshot truth | export file (new, snapshot-only) | reader rule |
|---|---|---|---|
| wind turbines | 53 `generator:source=wind` nodes, 0 ways; 4 `site=wind_farm` relations group the same nodes (Pakri 8, Paldiski 18, Vanaküla 3, Aulepa 16) | `derived-wind.geojson` | points as-is; relations skipped (twins) |
| quarries | 78 `landuse=quarry` areas (74 ways + 4 rels; Väo, Huntaugu, Valkla…) | `derived-quarry.geojson` | MP outer rings; 74 closed twins + 12 member rings out |
| motorsport | 53 `sport=motocross/karting` ways + 3 nodes (Laitse, Vasalemma, Kose-Risti…) | `derived-motorsport.geojson` | 37 area rings + 16 open centrelines + 3 nodes; 36 twins + 12 untagged member dots out |
| shooting ranges | 4 `military=range` polygons (Männiku…) | `derived-range.geojson` | MP outer rings; 4 twins out |

Deliberately excluded (audited, data-backed): `man_made=windmill`
(heritage monuments, e.g. Kotlandi/Sutlepa tuulik); solar/diesel/gas
gensets (silent/intermittent); indoor `sport=shooting` (42n+4w, tags
cannot tell indoor from outdoor); `leisure=shooting_ground`,
`sport=motorsport`, `man_made=mineshaft/adit` (0 mapped); nightlife
(283 pts, owned by nuisance/p162) and heavy highways (3 320 ways,
already in both layers).

Measured hook effect (real builder code + `lowspec_extra_points`,
`/tmp/exp_lowspec_hook.py`, 75 m test windows):

| window | cells changed | mean \|d\| | max d | newly exposed (old≥70 & new<50) |
|---|---|---|---|---|
| Tallinn | 14.33% (9 688) | 3.03 | 86 | 2 044 |
| Pakri/rural | 47.31% (23 945) | 3.32 | 87 | 1 191 |

City probes unchanged (Balti 0, Viru 36, Lasnamäe 13 — roads dominate
correctly); Pakri turbine probe 84 → 13. Calibration unchanged
(half 500 m / sigma 0.5 on the wire); no GENV_CAL drift.

## 3. Official noise maps: documented dead-end (no import)

Researched Transpordiamet / Keskkonnaagentuur END mapping, Tallinn
`mürakaart`, EEA Noise Observation service (2026-09-12, web research —
no runtime calls added to the repo):

* Tallinn strategic noise map exists (2008, 2012, 2022 update by ELLE
  OÜ, `Tallinna linna myrakaart 2022 ELLE 020922.pdf` on tallinn.ee):
  report PDF with Lden/Lnight exposure TABLES, contour figures only —
  no openly licensed bulk vector/raster download found.
* Transpordiamet CNOSSOS-EU maps for major roads/rail: PDFs + action
  plans — no open GIS download found.
* EEA END datahub: exposure statistics per agglomeration, not
  listing-scale rasters; the old download portal is gone (HTTP 410) and
  contours would cover only Tallinn-agglomeration road/rail/airport/
  industry bands — nothing for vibration, wind, quarries, tracks.
* REJECTED explicitly: per-address APIs (breaks hermetic/no-network
  rules), scraping kaart.tallinn.ee or contours out of PDFs (no bulk
  licence, ToS risk), invented service URLs (none cited above beyond
  verified pages).

Conclusion: no official source integrates cleanly today, so no import
is implemented and all layers stay honestly labelled
"proksi (hinnang)". What would unblock: Tallinn/Transpordiamet contour
polygons (Lden/Lnight bands) published under CC-BY on the national
open-data portal — import path = sample band polygons → recalibrate
the road/rail halves (p16/p234/p408 share them); staged as a future
hook, not built here.

## 4. Files changed (this branch only)

* `scripts/build/batch_genv_noise_src.py` (NEW): readers + union +
  HOOK splice for `batch_genv_exposure.py` (that file untouched —
  in-flight in another batch).
* `scripts/build/test_batch_genv_noise_src.py` (NEW): 8 hermetic tests.
* `apps/web/lib/layers_genv.ts`: lowspec source string (honest counts),
  GENV_TAGS lowspec + exclusion comment, builder HOOK note. GENV_CAL
  untouched. `layers.ts`/`snapshot.ts`/`overlays.ts`/`page.tsx` untouched.
* `apps/web/lib/layers_genv.test.ts`: lowspec tag assertions.
* `services/scoring/dims_group09b.py`: 4 new POI kinds (p408-only),
  LOWSPEC_KINDS, Overpass fragment lines, docstring counts.
* `services/scoring/tests/test_dims_group09b.py`: new-kind + mapping +
  fragment tests.
* Snapshot one-time exports (not committed, same pattern as
  `derived-heavyroads.geojson`): `derived-wind/-quarry/-motorsport/
  -range.geojson` in `~/hf-data/2026-09-12/osm/`.

## 5. Test evidence

`python3 -m pytest scripts/ services/scoring/tests -q` from the
worktree root — see PR description for the quoted output (all green:
new module 8/8, group09b extended, genv cal-drift lock intact).
`npx vitest run apps/web/lib/layers_genv.test.ts` green.
