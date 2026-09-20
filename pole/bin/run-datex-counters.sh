#!/bin/sh
# Pole wrapper: TarkTee DATEX traffic counters (hourly). Key from
# pole state only; repo scripts stay host-agnostic.
# HISTORY POLICY (#805, ToS re-check 2026-09-20): WINDOW-ONLY,
# no-store — this wrapper replaces the window table each pull and
# must never grow an observation log (DATEX SHORT-TERM CACHE ONLY:
# profile section 4.1, no storage/redistribution clause). A failed
# pull exits before mv (trap drops the tmp) so the previous table
# stays. See docs/realtime_history_805.md.
set -eu
POLE="$HOME/hf-pole"
export DATEX_API_KEY="$(cat "$POLE/state/datex.key")"
OUT="$POLE/built/datex-counters/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/datex-counters" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_datex_counters.py" \
  --pull --build --cache-dir "$POLE/cache/datex-counters" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
