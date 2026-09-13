"""P4 Tallinna välireklaam / reklaamimaks per-building dim (issue #318 demo).

Params (this module only — the REKLAAM SLICE of the param; sibling
slices are owned elsewhere and untouched):
* P4-036 Roof income: the Tallinna reklaamimaks +
  välireklaami load (gable ad-wall yield) slice
  (source (4), batch 3, demo in #318). Disjoint from the Elering
  feed-in rules + mikrotootja slice
  (dims_p4_elering.dim_feed_in_rules), the Elektrilevi
  liitumiskaart export-feasibility slice
  (dims_p4_elektrilevi.dim_roof_export), the Maa-amet LiDAR/LoD2
  roof-facet slice (dims_p4_maa_lidar.dim_roof_income), the EHR
  katuse slice (dims_p4_ehr.dim_roof_income), and the Utilitas
  return-temp bonus slice (dims_p4_heat.dim_roof_bonus) — their
  own demos, not this source. This source feeds only P4-036, so
  there is no follow-up coverage issue.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #318): Tallinn publishes no pollable per-building ad-load or
ad-yield feed. Polite evidence, 7 tiny requests total (single GETs
with a labelled one-off user-agent, headers + visible-text keyword
scope read only, no scraping, no auth, no form submissions, no XHR
probing, paced >= 4 s), raw bodies cached at /tmp/hf-reklaam/
(TTL: one-off check, kept for the PR record, never committed):
* https://www.riigiteataja.ee/akt/427042018036 ("Reklaamimaks
  Tallinnas") -> HTTP 200, 51763 bytes — a JS-only viewer shell
  ("Laeb... Ilma Javascript toeta lehitsejad ei ole toetatud"):
  zero server-rendered text for a polite client. The regulation
  itself is human law (per-m² tax rules), not a per-building
  dataset by construction.
* https://www.tallinn.ee/et/search?search_api_fulltext=reklaam
  (301 to /et/otsing) -> HTTP 200, 146341 bytes, "Otsi |
  Tallinn" — visible-text sweep: reklaam 38x, välireklaam 11x,
  reklaamimaks 3x, while masinloetav / csv / xlsx / json / api /
  X-tee / andmestik all score 0 (avaandmed 2x is footer nav,
  not a data link). Result links are human service pages, not
  feeds.
* https://www.tallinn.ee/et/teenused/valireklaami-ja-teabe-paigaldamine
  ("Välireklaami ja teabe paigaldamine") -> HTTP 200, 162842
  bytes — visible text: välireklaam 11x, reklaamimaks 5x,
  taotlus 20x, menetlus 7x, luba 3x; masinloetav / csv / xlsx /
  json / api / X-tee / andmestik all 0. A per-permit admin
  procedure (taotlus/menetlus/luba): no per-building load feed,
  no rate table.
* https://andmed.eesti.ee/dataset?q=reklaam and ?q=välireklaam ->
  HTTP 200 each, identical 75497-byte JS "Teabevärav" shells
  with zero server-rendered topical hits — no trivially
  pollable national-portal dataset.
So the dim returns None for EVERY input including missing
origin: a yield band painted from a one-off hand-check, from the
per-m² tax rate, or from negotiated vendor rate cards would be
fake precision (OTA PR #131 precedent). Reklaamimaks is a COST
(tax per m²), not yield, and yield itself is negotiated per
site — with no open per-building exposure/load/permit table
there is no honest join. The reason says "hinnang" (estimate)
and "EI OLE" and points at the concrete buyer-side check
(haldur + KÜ viiluseina sobivus ja loavõimalus, Tallinna
paigaldusloa procedure) — never a faked per-building number.

Style mirrors services/scoring/dims_p4_ttjacons.py (#295, the
closest sibling: same single-param dated-negative NULL shape)
and dims_group20a.py (#212): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for a
building's ad-wall yield, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param module with no ingestion function: unlike the
  Maa-amet sibling legs (downloadable LiDAR/tehingud files to
  parse), there is no open reklaam file or feed to fetch,
  parse, or cache — the only artefact of the demo is this
  dated-negative verdict plus its doc note. Fetching nothing
  is the polite choice, stated not hidden.
* P4-036 (reklaam slice) stays NULL even though the buyer CAN
  ask the haldur/KÜ about the gable wall and read the permit
  procedure by hand: a manual suitability question is not a
  pollable join, and a city-wide tax rate times wall area
  without exposure, load, and permit data is arithmetic on
  missing inputs — fake precision, not a yield hinnang.
* No scored "tax-rate hinnang" off the määrus: the tax is a per-m²
  cost schedule, and scoring cost as yield would invert the
  param's question (yield kicker). Until a per-building
  exposure/load feed exists, the upside leg is unjoined and
  the NULL names exactly that.
* No vendor rate-card scraping: per-site yields are negotiated
  commercial offers (human sales material, no open
  per-building table). Relabelling them as data would be
  scraping, not ingestion (same refused-steelman precedent
  as #266).

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-036 (reklaam slice): documented no-feed gable ad-wall yield NULL
# (OTA PR #131 precedent). Tax rules live in a human-readable määrus
# and ad load moves through a per-permit taotlus/menetlus with no
# public per-building feed; the scorer reports the gap with the
# concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_ad_wall_yield(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-036: NULL — gable ad-wall yield is procedure-only (no feed)."""
    return None, ("Seinareklaami (viilu) tootlus on hoonepõhine tulu-hinnang "
                  "(EI OLE masinloetavat reklaamikoormuse voogu): "
                  "reklaamimaksu määrad elavad Riigi Teataja inimloetavas "
                  "määruses ja välireklaami load käivad Tallinna paigaldusloa "
                  "taotluse ning menetluse kaudu, avalik hoonepõhine "
                  "tootlustabel puudub — küsi haldurilt ja KÜ-lt viiluseina "
                  "sobivust ning loavõimalust ja ära feigi olematut "
                  "tootlusnumbrit")


P4_REKLAAM_DIMS = (
    ("ad_wall_yield", "P4-036", dim_ad_wall_yield),
)


def score_p4_reklaam(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 reklaam dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_REKLAAM_DIMS). The
    value is None by design — procedure-only source, never a
    faked per-building yield."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_REKLAAM_DIMS}
