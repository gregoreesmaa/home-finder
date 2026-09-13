# #486 — MARU per-KOV market choropleth (5 flipped G16 params)

## Status: implemented, verifying (live smoke next)

### What
Four honest MARU-derived per-KOV choropleth map layers
(`apps/web/lib/layers_maru.ts`): kovkasv (p41 YoY appreciation),
kovkaive (p149 quarterly deal count), kovedas (p43 resale composite),
kovkiirus (p484 deal-velocity QoQ, weak flip cap 70). Exact KOV fills
on open OSM admin_level=7 polygons (KOV-identity join or NULL/255,
never kernels, never smoothing, never forward-fill) — the map twin of
the dims_overturn_maru.py NULLs.

p421 REFUSED for the map (pinned in test): the appraisal-gap band needs
the listing asking price, so no per-KOV cell value exists; painting KOV
medians as gap scores would fake the join (IA028 refusal precedent,
#485). p421 stays a per-listing registry join.

### Gray areas (reviewable, AGENTS.md §7.5)
- 4 map layers, not 5: p421 has no per-KOV value (asking=NULL at KOV
  grain). Refusal pinned (`not.toContain("kovgap")` + hook marker).
- paramIds carry the REAL G16 numbers [41]/[149]/[43]/[484] (these ARE
  the flipped params; OSMDAILY empty-paramIds precedent is P4-only).
  GROUP16A/B verdict files untouched (they refuse GRADIENT maps; the
  exact fill is the overturn's new shape; docs-index PR owns nomap.md).
- Committed fixture is SYNTHETIC under FAKE kov names (no MARU bulk
  contract exists to harvest); building it against the real extract
  fails closed by construction. Masters stay unbuilt until the
  maintainer places the quarterly export → layers render honestly
  unknown until then.
- Geometry (Grid/fill/DP) copied from the #485 builder pattern with
  attribution, not imported: #485 is unmerged, an import would dangle
  on main.

### Wiring (MARUKOV-HOOK (#486) blocks only, siblings disjoint)
- `lib/layers.ts`: LayerId + DECAY + LAYERS + TAGS + bonusSpecFor
- `lib/overlays.ts`: 4 distinct marker colors + Estonian legends
- `lib/server/snapshot.ts`: RASTER_FILE + EUCLIDEAN_MASTER + METRO_PREFIX
- `app/layers/page.tsx`: skip otsekaugus/varu suffix (exact fills,
  not distances); button `(p…)` suffix needs no change (paramIds set)
- Builder: `scripts/build/batch_maru_choropleth.py` + synthetic
  `maru_kov_tables.example.json` + `test_batch_maru_choropleth.py`

### Verification
- `pytest scripts/build/test_batch_maru_choropleth.py`: 20 passed
- `vitest run apps/web/lib`: 75 files / 806 tests green
- `pytest services/scoring/tests + builder`: 2308 passed, 4 skipped
- `tsc --noEmit`: clean; `eslint` on touched files: clean
- Live smoke (`next dev -p 3106` + headless system Chrome):
  /layers renders all four MARU buttons with (p41)/(p149)/(p43)/
  (p484) suffixes (title+suffix doubling matches page convention,
  e.g. `(proksi, hinnang) (p409)`); DOM contains all four titles;
  map + legend healthy, no page errors with software WebGL.
  Screenshots: /tmp/hf-486-layers-full.png (DoD evidence for PR).
  Note: one transient "1 error" badge under --disable-gpu is the
  headless-no-GPU WebGL-init artifact (maplibre-gl, affects any
  layer, absent with --enable-unsafe-swiftshader) — not this change.
