# P4 PLANK/TPR designated-use polygons (issue #492)

Group B verify-first layer issue. AC: polite WFS harvest,
per-parcel designated-use overlay **or dated-negative with evidence**.

## Verdict: overlay SHIPPED, live harvest dated-NULL

Both AC branches are met at once: the `planktpr` polygon overlay is
wired end-to-end (registry, fills, legend, sidecar route, harvester),
and the live harvest holds no polygons — the layer renders honestly
empty with the re-verification date in its legend + source until bulk
reopens (the overturn #236 shapes stay live-NULL with it).

## Openness evidence (one polite round, 2026-09-13, no scraping)

5 tiny requests total (labelled one-off user-agent
`home-finder-492-planktpr/1.0`, paced ≥ 3 s, headers + two small shells
only, no form submissions, no bulk pull). Raw bodies:
`/tmp/hf-492-planktpr/` (one-off PR record, not committed).
Re-confirms the #236 dated verdicts in `dims_p4_plank.py` (#251) and
`dims_p4_tpr.py` (#250/#334) the same day.

| Check | Observed | Meaning |
|---|---|---|
| `HEAD planeeringud.ee/` → 301 (Apache/ZoneOS) | `location: https://livekluster.ehr.ee/ui/ehr/v1/detailsearch/PLANNINGS_SEARCH` | PLANK portal still inside the E-ehitus platform |
| `HEAD planeeringud.ee/geoserver/wfs` → 301 | same location | the documented OGC WFS 2.0.0 base still serves no WFS |
| `GET .../geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities` (-L) → 200 text/html, 3663 B | `<title>e-ehituse platvorm</title>`, zero `wfs:`/`opengis`/`FeatureType` markers | NO GetCapabilities document — the old GeoServer endpoint is gone |
| `HEAD tpr.tallinn.ee/` → 200 (Apache, 83 331 B) | `Last-Modified: 09 Sep 2026` | human register, as before |
| `GET tpr.tallinn.ee/` → 200, 83 331 B shell | zero `wfs`/`bulk`/`api/`/`download`/`csv`/`geojson` hits | NO open bulk endpoint behind the shell |

## What ships

* `scripts/build/batch_planktpr_wfs.py` — polite harvester
  (GetCapabilities → designated-use typename → one GetFeature pull,
  max 1 / 14 d, single GETs, 429 = stop) into the `plank/areas.json`
  sidecar (kehtestatud Tallinn polygons only, raw use codes, malformed
  features skipped). While `PLANK_BULK_URL` is None it performs NO
  requests (dated negative as an explicit code path, pinned by test).
* `apps/web/lib/layers_planktpr.ts` — layer `planktpr` (p47):
  per-parcel exact-join fills colored by band (residential 80 / mixed
  60 / commercial 35 / restricted 20, cap 80 — byte parity with the
  `dims_overturn_planktpr` scorer, pinned by tests on both sides).
  Outside a harvested kehtestatud polygon there is no hinnang;
  `fallbackPoints` is EMPTY by documented decision (no honest demo
  polygons exist).
* Wiring (`PLANKTPR-HOOK (#492)` blocks): `lib/layers.ts` (registry,
  decay, tags, spec), `lib/overlays.ts` (marker color + legend with the
  dated negative), `lib/outlines.ts` (`applyUsePolygons` fills),
  `components/ValueHeatMap.tsx` (`usePolygons` slot), `app/layers/
  page.tsx` (fills fetch + toggle count + suffix skip),
  `lib/server/snapshot.ts` (`loadPlanktprAreas` sidecar + absent
  raster/metro names), `app/api/layers/planktpr/areas/route.ts`.
* p74 decree + p274 ceiling stay SCORER-ONLY (verdicts table in the
  module): decree texts are not a parcel feed, a ceiling number is not
  a polygon, the deed stays in the paid register.

## Judgment calls (for the reviewer)

1. New `cover` BonusSpec instead of a new kind: the polygon bands ARE
   the calibration (self-scaling, statkov/mobile precedent); the wire
   contract (half null, sigma 0.5) is checked by `matchesContract`.
   The live points path serves nothing, so the splat degrades to
   honestly unknown — the fills ARE the field.
2. Empty `fallbackPoints` + a pinned exemption in the global
   "every layer has demo points" contract test: two demo centroid dots
   would imply point data for a polygons-only layer. The exemption
   expects exactly `[]` so no demo junk can creep in.
3. The harvester keeps RAW use codes (unknown codes kept, never
   judged): classification lives in the scorer + web layer, where
   unknown stays NULL. Splitting harvest from judgment keeps the
   sidecar a faithful register copy.
4. p47 graduates from the G05A no-map row to a map layer
   (`docs/layers.md` 97→98, `docs/nomap.md` p47 row → proxy): the
   no-map rationale (OSM landuse ≠ decree) still holds — this layer
   paints harvested decree polygons, never OSM. The p74/p274 and P4-006
   pipeline no-map rows are untouched.
5. No county raster is built (documented `PLANKTPR_NO_RASTER`): a stamp
   of an empty harvest would be county-wide unknown with build
   machinery and no meaning (parks-outline precedent — outlines draw
   over the base field). The `/window` 500 for this layer is the
   designed no-raster path (GTFS precedent).

## Reopening checklist (when PLANK/TPR serve per-parcel bulk)

1. Re-run `batch_planktpr_wfs.py --probe`; paste fresh evidence here.
2. Set `PLANK_BULK_URL` (+ the TPR typename if separate) to the
   verified bulk URL; pull one harvest; confirm the sidecar fills the
   overlay (toggle count > 0).
3. Verify the Tallinn `kov` spellings + `use_stage` + `designated_use`
   codelists against the live registers; adjust `TALLINN_KOVS`,
   `DECREE_STAGE`, and the use-stem sets in all three places (drift
   tests point at each other).
4. Recalibrate `USE_BANDS` from real histograms (first-cut bands are
   uncalibrated by construction); resolve the PLANK↔TPR↔KKIS overlap
   rule with the central hook. Re-check no later than **2027-03-13**.
