# P4 citybudget verdict note — Tallinna linna eelarve, P4-019 leg (issue #326 demo)

> Dated-negative verdict for issue #326 (demo). Checked 2026-09-13.
> Single-param demo: P4-019 is the only param naming this source, so
> no coverage follow-up is owed. The scorer lives in
> `services/scoring/dims_p4_citybudget.py`, pinned by
> `services/scoring/tests/test_dims_p4_citybudget.py`.

## Verdict

**No open machine feed — the dim stays NULL with an Estonian reason.**
Tallinn publishes its budget as a human page
(`tallinn.ee/et/tallinna-linna-eelarve`, title "Tallinna linna
eelarve | Tallinn") with yearly PDF budget books (2024/2025/2026 "EA
raamat — KOOND") and year-stamped comparison spreadsheets
("Võrdlusandmed 2025. aasta eelarve ja 2026. aasta eelarve eelnõu
kohta"); the strategy page (`/et/eelarvestrateegia`) is strategy
PDFs only. There is no per-KOV finance table and no per-listing data
to poll — and Tallinn's own site can never carry other KOVs'
budgets, so the per-KOV table shape P4-019 requires cannot come from
here. There is no ingestion to cache and no TTL beyond this one-off
check: re-probe yearly (the param's TTL is annual), or sooner if
tallinn.ee or Teabevärav gains a machine-readable per-KOV budget
table.

## Openness evidence (one polite round, 2026-09-13, no file download, no auth)

3 content GETs + 1 redirect + 1 HEAD total (single requests,
labelled one-off user-agent `home-finder citybudget openness-check
#326 (one-off, single GETs, no retry; contact via GitHub
home-finder)`, `--max-time 25`, headers + visible-text keyword scope
read only). Raw bodies: `/tmp/hf-citybudget-probe/` (one-off PR
record, not committed).

| Check | Observed | Meaning |
|---|---|---|
| `https://www.tallinn.ee/` → HTTP 301 (162 bytes) | Redirect to `/et` | Entry point moved, followed once |
| `https://www.tallinn.ee/et` → HTTP 200 (137832 bytes, ~8.3k visible chars, title "Tallinn \| Tallinn", 255 links) | Real budget pages linked from the homepage itself: `/et/tallinna-linna-eelarve`, `/et/eelarvestrateegia` (plus `/kaasaveelarve/`) | No guessing needed — budget section is first-class navigation |
| `https://www.tallinn.ee/et/tallinna-linna-eelarve` → HTTP 200 (152493 bytes, ~12.7k visible chars, 293 links, 56 eelarve hits) | Yearly PDF budget books + year-stamped comparison xlsx attachments; sweep 0 for võlakoormus / investeering / andmestik / masinloetav / csv / xlsx in prose (avaandmed hits are site-nav chrome; xlsx hits are attachment hrefs, not a dataset endpoint) | Human budget shelf, not a feed |
| `https://www.tallinn.ee/et/eelarvestrateegia` → HTTP 200 (143894 bytes, ~9.5k visible chars, 255 links) | Strategy PDFs only ("Tallinna eelarvestrateegia aastateks 2024 – 2027", "Tallinn 2035" rakenduskava); same 0-sweep | Strategy shelf, not a feed |
| `HEAD .../Võrdlusandmed%202025-2026%2014.01.2026_1.xlsx` → HTTP 200, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, 563075 bytes | A real spreadsheet — but a Tallinn-internal year-to-year draft comparison ("Võrdlusandmed 2025. aasta eelarve ja 2026. aasta eelnõu kohta"), not a per-KOV table | Headers-only check; file NOT downloaded, NOT parsed |

Judgment call: the check stopped at page level on purpose — no
spreadsheet download, no PDF parsing, no kaasaveelarve
(participatory-budget) crawl, no site-search crawling, no Teabevärav
re-probe (andmed.eesti.ee/dataset is a JS shell per the #301
precedent). Deeper probing is exactly the enumeration this repo
refuses (AGENTS.md §5). Files-exist is still a negative verdict for
the three named reasons in the module docstring (single-KOV, no
stable feed, PDFs are not per-listing data).

## Honest shape per param (NULL until a feed appears)

| Param | Dim key | Honest shape when a feed lands | Buyer-side check meanwhile |
|---|---|---|---|
| P4-019 KOV fiscal health (demo) | `eelarve_citybudget` | per-KOV table, annual (võlakoormus, investeeringud, maamaksu trend — the city-budget leg) | Read the budget page + eelarvestrateegia (tallinn.ee/et/tallinna-linna-eelarve); ask võlakoormus + investeeringud; Statamet leg dims_p4_stat + EMTA leg dims_p4_emta + Rahandusministeeriumi leg dims_p4_rahmin + Riigikontrolli leg dims_p4_riigik + arengukava leg dims_p4_cityplans + overturn-#242 G16 tables |

Never 0 and never 100 would apply once scored (a published budget
book is not proof of a healthy KOV); today the reason says `EI OLE`
and points at the concrete checks above. Every scored-future reason
must trace to a joined record.

## Judgment calls (for the reviewer)

1. Single-param demo, no coverage issue: P4-019 source (1) is the
   only parameters4.md line naming Tallinna linna eelarve, so one
   module, one test file, one verdict note — no second file
   importing a pipeline that does not exist (Riigikontroll #316
   precedent). The issue body's "remaining 0 params" line is taken
   literally.
2. Pairing rationale: the EMTA sibling (dims_p4_emta.py,
   `dim_fiscal_health`), the Rahandusministeeriumi sibling
   (dims_p4_rahmin.py, `dim_fiscal_rahmin`) and the Riigikontrolli
   sibling (dims_p4_riigik.py, `dim_audit_riigik`) were read first;
   their P4-019 slices are named, never re-scored here, and
   dims_group16*.py is untouched. Same split-slice precedent as
   P4-020 (ATA notices in dims_p4_ata, bureau scores NULL in
   dims_p4_creditinfo).
3. Files-exist is still negative: the openly readable budget page
   plus its PDF books and comparison xlsx were deliberately NOT
   turned into a proxy score (budget-PDF-exists-for-Tallinn would
   score every listing identically while claiming fiscal health).
4. No shared-file edits (livability.py, WEIGHTS, layers, layers.md,
   parameters4.md untouched): 3 new files only. Central hook (enrich
   join + WEIGHTS rebalance) stays one joint change across all
   batches.

## Reopening checklist (when a pollable feed appears)

1. Re-run the probes above yearly (or sooner if tallinn.ee or
   Teabevärav gains a per-KOV budget dataset); paste fresh evidence
   in the reopen PR.
2. If a per-KOV budget table appears, transcribe one vintage into
   the cache dir and run it through a parser + per-KOV join on
   fixtures first.
3. Graduate the dim to a per-KOV table ONLY from joined records;
   keep NULL-with-Estonian-reason for every missing leg.
4. Add the explicitly-flagged live integration test (not a unit run).
