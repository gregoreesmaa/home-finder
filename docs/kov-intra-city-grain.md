# KOV choropleths flat inside Tallinn: grain decision (issue #521)

> Buyer report: kovkaive looks monotonous — one flat colour over the
> city. Verified: Harju-wide the layer is RICH, but Tallinn is a single
> KOV polygon so it reads one band by construction. Works as designed;
> expectation gap, not a data bug.

## Decision (2026-09-16)

**Legend/expectation note, no restretch, no disaggregation.**
`MARUKOV_GRAIN` in `apps/web/lib/layers_maru.ts` (appended to all four
MARU sources) states: Tallinn is one KOV polygon, so every KOV layer is
flat inside the city by construction; bands are never restretched for
contrast. Regression-pinned by
`apps/web/lib/layers_maru_grain.test.ts` (note present + band table
unchanged).

## Finer-grain research (no faking)

- **linnaosa/asum turnover**: not in the MARU contract. The query env
  (`maaamet.ee/kinnisvara/htraru/`) aggregates per-KOV (`Maakond` +
  `Omavalitsus` selects — docs/overturn_maru.md, 2026-09-13); there is
  no anonymous bulk contract, and the maintainer export schema is
  `kov;quarter;median_eur_m2;deals`. A linnaosa turnover feed would
  need a new verified source — none found, none invented.
- **Grid-disaggregated turnover**: refused. Splitting one KOV quarterly
  deal count across 75 m cells would manufacture intra-city variation
  the register never measured — the same family as the already-refused
  cross-KOV smoothing / forward-fill (docs/overturn_maru.md
  near-misses). Every cell keeps its own KOV's band; Tallinn keeps one.
- **Asum medians (#495, sibling in flight)**: price-level medians, not
  turnover — a disjoint question from kovkaive/kovkiirus. No double
  counting; this PR does not touch it.
- **No band restretch**: verified — `MARUKOV_BANDS`/`MARUKOV_DEFAULTS`
  byte-identical to the locked 2026-09-13 calibration (drift-pinned in
  both `layers_maru.test.ts` and
  `scripts/build/test_batch_maru_choropleth.py`, re-run green).

No network was used for this issue (existing 2026-09-13 evidence
stands; MARU re-check stays on the overturn TTL).
