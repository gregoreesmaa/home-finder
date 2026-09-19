"""Verdict carrier for #703 Maa-amet lidar density probe (PROBE, not build).

Shared verification for #703 (sunlight) and #712 (sea viewshed): does
the open Maa-amet point cloud cover Tallinn at density sufficient for
per-building shadow/viewshed analysis? Verdict: INSUFFICIENT
(2026-09-19) — see docs/probe_lidar.md for the full evidence table.
"""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `density_pts_m2` is the measured tile density
#: (approximate — header bounds slots are axis-inconsistent, see note).
LIDAR_VERDICT = {
    "kind": "negative",
    "checked": "2026-09-19",
    "source": "polite Maa-amet Geoportaal checks (/tmp/hf-lidar703 only): "
               "elevation download catalogue + mass-download guidance "
               "article + one LAZ tile GET (server ignored Range, sent "
               "full ~16 MB once — one-off, not repeated, never committed)",
    "tile": "618641_2020_tava.laz (lidar_laz_tava normal flight)",
    "tile_bytes": 15973699,
    "tile_points": 1997092,
    "density_pts_m2": 2.0,
    "density_note": "approximate: N=1997092 over an inferred ~1x1 km "
                    "footprint (header carries two ~1000 m ranges but in "
                    "inconsistent axis slots, so the area is inferred, "
                    "not read); the tile is not a Tallinn sheet",
    "note": "Open per-sheet LAZ serves keyless, but the measured "
            "normal-flight density (~2 pts/m2 approx) does not resolve "
            "facades/rooflines for per-facade sun hours (#703) or "
            "reliable per-building sea viewsheds (#712); no Tallinn "
            "sheet of either the normal or the denser spring "
            "low-altitude product was measured within probe budget. "
            "No heavy compute, no invented viewsheds.",
    "follow_up": None,
}
