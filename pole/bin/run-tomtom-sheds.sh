#!/bin/sh
# Pole wrapper: TomTom commute sheds (weekly keyed pull, issue #787).
# Key from pole state only; repo scripts stay host-agnostic. Without
# state/tomtom.key the harvester refuses (exit 2, nothing cached,
# nothing faked) and this wrapper exits nonzero with the previous
# cache untouched (never writes failure as data). Until the first
# keyed pull lands, /api/layers/sheds/areas stays honestly-503 and
# the map paints slate "mõõtmata".
set -eu
POLE="$HOME/hf-pole"
export TOMTOM_API_KEY="$(cat "$POLE/state/tomtom.key")"
mkdir -p "$POLE/cache/tomtom-sheds"
python3 "$POLE/harvesters/batch_tomtom_isochrones.py" \
  --pull --build --cache-dir "$POLE/cache/tomtom-sheds"
