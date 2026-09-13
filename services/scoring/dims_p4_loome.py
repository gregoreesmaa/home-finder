"""P4 loome dims (issue #322, single-param demo, no coverage issue).

Demo (#322): Tallinna loomemajandus stats source family for P4-044
end-to-end in Tallinn — openness verification plus the honest-shape
per-linnaosa creative-economy slice (batch 4 source (5): Tallinna
loomemajanduse statistika per linnaosa). Honest shape when a table
lands: linnaosa join feeding the P4-044 grid taste-match (never worth
judgement). Single param: P4-044 Herd of picky people, loome-stats
slice only.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #322): Tallinn publishes no pollable machine-readable
per-linnaosa creative-economy table. Polite evidence, 6 served
requests total (single GETs with a labelled one-off user-agent,
25 s timeout, no retries, 2 s pacing; headers + visible-text keyword
scope read only, no scraping, no auth, no form driving, no service
enumeration, no JS-app driving), raw bodies cached at
/tmp/hf-loome-probe/ (one-off PR record, never committed):
* https://www.tallinn.ee/et/otsing?search_api_fulltext=loomemajandus
  -> HTTP 200 (~138 KB, ~9.0k visible chars, title "Otsi | Tallinn").
  3x loomemajandus = policy/prose pages (Ettevõtjale loomemajandus
  page, uuringud/statistika directory); 0 for csv / geojson / wfs /
  wms / masinloetav / andmestik / api.
* https://andmed.eesti.ee/dataset?q=loomemajandus -> HTTP 200
  (~76 KB, 12 visible characters, title "Teabevärav") — JS app
  shell, zero keyword hits: no trivially pollable national-portal
  loome dataset (same shell as the #264/#277/#284/#290/#299
  national-portal checks).
* https://www.tallinn.ee/et/avaandmed -> HTTP 200 (1 420 B, title
  "Avaandmed API") — "Universal API for Tallinn city open data"
  pointer page: datasets are documented at avaandmed.eesti.ee (the
  JS shell above), table names guessed against ../data/ would be
  enumeration, so the check stops here.
* https://www.tallinn.ee/et/ettevotjale/loomemajandus-tuleviku-ettevotlus
  -> HTTP 200 (~79 KB, ~5.4k visible chars, title "Loomemajandus —
  tuleviku ettevõtlus | Tallinn"). Ettevõtlusamet policy/prose
  (8x loomemajandus, 2x loomeettevõt...); 0 for linnaosa / csv /
  xlsx / pdf / geojson / wfs / andmestik / masinloetav / avaandmed /
  api, and 0 file links of any kind.
* https://www.tallinn.ee/et/ettevotjale/uuringud-statistika-turundusmaterjalid
  -> HTTP 200 (~71 KB, ~3.9k visible chars). Human study/statistics
  directory (12x statistika, 8x uuring); 0 for loomemajandus /
  linnaosa / any machine-readable keyword, 0 file links.
* https://www.tallinn.ee/et/ettevotlus/tallinna-ettevotlusstatistika
  -> HTTP 200 (~84 KB, ~5.6k visible chars, title "Tallinna
  ettevõtlusstatistika | Tallinn"). City-level business-stats prose
  (25x statistika); 0 for loomemajandus / loome / linnaosa / csv /
  xlsx / pdf / andmestik / masinloetav / avaandmed / api, 0 file
  links.
So the dim returns None for EVERY input including missing origin:
a taste gradient painted from one-off hand-reads of human policy
pages would be fake precision (OTA PR #131 precedent). Reasons say
"hinnang" (estimate) and "EI OLE" and point at the concrete
buyer-side check (ostjaprofiili loomekvartali-eelistus +
Telliskivi/Paavli/Noblessneri jalutuskäik) — never a faked area
score, never a worth judgement ("maitsesobivus" always).

SIBLING OVERLAP (read first, not edited): the other P4-044 legs
stay where they live and are named here, never re-scored. SCORED
legs — REL2021 occupation-mix taste-match (dims_p4_rel2021
dim_herd_occupation_rel, the primary grid leg), OSM gallery/museum
taste-match (dims_p4_osm dim_herd), EHIS art/music-school density
(dims_p4_ehis dim_artschool_density, #347 coverage), tehingud
gentrification front (dims_p4_maa_tehingud
dim_herd_gentrification_front). NULL agreer — the arireg
creative-employer address-cluster leg (dims_p4_arireg
dim_herd_arireg: no address-cluster join either). This module owns
ONLY the loome-stats-table leg below: the city's per-linnaosa
creative-economy statistics publication (a different artifact from
every sibling join). Distinct dim key, no double-scoring (same
split-slice precedent as P4-024 across pria/kaur/eelis/tervise/
komun, and P4-048 across ehr/peatus/tlt/osm/green/recre).

Style mirrors services/scoring/dims_p4_recre.py (#312, the
dated-negative single-param precedent): every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for a
city-published loome table, so there is nothing for the live path
to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #322 states the remaining
  0 params using this source need only a follow-up created after
  this demo — with a dated-negative demo there is no ingestion to
  extend, so one dim in one module is the whole honest scope.
  (Recre #312 carried two dims because its source family holds two
  distinct artifacts — facility timetables vs association queue
  publications — with different buyer checks; the loome source is
  one table, so splitting it would fake scope.)
* No fetch_* helper: with a dated-negative verdict there is no
  pollable feed to wrap, and a fetcher around human policy pages
  would be brittle scraping dressed as ingestion (komun #290
  precedent — verdict modules carry no network code, pinned by
  test_module_adds_no_network_calls).
* The check stopped at search/shell/pointer/policy level on
  purpose — no uuringud-register driving, no Teabevärav JS-app
  driving, no open-data-API table-name enumeration, no
  Ettevõtlusamet subsite scraping.
* Honest shape when a table lands (documented, not implemented):
  per-linnaosa join -> grid taste-match under the same contract as
  the ehis P4-044 slice (capped, neutral floor, "maitsesobivus",
  never worth judgement); exact bands calibrate against the first
  real pull, never against this prose.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-044 (demo): per-linnaosa loomemajandusstatistika needs the city
# table join (loomeettevõtete / loomehõivatute arv per linnaosa).
# Human policy pages only, no pollable table — the scorer reports the
# gap with the concrete buyer-side check.
# ---------------------------------------------------------------------------

def dim_loome_linnaosa_stats(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-044: NULL — linnaosa loomemajandusstatistika tabel puudub."""
    return None, ("Loomemajanduse maitsesobivus linnaosas on ostja maitse-hinnang "
                  "(EI OLE masinloetavat linnaosa-tabelit): Tallinna loomelehed on "
                  "inimloetavad kataloogilehed (poliitika + uuringute kataloog, 0 "
                  "faililinki, 0 linnaosa-jaotust) ja Teabevärav on JS-kest ilma "
                  "loome-andmestikuta — linnaosa loomeprofiili tabelit pole viisakalt "
                  "kusagilt küsida, hinnangut ei anta: kaalu loomekvartali-eelistust "
                  "ostjaprofiilis, tee jalutuskäik Telliskivi / Paavli / Noblessneri "
                  "kandis ning vaata liidetud maitse-slice'e dims_p4_rel2021-st "
                  "(dim_herd_occupation_rel), dims_p4_osm-ist (dim_herd), "
                  "dims_p4_ehis-ist (dim_artschool_density), dims_p4_arireg-ist "
                  "(dim_herd_arireg) ja dims_p4_maa_tehingud-ist "
                  "(dim_herd_gentrification_front), ära feigi")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_LOOME_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_LOOME_DIMS = (
    ("loome_linnaosa_stats", "P4-044", dim_loome_linnaosa_stats),
)


def score_p4_loome(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 loome dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_LOOME_DIMS). The value
    is None by design — unpublished per-linnaosa loome table, never
    a faked taste gradient."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_LOOME_DIMS}
