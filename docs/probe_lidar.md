# Probe: Maa-amet point-cloud density for sun/viewshed (#703, shared with #712)

**Verdict (2026-09-19): INSUFFICIENT — dated negative.** The open
Maa-amet point cloud does not verify at density sufficient for
per-building shadow (#703) or sea-viewshed (#712) analysis. No heavy
compute, no invented viewsheds. Verdict carrier:
`services/scoring/probe_lidar.py` (`LIDAR_VERDICT`), guard:
`services/scoring/tests/test_probe_lidar.py`.

## Method (polite, /tmp only)

UA `home-finder-research/0.1`, `--max-time` 20–25, paced ≥ 3 s,
429 = stop (no 429 seen). Raw bodies in `/tmp/hf-lidar703/`, never
committed. Four requests total:

| # | Check | Observed | Meaning |
|---|---|---|---|
| 1 | `GET geoportaal.maaruum.ee/.../download-elevation-data-p664.html` | 200, 54 665 B; per-map-sheet raw LiDAR (spring low-altitude, summer forestry, surface keypoints) + DTM/DSM/CHM; update 29.04.2026 | Catalogue confirms per-sheet open LAZ, states **no density** |
| 2 | `GET .../laadi-korgusandmed-alla-p614.html` (Estonian twin) | 200, 76 714 B; same JS map-number form | No density statement either |
| 3 | `GET .../kuidas-on-voimalik-palju-kaardilehti-korraga-alla-laadida/86` (mass-download guidance) | 200, 27 698 B; documents the tile URL pattern `index.php?...&kaardiruut=N&andmetyyp=lidar_laz_tava&dl=1&f=N_2020_tava.laz` | Gives a real tile URL with zero guessing |
| 4 | `GET` (ranged 0–4095, server ignored Range) the guidance article's example tile `618641_2020_tava.laz` | 200, **15 973 699 B** full file, `LASF` signature, LAS 1.4, header 375 B, **N = 1 997 092** points | One tile measured; the 16 MB one-off overage was the server ignoring Range — not repeated |

## Measured density

- Points: 1 997 092 (LAS 1.4 extended count; legacy count zeroed by writer).
- Footprint: the header bounds slots are axis-inconsistent (max < min,
  a northing-scale value in the Z slot), so the area is **inferred**:
  the header carries two ~1000 m ranges → ~1×1 km sheet → **≈ 2.0
  pts/m² (approximate)**. File size corroborates: 16 MB LAZ ≈ 2 M
  points ≈ 1–2 km² of raw ALS, not a 25 km² sheet.
- Tallinn coverage: **unverified** — sheet 618641 is not a known
  Tallinn sheet (easting slot reads ~641 km, i.e. eastern Estonia);
  no Tallinn sheet of the normal flight, and no sheet at all of the
  denser spring low-altitude product, was measured within probe budget
  (deriving a Tallinn sheet number needs the interactive kartogram —
  beyond the polite budget).

## Why insufficient

Per-**facade** sun hours (#703) need sub-metre wall/roofline geometry;
~2 pts/m² (≈ 0.7 m mean spacing) does not resolve facades. A coarse
DSM viewshed at that posting overestimates through-gap visibility, so
a per-building sea-visible boolean (#712) off this product would be an
invented viewshed. Two independent gaps (density + Tallinn coverage)
→ negative on both issues.

## Overturn path (not wired here)

Verify a Tallinn sheet of the spring low-altitude (`madal`) product
at ≥ ~8 pts/m², or combine the per-sheet 1 m DTM with the Tallinn
LoD2 CityGML already covered by `dims_p4_maa_lidar.py` — then re-open
#703/#712 with the measured sheet pasted here.
