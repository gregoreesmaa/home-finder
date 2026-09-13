"""P4 recreation dims (issue #312, single-param demo, no coverage issue).

Demo (#312): Tallinna recreation & allotments source family for P4-048
end-to-end in Tallinn — openness verification plus the honest-shape
recreation-facility leg and the allotment-queue-publication leg.
Single param: P4-048 Small delights + allotment queues, recreation
slice (batch 4 sources (3)+(4): RMK seenemetsad + Pirita/Stroomi
ujulad + gym/ice venues <15 min; Tallinna linnaaiad/aiandusühistute
järjekorrad — Lillepi, Pelgu — queues = true demand). Honest shape
when feeds land: per-listing dims + annual queue tables.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #312): Tallinn and RMK publish no pollable machine-readable feed
for either slice below. Polite evidence, 10 served requests total
(eight single GETs with a labelled one-off user-agent, 25 s timeout,
no retries, 2 s pacing, plus two single canonical-redirect follows;
headers + visible-text keyword scope read only, no scraping, no auth,
no form driving, no service enumeration), raw bodies cached at
/tmp/hf-recre-probe/ (one-off PR record, never committed):
* https://www.rmk.ee/ -> HTTP 301 to canonical https://rmk.ee/
  (empty 301 body, documented once, not spidered). Canonical front
  -> HTTP 200 (~118 KB, ~6.4k visible chars, title "Riigimetsa
  Majandamise Keskus (RMK)"). Visible-text sweep: "rmk" 20x only;
  0 for csv / geojson / wfs / wms / masinloetav / andmestik /
  avaandmed / api — no bulk/visitor-feed pointer at landing level.
* https://www.rmk.ee/kulastajale -> HTTP 301 to canonical
  https://rmk.ee/kulastajale -> HTTP 404 (~86 KB). Stale guess,
  documented as tried — no visitor-info bulk URL there.
* https://www.tallinn.ee/et/sport -> HTTP 200 (~61 KB, ~2.8k
  visible chars, title "Sport | Tallinn"). Human directory only
  ("Spordisaalid ja -hallid", "Ujulad ja veespordikeskused",
  "Linna spordibaasid", Kultuuri- ja Spordiamet contacts);
  "ujula" 2x + "spordikeskus" 2x are directory prose, not a feed.
  (Full link-text inventory: "Spordisaalid ja -hallid", "Ujulad ja
  veespordikeskused", "Linna spordibaasid", Kultuuri- ja Spordiamet.)
* https://www.tallinn.ee/et/otsing?search_api_fulltext=ujula ->
  HTTP 200 (~146 KB, server-rendered). 25x "ujula" + 2x
  "tunniplaan" + 7x "pilet" are human pool/timetable/ticket pages
  (Spordivoimalused, Kultuuri- ja spordiamet); 0 for csv /
  geojson / wfs / masinloetav / andmestik / jarjekord.
* https://www.tallinn.ee/et/otsing?search_api_fulltext=aiandus%C3%BChistu
  -> HTTP 200 (~144 KB, server-rendered). Only 1x "aiandusühistu";
  0 for järjekord / csv / geojson / wfs — no
  association queue table anywhere (only 1x "aiandusühistu" total).
* https://www.tallinn.ee/et/otsing?search_api_fulltext=Lillepi ->
  HTTP 200 (~146 KB, server-rendered). 6x "Lillepi" = Lillepi
  pargi hoolduskava (a park maintenance plan, not an allotment
  queue) + Pirita sport-site pages (19x "pirita"); 0 for
  järjekord / csv / geojson / wfs.
* https://andmed.eesti.ee/dataset?q=spordirajatis -> HTTP 200
  (~75 KB, 10 visible characters, title "Teabevärav" JS shell) —
  no trivially pollable national-portal recreation dataset (same
  shell as the #264/#277/#284/#290/#299 national-portal checks).
* https://www.tallinn.ee/et/otsing?search_api_fulltext=spordikeskus
  -> HTTP 200 (~145 KB, server-rendered). 25x "spordikeskus" are
  human venue pages (Pirita / Pae / Härma / Nõmme / Sõle / Tallinna
  Spordikeskus); 0 for csv / geojson / wfs / masinloetav.
So both dims return None for EVERY input including missing origin:
a delight gradient painted from one-off hand-reads of human
directory pages would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (15-minuti prooviring RMK-suunal /
ujula-tunniplaan + piletiinfo kontroll, aiandusühistu
järjekorrapäring) — never a faked area score.

SIBLING OVERLAP (read first, not edited): the other P4-048 legs
stay where they live and are named here, never re-scored. SCORED
legs — p101 specialised-recreation snapshot proximity
(dims_group11 dim_rec_special: stadium/pool/sports-centre distance
bands off the OSM snapshot), EHR orientation breakfast-sun
(dims_p4_ehr dim_small_delights), <15 min access halves
(dims_p4_peatus dim_delights_access, dims_p4_tlt
dim_tlt_delight_access). NULL agreers — the green-inventory source
family (dims_p4_green dim_bench_view_3min, dim_delight_green_15min,
dim_allotment_queue: pinkide register / rohealade-kava isochrone /
city-register queue leg, dated negative #300) and the OSM snapshot
leg (dims_p4_osm dim_delights: queues/registers not in snapshot).
This module owns ONLY the two recreation-source-family legs below:
operator timetables/tables (pool tunniplaan, venue lahtiolekuajad,
RMK visitor info — a different artifact from green's
planning-document kava join) and association-published queue tables
(aiandusühistute publications — a different artifact from green's
city-register leg). Distinct dim keys, no double-scoring (same
split-slice precedent as P4-024 across pria/kaur/eelis/tervise/
komun, and P4-048 across ehr/peatus/tlt/osm/green).

Style mirrors services/scoring/dims_p4_pria.py (#299, the
dated-negative single-param precedent): every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for venue
timetables or association queue tables, so there is nothing for
the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #312 states the remaining
  0 params using this source need only a follow-up created after
  this demo — with a dated-negative demo there is no ingestion to
  extend, so there is nothing to split out. Two dims (facility
  table/timetable leg vs annual queue-publication leg — different
  honest shapes with different buyer checks), one module, three
  new files, no shared-file edits.
* P4-048 is shared with dims_p4_green by design (same-param
  distinct-source slices, P4-024 precedent): green owns the
  kava/register legs, recre owns the timetable/publication legs.
  The two queue dims agree (both NULL) but probe different
  artifacts — city-register search (#300) vs association-level
  publication search (this issue) — and each names the other.
* No fetch_* helper: with a dated-negative verdict there is no
  pollable feed to wrap, and a fetcher around human directory
  pages would be brittle scraping dressed as ingestion (komun
  #290 precedent — verdict modules carry no network code, pinned
  by test_module_adds_no_network_calls).
* The check stopped at landing/search/shell level on purpose — no
  RMK subsite enumeration, no tallinn.ee venue-page scraping, no
  Teabevarav JS-app driving, no allotment-association queue
  scraping.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-048 (demo): recreation-facility <15 min needs the operator
# timetable/table join (RMK visitor info, Pirita/Stroomi pool
# tunniplaan, gym/ice venue lahtiolekuajad). Human directories only,
# no pollable facility table — the scorer reports the gap with the
# concrete buyer-side check.
# ---------------------------------------------------------------------------

def dim_recre_facility_15min(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-048: NULL — puhkeasutuste tunniplaan/tabel (<15 min) puudub."""
    return None, ("Puhkeasutuste <15 min ligipääs (RMK seenemets, Pirita / "
                  "Stroomi ujula, jõusaal / jää) on päevarõõmu-hinnang (EI OLE "
                  "masinloetavat tunniplaani- või rajatiste tabelit): ujulad ja "
                  "spordikeskused elavad inimloetavates kataloogilehtedel "
                  "(tunniplaan + pilet) — tee 15-minuti prooviring kaardilt, "
                  "kontrolli tunniplaani ja ligipääsu-slice'e dims_p4_peatus-ist "
                  "ja dims_p4_tlt-st ning kauguse-slice'i dims_group11-st "
                  "(dim_rec_special), ära feigi")


