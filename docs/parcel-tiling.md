# Kataster parcels beyond the 100-sample: Tallinn tiling (issue #520)

> Buyer report: only ~100 cadastral parcels show (Kesklinn), then
> nothing. The #491 harvest was a polite count-capped sample
> (`count <= 100`, one window) — coverage ends where the sample ends.

## Verdict

**Harvest path shipped; served coverage unchanged (honestly labelled).**
`scripts/build/harvest_maaparcel_tiles.py` bbox-tiles
`kataster:ky_kehtiv` over the Tallinn city bbox (24.5/59.35/24.9/59.5):
300 windows of 0.02° × 0.01°, one polite GET each (`count <= 100`
always, paced ≥ 3 s, identifying UA, fresh-cache wins, HTTP 429 stops
the run with a partial manifest, transport errors never cached).
Dense tiles subdivide recursively instead of raising `count`; tiles
still full at the minimum span stay flagged `truncated` in
`harvest_manifest.json` (honest partial, never silent). Per-tile raw
GeoJSON caches merge (dedupe by `tunnus`) into
`kk_ky_tallinn_merged.json`, which the existing
`batch_maaparcel_kataster.py --parcels` rebuild consumes unchanged
(dry-proven offline, 2026-09-16 — see below). No network was used to
ship this: all tests run on stub fetchers.

## Vector-tile alternative (researched 2026-09-16, negative)

Adopting openly offered Maa-amet cadastre vector tiles would beat
tiling, but **no such endpoint is on offer**: two public searches
(Maa-amet WFS/MVT/vector-tile docs, geoportaal WMS guides, OSM wiki)
surface only raster WMS base maps (`kaart.maaamet.ee/wms/...`),
feature WFS (`teenus.maaamet.ee/ows/...`,
`gsavalik.envir.ee/geoserver/wfs`), the In-ADS address API, and the
login-walled `minu.kataster.ee` e-service. WMS paints pictures, not
parcel records — it cannot feed the `tunnus`/`omvorm` join. So tiling
the verified open WFS is the path; if Maa-amet ever publishes
cadastre MVT, this harvester retires tile-by-tile (the merge contract
is just GeoJSON).

## Legend / unknown-outside (no change needed)

`layers_maaparcel.ts` already reads "väljaspool proovivalimit =
teadmata, mitte tühi (100 katastritunnust Kesklinna aknas)" — accurate
today and untouched. When the tiled harvest lands in a snapshot, the
follow-up flips the legend window text AND the builder provenance
(`SAMPLE_BBOX`/`HARVEST_DATE` still bake the 100-sample window) in one
joint change; until then outside-harvest stays unknown, never
blank-as-zero (the route contract is unchanged).

## Out of scope (follow-ups, not this PR)

- Running the full ~300-GET harvest (maintainer operation: `--probe`
  first — 1 GET validating the URL shape — then the paced run, then
  `batch_maaparcel_kataster.py --parcels <merged> --snap <snap>`).
- KKIS tiling (touch counts outside the #491 window stay `None` =
  unknown; the restriction layer was thin there anyway).
- Builder provenance parametrisation for multi-window harvests.

## Regression cover

`scripts/build/test_harvest_maaparcel_tiles.py` (hermetic): gapless
300-tile plan, scorer-contract URL shape (WFS 2.0.0, count=100,
lon-lat bbox), exact subdivision cover, junk-body rejection,
tunnus-dedupe merge, pull+merge+manifest, subdivision (never raises
`count`), minimum-span `truncated` flag, 429-stop with partial kept,
errors-never-cached, offline `--merge-only`, single-GET `--probe`
shape, single-`urlopen` guard. Existing
`test_batch_maaparcel_kataster.py` re-run green.
