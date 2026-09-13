# P4 peatus: Peatus.ee GTFS verdict note (issues #314 + #376)

Demo (#314) implements the Peatus.ee GTFS ingestion + P4-061 end-to-end;
coverage (#376) wires the remaining 4 params off the same ingestion.
One PR closes both because the #376 body states it extends the demo
ingestion — the evening/Saturday windows and the prev-vintage diff are
same-zip extensions, no new source.

## Openness verdict: dated negative (2026-09-13, keeps per #314)

`https://peatus.ee/gtfs/gtfs.zip` (parameters3.md §5.12 URL) does NOT
currently serve a GTFS zip. Polite evidence, 3 tiny requests total
(custom UA, headers + one 601-byte range peek, no scrape):

```
HEAD /gtfs/gtfs.zip         -> HTTP/2 302, location: /reitti/gtfs/gtfs.zip
HEAD /reitti/gtfs/gtfs.zip  -> HTTP/2 200, content-type: text/html, 1311 bytes
GET  bytes 0-600            -> <title>Rakendus on suletud</title> (app closed)
```

Raw headers: `/tmp/peatus-gtfs-head*.txt` (one-off PR record, not committed).
Pull contract: max 1 download / 24 h per cache dir (`GTFS_TTL_S = 86400`,
parameters3.md cadence: daily cron 03:30 UTC), single GET, no retries —
HTTP 429/errors are a stop signal. Transport errors are never cached as
data; the scorers stay NULL with an Estonian EI OLE reason until the feed
reopens. Scored shapes are proven on fixtures only (hermetic tests).
Stop positions meanwhile ride the `gtfsstops` point overlay (#483):
TLT-city stops from the snapshot GTFS vintage
`gtfs/tallinn-gtfs-2026-09-11.zip` (scheduled Wednesday departures as
marker size); regional stops beyond that vintage stay unplotted and
evening ridership stays NULL — the overlay shows schedules, never
occupancy.

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-061 bus-cut tracker | `bus_cut` | nearest stop ≤ 1500 m | cut-fraction band: ≤ −30% → 20, < −10% → 45, ≤ +10% → 70, else 90; prev 0 + cur>0 = new service 90; 0/0 = persistent gap 20 | single vintage (no prev/cur), no stop in window |
| P4-037 policy exposure | `policy_exposure` | ≤ 750 m | Wednesday-deps offset band (group-12 anchored: 0→20 … ≥150→100); GTFS half only, never a full exposure verdict | no Wednesday table / join |
| P4-045 third places | `third_places` | ≤ 750 m | Wednesday deps ≥ 18:00 band (0→20 … ≥20→100); access leg only | no evening window |
| P4-048 small delights | `delights_access` | ≤ 1125 m (= 15 min × 75 m/min) | walk-distance band (≤300→100 … ≤1125→55); distance-only, bird-flight, marsruutimata | no stop in the 15 min window |
| P4-049 taxi/guest | `guest_arrival` | ≤ 750 m | Saturday-deps band (0→20 … ≥40→100); access leg only | no Saturday window |

Measured zero (deps == 0 from GTFS) scores low — a real no-service
signal; missing join (deps None) stays NULL. Beyond-window is unknown,
never 0. Every scored reason says `hinnang` with components; every NULL
reason says `EI OLE` and names the missing input.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: the #376 body defines coverage as
   extending the demo ingestion — nothing here needs a second source.
2. Exposure bands reuse the 2026-09-12 group-12 Wednesday calibration
   (median 138, p10 42) un-remeasured: the feed is closed, so
   recalibration is impossible — stated, not hidden.
3. Evening/Saturday bands are first-cut judgments with no prior
   calibration; they MUST be recalibrated from a real vintage on reopen.
4. P4-048 scores on stop positions before the frequency join lands
   (<15 min access is a walk fact) — pinned by test.
5. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   nomap.md, parameters4.md untouched): 3 new files only. Central hook
   (Overpass fragment + `_POI_KIND` + WEIGHTS rebalance) stays one joint
   change across all batches.

## Reopening checklist (when peatus.ee serves a zip again)

1. Re-run the HEAD/peek probes; paste fresh evidence in the reopen PR.
2. Pull one vintage into the cache dir; build Wed/eve/Sat sidecars.
3. Recalibrate `EVENING_BANDS` / `SAT_BANDS` from real histograms.
4. Add the explicitly-flagged live integration test (not a unit run).
