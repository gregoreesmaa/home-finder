# P4 EMTA KOV-fiscal verdict note (issue #539)

Date: 2026-09-16. Scope: P4-019 KOV fiscal health,
transfer-composition leg (income-tax + land-tax transferred to KOVs),
per-KOV choropleth join (`services/scoring/dims_p4_emta_kov.py` +
`scripts/build/batch_emta_choropleth.py`).

## Openness verdict: OPEN with a licence judgment call (reviewer call)

Polite probes, one GET per endpoint, `home-finder-probe/1.0`
User-Agent, raw pages at /tmp/hf-probes/ (one-off PR record, never
committed):

| Probe | Result |
|---|---|
| `GET https://www.emta.ee/statistika-ja-avaandmed` | HTTP 404 (140 404 bytes) — old IA dead |
| `GET https://www.emta.ee/statistika/statistika-ja-avaandmed` | HTTP 404 — old IA dead |
| `GET https://andmed.eesti.ee/datasets/maksu-ja-...-maamaks` | HTTP 200, 75 497 bytes — Teabevärav JS shell, no server rows (same shell as #264/#277/#284) |
| `GET https://andmed.eesti.ee/api/v2/datasets?search=...` | HTTP 404 `Cannot GET /v2/datasets?search=...` — Guessed API shape, documented miss |
| `GET https://emta.ee/` | HTTP 200, 203 612 bytes — new bare-domain site; stats path found: `/eraklient/amet-uudised-ja-kontakt/uudised-pressiinfo-statistika/statistika-ja-avaandmed` |
| `GET <stats page>` | HTTP 200, 296 288 bytes — section `#kov-tulumaks-maamaks` with yearly 2019–2026 files in XLSX **and** CSV (two links per dataset per year — both formats verified, ET anchors) |
| `GET .../download/maamaks_2026.csv` (+303→follow) | HTTP 200, 9 893 bytes — `;`-delimited, BOM, Estonian thousands spaces; `Kood` EHAK column + monthly 2026/2025 pairs + `Kokku`; 78 KOV rows, 16/16 Harjumaa |
| `GET .../download/tulumaks_2026.csv` (+303→follow) | HTTP 200, 17 837 bytes — same shape, 78 KOV rows, 16/16 Harjumaa |

Licence evidence, verbatim: the catalogue states NONE; the EMTA page
carries no CC machine tag. It DOES publish the files under
`"Maksu- ja Tolliameti avaandmed"`, cross-linked from
`"Teabevärav / Eesti riigi avaandmete ametlik portaal"`. Reading: a
publisher-declared open-data publication → proceed WITH attribution
(`EMTA_ATTRIBUTION`), WITHOUT committing pulled data. Strict-gate
fallback: flip to documented no-map; the evidence above is the flip
kit.

## Honest-shape table (per-KOV choropleth join)

| Param | EMTA slice consumed | Shape when joined | When missing |
|---|---|---|---|
| P4-019 transfers (this leg) | maamaks share of 2025 transfers | ≤3.0% → 70 / ≤4.4% → 55 / above → 40 (`hinnang`, transfers ≠ service quality) | NULL → KOV rate table (p4_emta) + KOV budget |

Measured Harjumaa distribution (16 KOVs, 2025 full-year, 2026-09-16):
Keila 1.50%, Raasiku 2.21%, Kiili 2.45%, Saue 2.76%, Anija 2.91%,
Saku 2.95% (p33), Loksa 3.17%, Rae 3.30%, Kose 3.60%, Tallinn 4.29%,
Harku 4.37% (p67), Kuusalu 4.81%, Lääne-Harju 5.55%, Viimsi 6.41%,
Maardu 9.44%, Jõelähtme 9.72%. Cutoffs: 3.0 / 4.4.

## Pairing rationale (why this slice, why these bands)

- Share-of-transfers INSTEAD of per-capita: the files carry no
  population column, and totals alone would rank Tallinn worst
  (33.9M€ maamaks) vs Loksa best (81k€) — dishonest without the
  rahvastik join. The share is comparable across KOV sizes.
- YoY trend COMPUTED but NOT scored: the 2025 revaluation reform makes
  one jump noise (Rae +83.9%, Raasiku +38.4%, Jõelähtme +36.6%).
  Revisit with 2026-full + 2027.
- Cousins, untouched: maamaks rate leg (`dims_p4_emta`), MARU
  choropleths (pattern precedent), Statamet KOV tables. #521
  inside-Tallinn flatness acknowledged: Tallinn is one KOV row.
- New files only, zero shared-file edits. Monthly harvest at most.

## Reopening checklist

1. Re-pull monthly at most; on each yearly file, re-paste the 16-KOV
   share table and re-lock cutoffs only if tertiles move materially.
2. If Statamet rahvastik is joined, add per-capita legs as NEW dims
   (never replace the share — different question).
3. If EMTA adds a CC tag, record the exact string here.
