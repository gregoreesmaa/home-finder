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

## #629 sampler + corridor layers (built 2026-09-17)

**Parse correction (load-bearing):** the live feed carries LONGITUDE
first (`2,1,24841420,59519450,...` = bus 1 to Viimsi at
24.84142/59.51945) — the catalogue description had lat/lon swapped
and the #557 parser read ZERO live rows (verified: 0/384 before,
384/384 after). Live rows carry 10 fields and NO speeds (0/384 rows
with speed), so delay factors come from **vehicle-tracked segment
speeds** (same vehicle, consecutive pulls, 30–900 s apart, 3–80 km/h),
not the speed column.

**Sampler** (`scripts/build/batch_delay_sampler.py`): `--pull` (one
polite snapshot per cron tick, 60 s cadence guard, timestamped
cache) + `--build` (fixes → segments → corridor×hour medians →
free-flow = off-peak "muu" median per corridor → factors ≥ 1.0 →
`delay/delay-corridors.json` with scorer POIs + map strips + GTFS
stop-nearby validation). Cron hosts MUST run TZ=Europe/Tallinn
(hour bands are Tallinn wall-clock; tests anchor local-midnight so
they pass in any host TZ).

**Live proof 2026-09-17:** 3 pulls ~70 s apart → 1015 fixes → 186
segments across all 8 corridors (p50 16.9 km/h, plausible urban bus)
→ 0 table cells (honestly thin: 3 snapshots cannot reach n=20 with
a free-flow baseline — NULLs, never assumed factors).

**Corridors** (#667: the full GTFS shape web, NOT the 8 legacy
streets): every trip shape_id is a corridor (name "short ·
headsign", e.g. "5 · Männiku"), geometry = ±150 m ribbon along the
shape polyline (road-following by construction — shapes ARE the
driven roads, so sea overlap is gone by construction), join =
nearest shape within the 500 m window (bbox-prefiltered). Legacy 8
survive only as the GTFS-less fallback. Validation = weekday stops
nearby per shape.

**Map** (approved 5-layer design): delay-morning/midday/evening/
offpeak/worst (`apps/web/lib/layers_p4_delay.ts` + areas route +
DELAY-HOOK blocks). Off-peak shows the measured free-flow anchor
(factor 1.0 where n≥20); worst = max over peaks. Fills mirror the
scorer bands; thin cells slate mõõtmata; every label carries
"tavaline, mitte reaalajas".

**Sampler host (recorded decision):** scheduled GitHub workflow
REJECTED (60 s+ cadence pulls with artefact round-trips are the
wrong tool); production = container cron sidecar (compose
follow-up), research = maintainer machine. No school-holiday split
(unchanged limitation).
