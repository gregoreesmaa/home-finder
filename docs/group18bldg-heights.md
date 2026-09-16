# G18 3D-height upgrade verdict (issue #547)

Closes #547 — measured building heights from 3D LoD1/LoD2.

Code: `services/scoring/dims_group18bldg.py` (2 upgrade dims +
shade/ehr helpers); tests:
`services/scoring/tests/test_dims_group18bldg.py` (hermetic, fixture
artefacts, no network).

## 1. Polite probe (2026-09-16, UA `home-finder-idea-probe/1.0`)

Metadata page only (no bulk download — the 33 MB zip stays on the
server until the annual bulk-job day):

| Check | Result |
|---|---|
| URL | `https://geoportaal.maaruum.ee/eng/spatial-data/download-3d-data-p837.html` |
| Result | **OPEN.** HTTP 200, 778 287 B, ~0.45 s. No 429, no key. |
| LoD1 refs | 1027 (`hooned_lod1` per-municipality citygml/gdb/obj) |
| LoD2 refs | 1012 (`hooned_lod2` same matrix) |
| Tallinn | `hooned_lod2-Tallinn-{citygml,gdb,obj}.zip` all present |
| Last update | 29.04.2026 (yearly Q1 recompute — matches catalogue) |
| Licence | CC BY 4.0 (catalogue claim; page links the open-data terms) |

Harjumaa/Tallinn building counts, ALS-year distribution and ehr_gid
fill rate need the bulk parse (GDB/CityGML → GDAL-class tooling, stated
dependency for the harvest script); `ehr_link_rate()` ships here so the
job reports the rate instead of hand-waving it. Per-feature attributes
(etak_id, ehr_gid, ads_oid, z_min/z_max EH2000, type, ALS year) are the
catalogue claim the bulk job validates on first parse.

## 2. One-building worked example (footprint + z_max → shade sketch)

27.5 m slab (typical Lasnamäe 9-storey, LoD1 z_max), winter sun
altitude 12° (stated dull middle for Tallinn December), azimuth 180°
(south): shadow length = 27.5 / tan(12°) ≈ **129.4 m due north**
(`shade_polygon(27.5, 180.0)` → `{dx 0.0, dy +129.4, length 129.4}`,
pinned by test). An 18 m garden setback sits deep inside the shadow —
the pipeline goes from footprint polygon + one z_max to a directional
shade vector in one pure function, before any county run.

## 3. Old-cap → new-cap justification + pre/post shape

| Leg | Old geometry cap | New measured cap | Evidence |
|---|---|---|---|
| Shade (p405) | 20 m+ footprint bands, no direction | shadow = h × 4.7 (12°), bands on h ≤9/15/25 m | Worked example: 27.5 m throws 129 m — the old 20 m band never saw it. LoD1 parapet overstatement absorbed by the hinnang cap (worst = 25, never survey-grade). |
| Overlook (p468) | distance-only bands | h ≥20 & d ≤30 → 35; h ≥10 & d ≤50 → 55 | Height gates the band (an 8 m house at 40 m scores 75, a 27.5 m slab at 18 m scores 35). |

Pre/post Tallinn-window histogram: fixture shape test
(`test_upgrade_discriminates_tallinn_window_shape`) — six fixture
heights at fixed 10 m setback spread three score bands where the
footprint-only guess gives one. Synthetic shape check, labelled; the
real county histogram runs in the bulk job.

EHR/address join path: `ehr_gid`/`ads_oid` ride the artefact untouched
(the #234/#537 + AKS join, recorded here, never rebuilt).

## 4. Judgment calls for the reviewer

1. LoD1-first (flat-roof max): overstates parapet shade → capped
   hinnang in title, legend, and every reason; LoD2 roof shapes only
   where they improve it (artefact records the winning LOD).
2. No building within 100 m → 90, not NULL (absence of a tall
   neighbour IS the shade/privacy signal).
3. ALS year in every reason (heights stale where building continues);
   unknown year flags, never mixes silently.
4. No WEIGHTS/livability/layers edits (joint-rebalance precedent).

## 5. DoD evidence

```text
python3 -m pytest services/scoring/tests/test_dims_group18bldg.py -q
# → 9 passed (observed 2026-09-16, worktree 547-3d-heights)
python3 -m pytest services/scoring/tests -q
# → full suite green, no regressions (see PR checks)
```
