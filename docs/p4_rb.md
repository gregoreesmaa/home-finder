# P4 RB: Rail Baltica Estonia verdict note (issues #281 + #355)

Demo (#281) implements the RB ingestion + P4-014 end-to-end;
coverage (#355) wires the P4-006 corridor-reservation leg off the
same ingestion. One PR closes both because the #355 body states
coverage "extends the demoed ingestion" with "no new plumbing
expected": the `corridors` table is a same-snapshot second table
(P4-006 source (6): "Rail Baltica/tram-corridor reservations
(Tallinn sections)"), not a second source.

Scope guard: sibling P4-006 legs stay in
`dims_p4_maa_kataster.dim_naaber_planeering` (kataster leg) and
`dims_p4_tpr.dim_pipeline_500m` (register leg) — untouched
(`livability.py`, WEIGHTS, all shared/group files unmodified;
3 new files only, `_rb`-suffixed keys, no double-scoring).

## Openness verdict: dated negative (2026-09-13, keeps per #281)

Rail Baltica Estonia publishes human pages and documents, but NO
open bulk endpoint for a machine-readable Ülemiste construction
timetable. Polite evidence, 7 tiny requests total (custom UA,
headers + two front pages + one 3 kB wp-json search, no scrape):

```
HEAD www.railbaltica.org/            -> HTTP 200, WordPress
wp-json search "Ulemiste"            -> 3.2 kB JSON, news posts only
  (tram-tunnel completion, Ülemiste–Lasnamäe start — no feed)
HEAD railbaltica.ee/                 -> HTTP 200 BUT Zone parking page
  ("Domain is Registered", 71 533 B, zero data links)
HEAD www.rbestonia.ee/               -> HTTP 200, implementer site
GET  rbestonia.ee/avalikud-andmed/   -> HTTP 200, 149 328 B: human
  document library (dokumendid/ehituse-seis/hanked/infokirjad),
  /naidissoidugraafik/ sample-passenger page, ArcGIS Experience
  Builder viewer (human map, no bulk). ".json" hits are WP plumbing.
```

Raw headers/pages: `/tmp/rb-open/` (one-off PR record, not committed).
Pull contract: max 1 download / 30 d per cache dir
(`RB_TTL_S = 2592000`, parameters4.md P4-014 TTL monthly,
expiry-dated; the P4-006 RB leg rides the same monthly ticket —
reservations change on project milestones, not weekly), single GET,
no retries — HTTP 429/errors are a stop signal. `RB_BULK_URL` stays
`None` until the checklist below names a verified bulk URL; until
then the fetcher performs no requests and the scorers stay NULL with
an Estonian EI OLE reason. Scored shapes are proven on fixtures only
(hermetic tests).

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-014 phase (demo) | `ehitusfaas_rb` | live timetable works ≤ 800 m | phase band: ehituses→35, planeerimisel→55, valmis→75 (`hinnang`, expiry printed) | no snapshot / no work POIs / all rows expired-unknown-future / unknown phase / beyond window |
| P4-006 corridor (RB leg) | `koridor_reserv_rb` | corridor ≤ 500 m | ≤150 m→30 doorstep, ≤500 m→55 pressure, measured clear→85 | no snapshot / no corridor POIs / no link (unknown, never clear) |

Measured values score; missing joins stay NULL. Beyond-window is
unknown, never calm/clear. Every scored reason says `hinnang` with
components (incl. `kehtib kuni` expiry); every NULL reason says
`EI OLE` and names the missing input.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #355 defines coverage as extending the
   demo ingestion — works + corridors tables, one snapshot.
2. Calendar dim takes an explicit valuation date (`today`, default
   real today): expiry is deterministic under test, honest in
   production. Rows without parseable `valid_until` are excluded
   (unknown expiry); unknown phase labels stay NULL.
3. Bands (35/55/75, 30/55/85) and the 800 m nuisance window are
   first-cut judgments with no live calibration; MUST be
   recalibrated from a real timetable on reopen.
4. P4-006 RB leg is `_rb`-suffixed and reservation-only: register +
   kataster legs untouched, no double-scoring.
5. No Overpass fragment / tag mapping staged: OSM has no honest tag
   for RB phases or reservations (group20a no-map precedent).
6. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches.

## Reopening checklist (when RB serves bulk data)

1. Re-run the probes above; paste fresh evidence.
2. Set `RB_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Recalibrate `PHASE_SCORES` / corridor bands from real data.
4. Add the explicitly-flagged live integration test (not a unit run).
