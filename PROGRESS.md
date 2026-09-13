# #487 — flood-risk polygon overlay (KAUR/EFAS per-parcel join)

## Status: implemented, verified, PR opened

### What (per `docs/overturn_flood.md` verdict + issue AC)
- Polygons ONLY (no fake gradient): new `floodzone` layer (p112) serves the
  KAUR `eelis:kr_yleujutusohuga_ala` zone polygons as a choropleth fill
  (inside a named polygon vs outside/unknown). Zero points, zero raster —
  the map paints basemap + fills only.
- Per-parcel join or NULL with Estonian reason: scorer side ships as
  `services/scoring/dims_overturn_flood.py` (`dim_floodzone_p112`, 24 tests
  green, untouched) — this PR wires the map overlay + the GML→sidecar
  builder (`scripts/build/batch_flood_kaur.py`, 8 tests green).
- p112 ships twice (g08a OSM no-map verdict stands; floodzone KAUR overlay
  from the polygon register) — p13/p15 precedent. Rebased onto
  origin/main @ 6a5fd5e (#484 senscom + #485 3×kov → registry 90);
  conflicts resolved by keeping both sides; recount 89+1=90 in 12 files.
  Rebase catch: floodzone sourceNote wrongly carried the Euclidean "varu"
  suffix (zero points ⇒ no fallback exists) — fixed via the #485
  isStatKovLayerId skip pattern. #485's rasterized KOV choropleths are a
  different honest shape (exact per-KOV values); no overlap.

### DoD
- [x] AC met per verdict doc honest shape
- [x] Proof pasted in PR (vitest/pytest output, /layers screenshots)
- [x] Regression tests added + green
- [x] Existing suite green (no regressions)
- [ ] Fresh no-context review -> approve + merge
