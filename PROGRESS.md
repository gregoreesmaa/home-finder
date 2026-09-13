# #482 — OSM daily-life overlay (P4-027/032/044/045/049/061 proxies)

## Status: implemented, verified, PR opened

### What
Six honest OSM-derived PROXY map layers (`apps/web/lib/layers_osmdaily.ts`):
dailyshop (P4-027), activity (P4-032), herd (P4-044), thirdplace (P4-045),
taxidoor (P4-049), lastshop (P4-061). Sparse-but-real count kernels with
caps + caveats; last-shop absence = warning (HOIATUS), never measured.

### Wiring (OSMDAILY-HOOK blocks only, sibling batches disjoint)
- `lib/layers.ts`: LayerId union + DECAY_KM + LAYERS + TAGS + bonusSpecFor
- `lib/overlays.ts`: 6 distinct marker colors + Estonian legends
- `lib/server/snapshot.ts`: RASTER_FILE + METRO_PREFIX entries
- `app/layers/page.tsx`: skip `(p…)` suffix for empty paramIds
- paramIds stays EMPTY (parameters4 namespace; 44/61 belong to parameters3 audit)

### Verification (2026-09-13, worktree 482-osm-daily)
- `vitest run apps/web/lib`: 72 files / 766 tests green
- `tsc --noEmit`: clean; `eslint` on touched files: clean
- Live smoke (`next dev -p 3101` + system Chrome): /layers shows all six
  P4 buttons; dailyshop renders 477 snapshot points (points-splat fallback;
  window raster 500 → client fallback, by design until follow-up raster build)
- Derived snapshot counts match module header: 477/1840/149/1211/4085/840
- Screenshot: /tmp/hf-482-layers.png (attached in PR as DoD evidence)
