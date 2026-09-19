# TarkTee DATEX traffic counters — keyed harvester (issue #684)

> Code: `scripts/build/batch_datex_counters.py`; tests:
> `services/scoring/tests/test_batch_datex_counters.py` (hermetic; one
> explicitly-flagged keyed probe, skipped without `DATEX_API_KEY`,
> never runs in CI).

## §0 ToS verdict (STEP ZERO — shared with #681–#686)

**SHORT-TERM CACHE ONLY — no committed sidecars, no stored tables.**
Pasted from `docs/datex_restrictions.md` §0 (the step-zero home):
the DATEX profile PDF (live text 2026-09-19) contains NO
storage/redistribution/licence clause; no separate TarkTee gateway
terms or open-data entry was locatable. The key is personal and
manually activated ("Keep your API-key secret!"); the data is live
operational state (historic unavailable, flow measured in 15 min
intervals). Built tables live on the harvest pole only
(`built/datex-counters/table.json`, honest 503 until the first keyed
pull); raw bodies are /tmp-only in tests; fixtures are hand-written
minima; the key travels only as the `X-DATEX-API-KEY` header.

## Buyer question

"Kas selle piirkonna teed on ummikutes?" — car-truth per area from
traffic counters (profile §6.1/§6.5): vehicle flow (vehicles/hour) +
average speed per counter site (UUID+direction ids), cross-check for
the TomTom flow leg.

## Quota math (pinned in code)

2 feeds × 24 pulls/day = 48 → `QUOTA_MAX_CALLS = 50` per 24 h
window; TTL 1 h; 429 = stop; transport errors never cached. Feed
slugs confirmed at the first keyed run via `--feeds`; non-200 feeds
skip honestly.

## Harvester

`batch_datex_counters.py --pull/--build --cache-dir DIR
[--feeds trafficCounterSites,traffic] [--fixture file.xml]`.
Refuses without `DATEX_API_KEY` (exit 2, both paths tested); key
never printed/written (pinned). `--build` merges site + measured
bodies by counter id and prints `{"counters", "measured",
"located"}`.

## Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-datex-counters.sh`:

```sh
#!/bin/sh
# Pole wrapper: TarkTee DATEX traffic counters (hourly). Key from
# pole state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-counters/table.json"
mkdir -p "$POLE/cache/datex-counters" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_counters.py" \
  --pull --build --cache-dir "$POLE/cache/datex-counters" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab): `32 * * * * $HOME/hf-pole/bin/run-datex-counters.sh >>$HOME/hf-pole/logs/datex-counters.log 2>&1`

Read API: `GET /v1/datex-counters` (honest 503 until the first keyed
pull builds the table).

## §7 key placement

Export `DATEX_API_KEY` in the operator shell only (pole: `state/` +
wrapper). Never commit it, never put it in repo files, never paste
it in chat. Optional `DATEX_BASE_URL` override the same way.
