#!/bin/sh
# pole/bin/wrap-run.sh — cron-level exit recorder (issue #806).
#
# Usage: wrap-run.sh <job> <command> [args...]
# Runs the command with stdout/stderr untouched (so crontab `>>log 2>&1`
# redirections keep working), records {"job","rc","at"} atomically to
# $POLE/state/wrapper-status/<job>.json for the /v1/errors endpoint,
# and exits with the command's own code.
#
# The recorder never fails the job: recording errors are swallowed and
# the command's exit code is always preserved. Job names are restricted
# to [a-z0-9-] so the status filename cannot escape its directory.
set -u
POLE="${POLE:-$HOME/hf-pole}"
JOB="${1:-unknown}"
shift || true
case "$JOB" in
  *[!a-z0-9-]* | "") JOB="unknown" ;;
esac
"$@"
RC=$?
STAMP="$(date -u +%FT%TZ 2>/dev/null || echo unknown)"
if mkdir -p "$POLE/state/wrapper-status" 2>/dev/null; then
  printf '{"job":"%s","rc":%d,"at":"%s"}\n' "$JOB" "$RC" "$STAMP" \
    >"$POLE/state/wrapper-status/$JOB.json.tmp" 2>/dev/null && \
    mv "$POLE/state/wrapper-status/$JOB.json.tmp" \
      "$POLE/state/wrapper-status/$JOB.json" 2>/dev/null || true
fi
exit "$RC"
