# P4 building-height character tint (issue #621, graduation of #547)

Building height ships as a character/taste overlay, NOT a scored
gradient — height is a buyer tradeoff (view vs shade, openness vs
shelter), not good/bad. Tint first; capped taste legs second (legs
need the buyer-taste selection they hang on and land separately,
never unlabeled).

## Source (probed + harvested 2026-09-17, polite)

- Maa- ja Ruumiamet 3D hoonete LoD1 CityGML 2.0 (CC BY 4.0, PUBLIC),
  per-municipality zips off the geoportal 3D download page
  (`Laadi-3D-andmed-alla-p833.html`, `andmetyyp=hooned_lod1`).
- Harvest: 16 Harju zips, sequential with pauses, custom UA (~80 MB
  over the wire, no 429; 429 stops the run by policy). Portal file
  dates 11.09.2026; per-building `lod1_muutmisaeg` all 2025 (fresh
  ALS — heights go stale where building continues, legend says 2025).
- CityGML is plain XML: stdlib-only build (zipfile + iterparse), NO
  GDAL needed (the issue's "GDAL-class tooling" worry dissolves —
  GDB/OBJ variants exist but were never touched).
- AXIS TRAP (caught live): EPSG:3301 axis order is NORTHING,EASTING
  (envelope lowerCorner reads N E h); a naive (E,N) read lands at lon
  72. Triples are (n,e,h) — swapped on ingest, pinned by test.

## Calibration (county class grid 1000x570, 570 000 cells)

198 541 buildings parsed, 100 % with measuredHeight (186 negative =
underground parts, excluded + counted; 13 without a year stamp).

| Class (OUR bins) | Cells | Reads as |
|---|---|---|
| 0-3 m | 1 727 | sheds, garages |
| 3-6 m | 5 454 | 1-storey houses |
| 6-12 m | 20 490 | 2-3 storey stock (dominant) |
| 12-25 m | 4 592 | apartment blocks |
| >25 m | 793 | towers (Tallinn centre) |

Painted cells: 33 056/570 000. Only roof-plane rings paint (walls/
ground never do); courtyards subtract (even-odd); sub-cell houses
mark their centroid cell (the cell DOES contain the building — no
invented area); max class wins per cell (stated). Spot-checks:
suspect lone sea cells reverse-geocode to real villages (Kasispea,
Kelnase) — no phantom painting.

Window note: the grid window (lon 23.7–26.0, lat 58.95–59.75) is
DELIBERATELY wider than the relief/canopy window (which clips Loksa
+ eastern Kuusalu + southern Saue/Kose): a building layer must
contain whole municipalities. Each sidecar carries its own bbox.

## Overlay-vs-leg split

- Overlay (this issue): height-tint image (pale stone → deep indigo,
  deliberately NOT green/red), taste-only legend ("maitse, mitte
  hinne", bins stated as OURS), zero points, no raster master, no
  scorer legs. Missing sidecar renders honestly-empty (toggle 0).
- Legs (later, #547 graduations): measured shade-casting from z_max +
  footprint, overlooking from z_max + distance — each capped, each
  labelled with its named taste. LoD1 flat roofs overstate parapet
  shade: capped hinnang, never survey-grade (legend says so).

## Rebuild

`python3 scripts/build/batch_buildings.py --cache-dir <zips> --snap <snapshot>`
writes `<snap>/buildings/buildings-tint.json` (base64 uint8 classes +
stats). Served verbatim by `/api/layers/buildings/areas`; the client
decodes + renders (see `renderBuildingsTint` — pure, unit-tested).
