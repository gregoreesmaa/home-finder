# P4 strategic-noise-map verdict (issue #526): documented no-map + band dim

Closes #526.

## 1. Verdict (2026-09-16): NO-MAP (licence unconfirmed) + provisional band dim

One polite probe round (UA `home-finder-idea-probe/1.0`, `--max-time 25`,
no retries, paced ≥ 3 s), cached to `/tmp/hf-526-529-probe` (one-off PR
record, not committed):

| # | URL | Result |
|---|-----|--------|
| 1 | `…/ows/myrakaart?service=WFS&version=2.0.0&request=GetCapabilities` | **OPEN.** `HTTP/2 200`, `text/xml`, **69 922 B**. Title `Mürakaardi rakenduse kaardikihid`. ~70 layers: 2017 `myra_*` (auto/mnt/rdt/lend/toostus/kast/sum × paev/ohtu/oo/aasta) + 2022 `myra22_siser_*` (national Ld/Ln at 2 m height) + 2022 `myra22_strat_*` (strategic: auto/mnt/rdt/lend/toostus/kast/sum × paev/ohtu/oo/oopaev). Service self-declares `Fees: Teenuse kasutamisel tasusid ei rakendu`, `AccessConstraints: NONE`. CRS default `EPSG:3301` (+3857/4258/4326) |
| 2 | `…request=DescribeFeatureType&typeName=ms:myra22_strat_sum_oopaev` (Lden sum leg) | **OPEN.** 1 339 B. Attributes: `ID, YLDKLASS, MYRALIIK, MYRAINDEKS, MYRAKLASS` (band field), `AEG` |
| 3 | `…request=GetFeature&typeName=ms:myra22_strat_sum_oopaev&resultType=hits&bbox=59.2,23.9,59.7,25.4,EPSG:4326` | **4 705 Lden polygons matched in the Harjumaa window** (hits only — no feature data transferred) |
| 4 | Licence check: `andmed.eesti.ee/datasets/eesti-strateegilised-murakaardid-(wfs)` (GET) | **UNCONFIRMED.** Page is a JS app shell (`Teabevärav`, Angular) with no static licence text; the national catalogue entry the issue cites states NONE. The WFS Fees/AccessConstraints lines govern service use, not the data licence. **Per the issue contract, no open licence confirmed → no harvest, no map.** |

No 429 encountered at any step. No feature data was pulled
(capabilities + schema + hits only), so no Tallinn histogram exists —
bands are uncalibrated by construction.

## 2. What ships

`services/scoring/dims_p4_noisemap.py` (new): `fetch_wfs_capabilities()`
(polite, cache-first, `NOISEMAP_CACHE_TTL_S = 180 d` — maps renew every
5 years; dates the verdict, never feeds the scorer) →
`parse_capabilities_layers()` (pure verdict record, fixture-tested) →
`dim_noise_lden()` (provisional bands on caller-supplied dB legs:
Lden ≤45 → 85, ≤55 → 65, ≤65 → 40, >65 → 20; Lnight shifted 5 dB down;
binding/minimum leg wins; without rows — or outside mapped polygons —
NULL with `hinnang` + `EI OLE`, teadmata never "quiet") +
`parse_myaklass()` (explicitly UNVERIFIED adapter seam for the band
domain). Transport errors raise and never touch the cache; 429 stops
the run. Group 9 proxies and `dims_p4_trans.noise_zone_trans` untouched.

## 3. Judgment calls for the reviewer

1. New files only (`dims_p4_noisemap.py`,
   `tests/test_dims_p4_noisemap.py`, `docs/p4_noisemap.md`). No
   shared-file edits; no livability/WEIGHTS hook (joint-change rule).
2. Lnight −5 dB offset is a sleep-disturbance judgment call —
   challenge with the histogram once harvested.
3. `parse_myaklass` assumes `"55-59" / ">65" / "<45"` shapes without
   evidence; the assumption is fenced in the docstring, the doc (§5),
   and a fail-closed test — the adapter must confirm or replace it.
