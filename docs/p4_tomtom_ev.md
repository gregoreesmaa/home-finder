# P4 TomTom EV-charging POI layer — static only (issue #673)

> Code: `services/scoring/dims_tomtom_evpois.py` (keyed pull +
> scorer leg); harvester: `scripts/build/batch_tomtom_evpois.py`;
> tests: `services/scoring/tests/test_batch_tomtom_evpois.py` (+
> hermetic `test_dims_tomtom_evpois.py`; one explicitly-flagged
> keyed probe, skipped without `TOMTOM_API_KEY`, never runs in CI).

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

Category-ID judgment call (for the reviewer): `EV_CATEGORY = 7309`
is the widely-used TomTom Search categorySet value for EV charging
stations, but the category docs page is login-walled, so the value
is SPIKE-UNVERIFIED (`EV_CATEGORY_VERIFIED = False`, pinned by
test). The first keyed operator run must resolve it via one
POI-Categories call and correct it if wrong; the harvester warns on
every run until then and accepts `--category` to override.

## Buyer question (EV-driving segment)

"Kus on lähim laadija" — EV-station POIs + connector info, tiled
over Tallinn (6 district tiles, 4 km radius), monthly. Amenity score
+ map points.

## Static-only rule (load-bearing)

Real-time per-plug availability is an enterprise product — the layer
ingests locations + connector types, NEVER availability. Every
user-facing string carries "staatiline ... (saadavus teadmata, mitte
reaalajas)"; a live-looking label is a bug (pinned by test).

## Quota math (pinned in code)

**~20 txn per monthly refresh** (tiled). `EV_MAX_CALLS = 20` per 30 d
window; 429 = stop.

## Harvester

`batch_tomtom_evpois.py --pull/--build --cache-dir DIR [--category
N]`. Refuses without `TOMTOM_API_KEY` (exit 2, both paths tested);
key never printed/written (pinned by test). `--build` dedupes POIs
across tiles and prints counts.

## Honest shapes (scorer dim)

| Leg | Dim key | Scored shape | NULL when |
|---|---|---|---|
| EV amenity | `ev_amenity` | nearest static charger ≤2 km: ≤500 m→75, ≤1 km→60, ≤2 km→50, none→35 (no charger ≠ bad) | no keyed pull; unmeasured |

## §7 key placement

Export `TOMTOM_API_KEY` in the operator shell only. Never commit it,
never put it in repo files, never paste it in chat. No WEIGHTS splice
here (joint follow-up). 5 new files, zero shared-file edits.
