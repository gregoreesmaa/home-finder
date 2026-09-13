# P4 TPR: Tallinna planeeringute register verdict note (issues #250 + #334)

Demo (#250) implements the TPR ingestion + P4-006 end-to-end;
coverage (#334) wires P4-005 + P4-050 off the same ingestion.
One PR closes both because the #334 body states coverage "extends
the demoed ingestion" with "no new plumbing expected": the `areas`
table is a same-snapshot second table, not a second source.

Scope guard: overturn #236 owns PLANK/TPR for parameters3 Group 5
this-parcel zoning — untouched (`dims_group05*.py`, shared/group
files, `livability.py`, WEIGHTS all unmodified; 3 new files only).

## Openness verdict: dated negative (2026-09-13, keeps per #250)

`https://tpr.tallinn.ee/` is a human-facing web register with NO open
bulk endpoint. Polite evidence, ~5 tiny requests total (custom UA,
headers + one 83 kB front page, no scrape):

```
HEAD tpr.tallinn.ee/                    -> HTTP 200, Apache, text/html (83331 B)
GET  tpr.tallinn.ee/                    -> <title>Tpr</title> Angular SPA
HEAD tpr.tallinn.ee/main-*.js           -> application/javascript, 3960409 B
                                          (size probe ONLY — not downloaded)
PLANK WFS planeeringud.ee/geoserver/wfs -> HTTP 301 to
  livekluster.ehr.ee/.../PLANNINGS_SEARCH (E-ehitus SPA; old endpoint gone)
```

Raw headers/page: `/tmp/tpr-open/` (one-off PR record, not committed).
Pull contract: max 1 download / 7 d per cache dir
(`TPR_TTL_S = 604800`, parameters4.md P4-006 TTL weekly; P4-050
quarterly counts ride the same weekly ticket), single GET, no retries —
HTTP 429/errors are a stop signal. `TPR_BULK_URL` stays `None` until
the checklist below names a verified bulk URL; until then the fetcher
performs no requests and the scorers stay NULL with an Estonian EI OLE
reason. Scored shapes are proven on fixtures only (hermetic tests).

## Honest shapes per param (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-006 pipeline (demo) | `pipeline_500m` | menetluses plans ≤ 500 m | count band: 0→90, 1→65, 2–3→40, ≥4→20 | no snapshot / no plan POIs / origin missing |
| P4-005 permit existence (TPR leg) | `permit_existence_tpr` | kehtestatud plan ≤ 150 m | presence 75 capped (EHR-ristkontroll puudub) | no kehtestatud+permits link (unknown, never 0) |
| P4-050 glut vs completions (TPR leg) | `permit_glut_tpr` | area row ≤ 1000 m | ratio pipe/done: ≤0.5→80, ≤1→60, ≤2→40, else 20; pipeline-only fallback 0→85 … >200→25 flagged "ainult torustik" | no area row / 0/0 gap / counts missing |

Measured zero scores (0 menetluses in buffer with plans elsewhere;
`pipeline_units == 0` row); missing join stays NULL. Beyond-window is
unknown, never 0. Every scored reason says `hinnang` with components;
every NULL reason says `EI OLE` and names the missing input.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #334 defines coverage as extending the
   demo ingestion — the plans + areas tables come from one snapshot.
2. Pipeline counts ONLY `stage == "menetluses"` (parameters4.md
   wording); algatatud/vastuvõetud labels are NOT counted until
   verified live — conservative, pinned by test.
3. P4-006 bands (90/65/40/20) are a first-cut judgment with no live
   calibration; MUST be recalibrated from a real snapshot on reopen.
4. P4-005 is presence-only 75|None: a missing TPR link is not proof of
   no permit. Bankability stays in `dims_p4_ehr.dim_permit_bankable`;
   falling prices stay in `dim_permit_glut_price_leg` (tehingud leg) —
   `_tpr`-suffixed keys, no double-scoring. The EHR P4-050 NULL
   ("needs a quarterly micro-area table") is exactly the gap the TPR
   areas table fills on its leg.
5. No Overpass fragment / tag mapping staged: OSM has no honest tag
   for TPR menetlus stages (group20a no-map precedent).
6. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches.

## Reopening checklist (when TPR serves bulk data)

1. Re-run the HEAD/front-page probes; paste fresh evidence.
2. Set `TPR_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Recalibrate `PIPELINE_BANDS` / `GLUT_BANDS` from real histograms.
4. Add the explicitly-flagged live integration test (not a unit run).
