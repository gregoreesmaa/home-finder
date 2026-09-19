#!/bin/bash
POLE="$HOME/hf-pole"
cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python"   batch_fixit.py --cache-dir "$POLE/cache/fixit" --out-dir "$POLE/built" >>"$POLE/logs/fixit.log" 2>&1
