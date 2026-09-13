"""P4 Riigikontroll dim (issue #316 demo only): KOV audit verdict.

Demo (#316): the Riigikontroll KOV-audit source via P4-019 KOV fiscal
health (volakoormus, investments, maamaks trend, Tallinn where
available) end-to-end in Tallinn - the Riigikontroll audit leg
(per-KOV table, annual). Single-param demo: P4-019 is the only param
naming this source (parameters4.md P4-019 source (6) "Riigikontroll
KOV auditid (Tallinn where available)"), so there is no coverage
follow-up issue; P4-019's sibling legs are already scored where they
live (see SIBLING OVERLAP).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #316: audit publications are human report pages, not a pollable
per-KOV table, so the dim stays NULL). Polite evidence, 4 served
requests with a labelled one-off user-agent `home-finder riigik
openness-check #316 (one-off, single GETs, no retry; contact via
GitHub home-finder)`, `--max-time 25`, headers + visible-text scope
reads only (no PDF download, no auth, no form driving, no site-search
crawling), raw bodies cached at /tmp/hf-riigik-probe/ (one-off PR
record, never committed):
* GET https://www.riigikontroll.ee/ -> HTTP 200 (80747 bytes, ~4.9k
  visible chars, title "Avaleht | Riigikontroll"). Audit topic
  present in prose (15 audit hits, "Eelarve, rahandus, maksundus"
  filter); sweep 0 for andmestik / masinloetav / avaandmed /
  open data (the csv/json/rss raw hits are Drupal chrome: ajax-loader
  SVG markup, drupal-settings-json, feed-link tags).
* GET https://www.riigikontroll.ee/auditid (guessed) -> HTTP 404
  ("Lehte ei leitud", 60157 bytes; documented negative guess, not a
  real path - the listing lives at /auditiaruanded/koik, below).
* GET https://www.riigikontroll.ee/en/audits -> HTTP 200 (166382
  bytes, ~12.8k visible chars, title "Auditid | Riigikontroll",
  226 links). Links the real Estonian listing /auditiaruanded/koik
  plus /en/audits/all and per-type filters - human navigation, no
  dataset endpoint.
* GET https://www.riigikontroll.ee/auditiaruanded/koik -> HTTP 200
  (173503 bytes, ~12.5k visible chars, 0 PDF hrefs on the listing
  itself). Per-report pages (/auditiaruanded/<slug>) with topic
  filters ("Eelarve, rahandus, maksundus"); KOV audits exist as
  prose reports (e.g. "Asutuste vork ja kinnisvara kohalikes
  omavalitsustes parast haldusterritoriaalset reformi" - "Kuidas on
  omavalitsustes hallatavate asutuste vorku ... 2018-2024
  korrastatud?"); sweep 0 for xlsx / andmestik / masinloetav /
  avaandmed / open data (the lone csv/json raw hits are the same
  Drupal chrome as above).

So the dim returns None for EVERY input including missing origin:
a per-KOV fiscal table (volakoormus, investeeringud, maamaksu trend)
painted from a one-off hand-read of human audit prose would be fake
precision (OTA PR #131 precedent), and audit PDFs are not pollable
per-listing data. The reason says "hinnang" (estimate) and "EI OLE"
and points at the concrete buyer-side checks (the Riigikontroll
audit report page for the KOV in question, Tallinna eelarve +
eelarvestrateegia, scored fiscal cousins below) - never a faked
area score.

SIBLING OVERLAP (read first, not edited): the P4-019 legs owned by
the EMTA and Rahandusministeerium siblings stay scored where they
live - this module owns ONLY the Riigikontroll audit leg and never
re-scores them:
* EMTA maamaksu-maara/trendi leg - dims_p4_emta dim_fiscal_health
  (key fiscal_health, rate level + trend, capped 70).
* Rahandusministeeriumi KOV-finantsandmete leg - dims_p4_rahmin
  dim_fiscal_rahmin (key fiscal_rahmin, documented NULL).
The Statamet KOV-finantsnaitajte leg (dims_p4_stat
dim_kov_fiscal_stat), the arengukava investeeringute-tabeli leg
(dims_p4_cityplans dim_investeering_cityplans) and the overturn-#242
G16 tax-table legs (dims_group16*.py, untouched) are likewise named,
never re-scored.

Style mirrors services/scoring/dims_p4_s2.py (#305): the scorer is
pure and offline-tested - (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois; this
module adds no network calls, no Overpass fragment, and no tag
mapping: there is no honest snapshot tag to query for a KOV audit
finding, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing audit-table leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-019 is the only param
  naming this source, so one module, one test file, one verdict
  note - no second file importing a pipeline that does not exist.
  The issue body's "remaining 0 params" line is taken literally:
  no follow-up coverage issue is owed.
* Human report pages are not a table: the openly readable listing
  plus per-report pages were deliberately NOT turned into a proxy
  score (report-exists-for-Tallinn would score every listing
  identically while claiming fiscal health). The reason says this
  plainly instead of hiding the open-prose / no-table split.
* The check stopped at listing level on purpose: one listing page
  plus the topic/KOV title evidence carries the verdict for the
  source family - per-report PDF downloads and full-text parsing
  would add pages, not a per-KOV machine table. No Teabevärav
  re-probe (andmed.eesti.ee/dataset is a JS shell per the #301
  precedent) and no DOC/PDF parsing (AGENTS.md section 5).
* (origin, pois) signature instead of a join signature: with the
  dated-negative verdict there is no ingestion and hence no join
  input - the dim reports the audit-table gap for any listing, the
  same shape as the Sentinel-2 dated-negative NULL.
* Re-probe yearly (param TTL: annual): audits publish a few times
  a year as prose; a yearly re-check of /auditiaruanded/koik for a
  machine-readable per-KOV table is the honest refresh cadence.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-019: documented no-map Riigikontroll-audit-leg NULL (OTA PR #131
# precedent). KOV audits (volakoormus, investeeringud, maamaksu trend,
# Tallinn where available) are human report publications with no public
# machine-readable per-KOV table (2026-09-13 dated-negative verdict
# above); the scorer reports the gap with concrete buyer-side checks
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_audit_riigik(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-019: NULL - Riigikontroll KOV-audititabel puudub (no map)."""
    return None, ("KOV finantstervis Riigikontrolli audititest "
                  "(võlakoormus, investeeringud, maamaksu trend, "
                  "per-KOV tabel, aastane) on auditi-hinnang "
                  "(EI OLE liidestatud audititabelit): Riigikontroll "
                  "avaldab auditeid inimloetavate aruandelehtedena "
                  "(riigikontroll.ee/auditiaruanded/koik, teema "
                  "'Eelarve, rahandus, maksundus'), mitte automaatselt "
                  "päritava KOV-tabelina — loe Tallinna/KOV aruannet "
                  "aruandelehelt ning hinda Tallinna eelarvest ja "
                  "eelarvestrateegiast (tallinn.ee), vaata Statameti "
                  "KOV-legi dims_p4_stat-ist (dim_kov_fiscal_stat), EMTA "
                  "maamaksu-legi dims_p4_emta-st (dim_fiscal_health), "
                  "Rahandusministeeriumi finantslegi dims_p4_rahmin-ist "
                  "(dim_fiscal_rahmin), arengukava investeeringu-legi "
                  "dims_p4_cityplans-ist (dim_investeering_cityplans) ja "
                  "overturn-#242 maksutabeleid dims_group16*.py-st, "
                  "ära feigi")


P4_RIIGIK_DIMS = (
    ("audit_riigik", "P4-019", dim_audit_riigik),
)


def score_p4_riigik(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 Riigikontroll dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_RIIGIK_DIMS). The value
    is None by design - human audit publications with no pollable
    per-KOV table, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_RIIGIK_DIMS}
