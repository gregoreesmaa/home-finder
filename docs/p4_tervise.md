# P4 tervise verdict note — Terviseamet (new uses) feed (P4-017 + P4-024)

> Dated-negative verdict for issues #289 (demo) and #362 (coverage).
> Checked 2026-09-13. Both params are documented no-map NULL dims
> (OTA PR #131 precedent); scorers live in
> `services/scoring/dims_p4_tervise.py`, pinned by
> `services/scoring/tests/test_dims_p4_tervise.py`.

## Verdict

**No open machine feed — both dims stay NULL with Estonian reasons.**
Terviseamet's drinking-water monitoring lives as a human query UI
(vtiav.sm.ee per-veevärk üldhinnang lookups), tick stats as
county-grain PDFs, bathing-water quality classes as seasonal PDFs.
There is no public bulk feed (no CSV/JSON/API/export, no open-data
page) to poll politely, so there is no ingestion to cache, no TTL to
state beyond this one-off check, and no honest per-parcel join or
coarse hinnang cell to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

6 tiny requests total (six single GETs, labelled one-off user-agent
`home-finder-research/0.1 (polite one-off openness check, single
GETs; GitHub gregoreesmaa/home-finder issues 289/362)`, headers +
visible-text keyword scope read only). Raw bodies:
`/tmp/tervise-open/` (one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.terviseamet.ee/` (HTTP 200, ~155 KB, cloudflare) | Visible text ~6.9k chars; sweep 0 for avaandmed / open data / GTFS / arendaja / developer / API / X-tee / andmestik / masinloetav | No open-data page, no developer portal, no machine feed advertised |
| `…/keskkonnatervis/vesi/joogivesi` (HTTP 200, ~173 KB) | Visible text ~16.0k chars; sweep 0 for avaandmed / API / X-tee / andmestik / masinloetav / csv / xls / json; file links are human PDFs (indicator descriptions, lab certificates) + site RSS; page points at the vtiav.sm.ee "Joogivee kvaliteedi andmebaas" | Monitoring guidance exists as a human page — the P4-017 Tallinn-proovid slice cannot be joined |
| `…/keskkonnatervis/vesi/suplusvesi` (HTTP 200, ~188 KB) | Visible text ~18.6k chars (seire x6, proov x9); file links are human PDFs (Suplusvee kvaliteediklassid 2025, Supluskohtade kvaliteediklassid 2026. a hooajaks, microbiology indicators) + site RSS; links into the vtiav.sm.ee suplusvesi tab | Bathing-water quality exists as seasonal PDFs — the P4-024 Pirita/Stroomi/Kakumäe slice cannot be joined |
| `https://vtiav.sm.ee/index.php/?active_tab_id=JV` (HTTP 200, ~32 KB, "Avalikud andmed :: Terviseamet") | Human query UI: POST filter form with autocomplete, 971 kirjet over 49 pages, per-veevärk üldhinnang (Vastav/Mittevastav); tabs load via tabRefresh AJAX (`/ajax_urls/otsiTulemused…`); the "Avaandmed" tab is a JS tab, not a bulk export — no CSV/JSON/API/export endpoint | Per-veevärk compliance is look-up-able by a human, never a comparable machine vintage — the P4-017 seire leg cannot be polled |
| `…/nakkushaigused/statistika` (HTTP 200, ~221 KB) | Visible text ~17.0k chars; sweep 0 for csv / json / API / andmestik / masinloetav; current stats are human PDFs (monthly NH_haigestumine_Eestis_maakondade kaupa, annual epid overviews); the single .xls is a 2000–2006 archive table (kuude ja maakondade kaupa) | Tick stats exist as county-grain human PDFs — every Tallinn listing would share one Harju number, so no listing-discriminating cell can be painted; the archive .xls is stale by construction on top of county grain |
| `https://andmed.eesti.ee/dataset?q=terviseamet` (HTTP 200, ~75 KB) | JS "Teabevärav" shell, 12 visible characters, no server-rendered results | No trivially pollable national-portal Terviseamet dataset (same shell as the #264/#277/#284 checks) |

Judgment call: the check stopped at storefront/page level on
purpose — no AJAX filter driving, no vtiav pagination walking, no
PDF parsing. Driving the query UI page-by-page would be scraping
human publications, not polling a feed — exactly what this repo
refuses (AGENTS.md §5).

## What stays open (overturn paths, not wired here)

- **P4-017 seire half:** the vtiav.sm.ee veevärk üldhinnang lookup
  + Tallinna Vesi iseteenindus technical conditions stay the human
  buyer checks; the Tallinna Vesi zone-table + tariff legs
  (dims_p4_tvesi dim_water_sewer_zone / dim_water_tariff, #263/#343)
  and the geology-side ÜVK leg (dims_p4_maa_subsurface
  dim_water_sewer, #248/#332) stay the scored machine cousins for
  the same param. A Terviseamet machine monitoring vintage would
  graduate only the seire leg here.
- **P4-024 Terviseamet half:** the supluskohtade nimekiri +
  kvaliteediklassid PDFs, the vtiav.sm.ee suplusvesi lookup, the
  puugihaiguste guidance page, and kohapealne vaatlus (roheline
  serv / pritsimisriba / farmilõhn) stay the checks. The õietolm
  (Keskkonnaagentuur), PRIA spray-drift, EELIS habitat-proxy and
  farm-odour slices belong to future source issues; the OSM/group07
  allergen proxies stay where they live.
- **Full overturn:** Terviseamet (or andmed.eesti.ee) publishes a
  machine monitoring/stats feed for either slice → re-open #289,
  build the polite cached ingestion (annual TTL per
  parameters4.md P4-017/P4-024), and graduate that dim to a
  per-parcel join (P4-017) or coarse hinnang cells (P4-024).

## Layer re-check #494 (2026-09-13) — monitoring-point locations

Group B verify-first (issue #494): if monitoring-point LOCATIONS are
open, build a point overlay; per-point quality gradients need a dated
feed or stay NULL.

**Verdict: still no open feed — `tervise` ships as a points-empty
layer.** Four polite single GETs (labelled one-off user-agent
`home-finder-research/0.1 (… issue 494)`, headers + visible-text
keyword scope only, no form driving, no pagination walking), raw
bodies one-off in `/tmp/tervise494/` (not committed):

| Check | Observed | Meaning |
|---|---|---|
| `terviseamet.ee/keskkonnatervis/vesi/suplusvesi` (HTTP 200, ~188 KB) | Visible text ~18.6k chars; `seirepunkt` x1 — glossary prose ("Seirepunkt – koht, kus suplusvee proovid võetakse"), not a list; file links are human PDFs only (kvaliteediklassid 2025, 2026 hooaeg, microbiology indicators, lab certificates) | Monitoring points exist as a defined term + seasonal PDFs — no plottable locations, no coordinates |
| `vtiav.sm.ee/index.php/?active_tab_id=SV` (HTTP 200, ~31 KB) | Human POST-filter query UI (Maakond/Valdaja/Supluskoha nimi/Veekogu/Staatus/Aasta); `avaandmed` x1 — the JS "Avaandmed" tab label, not a bulk export; zero file links | Per-beach lookups stay human-only; driving the filters page-by-page would be scraping, not polling (AGENTS.md §5 refusal stands) |
| `andmed.eesti.ee/dataset?q=terviseamet` and `?q=suplusvesi` (HTTP 200, ~75 KB each) | JS "Teabevärav" shell, 12 visible characters each, no server-rendered results | No trivially pollable national-portal dataset (same shell as #264/#277/#284) |

Out of scope (different agencies, different future issues): õhuseire
air stations (Keskkonnaagentuur, G07 alternate) and the EGT radon WFS
(nomap.md G7 overturn) — #494 covers Terviseamet P4-017/P4-024 only.

**Layer shape** (`apps/web/lib/layers_tervise.ts`, `TERVISE-HOOK
(#494)`): `tervise` (parameters4 `P4-017+P4-024`, paramIds `[]`)
serves zero points and builds zero raster — the map renders basemap +
honestly-unknown, the status line names the missing feed, and
per-point quality stays NULL in `dims_p4_tervise.py`. Monitoring
points are never invented: a hand-transcribed beach triple from a
seasonal PDF would be unanchored geometry with no poll path and no
TTL. Overturn: a machine monitoring-point feed (CSV/JSON/WFS) →
re-open #494, build the polite cached ingestion, graduate to real
points (quality per point still needs a DATED feed).

## Why demo + coverage share one PR

The coverage body (#362) states it extends the demoed ingestion
(#289). With the demo verdict dated-negative there is no ingestion
to extend, so the coverage slice (P4-024) lands in the same verdict
module instead of a second file importing a pipeline that does not
exist. One module, one test file, one verdict note — no edits to
shared files (same precedent as Elron #284+#358 and TLT
#277+#351).
