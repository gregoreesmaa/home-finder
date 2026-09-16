# P4 typical traffic delay — probe verdict + table-schema note (issue #557)

> Verdict date: 2026-09-16 (docs + one polite capability check per
> path; no key requests beyond published self-serve; no 429).
> Code: `services/scoring/dims_p4_typical_delay.py` (gps.txt reader
> + aggregation + 1 delay leg); tests:
> `services/scoring/tests/test_dims_p4_typical_delay.py`
> (hermetic, fixture snapshots, no network).

## Buyer question

"How bad is the jam on my commute at 8:15" — answered as **typical
delay**, not live traffic. Live-jam map: non-goal (snapshot-frozen
product + buyer need).

## Probe (all three feed paths)

| Path | Result |
|---|---|
| Tark Tee DATEX II | **Gated** (reuses inspected `dims_p4_trans.py` evidence, 2026-09-13: driver-app shell, no keyless feed; DATEX II SRTI needs a registered key). No keyless typical-speed series — not re-probed, 3 days old |
| TomTom / HERE traffic APIs | **Key-gated** (docs half probed 2026-09-16: real-time + historical/stats products behind an API key; typical speeds live in the keyed products). Capability check needs a self-serve key — out of scope, no endpoint touched. Key from env only if ever pursued |
| Tallinn bus positions vs GTFS schedule | **Keyless angle PROVEN**: catalogue `…/api/datasets/slug/uhistranspordivahendite-asukohad-reaalajas` → HTTP 200 JSON, 5994 B, access PUBLIC, accrual CONT, org Tallinna Linnavalitsus. `https://transport.tallinn.ee/gps.txt` carries type/line/WGS84 position/speed/heading/vehicle every ~5 s, keyless. Buses sit in the same jams; GTFS headways (p11/p17) give the baseline for free |

## Outcome: documented partial-open (sampler deferred)

The keyless proxy source is confirmed, but no sampled typical-delay
table exists yet — building it needs a sampler cron (polite 60 s+
cadence → corridor × hour aggregation), which is deferred work, not
this issue. Static OSM road class + maxspeed legs stand (load, never
delay). No incident feed (accidents owned by #522).

## Delay-table schema (reviewer calls, documented)

Corridor grain = **named commute corridors** (not per-segment:
per-segment tables would re-identify bus runs and overfit). Hour
bands = hommikune tipp 7–9 / keskpäev 10–15 / õhtune tipp 16–18 /
muu. **No school-holiday split** (no calendar join — single table,
documented limitation). Factor = typical / free-flow (≥ 1.0).
**Missing hour/corridor → NULL** (never a free-flow assumption).

| Leg | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| Typical commute delay | `commute_delay` | corridor cell ≤ 500 m, matching hour band | factor ≤1.1→75, ≤1.3→60, ≤1.6→45, else 30 — "tavaline, mitte reaalajas" | no table join; hour missing; thin cell (< 20 samples); all gated feeds |

No live polling in the scorer path (harvested tables only); keys
from env, never committed; provider quotas enforced. Trams excluded
from aggregation (rails, not road jams).

## Judgment calls (for the reviewer)

1. Partial-open, not no-map: the bus proxy is one sampler cron away
   from real tables, so the schema + leg ship fixture-proven now.
2. Corridor grain over segments: privacy + robustness over
   precision, stated not hidden.
3. No livability.WEIGHTS splice here (joint follow-up). 3 new files
   only, zero shared-file edits.
