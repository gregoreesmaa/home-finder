# P4 TomTom parking / P&R POI layer — static only (issue #674)

> Code: `services/scoring/dims_tomtom_parking.py` (keyed pull +
> scorer leg); harvester: `scripts/build/batch_tomtom_parking.py`
> (sibling of the #673 EV script); tests:
> `services/scoring/tests/test_batch_tomtom_parking.py` (+ hermetic
> `test_dims_tomtom_parking.py`; one explicitly-flagged keyed probe,
> skipped without `TOMTOM_API_KEY`, never runs in CI).

## §0 ToS verdict (STEP ZERO from #669 — applies verbatim)

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
POI lists.** Full verdict in `docs/p4_tomtom_matrix.md` §0. This
harvester keeps a 30 d operator cache (monthly refresh) and honors
response max-age in code.

Sibling-script judgment call (for the reviewer): the issue allows
sharing the EV script's `--category` flag "or sibling script". The
seven branches run parallel (one issue per worktree/PR from main),
so literal flag-sharing would couple them — this ships
`batch_tomtom_parking.py` as a sibling with identical plumbing by
construction (same quota/TTL/refusal/max-age shape, its own
`--category` default). Convergence to one script is a follow-up once
both land.

Category-ID judgment call: `PARKING_CATEGORY = 7311` is the
widely-used TomTom Search categorySet value for parking, but the
category docs page is login-walled, so the value is SPIKE-UNVERIFIED
(`PARKING_CATEGORY_VERIFIED = False`, pinned by test). The first
keyed operator run must resolve it via one POI-Categories call; the
harvester warns every run until then and accepts `--category`.

## Buyer question (car-commute segment)

"Kuhu auto jätta enne viimast ühistranspordilõiku" — parking /
park-and-ride POIs, tiled over Tallinn (5 district tiles, 4 km
radius), monthly. Amenity score; pairs with the car-commute layers
(where to leave the car before the last PT leg).

## Static-only rule (load-bearing)

Real-time occupancy is out of reach — the layer ingests locations +
P&R name markers, NEVER occupancy. Every user-facing string carries
"staatiline ... (vabade kohtade arv teadmata, mitte reaalajas)"; a
live-looking label is a bug (pinned by test).

## Quota math (pinned in code)

**~10 txn per monthly refresh** (tiled). `PARKING_MAX_CALLS = 10`
per 30 d window; 429 = stop.

## Harvester

`batch_tomtom_parking.py --pull/--build --cache-dir DIR [--category
N]`. Refuses without `TOMTOM_API_KEY` (exit 2, both paths tested);
key never printed/written (pinned by test). `--build` dedupes POIs
across tiles and prints counts (incl. `park_and_ride` sub-count).

## Honest shapes (scorer dim)

| Leg | Dim key | Scored shape | NULL when |
|---|---|---|---|
| Parking amenity | `parking_amenity` | nearest static parking ≤1 km: ≤300 m→75, ≤600 m→65, ≤1 km→55, none→40; P&R ≤2 km adds a named car+PT note (scale unchanged) | no keyed pull; unmeasured |

## §7 key placement

Export `TOMTOM_API_KEY` in the operator shell only. Never commit it,
never put it in repo files, never paste it in chat. No WEIGHTS splice
here (joint follow-up). 5 new files, zero shared-file edits.
