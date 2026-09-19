#!/bin/bash
POLE="$HOME/hf-pole"
cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python"   batch_delay_sampler.py --pull --cache-dir "$POLE/cache/delay" >>"$POLE/logs/delay-pull.log" 2>&1
