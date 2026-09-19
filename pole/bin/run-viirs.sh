#!/bin/sh
# Pole wrapper: VIIRS brightness grid (annual rebuild, keyless GIBS).
set -eu
POLE="$HOME/hf-pole"
OUT="$POLE/built/viirs/grid.json"
mkdir -p "$POLE/cache/viirs" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_viirs.py" \
  --pull --build --cache-dir "$POLE/cache/viirs" --out "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
