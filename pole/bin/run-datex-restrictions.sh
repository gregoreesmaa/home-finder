#!/bin/sh
# Pole wrapper: TarkTee DATEX restrictions (daily). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-restrictions/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/datex-restrictions" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_restrictions.py" \
  --pull --build --cache-dir "$POLE/cache/datex-restrictions" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
