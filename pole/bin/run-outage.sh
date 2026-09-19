#!/bin/sh
# Pole wrapper: Elektrilevi hetkeseis sidecar (5-min pull, keyless) +
# observed-reliability build (issue #780).
#
# Every successful pull appends one compact record to the rolling
# observation log (pole cache/outage/observations.jsonl, 90-day
# retention, harvester-side); failures leave the sidecar AND the log
# untouched (no loss on failure, corrupt never logged as data). The
# reliability table rebuilds from the surviving log either way, so a
# failed pull never loses history; a failed build leaves the previous
# table in place (atomic tmp+mv both steps). Until the first build,
# GET /v1/outage-reliability answers an honest 503.
set -eu
POLE="$HOME/hf-pole"
OUT="$POLE/built/outage/table.json"
REL="$POLE/built/outage/reliability.json"
LOG="$POLE/cache/outage/observations.jsonl"
mkdir -p "$POLE/cache/outage" "$(dirname "$OUT")"
PULL_RC=0
if python3 "$POLE/harvesters/batch_outage.py" \
  --pull --cache-dir "$POLE/cache/outage" --out "$OUT.tmp"; then
  mv "$OUT.tmp" "$OUT"
else
  PULL_RC=$?
  rm -f "$OUT.tmp"
fi
if python3 "$POLE/harvesters/batch_outage.py" \
  --build-reliability --log "$LOG" --out "$REL.tmp"; then
  mv "$REL.tmp" "$REL"
else
  rm -f "$REL.tmp"
fi
exit "$PULL_RC"
