# P4 canopy-height character tint (issue #620, graduation of #553)

Canopy height ships as a character/taste overlay, NOT a scored
gradient — height is a buyer tradeoff (shade/shelter vs light/view),
not good/bad. Tint first; capped taste legs second (legs need the
buyer-taste selection they hang on and land separately, never
unlabeled).

## Source (probed 2026-09-17, polite: 1 caps + 1 legend + 1 probe + 1 harvest)

- Maa- ja Ruumiamet CHM WMS `teenus.maaamet.ee/ows/wms-chm`
  (CC BY 4.0). Layer `CHM2022_suvi` (2022 summer flight).
- Layer serves EPSG:3301 ONLY (no 4326 — the batch reprojects by
  exact inverse Transverse Mercator, L-EST97, verified <1 m at
  Tallinn, pinned by test).
- Publisher legend (`GetLegendGraphic`, exact RGB match in
  `CLASS_COLORS` — verified against the live legend 2026-09-17):
  `25510F` 1-4 m, `35690D` 4-10 m, `6B860A` 10-20 m,
  `DF7F03` 20-30 m, `E01F1F` >30 m. `<1 m` renders transparent and
  stays MISSING (never painted as short canopy).
- Harvest: ONE county GetMap, Harju window E 459086–587668
  N 6473458–6613389 at 1004x1093 (~128 m cells, RGBA), 202 KB over
  the wire. No 429 seen; 429 stops the run by policy.
- Unmatched-opaque pixels are MISSING + counted, never guessed
  into the nearest class: a publisher style change fails visibly.
  This harvest: unmatched = 0 (legend still current).

## Calibration (county class grid 1000x570, 570 000 cells)

| Class | Cells | Share of canopy |
|---|---|---|
| <1 m / puudub (transparent) | 326 016 | — (missing) |
| 1-4 m | 44 915 | 18 % |
| 4-10 m | 73 771 | 30 % |
| 10-20 m | 114 055 | 47 % (dominant) |
| 20-30 m | 11 239 | 5 % |
| >30 m | 4 | <0.1 % |

Canopy cells: 243 984/570 000 (~43 %). Tall canopy (>20 m) is
rare; the tint ERISTAB (distinguishes), never hindab (scores).
(Reverse-map sampling: every lon/lat cell reads its nearest source
pixel, so 0 cells are transparent source, never splat gaps.)

## Overlay-vs-leg split

- Overlay (this issue): class-tint image (publisher greens +
  amber/red LUT, alpha 150, taste-only legend "maitse, mitte
  hinne"), zero points, no raster master, no scorer legs. Missing
  sidecar renders honestly-empty (toggle 0).
- Legs (later, #553 graduations): shade/shelter taste leg,
  view-openness taste leg — each capped, each labelled with its
  named taste.

## Rebuild

`python3 scripts/build/batch_canopy.py --png <cached PNG> --snap <snapshot>`
writes `<snap>/canopy/canopy-tint.json` (base64 uint8 classes +
stats). Served verbatim by `/api/layers/canopy/areas`; the client
decodes + renders (see `renderCanopyTint` — pure, unit-tested).
