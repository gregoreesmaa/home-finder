# P4 arireg: e-Äriregister KÜ reports (new fields) verdict note (issues #257 + #338)

Demo (#257) implements the KÜ-report ingestion + P4-007 end-to-end;
coverage (#338) wires the remaining 13 params off the same ingestion.
One PR closes both because the #338 body states coverage "extends
the demoed ingestion" with "no new plumbing expected": the
company-card slice (founded_year, turnover, payment defaults) rides
the same reports table as the XBRL rows — coverage adds field
readers, not fetchers.

Scope guard: overturn #232 owns the parameters3 e-Äriregister bulk
for p361/p369 in `dims_group04*.py` — untouched (no shared/group
files, `livability.py`, WEIGHTS all unmodified; 3 new files only).
Sibling-leg splits: P4-020 also lives in `dims_p4_ata` (teadaande
slice, cap 75) and `dims_p4_taitur` (kohtutäitur slice); P4-021 also
in `dims_p4_ehr` (builder-completion slice, cap 80) and `dims_p4_ata`
(notice slice, cap 75); P4-010's grant level also in `dims_p4_ehr`.
This module scores ONLY the arireg legs with `_arireg`-suffixed keys.

## Openness verdict: OPEN-but-gated (2026-09-13, keeps per #257)

e-Äriregister HAS an open-data environment, but its bulk API is
contract-gated — no anonymous bulk download verified. Polite
evidence, 9 tiny doc/search reads total (custom UA, no scrape):

```
ariregister.rik.ee/            -> HTTP 303 -> /est (HTTP 200,
  "Juriidilise isiku otsing | e-Äriregister", 80541 B)
  per-company search UI, no bulk link
rik.ee/.../ariregistri-paringud -> HTTP 200 (37760 B)
  documents the "Avaandmete teenus" (open-data download env)
avaandmed.ariregister.rik.ee/.../api-teenuste-tutvustus -> HTTP 200
  "Avaandmete API ehk XML teenuste kasutamiseks on vajalik sõlmida
   RIKiga leping (v.a e-arvete vastuvõtjate ja autocomplete
   päringute kasutamiseks)" — free-tier choice exists ("Ainult
   tasuta API teenuste kasutamiseks ... igakuist lepingutasu ei
   lisandu", review within five workdays)
.../ettevotja-majandusaasta-aruannete-paring -> HTTP 200
  query arireg.majandusaastaAruanneteKirjed_v1 over loetelu_v1,
  RIK-makett structure, TWO periods (A1 + A2 võrdlusperiood)
```

Raw pages: `/tmp/arireg-open/` (one-off PR record, not committed).
Pull contract: max 1 download / 90 d per cache dir
(`ARIREG_TTL_S = 7776000`, parameters4.md P4-007 "annual +
quarterly refresh" ride one quarterly ticket), single GET, no
retries — HTTP 429/errors are a stop signal. `ARIREG_BULK_URL`
stays `None` until the checklist below names a contracted endpoint;
until then the fetcher performs no requests and the scorers stay
NULL with an Estonian EI OLE reason. Paid extracts stay NULL.
Scored shapes are proven on fixtures only (hermetic tests).

## Honest shapes per param (bands, NULL stays NULL)

| Param | Dim key | Scored shape | NULL when |
|---|---|---|---|
| P4-007 loan (demo) | `ku_loan_per_m2` | €/m²: 0→85, ≤50→65, ≤150→40, else 20 (cap 85, ülempiir) | no record / no loan or area row / out of Tallinn |
| P4-007 fund (demo) | `repair_fund_per_m2` | €/m²: <2→25, <8→40, <20→60, else 80 | same as above |
| P4-007 heat (demo) | `heating_cost_per_m2` | €/m²/a: ≤8→80, ≤14→60, ≤22→40, else 25 | same as above |
| P4-010 grant (arireg leg) | `grant_fund_cover_arireg` | always NULL, echoes kogutud fond €/m² | always (EIS register missing) |
| P4-020 enforcement (arireg leg) | `enforcement_arireg` | defaults/debts→20; clean→70 (cap) | fields missing |
| P4-021 age (arireg leg) | `developer_age_arireg` | age <3→45, <10→60, else 75 (cap) | founded_year missing |
| P4-026 fix-it (arireg leg) | `fixit_cost_arireg` | always NULL, echoes hoolduskulu €/m² | always (hex rate missing) |
| P4-034 overheat (arireg leg) | `overheat_roof_arireg` | always NULL, echoes roof_state | always (sim is EHR's) |
| P4-039 civic (arireg leg) | `civic_commons_arireg` | always NULL, echoes kogutud fond | always (turnout/OSM missing) |
| P4-042 smell (arireg leg) | `smell_arireg` | always NULL, names address-cluster join | always (not a KÜ row) |
| P4-044 herd (arireg leg) | `herd_arireg` | always NULL, names address-cluster join | always (not a KÜ row) |
| P4-051 stairwell (arireg leg) | `dead_stairwell_arireg` | arrears→30 (hex flag); clean→NULL | clean or fields missing |
| P4-052 turnover (arireg leg) | `turnover_fund_arireg` | always NULL, echoes A1/A2 dynamics | always (tehingud missing) |
| P4-057 hum (arireg leg) | `heatpump_capex_arireg` | always NULL, echoes capex note | always (EHR + complaints missing) |
| P4-060 stormwater (arireg leg) | `stormwater_cost_arireg` | always NULL, echoes sademevee kulu | always (zone + queue missing) |
| P4-062 waste (arireg leg) | `waste_cost_arireg` | always NULL, echoes prügi/hooldus | always (hex flags missing) |

Measured zero scores (laen 0, fond 0 kirjutatud reana); missing
join stays NULL. Beyond-Tallinn is out of scope, never 0. Every
scored reason says `hinnang` with components; every NULL reason
says `EI OLE` and names the missing input.

## Judgment calls (for the reviewer)

1. Demo + coverage in one PR: #338 defines coverage as extending
   the demo ingestion — one reports table, no second source.
2. P4-007 is three dims, not one composite: loan, fund, and heat
   fail independently; averaging would hide the binding constraint.
3. P4-007 bands are first-cut with no live calibration; MUST be
   recalibrated from a real snapshot on reopen.
4. P4-010 stays NULL-echo on purpose: scoring the fund level again
   would double-score P4-007's fund dim (EHR P4-030/031 precedent).
5. P4-020 clean caps at 70 (below ATA's 75): a ledger with no
   defaults is narrower evidence than a searched notice window.
   Active arrears never score 0 (stale/mis-joined records exist).
6. P4-021 youth scores 45 (thin history, not fraud); cap 75 —
   TTJA complaints stay unjoined in every slice.
7. P4-051 is bad-side-only: a clean single-KÜ ledger does not
   clear the hex (asymmetric by design, pinned by test).
8. P4-042/P4-044 name the missing address-cluster join instead of
   echoing: emitter/employer addresses are a different ariregister
   query, not fields of the KÜ-report rows.
9. No Overpass fragment / tag mapping staged: OSM has no honest
   tag for KÜ ledger rows (group20a no-map precedent).
10. No shared-file edits; central hook (record feed + WEIGHTS
    rebalance) stays one joint change across all batches.

## Reopening checklist (when RIK grants a contract)

1. Re-run the 9 probes; paste fresh evidence.
2. Sign the free-tier contract; set `ARIREG_BULK_URL` to the
   contracted endpoint; pull one Tallinn-KÜ snapshot.
3. Recalibrate `LOAN_BANDS` / `FUND_BANDS` / `HEAT_BANDS` from real
   histograms (especially the heat €/m²/a cut points).
4. Add the explicitly-flagged live integration test (not a unit run).
