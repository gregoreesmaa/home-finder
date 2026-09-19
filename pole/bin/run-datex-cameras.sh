#!/bin/sh
# Pole wrapper: TarkTee DATEX road cameras, URL-only (hourly). Key
# from pole state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-cameras/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/datex-cameras" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_cameras.py" \
  --pull --build --cache-dir "$POLE/cache/datex-cameras" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
