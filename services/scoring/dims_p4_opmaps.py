"""P4 operator-coverage-map dim (issue #267 demo only): Telia/Elisa/Tele2
levikaardid verdict.

Demo (#267): the Operator coverage maps source via P4-009
Power/internet reliability at address - the operator-levikaart leg
(mobile coverage at the address from the operators' own maps)
end-to-end in Tallinn. Single-param demo: P4-009 is the only param
using this source, so there is no coverage follow-up issue.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #267: the operators publish no pollable bulk coverage feed, so
the dim stays NULL). Polite evidence, 6 single GETs total (labelled
one-off user-agent, >= 6 s pacing, `--max-time 25`, headers +
visible-text/link scope read only, no scraping, no auth), raw bodies
cached at /tmp/hf-opmaps-probe/ (one-off PR record, never committed):
* https://www.telia.ee/ -> 302 to /era (locale split); /era ->
  HTTP 200 (360921 bytes, 3829 visible chars, 10 script tags):
  marketing storefront. Visible text mentions leviala / levikaart /
  coverage 0x; avaandmed / open data / developer / download /
  andmestik / masinloetav all 0. The single "arendaja" hit is the
  "Ehitajale, arendajale" construction-developer footer, and
  "Sideettevõtjale" is the wholesale/carrier footer - neither is a
  developer portal.
* https://www.elisa.ee/ -> HTTP 200 (97646 bytes, 5793 visible
  chars, 11 script tags): marketing storefront. No leviala link or
  mention anywhere in the served HTML (JS nav only); no open-data
  terms. Footers mirror Telia ("Ehitajale, arendajale", "For
  carriers") - construction/wholesale, not a data portal.
* https://www.tele2.ee/ -> 301 to the apex https://tele2.ee/ ->
  HTTP 200 (408501 bytes, 3496 visible chars, 32 script tags):
  marketing storefront whose nav/footer links confirm the coverage
  page ("Tele2 leviala" -> /leviala, /internet/leviala, plus a
  device-support page). No open-data terms; the single visible-text
  "api" hit is a shop-menu substring (context-checked, not a
  developer surface).
* https://tele2.ee/leviala -> HTTP 200 (269826 bytes, 4522 visible
  chars, 31 script tags, no <title>): the confirmed "Tele2
  levikaart" page is a JS map-app shell (under 2% visible text).
  csv / geojson / wfs / download / andmestik / masinloetav all 0 -
  no bulk endpoint, no machine feed advertised. "Tingimused" is the
  generic service-terms footer link.

So the dim returns None for EVERY input including missing origin:
painting a per-address band from a marketing map screenshot, or
reverse-engineering the map app's tile/API calls, would be scraping
(AGENTS.md section 5 refuses it) and fake precision (OTA PR #131
precedent). The reason says "hinnang" (estimate) and "EI OLE" and
points at the concrete buyer-side checks (TTJA netikaart address
check, Ookla open tiles, OpenCellID mast density, rikkekaart for
the power half) - never a faked area score.

Style mirrors services/scoring/dims_p4_muinsus.py (#324/#380): the
scorer is pure and offline-tested - (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for operator coverage, so there is nothing for the
live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing operator leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-009 is the only param
  naming this source family (parameters4.md source (4)
  "Telia/Elisa/Tele2 levikaardid Tallinn (verify ToS, cache)"), so
  one module, one test file, one verdict note - no second file
  importing a pipeline that does not exist.
* Per-source slice, not the full param: the dim owns ONLY the
  operator-levikaart leg. Sibling P4-009 slices keep their owners,
  untouched: Elektrilevi feeder SAIDI (dims_p4_elektrilevi -
  documented NULL), Elering system series (dims_p4_elering - NULL
  per-address), TTJA netikaart / Ookla tiles / OpenCellID masts
  (their own demos). The reason names each cousin so the NULL
  stays actionable.
* ToS deep-read deliberately not done: all three storefronts show
  only generic "Tingimused" service-terms footers and no
  open-data/API licence anywhere. With no bulk feed to license,
  clause-level ToS reading answers nothing - and the moment a
  feed appears, the reopening checklist in docs/p4_opmaps.md
  applies before any pull.
* The check stopped at storefront/shell level on purpose: no tile
  harvesting, no app-API chasing, no session flows. Driving the
  marketing map to extract coverage would be exactly the scraping
  this repo refuses (AGENTS.md section 5).

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-009: documented no-map operator-leg NULL (OTA PR #131 precedent).
# The operators' levikaardid are interactive marketing map apps with no
# public bulk feed (2026-09-13 dated-negative verdict above); the scorer
# reports the gap with concrete buyer-side checks instead of a faked
# number.
# ---------------------------------------------------------------------------

def dim_operator_coverage(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """P4-009: NULL - operator levikaart leg needs a bulk feed (no map)."""
    return None, ("Operaatori levikaart on turundus-hinnang (EI OLE "
                  "masinloetavat levivoogu): Telia/Elisa/Tele2 "
                  "interaktiivsetel levikaartidel hulgi-allalaadimist "
                  "ega API-d pole (kontrollitud 2026-09-13, Tele2 "
                  "levikaart on andmevoota JS-rakendus) - aadressi "
                  "tegelikku mobiililevi kontrolli TTJA netikaardilt, "
                  "kiirust Ookla avaandmetest, mastitihedust "
                  "OpenCellID-st ja elektrikatkestusi rikkekaardilt, "
                  "ära feigi kaardipildist skoori")


P4_OPMAPS_DIMS = (
    ("operator_coverage", "P4-009", dim_operator_coverage),
)


def score_p4_opmaps(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 opmaps dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_OPMAPS_DIMS). The value
    is None by design - marketing map app with no pollable feed,
    never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_OPMAPS_DIMS}
