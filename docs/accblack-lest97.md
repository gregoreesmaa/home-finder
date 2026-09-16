# Accident blackspots: L-EST97 → WGS84 unlock (issue #522)

> Buyer report: the accident-blackspot layer reads empty. The CSV HAS
> X/Y on newer rows (L-EST97 metres); pre-2019 rows are blank. PR #506
> shipped honestly-empty rather than fake points. This note records the
> #522 unlock: the ported transform, the per-point join, and what stays
> open.

## Verdict

**UNLOCKED at the builder, still honestly-empty on the map.**
`scripts/build/batch_accblack.py` now ports the labelled
`lest97_to_wgs84` inverse Lambert Conformal Conic from
`scripts/build/batch_tervise.py` (#511, verified <1 mm vs pyproj
there): same constants, same `LEST97_ACCURACY_LABEL`
("GRS80~WGS84 daatumi vahe ~1 m"). `projected_records()` emits
per-point `{lat, lon, x_lest, y_lest, sev, year, vintage, commune,
projected: True, transform}`; pre-2019 blank-coordinate rows are
skipped (NULL — counted via `split_coords`, never plotted, never
zero-filled). `measured_records()` keeps its raw shape for back-compat.

## Dated probe (2026-09-16, polite, /tmp only)

ONE bytes 0–2500 range peek at the Transpordiamet CSV distribution
(`pilv.transpordiamet.ee … lo_2011_2026.csv`, UA
`home-finder-522-accblack-probe/1.0`) → HTTP 206 `text/csv`,
byte-identical size **12342189 B**, same `;`-delimited header ending
in `X koordinaat;Y koordinaat`. No re-pull, no dumps committed, zero
429. `PROBE_DATE`/`PROBE_CSV_BYTES`/`PROBE_HEADER_COLS` unchanged.

## Regression cover

`scripts/build/test_batch_accblack_proj.py` (hermetic, fixture CSV
only): transform parity with the tervise oracle (<1e-9° on the live
fixture coord + the Pirita control point), fixture projects to Harju,
accuracy-label byte parity, vintage labels (`year`/`vintage`),
blank-row NULLs, no-network-imports guard.

## What stays open (follow-up, not this PR)

Wiring the projected extract into the serving path (snapshot sidecar +
route, severity-sum kernel master) and flipping `layers_accblack.ts`
off empty-on-purpose. The TS reopen checklist and drift guard are
deliberately untouched here.
