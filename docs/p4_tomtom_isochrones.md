# P4 TomTom commute-shed isochrones — keyed harvester + overlay (issue #670)

> Code: `services/scoring/dims_tomtom_isochrones.py` (keyed pull +
> scorer leg); harvester: `scripts/build/batch_tomtom_isochrones.py`;
> overlay: `apps/web/lib/layers_p4_tomtom_sheds.ts` (+ vitest);
> tests: `services/scoring/tests/test_batch_tomtom_isochrones.py` (+
> hermetic `test_dims_tomtom_isochrones.py`; one explicitly-flagged
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
tables.** Full verdict in `docs/p4_tomtom_matrix.md` §0. This
harvester keeps a 7 d operator cache (weekly refresh) and honors
response max-age in code.

## Buyer question

"Mitu töökohta jääb 30 min autosõidu kaugusele" — 15/30-min
peak/off-peak reachable-range polygons from the 5 job hubs (same hubs
as #669), `traffic=true`. Per-area jobs-within-30-min score feeds
ranking; shed polygons render as overlay.

## Quota math (pinned in code)

5 hubs × 2 budgets (900/1800 s) × 2 bands = **20 txn per refresh,
weekly**. `SHED_MAX_CALLS = 20` per 7 d window; 429 = stop.

## Harvester

`batch_tomtom_isochrones.py --pull/--build --cache-dir DIR`.
Refuses without `TOMTOM_API_KEY` (exit 2, both paths tested); key
never printed/written (pinned by test).

## Overlay (standalone — judgment call for the reviewer)

`layers_p4_tomtom_sheds.ts` ships 4 layer defs (15/30 min ×
peak/off-peak), Estonian short-cache-never-live labels
("mõõtmik lühiajalisest puhvrist, mitte reaalajas"), slate
unmeasured paint, and a ray-casting `shedCoversPoint` (parity with
the scorer's `point_in_ring`, pinned by both test suites). It is
deliberately NOT wired into the shared `LayerId` union / overlays
registry: wiring needs a stored snapshot and the ToS verdict forbids
storing one, so the overlay consumes the operator cache at runtime.
Shared-file wiring is a follow-up once a live keyed cache exists.

## Honest shapes (scorer dim)

| Leg | Dim key | Scored shape | NULL when |
|---|---|---|---|
| Jobs within 30 min | `jobs_within_30min` | rush 30-min sheds covering listing: 5→80, 3–4→65, 1–2→50, 0→35 (far, not bad) | no keyed pull; unmeasured |

## §7 key placement

Export `TOMTOM_API_KEY` in the operator shell only. Never commit it,
never put it in repo files, never paste it in chat. No WEIGHTS splice
here (joint follow-up). 6 new files, zero shared-file edits.
