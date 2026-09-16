# P4 Seveso hazard-avoidance layer (issue #527)

Closes #527.

## 1. Verdict (2026-09-16): VIABLE — measured zone-membership dim, raster deferred

One polite probe round (UA `home-finder-idea-probe/1.0`, `--max-time 20/30`,
no retries, paced ≥ 3 s), cached to `/tmp/hf-526-529-probe` (one-off PR
record, not committed):

| # | URL | Result |
|---|-----|--------|
| 1 | `https://opendata.smit.ee/gis/ohtlikud_kaitised.csv` (HEAD) | **OPEN.** `HTTP/1.1 200`, `application/octet-stream`, 88 598 B |
| 2 | same (GET) | **238 enterprise rows (98 Harju).** `;`-separated, BOM-free UTF-8. Columns: nimi, kaitise_id, aadress, x/y_tegevuskoht (L-EST97), x/y_ohuallikas (L-EST97), kaitise_ohtlikkus (A 44 / B 37 / C 157), tegevusala, doomino_efekt, mojutatud_ettevotted, ohu_tuup (Soojuskiirgus 180, Mürgised ained 40, Ülerõhk 14), kemikaalid, infovoldik, lon/lat_ohuallikas (WGS84) |
| 3 | `https://opendata.smit.ee/gis/ohtlikud_kaitised_ohualad.csv` (HEAD) | **OPEN.** `HTTP/1.1 200`, 355 065 B |
| 4 | same (GET) | **235 danger-area rows (95 Harju) with WKT POLYGONs (L-EST97) + raadius.** Same ohu_tuup split (heat 182, toxic 40, overpressure 13). raadius range 1–4512 m; medians per type: toxic 342, heat 177.5, overpressure 108 |
| 5 | CRS check (local, no new request) | **Dual-coordinate oracle.** All 238 point rows carry BOTH L-EST97 and WGS84: the ported inverse-LCC transform reproduces the published WGS84 within **6.1 cm worst-case** (238/238 rows). L-EST97 convention: x_* = northing, y_* = easting. Spot sanity: Haabersti LOV (Järveotsa tee 67) projects to (59.4136, 24.6565), Vasalemma (Ranna tee 8) to (59.2435, 24.2900) |

Licence: **CC_BY_NC_ND_4.0** per the national catalogue (stated in the
issue body) — attribute Päästeamet, keep raw snapshots unmodified,
fixtures in-repo are fully synthetic. No 429 encountered at any step.

## 2. What ships

`services/scoring/dims_p4_seveso.py` (new): `fetch_seveso_snapshot()`
(polite, cache-first per file, `SEVESO_CACHE_TTL_S = 7 d` — publisher
updates weekly, default dir `/tmp/hf-seveso-cache`) → `parse_points_csv()`
/ `parse_danger_csv()` (pure: WKT outer rings project to WGS84 once,
holes ignored fail-safe towards over-coverage) → `dim_seveso_zone()`
(inside a polygon scores by danger type: toxic → 20, heat/overpressure
→ 35, combustion-promoting → 50, unmapped label → 30, worst polygon
wins; outside every polygon is NULL, never "safe"; point-buffer
fallback with observed-median radii applies only with zero polygons).
Transport errors raise and never touch the cache; HTTP 429 stops the run.

No raster master in this PR (one probe round, no harvest): the dim is
the honest measured layer half; the raster follow-up is checklist item 1
in §5. No web overlay file — painting 2–3 fixture polygons as a map
would be fake precision.

## 3. Judgment calls for the reviewer

1. New files only (`dims_p4_seveso.py`,
   `tests/test_dims_p4_seveso.py`, `docs/p4_seveso.md`). No shared-file
   edits; no livability/WEIGHTS hook (joint-change rule).
2. Mixed labels (`Mürgised ained, Soojuskiirgus`, observed 4×) score the
   binding (lowest) leg; `combustion → 50` covers catalogue vocabulary
   unobserved on the probe date.
3. Fallback radii are observed ohualad medians per type (350/180/110 m,
   unknown 200 m), rounded up — challenge with a fuller distribution.
4. Test fixtures are fully synthetic; the one geodetic anchor
   (Haabersti lest pair) is labelled as probe evidence and pins axis
   order, not data.
5. NC/ND respected: raw CSVs are never modified/redistributed, only
   parsed in-memory; reasons attribute Päästeamet and point at the
   enterprise infovoldik.

## 4. DoD evidence

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_seveso.py -q
.......................s                                                 [100%]
23 passed, 1 skipped in 0.04s
```

Hermetic: suite makes zero network calls (live pull env-gated behind
`HF_LIVE_SEVESO=1`). Full-suite output pasted in the PR body.

## 5. Reopening checklist

* Raster follow-up: weekly-cron harvest → snapshot dir → walk-graph or
  honestly-labelled Euclidean kernel off the WKT polygons, contract
  check (half/σ), Lasnamäe/Muuga screenshot.
* Archive check: re-probe row counts yearly (register churn); unobserved
  `combustion` value appearing flips no code (already mapped).
* P4-012/P4-015/P4-054 cousins untouched — distinct dim key
  (`seveso_zone`), no double-scoring.

## 6. Graduation: map overlay (issue #613, 2026-09-17)

Closes #613. One layer (`seveso`, `paramLabel P4-ohuala`,
`paramIds []` — parameters4 namespace): the register's danger polygons
as a danger-class choropleth (toxic red / heat orange / overpressure
light-orange / combustion brown / unknown slate), outside every polygon
NULL (never safe).

* Polygon sidecar: `scripts/build/batch_seveso.py --danger
  <cached ohtlikud_kaitised_ohualad.csv> --snap <snap>` →
  `<snap>/seveso/seveso-areas.json` (zone_id/nimi/danger/danger_label/
  aadress + GeoJSON [lon, lat] outer rings + prefilter box). Offline,
  stdlib-only; rows unmodified apart from the mechanical L-EST97→WGS84
  projection (same ~1 m port as the scorer, copied per per-issue
  convention); attribution rides the build stats + every reason string.
  Rebuild on the cached 2026-09-16 pull: **235 zones, 0 skipped, 95
  Harju** (heat 182 / toxic 40 / overpressure 13 — byte parity with the
  §1 probe).
* No raster master by licence decision (`SEVESO_NO_RASTER`,
  `SEVESO_NO_METRO`): CC BY-NC-ND forbids derivatives — the points
  endpoint answers honestly-empty, windows serve county.
* Wiring: `SEVESO-HOOK (#613)` blocks in layers.ts (import/union/DECAY/
  LAYERS/TAGS/bonusSpecFor), overlays.ts (marker `#3b0764` + legend),
  outlines.ts (`applySevesoPolygons` match-expression fills + slot),
  server/snapshot.ts (`loadSevesoAreas` + raster/metro absent names),
  route.ts (honestly-empty points branch), new
  `/api/layers/seveso/areas`, page.tsx (fetch/paint/status `Päästeameti
  Seveso ohualad · N polügooni (väljaspool = teadmata, mitte ohutu)`),
  ValueHeatMap (`sevesoAreas` prop). Registry now 124 layers.
* Scorer parity: `SEVESO_DANGER_SCORE` mirrors `DANGER_SCORES`
  (toxic 20 / heat+pressure 35 / combustion 50 / unknown 30); the map
  paints class fills, never numbers.

DoD evidence: `vitest` (new `layers_p4_seveso.test.ts` + painter tests
in `outlines.test.ts` + `test_batch_seveso.py`), full suites green,
typecheck clean — pasted in the PR. Screenshot: `/layers?layer=seveso`
Muuga/Väo fills.
