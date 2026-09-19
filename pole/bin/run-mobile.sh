#!/bin/bash
POLE="$HOME/hf-pole"
mkdir -p "$POLE/cache/mobile" "$POLE/built/osm"
TOK="$(cat $POLE/state/opencellid.token)"
curl -s --max-time 600 -o "$POLE/cache/mobile/248.csv.gz"   "https://opencellid.org/ocid/downloads?token=$TOK&type=mcc&file=248.csv.gz" >>"$POLE/logs/mobile.log" 2>&1
du -sh "$POLE/cache/mobile/248.csv.gz" >>"$POLE/logs/mobile.log" 2>&1
cd "$POLE/harvesters" && PYTHONPATH="$POLE/dims" "$POLE/venv/bin/python"   batch_mobile_import.py --csv "$POLE/cache/mobile/248.csv.gz" --snap "$POLE/built" >>"$POLE/logs/mobile.log" 2>&1
