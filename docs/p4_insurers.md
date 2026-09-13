# P4 insurers verdict note — PZU/ERGO/If tariifitsoonid (P4-015 insurer leg)

> Dated-negative verdict for issue #286 (demo only — P4-015 is the
> only param naming this source, so there is no coverage follow-up;
> P4-015's sibling legs are already scored where they live, see below).
> Checked 2026-09-13. Single param is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_insurers.py`, pinned by
> `services/scoring/tests/test_dims_p4_insurers.py`.

## Verdict

**No pollable insurer tariff feed — the dim stays NULL with an Estonian reason.**
Insurer tariff zones are internal underwriting/pricing data: the public
surface is a marketing storefront plus per-customer quote calculators,
with no bulk download, no API, and no machine-use licence advertised
anywhere. There is no ingestion to cache, no TTL to state beyond this
one-off check, and no honest per-address tariff band to paint.

## Openness evidence (one polite check, 2026-09-13, no scraping, no auth)

2 served requests total (labelled one-off user-agent `home-finder
insurers openness-check #286 (one-off, single GETs, no retry; contact
via GitHub home-finder)`, `--max-time 25`, headers + visible-text/link
scope read only). Raw bodies: `/tmp/hf-insurers-probe/` (one-off PR
record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.if.ee/` → 301 to `/eraklient` | 0 bytes, locale-split gate | storefront entry, not a data portal |
| `https://www.if.ee/eraklient` → HTTP 200 (189 542 bytes, 5 515 visible chars, 15 script tags, 181 links, title "If Kindlustus") | avaandmed / open data / andmestik / masinloetav / api / csv / geojson / wfs / download / arendaja / developer all 0 in visible text; 0 machine-looking hrefs (no api/download/csv/json/geojson/wfs/andmestik/opendata/developer in any link target); tariif / kindlustustsoon / flood / üleujutus / varguse all 0 | no open-data surface, no developer portal, no zone table advertised — the storefront sells policies, it does not publish pricing inputs |
| Quote-flow links on the same page | `ekindlustus.if.ee` policies/invoices/claims + `/eraklient/kindlustused/*` product pages | per-customer authenticated quote/self-service flows — individual calculators, never a bulk zone feed |

Judgment call: the check stopped at one insurer's storefront on purpose —
tariff tables are proprietary everywhere by construction, and PZU/ERGO
quote flows are the same per-customer calculators, not bulk feeds.
Chasing PZU/ERGO shells would add bytes, not information, and driving a
quote calculator with invented customer profiles would be exactly the
form-driving this repo refuses (AGENTS.md §5).

## Honest shape (NULL until an insurer opens a feed)

| Param | Dim key | Honest shape when a feed answers | Buyer-side check meanwhile |
|---|---|---|---|
| P4-015 insurability, insurer leg (demo) | `insurer_tariff` | per-address tariff band from joined insurer rows only, never a storefront grade or a calculator scrape | kodukindlustuse pakkumine oma andmetega PZU/ERGO/If kalkulaatorist, omavastutuse ja üleujutus-/varguse-välistuste võrdlus |

Sibling P4-015 slices keep their owners (untouched): KAUR flood zones
(`dims_p4_kaur` `dim_kindlustatavus_kaur`), EELIS flood/restriction
(`dims_p4_eelis` `dim_kindlustus_eelis`), PPA theft tertile
(`dims_p4_ppa` `dim_theft_tariff_proxy`), Päästeamet fire density
(`dims_p4_paaste` `dim_insurability`, linnaosa join + illiquidity flag
on kõrge). The parameters4.md "else illiquidity flag only" branch is
already carried by these cousins (flood/restriction hits flag in
KAUR/EELIS, kõrge flags in paaste/PPA) — no unflagged residual remains
for this leg.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: P4-015 is the only param naming
   this source family (parameters4.md P4-015 source (3) "insurer tariff
   zones Tallinn — PZU/ERGO/If (verify openness first, else illiquidity
   flag only)") — one module, one test file, one verdict note.
2. The If storefront carries the verdict for the source family: the page
   advertises no open-data surface and no zone table, and the only
   transaction surface is authenticated per-customer quote flows. A PZU
   and ERGO shell fetch would confirm the same calculator shape, not a
   feed.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when an insurer opens a feed)

1. Re-run the probes above on demand (a feed announcement, not a cron —
   there is no ingestion to refresh); paste fresh evidence in the reopen PR.
2. If any insurer publishes a pollable bulk tariff-zone feed (CSV/GeoJSON/
   WFS/API with a machine-use licence), transcribe one Tallinn week of
   dated rows into the cache dir and run them through a parser + per-address
   join on fixtures first.
3. Graduate the dim to a band ONLY from joined rows (zone-join hinnang per
   parameters4.md P4-015 shape, illiquidity flag where the tariff bites);
   keep NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
