# P4 building-era mix — gate verdict + taste-leg note (issue #555)

> Verdict date: 2026-09-16 (no new probe — reuses the inspected #537
> evidence, commit `7424533`, probed the same day; re-hammering the
> same unrouted base would be impolite).
> Code: `services/scoring/dims_p4_era.py` (aggregation + 2 taste legs);
> tests: `services/scoring/tests/test_dims_p4_era.py`
> (hermetic, hand-built year records, no network).

## Source (same as #537 — this is its second leg, not a new source)

- EHR avaandmed API (`swaggerui.ehr.ee`, CC_BY_SA_3.0, DAILY) —
  prerequisite: #537 proves the backfill reachable first.

## Gate: #537 backfill proven + build-year field confirmed? NO

#537's probe (see `docs/ehr_backfill.md` on branch
`537-ehr-backfill`): the EHR Avaandmete live base is **UNROUTED**
(`https://livekluster.ehr.ee/api/av/v1/version` and
`…/alus/reports` → HTTP 404 "default backend"). No anonymous
per-`ehr_code` query is reachable, so **no build-year field
(ehitusaasta / esmane kasutus) could be confirmed and no Harjumaa
fill rate measured** — the pipe is dry, not the field. Per this
issue's contract ("no field, no issue") production joins stay NULL
with the gate reason; the aggregation below is fixture-proven for
the day the route is restored. No fetcher ships (nothing unverified
is ever fetched).

## Honest shapes (taste + price-covariate, never condition)

| Leg | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| Old-charm delight | `old_charm` | nearest mix ≤ 500 m | pre-1945 share: ≤0.1→35, ≤0.25→50, ≤0.4→60, else 70 (capped; era ≠ condition) | no mix join; thin area (< 5 houses); gate closed |
| New-build delight | `newbuild` | nearest mix ≤ 500 m | post-1990 share: ≤0.15→35, ≤0.35→50, ≤0.5→60, else 70 (capped; era ≠ condition) | same |

Character overlay first: `era_character` (puitasum / paneel /
uusasum / sega, thresholds 0.4 / 0.5 / 0.5 over year-known stock)
carries no score field. Aggregation grain: asum / micro-area with
≥ 5 year-known buildings — era mix must never identify single
houses, so thinner areas stay NULL and per-house display stays out.
Era-band cuts (1945 / 1990) read the Harjumaa stock: pre-1945 wooden
town (Kalamaja/Pelgulinn), 1945–1990 serial/panel mass housing
(Lasnamäe/Õismäe/Mustamäe), post-1990 sprawl + infill (Viimsi/Rae).

## Judgment calls (for the reviewer)

1. Gate-unmet close with dims anyway: the task contract wants the
   verdict + fixture-proven aggregation so the #537 reopen wires
   records straight into `aggregate_era_mix` with no scorer changes.
2. No condition claims from era (pinned "ajastu pole seisukord" in
   every scored reason); renovation grants (#538) stay the condition
   cousin; heritage designations stay authoritative.
3. No livability.WEIGHTS splice here (joint follow-up). 3 new files
   only, zero shared-file edits, EHR files untouched.
