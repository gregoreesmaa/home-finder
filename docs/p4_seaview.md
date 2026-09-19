# Probe: Maa-amet lidar density for sea viewshed (#712, shared round with #703)

**Verdict (2026-09-19): INSUFFICIENT — dated negative.** The open
Maa-amet point cloud does not verify at density sufficient for a
per-building sea-viewshed (sea-visible boolean + quality). No heavy
compute, no invented viewsheds. Verdict carrier:
`services/scoring/probe_seaview.py` (`SEAVIEW_VERDICT`), guard:
`services/scoring/tests/test_probe_seaview.py`.

## §1 Shared measurement (same probe round as #703)

The density question is one question for both issues, answered by one
polite round (UA `home-finder-research/0.1`, `--max-time` 20–25,
paced, 429 = stop, raw in `/tmp/hf-lidar703/`, never committed):

| # | Check | Observed |
|---|---|---|
| 1 | Elevation catalogue `download-elevation-data-p664.html` | 200, 54 665 B; per-sheet raw LAZ open, no stated density |
| 2 | Estonian twin page `laadi-korgusandmed-alla-p614.html` | 200, 76 714 B; no density statement |
| 3 | Mass-download guidance article | 200, 27 698 B; documents the tile URL pattern (`andmetyyp=lidar_laz_tava`) |
| 4 | One tile GET `618641_2020_tava.laz` | 200, **15 973 699 B**, LAS 1.4, **N = 1 997 092** points |

Measured density **≈ 2.0 pts/m² (approximate)**: N over an inferred
~1×1 km footprint (header bounds slots are axis-inconsistent, so the
area is inferred from the two ~1000 m ranges, corroborated by the
16 MB file size). The tile is not a Tallinn sheet; no Tallinn sheet
of the normal flight, and no sheet of the denser spring low-altitude
product, was measured within probe budget.

## §2 Why insufficient for a sea viewshed

A per-building sea-visible boolean + quality needs a surface model
that resolves rooflines, tree crowns and shoreline walls along the
sight line. At ~2 pts/m² a coarse DSM leaks visibility through gaps
the buyer would see as blocked — the boolean would read "sea view"
where there is none. That is an invented viewshed, so the build leg
is refused (AGENTS.md §7.2).

## Overturn path (not wired here)

Verify a Tallinn sheet of the spring low-altitude product at ≥
~8 pts/m², or combine the per-sheet 1 m DTM with the Tallinn LoD2
CityGML (`dims_p4_maa_lidar.py` view-fan leg) — then re-open #712
with the measured sheet pasted here.

## PR independence note

This PR duplicates the measured numbers into its own carrier
(`probe_seaview.py`) instead of importing the #703 carrier, so both
PRs are green and mergeable independently. Once both land, a cleanup
may fold both carriers behind one import.
