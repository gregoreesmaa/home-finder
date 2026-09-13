"""P4 citybudget dim (issue #326 demo only): Tallinna linna eelarve verdict.

Demo (#326): the Tallinna linna eelarve source via P4-019 KOV fiscal
health (volakoormus, investments, maamaks trend) end-to-end in
Tallinn - the city-budget leg (per-KOV table, annual). Single-param
demo: P4-019 is the only param naming this source (parameters4.md
P4-019 source (1) "Tallinna linna eelarve + eelarvestrateegia
(võlakoormus, investeeringud, tallinn.ee)"), so there is no coverage
follow-up issue; P4-019's sibling legs are already scored where they
live (see SIBLING OVERLAP).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #326: budget publications are human pages plus year-stamped file
attachments, not a pollable per-KOV table, so the dim stays NULL).
Polite evidence, 3 content GETs plus 1 redirect plus 1 HEAD with a
labelled one-off user-agent `home-finder citybudget openness-check
#326 (one-off, single GETs, no retry; contact via GitHub
home-finder)`, `--max-time 25`, headers + visible-text scope reads
only (no PDF/XLSX download, no auth, no form driving, no site-search
crawling), raw bodies cached at /tmp/hf-citybudget-probe/ (one-off PR
record, never committed):
* GET https://www.tallinn.ee/ -> HTTP 301 to /et (162 bytes).
* GET https://www.tallinn.ee/et -> HTTP 200 (137832 bytes, ~8.3k
  visible chars, title "Tallinn | Tallinn", 255 links). Real budget
  pages linked from the homepage itself: /et/tallinna-linna-eelarve,
  /et/eelarvestrateegia (plus /kaasaveelarve/).
* GET https://www.tallinn.ee/et/tallinna-linna-eelarve -> HTTP 200
  (152493 bytes, ~12.7k visible chars, title "Tallinna linna eelarve
  | Tallinn", 293 links, 56 eelarve hits). Yearly budget books as
  PDFs (2024/2025/2026 "EA raamat - KOOND") plus year-stamped
  comparison spreadsheets ("Võrdlusandmed 2025. aasta eelarve ja
  2026. aasta eelarve eelnõu kohta", yearly URLs). Sweep 0 for
  võlakoormus / investeering / andmestik / masinloetav / csv / xlsx
  in prose (the avaandmed hits are site-nav chrome); the xlsx hits
  are attachment hrefs, not a dataset endpoint.
* GET https://www.tallinn.ee/et/eelarvestrateegia -> HTTP 200
  (143894 bytes, ~9.5k visible chars, 255 links). Strategy PDFs
  only ("Tallinna eelarvestrateegia aastateks 2024 - 2027",
  "Tallinn 2035" rakenduskava) - same 0-sweep as above.
* HEAD .../Võrdlusandmed%202025-2026%2014.01.2026_1.xlsx -> HTTP 200,
  Content-Type
  application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,
  563075 bytes. A real spreadsheet - but a Tallinn-internal
  year-to-year draft comparison, not a per-KOV table (see judgment
  calls).

So the dim returns None for EVERY input including missing origin:
a per-KOV fiscal table (volakoormus, investeeringud, maamaksu trend)
painted from a one-off hand-read of Tallinn's own budget PDFs would
be fake precision (OTA PR #131 precedent), and budget PDFs plus
year-stamped draft-comparison spreadsheets are not pollable
per-listing data. The reason says "hinnang" (estimate) and "EI OLE"
and points at the concrete buyer-side checks (the budget page
itself, eelarvestrateegia, scored fiscal cousins below) - never a
faked area score.

SIBLING OVERLAP (read first, not edited): the P4-019 legs owned by
the EMTA, Rahandusministeerium, Riigikontroll, Statamet and
cityplans siblings stay scored where they live - this module owns
ONLY the city-budget (Tallinna eelarve) leg and never re-scores
them:
* EMTA maamaksu-maara/trendi leg - dims_p4_emta dim_fiscal_health
  (key fiscal_health, rate level + trend, capped 70).
* Rahandusministeeriumi KOV-finantsandmete leg - dims_p4_rahmin
  dim_fiscal_rahmin (key fiscal_rahmin, documented NULL).
* Riigikontrolli auditi leg - dims_p4_riigik dim_audit_riigik (key
  audit_riigik, documented NULL).
The Statamet KOV-finantsnaitajte leg (dims_p4_stat
dim_kov_fiscal_stat), the arengukava investeeringute-tabeli leg
(dims_p4_cityplans dim_investeering_cityplans) and the overturn-#242
G16 tax-table legs (dims_group16*.py, untouched) are likewise named,
never re-scored.

Style mirrors services/scoring/dims_p4_riigik.py (#316): the scorer
is pure and offline-tested - (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois; this
module adds no network calls, no Overpass fragment, and no tag
mapping: there is no honest snapshot tag to query for a city-budget
row, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing budget-table leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-019 is the only param
  naming this source, so one module, one test file, one verdict
  note - no second file importing a pipeline that does not exist.
  The issue body's "remaining 0 params" line is taken literally:
  no follow-up coverage issue is owed.
* Files-exist is still a negative verdict: the openly readable
  budget page plus its PDF books and comparison xlsx were
  deliberately NOT turned into a proxy score, for three named
  reasons. (1) Single-KOV: Tallinn publishes only its own budget,
  so the per-KOV table shape P4-019 requires can never come from
  tallinn.ee - "budget PDF exists for Tallinn" would score every
  Tallinn listing identically while claiming fiscal health.
  (2) No stable feed: the comparison spreadsheets live at
  year-stamped attachment URLs that change every budget round, so
  there is nothing pollable to cache with a TTL - hand-mapping
  this year's layout is a one-off read, not an ingestion.
  (3) PDFs are not per-listing data: no PDF/XLSX parsing per the
  #316 precedent and AGENTS.md section 5. The reason says this
  plainly instead of hiding the open-page / no-table split.
* The check stopped at page level on purpose: one budget page plus
  the strategy page plus a headers-only xlsx check carries the
  verdict for the source family - downloading and parsing the
  550 kB spreadsheet would add bytes, not a per-KOV machine table.
  No kaasaveelarve (participatory-budget) crawl, no Teabevärav
  re-probe (andmed.eesti.ee/dataset is a JS shell per the #301
  precedent) and no DOC/PDF parsing.
* (origin, pois) signature instead of a join signature: with the
  dated-negative verdict there is no ingestion and hence no join
  input - the dim reports the budget-table gap for any listing, the
  same shape as the Riigikontroll dated-negative NULL.
* Re-probe yearly (param TTL: annual): budgets publish yearly as
  books plus draft comparisons; a yearly re-check of
  /et/tallinna-linna-eelarve for a machine-readable per-KOV table
  is the honest refresh cadence.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-019: documented no-map city-budget-leg NULL (OTA PR #131
# precedent). Tallinna linna eelarve + eelarvestrateegia (volakoormus,
# investeeringud, maamaksu trend) are human budget publications with
# no public machine-readable per-KOV table (2026-09-13 dated-negative
# verdict above); the scorer reports the gap with concrete
# buyer-side checks instead of a faked number.
# ---------------------------------------------------------------------------

def dim_eelarve_citybudget(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-019: NULL - Tallinna eelarve KOV-tabel puudub (no map)."""
    return None, ("KOV finantstervis Tallinna linna eelarvest "
                  "(võlakoormus, investeeringud, maamaksu trend, "
                  "per-KOV tabel, aastane) on eelarve-hinnang "
                  "(EI OLE liidestatud eelarvetabelit): Tallinn "
                  "avaldab eelarve inimloetava lehena koos aasta-PDF "
                  "raamatute ja aasta-võrdlusarvutustabelitega "
                  "(tallinn.ee/et/tallinna-linna-eelarve), mitte "
                  "automaatselt päritava KOV-tabelina — loe eelarve "
                  "lehte ja eelarvestrateegiat (tallinn.ee), küsi "
                  "võlakoormust ja investeeringuid ning vaata Statameti "
                  "KOV-legi dims_p4_stat-ist (dim_kov_fiscal_stat), EMTA "
                  "maamaksu-legi dims_p4_emta-st (dim_fiscal_health), "
                  "Rahandusministeeriumi finantslegi dims_p4_rahmin-ist "
                  "(dim_fiscal_rahmin), Riigikontrolli auditilegi "
                  "dims_p4_riigik-ist (dim_audit_riigik), arengukava "
                  "investeeringu-legi dims_p4_cityplans-ist "
                  "(dim_investeering_cityplans) ja overturn-#242 "
                  "maksutabeleid dims_group16*.py-st, ära feigi")


P4_CITYBUDGET_DIMS = (
    ("eelarve_citybudget", "P4-019", dim_eelarve_citybudget),
)


def score_p4_citybudget(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 citybudget dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_CITYBUDGET_DIMS). The
    value is None by design - human budget publications with no
    pollable per-KOV table, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_CITYBUDGET_DIMS}
