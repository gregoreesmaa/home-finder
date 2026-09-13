# P4 airbnb verdict note — Inside-Airbnb-style short-rental density (P4-003 density leg)

> Dated-negative verdict for issue #293 (demo only — P4-003 is the
> only param using this source, so there is no coverage follow-up).
> Checked 2026-09-13. Single param is a documented no-map NULL dim
> (OTA PR #131 precedent); the scorer lives in
> `services/scoring/dims_p4_airbnb.py`, pinned by
> `services/scoring/tests/test_dims_p4_airbnb.py`.

## Verdict

**Open licence, no Tallinn dataset — the dim stays NULL with an Estonian reason.**
Inside Airbnb publishes its dumps under CC licences (CC BY 4.0 / CC0
links on the index), and bulk CSV downloads are the sanctioned path —
but the city index carries no Tallinn or Estonia dataset at all. There
is no ingestion to cache, no TTL to state beyond this one-off check,
and no honest Tallinn hex nuisance-hinnang to paint.

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth, no downloads)

3 single GETs total (labelled one-off user-agent `home-finder airbnb
openness-check #293 (one-off, single GETs, no retry; contact via GitHub
home-finder)`, ≥ 6 s pacing, `--max-time 25`, headers + visible-text/link
scope read only). Raw bodies: `/tmp/hf-airbnb-probe/` (one-off PR record,
not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://insideairbnb.com/` → HTTP 200 (318 618 bytes, 4 575 visible chars) | tallinn / estonia / eesti 0× in visible text | storefront only — no Tallinn surface on the front page |
| `https://insideairbnb.com/get-the-data/` → HTTP 200 (572 256 bytes, 98 241 visible chars, 1 009 links) | tallinn 0×, estonia 0×; a `/riga/` city page exists but NO `/tallinn/` page and no Estonia path under `data.insideairbnb.com`; index links `creativecommons.org/licenses/by/4.0/` + CC0 Zero | full city index audited — licence is OPEN, Tallinn coverage is MISSING (nearest covered city: Riga) |
| `https://insideairbnb.com/data-policies/` → HTTP 200 (308 651 bytes, 3 949 visible chars) | "Do not scrape data from the site" (bulk downloads + archived-data requests are the sanctioned paths); new cities "in most cases" NOT added (limited resources) | scraping is forbidden by the source itself; waiting for a Tallinn add is not a plan |

Judgment call: the check stopped at index/policy level on purpose —
no listing scraping, no Airbnb-site crawling, no Riga-dump download
(the policies ask to take only the data you need, and a foreign city's
dump would add bytes, not Tallinn information).

## Honest shape (NULL until Inside Airbnb ships Tallinn)

| Param | Dim key | Honest shape when a feed answers | Buyer-side check meanwhile |
|---|---|---|---|
| P4-003 density leg (demo) | `short_rental_density` | hex nuisance-hinnang from joined Tallinn rows only, never a Riga proxy | neighbour turnover küsi KÜ-lt; rent reality from KV üürimedianid + REL2021 grid |

Sibling P4-003 slices keep their owners (untouched): KV üüri medians /
city24 üripakkumised (portal adapters), Statamet üüri statistika
(`dims_p4_stat`), REL2021 1 km grid (`dims_p4_rel2021`). The AirDNA-style
fallback was NOT pursued — commercial feed, no verified anonymous bulk
endpoint, needs its own openness/ToS probe (see reopening checklist).

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: P4-003 is the only param naming
   this source family (parameters4.md source (4)
   "Inside-Airbnb-style Tallinn density (verify openness/ToS first,
   else AirDNA-style, label hinnang)") — one module, one test file, one
   verdict note.
2. The Riga page carries no weight for Tallinn: Riga IS covered (10
   index mentions) but carrying a foreign city's density onto a Tallinn
   hex scores the WRONG city — refused as fake precision, not kept as a
   conservative estimate.
3. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when a Tallinn dataset appears)

1. Re-run the probes above on demand (an index announcement, not a cron —
   there is no ingestion to refresh); paste fresh evidence in the reopen PR.
2. If Inside Airbnb publishes a Tallinn dataset (bulk CSV with a CC
   licence), transcribe one Tallinn month of dated rows into the cache dir
   and run them through a parser + hex join on fixtures first.
3. Graduate the dim to a hex nuisance-hinnang ONLY from joined Tallinn
   rows (coarse bands per parameters4.md, labelled hinnang); keep
   NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
