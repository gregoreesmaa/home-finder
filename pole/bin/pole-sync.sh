#!/bin/sh
# pole/bin/pole-sync.sh — hourly auto-sync (issue #806).
#
# Lands the latest green-main on the pole without operator action:
# fetches origin, picks the deploy target (the `pole-release` tag when it
# exists, else origin/main), and — only when the target SHA differs from
# state/deployed-sha.txt — re-runs the bootstrap sync subset, restarts the
# API, and records the deployed SHA. Cadence: hourly cron, so worst-case
# lag behind green-main is ~1 h (the Mac watcher files an issue past 2 h).
#
# Touches CODE ONLY (harvesters/, dims/, api.py, bin/, crontab, venv only
# when pole/requirements.txt changed). NEVER touches cache/built/logs or
# operator keys in state/ (only sync bookkeeping files:
# state/deployed-sha.txt, state/deployed-at.txt, state/sync-status.json
# and code backups under state/code-backup/, newest 3 kept).
#
# Usage: pole-sync.sh [REPO_DIR] [--dry-run|--check]
#   (no flag)  perform the sync; nonzero exit on failure (cron logs it,
#              the watcher surfaces it as "pole sync failing").
#   --dry-run  print what would happen, change nothing.
#   --check    print target vs deployed SHAs, change nothing (exit 0 when
#              in sync, 1 when behind — for humans, not alerting).
set -eu
REPO="${1:-$HOME/home-finder}"
POLE="${POLE:-$HOME/hf-pole}"
MODE="${2:-}"
DRY=""
[ "$MODE" = "--dry-run" ] && DRY=echo
TAG="pole-release"

run() { if [ -n "$DRY" ]; then echo "+ $*"; else "$@"; fi }

if ! git -C "$REPO" fetch -q --tags origin 2>/dev/null; then
  echo "pole-sync: fetch failed (transport down, not data — retry next hour)" >&2
  exit 3
fi
if git -C "$REPO" rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
  TARGET_REF="refs/tags/$TAG"
else
  TARGET_REF="refs/remotes/origin/main"
fi
TARGET_SHA="$(git -C "$REPO" rev-parse --verify "$TARGET_REF")"
DEPLOYED_SHA=""
[ -f "$POLE/state/deployed-sha.txt" ] && DEPLOYED_SHA="$(cat "$POLE/state/deployed-sha.txt")"

if [ "$MODE" = "--check" ]; then
  echo "target:   $TARGET_REF $TARGET_SHA"
  echo "deployed: ${DEPLOYED_SHA:-none}"
  [ "$TARGET_SHA" = "$DEPLOYED_SHA" ] && exit 0 || exit 1
fi

if [ "$TARGET_SHA" = "$DEPLOYED_SHA" ]; then
  echo "pole-sync: in sync ($TARGET_SHA)"
  exit 0
fi

if [ -n "$DRY" ]; then
  echo "pole-sync: would deploy $TARGET_REF $TARGET_SHA (deployed: ${DEPLOYED_SHA:-none})"
  echo "+ git -C $REPO checkout -q $TARGET_SHA"
  echo "+ backup pole code to $POLE/state/code-backup/"
  echo "+ re-sync harvesters/dims/api.py/bin + crontab (data dirs untouched)"
  echo "+ restart API + write $POLE/state/deployed-sha.txt"
  exit 0
fi

STAMP="$(date -u +%FT%TZ | tr ':+' '--')"
BACKUP_DIR="$POLE/state/code-backup"
mkdir -p "$BACKUP_DIR"
# Code backup BEFORE overwriting: previous code restorable by hand
# (data dirs are never in the tarball — code only).
if [ -d "$POLE/harvesters" ]; then
  tar -czf "$BACKUP_DIR/sync-$STAMP-$(printf '%s' "$TARGET_SHA" | cut -c1-12).tgz" \
    -C "$POLE" harvesters dims api.py bin 2>/dev/null || true
  ls -t "$BACKUP_DIR"/sync-*.tgz 2>/dev/null | tail -n +4 | \
    while IFS= read -r old; do rm -f "$old"; done
fi

git -C "$REPO" checkout -q "$TARGET_SHA"
# shellcheck disable=SC1091
. "$REPO/pole/manifest.sh"
for m in $HARVESTERS; do
  cp "$REPO/scripts/build/$m.py" "$POLE/harvesters/"
done
for m in $DIMS; do
  cp "$REPO/services/scoring/$m.py" "$POLE/dims/"
done
cp "$REPO/pole/api.py" "$POLE/api.py"
cp "$REPO"/pole/bin/*.sh "$POLE/bin/"
chmod +x "$POLE"/bin/*.sh
crontab "$REPO/pole/crontab.txt"
# venv rebuild only when the API runtime pin changed (hourly pip hits
# the index otherwise); the deployed pin copy is bookkeeping, not a key.
if [ ! -f "$POLE/state/requirements.txt" ] || \
   ! cmp -s "$REPO/pole/requirements.txt" "$POLE/state/requirements.txt"; then
  "$POLE/venv/bin/pip" install -q -r "$REPO/pole/requirements.txt"
  cp "$REPO/pole/requirements.txt" "$POLE/state/requirements.txt"
fi
# Restart the API on the new code (same start line as pole-start.sh so
# the guard pidfile contract holds), then record the deployment.
if [ -f "$POLE/state/api.pid" ]; then
  kill "$(cat "$POLE/state/api.pid")" 2>/dev/null || true
  sleep 2
fi
mkdir -p "$POLE/logs"
nohup "$POLE/venv/bin/python" -m uvicorn api:app --app-dir "$POLE" \
  --host 0.0.0.0 --port 8001 >>"$POLE/logs/api.log" 2>&1 &
echo $! > "$POLE/state/api.pid"
printf '%s\n' "$TARGET_SHA" > "$POLE/state/deployed-sha.txt"
date -u +%FT%TZ > "$POLE/state/deployed-at.txt"
printf '{"rc":0,"at":"%s","sha":"%s","ref":"%s"}\n' \
  "$(cat "$POLE/state/deployed-at.txt")" "$TARGET_SHA" "$TARGET_REF" \
  > "$POLE/state/sync-status.json"
echo "pole-sync: deployed $TARGET_REF $TARGET_SHA"
