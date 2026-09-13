# Overturn note — PLANK/TPR per-parcel joins (p47/p74) + p274 ceiling partial (issue #236)

> Hunted + built 2026-09-13. **Verdict: PARTIAL-OVERTURN by shape,
> KEEP-NULL live** — the per-parcel join shapes (p47 designated-use,
> p74 decree, p274 ceiling proxy) are implemented and fixture-proven in
> `services/scoring/dims_overturn_planktpr.py`, pinned by
> `services/scoring/tests/test_dims_overturn_planktpr.py` (27 tests).
> Live production joins stay NULL: PLANK WFS is gone and TPR serves no
> bulk (dated negative, re-verified today — evidence below). Re-check
> the two register surfaces no later than **2027-03-13**.
>
> What flipped vs stayed NULL: the *shapes* flipped (exact-parcel joins
> with first-cut bands now exist where only documented NULLs stood);
> the *live verdicts* stayed NULL (no snapshot feed exists to join
> against). The deed clause of p274 never flips on a ceiling number —
> soft caps [55, 65] pin that permanently.

## Verdict

| Param | Shape (this module) | Live | Evidence (2026-09-13) |
|---|---|---|---|
| p47 zoning → `zoning_use_overturn` | kehtestatud designated-use exact join; residential 80 / mixed 60 / commercial 35 / restricted 20; cap 80 | NULL (no snapshot) | PLANK WFS 301 → E-ehitus SPA; GetCapabilities → SPA shell, no WFS XML |
| p74 restrictions → `rentrestr_decree_overturn` | decree-row exact join; present 30 (ref printed) / absent 80 measured-clear dated | NULL (no snapshot) | same missing bulk; decree texts are not a parcel feed |
| p274 air rights → `airrights_ceiling_overturn` | PARTIAL: plan max-height ceiling proxy, soft caps 55/60/65; deed stays NULL | NULL (no snapshot; deed paid-register) | same missing bulk + e-Kinnistusraamat Tier 2 PAID (group04 precedent) |

## Openness evidence (one polite round, 2026-09-13, no scraping, no auth)

