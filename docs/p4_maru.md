# P4 MARU quarterly harvest (per-KOV market tables)

Source of truth for the four MARU choropleths (`kovkasv` p41, `kovkaive`
p149, `kovedas`, `kovkiirus` p484 — module `apps/web/lib/layers_maru.ts`,
builder `scripts/build/batch_maru_choropleth.py`): the Maa-amet
hinnastatistika query env (`htraru/FilterUI.aspx`), report **T13
apartment transactions**, all Harju KOVs, quarterly. Harvested 2026-09-16:
2025-Q1..2026-Q2, 16 KOVs × 6 quarters = 96 rows (2026-Q2 thin: Anija 4
and Loksa 2 deals masked by the source min-5 rule, read as unknown).

## Why a script, not a download

The env has **no bulk export** — the quarterly KOV table exists only
through the same postback sequence a human drives (county cascade,
publication-type flip, location checkboxes, two-step region reveal).
The repo's overturn verdict defined this table as a caller-supplied
maintainer export ("never scraped"); the maintainer explicitly
authorized this automated pull on 2026-09-16 as the supplier of record.
That override, and the politeness rules below, are the contract — a
reviewer changing either must update this file first.

## Flow mechanics (reverse-engineered 2026-09-16)

ASP.NET WebForms; the app answers any deviation with `Töötlemata viga`
(unhandled error), which made each rule below load-bearing:

1. Land → flip `DDTrykis=G` (Price statistics) via `__EVENTTARGET`
   postback. Report list becomes T09..T12, T13, E01..E03, K01..K02.
2. The county→municipality cascade works under General statistics but
   **crashes under Price statistics** — never cascade under G.
3. The location section renders only with `chkAsukoht=on`;
   `chkValiKoik=on` means all municipalities. The G-flip wipes the
   municipality options, so drilldown selection is impossible under G
   (EVENTVALIDATION rejects values absent from the rendered list).
4. Region radios (`RBLPiirkond`) do **not** render until a first submit;
   submit-1 (T13 + checkboxes + quarter dates) reveals them with
   "all municipalities" (0) checked; submit-2 (same state mirrored)
   returns the 16-KOV report.
5. Golden rule: every POST carries **exactly** the controls rendered in
   the current page state (`controls()` in the script mirrors a
   browser). Proven poisons: `DDLoikeProtsent` on landing,
   `RBLTehingud` under Price statistics, `RBLPiirkond` before it
   renders, municipality values with an empty options list.
6. Date fields are `mm.yyyy` (datepicker `format: "mm.yyyy"`).
   `RBLTehingud` (All transactions vs Purchase-Sale) is absent from the
   Price-statistics tree, so scope stays All transactions (the
   screenshot default) — documented, not silently chosen.

## Scope and limits of the data

- T13 apartment/dwelling transactions, Harju KOVs only (16 blocks;
  Tallinn is one aggregate — no linnaosa split exists here).
- Min-5 masking: cells with <5 deals render `***`, parsed as `None`
  (never 0). Q2-2026 is thin (late registrations still arriving —
  Tallinn 931 vs ~2,200 typical); the builder's NULL rules and the
  layer's vintage stamp carry that honestly.
- Source page states results are informative/unofficial and subject to
  correction; the tables file records period + scope + pull date.

## Periodic run (quarterly, TTL 90 days with the Ookla re-pull)

```bash
python3 scripts/build/harvest_maru_quarterly.py /tmp/maru-Q.json 2026-Q3
python3 -c assemble tables doc: synthetic False, period, scope note, rows
python3 scripts/build/batch_maru_choropleth.py --tables ... \
    --kov-extract ... --outdir $HF_SNAPSHOT/osm
# restart web (masters are cached per process) + verify /api routes
```

Raw report HTML is never committed (repo hygiene: fixtures only —
the committed test fixture is hand-made synthetic). The pull itself:
~4 requests/quarter at >=5 s pacing, single session, descriptive UA,
HTTP 429 aborts the run (stop signal, never a dare).
