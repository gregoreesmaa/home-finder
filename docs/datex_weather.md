# TarkTee DATEX road weather — keyed harvester (issue #683)

> Code: `scripts/build/batch_datex_weather.py`; tests:
> `services/scoring/tests/test_batch_datex_weather.py` (hermetic; one
> explicitly-flagged keyed probe, skipped without `DATEX_API_KEY`,
> never runs in CI).

## §0 ToS verdict (STEP ZERO — shared with #681–#686)

**SHORT-TERM CACHE ONLY — no committed sidecars, no stored tables.**
Pasted from `docs/datex_restrictions.md` §0 (the step-zero home):
the DATEX profile PDF (live text 2026-09-19) contains NO
storage/redistribution/licence clause; no separate TarkTee gateway
terms or open-data entry was locatable. The key is personal and
manually activated ("Keep your API-key secret!"); the data is live
operational state (historic unavailable, stations refresh every
10 min). Built tables live on the harvest pole only
(`built/datex-weather/table.json`, honest 503 until the first keyed
pull); raw bodies are /tmp-only in tests; fixtures are hand-written
minima; the key travels only as the `X-DATEX-API-KEY` header.

## Buyer question

"Kas see piirkond on talvel libe / lumine?" — winter severity per
area from road weather stations (profile §6.1/§6.3–§6.4):
precipitation, humidity, wind, visibility, air/dew/road-surface
temperatures, road status (dry/ice/slipperyRoad/slush/snow/wet) plus
3.6 friction/snow/ice-layer/de-icing where measured.

## Quota math (pinned in code)

2 feeds × 24 pulls/day = 48/day in practice (cron-bounded) →
`QUOTA_MAX_CALLS = 50` per TTL window (1 h) as backstop (code counts
keyed calls per `TTL_S` window; up to 24 × 50 = 1200/day theoretical);
429 = stop; transport errors never cached. Feed
slugs confirmed at the first keyed run via `--feeds`; non-200 feeds
skip honestly.

## Harvester

`batch_datex_weather.py --pull/--build --cache-dir DIR
[--feeds weatherStations,weather] [--fixture file.xml]`. Refuses
without `DATEX_API_KEY` (exit 2, both paths tested); key never
printed/written (pinned). `--build` merges station + measured bodies
by station id and prints `{"stations", "measured", "located"}`.

## Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-datex-weather.sh`:

```sh
#!/bin/sh
# Pole wrapper: TarkTee DATEX road weather (hourly). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-weather/table.json"
mkdir -p "$POLE/cache/datex-weather" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_weather.py" \
  --pull --build --cache-dir "$POLE/cache/datex-weather" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab): `12 * * * * $HOME/hf-pole/bin/run-datex-weather.sh >>$HOME/hf-pole/logs/datex-weather.log 2>&1`

Read API: `GET /v1/datex-weather` (honest 503 until the first keyed
pull builds the table).

## §7 key placement

Export `DATEX_API_KEY` in the operator shell only (pole: `state/` +
wrapper). Never commit it, never put it in repo files, never paste
it in chat. Optional `DATEX_BASE_URL` override the same way.
