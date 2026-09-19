#!/bin/bash
# Delay corridor table rebuild.
# flock: one build outlasts the hourly slot on the Pi (multi-hour over a
# multi-day cache), so overlapping invocations exit quietly (logged)
# instead of piling up and starving the machine (seen 2026-09-19: 5
# overlapping builds, load 5+, ssh refused).
# Raw retention: NEVER delete per operator decision 2026-09-19 (was yearly, was 7 d). The pole only gathers; cache grows unboundedly.
# NOTE: build cost scales with cache size; if builds stop completing
# inside 24 h, the sampler needs a --since-days window (tracked issue).
POLE="$HOME/hf-pole"
LOG="$POLE/logs/delay-build.log"
(
  /usr/bin/flock -n 9 || {
    echo "$(date -u +%FT%TZ) build skipped (previous still running)" >>"$LOG"
    exit 0
  }
  cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python" \
    batch_delay_sampler.py --build --cache-dir "$POLE/cache/delay" --snap "$POLE/built" \
    --vintage "$POLE/state/tallinn-gtfs-2026-09-11.zip" >>"$LOG" 2>&1
) 9>"$POLE/state/delay-build.lock"
