#!/bin/bash
# Watchdog (every 5 min): restart pole API if deployed but dead.
POLE="$HOME/hf-pole"
if [ -f "$POLE/api.py" ]; then
  if [ -f "$POLE/state/api.pid" ] && kill -0 "$(cat $POLE/state/api.pid)" 2>/dev/null; then
    exit 0
  fi
  echo "$(date -u +%FT%TZ) guard: api dead, restarting" >>"$POLE/logs/api.log"
  nohup "$POLE/venv/bin/python" -m uvicorn api:app --app-dir "$POLE"     --host 0.0.0.0 --port 8001 >>"$POLE/logs/api.log" 2>&1 &
  echo $! > "$POLE/state/api.pid"
fi
