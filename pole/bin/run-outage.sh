#!/bin/sh
# Pole wrapper: Elektrilevi hetkeseis sidecar (5-min pull, keyless).
set -eu
POLE="$HOME/hf-pole"
OUT="$POLE/built/outage/table.json"
mkdir -p "$POLE/cache/outage" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_outage.py" \
  --pull --cache-dir "$POLE/cache/outage" --out "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
