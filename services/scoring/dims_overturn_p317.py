"""Overturn re-check for p317 park upkeep quality (issue #240).

Param: p317 local park maintenance & enforcement (parameters3.md
section 5.11, Group 11). Canonical scorer stays
dims_group11.dim_park_upkeep (batch B2, issue #97) and its batch-D
re-export dims_group11d.dim_park_upkeep_listing (issue #135) --
this module adds NO new scoring semantics and does NOT replace
either. It exists to make the #240 time-boxed source hunt dated
and reviewable: the KEEP verdict below is pinned by tests, with a
re-check date, per the overturn protocol (docs/nomap.md section 2)
and the OTA PR #131 precedent (no gradient where honest
calibration cannot discriminate).

HUNT (2026-09-13, ~25 min, polite: 6 tiny GETs with a labelled
one-off user-agent, paced >= 4 s, headers + visible-text scope
read only, no scraping, no auth, no form submissions, no XHR
probing; raw bodies at /tmp/hf-p317/, never committed). Full log:
docs/overturn_p317.md.
* OSM (local snapshot ~/hf-data/2026-09-12, PBF
  harjumaa-260911.osm.pbf, zero network): `osmium tags-count`
  finds key `maintenance` on exactly 1 object county-wide --
  relation 1175710, maintenance=good on the E11 European long
  distance path (a trail-condition tag on a trans-European hiking
  route, verified via osmium cat XML), NOT park upkeep. Key
  `cutting` on 13 objects -- all road/railway terrain cuttings
  (highway=residential / railway=abandoned / footway), not
  mowing. 294 leisure=park + 2155 leisure=garden objects carry
  no upkeep-quality key family at all.
* Tallinn open-data front (https://avaandmed.tallinn.ee/ -> 200,
  1420 B): a real "Universal API for Tallinn city open data"
  (/data/?table=... endpoint, FastAPI 0.1.0 per openapi.json) --
  but the table catalog lives in the JS portal and the schema
  exposes only the generic endpoint (free-form table param, no
  table enumeration), so no haljastus/hooldus table is
  discoverable politely.
* National portal (andmed.eesti.ee/dataset?q=haljastus -> 200,
  75497 B): JS-only "Teabevärav" shell, 12 visible chars, zero
  server-rendered hits. No CKAN API either
  (/api/3/action/package_search -> 404 "Cannot GET" for both
  q=haljastus and q=pargi hooldus).
* Procurement register (https://riigihanked.riik.ee/ -> 200,
  AngularJS rhrApp shell): tender/award notices live behind the
  JS app as per-procurement human documents -- no per-park
  polygon feed to join.
So the dim returns None for EVERY input including missing
origin: painting a mowing-frequency fantasy from leisure=park
density, from a contractor's name on an award notice, or from an
operator= manager tag would score the map for what only a KOV
contract holds (nomap.md section 3 G11). The reason says
"hinnang" (estimate) and "EI OLE" and points at the concrete
buyer-side check (KOV / Kommunaalamet / linnaosa valitsus:
hooldusleping + niidukordade graafik, plus a walk-through of the
park itself) -- never a faked per-park number.

Style mirrors services/scoring/dims_p4_reklaam.py (#318, the
closest sibling: same single-param dated-negative NULL shape):
the scorer is pure and offline-tested -- (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a park's upkeep quality, so there is
nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* The check stopped at storefront level on purpose -- no RHR XHR
  probing, no tender-PDF enumeration, no blind guessing of
  Tallinn `table=` names one by one (each miss is load on a city
  API). Deeper probing is exactly the scraping this repo refuses
  (AGENTS.md section 5).
* Even a readable award notice would NOT overturn: notices name
  a contractor and a lump area, never per-park upkeep quality
  polygons. Scoring p317 off "a contractor exists" inverts the
  param's question (presence of a contract is not quality of
  upkeep) -- fake precision, not a quality hinnang.
* operator= on a park names the manager (e.g. Kommunaalamet),
  never mowing frequency or quality -- relabelling management
  proximity as upkeep quality is the refused near-miss proxy.
* Re-check hook (the honest way this verdict dies): a haljastus
  / hooldus table name surfaces in the Tallinn catalog (then one
  /data/ query tests the join), or a per-park upkeep polygon
  feed appears in-snapshot -- re-open #240 and propose the
  per-park-polygon contract join. Re-check by RECHECK_AFTER.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed), no WEIGHTS change, and no edits to
shared/group files (dims_group11*.py, livability.py,
docs/nomap.md) -- existing tests pin set(WEIGHTS) exactly, so
per-issue WEIGHTS edits would break every sibling. Rebalancing
stays one joint change across all batches; the final docs-index
PR updates nomap.md.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Hunt date (2026-09-13) -- the day the six polite checks above ran.
VERDICT_DATE = "2026-09-13"

#: Re-check the three discovery surfaces (Tallinn table catalog,
#: national portal, per-park polygon feed) no later than this date.
RECHECK_AFTER = "2027-03-13"


# ---------------------------------------------------------------------------
# p317: documented no-feed park-upkeep NULL (OTA PR #131 precedent).
# Upkeep quality lives in KOV maintenance contracts per park polygon;
# no OSM tag family and no pollable KOV feed carries it, so the scorer
# reports the gap with the concrete buyer-side check instead of a
# faked per-park number.
# ---------------------------------------------------------------------------

def dim_park_upkeep_overturn(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """p317: NULL -- park upkeep quality is contract-only (no feed)."""
    _ = (origin, pois)
    return None, ("Pargihoolduse kvaliteet on KOV-lepingu hinnang "
                  "(EI OLE masinloetavat haljastuslepingute voogu): "
                  "OSM-is kannab hooldusmärget terves Harjumaal üks "
                  "matkarada (E11), riigiportaal pakub vaid JS-vaadet "
                  "ilma serveripoolsete vasteteta ja hanketeated on "
                  "inimloetavad üksikdokumendid ilma pargipõhise "
                  "liiteta -- küsi KOV-ist (Kommunaalamet / linnaosa "
                  "valitsus) pargi hoolduslepingut ja niidukordade "
                  "graafikut ning vaata park üle kohapeal, ära feigi "
                  "olematut hooldusnumbrit")


OVERTURN_P317_DIMS = (
    ("park_upkeep_overturn", "p317", dim_park_upkeep_overturn),
)


def score_overturn_p317(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The p317 overturn-check dim for one listing (entry point for the
    weight-rebalance follow-up; keys match OVERTURN_P317_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in OVERTURN_P317_DIMS}
