#!/bin/bash
# Pole wrapper: TEHIK medre Step 1 (register) + Step 2 (ADS join, #660).
set -eu
POLE="$HOME/hf-pole"
export HF_MEDRE_CACHE="$POLE/cache/medre" HF_MEDRE_OUT="$POLE/built"
mkdir -p "$POLE/cache/medre" "$POLE/cache/medre-ads" "$POLE/built"
cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python" -c "import os; from batch_medre import main; raise SystemExit(main(os.environ['HF_MEDRE_CACHE'], os.environ['HF_MEDRE_OUT']))"
cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python" batch_medre_ads.py --cache-dir "$POLE/cache/medre-ads" --medre-cache-dir "$POLE/cache/medre" --out-dir "$POLE/built"
