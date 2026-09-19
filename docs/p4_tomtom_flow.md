# P4 TomTom flow-segment car speeds — bus-delay calibrator (issue #671)

> Code: `services/scoring/dims_tomtom_flow.py` (keyed pull +
> calibrator); harvester: `scripts/build/batch_tomtom_flow.py`;
> tests: `services/scoring/tests/test_batch_tomtom_flow.py` (+
> hermetic `test_dims_tomtom_flow.py`; one explicitly-flagged keyed
> probe, skipped without `TOMTOM_API_KEY`, never runs in CI).

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
harvester keeps a 1 d operator cache (daily samples) and honors
response max-age in code.

## Buyer question

Independent car-speed truth to calibrate the GPS bus-delay proxy:
`currentSpeed` vs `freeFlowSpeed` at arterial probe points,
morning/evening bands. Where TomTom car speeds and bus delays
disagree is itself a signal (bus lanes working vs general jam).

## Quota math (pinned in code)

1 txn per call → ~40 probes × 2 bands = **~80 txn/day**, well inside
budget. `FLOW_MAX_CALLS = 80` per 1 d window; 429 = stop. The static
probe list ships 10 named arterials (approximate public midpoints —
public facts, ToS-clean to commit); the operator extends to ~40 via
`--probes-file`.

## Harvester

`batch_tomtom_flow.py --pull/--build --band morning|evening
--cache-dir DIR [--delay-file factors.json]`. Refuses without
`TOMTOM_API_KEY` (exit 2, both paths tested); key never
printed/written (pinned by test). `--build` prints counts +
calibration agree/disagree summary.

## Calibration note vs bus-delay corridors (acceptance)

`calibrate_vs_delay` maps each flow speed band to the delay-corridor
band scale (free ≤0.9 ratio / steady / slow / jammed — same cutoffs
by construction) and compares per probe_id:

- **agree** — car and bus see the same band (proxy validated there).
- **disagree** — the signal: bus fast + cars jammed = bus lanes
  working; bus slow + cars free = bus-side friction (stops, bunching),
  not a jam.

Fixture proof (from the test run): flow `slow` vs delay factor 1.8
(`jammed`) → `disagree: 1`; flow `free` vs factor 1.05 → `agree: 1`.
Unknowns on either side are skipped, never forced. The disagreement
flag is surfaced in docs + `--build` output, NOT scored (optional
acceptance item left for the delay-layer follow-up).

## Honest shapes (scorer dim)

| Leg | Dim key | Scored shape | NULL when |
|---|---|---|---|
| Car speed (calibrator context) | `car_speed` | probe band: free→75, steady→60, slow→45, jammed→30 | no keyed pull; probe unmeasured |

## §7 key placement

Export `TOMTOM_API_KEY` in the operator shell only. Never commit it,
never put it in repo files, never paste it in chat. No WEIGHTS splice
here (joint follow-up). 5 new files, zero shared-file edits.
