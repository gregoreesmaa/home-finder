# #487 — flood-risk polygon overlay (KAUR/EFAS per-parcel join)

## Status: implementing

### What (per `docs/overturn_flood.md` verdict + issue AC)
- Polygons ONLY (no fake gradient): new `floodzone` layer (p112) serves the
  KAUR `eelis:kr_yleujutusohuga_ala` zone polygons as a choropleth fill
  (inside a named polygon vs outside/unknown). Zero points, zero raster —
  the map paints basemap + fills only.
- Per-parcel join or NULL with Estonian reason: scorer side ALREADY ships as
  `services/scoring/dims_overturn_flood.py` (`dim_floodzone_p112`, proven on
  fixtures) — this PR wires the map overlay + the GML→sidecar builder, and
  cites (not duplicates) the scorer. `dims_group08a-d`, `livability.py`,
  WEIGHTS untouched (verdict doc §"Sibling split").
- p112 ships twice (g08a OSM-snapshot no-map verdict stands; floodzone join
  overlay from the KAUR polygon register) — p13/p15 precedent.

### Files
- NEW `apps/web/lib/layers_flood.ts` + `layers_flood.test.ts`
- EDIT `apps/web/lib/layers.ts`, `overlays.ts`, `outlines.ts`,
  `server/snapshot.ts`, `app/api/layers/[layer]/route.ts`,
  `app/layers/page.tsx`, `components/ValueHeatMap.tsx`
- NEW `apps/web/app/api/layers/floodzone/areas/route.ts`
- NEW `scripts/build/batch_flood_kaur.py` + `test_batch_flood_kaur.py`
- Count 85→86 in 8 registry tests + `layers.test.ts` id list
- Docs: `docs/layers.md` G8 row, `docs/p4_kaur.md` cross-link

### DoD
- [ ] AC met per verdict doc honest shape
- [ ] Proof pasted in PR (vitest/pytest output, /layers screenshot)
- [ ] Regression tests added + green
- [ ] Existing suite green (no regressions)
- [ ] Fresh no-context review -> approve + merge
