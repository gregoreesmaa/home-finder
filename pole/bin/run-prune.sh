#!/bin/bash
# Pole log trimmer (NOT a data pruner).
# Operator decision 2026-09-19: the pole NEVER deletes gathered data
# (raw caches, built tables) - it only gathers. The old gps-*.txt
# -mtime deletes (+7 d, later +365 d) are removed; cache grows
# unboundedly (~24 MB/day delay GPS, ~6 y headroom on 53 G free).
# This wrapper only trims oversized logs (>10 MB) so logging itself
# can never fill the disk; logs are operational, not data.
POLE="$HOME/hf-pole"
for l in "$POLE"/logs/*.log; do
  if [ "$(stat -f%z "$l" 2>/dev/null || stat -c%s "$l")" -gt 10485760 ]; then
    tail -c 8388608 "$l" > "$l.tmp" && mv "$l.tmp" "$l"
  fi
done
