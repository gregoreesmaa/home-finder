# P4 TomTom car-commute matrix — keyed verdict + short-lived-cache design (issue #669)

> Verdict date: 2026-09-19 (agreement text fetched live, no key used).
> Code: `services/scoring/dims_tomtom_matrix.py` (keyed pull + scorer
> leg); harvester: `scripts/build/batch_tomtom_matrix.py`; tests:
> `services/scoring/tests/test_batch_tomtom_matrix.py` (+ hermetic
> `test_dims_tomtom_matrix.py`; one explicitly-flagged keyed probe,
> skipped without `TOMTOM_API_KEY`, never runs in CI).

## §0 ToS verdict (STEP ZERO — gates ALL TomTom work, #669–#675)

Source: TomTom Portal Terms & Conditions (live text, fetched
2026-09-19 via docs-tomtom legal page),
`https://docs.tomtom.com/legal/terms-and-conditions/`.

**Verdict: SHORT-TERM CACHE ONLY — no committed sidecars, no stored
tables.** Verbatim clause 11.4:

> "The caching or storing of any Results shall be prohibited except
> that you may cache Results delivered by the Licensed Products
> provided that: 11.4.1. such Results may only be cached in clients
> where the control headers are present in the Result; 11.4.2. such
> Results must not be cached in clients for longer than the maximum
> age period indicated in such cache control headers; 11.4.3. where
> supported in the Permitted Solution, client caches should be
> invalidated when a content update has occurred. Nothing under
> Clause 11.4 entitles any form of caching for the purpose of scaling
> results to serve multiple clients or users."

Supporting: "Results" is defined to include *"geocodes and reverse
geocodes, map data tiles and route information"* — i.e. every one of
the seven harvesters. Clauses 11.6.1/11.6.2 additionally forbid
derivative works and secondary/derived databases.

Design consequence (all seven PRs state this): every TomTom
harvester uses a **short-lived-cache design** — a git-ignored
operator cache dir, TTL-capped (matrix 2 d), response cache-control
`max-age` honored in code and never exceeded
(`fetch_matrix` backdates freshness when max-age < TTL). The repo
holds code + fixtures only. Production legs stay NULL until a keyed
pull fills the local cache.

Judgment call (for the reviewer): the agreement's caching rule keys
off response control headers; TomTom routing responses do not always
carry them, so the harvester defaults to a conservative 2 d TTL
(3×/week refresh cadence) and documents it here rather than hiding
the gap. Re-check the live clause before the first keyed pull.

## Buyer question

"Autoga tööle: N min (+M ummikulisand)" — per-area rush vs off-peak
drive times to the 5 job hubs (Kesklinn, Ülemiste, Mustamäe, Sadam,
Lennujaam). First true car-commute score; bus-delay covers transit
riders only.

## Quota math (pinned in code)

196 GTFS shape-area centroids × 5 hubs, sync cap 200 cells/call →
one call per hub × band = 10 calls per full refresh. One band ≈ 980
txn (issue-body number); full refresh ≈ 1960 txn, 3×/week ≈ 840
txn/day average inside the 2500/day free budget.
`MATRIX_MAX_CALLS = 10` per 2 d window; 429 = stop.

## Harvester

`batch_tomtom_matrix.py --pull/--build --areas-file areas.json
--cache-dir DIR` (areas file is operator-supplied, never committed).
Refuses without `TOMTOM_API_KEY` (exit 2, both paths tested); key
never printed/written (pinned by test). `--build` may read
`--fixture` for offline table proofs.

## Honest shapes (scorer dim, never a raster)

| Leg | Dim key | Scored shape | NULL when |
|---|---|---|---|
| Car commute | `car_commute` | best-hub rush: ≤20 min → 75, ≤35 → 65, ≤50 → 45, else 30; reason always carries `+M ummikulisand` | no keyed pull (buyer check); area unmeasured (mõõtmata pole halb) |

Extra probe from the issue body (`travelMode=bus` in the same
spike): NOT done here — no key in this change; flagged as follow-up
for the first keyed operator run.

## §7 key placement

Export `TOMTOM_API_KEY` in the operator shell only. Never commit it,
never put it in repo files, never paste it in chat. No WEIGHTS
splice here (joint follow-up). 5 new files, zero shared-file edits.
