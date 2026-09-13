"""P4 StaMT service-map dim (issue #273 demo only): Tallinna Sotsiaal- ja
Tervishoiuamet teenuste kaardid verdict.

Demo (#273): the Sotsiaal- ja Tervishoiuamet source via P4-011
Lasteaia queue length + perearst nimistu open/closed - the StaMT
teenuste-kaardid leg (social/health service locations per linnaosa
as the family-services map leg) end-to-end in Tallinn. Single-param
demo: P4-011 is the only param using this source (parameters4.md
source (4) "Tallinna Sotsiaal- ja Tervishoiuamet teenuste
kaardid"), so there is no coverage follow-up issue.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #273: StaMT publishes no pollable bulk service-map feed, so the
dim stays NULL). Polite evidence, 7 single GETs total (labelled
one-off user-agent, >= 6 s pacing, `--max-time 25`, headers +
visible-text/link scope read only, no scraping, no auth attempts),
raw bodies cached at /tmp/hf-stamt-probe/ (one-off PR record, never
committed):
* https://www.tallinn.ee/et/sotsiaal -> HTTP 404 "Lehekülge ei
  leitud" (123 245 B CMS 404 template) - the guessed short agency
  slug is dead.
* https://www.tallinn.ee/et/sotsiaal-ja-tervishoiuamet -> 301
  (410 B) to /group/77/toc/14705, which itself answers 404 - a
  stale CMS redirect to a dead group URL, not a reachable agency
  page. https://www.tallinn.ee/et/tervishoid answers 301 the same
  way (474 B). Probing stops here rather than enumerating URL
  guesses.
* https://kaart.tallinn.ee/ -> HTTP 200
  https://gis.tallinn.ee/veebikaart/ (5 023 B, "Tallinna
  veebikaart", 21 visible chars, 4 script tags): an Esri Experience
  Builder app shell (ArcGIS JS API 4.34, jimu-core) with zero
  server-rendered data and no bulk/download/API href advertised at
  storefront level. The teenuste kaardid live here as interactive
  app layers, not as a feed.
* https://andmed.eesti.ee/dataset?q=sotsiaal -> HTTP 200
  "Teabevärav" (75 497 B, 12 visible chars): a JS shell with no
  server-rendered results - no trivially pollable national-portal
  StaMT dataset (same finding as Haridusamet #270).
* https://www.tallinn.ee/sitemap.xml -> HTTP 404 (same CMS 404
  template) - no machine page index to poll.
TTL: one-off dated check only - with no pollable feed there is no
ingestion to cache and no recurring TTL to state.

So the dim returns None for EVERY input including missing origin:
painting a per-linnaosa band from a map screenshot, or chasing the
veebikaart app's ArcGIS item/service calls to extract StaMT
layers, would be scraping (AGENTS.md section 5 refuses it) and fake
precision (OTA PR #131 precedent). The reason says "hinnang"
(estimate) and "EI OLE" and points at the concrete buyer-side
checks (Haridusameti lasteaiakoha taotlemise e-teenus, Tervisekassa
nimistuotsing, Tallinna veebikaart, kohapealne küsimine) - never a
faked area score.

Style mirrors services/scoring/dims_p4_opmaps.py (#267): the scorer
is pure and offline-tested - (origin, pois) -> (Optional[int
0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for StaMT service coverage, so there is nothing for
the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing StaMT leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-011 is the only param
  naming this source (parameters4.md P4-011 source (4)), so one
  module, one test file, one verdict note - no second file
  importing a pipeline that does not exist.
* Per-source slice, not the full param: the dim owns ONLY the
  StaMT teenuste-kaardid leg. Sibling P4-011 slices keep their
  owners, untouched: Haridusamet queue stats (dims_p4_haridus -
  documented NULL), EHIS capacity (dims_p4_ehis - joined rows
  only), Tervisekassa GP lists, REL2021 age grid, koolivõrgu
  arengukava (their own demos). The reason names each cousin so
  the NULL stays actionable.
* The check stopped at storefront/shell level on purpose: no
  ArcGIS service chasing, no layer harvesting, no session flows.
  Driving the veebikaart app to extract StaMT points would be
  exactly the scraping this repo refuses (AGENTS.md section 5).
* Honest shape stays a per-linnaosa table (per #273 acceptance):
  IF StaMT ever opens a bulk service-location feed, the graduate
  dim joins rows per linnaosa - until then NULL with the
  Estonian reason below, never a screenshot grade.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-011: documented no-map StaMT-leg NULL (OTA PR #131 precedent).
# StaMT teenuste kaardid live as interactive veebikaart app layers
# with no public bulk feed (2026-09-13 dated-negative verdict
# above); the scorer reports the gap with concrete buyer-side
# checks instead of a faked number.
# ---------------------------------------------------------------------------

def dim_stamt_services(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-011: NULL - StaMT service-map leg needs a bulk feed (no map)."""
    return None, ("Sotsiaal- ja tervishoiuteenuste kaardi hinnang on "
                  "linnaosa tabeli hinnang (EI OLE masinloetavat "
                  "teenusevoogu): Sotsiaal- ja Tervishoiuameti teenuste "
                  "kaardid elavad interaktiivses veebikaardis, millel "
                  "hulgi-allalaadimist ega API-d pole (kontrollitud "
                  "2026-09-13, veebikaart on andmevoota JS-rakendus) - "
                  "lasteaia järjekorda kontrolli Haridusameti "
                  "lasteaiakoha taotlemise e-teenusest, perearsti "
                  "nimistu avatust Tervisekassa nimistuotsingust ja "
                  "lähimaid teenuseid Tallinna veebikaardilt või "
                  "kohapeal, ära feigi kaardipildist skoori")


P4_STAMT_DIMS = (
    ("stamt_services", "P4-011", dim_stamt_services),
)


def score_p4_stamt(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 StaMT dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_STAMT_DIMS). The value
    is None by design - service maps with no pollable feed, never a
    faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_STAMT_DIMS}
