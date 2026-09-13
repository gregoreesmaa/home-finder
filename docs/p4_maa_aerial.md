# P4 Maa-aerial — openness verdict + demo/coverage note (issues #246, #330)

> Verdict date: 2026-09-13 (all probes single polite fetches, cached
> `/tmp/hf-p4-maa-aerial/`, ≥ 3 s pacing, contact UA in headers).
> Code: `services/scoring/dims_p4_maa_aerial.py` (demo P4-022 + 7 coverage
> params); tests: `services/scoring/tests/test_dims_p4_maa_aerial.py`
> (hermetic, synthetic fixtures, no network).

## Verdict

| Source | Result | Evidence (2026-09-13) |
|---|---|---|
| Maa-amet **fotokaart WMS** GetCapabilities (EESTIFOTO orthophoto + queryable nDSM) | **OPEN** | `GET kaart.maaamet.ee/wms/fotokaart?SERVICE=WMS&REQUEST=GetCapabilities` → HTTP 200, 60 038 B, `application/vnd.ogc.wms_xml`; layers `EESTIFOTO` (Ortofoto), `nDSM` + queryable `nDSM_info` ("Alusandmed 2020-2023") |
| Maa-amet **ajalooline WMS** GetCapabilities (historical topo, change context) | **OPEN** | HTTP 200, 154 273 B; layers `kaheverstakaart`/`kolmeverstakaart`/NL-topo vintages + `_info` metainfo layers |
| Maa-amet **kõrgusandmed** page (DEM/DSM/nDSM + WCS refs) | **OPEN** | HTTP 200, 59 528 B; documents `Maakattemudeli WCS` + `Maapinnamudeli WCS`, LiDAR-flown areas, nDSM Toompea example |
| Tallinna Vesi **sademevesi** page (zones + tariff) | **OPEN** | HTTP 200, 317 921 B (final URL `/veetarbijale/sademevesi`); documents lahkvoolne/ühisvoolne piirkonnad + `Hinnakiri` — P4-060 zone-table leg is real |
| Per-year **aerial-vintage WMS** layers | **DATED PARTIAL-NEGATIVE** | fotokaart serves the current `EESTIFOTO` mosaic; no per-year vintage layer names in caps — vintages live in downloads/production history. Consequence: P4-022/P4-030 score a coarse then/now cross-check, never a true year-delta |
| Dedicated Maa-amet **shoreline-retreat** layer | **DATED PARTIAL-NEGATIVE** | Not found on the probed pages/services. Consequence: P4-058 cliff leg is a coarse cross-check (ajalooline topo + ETAK vetevõrk + manual flag with date) |
| Maa-amet **impervious-surface** (vett mitteläbilaskva pinna) layer | **DATED PARTIAL-NEGATIVE** | Not found on the probed pages/services. Consequence: P4-060 scores the Tallinna Vesi zone table + checklist; the proxy leg is named EI OLE, not faked |
| `kaart.maaamet.ee/wms/alus-kaart` (invented path, my first guess) | **403 — my error, not a verdict** | The documented path is `/wms/alus` (see WMS-services page); the 403 came from a guessed URL. Kept here so the reviewer sees the mistake, not a claim |

Re-probe annually (TTL 365 d); a newly opened vintage/retreat/surface
layer flips the verdict without code changes (ingestion already caches
with TTL; `parse_wms_layer_names` verifies layer presence off caps).

## Pull policy (polite, cached, TTL-stated)

- One request per source per run; `User-Agent: home-finder-research/0.1`
  (polite annual bulk; issue 246); 25 s timeout; ≥ 3 s pacing between hosts.
- `fetch_cached(url, cache_dir, name, ttl_days)`: fresh cache wins (no
  request); transport errors are raised and **never cached as data**; HTTP 429
  raises immediately (stop signal, no retry).
- TTLs: every source **365 d** (annual bulk per #246; WCS models and
  tariffs move yearly at most).

## Per-param wiring (all honest shapes = coarse flag / cross-check / context)

| Param | Wired leg (this ingestion) | Legs honestly missing (EI OLE, named not faked) |
|---|---|---|
| P4-022 photo forensics (demo) | 4-leg cross-check: image-hash dupes + EXIF daylight + photo/EHR room-count + aerial facade flag; 2+ flags → 30, 1 → 55, clean → 80 | any leg with no data; zero legs → NULL (never a clean bill off zero evidence) |
| P4-029 street observer | Mapillary/CV date + facade/issues + OSM sidewalk cross-check; clean ≤ 2 y → 75, stale cap 60 | no imagery at all; P4-022 join named, not re-scored |
| P4-030 change delta | NDVI-drop / new-neighbour / raieluba / facade signals → 45; dump → 35; quiet legs → 70 | true year-delta (single mosaic); no leg → NULL |
| P4-041 glimpse | LiDAR/LoD2 fan class: open 85 / sliver 70 / none 50 (neutral taste-match) | fan itself (floor alone never scores); future blockage −15 via P4-006 join |
| P4-056 courtyard trap | LiDAR enclosure index ≥ 0.7 → 35 / ≥ 0.4 → 55 / else 75 | Harku wind leg (lives in dims_p4_ilm, cross-referenced, never re-scored) |
| P4-057 heat-pump hum | uptake + complaints → 40; uptake only → weak neutral 55; clean data → 70 | measurement itself (proxy by construction); no heating data → NULL |
| P4-058 ice + cliff | steep roof / warning date / retreat flag / < 100 m edge → 40 with date; clean-with-data → 70 | dedicated retreat layer; no leg → NULL (warnings absent ≠ safe) |
| P4-060 stormwater | Tallinna Vesi zone-table fee bands (0 → 75 / ≤ 50 → 65 / ≤ 150 → 50 / else 40) + EIS queue in reason | Maa-amet impervious-surface proxy; no zone/table → NULL |

Never a gradient: no distance weighting, no interpolation, exact-match /
threshold joins only; P4-041 `none` and P4-057 uptake-only score neutral
so taste/ambiguity cannot push the steal sort.

## Pairing + overlap notes (for the reviewer)

- Demo + coverage share ONE PR because #330's body states it extends the
  #246 demo ingestion ("no new plumbing expected") — same precedent as
  #384 (#244 demo + #328 coverage).
- P4-056 overlap with `dims_p4_ilm.dim_courtyard_trap` is a deliberate
  fold-in: that ilm dim is a documented NULL whose reason says the
  enclosure index "eeldaks Maa-ameti LiDAR-it" — this module provides
  exactly that leg. The ilm file is untouched; its wind leg is named in
  the reason, never re-scored. The weight-rebalance follow-up merges legs.
- Overturn #235 (Maa-amet WFS for parameters3 G3) is untouched:
  no `dims_group03*.py` or shared/group file was modified — new files only.
