# P4 forest-change verdict: FLIPPED LIVE (issues #548, #624)

Closes #548's gate and #624's bulk job: the distribution bundles its
licence (ETAK-open-data-licence.pdf + Estonian twin, verified in the
2024 zip central directory; English PDF range-fetched, decompresses to
its stated size) — the Land Board open-data licence 01.01.2025,
grant-by-use for ETAK spatial data, catalogue access PUBLIC.
Attribution stamped in every sidecar + source line. Residual gray
(reviewable): the glyph-encoded PDFs defeated verbatim clause
extraction, and the catalogue still shows no licence field — the
verdict cites the bundled file + indexed grant text, and the reviewer
judges.

Code: `services/scoring/dims_p4_forestchange.py` (`LICENCE_OK = True`,
bands live); builder: `scripts/build/batch_forest.py` (SHP vintage →
snapshot `forest/forest-areas.json`); web: `apps/web/lib/layers_p4_forest.ts`
+ `/api/layers/forest/areas` + map fills; tests:
`services/scoring/tests/test_batch_forest.py` (hermetic, synthetic
SHP/DBF bytes) + `apps/web/lib/layers_p4_forest.test.ts`.

## 1. Bulk pull (2026-09-17, UA `home-finder-dev/0.1`, polite single pull)

| Check | Result |
|---|---|
| URL | `https://geoportaal.maaruum.ee/docs/Avaandmed/Metsamuutused_2024.zip` |
| Result | **SERVES.** HTTP/2 200, `content-type: application/zip`, `content-length: 59179549` (~56.4 MB), `last-modified: 16.09.2026`. No 429. |
| Schema/CRS | SHP Polygon (L-EST97 — true Lambert Conformal Conic 2SP per the bundled `.prj`, NOT the legacy TM; see #648) + DBF `Pindala` (area ha) / `Algus` / `Lopp` (first/second survey dates). |
| Counts | **SERVES, INGESTED.** National: kevad 9212 + suvi 989 = 10201 polygons; Harju+2 km keep: kevad 4951 + suvi 337 = **5288 polygons**, 0 dropped. All second_dates 2024-04/05/08 (age ~2.3 y — RECENT bracket, all class 3). |
| Simplify | Douglas-Peucker 5 m in metric 3301 before projection: 2 982 965 → 119 881 verts. |

Rebuild: `python3 scripts/build/batch_forest.py --zip
/tmp/hf-624-cache/metsamuutused-2024.zip --snap ~/hf-data/2026-09-12`
(annual TTL — maps detect change yearly; a missing/unreadable input
writes NOTHING: unknown, never partial).

## 2. 20-spot precision note (2026-09-17, offline, deterministic)

Method (throwaway probe `/tmp/hf624-precision.py`, output recorded
here): every 264th kept polygon by change_id (20 of 5288) vs the
snapshot's 252 140 OSM building centroids
(`osm/derived-buildings.json`): point-in-polygon count per polygon +
buildings within 100 m of centroid (development clearings pack
buildings; real cuts don't). Plus per-spot ring validity and DBF
`Pindala` vs LCC-recomputed ring area (a wrong projection would blow
areas up — it doubles as projection sanity).

Result: **20/20 clean-forest context, 0/20 development-adjacent.**
Zero buildings inside any sampled polygon (max 4 within 100 m, twice);
all 20 rings valid; DBF vs ring area agrees to ≤0.1 ha (smallest
polygons read ~0.1 ha low — DP-5 m vertex loss, honest and stated;
scorer distances read the same simplified rings, consistently).

```text
kevad-0 dbf=0.6 ring=0.6 bldg_in=0 bldg_100m=0 (24.88886, 59.10803)
kevad-1259 dbf=0.8 ring=0.8 bldg_in=0 bldg_100m=0 (25.10737, 59.38373)
kevad-1932 dbf=5.5 ring=5.5 bldg_in=0 bldg_100m=0 (24.19502, 59.20964)
kevad-2405 dbf=4.4 ring=4.4 bldg_in=0 bldg_100m=0 (25.24750, 59.07321)
kevad-2683 dbf=7.5 ring=7.4 bldg_in=0 bldg_100m=0 (24.19502, 59.32910)
kevad-3809 dbf=1.1 ring=1.1 bldg_in=0 bldg_100m=0 (23.92253, 59.05892)
kevad-4194 dbf=0.7 ring=0.7 bldg_in=0 bldg_100m=0 (23.63190, 59.18681)
kevad-4447 dbf=0.4 ring=0.4 bldg_in=0 bldg_100m=0 (24.26716, 59.16795)
kevad-502 dbf=0.7 ring=0.7 bldg_in=0 bldg_100m=0 (23.79965, 59.13117)
kevad-5393 dbf=0.3 ring=0.2 bldg_in=0 bldg_100m=0 (24.81234, 58.99138)
kevad-5906 dbf=0.3 ring=0.3 bldg_in=0 bldg_100m=0 (25.25355, 58.99425)
kevad-6146 dbf=0.5 ring=0.4 bldg_in=0 bldg_100m=0 (24.73247, 59.13518)
kevad-6387 dbf=0.4 ring=0.4 bldg_in=0 bldg_100m=1 (24.98392, 59.39743)
kevad-6651 dbf=0.9 ring=0.9 bldg_in=0 bldg_100m=0 (25.13770, 59.33082)
kevad-7449 dbf=3.1 ring=3.0 bldg_in=0 bldg_100m=0 (23.94999, 59.04009)
kevad-7762 dbf=3.3 ring=3.3 bldg_in=0 bldg_100m=0 (24.03441, 59.16511)
kevad-8225 dbf=2.1 ring=2.1 bldg_in=0 bldg_100m=0 (24.47929, 59.05366)
kevad-8641 dbf=4.2 ring=4.2 bldg_in=0 bldg_100m=0 (25.22899, 59.10502)
kevad-8881 dbf=2.0 ring=2.0 bldg_in=0 bldg_100m=4 (25.09257, 59.25605)
suvi-286 dbf=0.3 ring=0.3 bldg_in=0 bldg_100m=0 (25.61207, 59.44816)
```

Caveat (load-bearing, restated): OSM buildings can miss the newest
construction, and detected change is NOT official logging statistics
(automatic CHM-difference processing, errors possible) — the caveat
rides in every scorer reason and the map legend, always.

## 3. Recency bands + NULL rule (live)

`_score_change()`: ≤3 yrs & ≤500 m → 30; ≤3 yrs & ≤1500 m → 55;
4–10 yrs & ≤500 m → 60; else on-record → 70; empty window → **NULL**
("turvalist metsa see ei tõenda" — never "safe forest"). Publisher
caveat in every reason.

## 4. DoD evidence

```text
python3 scripts/build/batch_forest.py --zip /tmp/hf-624-cache/metsamuutused-2024.zip --snap /tmp/hf-624-proof
# → ok=True polygons=10201 kept=5288 dropped=0 verts=2982965->119881
python3 -m pytest services/scoring/tests/test_batch_forest.py services/scoring/tests/test_dims_p4_forestchange.py -q -p no:cacheprovider
# → 25 passed (observed 2026-09-17, worktree 624-forest)
python3 -m pytest services/scoring/tests -q -p no:cacheprovider
# → 2952 passed, 8 skipped
npm test (turbo vitest) → green; npm run typecheck, npm run lint → clean
GET /api/layers/forest/areas (live dev) → 200, 5288 areas, 0 guard-rejected
Map screenshot (/layers, P4-mets): 5288 polygons painted, zero page errors
```
