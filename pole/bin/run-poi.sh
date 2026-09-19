#!/bin/bash
POLE="$HOME/hf-pole"
cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python"   batch_poi.py --cache-dir "$POLE/cache/poi" --out-dir "$POLE/built" >>"$POLE/logs/poi.log" 2>&1
