#!/bin/sh
# Pole wrapper: TomTom daily incidents (6-hourly keyed pull, issue
# #782). Key from pole state only; repo scripts stay host-agnostic.
# Without state/tomtom.key the harvester refuses (exit 2, nothing
# cached, nothing faked) and this wrapper exits nonzero with the
# previous cache AND the previous built table untouched (never
# writes failure as data). The harvester self-skips the pull while
# the 6 h cache is fresh and quota-caps at 2 pulls / 6 h, so the
# 6-hourly cron stays inside quota by construction. The --build
# stdout contract (#776) writes the servable table (incidents +
# fetched_at + counts) to built/tomtom-incidents/table.json (atomic
# tmp+mv); until its first keyed pull, GET /v1/incidents answers an
# honest 503 and the map shows labeled demo (never fake-live).
set -eu
POLE="$HOME/hf-pole"
export TOMTOM_API_KEY="$(cat "$POLE/state/tomtom.key")"
OUT="$POLE/built/tomtom-incidents/table.json"
trap 'rm -f "$OUT.tmp"' EXIT
mkdir -p "$POLE/cache/tomtom-incidents" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_tomtom_incidents.py" \
  --pull --build --cache-dir "$POLE/cache/tomtom-incidents" > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
