"""P4 short-rental density dim (issue #293 demo only): Inside-Airbnb-style
Tallinn verdict.

Demo (#293): the Inside-Airbnb-style short-rental density leg of P4-003
Rent reality + Airbnb density - the hex nuisance-hinnang leg (short-let
density around the listing as a neighbour-nuisance signal) end-to-end
in Tallinn. Single-param demo: P4-003 is the only param naming this
source, so there is no coverage follow-up issue.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #293: Inside Airbnb publishes open data but NO Tallinn dataset, so
the dim stays NULL). Polite evidence, 3 single GETs total (labelled
one-off user-agent, >= 6 s pacing, `--max-time 25`, headers +
visible-text/link scope read only, no scraping, no auth, no downloads),
raw bodies cached at /tmp/hf-airbnb-probe/ (one-off PR record, never
committed):
* https://insideairbnb.com/ -> HTTP 200 (318 618 bytes, 4 575 visible
  chars): project storefront. Visible text mentions tallinn / estonia /
  eesti 0x; no Tallinn surface anywhere on the front page.
* https://insideairbnb.com/get-the-data/ -> HTTP 200 (572 256 bytes,
  98 241 visible chars, 1 009 links): the full city index. tallinn 0x,
  estonia 0x - there is a /riga/ city page but NO /tallinn/ page and no
  Estonia dataset path under data.insideairbnb.com. The index links the
  CC licences (creativecommons.org/licenses/by/4.0/ + CC0 Zero), so the
  source family is OPEN-licensed - it is the Tallinn COVERAGE that is
  missing, not the licence.
* https://insideairbnb.com/data-policies/ -> HTTP 200 (308 651 bytes,
  3 949 visible chars): "Do not scrape data from the site" (bulk CSV
  downloads are the sanctioned path; archived data by request), and new
  cities are in most cases NOT added ("limited resources ... in most
  cases, it is not possible to respond to most requests to add data
  for new cities").

So the dim returns None for EVERY input including missing origin:
painting a Tallinn hex band from the Riga dump, or scraping Airbnb
listings to build a Tallinn density ourselves, would be fake precision
(OTA PR #131 precedent) and refused scraping (AGENTS.md section 5 +
the site's own "do not scrape" policy). The reason says "hinnang"
(estimate) and "EI OLE" and points at the concrete buyer-side checks
(KU enquiry for neighbour turnover, KV uri medians + REL2021 grid for
the rent-reality half) - never a faked area score.

Style mirrors services/scoring/dims_p4_opmaps.py (#267): the scorer is
pure and offline-tested - (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois; this
module adds no network calls, no Overpass fragment, and no tag mapping:
there is no honest snapshot tag to query for short-let density, so
there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing Tallinn leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-003 is the only param
  naming this source family (parameters4.md source (4)
  "Inside-Airbnb-style Tallinn density (verify openness/ToS first,
  else AirDNA-style, label hinnang)"), so one module, one test file,
  one verdict note - no second file importing a pipeline that does
  not exist.
* Per-source slice, not the full param: the dim owns ONLY the
  Inside-Airbnb-style density leg. The rent-reality half keeps its
  owners, untouched: KV uri medians / city24 uripakkumised (portal
  adapters), Statamet uri statistika (dims_p4_stat), REL2021 1 km
  grid (dims_p4_rel2021). The reason names each cousin so the NULL
  stays actionable.
* Riga proxy deliberately refused: Riga IS covered (10 mentions on
  the index) but carrying a foreign city's density onto a Tallinn
  hex would score the WRONG city - fake precision by construction,
  not a conservative estimate. No Riga dump was downloaded (the
  data-policies ask to take only the data you need).
* AirDNA-style fallback NOT pursued: it is a commercial feed with no
  verified anonymous bulk endpoint, so it would need its own
  openness/ToS probe - out of scope for this one-leg demo; the
  reopening checklist in docs/p4_airbnb.md covers it.
* The check stopped at index/policy level on purpose: no listing
  scraping, no Airbnb-site crawling, no session flows. Building a
  Tallinn density by scraping listings would be exactly the scraping
  this repo refuses (AGENTS.md section 5) and the site forbids.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-003: documented no-map short-rental-density NULL (OTA PR #131
# precedent). Inside Airbnb is open-licensed but publishes no Tallinn
# dataset (2026-09-13 dated-negative verdict above); the scorer reports
# the gap with concrete buyer-side checks instead of a faked number.
# ---------------------------------------------------------------------------

def dim_short_rental_density(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-003: NULL - short-let density needs a Tallinn dataset (no map)."""
    return None, ("Lühiajalise üüri tihedus on Inside-Airbnb-stiilis "
                  "hinnang (EI OLE Tallinna andmestikku): Inside Airbnb "
                  "avaldab avaandmeid (CC-litsents), aga Tallinna "
                  "hetktõmmist loendis pole (kontrollitud 2026-09-13, "
                  "lähim kaetud linn on Riia — võõra linna tihedust ei "
                  "tohi Tallinna heksile kanda) — naabrite läbikäivust "
                  "küsi KÜ-lt, üüri reaalsust vaata KV üürimedianidest "
                  "ja REL2021 ruudustikust, ära feigi kraapitud skoori")


P4_AIRBNB_DIMS = (
    ("short_rental_density", "P4-003", dim_short_rental_density),
)


def score_p4_airbnb(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]
                    ) -> Dict[str, Optional[int]]:
    """The P4 airbnb dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_AIRBNB_DIMS). The value
    is None by design - open licence but no Tallinn dataset, never a
    faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_AIRBNB_DIMS}
