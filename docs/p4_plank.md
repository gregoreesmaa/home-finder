# P4 PLANK: national WFS verdict note (issue #251, single-param demo)

Demo (#251) implements the PLANK national WFS ingestion + P4-006
end-to-end in Tallinn (parameters4.md P4-006 source (2)). Single-param:
the remaining P4-006 sources are covered by sibling legs, and no
follow-up coverage issue uses this source (per the #251 body).

Scope guard: overturn #236 owns PLANK/TPR for parameters3 Group 5
this-parcel zoning — untouched (`dims_group05*.py`, shared/group
files, `livability.py`, WEIGHTS all unmodified; 3 new files only).
Sibling P4-006 legs untouched: `dims_p4_tpr.py` (`pipeline_500m`, TPR
register leg), `dims_p4_cityplans.py` (`arenguala_cityplans`,
üldplaneering leg), `dims_p4_rb.py` (`koridor_reserv_rb`, corridor
leg), `dims_p4_maa_kataster.py` (`naaber_planeering`, kataster leg).
This module scores ONLY the PLANK-WFS leg (`pipeline_plank_500m`).

## Openness verdict: dated negative (2026-09-13, keeps per #251)

`https://planeeringud.ee/geoserver/wfs` (the OGC WFS 2.0.0 base named in
parameters3.md Group 5) no longer serves WFS. Polite evidence, 4 tiny
requests total (custom UA, headers + two ~3.7 kB SPA shells, no scrape):

```
HEAD planeeringud.ee/                   -> HTTP 301 (Apache/ZoneOS) to
  https://livekluster.ehr.ee/ui/ehr/v1/detailsearch/PLANNINGS_SEARCH
HEAD planeeringud.ee/geoserver/wfs      -> same HTTP 301 (WFS gone)
GET  .../geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities
  (redirects followed)                  -> HTTP 200 text/html, E-ehitus
  SPA shell ("e-ehituse platvorm") — NO WFS XML, no GetCapabilities
GET  planeeringud.ee/ (followed)        -> same SPA shell
  (<title>e-ehituse platvorm</title>, 3663 B)
```

A web search for a documented PLANK bulk/API replacement surfaced
nothing open (2019 data-model PDF, EVALD guides referencing register
extracts on request — not open bulk).

Raw headers/shells: `/tmp/plank-open/` (one-off PR record, not
committed). Pull contract: max 1 download / 7 d per cache dir
(`PLANK_TTL_S = 604800`, parameters4.md P4-006 TTL weekly), single GET,
no retries — HTTP 429/errors are a stop signal. `PLANK_BULK_URL` stays
`None` until the checklist below names a verified bulk URL; until then
the fetcher performs no requests and the scorer stays NULL with an
Estonian EI OLE reason. The scored shape is proven on fixtures only
(hermetic tests).

## Honest shape (checklist / bands, NULL stays NULL)

| Param | Dim key | Window | Scored shape | NULL when |
|---|---|---|---|---|
| P4-006 pipeline, PLANK leg (demo) | `pipeline_plank_500m` | Tallinn-filtered menetluses plans ≤ 500 m | count band: 0→90, 1→65, 2–3→40, ≥4→20 | no snapshot / no Tallinn plan POIs / origin missing |

Measured zero scores (0 menetluses Tallinn plans in buffer with Tallinn
plans elsewhere in the snapshot); missing join stays NULL.
Beyond-window is unknown, never 0. The scored reason says `hinnang`
with components; every NULL reason says `EI OLE` and names the missing
input. Distances are bird-flight, never routed or parcel-exact.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage pairing: unlike the TPR demo+coverage
   pair, the #251 body states no follow-up coverage issue uses this
   source — one snapshot table (`plans`), one dim.
2. Pipeline counts ONLY `stage == "menetluses"` (parameters4.md
   wording); algatatud/vastuvõetud labels are NOT counted until
   verified against the live PLANK codelist — conservative, pinned by
   test (same call as the TPR sibling; the kataster sibling counts
   algatatud too — the legs differ honestly by source).
3. Tallinn filter: national-register rows join only on a recognised
   Tallinn `kov` (`tallinn` / `tallinna linn`, case-insensitive);
   kov-less rows are skipped (unknown municipality is never assumed
   local), pinned by test.
4. P4-006 bands (90/65/40/20) are a first-cut judgment with no live
   calibration, shared with the TPR sibling so the legs stay
   comparable; MUST be recalibrated from a real snapshot on reopen.
5. PLANK (national aggregate) and TPR (municipal register) may describe
   the SAME Tallinn plans on reopen — the central hook must decide how
   the legs combine, never sum them blindly. No Overpass fragment / tag
   mapping staged: OSM has no honest tag for PLANK menetlus stages
   (group20a no-map precedent).
6. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches.

## Reopening checklist (when PLANK serves bulk data again)

1. Re-run the HEAD/GetCapabilities probes; paste fresh evidence.
2. Set `PLANK_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Verify the Tallinn `kov` spellings + `stage` codelist against the
   live register; adjust `TALLINN_KOVS` / `PIPELINE_STAGE` handling.
4. Recalibrate `PIPELINE_BANDS` from real histograms; resolve the
   PLANK↔TPR overlap rule with the central hook.
5. Add the explicitly-flagged live integration test (not a unit run).