7 tiny requests total (labelled one-off user-agent
`home-finder-236-hunt/1.0`, paced ≥ 3 s, headers + SPA-shell scope read
only, no form submissions, no bulk pull). Raw bodies:
`/tmp/hf-236-planktpr/` (one-off PR record, not committed).
Re-confirms the sibling dated verdicts in `dims_p4_plank.py` (#251)
and `dims_p4_tpr.py` (#250/#334) one day later.

| Check | Observed | Meaning |
|---|---|---|
| `HEAD planeeringud.ee/` → 301 (Apache/ZoneOS) | `location: https://livekluster.ehr.ee/ui/ehr/v1/detailsearch/PLANNINGS_SEARCH` | PLANK portal now lives inside the E-ehitus platform |
| `HEAD planeeringud.ee/geoserver/wfs` → 301 | same location | the documented OGC WFS 2.0.0 base no longer serves WFS |
| `GET .../geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities` → 200 text/html, 4024 B | `<title>e-ehituse platvorm</title>` SPA shell, zero WFS markers | NO GetCapabilities document — the old GeoServer endpoint is gone |
| `HEAD tpr.tallinn.ee/` → 200 (Apache, 83 331 B) | `Tpr` Angular SPA | human register, as before |
| `GET tpr.tallinn.ee/` → 200 text/html shell | first 16 kB carry no wfs/bulk/api/download link | NO open bulk endpoint behind the shell |

Pull contract (when bulk reopens): max 1 download / 14 d per cache dir
(`OVERTURN_TTL_S = 1209600`, parameters3.md §5.5 bi-weekly ticket),
single GET with `OVERTURN_UA`, no retries — HTTP 429/errors are a stop
signal. `OVERTURN_BULK_URL` stays `None` until the checklist below
names a verified bulk URL; until then the fetcher performs no requests.

## Honest shapes per param (bands, NULL stays NULL)

| Param | Dim key | Join | Scored shape | NULL when |
|---|---|---|---|---|
| p47 designated-use fit | `zoning_use_overturn` | exact parcel, kehtestatud row only | residential→80, mixed→60, commercial→35 (+financing flag), restricted→20; cap 80 | no snapshot / parcel absent / stage ≠ kehtestatud / unrecognised code |
| p74 restriction decree | `rentrestr_decree_overturn` | exact parcel, decree rows | present→30 (decree_ref printed) / absent→80 measured-clear dated | no snapshot / parcel absent / flag unknown |
| p274 ceiling proxy | `airrights_ceiling_overturn` | exact parcel, max_height_m | ≤9 m→55, ≤25 m→60, above→65 (soft caps, never outside) | no snapshot / parcel absent / unknown-garbage ceiling |

Measured join scores (parcel row present in the snapshot); missing join
stays NULL — unknown, never good. Every scored reason says `hinnang`
with components; every NULL reason says `EI OLE` and names the missing
input. Exact-parcel joins only: no distance weighting, no
interpolation.

## Near-miss proxies considered and refused

- **OSM `landuse=*` as p47 zoning** (descriptive what-is-built, never
  the prescriptive decree — painting it as zoning is fake precision,
  group05a precedent). The module takes no OSM tags and stages no
  Overpass fragment — pinned by test.
- **`tourism=apartment` counts as p74 restrictions** (supply, not
  restriction — group05a: 25 objects, zero signal by construction).
- **KKIS restriction detail as p74** — that leg belongs to the kataster
  sibling (`dims_p4_maa_kataster.dim_kinnistus_syva`, P4-004); this
  module reads only the planning decree feed. No overlap.
- **Ceiling height as the p274 deed verdict** — a viewshed/ceiling
  shows what fits above, not who owns it (group04 p271 precedent). The
  proxy is capped [55, 65] and always disclaims the deed — pinned by
  sweep test.
- **Non-kehtestatud stages as the p47 decree** (menetluses/algatatud
  labels are pipeline, not law — same call as the PLANK/TPR P4-006
  siblings). Unknown use codes stay NULL (unverified codelist never
  assumed).

## Judgment calls (for the reviewer)

1. Partial-overturn, not full: shapes exist + scored on fixtures, live
   stays NULL. The alternative (pure KEEP with no shapes, p317-style)
   was rejected because the issue acceptance explicitly asks for the
   join shapes and soft caps — but with no live feed, first-cut bands
   are uncalibrated by construction and MUST be recalibrated on reopen.
2. p47 commercial→35 carries the parameters3 Illegal-Land-Use edge
   case (ärimaa flags financing restrictions + commercial land tax) in
   the reason, not in the score alone.
3. p74 present→30, never an abort: parameters3 says "Abort deal if
   missing" — the abort belongs to the deal layer; the dim scores low
   and names the decree + notary check.
4. p274 bands differentiate weakly on purpose (55/60/65): allowed
   height alone barely answers air-rights ownership. The value of the
   partial is the *known-ceiling vs unknown* split plus the permanent
   deed disclaimer — challenge the band slopes on reopen.
5. Tallinn kov filter (`tallinn` / `tallinna linn`, case-insensitive;
   unknown kov skipped) mirrors the PLANK sibling — TPR is
   Tallinn-only, PLANK national rows must not join blindly.
6. No shared-file edits; central hook (snapshot feed + WEIGHTS
   rebalance) stays one joint change across all batches. `docs/nomap.md`
   is deliberately untouched here — the final docs-index PR updates it.

## Scope guard (siblings untouched)

`dims_group05*.py` (canonical p45/p47/p74 NULLs + p42/p44 proxies),
`dims_group04.py` (canonical p274 deed NULL), `dims_p4_plank.py`
(P4-006 PLANK pipeline leg), `dims_p4_tpr.py` (P4-006/P4-005/P4-050 TPR
legs), `dims_p4_maa_kataster.py` (P4-004 KKIS restriction leg),
`livability.py`, WEIGHTS, `docs/nomap.md` — all unmodified; 3 new
files only.

## Reopening checklist (when PLANK/TPR serve per-parcel bulk)

1. Re-run the HEAD/GetCapabilities probes; paste fresh evidence.
2. Set `OVERTURN_BULK_URL` to the verified bulk URL; pull one snapshot.
3. Verify the Tallinn `kov` spellings + `use_stage` + `designated_use`
   codelists against the live registers; adjust `TALLINN_KOVS`,
   `DECREE_STAGE`, and the use-stem sets.
4. Recalibrate `USE_BANDS` / `CEILING_BANDS` (+ the 30/80 p74 pair)
   from real histograms; resolve the PLANK↔TPR↔KKIS overlap rule with
   the central hook (same parcel may appear in all three feeds).
5. Add the explicitly-flagged live integration test (not a unit run).
