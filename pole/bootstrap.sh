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

# Exact pole code inventory (audited 2026-09-19, issue #767). Explicit so a
# new dataset fails loudly here instead of silently missing on the next Pi.
HARVESTERS="batch_datex_cameras batch_datex_counters batch_datex_restrictions
  batch_datex_srti batch_datex_truckpark batch_datex_weather
  batch_delay_sampler batch_fixit batch_medre batch_medre_ads
  batch_mobile_import batch_outage batch_poi batch_tomtom_evpois
  batch_tomtom_flow batch_tomtom_geocode batch_tomtom_incidents
  batch_tomtom_isochrones batch_tomtom_matrix batch_tomtom_parking
  batch_viirs"
DIMS="dims_p4_fixit dims_p4_gtfsstops dims_p4_medre dims_p4_poi
  dims_p4_typical_delay dims_tomtom_evpois dims_tomtom_flow
  dims_tomtom_geocode dims_tomtom_incidents dims_tomtom_isochrones
  dims_tomtom_matrix dims_tomtom_parking"

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
  2. crontab -l (verify 17 lines); sudo reboot (verify API + tunnel after boot)
  3. curl 127.0.0.1:8001/health (expect honest 503s until first pulls land)
EOF
fi
