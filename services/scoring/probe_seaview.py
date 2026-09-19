"""Verdict carrier for #712 sea-view viewshed probe (PROBE, not build).

Shares the Maa-amet point-cloud density question with #703 (same open
per-sheet LAZ, same probe round 2026-09-19 — see docs/p4_seaview.md),
but carries its own verdict so the #712 PR stays independent of the
#703 PR: no shared new files, no merge coupling. A future cleanup may
fold both carriers behind one import once both PRs land.
"""

#: Machine-checkable verdict. `kind` is one of "negative" | "positive".
#: `checked` is ISO date. `density_pts_m2` repeats the #703 measured
#: tile density (approximate — see docs/p4_seaview.md §1).
SEAVIEW_VERDICT = {
    "kind": "negative",
    "checked": "2026-09-19",
    "source": "shared Maa-amet density round with #703 (/tmp/hf-lidar703 "
               "only): elevation catalogue + guidance-article tile URL "
               "pattern + one LAZ tile GET (lidar_laz_tava)",
    "tile": "618641_2020_tava.laz (lidar_laz_tava normal flight)",
    "tile_bytes": 15973699,
    "tile_points": 1997092,
    "density_pts_m2": 2.0,
    "density_note": "approximate: N=1997092 over an inferred ~1x1 km "
                    "footprint (header bounds slots axis-inconsistent); "
                    "the tile is not a Tallinn sheet",
    "note": "A coarse ~2 pts/m2 DSM overestimates through-gap "
            "visibility, so a per-building sea-visible boolean off this "
            "product would be an invented viewshed; no Tallinn sheet "
            "measured within probe budget. No heavy compute.",
    "follow_up": None,
}
