# Flood Harju-coverage verdict (issue #518)

Buyer report: flood-risk layer reads empty in Tallinn. The KAUR
sidecar holds 2 REAL zones (Mullutu-Suurlaht, Suur-Emajõgi — both
outside Harjumaa): Tallinn reads honest-empty, correctly but
uselessly.

## Verdict: DOCUMENTED COVERAGE GAP (no Harju harvest exists)

Harju probe 2026-09-16 (2 tiny WFS hits requests, labelled
one-off UA `home-finder-518-flood-harju/1.0`, paced, ~1 kB bodies,
no scrape, no bulk pull; HTTP 429 never seen):

| Check | Observed | Meaning |
|---|---|---|
| `GetFeature resultType=hits`, `eelis:kr_yleujutusohuga_ala`, Harju BBOX (lat 58.9–59.7, lon 23.3–25.6: Pirita catchment + Tallinn coast) | `numberMatched="0"`, `timeStamp 2026-09-16T02:40Z` | ZERO open-register polygons for every Harju water body |
| Sidecar zones | Mullutu-Suurlaht + Suur-Emajõgi, both outside Harjumaa | nothing to install for Tallinn; nothing invented |

Tallinn stays honest-empty. The layer's open register family
(single constant tyyp `Suurte üleujutusohuga siseveekogu`) covers
NEITHER the riverine/spring-thaw family (Pirita 10/50/100-yr)
NOR — in Harju — the coastal-surge family in this source. The
andmed-eesti coastal mirror entry stays OPEN (no local mirror copy
in this repo to check against; next probe).

## What ships (3 new files, no shared edits)

* `services/scoring/dims_flood_harju.py` — gap record:
  `coverage_legend` builds the legend note (echoes ONLY sidecar
  zone names present in the input, then states the Harju/Tallinn
  gap dated); `probe_harju_hits` is the one-query 2027 re-check
  (transport errors → None, never a zero, never cached).
* `services/scoring/tests/test_dims_flood_harju.py` — 12 hermetic
  tests (stubbed probe incl. error paths; legend pins: no invented
  Tallinn zones, fiction skipped, gap sentence always present).
* This note.

Wiring the legend copy into `apps/web/lib/layers_flood.ts` stays
an explicit follow-up (shared-file edit, out of scope here).

## Judgment calls (for the reviewer)

1. One Harju BBOX instead of per-stretch queries: the register has
   16 objects nationally and zero in the wider Tallinn window, so a
   single county bbox answers the coverage question with minimum
   load. Per-stretch family mapping waits on the coastal mirror.
2. `probe_harju_hits` parses `numberMatched` only — a count is not
   data and is never stored.

## Reopening checklist

1. Check the andmed-eesti coastal mirror for Tallinn-coast
   polygons; record per stretch which family covers it.
2. Re-run `probe_harju_hits`; if Harju > 0, pull the GML and
   rebuild the sidecar (real polygons only, never invented).
3. Wire `coverage_legend` into the floodzone legend. Re-check no
   later than **2027-03-16**.
