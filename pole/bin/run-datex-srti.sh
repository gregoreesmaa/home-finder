#!/bin/sh
# Pole wrapper: TarkTee DATEX SRTI bundle (every 6 h). Key from pole
# state only; repo scripts stay host-agnostic.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-srti/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/datex-srti" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_srti.py" \
  --pull --build --cache-dir "$POLE/cache/datex-srti" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
