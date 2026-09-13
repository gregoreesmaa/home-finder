# P4 Maa-LiDAR verdict: LiDAR/DEM/LoD2 (P4-041 demo + 6-param coverage)

Closes #247 (demo) and #331 (coverage) — paired in one PR because the
coverage body states it extends the demo ingestion; the per-parcel `lidar`
artefact dict is the coverage-anticipated plumbing (said here as required).

Code: `services/scoring/dims_p4_maa_lidar.py` (demo P4-041 + 6 coverage
params); tests: `services/scoring/tests/test_dims_p4_maa_lidar.py`
(hermetic, synthetic fixtures, no network).

## 1. Openness verdict (2026-09-13, KEEP — dated negatives count)

Six polite pulls total (UA `home-finder-p4-lidar-probe/1.0`,
`--max-time 25`, 3 s pacing between hosts), cached to `/tmp/hf-maa-lidar/`
(headers + pages kept for the PR record, never committed):

| # | URL | Result |
|---|-----|--------|
| 1 | `https://geoportaal.maaruum.ee/eng/spatial-data-p58.html` | **OPEN.** HTTP/2 200, 40 295 B. Index lists `elevation-data-p308.html` (+ `download-elevation-data-p664.html`, "LiDAR collected elevation points") and `geo3d/` (+ `3d-data-p836.html`, `download-3d-data-p837.html`). |
| 2 | `https://kaart.maaamet.ee/wms/alus?service=WMS&request=GetCapabilities` | **No elevation/DEM/LiDAR/3D layer (dated note, not a block).** HTTP 200, 66 092 B, 108 layers; keyword scan for kõrgus/reljeef/DEM/LiDAR/3D/hoone-building hits nothing (relief-shaded basemap only). View, never data. |
| 3 | `.../elevation-data/download-elevation-data-p664.html` | **OPEN.** HTTP/2 200, 54 665 B. Per-map-sheet raw LiDAR (spring low-altitude, summer forestry, surface keypoints) + DTM 1/5/10 m GeoTIFF+XYZ + whole-Estonia DTM/DSM/CHM vintages (CHM 2008–2024 kevad/suvi, DSM/nDSM 5 m 2017–2020/2020–2023). Last update 29.04.2026. Open-data licence linked. |
| 4 | `.../geo3d/download-3d-data-p837.html` | **OPEN.** HTTP/2 200, 778 287 B. Per-municipality LoD1 AND LoD2 (`hooned_lod1` / `hooned_lod2`) in citygml/gdb/obj — incl. `hooned_lod2-Tallinn-{citygml,gdb,obj}.zip` (745 lod2 references on page). Last update 29.04.2026. |
| 5 | HEAD `index.php?...&andmetyyp=hooned_lod2&dl=1&f=hooned_lod2-Tallinn-citygml.zip&page_id=837` | **OPEN bulk endpoint.** HTTP/2 200, `content-type: application/zip`, `content-length: 33043884` (~31.5 MB, matches the page table), `content-disposition: inline; filename=hooned_lod2-Tallinn-citygml.zip`. No key, no login. The 33 MB zip itself was NOT downloaded (polite: headers prove servability). |
| 6 | HEAD `index.php?...&andmetyyp=mp_korgusmudelid&dl=1&f=DTM_5m_eesti.tif&page_id=664` | **Transport non-answer, NOT a negative.** `curl: (28) timeout after 25 s, 0 bytes`. The identical `dl=1` pattern is proven by pull #5; re-probe on bulk-job day, do not hammer (AGENTS.md §7.4). |

## 2. Ingestion contract (what the demo implements end-to-end)

`services/scoring/dims_p4_maa_lidar.py`: `fetch_cached()` (polite,
cache-first, `TTL_DAYS = {lod2_bulk: 365, dtm_bulk: 365}` — ~1/4 of Estonia
re-flown yearly, LoD2 updated annually per the Geo3D summary; pages show
last update 29.04.2026) → `parse_dtm_xyz()` / `parse_lod2_summary()` (pure,
fixture-tested: XYZ stats, CityGML building count + measuredHeight/storeys)
→ annual bulk job parses Tallinn LoD2 CityGML + covering DTM sheets into the
per-parcel `lidar` artefact the seven dims join against. Transport errors
raise and never touch the cache; HTTP 429 stops the run. Cache files:
`<cache-dir>/hf-p4-maa-lidar/<name>` (default bulk: Tallinn LoD2 CityGML
~31.5 MB + covering DTM sheets; `lod2_url()` builds per-municipality URLs).

## 3. Per-param honest shapes (per-listing / per-parcel geometry joins only)

