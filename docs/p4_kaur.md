# P4 KAUR: Keskkonnaagentuur verdict note (issues #285 + #359)

Demo (#285) implements the KAUR ingestion + P4-015 (flood-zone
insurability leg) end-to-end; coverage (#359) wires the remaining 10
params off the same ingestion. One PR closes both because the #359
body states it extends the demoed ingestion with "no new plumbing
expected": the ten coverage params ride the same two snapshot tables
(`zones` for P4-016/P4-046/P4-058, `stations` for P4-023/P4-024/
P4-031/P4-042 plus validation for P4-056/P4-059) and the documented
`kaur_ctx_p4` convention — P4-053/P4-056/P4-059 need rows their owner
legs supply (wind-rose join, LiDAR morphology, restriction register),
not a second KAUR fetch. No new plumbing.

Overturn #239 covers KAUR/EFAS flood polygons for parameters3 G8
separately — flood WFS verification belongs to that track and is
deliberately NOT duplicated here (this module proves the P4-015
zone-join shape on fixtures only). No `dims_group08*` or other
shared/group files touched.

## Openness verdict: mixed (2026-09-13, keeps per #285)

Nine polite requests total (custom UA, short timeouts, paced ≥4 s,
cached `/tmp/hf-p4-kaur/`, no scraping, no auth attempts, redirects
not spidered):

```
HEAD https://keskkonnaagentuur.ee/              -> HTTP 200 (Drupal)
GET  https://keskkonnaagentuur.ee/               -> HTTP 200, 113 152 B ("Avaleht | Keskkonnaagentuur")
HEAD https://www.ilmateenistus.ee/               -> HTTP 200 (Cloudflare)
GET  .../keskkonnainfo-ja-avaandmed              -> HTTP 200, 95 074 B (e-service catalogue)
HEAD https://keskkonnaportaal.ee/                -> HTTP 200 (server KEMIT)
GET  https://keskkonnaportaal.ee/et/avaandmed    -> HTTP 200, 163 537 B ("Avaandmed | Keskkonnaportaal")
GET  .../keskkonna-ja-ilma-valdkonna-andmeteenused -> HTTP 200, 160 993 B (API environment page)
GET  keskkonnaandmed.envir.ee/f_kliima_paev?...&limit=1 -> HTTP 200, 261 B (postgrest/12.0.1, Tallinn-Harku row)
HEAD https://www.efas.eu/                        -> HTTP 301 (not followed, polite stop)
```

What each layer actually carries:

- Agency/Ilmateenistus front pages: human sites, zero machine hrefs.
- `keskkonnaportaal.ee/et/avaandmed`: documents EELIS + Geoserver
  WMS/WFS services, the KAIA file store, the API environment, and a
  dataset catalogue — documented services, no verified per-parcel
  bulk URL on the page itself.
- `keskkonnaandmed.envir.ee` (PostgREST 12.0.1): answers anonymously —
  the probe query returned a real Tallinn-Harku daily observation
  (`AJHARK01`, 2023-12-01, `DPA008`). OPEN as the re-pull anchor for
  the station/observation slices (P4-031 Harku baseline, P4-053 wind
  data via `f_kliima_*`, KESE/EELIS tables on the same host).
- Dated negative keeps the zone-bulk verdict: no anonymous
  per-parcel bulk URL for the flood-zone polygons, the
  groundwater-protection zones, or the air/pollen station registry
  was verified 2026-09-13 — `KAUR_BULK_URL` stays `None`, and flood
  WFS verification stays with #239.

Pull contract: max 1 download / 365 d per cache dir (`KAUR_TTL_S =
31536000`; zones move on planning cycles, station rows are reference
rows; KAUR publications trigger an out-of-band re-pull), single GET,
no retries — HTTP 429/errors are a stop signal. Transport errors are
never cached as data; the scorers stay NULL with an Estonian EI OLE
reason until a join lands. Scored shapes are proven on fixtures only
(hermetic tests).

## Honest shapes per param (bands, NULL stays NULL)

| Param | Dim key | Joined slice | Scored shape | NULL when |
|---|---|---|---|---|
| P4-015 insurability (demo) | `kindlustatavus_kaur` | flood zone ≤300 m | T10→25, T100→45, surge→50, T1000→65, measured clear→80 | no snapshot, no flood slice, beyond window |
| P4-016 geology | `pinnas_kaur` | groundwater zone ≤300 m | gw_strict→30, gw_mild→55, clear→75 | no groundwater slice, beyond window |
| P4-023 noise | `mura_kaur` | air station ≤3 km | rattle→45, quiet→70 (cross-check, never gradient) | no air slice, beyond window, flag unknown |
| P4-024 nuisances | `tervis_kaur` | pollen station ≤3 km | korge→40, keskmine→55, madal→70 | no pollen slice, level unknown |
| P4-031 backyard weather | `mikrokliima_kaur` | met/wind density ≤2 km | Harku-only→50, 1–2 local→65, 3+→75 (count in reason) | no met/wind slice at all |
| P4-042 smell | `louna_kaur` | air station ≤2 km | episode→40, quiet→65 (coarse, never doorway) | no air slice, episode unknown |
| P4-046 dread removal | `varu_kaur` | flood/groundwater ≤300 m | bad→35, mild-only→60, dry→75 | no water slice |
| P4-053 odour roses | `lounarose_kaur` | sector ctx ≤1500 m | >15 d→35, 6–15 d→50, ≤5 d→65 (sector, never circle) | no sector, days unparseable/negative, beyond window |
| P4-056 courtyard | `sisehoov_kaur` | court ctx ≤500 m + air validation | korge+episode→40, korge alone→55, keskmine→65 | no court cell, enclosure unknown |
| P4-058 ice/cliff | `jaapurikas_kaur` | surge zone ≤300 m | surge→45, clear→75 | no surge slice, beyond window |
| P4-059 wood burning | `tahkekyte_kaur` | burn-rule ctx ≤500 m + air station ≤3 km | keelatud+episode→25, keelatud quiet→50, piiratud+episode→40, piiratud quiet→60 | no rule cell, rule unknown, no monitoring station |

Never 0 and never 100 (one KAUR slice never prices insurance, proves
calm, or clears a parcel). Every scored reason says `hinnang` with
the joined zone/station/sector; every NULL reason says `EI OLE` and
points at the missing join. Absence of data is unknown, never good.

## Sibling-leg split (no double-scoring)

| Param | KAUR slice (this module) | Owner leg (untouched, named in reasons) |
|---|---|---|
| P4-015 | flood zones | PPA theft stats, insurer tariffs, paaste fire density |
| P4-016 | groundwater protection | EGT turvas/karst/alvar, Maa-amet geology |
| P4-023 | Ämari-rattle cross-check | trans/EANS zone gradient |
| P4-024 | pollen monitoring | Terviseamet tick stats, PRIA spray-drift, farm odour |
| P4-042 | smoke-episode cross-check | paaste chimney-notice cells |
| P4-046 | draining ground floor | EHR fireplace, ÜVK well-water, teeregister 2nd exit |
| P4-056 | fume-hold validation | Maa-amet LiDAR enclosure index |
| P4-058 | storm-surge erosion edge | paaste ice-fall notices, EHR roof type |
| P4-059 | enforcement recency | paaste rule join (scores the rule itself) |

All dim keys carry the `_kaur` suffix so a future central hook can
import this module alongside paaste/trans without collisions.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #359 defines coverage as extending the
   demoed ingestion (taitur #255/#336 and RB #281/#355 precedent).
2. Mixed verdict, not a pure negative: the PostgREST host is verified
   open, so the module documents it as the re-pull anchor — but no
   per-parcel zone bulk URL was verified, so `KAUR_BULK_URL` stays
   `None` and the fetch path performs no requests (RB honest-plumbing
   precedent). Flood WFS stays with #239.
3. First-cut bands (see table) MUST be recalibrated from a real
   snapshot on reopen — stated in code and here, not hidden.
4. Station windows (3 km air/pollen, 2 km backyard) vs the 300 m zone
   window: gases and rattle carry across the asum, parcels do not.
5. P4-059 scores enforcement recency, not the rule — a rule cell
   without a monitor stays NULL (paaste already scores the rule).
6. No shared-file edits (livability.py, WEIGHTS, group08 files,
   parameters4.md untouched): 3 new files only. Central hook
   (enrich join + WEIGHTS rebalance) stays one joint change across
   all batches.

## Reopening checklist (when a per-parcel feed appears)

1. Re-run the probes above; verify the exact bulk/table URLs
   (flood WFS via #239, station registry + KESE tables on the
   PostgREST host) and paste fresh evidence in the reopen PR.
2. Set `KAUR_BULK_URL`, pull one snapshot into the cache dir; run it
   through `parse_kaur_snapshot` + `snapshot_to_pois` on fixtures
   first.
3. Recalibrate all first-cut bands against real zone/station spreads.
4. Add the explicitly-flagged live integration test (not a unit run).
