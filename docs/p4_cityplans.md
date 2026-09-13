# P4 cityplans: Tallinna strategic plans & stats verdict note (issues #282 + #356)

Demo (#282) implements the cityplans ingestion + P4-014 tram slice
end-to-end; coverage (#356) wires P4-006 + P4-019 + P4-025 + P4-037 +
P4-041 + P4-050 + P4-061 off the same ingestion. One PR closes both
because the #356 body states coverage "extends the demoed ingestion"
with "no new plumbing expected": the seven coverage tables are
same-snapshot second tables, not new sources (same pairing rationale
as the #281/#355 RB PR).

Scope guard: sibling legs untouched (`dims_p4_rb`, `dims_p4_emta`,
`dims_p4_rel2021`, `dims_p4_haridus`, `dims_p4_trans`,
`dims_p4_peatus`, `dims_p4_tlt`, `dims_p4_tpr`,
`dims_p4_maa_kataster`, `dims_p4_maa_aerial`, `dims_p4_ehr`,
`dims_p4_maa_tehingud`, shared/group files, `livability.py`, WEIGHTS
all unmodified; 3 new files only).

## Openness verdict: dated negative (2026-09-13, keeps per #282)

Tallinna strategic plans & stats live as human-facing CMS pages and
document libraries with NO open bulk endpoint. Polite evidence, ~7
tiny requests total (custom UA, headers + one 74 kB plan page, no
scrape):

```
HEAD tallinn.ee/et/uldplaneering   -> HTTP 301 to /et/kristiine/uldplaneering
HEAD tallinn.ee/et/arengukava      -> HTTP 301 to a district subsite
HEAD tallinn.ee/et/transpordi-arengukava -> HTTP 404 (no stable slug)
HEAD railbaltica.org/              -> HTTP 200 WordPress (press only)
HEAD tlt.ee/                       -> HTTP 301 to tlt.ee/ (WordPress)
GET  tallinn.ee/et/kristiine/uldplaneering -> HTTP 200, 74300 B,
  <title>Üldplaneering | Tallinn</title>, zero bulk links
```

Raw headers/page: `/tmp/cityplans-open/` (one-off PR record, not
committed). Pull contract: max 1 download / 30 d per cache dir
(`CITYPLANS_TTL_S = 2592000`, parameters4.md P4-014 TTL monthly,
expiry-dated; all coverage legs ride the same ticket — plan tables
change on milestones, not weekly; weekly P4-006 freshness stays with
the TPR leg), single GET, no retries — HTTP 429/errors are a stop
signal. `CITYPLANS_BULK_URL` stays `None` until the checklist below
names a verified bulk URL; until then the fetcher performs no
requests and the scorers stay NULL with an Estonian EI OLE reason.
Scored shapes are proven on fixtures only (hermetic tests).

## Honest shapes per param (calendar / choropleth / pipeline, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-014 tram works (demo) | `tramfaas_cityplans` | live tram row ≤ 800 m | phase: ehituses→35, planeerimisel→55, valmis→75, expiry-dated | no snapshot / expired or unknown expiry / unknown phase / beyond-window |
| P4-006 arenguala leg | `arenguala_cityplans` | arenguala ≤ 500 m | ≤200 m→50, ≤500 m→65, measured clear→85 | no snapshot / no arenguala POIs |
| P4-019 investment leg | `investeering_cityplans` | arengukava row ≤ 1500 m | trend kasv→75, stabiilne→60, kahaneb→40 (+invest figure) | no row / invest None / trend unknown |
| P4-025 forecast leg | `prognoos_cityplans` | prognoos row ≤ 1500 m | pop ≥+3→75, ≥0→65, ≥−3→50, else 35; suletakse −10, avatakse +5 (20..80) | no row / pop None |
| P4-037 planned-zone leg | `poliitika_kava_cityplans` | planned zone ≤ 600 m | ummikumaks_arutelu→45 (arutelu, mitte otsus), autovaba→50, tasuline_parkimine→60 | no row / unknown kind / beyond-window |
| P4-041 corridor leg | `vaatekoridor_cityplans` | corridor ≤ 300 m | inside→65 capped (säilimise tugi, mitte vaate garantii) | no corridor in window (never "clear") |
| P4-050 stats leg | `ehitusstat_cityplans` | stats row ≤ 1500 m | ratio ≤0.5→80, ≤1→60, ≤2→40, else 20; pipeline-only fallback flagged "ainult torustik" | no row / 0/0 gap / counts missing |
| P4-061 fringe leg | `aareala_teenus_cityplans` | settlement ≤ 2000 m | services 3→80, 2→60, 1→40, 0→25; bus_cuts −10 (floor 20) | no settlement in window |

Measured values score; missing joins stay NULL. Beyond-window is
unknown, never good. Every scored reason says `hinnang` with
components; every NULL reason says `EI OLE` and names the missing
input.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #356 defines coverage as extending the
   demo ingestion — eight tables, one snapshot, one TTL ticket.
2. Second P4-014 leg after #281: the RB PR scores the Ülemiste-works
   slice; this module scores the TRAM slice of the same param source
   list (Vanasadama/Pelguranna-Liivalaia + arengukava). Same calendar
   shape, bands, and 800 m footprint — consistency is deliberate —
   with `_cityplans` keys so slices never double-score.
3. P4-006 arenguala bands (50/65/85) are softer than the RB corridor
   leg (30/55/85): a development area is planning pressure, not a
   reserved corridor at the doorstep.
4. P4-019 scores the TREND with the invest figure as context;
   maamaks level stays in EMTA. P4-025 scores the forecast with the
   school plan as modulation; the REL2021 grid stays in rel2021.
5. P4-037 does not know the buyer's car dependence — the reason says
   so and points at EMTA. `ummikumaks_arutelu` is flagged as
   discussion, never decision.
6. P4-041 has no "clear" score: absence of a corridor is not a view
   verdict. The piilukas class stays in EHR/AER.
7. P4-050 mirrors the TPR ratio bands on coarser linnaosa grain
   (1500 m vs 1000 m, said in the reason); falling prices stay in
   tehingud. P4-061 mirrors the checklist idea with the GTFS diff
   staying in peatus.
8. All bands are first-cut judgments with no live calibration; MUST
   be recalibrated from a real snapshot on reopen.
9. No Overpass fragment / tag mapping staged: OSM has no honest tag
   for tram phases, budget rows, planned zones, or fringe
   checklists (group20a no-map precedent).
10. No shared-file edits; central hook (snapshot feed + WEIGHTS
    rebalance) stays one joint change across all batches.

## Reopening checklist (when Tallinn serves bulk plans/stats)

1. Re-run the HEAD/plan-page probes; paste fresh evidence.
2. Set `CITYPLANS_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Recalibrate `PHASE_SCORES` / `TREND_SCORES` / `GLUT_BANDS` /
   `FRINGE_BANDS` from real histograms.
4. Add the explicitly-flagged live integration test (not a unit run).