| Param | Shape (this ingestion's leg) | Missing-input behaviour |
|-------|------------------------------|-------------------------|
| P4-041 glimpse (demo) | View class off the LoD2 view-fan: ≥3° → 85, thin → 70, none → 45 | NULL (no floor fact / no fan artefact); price-premium leg (P4-002) named EI OLE |
| P4-016 eng. geology | Coarse DEM screen: sink ≥0.5 m or roughness ≥1.0 m → 40, else 60 | NULL (no DEM); EGT turvas/karst/alvar class named EI OLE (#235 leg) |
| P4-031 backyard weather | Cold-air screen: parcel ≥1 m below surroundings → 45, else 60 | NULL (no DEM); sensor.community density named EI OLE (Harku leg in dims_p4_ilm) |
| P4-034 overheating | LoD2 shade: deep shade → 65; exposed top floor capped at 40; else 55 | NULL (no shading); EHR-sim + July band named EI OLE |
| P4-035 darkness | LoD2 open-sky bands 35/50/65 (capped — lamps need inventory) | NULL (no shading); lamp inventory + December band named EI OLE |
| P4-036 roof income | Usable facets → kWp (8 m²/kWp): ≥3 → 75 / ≥1.5 → 60 / >0 → 50 / none → 40 | NULL (no roof artefact); Elering tariff + ad yield named EI OLE (upside-only) |
| P4-056 courtyard trap | Enclosure index h/w: trapped ≥1.2 → 35 / open court → 55 / no court → 70 | NULL (no enclosure); air-station validation named EI OLE (calm-share in dims_p4_ilm) |

All NULL reasons say `hinnang` + `EI OLE` and name the buyer-side check.
No Overpass fragment / tag mapping: DEM/LoD2 geometry is not OSM data, and
the per-parcel artefact arrives caller-side until the bulk job owns it —
inventing a fragment would be dishonest plumbing. No WEIGHTS / livability /
layers / docs changes (joint rebalancing stays a joint change).

## 4. Judgment calls for the reviewer

1. Demo+coverage in ONE PR (AGENTS.md §3 says one issue per PR): #331
   explicitly extends the #247 ingestion, so splitting would review the same
   ingestion twice. Both issues close here; a fresh reviewer still merges.
2. `(listing, lidar)` — the optional-per-parcel second argument is the
   coverage-anticipated new plumbing: geometry joins cannot ride the OSM POI
   channel, so the artefact travels explicitly (same rationale as the ilm
   batch's `baseline` argument, PR #383).
3. No double-scoring vs the ilm batch (#383): ilm owns the Harku-station legs
   (July/December bands, calm-share, documented NULLs pointing at LiDAR);
   this module owns ONLY the LiDAR/DEM/LoD2 legs and cross-references ilm in
   reasons. P4-016's EGT/WFS legs stay with the #235 overturn (untouched).
4. Band edges (3° sliver, 0.5 m sink / 1.0 m roughness, 1.0 m frost dip,
   0.35/0.3/0.6 sky, 8 m²/kWp, 1.2 enclosure) are coarse first-cut judgments,
   documented in the module docstring — challengeable, dull by design.
5. The 33 MB Tallinn LoD2 zip was deliberately NOT downloaded; HEAD headers
   prove the endpoint serves. The annual bulk job downloads it once/TTL.
6. Test CityGML/XYZ fixtures are synthetic (clearly labelled) — real observed
   values appear only in §1 above, never as ingested data.

## 5. DoD evidence (observed 2026-09-13, worktree `247-p4-maa-lidar`)

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_maa_lidar.py -q
.........................                                                     [100%]
25 passed in 0.07s

$ python3 -m pytest services/scoring/tests/test_dims_p4_maa_lidar.py services/scoring/tests/test_dims_p4_ilm.py services/scoring/tests/test_dims_p4_maa_tehingud.py services/scoring/tests/test_dims_p4_peatus.py services/scoring/tests/test_dims_p4_comapps.py -q
............................................s........................... [ 55%]
..........................................................               [100%]
129 passed, 1 skipped in 0.11s   (skip: pre-existing HF_LIVE_ILM=1 live test)

$ python3 -m pytest services/scoring/tests -q
892 passed, 2 skipped in 8.95s   (skips: HF_LIVE_ILM=1 live + DATABASE_URL integration — both pre-existing env gates)
```

- Hermetic: the suite makes zero network calls (cache-hit path only).
- New files only: `services/scoring/dims_p4_maa_lidar.py`,
  `services/scoring/tests/test_dims_p4_maa_lidar.py`, `docs/p4_maa_lidar.md`.
  No edits to shared files (`livability.py`, WEIGHTS, layers,
  `docs/layers.md`, `docs/nomap.md`, `parameters4.md`, `dims_group03*.py` —
  untouched).
