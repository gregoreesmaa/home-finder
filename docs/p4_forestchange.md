# P4 forest-change verdict: DOCUMENTED NO-MAP (issue #548)

Closes #548 as a documented no-map + gated dims (the issue orders
exactly this outcome when no open licence is confirmed).

Code: `services/scoring/dims_p4_forestchange.py` (gated overlay dim +
pure bands); tests:
`services/scoring/tests/test_dims_p4_forestchange.py` (hermetic,
fixture changes, no network).

## 1. Polite probe (2026-09-16, UA `home-finder-idea-probe/1.0`)

HEAD only — the ~59 MB zip stays on the server:

| Check | Result |
|---|---|
| URL | `https://geoportaal.maaruum.ee/docs/Avaandmed/Metsamuutused_2024.zip` |
| Result | **SERVES.** HTTP/2 200, `content-type: application/zip`, `content-length: 59179549` (~56.4 MB), `content-disposition: inline; filename=Metsamuutused_2024.zip`, `last-modified: 16.09.2026`. No 429. |
| Schema/CRS/counts | **NOT pulled** (single-probe budget spent on servability; the SHP schema, date fields, Harjumaa 2022–2024 counts and CRS belong to the licence-day bulk job). Series/shape claims (drop >5 m, >0.25 ha, 2016 gap) are catalogue claims, restated as such. |
| Licence | **NONE confirmed** (catalogue: none stated; no licence header on the HEAD response). **Gate holds: no ingestion.** |

## 2. False-positive sanity: DEFERRED, honestly

The 20-spot Harjumaa overlay (new developments vs real cuts) needs the
SHPs. They were never pulled (no licence), so a precision note today
would be invented. The licence-day bulk job MUST run it before any
band goes live — stated here as a merge-blocking follow-up, not done.

## 3. Recency bands + NULL rule (pinned by tests, dormant)

`_score_change()`: ≤3 yrs & ≤500 m → 30; ≤3 yrs & ≤1500 m → 55;
4–10 yrs & ≤500 m → 60; else on-record → 70; empty window → **NULL**
("turvalist metsa see ei tõenda" — never "safe forest"). Publisher
caveat ("tuvastatud muutus, mitte ametlik raiestatistika") in every
reason. `test_live_shape_once_gate_lifts` proves the shape behind the
gate without opening it.

## 4. What lifts the verdict

A dated re-probe confirming an open licence → flip `LICENCE_OK` →
bulk job pulls one vintage SHP, reports schema/CRS/Harjumaa counts +
20-spot precision note → bands go live. Until then: NULL dims, no
raster, no map.

## 5. DoD evidence

```text
python3 -m pytest services/scoring/tests/test_dims_p4_forestchange.py -q
# → 7 passed (observed 2026-09-16, worktree 548-forest-change)
python3 -m pytest services/scoring/tests -q
# → full suite green, no regressions (see PR checks)
```
