#!/bin/sh
# Pole wrapper: TomTom commute sheds (weekly keyed pull, issues
# #787 + #782). Key from pole state only; repo scripts stay
# host-agnostic. Without state/tomtom.key the harvester refuses
# (exit 2, nothing cached, nothing faked) and this wrapper exits
# nonzero with the previous cache AND the previous built table
# untouched (never writes failure as data). The --build stdout
# contract (#776) writes the servable table (polygons + counts) to
# built/tomtom-sheds/table.json (atomic tmp+mv); until its first
# keyed pull, GET /v1/sheds answers an honest 503 and
# /api/layers/sheds/areas stays honestly-503 with the map painting
# slate "mõõtmata".
set -eu
POLE="$HOME/hf-pole"
export TOMTOM_API_KEY="$(cat "$POLE/state/tomtom.key")"
OUT="$POLE/built/tomtom-sheds/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/tomtom-sheds" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_tomtom_isochrones.py" \
  --pull --build --cache-dir "$POLE/cache/tomtom-sheds" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