4. Test fixtures are fully synthetic; real observed values appear only
   in §1 above, never as ingested data.

## 4. DoD evidence

```text
$ python3 -m pytest services/scoring/tests/test_dims_p4_noisemap.py -q
.................s                                                       [100%]
17 passed, 1 skipped in 0.06s
```

Hermetic: suite makes zero network calls (live pull env-gated behind
`HF_LIVE_NOISEMAP=1`). Full-suite output pasted in the PR body.

## 5. Reopening checklist

* Licence clears (Teabevärav shows an open licence, or Maa-amet
  confirms in writing) → snapshot harvest script under
  `scripts/build/batch_noisemap_*.py` (cache to snapshot dir, fixtures
  only in repo) → confirm/replace the `parse_myaklass` domain against
  real MYRAKLASS values → Tallinn histogram to justify bands (median
  mid-ramp) → walk-graph or honestly-labelled Euclidean kernel →
  contract check (half/σ) → Tallinn + rural screenshot.
* Lnight handling: binding-leg rule stands unless the histogram says
  otherwise (state it in the harvest PR).
* Existing Group 9 proxies stay until the measured layer proves itself
  (no re-tuning in the harvest PR either).

## 6. Harvest addendum (2026-09-17, issue #625 — owner: usable without a licence)

Owner decision (issue #625): the WFS self-declares Fees none +
AccessConstraints NONE and GetMetadata carries no use constraints —
harvest proceeds with attribution in every sidecar. `parse_myaklass`
domain CONFIRMED against real features: plain 5 dB lower bounds
("45","50","55",… on nested contours; the old "55-59" guess was
wrong) — upper edge reads L + 4.9 (buyer-conservative, pinned).

Bulk job (`scripts/build/batch_noisemap.py`, UA `home-finder-dev/0.1`,
paced 3 s, resume-aware per-cell cache, 429 stops the run): tiled
Harju+2 km pull of `myra22_strat_sum_oopaev` (Lden) +
`myra22_strat_sum_oo` (Lnight), 126 cells × 2 legs = 252 pulls, no
429. Findings that shaped the build: EPSG:3301 serves N,E axis order
(BBOX + posList); members carry NO per-polygon id (gml:id repeats per
category, ms:ID IS the category 63–69) → edge overlaps dedupe on
geometry hash (7113 members → 6627 rows + 486 dupes, exact); a
degenerate DP seed segment collapsed closed rings to 2 points (fixed +
pinned — seed at the farthest vertex).

Sidecar `noise/noise-areas.json` (2.2 MB): **6627 rows**
(Lden 4552 + Lnight 2075), 0 dropped, 0 unparseable, DP-5 m
2 165 360 → 744 752 verts, all rows pass the `isNoiseArea` guard.

Tallinn histogram (bbox-centre box) — band justification: counts fall
with loudness on both legs (Lden 45:1715 / 50:864 / 55:444 / 60:396 /
65:326, then airport/highway cores 70:602 / 75:205; Lnight 45:638 /
50:426 / 55:334 / 60:349 / 65:259 / 70:69). The median sits in the
45–50 dB bands — mid-ramp of the issue's table (≤45→85, ≤55→65,
≤65→40, >65→20; Lnight −5 dB) — so the bands stand unchanged.
Binding (minimum) leg still wins in the scorer.

Map: `layers_p4_noise.ts` + `/api/layers/noise/areas` + band fills
(quiet-green → loud-red, Lnight same ramp at lower opacity) + legend
(MUDEL, never quiet) + toggle dot. Group 9 proxies untouched.

DoD evidence: `pytest services/scoring/tests/test_batch_noisemap.py
services/scoring/tests/test_dims_p4_noisemap.py` → 27 passed,
1 skipped; full `pytest` + `npm test` green; `typecheck` + `lint`
clean; live GET /api/layers/noise/areas → 200, 6627 areas;
screenshot (/layers?c=24.75,59.43,11, P4-müra): Tallinn green fills
+ red loud cores, zero page errors.
