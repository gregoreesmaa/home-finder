#!/bin/sh
# Pole wrapper: seasonal ski-track table from the operator drop.
# MANUAL WINTER STEP, no cron (off-season the cron does not run at all —
# see docs/p4_skis.md): in season (roughly Nov-Mar) the operator reads
# the human page (tallinn.ee Pirita spordikeskus + phone 600 8333) and
# drops a verified status.json at $POLE/state/skis-status.json, then
# runs this wrapper. Absent drop = honest off-season empty, never faked.
set -eu
POLE="$HOME/hf-pole"
OUT="$POLE/built/skis/table.json"
STATUS="$POLE/state/skis-status.json"
mkdir -p "$POLE/cache/skis" "$(dirname "$OUT")"
if [ -f "$STATUS" ]; then
  python3 "$POLE/harvesters/batch_skis.py" \
    --build --cache-dir "$POLE/cache/skis" \
    --status "$STATUS" --out "$OUT.tmp"
else
  python3 "$POLE/harvesters/batch_skis.py" \
    --build --cache-dir "$POLE/cache/skis" --out "$OUT.tmp"
fi
mv "$OUT.tmp" "$OUT"
