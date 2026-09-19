#!/bin/sh
# Pole wrapper: TarkTee DATEX traffic counters (hourly). Key from
# pole state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-counters/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/datex-counters" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_counters.py" \
  --pull --build --cache-dir "$POLE/cache/datex-counters" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
