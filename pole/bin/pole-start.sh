#!/bin/bash
# Boot entry (@reboot): start pole API if deployed, warm one delay pull.
# Safe to re-run (pidfile guard makes repeats no-ops).
POLE="$HOME/hf-pole"
mkdir -p "$POLE"/{cache,built,state,logs}
if [ -f "$POLE/api.py" ]; then
  if [ -f "$POLE/state/api.pid" ] && kill -0 "$(cat $POLE/state/api.pid)" 2>/dev/null; then
    :
  else
    nohup "$POLE/venv/bin/python" -m uvicorn api:app --app-dir "$POLE"       --host 0.0.0.0 --port 8001 >>"$POLE/logs/api.log" 2>&1 &
    echo $! > "$POLE/state/api.pid"
  fi
fi
cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python"   batch_delay_sampler.py --pull --cache-dir "$POLE/cache/delay" >>"$POLE/logs/delay-pull.log" 2>&1
