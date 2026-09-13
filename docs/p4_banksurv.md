# P4 banksurv verdict note — Swedbank/SEB/Luminori tagatis-küsitluste koondid (P4-038 bank leg)

> Dated-negative verdict for issue #323 (demo only — P4-038 is the
> only param naming this source, so there is no coverage follow-up;
> P4-038's sibling legs are already scored where they live, see below).
> Checked 2026-09-13. Single param is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_banksurv.py`, pinned by
> `services/scoring/tests/test_dims_p4_banksurv.py`.

## Verdict

**No pollable bank collateral-survey feed — the dim stays NULL with an Estonian reason.**
Bank collateral surveys are internal lending-decision/underwriting inputs: the public
surface is a marketing storefront plus per-customer loan flows and a commentary blog,
with no bulk download, no API, and no machine-use licence advertised
anywhere. There is no ingestion to cache, no TTL to state beyond this
one-off check (a future feed would pull quarterly at most — see below),
and no honest area-type gap table to paint.

## Openness evidence (one polite check, 2026-09-13, no scraping, no auth)

1 polite check, 2 served requests total (labelled one-off user-agent `home-finder
banksurv openness-check #323 (one-off, single GETs, no retry; contact
via GitHub home-finder)`, `--max-time 25`, headers + visible-text/link
scope read only). Raw bodies: `/tmp/hf-banksurv-probe/` (one-off PR
record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.swedbank.ee/` → 302 to `/private` | 0 bytes, locale-split gate | storefront entry, not a data portal |
| `https://www.swedbank.ee/private` → HTTP 200 (444 765 bytes, 4 344 visible chars, 75 links, title "Avaleht - Swedbank") | avaandmed / open data / andmestik / masinloetav / api / csv / geojson / wfs / download / allalaadimine / arendaja / developer all 0 in visible text; 0 machine-looking hrefs (no api/download/csv/json/geojson/wfs/andmestik/opendata/developer/arendaja/allalaadi in any link target); survey / koond / aggregaat / kinnisvaraturg / ülevaade all 0 | no open-data surface, no developer portal, no survey-aggregate table advertised — the storefront sells loans, it does not publish valuation inputs |
| "tagatis" hits on the same page (2x) | õppelaenu marketing prose ("kinnisvara tagatiseta" — unsecured study loan) | collateral word appears as ad copy, never as a dataset |
| Transaction surfaces on the same page | per-customer loan flows + `blog.swedbank.ee` commentary links | individual calculators and human analysis — never a bulk aggregate feed |

Judgment call: the check stopped at one bank's storefront on purpose —
collateral surveys are proprietary everywhere by construction, and SEB/Luminor loan
flows are the same per-customer calculators, not bulk feeds.
Chasing SEB/Luminor shells would add bytes, not information, and driving a
valuation calculator with invented borrower profiles would be exactly the
form-driving this repo refuses (AGENTS.md §5).

Pulls / cache / TTL: no pulls beyond the one-off check above (nothing pollable
exists — no cache, no live TTL). If a bank ever publishes a pollable aggregate
feed, the honest cadence is quarterly at most (area-type aggregates move on
publication timescales, matching the Stat KK11 quarterly and Maa-amet
publication legs): single GET, file cache, re-pull only.

## Honest shape (NULL until a bank opens a feed)

| Param | Dim key | Honest shape when a feed answers | Buyer-side check meanwhile |
|---|---|---|---|
| P4-038 bargaining margin, bank leg (demo) | `bargaining_margin_banksurv` | area-type offer-vs-valuation gap table from joined bank rows only, never a storefront grade or a calculator scrape | küsi maaklerilt piirkonnatüübi pakkumis-vs-tehingu lõhe statistikat (Maa-ameti publikatsioon), võrdle küsitavat P4-002 võrdlustehingutega |

Sibling P4-038 slices keep their owners (untouched): Land Board publication gap table
(`dims_p4_maa_tehingud` `dim_bargaining_margin`), Stat quarterly-index calibration
(`dims_p4_stat` `dim_bargaining_margin_stat`), own-store per-listing drop NULL-by-design
(`dims_p4_own_store` `dim_bargaining_margin` — the listing's own cut already belongs to
P4-001, no double-score). KV.ee/city24 asking-vs-microcomp residuals, the own-adapter
price-drop distribution, and notariaat volume heat have no dims module of their own
(adapter-store / unpublished inputs) — named where the param needs them, never faked here.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: P4-038 is the only param naming
   this source family (parameters4.md P4-038 source (5) "Tallinn bank
   collateral survey aggregates (verify openness)") — one module, one test file, one verdict note.
2. The Swedbank storefront carries the verdict for the source family: the page
   advertises no open-data surface and no survey-aggregate table, and the only
   transaction surfaces are per-customer loan flows plus a commentary blog. An SEB
   and Luminor shell fetch would confirm the same calculator shape, not a
   feed.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when a bank opens a feed)

1. Re-run the probes above on demand (a feed announcement, not a cron —
   there is no ingestion to refresh); paste fresh evidence in the reopen PR.
2. If any bank publishes a pollable bulk collateral-survey aggregate feed (CSV/
   API with a machine-use licence), transcribe one Tallinn quarter of
   dated area-type rows into the cache dir and run them through a parser +
   area-type join on fixtures first.
3. Graduate the dim to a band ONLY from joined rows (area-type gap-table hinnang per
   parameters4.md P4-038 shape, quarterly cadence); keep NULL-with-Estonian-reason
   for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
