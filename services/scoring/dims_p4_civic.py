"""P4 civic dims (issue #320, single-param demo, no coverage issue).

Demo (#320): civic participation signals via P4-039 end-to-end in
Tallinn — openness verification plus the honest-shape turnout leg,
the participatory-budget leg, and the cleanup-campaign leg. Single
param: P4-039 Civic capital (turnout + OSM freshness), the three
legs of its DATA SOURCES line (Valimiskomisjon turnout per
jaoskond + kaasava eelarve + Teeme Ära). Honest shape when feeds
land: precinct/hex choropleth, Group-20 taste-match only, never an
ethnic/wealth proxy.

OPENNESS VERDICT (checked 2026-09-13, dated verdict keeps the
NULLs per #320): mixed — a verified positive-partial for static
result numbers, negative for everything needed to join them to a
listing. Polite evidence, 10 served requests total (nine single
GETs with a labelled one-off user-agent, 25 s timeout, no retries,
2 s pacing, plus one single licensed static-file download;
headers + visible-text keyword scope read only, no scraping, no
auth, no form driving, no archive-UI driving, no service
enumeration), raw bodies cached at /tmp/hf-civic-probe/ (one-off
PR record, never committed):
* https://valimised.ee/ -> HTTP 301 (162 B) to the www host
  (canonical redirect, documented once, not spidered).
* https://www.valimised.ee/ -> HTTP 200 (~79 KB, ~4.8k visible
  chars). Human election site with result-archive nav per
  election (RKV/KOVV/EP/VPV/RH/RKJV üldstatistika pages),
  "Statistika ja analüüs" + "Valimiste avaandmed" nav. The 1x
  "api" is a substring artifact inside "etapid" (stages), not a
  feed pointer; "statistika" 8x is archive nav prose.
* https://www.valimised.ee/et/valimiste-arhiiv/valimiste-avaandmed
  -> HTTP 200 (~89 KB, ~5.7k visible chars, one follow of the
  site's own advertised open-data nav pointer). POSITIVE-PARTIAL:
  "Avaandmed on tervikuna allalaaditavad masinloetavas
  XML-formaadis, tasuta ... (CC BY 4.0). Avaandmed avaldatakse
  XML-formaadis veebilehel pärast valimistulemuste
  väljakuulutamist ning need ei uuene reaalajas." Related files:
  seven static per-election ZIPs (KOV2013–2021, RK2015/2019,
  EP2014/EP2019 vintages on this page; newer data behind the
  unfollowed "Valimiste avaandmed alates 2023" hub). Boundary
  sweep on the full page: 0x geomeetria/wfs/geojson/shp/gml/
  koordinaat; "piir" 1x is "ligipääsupiiranguteta" (no access
  restrictions), "kaart" 2x is "Sisukaart" (sitemap), "jaoskonna"
  4x is voting-procedure nav prose — no precinct-boundary feed
  advertised anywhere at landing/open-data level.
* KOV2021_election_result_data.zip (one licensed CC-BY download,
  HTTP 200, 2 814 943 B): per-municipality DETAILED_RESULT XMLs
  (Tallinn = PARISH_0784, ~4.0 MB, generated 2021-10-22) plus
  PARTICIPATION_INFO time series + EHAK classifier + Estonian
  usage PDF. Structure check (tags/rows only, aggregates, no
  personal data): Tallinn participation rows are EIGHT
  valimisringkond rows (R1–R8, districtNumber 1–8) — ringkond
  granularity, NO jaoskond (precinct) rows; PARTICIPATION_INFO
  is county-level (Harju maakond) control-time series. So the
  numbers exist one level coarser than the param's honest shape.
* https://www.tallinn.ee/et/otsing?search_api_fulltext=valimisaktiivsus
  -> HTTP 200 (~136 KB, server-rendered, ~8.6k visible chars).
  3x "valimisaktiivsus" is a youth-turnout grant-call news item
  (ministry fund, not a table); 2x "avaandmed" + 4x "statistika"
  are footer/nav chrome ("Uuringud ja statistika", "Avaandmed"
  links). No turnout table.
* https://www.tallinn.ee/et/otsing?search_api_fulltext=kaasav%20eelarve
  -> HTTP 200 (~146 KB, server-rendered, ~9.7k visible chars).
  13x "kaasav" is human service/vote content ("Kaasav eelarve
  2026", "Koos loodud linn 2026" vote 8.–28. September 2026)
  plus nav; 0x csv/geojson/wfs/masinloetav/andmestik. No
  participation table per linnaosa.
* https://www.teemeara.ee/ -> HTTP 200 (~42 KB, ~2.7k visible
  chars, title "Esileht – Teeme Ära"). Campaign front page:
  "talgupäev" 8x is event news + "PANE TALGUD KIRJA" signup
  CTA; 0x feed keywords. No per-asum participation register.
* https://andmed.eesti.ee/dataset?q=<valimised|kaasav eelarve|
  teeme ära> -> HTTP 200 each (~75 KB, 10 visible chars, title
  "Teabevärav" JS shell), zero keyword hits — no trivially
  pollable national-portal civic dataset (same shell as the
  #264/#277/#284/#290/#299 national-portal checks).
So all three dims return None for EVERY input including missing
origin: ringkond-level 2021 numbers without precinct boundaries
cannot paint the param's precinct/hex choropleth, and a
linnaosa-turnout gradient from a stale coarse snapshot risks
exactly the ethnic/wealth proxy the param forbids. Reasons say
"hinnang" (estimate) and "EI OLE" and point at the concrete
buyer-side check (valimiste avaandmed page + kohapealne
ühisvara-vaatlus, kaasava eelarve hääletusel osalemine +
linnaosakogu päring, talgutele registreerimine + asumiseltsi
päring) — never a faked area score. P4-039 stays taste-match
only, never an ethnic/wealth proxy, per parameters4.md.

SIBLING OVERLAP (read first, not edited): the other P4-039 legs
stay where they live and are named here, never re-scored. SCORED
legs — none: every existing P4-039 slice is a NULL agreer, each
owning a distinct artifact. NULL agreers — OSM edit freshness
(dims_p4_osm dim_civic: fixme density points the wrong way),
KÜ remondifondi echo (dims_p4_arireg dim_commons_echo: fond
known, turnout/OSM freshness not), library/youth-centre visits
per linnaosa (dims_p4_libs dim_civic_use_visits, civic-use leg,
#379). This module owns ONLY the three DATA-SOURCES legs
below: precinct/ringkond turnout numbers (a different artifact
from OSM freshness and from the fond echo), the participatory-
budget participation table (a different artifact from library
visits), and the cleanup-campaign participation register (a
different artifact from all of them). Distinct dim keys, no
double-scoring (same split-slice precedent as P4-020 across
ata/creditinfo and P4-048 across ehr/peatus/tlt/osm/green/
recre).

Style mirrors services/scoring/dims_p4_recre.py (#312, the
dated-verdict single-param precedent): every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for
precinct turnout, participatory-budget votes, or cleanup
participation, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #320 states the remaining
  0 params using this source need only a follow-up created after
  this demo — with no ingestion pipeline (nothing pollable to
  extend) there is nothing to split out. Three dims (1:1 with
  the DATA SOURCES artifacts — different honest shapes with
  different buyer checks), one module, three new files, no
  shared-file edits.
* The verified static XML ZIPs are deliberately NOT ingested:
  ringkond-only granularity (R1–R8, verified in the KOV2021
  Tallinn file — no jaoskond rows), vintages topping out at
  2021 on the static page (newer data behind the unfollowed
  post-2023 hub + per-election archive UIs, whose per-jaoskond
  driving would be scraping human publications, out of scope
  per AGENTS.md section 5), and no precinct-boundary feed to
  join any of it to a listing. Pulling numbers we cannot
  honestly join would be fake precision (OTA PR #131
  precedent). The ZIP stays /tmp PR-record evidence with TTL
  below, never committed, never parsed at runtime.
* No fetch_* helper: with no pollable living feed there is no
  pull to wrap, and a fetcher around human vote/campaign pages
  would be brittle scraping dressed as ingestion (komun #290
  precedent — verdict modules carry no network code, pinned by
  test_module_adds_no_network_calls).
* The check stopped at landing/search/shell + one advertised
  open-data page + one licensed static file on purpose — no
  archive-UI driving, no per-jaoskond result scraping, no
  Teabevärav JS-app driving, no talgute-registration scraping.

TTL: openness check one-off 2026-09-13. Election result ZIPs
are static per vintage ("ei uuene reaalajas", published once
after proclamation): re-probe per election cycle (KOV/RK/EP)
or sooner if a jaoskond-boundary feed appears. Kaasav eelarve
(annual vote) and Teeme Ära (annual talgupäev): re-probe
yearly. If a precinct-boundary feed plus jaoskond-level numbers
appear, graduate dim_civic_turnout to the precinct/hex join —
fixtures first, taste-match guard kept.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-039 (demo): precinct turnout needs the jaoskond-level join.
# Verified: static per-election XML ZIPs exist (CC BY 4.0) but carry
# ringkond rows only (KOV2021 Tallinn: R1–R8, no jaoskond rows),
# and no precinct-boundary feed is advertised at landing/open-data
# level — so no honest precinct/hex choropleth exists to score.
# ---------------------------------------------------------------------------

def dim_civic_turnout(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-039: NULL — jaoskonna-tasandi osalus + piirid liitmiseks puuduvad."""
    return None, ("Valimisaktiivsus on maitse-hinnang (EI OLE jaoskonna- "
                  "tasandi liidest liitmiseks): valimised.ee avaandmed on "
                  "staatised valimiste-lõikes XML ZIP-id (KOV2021 "
                  "kontrollitud: osalus ringkonna-tasandil R1–R8, "
                  "jaoskonna-ridu pole; CC BY 4.0, pärast tulemuste "
                  "väljakuulutamist, reaalajas ei uuene) ning "
                  "jaoskonnapiiride kihti maandumis- ja avaandmete "
                  "tasandil pole — ilma piirideta vana jäme "
                  "linnaosa-gradient oleks keelatud rahvus- ja "
                  "jõukusproksi riskiga (maitsefilter, mitte proksi). "
                  "Vaata valimiste avaandmete lehte, hinda ühisvara "
                  "kohapealsel jalutuskäigul ning vaata värskuse-NULL-i "
                  "dims_p4_osm-ist (dim_civic), fondikaja-NULL-i "
                  "dims_p4_arireg-ist (dim_commons_echo) ja "
                  "külastatavuse-NULL-i dims_p4_libs-ist "
                  "(dim_civic_use_visits), ära feigi")


