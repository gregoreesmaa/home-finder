# P4 relief character tint (issue #619, graduation of #553)

DTM relief ships as a character/taste overlay, NOT a scored gradient —
relief is scenery, not good/bad. Tint first; capped taste legs second
(legs need the buyer-taste selection they hang on — cyclist /
view-seeker / flood-avoider — and land separately, never unlabeled).

## Source (probed 2026-09-17, polite: 1 caps + 1 describe + 1 probe + 1 harvest)

- Maa-amet DTM WCS `teenus.maaamet.ee/ows/wcs-dtm` (CC BY 4.0, annual).
- Coverages: `dtm-25` / `dtm-10` / `dtm-1`; used `dtm-10` (10 m,
  EPSG:3301, national extent N 6375000–6635000 E 365000–740000).
- WCS 2.0 subset axes rejected (`InvalidAxisLabel`); WCS 1.0.0
  `bbox+crs+width+height` works (server-side resample).
- Harvest: ONE GetCoverage, Harjumaa window lon 23.3–25.5 lat 58.4–59.65
  at 1000x570 (~130x240 m cells, float32 EH2000 heights), 2.3 MB over
  the wire. No 429 seen; 429 stops the run by policy.
- Vertical datum: EH2000 heights as served (no datum shift applied —
  tint is relative character, not engineering data).

## Calibration (county grid + Saku probe)

County: 570 000/570 000 valid, 0–112.1 m, p50 19.9 m (sea cells read
0.0 — the DTM does not mark water; they tint as lowland, honestly:
we never invent a watermask).

| Window | min | p10 | p50 | p90 | max | Reads |
|---|---|---|---|---|---|---|
| klint Lasnamäe | 0 | 13 | 41 | 45 | 54 | plateau 41–45, sea at 0 |
| Nõmme slope | 13 | 27 | 44 | 52 | 61 | slope 27→52 |
| Pirita lowland | 0 | 0 | 6 | 41 | 48 | lowland 0–6, klint behind |

The bands discriminate (plateau vs slope vs lowland); the tint
ERISTAB (distinguishes), never hindab (scores).

## Overlay-vs-leg split

- Overlay (this issue): hypsometric tint image (moss→sand→tan→pale
  rock LUT, alpha 150, deliberately not green/red), taste-only legend
  ("maitse, mitte hinne"), zero points, no raster master, no scorer
  legs. Missing sidecar renders honestly-empty (toggle 0).
- Legs (later, #553 graduations): lowland-dampness flag,
  viewpoint-elevation taste leg, cycling-effort leg, klint-edge
  build-complexity flag — each capped, each labelled with its named
  taste. Driveway-grade NULL and p336 slidebuf stay as-is until then.

## Rebuild

`python3 scripts/build/batch_relief.py --tif <cached GeoTIFF> --snap <snapshot>`
writes `<snap>/relief/relief-tint.json` (base64 int16 decimetres +
stats). Served verbatim by `/api/layers/relief/areas`; the client
decodes + renders (see `renderReliefTint` — pure, unit-tested).
