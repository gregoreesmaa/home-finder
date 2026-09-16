"""P4 harbour dims (issue #542): measured sadamaregister + AIS verdict.

Two legs, both documented no-map NULLs until their gates clear:

* ``harbour_function_zone`` -- measured port-function proximity/noise-calendar
  leg (the replacement for the P4-023 ``sadam`` fixture zone in
  ``dims_p4_trans``). GATE: sadamaregister licence unstated -- no ingestion
  of that leg until an open licence is confirmed (issue hard gate).
* ``ais_pleasure_density`` -- AIS pleasure-craft 500 m-grid overlay leg.
  GATE: no grid values pulled (catalogue entry not retrievable from the
  local mirror; grid CRS/values unprobed) -- the grid would be used as-is,
  never re-interpolated.

OPENNESS VERDICT (probed 2026-09-16, polite one-off round, custom UA
``home-finder openness-check (one-off, few pages max, no scrape)``,
single GETs with 2 s pacing, ``--max-time 30``; raw bodies kept at
/tmp/hf-probes/, never committed):

* https://www.sadamaregister.ee/avaandmed -> HTTP 200, 1632 B, a JS app
  shell (``<div id="app">`` + ``/js/app.2bb0d667.js``), zero server-rendered
  rows (AGENTS.md section 7.7: a shell is a lead, not a verdict).
* /avaandmed.xsd -> HTTP 404 (``Cannot GET /avaandmed.xsd``): the schema
  the issue hoped for is not served at the documented path.
* App bundle (HTTP 200, 47 KB, one GET): the register IS a data-backed app
  (``window.appSettings.ApiBaseUrl`` + ``/ports/public-active``,
  ``/ports/{id}/public-details``, ``GisBaseUrl``) -- but the settings
  endpoint (``/appsettings.json``, ``/js/settings.js``, ``/config.js``)
  404s on all three probed paths, so the API base URL stays undiscovered
  and no port row was pulled. No licence statement found anywhere in the
  shell or bundle. Per human-page restraint (AGENTS.md section 5) the
  check stops here: no login/session flow, no per-record scraping.
* INSPIRE WFS ``inspire.geoportaal.ee/geoserver/TN_sadam/wfs`` ->
  GetCapabilities HTTP 200 (108 KB): exactly two feature types,
  ``TN_sadam:TN.WaterTransportNetwork.PortArea`` (``Eesti sadamaregistri
  sadamaalad``) and ``...PortNode`` (``Eesti sadamaregistri sadamad``),
  Fees/AccessConstraints ``puudub`` (no charge -- NOT a licence grant).
  DescribeFeatureType HTTP 200 (4 KB) pins the schema: PortArea carries
  ONLY inspireId + ``geom``; PortNode adds the port NAME spelling +
  ``validfrom``. There is NO function taxonomy, NO season dates, NO max
  vessel size -- the function slices the issue wants (cruise/cargo/marina
  score differently) cannot be built off this WFS; they live only behind
  the unlicensed app API. Schema proof first -- done, and it closes the
  WFS as the function source.
* AIS leg: the ``laevaliikluse-tihedus`` catalogue entry is not present in
  the local checkout (no ``sources/`` dir), so file sizes, grid CRS and
  2024 pleasure-craft values off Pirita/Kakumäe are UNPROBED -- stated,
  not faked. Reopen checklist in docs/p4_harbour.md says exactly what to
  pull (one HEAD per S3 link + one 500 m cell value).

HONESTY (AGENTS.md section 7.2): both dims return None for EVERY input.
Outside port influence stays NULL (never "quiet/calm"). Every reason says
"hinnang" + "EI OLE" and points at the concrete buyer-side check
(sadamaregister.ee port pages, ts.ee timetables, on-site listening at the
Vanasadam/Pirita edge, sibling slices) -- never a faked area score.
Transport errors are never cached as data: this module makes NO network
calls at all (pinned by test via source inspection).

FIXTURE-REPLACEMENT AUDIT (P4-023 sadam leg, row-for-row): the live
``dims_p4_trans.dim_noise_zone_trans`` join reads fixture labels
``NOISE_ZONE_SCORES = {"lennumüra": 35, "õppus": 50, "sadam": 60}`` --
any ``noisezone_p4`` POI labelled ``sadam`` within 1 km scores a flat 60.
The measured replacement (BLOCKED on the licence gate) maps row-for-row:
fixture ``sadam``-within-1km -> PortArea containment by function
(cruise-terminal adjacency -> calendar leg, cargo-port adjacency -> low
noise band, marina adjacency -> recreation note, each scored from joined
port rows, never a distance gradient). Until the gate clears, the fixture
stays EXACTLY as-is -- this PR changes no shared file and no existing
score. Full table in docs/p4_harbour.md.

Style mirrors services/scoring/dims_p4_sadam.py (#298/#368): pure
offline scorers (origin, pois) -> (Optional[int 0..100], Estonian
reason); helpers are local (no livability import -- that would turn the
future central hook into a cycle, same precedent as PRs #100/#106/#115).
No shared-file edits: 3 new files only (this module + tests +
docs/p4_harbour.md).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Verdict instead of bands: the licence hard gate (issue Constraints)
  forbids ingesting the sadamaregister leg, and the AIS values were never
  pulled -- painting bands from either would be fake precision (OTA PR
  #131 precedent).
* P4-047 event-traffic + P4-055 icebreaking dims stay cousins (distinct
  keys); P4-023 keeps the trans fixture band plus the KAUR/EHR slices --
  each reason names its cousins.
* AIS gaps note: the publisher (per issue) ships annual 2018-2024 grids;
  brief AIS coverage gaps are a stated reopen-check, not a silent caveat.

Integration (deliberately NOT done here): WEIGHTS/livability/layers
rebalancing stays one joint change across all batches (existing tests pin
set(WEIGHTS) exactly).
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-023/P4-033-adjacent: measured harbour legs (licence-gated NULLs).
# sadamaregister.ee serves a JS shell + an undiscovered keyless-looking app
# API with NO licence statement (2026-09-16 verdict above); the INSPIRE WFS
# carries geometry + names only (no function taxonomy); AIS grid values are
# unprobed. Each scorer reports the gap with a concrete buyer-side check.
# ---------------------------------------------------------------------------

def dim_harbour_function_zone(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """Measured port-function zone leg: NULL until the licence gate clears."""
    return None, ("Sadama funktsiooni-tsooni hinnangut pole (EI OLE "
                  "sadamaregistri litsentsi: avaandmete-leht on JS-kest, "
                  "/avaandmed.xsd puudub (404), rakenduse API-alus "
                  "avastamata ja litsentsita -- kontrollitud 2026-09-16; "
                  "INSPIRE WFS kannab ainult sadama nime + geomeetriat, "
                  "funktsiooni-taksonoomiat seal EI OLE): kruiisi/kauba/"
                  "jahisadama-funktsioonide mõõdetud asendus "
                  "dims_p4_trans'i sadam-fikstiivile (60) valmib alles "
                  "loa kinnitusel -- kontrolli sadamaregistri sadamalehti, "
                  "ts.ee sõiduplaane ja kuula Vanasadama/Pirita serva "
                  "kohapeal, ära feigi")


def dim_ais_pleasure_density(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """AIS pleasure-craft 500 m-grid overlay leg: NULL, no values pulled."""
    return None, ("Väikelaevade AIS-tiheduse hinnangut pole (EI OLE "
                  "laevaliikluse 500 m ruudustiku väärtusi: kataloogikirje "
                  "pole kohalikust peeglist kättesaadav, failisuurused/CRS/"
                  "2024 Pirita/Kakumäe väärtused tõmbamata -- kontrollitud "
                  "2026-09-16): ruudustik loetaks 1:1 (ruut ON väli, "
                  "interpolatsiooni EI OLE), lühiajalised AIS-lüngad "
                  "märgitaks -- kontrolli sadamateenuseid ja tee "
                  "purjetamis-hooajal kohapealne vaatlus, ära feigi")


P4_HARBOUR_DIMS = (
    ("harbour_function_zone", "P4-023", dim_harbour_function_zone),
    ("ais_pleasure_density", "P4-033", dim_ais_pleasure_density),
)


def score_p4_harbour(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 harbour dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_HARBOUR_DIMS). Every value
    is None by design -- licence-gated register, unprobed AIS grid, never
    a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_HARBOUR_DIMS}
