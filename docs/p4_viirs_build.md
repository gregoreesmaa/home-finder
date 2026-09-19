# Build: VIIRS Black Marble light-pollution sidecar (issue #719)

> Follow-up of the POSITIVE probe #699 (`docs/probe_viirs.md`,
> `services/scoring/probe_viirs.py`).
> Code: `scripts/build/batch_viirs.py`; tests:
> `services/scoring/tests/test_batch_viirs.py` (hermetic).
> Scorer: `services/scoring/dims_viirs.py` + `tests/test_dims_viirs.py`
> (brightness-proxy leg, `viirs_brightness` key).
> Overlay: `apps/web/lib/layers_p4_viirs.ts` + `.test.ts`
> (96 sampled cells, qbands).

## Buyer question

"Kui pime on öösel?" — light-pollution darkness score from
night-lights imagery for the darkness-sensitive buyer (P4-035
brightness-proxy slice; sibling slices veebi/ilm/lidar/ehr/osm +
the login-walled EOG radiance NULL stay untouched).

## §6 Build basis (STEP ZERO — dated positive, 2026-09-19)

Keyless VIIRS night-lights tiles confirmed via NASA GIBS WMTS.
Polite harvest, UA `home-finder-research/0.1`, `--max-time` 30,
paced ≥ 2 s, 429 as stop, timeout + retry-once-max (the caps round
showed one transient timeout then 200 — `probe_viirs.md`). Raw
PNGs in `/tmp/hf_viirs_*` (one-off PR record, never committed).

| Check | Observed | Meaning |
|---|---|---|
| `GET .../VIIRS_Black_Marble/default/default/GoogleMapsCompatible_Level8/8/75/145.png` → 200, 55 225 B, 256×256 RGB | Tallinn tile, no login | Keyless basis confirmed |
| `GET .../8/76/145.png` → 200, 44 530 B | Soomaa tile, no login | Dark anchor confirmed |
| `GET .../wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml` → 200, 5.8 MB (one-off) | Time dimension: 2012 + 2016 annuals, default 2016-01-01; matrix tops at Level8 | **Vintage 2016** stamped everywhere; no deeper tiles exist (z8 cap refused as error, never faked) |
| `GET eogdata.mines.edu/...` download dirs → 302 to Keycloak (probe #699) | Login wall stands | Untouched — NO credential workarounds, out of scope |

**Spot-check before ranking (required):** stdlib PNG decode —
saturated city-centre 5 px window mean **255.0** vs dark Soomaa bog
window **11.6** (≈22× contrast); tile means 26.9 vs 14.2. The proxy
resolves the gradient it claims (pinned in `test_batch_viirs.py`
+ `test_dims_viirs.py` + `layers_p4_viirs.test.ts`).

## Harvester

`batch_viirs.py --pull --build --cache-dir DIR --out grid.json
[--bbox ...] [--cols 12] [--rows 8] [--zoom 8]`. The Tallinn metro
bbox sits inside ONE z8 tile; the builder crops it and aggregates
nearest-pixel block means (12×8 ≈ 2.75 km cells — city-glow scale,
no resampling, no smoothing). Real grid 2026-09-19: **96 cells**,
min 9.4 (NW outskirts, sea-adjacent) / p50 91.6 / max 255.0
(Mustamäe/Õismäe glow); q-spread 6×90 / 19×70 / 26×50 / 18×30 /
27×10. `--zoom > 8` honestly refuses (no deeper tiles).

## BRIGHTNESS PROXY (user-visible limitation, required)

GIBS serves **visualization PNGs, not numeric radiance** — every
surface (layer title/legend/source, dims reason, pole grid
`source` field) says **heledusproksi, MITTE radiomeetria**.
Disclosed limits: 2016 composite (predates new builds); ≈2.75 km
cells (never street-level); open water carries no lights, so
coastal cells read darker than the sky is (never silently
corrected).

## Pole wiring (pole files, recorded here per AGENTS.md §9)

Wrapper `bin/run-viirs.sh` (annual — the composite barely moves):

```sh
#!/bin/sh
# Pole wrapper: VIIRS brightness grid (annual rebuild, keyless GIBS).
set -eu
POLE="$HOME/hf-pole"
OUT="$POLE/built/viirs/grid.json"
mkdir -p "$POLE/cache/viirs" "$(dirname "$OUT")"
python3 "$POLE/harvesters/batch_viirs.py" \
  --pull --build --cache-dir "$POLE/cache/viirs" --out "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
```

Cron (pole crontab, yearly January):
`23 4 15 1 * $HOME/hf-pole/bin/run-viirs.sh >>$HOME/hf-pole/logs/viirs.log 2>&1`

Read API: `GET /v1/viirs` (honest 503 until the first build).
The committed `VIIRS_CELLS` is the reviewed derived snapshot
(regenerate, never hand-edit); raw PNGs never leave cache//tmp.

## Buyer-side check

Detsembri-kohapealne 15:30 jalutuskäik (proxy + 2016 vintage —
trust eyes over pixels).