# ---------------------------------------------------------------------------
# P4-048 (demo): allotment queues (Lillepi, Pelgu — queues = true
# demand, annual tables) are unpublished at association level too:
# the city search yields a park maintenance plan, not a queue, and
# the aiandusuhistu search yields no queue table. The green
# city-register NULL agrees.
# ---------------------------------------------------------------------------

def dim_recre_allotment_queue(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-048: NULL — aiandusuhistute jarjekorratabelid (Lillepi / Pelgu)
    puuduvad."""
    return None, ("Linnaaia-järjekord (Lillepi, Pelgu — järjekord on "
                  "tegelik nõudlus) on aiamaa-hinnang (EI OLE ühistute "
                  "avaldatud aastast järjekorratabelit): Lillepi-otsing andis "
                  "pargi hoolduskava, mitte järjekorra, ja aiandusühistu-otsing "
                  "ei andnud ühtegi tabelit — küsi aiandusühistult järjekorra "
                  "pikkust ja vaata linna-registri NULL-i dims_p4_green-ist "
                  "(dim_allotment_queue) ning OSM NULL-i dims_p4_osm-ist, "
                  "ära feigi")


# ---------------------------------------------------------------------------
# Registry + aggregator (keys match P4_RECRE_DIMS; pnums per parameters4.md).
# ---------------------------------------------------------------------------

P4_RECRE_DIMS = (
    ("recre_facility_15min", "P4-048", dim_recre_facility_15min),
    ("recre_allotment_queue", "P4-048", dim_recre_allotment_queue),
)


def score_p4_recre(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 recreation dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_RECRE_DIMS). Every value
    is None by design — unpublished facility timetables and queue
    publications, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_RECRE_DIMS}
