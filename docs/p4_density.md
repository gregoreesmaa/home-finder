# P4 density 1 km character choropleth (issue #622, graduation of #554)

Population density ships as a character/taste choropleth, NOT a
scored gradient — urban buzz vs quiet is a buyer tradeoff, not
good/bad. Fills first; capped taste legs second (legs need the
buyer-taste selection they hang on and land separately, never
unlabeled).

## Source (probed + harvested 2026-09-17, polite)

- Maa- ja Ruumiamet INSPIRE PD 1x1 km WFS (CC0, Statistikaamet),
  layer `PD.StatisticalDistribution_` (EPSG:3301 twin, pulled in
  EPSG:4326).
- Harvest: 1 GetCapabilities + 1 DescribeFeatureType + ONE Harjumaa
  bbox GetFeature (custom UA, ~17 MB over the wire, no 429; 429 stops
  the run by policy).
- CONFRONTATION verdict (parent #554 demanded it): MAINTAINED series,
  NOT the dated census-2021 bulk — reference period 1.1.2024–
  31.12.2024, status definitive, last update 2025-05-07, measure
  populationAtResidencePlace (person, count). Proceed: confirmed.
- Privacy masking, load-bearing: squares with <4 inhabitants read 0
  (masked, never "empty"); class 0 is empty OR masked, honestly one
  class. Un-geocodable addresses were pinned to village/census
  centres by the publisher (stated, not ours to fix).

## Calibration (Harju squares, 8210 total, 0 dropped)

| Class (OUR bins) | Squares | Reads as |
|---|---|---|
| 0 (tühi/varjatud) | 5 166 | quiet/forest (masked or empty) |
| 1–9 | 1 136 | scattered farmsteads |
| 10–99 | 1 397 | villages |
| 100–999 | 378 | small towns |
| 1000–4999 | 96 | dormitory ring |
| 5000+ | 37 | city core (max 16 231) |

The bands discriminate (city core vs dormitory ring vs masked
rural); the fills ERISTAVAD (distinguish), never hindavad (score).

## Overlay-vs-leg split

- Overlay (this issue): exact-square class fills (bone → plum,
  deliberately NOT green/red), taste-only legend ("maitse, mitte
  hinne", bins stated as OURS, 1 km grain + 2024 vintage named), zero
  points, no raster master, no scorer legs. Missing sidecar renders
  honestly-empty (toggle 0). Outside every square is NULL (never
  rural — unmapped is not uninhabited).
- Legs (later, #554 graduations): urbanist delight leg, quiet-seeker
  cost leg, services-viability floor — each capped, each labelled
  with its named taste. Masked-zero squares score None in the scorer,
  never 0/100.

## Rebuild

`python3 scripts/build/batch_density.py --json <cached GeoJSON> --snap <snapshot>`
writes `<snap>/density/density-areas.json` (zone_id + inhabitants +
class + quad ring). Served verbatim by `/api/layers/density/areas`;
the client filters + paints (see `applyDensityPolygons` — pure color
map `densityFillColor`, unit-tested).
