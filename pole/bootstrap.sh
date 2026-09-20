#!/bin/sh
# pole/bootstrap.sh — materialize ~/hf-pole on a fresh Pi from this repo.
# Idempotent: safe to re-run (re-syncs code, keeps cache/built/state/logs).
# Usage: ./pole/bootstrap.sh [REPO_DIR] [--dry-run]
# Operator keys (state/datex.key, state/tomtom.key, state/opencellid.token)
# and static vintages (state/*.zip) are NEVER in the repo — install by hand
# (scp from the previous pole), then verify the cron lines that need them.
set -eu
REPO="${1:-$HOME/home-finder}"
DRY=""
[ "${2:-}" = "--dry-run" ] && DRY=echo
POLE="$HOME/hf-pole"

# Pole code inventory lives in pole/manifest.sh (single-sourced with
# pole/bin/pole-sync.sh, issue #806) so a new dataset fails loudly in
# tests/test_replica.py instead of silently missing on the next Pi.
# shellcheck disable=SC1091
. "$(dirname "$0")/manifest.sh"

run() { if [ -n "$DRY" ]; then echo "+ $*"; else "$@"; fi }
run mkdir -p "$POLE"/bin "$POLE"/harvesters "$POLE"/dims \
  "$POLE"/cache "$POLE"/built "$POLE"/state "$POLE"/logs
run python3 -m venv "$POLE/venv"
run "$POLE/venv/bin/pip" install -q -r "$REPO/pole/requirements.txt"
for m in $HARVESTERS; do
  run cp "$REPO/scripts/build/$m.py" "$POLE/harvesters/"
done
for m in $DIMS; do
  run cp "$REPO/services/scoring/$m.py" "$POLE/dims/"
done
run cp "$REPO/pole/api.py" "$POLE/api.py"
run cp "$REPO"/pole/bin/*.sh "$POLE/bin/"
run chmod +x "$POLE"/bin/*.sh
run crontab "$REPO/pole/crontab.txt"
if [ -z "$DRY" ]; then cat <<'EOF'
TODO operator (by hand, never committed):
  1. scp state/datex.key state/tomtom.key state/opencellid.token state/*.zip from the previous pole into ~/hf-pole/state/
  2. crontab -l (verify 20 lines); sudo reboot (verify API + tunnel after boot)
  3. curl 127.0.0.1:8001/health (expect honest 503s until first pulls land)
EOF
fi
