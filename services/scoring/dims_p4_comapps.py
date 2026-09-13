"""P4 comapps per-listing dimensions (issues #302 demo + #371 coverage).

Params (this agent only — demo + its coverage follow-up share one source):
* P4-027 Grocery slots + ride-price probes (batch 3, demo in #302)
* P4-049 Taxi/guest test (batch 4, coverage in #371)

HONESTY (AGENTS.md section 7.2): the Commercial delivery/ride APIs
source is closed commercial feeds — Wolt/Bolt Food coverage polygons,
Barbora/Selver delivery windows, and Bolt ride-price probes all live
behind partner-gated portals, session-gated storefronts, or
consumer-app ToS that forbids automated probing. The openness check
of 2026-09-13 (see docs/p4_comapps.md) found no public feed for ANY
of the three: Wolt's developer portal is merchant-order integration
only (no coverage/price feed), Bolt publishes no public developer
portal at all, Foodora's developer page is access-gated, and
Barbora is a JS storefront with no documented open API. Scraping the
consumer apps instead would violate ToS and AGENTS.md section 7.4
(polite automation), so both dims return None for EVERY input
including missing origin: a district band painted from a one-off
hand-check would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (evening coverage probe at your own
address, guest taxi/parking test, KÜ enquiry) — never a faked area
score.

Style mirrors services/scoring/livability.py and sibling batch
dims_group20a.py (#212): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a closed commercial feed's coverage, so
there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#371) states it extends the demo ingestion (#302): with the
  demo verdict dated-negative, there is no ingestion to extend, so
  the coverage param lands in the same verdict module rather than a
  second file importing a pipeline that does not exist.
* Both params stay NULL even though open cousins exist for SLIVERS
  of P4-027 (Tallinna ööbussid GTFS, OSM shop opening_hours,
  Omniva/SmartPOST parcel-point lists): the cousins cover night-bus
  lines / shop hours / parcel lockers, not Wolt/Bolt Food evening
  coverage or ride prices — the params' actual questions. Scoring a
  cousin as the commercial feed would mislead by construction.
  The cousins are recorded in docs/p4_comapps.md as overturn paths.
* P4-049 stays NULL rather than scoring OSM entrance/wheelchair
  tags: tag presence marks a mapped doorway, not taxi findability,
  guest parking at Sat 19:00, or entrance tidiness — the param's
  pride+resale question needs an on-site guest test.
* The reasons name the concrete buyer-side check (oma aadressi
  õhtune katvusproov, külalise takso-/parkimistest, KÜ päring) so
  the NULL is actionable, not a dead end.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-027/P4-049: documented no-map commercial-feed NULLs (OTA PR #131
# precedent). The feeds are partner/session-gated with no public API;
# the scorer reports the gap with a concrete buyer-side check instead
# of a faked number.
# ---------------------------------------------------------------------------

def dim_grocery_ride(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-027: NULL — grocery slots + ride prices are closed feeds (no map)."""
    return None, ("Toidu- ja sõiduteenuse katvus on suletud kommertstee- "
                  "nuste hinnang (EI OLE avaandmeid): Wolt/Bolt Foodi "
                  "katvuskaardid, Barbora/Selveri tarneajad ja Bolti "
                  "sõiduhinnad on partner- või sessiooniväravaga, avalikku "
                  "voogu pole — proovi oma aadressil õhtul kell 22 "
                  "tellimusäppides katvust ise, ära feigi ala skoori")


def dim_taxi_guest(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-049: NULL — taxi findability + guest test needs an on-site test."""
    return None, ("Takso-leitavus ja külalise-test on kohapealse katse "
                  "hinnang (EI OLE kaardikiht): aadressi leitavus, "
                  "laupäevaõhtune külalisparkimine ja sissepääsu korrasolek "
                  "selguvad taksotellimuse proovist ja KÜ päringust — "
                  "kaardikiht puudub, külaline testib kohapeal")


P4_COMAPPS_DIMS = (
    ("grocery_ride", "P4-027", dim_grocery_ride),
    ("taxi_guest", "P4-049", dim_taxi_guest),
)


def score_p4_comapps(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 comapps dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_COMAPPS_DIMS). Every value
    is None by design — closed commercial feeds, never a faked score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_COMAPPS_DIMS}
