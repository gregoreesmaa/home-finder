# P4 microclimate cells — Keskkonnaagentuur climate normals (issue #611)

Group-Y verify-first verdict: **POSITIVE for the station-normals legs**
(P4 winter-mildness + wetness cells, scorer
`services/scoring/dims_p4_kliima_stations.py`, issue #541). The map
ships two slices (`kliima_frost`, `kliima_wet`) painted from harvested
1991-2020 normals. `docs/p4_kliima.md` (strategy-PDF dated negative,
#319/#378) is untouched — distinct dims (measured normals vs strategy
verdict), no double-score. `docs/p4_ilm.md` (#308/#374, live Harku
observations) stays the nowcast cousin.

## Layer verdict #611 (2026-09-16, polite, labelled one-off UA)

Keyless kliimaandmestik PostgREST (`https://keskkonnaandmed.envir.ee`,
CC BY 4.0) serves the normals the scorer's docstring describes:

* Station view `f_kliima_jaam_vaatlus` → HTTP 200, 25 stations
  nationwide; usable in/near Harjumaa = 3 (Tallinn-Harku AJHARK01
  59.398122N 24.602870E, Pakri AJPAKR01 59.3895N 24.0401E, Kuusiku
  AJKUUS01 58.9732N 24.7340E). 3 ≥ the issue's <3 single-row rule →
  nearest-station cells (no interpolation between them, pinned by
  test: midpoints take the nearest band, never a blend).
* Element view `f_kliima_element` → HTTP 200, 25 elements (daily
  DPA008/DPREC/DRH08/DRQS/DSDUR/DSND/DTAN/DTAX/DTA08/DWSX/DWS08,
  hourly PA0/PR1H/RH/SDUR1H/TA/TAN1H/TAX1H, 10-min PR10M/WD10M/WD10MA/
  WSX1H/WS10M/WS10MA/WS10MX).
* Monthly view `f_kliima_kuu` → HTTP 200, query pattern confirmed
  (monthly aggregates per element: DPREC sums, DTAN monthly min —
  frost-day COUNTS are not derivable from it, so frost needs the
  daily view, not optional).
* Daily view `f_kliima_paev` → EXISTS (found via one GET of the API
  root OpenAPI listing, not by fishing names): schema
  (jaam_kood, aasta, kuu, paev, vaartus, element_kood) confirmed with
  a limit=1 probe.
* Raw bodies in `/tmp/hf-kliima-probe/` + `/tmp/hf-611-kliima/`
  (one-off PR record, never committed).

## Annual harvest (scripts/build/batch_kliima.py, 2026-09-16)

~40 paced single GETs (2 s pacing, TTL 365 d, 429 = stop), run once:

* frost_days: mean annual days with daily DTAN < 0 over usable years
  (year usable with ≥ 300 DTAN rows; station needs ≥ 24/30 years).
* precip_mm: mean annual precipitation from summed monthly DPREC
  (year usable with all 12 months numeric; station needs ≥ 24/30).
* Bands mirror `_rank_dim` byte-for-byte: 3 joined → 70/55/40 dense
  (ties share the better band), 2 joined → 70/40, <2 → unranked.

Tally: frost Harku 128.6 d (55) / Pakri 106.5 d (70) / Kuusiku
146.5 d (40); wet Harku 699.9 mm (70) / Kuusiku 730.1 mm (40) /
**Pakri NULL** — genuine feed gaps (null vaartus winter months
2004–2010 + 2020-07: 22/30 complete years < the 24-year minimum).
Pakri stays wet-NULL by the coverage rule: its cell renders unknown
on the wet slice, never a faked middle (scorer parity: Pakri-area
listings score EI OLE on the same gap). Re-check on the next annual
harvest; pro-rating partial years would be fake precision.

Partial-decade guard (regression, same PR): the monthly view's
1000-row cap truncates silently — the first harvest ranked precip
off ONE page (10 years) and Pakri read NULL for the wrong reason.
The harvester paginates every view to a short page, and
`read_cached_pages` stitches with the same stop rule (pinned by
`test_cached_pages_*`); a truncated pull now fails the coverage
rule instead of publishing.

## Map wiring

`apps/web/lib/layers_kliima.ts` owns KLIIMA_CELLS + `kliimaBandAt`
(the map twin of `_rank_dim`) + per-slice `kliimaPointsIn` (bands
ride q; unranked cells ride WITHOUT q — plotted, never scored).
Slices reuse the tervise `qbands` kernel with zero changes
(nearest-station-wins inside the hard 70 km county radius — Loksa
sits ~65 km from Harku, so the county stays covered and the sea
stays unknown; no smoothing, no street-level gradients). Shared
files carry only `KLIIMA-HOOK (#611)` blocks. Legend states the
3-cell thinness + the 1991-2020 vintage on both slices.
