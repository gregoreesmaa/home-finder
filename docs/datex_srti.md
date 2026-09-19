# TarkTee DATEX SRTI safety bundle — keyed harvester (issue #682)

> Code: `scripts/build/batch_datex_srti.py`; tests:
> `services/scoring/tests/test_batch_datex_srti.py` (hermetic; one
> explicitly-flagged keyed probe, skipped without `DATEX_API_KEY`,
> never runs in CI).

## §0 ToS verdict (STEP ZERO — shared with #681–#686)

**SHORT-TERM CACHE ONLY — no committed sidecars, no stored tables.**
Pasted from `docs/datex_restrictions.md` §0 (the step-zero home):
the DATEX profile PDF (live text 2026-09-19,
`https://tarktee.ee/assets/datex/DATEX_II_Estonian_profile_Tark_Tee.pdf`)
contains NO storage/redistribution/licence clause; no separate
TarkTee gateway terms or open-data entry was locatable. The key is
personal and manually activated ("Keep your API-key secret!"); the
data is live operational state (§4.1: historic data unavailable).
Built tables live on the harvest pole only
(`built/datex-srti/table.json`, honest 503 until the first keyed
pull); raw bodies are /tmp-only in tests; fixtures are hand-written
minima; the key travels only as the `X-DATEX-API-KEY` header.

## Buyer question

"Kas selle piirkonna teedel on praegu ohtlik?" — safety bundle per
area: libedus/jää (temporarySlipperyRoad), loomad/takistused,
kaitsmata avariikohad, lühiajalised teetööd, halb nähtavus,
blokeeringud, erakorraline ilm (profile §6.14 seven classes).
Seasonal feeds stay honestly-empty off-season (temporarySlipperyRoad
verified 200-empty 2026-09-18) — never faked.

## Quota math (pinned in code)

7 feeds × 4 pulls/day = 28/day in practice (cron-bounded) →
`QUOTA_MAX_CALLS = 32` per TTL window (6 h) as backstop (code counts
keyed calls per `TTL_S` window; up to 4 × 32 = 128/day theoretical);
429 = stop; transport errors never cached. Only
`temporarySlipperyRoad` is live-verified — `--feeds` confirms the
rest at the first keyed run; non-200 feeds skip honestly.

## Harvester

`batch_datex_srti.py --pull/--build --cache-dir DIR
[--feeds temporarySlipperyRoad,...] [--fixture file.json]`. Refuses
without `DATEX_API_KEY` (exit 2, both paths tested); key never
printed/written (pinned). `--build` prints `{"total", "by_kind"}`.

## Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-datex-srti.sh`:

```sh
#!/bin/sh
# Pole wrapper: TarkTee DATEX SRTI bundle (every 6 h). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-srti/table.json"
mkdir -p "$POLE/cache/datex-srti" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_srti.py" \
  --pull --build --cache-dir "$POLE/cache/datex-srti" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab): `47 */6 * * * $HOME/hf-pole/bin/run-datex-srti.sh >>$HOME/hf-pole/logs/datex-srti.log 2>&1`

Read API: `GET /v1/datex-srti` (honest 503 until the first keyed
pull builds the table).

## §7 key placement

Export `DATEX_API_KEY` in the operator shell only (pole: `state/` +
wrapper). Never commit it, never put it in repo files, never paste
it in chat. Optional `DATEX_BASE_URL` override the same way.
