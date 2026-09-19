# TarkTee DATEX truck parking — keyed harvester (issue #686)

> Code: `scripts/build/batch_datex_truckpark.py`; tests:
> `services/scoring/tests/test_batch_datex_truckpark.py` (hermetic;
> one explicitly-flagged keyed probe, skipped without
> `DATEX_API_KEY`, never runs in CI).

## §0 ToS verdict (STEP ZERO — shared with #681–#686)

**SHORT-TERM CACHE ONLY — no committed sidecars, no stored tables.**
Pasted from `docs/datex_restrictions.md` §0 (the step-zero home):
the DATEX profile PDF (live text 2026-09-19) contains NO
storage/redistribution/licence clause; no separate TarkTee gateway
terms or open-data entry was locatable. The key is personal and
manually activated ("Keep your API-key secret!"); the data is live
operational state (historic unavailable). Built tables live on the
harvest pole only (`built/datex-truckpark/table.json`, honest 503
until the first keyed pull); raw bodies are /tmp-only in tests;
fixtures are hand-written minima; the key travels only as the
`X-DATEX-API-KEY` header.

## Buyer question

"Kas lähedal on veoautoparkla (mugav logistikule / lärmakas
kõrvalmajale)?" — static truck-parking sites (profile §6.11,
GenericPublication + parkingTablePublication extension, UUID ids):
position + name + spaces. Scores both ways: logistics-worker amenity
nearby, heavy-vehicle noise/traffic disamenity next door.

## Quota math (pinned in code)

One GET per pull, monthly cadence → `QUOTA_MAX_CALLS = 4` per 30 d
window; TTL 30 d; 429 = stop; transport errors never cached. Feed
slug confirmed at the first keyed run via `--feed`; non-200 skips
honestly.

## Harvester

`batch_datex_truckpark.py --pull/--build --cache-dir DIR
[--feed truckParking] [--fixture file.xml]`. Refuses without
`DATEX_API_KEY` (exit 2, both paths tested); key never
printed/written (pinned). `--build` prints `{"sites", "located",
"spaces"}`.

## Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-datex-truckpark.sh`:

```sh
#!/bin/sh
# Pole wrapper: TarkTee DATEX truck parking (monthly). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-truckpark/table.json"
mkdir -p "$POLE/cache/datex-truckpark" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_truckpark.py" \
  --pull --build --cache-dir "$POLE/cache/datex-truckpark" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab): `23 5 3 * * $HOME/hf-pole/bin/run-datex-truckpark.sh >>$HOME/hf-pole/logs/datex-truckpark.log 2>&1`

Read API: `GET /v1/datex-truckpark` (honest 503 until the first keyed
pull builds the table).

## §7 key placement

Export `DATEX_API_KEY` in the operator shell only (pole: `state/` +
wrapper). Never commit it, never put it in repo files, never paste
it in chat. Optional `DATEX_BASE_URL` override the same way.
