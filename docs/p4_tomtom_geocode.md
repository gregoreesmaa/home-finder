# P4 TomTom geocode repair — coord-less listings join scoring (issue #675)

> Code: `services/scoring/dims_tomtom_geocode.py` (keyed Structured
> Geocode + address-hash cache + repair); harvester:
> `scripts/build/batch_tomtom_geocode.py`; tests:
> `services/scoring/tests/test_batch_tomtom_geocode.py` (+ hermetic
> `test_dims_tomtom_geocode.py`; one explicitly-flagged keyed probe,
> skipped without `TOMTOM_API_KEY`, never runs in CI).

## §0 ToS verdict (STEP ZERO from #669 — applies verbatim, plus one extra)

TomTom Portal Terms & Conditions, clause 11.4 (live text 2026-09-19,
`https://docs.tomtom.com/legal/terms-and-conditions/`):

> "The caching or storing of any Results shall be prohibited except
> that you may cache Results delivered by the Licensed Products
> provided that: ... such Results must not be cached in clients for
> longer than the maximum age period indicated in such cache control
> headers; ... Nothing under Clause 11.4 entitles any form of caching
> for the purpose of scaling results to serve multiple clients or
> users."

**Verdict: SHORT-TERM CACHE ONLY — no committed sidecars, no stored
tables.** Full verdict in `docs/p4_tomtom_matrix.md` §0.

Extra for this issue: the agreement NAMES "geocodes and reverse
geocodes" as Results, so the address-hash cache is TTL-BOUNDED (30 d,
`GEOCODE_TTL_S`), never permanent: zero re-calls within TTL (pinned
by urlopen call counts), re-verify after. Response max-age is honored
in code.

## Buyer question

Coord-less listings drop out of area scoring — Structured Geocode
(`countryCode=EE`, light street/municipality split) repairs them so
they join. Trickle volume: only coord-less listings cost calls
(`GEOCODE_MAX_CALLS = 100` per 30 d window; 429 = stop).

## Address-hash cache (acceptance: zero re-calls)

`sha256(normalize(address))` — spelling variants collapse to one
hash, so a known address is never re-geocoded. EMPTY/unresolvable
results are NEVER cached (they may resolve later); transport errors
never cached. Test proof: 3 coord-less (2 sharing one address) cost
exactly 2 calls; a second run costs 0 for resolved ones.

## Before/after proof (acceptance)

From the test run (`test_repair_before_after_counts_and_zero_recalls`):

- `coord_less_before: 3` → `repaired: 2` → `coord_less_after: 1`
- the unresolvable listing is KEPT with NULL coords and logged
  (`qa: geokodeerimata aadress, kuulutus alles`) — surfaced in QA,
  never dropped silently.

## Harvester

`batch_tomtom_geocode.py --repair/--report --listings-file F
--cache-dir DIR [--out-file O]`. Refuses without `TOMTOM_API_KEY`
(exit 2, both paths tested); key never printed/written (pinned by
test). `--report` counts without repairing (no requests, quota
untouched).

## §7 key placement

Export `TOMTOM_API_KEY` in the operator shell only. Never commit it,
never put it in repo files, never paste it in chat. No WEIGHTS splice
here (joint follow-up). 5 new files, zero shared-file edits.
