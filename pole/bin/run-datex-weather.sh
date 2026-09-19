#!/bin/sh
# Pole wrapper: TarkTee DATEX road weather (hourly). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-weather/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/datex-weather" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_weather.py" \
  --pull --build --cache-dir "$POLE/cache/datex-weather" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
