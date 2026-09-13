# P4 EGT: engineering-geology verdict note (issues #288 + #361)

Demo (#288) implements the EGT ingestion + P4-016 end-to-end;
coverage (#361) wires the P4-054 EGT-deposit leg off the same
ingestion. One PR closes both because the #361 body states coverage
"extends the demoed ingestion" with "no new plumbing expected": the
`quarries` table is a same-snapshot second table (P4-054 source (5):
"EGT geoloogia kaardid (quarry proximity)"), not a second source.

Scope guard: sibling P4-016/P4-054 legs stay in
`dims_p4_maa_subsurface` (WFS per-parcel containment joins +
deposit-polygon buffer, #248/#332 merged PR #394) — untouched; the
EGT radon-risk map stays with overturn issue #238 (parameters3 G7 —
`dims_group07*.py` and every shared/group file unmodified; 3 new
files only, `_egt`-suffixed keys, no double-scoring).

## Openness verdict: dated mixed (2026-09-13, keeps per #288)

EGT publishes human pages + an open viewer + downloads, but NO open
machine-readable bulk endpoint for per-parcel engineering-geology
classes. Polite evidence, 5 tiny requests total (custom UA, ≥3 s
pacing, headers + two front pages + one 404 sub-URL, no scrape):

```
HEAD www.egt.ee/                  -> HTTP 200 (Drupal, Cloudflare)
GET  www.egt.ee/                  -> HTTP 200, 145 109 B: "Ruumiandmed
  ja kaardid", "Teenused", "allalaadimiseks", geoportaal links; map
  rendering points at teenus.maaamet.ee OWS WMS — no EGT bulk API
HEAD gis.egt.ee/geoportaal/       -> HTTP 200
GET  gis.egt.ee/geoportaal/       -> HTTP 200, 21 195 B, "Avamus - EGT
  Geoportaal" (open viewer; shell holds no WFS/WMS/ArcGIS/download
  tokens)
GET  egt.ee/et/ruumiandmed-ja-kaardid -> HTTP 404 (offering known via
  #248 evidence: ruumiandmed "teenuste ja allalaaditavate failidena"
  under a data licence with a scale-class caveat — downloads, not a
  per-parcel API)
```

Raw headers/pages: `/tmp/egt-open/` (one-off PR record, not committed).
Pull contract: max 1 download / 365 d per cache dir
(`EGT_TTL_S = 31536000`, parameters4.md P4-016 TTL annual bulk; the
P4-054 EGT leg rides the same annual ticket — deposit data changes
on survey/register milestones, not weekly), single GET, no retries —
HTTP 429/errors are a stop signal. `EGT_BULK_URL` stays `None` until
the checklist below names a verified bulk URL; until then the
fetcher performs no requests and the scorers stay NULL with an
Estonian EI OLE reason. Scored shapes are proven on fixtures only
(hermetic tests).

Note: the EGT front-page nav lists "Looduslik radoonirisk" as an
activity — radon stays with #238, not scored here.

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-016 EGT class (demo) | `pinnas_klass_egt` | EGT map class ≤ 500 m (coarse) | karst→30, turvas→35, alvar→55, kandev→70 capped (`hinnang`, `jäme`) | no snapshot / no class POIs / unknown klass label / beyond window |
| P4-054 EGT deposit (coverage) | `karjaar_egt` | EGT quarry ≤ 2 km | ≤500 m→25 doorstep, 500 m–2 km→45 coarse (timetable EI OLE named) | no snapshot / no quarry POIs / beyond 2 km (unknown, never quiet) |

Measured values score; missing joins stay NULL. Beyond-window is
unknown, never good/quiet. Every scored reason says `hinnang` (+
`jäme` coarse marker); every NULL reason says `EI OLE` and names the
missing input. Bands mirror `dims_p4_maa_subsurface` so the two legs
of each param read consistently.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #361 defines coverage as extending the
   demo ingestion — classes + quarries tables, one snapshot.
2. 500 m EGT-class window is the coarse-map judgment (EGT licence
   scale caveat): neighbourhood grain here, exact per-parcel
   containment stays the WFS leg in subsurface — different keys,
   different grains, no double-scoring.
3. Bands (30/35/55/70 capped, 25/45) mirror the subsurface legs
   first-cut with no live calibration; MUST be recalibrated from
   real EGT classes on reopen.
4. P4-054 beyond-2 km is NULL, never quiet: a deposit point is not
   an active mine and the blast timetable is not open (negative
   carried from #248, named in every reason).
5. No Overpass fragment / tag mapping staged: OSM has no honest tag
   for EGT map-sheet classes or blast seasons (group20a no-map
   precedent).
6. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches.

## Reopening checklist (when EGT serves per-parcel bulk data)

1. Re-run the probes above; paste fresh evidence.
2. Set `EGT_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Recalibrate `KLASS_SCORES` / quarry bands from real EGT classes.
4. Add the explicitly-flagged live integration test (not a unit run).
