# P4 StaMT verdict note — Tallinna Sotsiaal- ja Tervishoiuamet teenuste kaardid (P4-011 StaMT leg)

> Dated-negative verdict for issue #273 (demo only — P4-011 is the
> only param using this source, so there is no coverage follow-up).
> Checked 2026-09-13. Single param is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_stamt.py`, pinned by
> `services/scoring/tests/test_dims_p4_stamt.py`.

## Verdict

**No pollable StaMT bulk feed — the dim stays NULL with an Estonian reason.**
The agency has no reachable storefront page at the canonical slugs
(one 404, one stale CMS redirect), and the service maps themselves
live as layers inside the interactive Tallinna veebikaart (an Esri
Experience Builder app shell with zero server-rendered data and no
bulk/download/API surface). The national open-data portal shows no
server-rendered StaMT dataset, and tallinn.ee exposes no sitemap to
poll. There is no ingestion to cache, no TTL to state beyond this
one-off check, and no honest per-linnaosa service band to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

7 single GETs total (labelled one-off user-agent `home-finder stamt
openness-check #273 (one-off, single GETs, no retry; contact via GitHub
home-finder)`, ≥ 6 s pacing, `--max-time 25`, headers +
visible-text/link scope read only). Raw bodies: `/tmp/hf-stamt-probe/`
(one-off PR record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tallinn.ee/et/sotsiaal` → 404 "Lehekülge ei leitud" (123 245 B CMS 404 template) | guessed short agency slug dead | no landing at this path |
| `https://www.tallinn.ee/et/sotsiaal-ja-tervishoiuamet` → 301 (410 B) → `/group/77/toc/14705` → 404 | stale CMS redirect to a dead group URL | agency page not reachable at storefront level; no further URL-guess enumeration |
| `https://www.tallinn.ee/et/tervishoid` → 301 (474 B) | same redirect family | no data surface here either |
| `https://kaart.tallinn.ee/` → 200 `https://gis.tallinn.ee/veebikaart/` (5 023 B, "Tallinna veebikaart", 21 visible chars, 4 script tags, ArcGIS JS API 4.34 / jimu-core) | Esri Experience Builder app shell, zero server-rendered data, no bulk/download/API href | teenuste kaardid live here as app layers, not a feed |
| `https://andmed.eesti.ee/dataset?q=sotsiaal` → 200 "Teabevärav" (75 497 B, 12 visible chars) | JS shell, no server-rendered results | no trivially pollable national-portal StaMT dataset (same finding as #270) |
| `https://www.tallinn.ee/sitemap.xml` → 404 (same CMS 404 template) | no machine page index | nothing to poll for agency/map URLs |

TTL: one-off dated check only — with no pollable feed there is no
ingestion to cache and no recurring TTL to state.

Judgment call: the check stopped at storefront/shell level on purpose —
no ArcGIS service chasing, no layer harvesting, no session flows, no
account creation. Driving the veebikaart app to extract StaMT points
would be exactly the scraping this repo refuses (AGENTS.md §5).

## Honest shape (NULL until StaMT opens a feed)

| Param | Dim key | Honest shape when a feed answers | Buyer-side check meanwhile |
|---|---|---|---|
| P4-011 family services, StaMT leg (demo) | `stamt_services` | per-linnaosa table from joined StaMT rows only, never a screenshot grade | lasteaia queue Haridusameti e-teenusest, GP nimistu avatus Tervisekassa nimistuotsingust, nearest services Tallinna veebikaardilt or kohapeal |

Sibling P4-011 slices keep their owners (untouched): Haridusamet queue
stats (`dims_p4_haridus`, NULL), EHIS capacity (`dims_p4_ehis`, joined
rows only), Tervisekassa GP lists, REL2021 age grid, koolivõrgu
arengukava (their own demos).

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: P4-011 is the only param naming
   this source (parameters4.md P4-011 source (4)
   "Tallinna Sotsiaal- ja Tervishoiuamet teenuste kaardid") — one
   module, one test file, one verdict note.
2. The veebikaart app shell carries the verdict for the source: the
   agency slugs are dead/stale and the one reachable map is a JS shell
   with zero machine markers. A second layer-level fetch would add
   bytes, not information — and chasing it would be scraping.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when StaMT opens a feed)

1. Re-run the probes above on demand (a feed announcement, not a cron —
   there is no ingestion to refresh); paste fresh evidence in the reopen PR.
2. If StaMT (or gis.tallinn.ee) publishes a pollable bulk service feed
   (CSV/GeoJSON/WFS/API with a machine-use licence), transcribe one
   Tallinn snapshot of dated rows into the cache dir and run them through
   a parser + per-linnaosa join on fixtures first.
3. Graduate the dim to a per-linnaosa band ONLY from joined rows; keep
   NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
