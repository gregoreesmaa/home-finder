# P4 renovation-grant verdict note (issue #538)

Date: 2026-09-16. Scope: P4-010 renovation-grant status, EISA SFOS leg
(apartment-building reconstructions supported since 2014), per-building
join scorer (`services/scoring/dims_p4_recongrant.py`).

## Openness verdict: OPEN (keyless direct XLSX, CC BY)

Polite probes, one GET each, `home-finder-probe/1.0` User-Agent,
`--max-time 60`, raw file at /tmp/hf-probes/ (one-off PR record, never
committed):

| Probe | Result |
|---|---|
| `GET .../api/v2/datasets/858e5768-.../distribution/f68abab5-.../file` | HTTP 302 → signed S3 URL (`Korterelamute-rekonstrueerimise-toetamine.xlsx`) |
| `GET <signed S3 URL>` (redirect followed once) | HTTP 200, 163 884 bytes, `application/octet-stream`, Excel 2007+ |
| Local inspection (openpyxl, no further network) | 1 sheet, 15 columns, 1313 data rows (header `Ehitusregistrikood ` has a trailing space; KOV values have a leading space, e.g. ` Anija vald`) |
| Coverage tally | Harju maakond 277 rows (21.1%); Tartu 217, Lääne-Viru 178; EHR-code fill 650/1313 overall (49.5%), 108/277 Harjumaa (39.0%) — above the 20% token bar, EHR join is real |
| Status / period values | `Lõpetatud` 916, `Rahastatud` 396 (+1 blank); periods 2014-2020 (632), 2021-2027 (567), 2020-2026 (113); funding years 2015–2026 |

Licence: CC BY (catalogue statement, publisher EISA). Attribution
`EISA (ettevõtlus- ja innovatsioonifond), andmed.eesti.ee, CC BY` rides
in `GRANTS_ATTRIBUTION`. IRREG feed → annual re-probe at most
(`GRANTS_TTL_DAYS = 365`).

## Honest-shape table (per-building join dim)

| Param | EISA slice consumed | Shape when joined | When missing |
|---|---|---|---|
| P4-010 grant (EISA leg) | status + funding year | `Lõpetatud` 75 / `Rahastatud` 60 / other matched status 50 neutral | NULL (EI OLE + KÜ remondifond/eelarve check) — never "unrenovated" |

No depth columns exist (no energy class before/after), so every scored
reason states grant ≠ quality. EHR-code hits outrank address hits; the
address fallback names its weaker join in the reason.

## Pairing rationale (why this slice, why these bands)

- Bands are status-based, not grant-share-based: `Toetus/kogumaksumus`
  varies by round rules, so a share cutoff would re-punish older rounds.
  Recency rides in the reason (funding year), not the score.
- Cousins, untouched: kliimakava district targets (`dims_p4_kliima`),
  EIS register leg (`dims_p4_eis`), EHR mirror slice (`dims_p4_ehr`),
  HOA buyer-side legs (Group 17). Distinct dim keys, no double-score.
- No shared-file edits: 3 new files only
  (`dims_p4_recongrant.py` + test + this note). Central hook (enrich
  join + WEIGHTS rebalance) stays one joint change across all batches.

## Reopening checklist (when the register changes shape)

1. Re-pull each spring at most (IRREG feed); paste row counts + EHR
   fill + any new status values in the reopen PR.
2. If a depth column appears (energy class before/after), graduate the
   bands from joined rows only — never backfill quality by hand.
3. If EHR fill drops under 20% Harjumaa, flip to documented no-map
   (NULL + tally) per the issue's token rule.
