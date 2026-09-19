#!/bin/sh
# Pole wrapper: TarkTee DATEX truck parking (monthly static). Key from
# pole state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-truckpark/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/datex-truckpark" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_truckpark.py" \
  --pull --build --cache-dir "$POLE/cache/datex-truckpark" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
