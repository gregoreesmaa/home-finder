# Ookla speed-layer tab crash — repro, root cause, fix (#516)

Buyer report: opening either Ookla layer (`Fikseeritud netikiirus` /
`Mobiilne netikiirus`, `/layers` -> layer buttons) freezes/crashes the
browser tab. Both `/api/layers/ookla_fixed` and `/api/layers/ookla_mobile`
return HTTP 200 (extract holds 1,914 fixed + 1,706 mobile tiles), so the
data path is healthy — the crash is in client-side rendering.

## Repro (no browser needed — pure compute, hermetic)

`vite-node /tmp/ookla-repro.mts` (scratch, not committed): builds the
`tileband` scored field exactly as `ValueHeatMap` refresh does —
`fieldResolution` over the Tallinn view
`{ minlon: 24.3, minlat: 59.3, maxlon: 25.1, maxlat: 59.6 }` with 1,914
synthetic qualifying tiles:

- Reference hardware: Apple M3, 16 GB RAM, macOS 26.6.2, Node v26.8.2.
- BEFORE (per-cell `ooklaTileAt` loop): grid 905x663 = 600,015 cells,
  `buildScoredField` **43,166 ms**, known=598,233/600,015.
- AFTER (indexed `ooklaDirectField`): same grid, **438 ms** (~98x),
  known=598,233/600,015 (identical coverage).
- Click path in the app: `/layers` -> `Fikseeritud netikiirus
  (P4-009 Ookla-hinnang)` or `Mobiilne netikiirus (P4-009
  Ookla-hinnang)` button. The full-Estonia default view resolves to an
  even larger grid (~1200x960), so the real freeze was ~2x worse than
  the Tallinn number above — and `refresh()` re-runs synchronously on
  the UI thread on every pan/zoom settle.

## Root cause

`buildScoredField`'s `tileband` branch (`apps/web/lib/distanceField.ts`)
called `ooklaTileAt` once per grid cell, and `ooklaTileAt` scans ALL
tiles (plus re-parses every tile's `avg_d`/`tests` tags per cell).
Cost was **cells x tiles** — ~1.1B inner iterations for the Tallinn
view, all on the UI thread. Point count was never the problem: 3.6k
points would not kill deck.gl/MapLibre by themselves (markers are
already capped at `OVERLAY_CAP` 800 via `selectOverlayPoints`), and the
mechanism is now proven, not hypothesised. The sibling `bands`/`qbands`
branches share the loop shape but serve tens of points, so they stay.

## Fix (both layers, one kernel)

`ooklaDirectField` in `apps/web/lib/layers_p4_ookla.ts` (called from the
`tileband` branch): tile tags are parsed + filtered ONCE, qualifying
centroids go into a degree-space spatial hash keyed at the join-radius
scale, and each field cell only tests tiles in the hash cells its
radius box touches. The box is conservative by construction
(`dist = hypot(dx*57.29, dy*110.57) <= r` implies `|dx| <= r/57.29`,
`|dy| <= r/110.57` — the same constants as `ooklaHavKm` — plus 1e-9 deg
float slack), the accept/reject check is the same `ooklaHavKm`
arithmetic, and ties resolve to the lowest original index exactly as
`ooklaTileAt`'s strict-`<` scan. Output is cell-identical to the old
loop (0 mismatches / 10,800 cells incl. thin, speed-less and coincident
adversarial tiles; see `/tmp/ookla-parity.mts`, scratch).

Deliberately NOT a cap/decimation: both layers share one kernel
(`ooklaBonusSpecFor` ignores the layer id — pinned by test), and
dropping measured tiles would punch dishonest gaps into the field.
Every tile still renders; no data change, no color change, no scorer
change (`goodnessAt` hex path still uses `ooklaTileAt` directly — it is
O(tiles) per call and was never the crash path).

## Regression tests

`apps/web/lib/layers_p4_ookla.test.ts` → `ookla crash fix (#516)`:
index-vs-old-loop cell parity, 1914-tile production-resolution render
under a 15 s bound (~35x headroom over the observed ~0.4 s), both-layer
field equality, all-unknown empty path. All synthetic, no network.