# ---------------------------------------------------------------------------
# P4-039 (demo): participatory-budget participation per linnaosa
# needs a pollable vote/participation table. The city publishes
# human service/vote pages only ("Kaasav eelarve 2026" vote
# 8.–28. September 2026), zero feed keywords.
# ---------------------------------------------------------------------------

def dim_civic_participatory_budget(origin: Optional[Tuple[float, float]],
                                   pois: Optional[List[dict]]) -> Score:
    """P4-039: NULL — kaasava eelarve osalustabel per linnaosa puudub."""
    return None, ("Kaasava eelarve osalus on maitse-hinnang (EI OLE "
                  "osalustabelit per linnaosa): tallinn.ee kaasava "
                  "eelarve lehed on inimloetav teenus- ja hääletusinfo "
                  "(Kaasav eelarve 2026, Koos loodud linn 2026 hääletus "
                  "8.–28. septembrini 2026), masinloetavat tabelit pole "
                  "— osale hääletusel, küsi linnaosakogult osalusarve "
                  "ning vaata osalus-NULL-e dims_p4_osm-ist (dim_civic) "
                  "ja dims_p4_libs-ist (dim_civic_use_visits), ära feigi")


# ---------------------------------------------------------------------------
# P4-039 (demo): cleanup-campaign (Teeme Ära) participation per asum
# needs a pollable participation register. The campaign site is a
# front page (talgupäev news + PANE TALGUD KIRJA signup CTA),
# zero feed keywords.
# ---------------------------------------------------------------------------

def dim_civic_cleanup_action(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-039: NULL — Teeme Ära osalusregister per asum puudub."""
    return None, ("Heakorratalgute osalus on maitse-hinnang (EI OLE "
                  "osalusregistrit per asum): teemeara.ee on kampaania- "
                  "esileht (talgupäeva uudised + PANE TALGUD KIRJA "
                  "registreerimine), mitte masinloetav register — pane "
                  "talgud kirja, küsi asumiseltsilt osalust ning vaata "
                  "osalus-NULL-e dims_p4_osm-ist (dim_civic) ja "
                  "dims_p4_libs-ist (dim_civic_use_visits), ära feigi")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_CIVIC_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_CIVIC_DIMS = (
    ("civic_turnout", "P4-039", dim_civic_turnout),
    ("civic_participatory_budget", "P4-039", dim_civic_participatory_budget),
    ("civic_cleanup_action", "P4-039", dim_civic_cleanup_action),
)


def score_p4_civic(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All three P4 civic dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_CIVIC_DIMS). Every value
    is None by design — ringkond-only static numbers without
    precinct boundaries plus unpublished participation tables,
    never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_CIVIC_DIMS}
