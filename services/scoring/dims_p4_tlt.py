"""P4 Tallinna Transport / TLT dims (issues #277 demo + #351 coverage).

Params (this module only — demo + its coverage follow-up share one source):
* P4-061 Last-shop/pharmacy/ATM + bus-cut tracker, TLT slice:
  liinimuudatuste teated / talvine bussiliiklus (batch 5, demo in #277)
* P4-012 Accident blackspots, TLT slice: liikluskorraldus + ohutud
  kooliteed (batch 1, coverage in #351)
* P4-018 Snow/road maintenance class, TLT slice: talvine bussiliiklus
  bus-cut cross-check (batch 2, coverage in #351)
* P4-027 Grocery slots + night life, TLT slice: öötransport (ööbussid)
  coverage (batch 3, coverage in #351)
* P4-032 Activity heat, TLT slice: evening ridership per stop, usage
  proxy only (batch 3, coverage in #351)
* P4-037 Policy exposure, TLT slice: commute alternatives per address,
  exposure offset (batch 3, coverage in #351)
* P4-045 Third places, TLT slice: evening access per third place
  (batch 4, coverage in #351)
* P4-048 Small delights, TLT slice: <15 min access per delight
  (batch 4, coverage in #351)
* P4-049 Taxi/guest test, TLT slice: guest-arrival time per address
  (batch 4, coverage in #351)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#277): TLT publishes no pollable machine-readable feed for any of the
nine slices above. Polite evidence, 6 tiny requests total (redirect
checks + three single GETs with a labelled one-off user-agent,
headers + visible-text keyword scope read only, no scraping, no
auth), raw bodies cached at /tmp/tlt-open/ (TTL: one-off check, kept
for the PR record, never committed):
* https://www.tlt.ee/ -> 301 to https://tlt.ee/ (HTTP 200, ~60 KB
  WordPress corporate site: news, piletiinfo, teenused; visible-text
  sweep scores 0 for avaandmed / open data / GTFS / arendaja /
  developer / API / X-tee / andmestik / masinloetav — sõiduplaan 1x
  as a passenger page link, liinimuudatus/ööbuss/öötransport/
  Kooliteed 0). Timetables and liinimuudatused live as human-readable
  teated (e.g. /teadeteajalugu/: "1. septembrist minnakse üle
  sügis-talvistele sõiduplaanidele"), never a bulk feed.
* https://transport.tallinn.ee/ (HTTP 200, ~150 KB) and its alias
  https://soiduplaan.tallinn.ee/ (301 -> transport.tallinn.ee) serve
  the interactive timetables / trip-planner web app (Routes and
  Schedules, Trip planner, Map); visible-text sweep scores 0 for
  every open-data keyword — an interactive planner, not a pollable
  join.
* National portal https://andmed.eesti.ee/dataset?q=tallinna+
  linnatransport+GTFS (HTTP 200, ~75 KB) serves the JS "Teabevärav"
  shell with 12 visible characters and no server-rendered results —
  no trivially pollable TLT dataset (same shell as the #264 check).
* https://opendata.tallinn.ee/ does not resolve (DNS NXDOMAIN) —
  there is no Tallinn open-data portal to poll.
Pulling any of this anyway would mean driving planner session flows
or scraping app internals — exactly the scraping this repo refuses
(AGENTS.md section 5). So all nine dims return None for EVERY input
including missing origin: a per-stop band painted from a one-off
hand-check would be fake precision (OTA PR #131 precedent). Reasons
say "hinnang" (estimate) and "EI OLE" and point at the concrete
buyer-side check (tlt.ee teadeteajalugu, transport.tallinn.ee trip
planner, EMTA automaksu kalkulaator, kohapealne vaatlus) — never a
faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_group20a.py (#212): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a bus operator's unpublished timetable
deltas, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#351) states it extends the demoed ingestion (#277): with
  the demo verdict dated-negative, there is no ingestion to extend,
  so the eight coverage slices land in the same verdict module
  rather than a second file importing a pipeline that does not
  exist (same precedent as elektrilevi #264+#344 and comapps
  #302+#371).
* No fixture-scored bands (unlike the peatus sibling #314+#376):
  Peatus could prove GTFS bands on fixtures because GTFS is a
  documented standard format with a documented feed URL behind the
  closed door. TLT has neither — no documented machine URL nor a
  machine format to parse — so a fixture timetable schema here would
  be invented, and scoring it would claim a join that has no source.
  The honest shape is the documented NULL with the concrete missing
  input named per param.
* Sibling legs stay scored where they live: the Peatus-GTFS legs of
  P4-061/P4-037/P4-045/P4-048/P4-049 (dims_p4_peatus) and the OSM
  proxies touching P4-012/P4-027/P4-032/P4-045/P4-049/P4-061
  (dims_p4_osm) are different sources' readings, not this verdict's
  TLT slices — re-scoring those cousins here would claim the full
  param on a partial signal (same split-slice precedent as P4-020:
  ATA notices scored in dims_p4_ata, bureau scores NULL in
  dims_p4_creditinfo).
* P4-032 names the usage-not-safety label explicitly (PPA/
  Päästeamet explicitly NOT a source): an evening-ridership count
  is a lived-in-street proxy, never a safety verdict.
* The openness check stopped at storefront/app-shell level on
  purpose — no endpoint enumeration, no planner session flows, no
  app-internals scraping.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-061/P4-012/P4-018/P4-027/P4-032/P4-037/P4-045/P4-048/P4-049: documented
# no-map TLT-feed NULLs (OTA PR #131 precedent). TLT's line-change
# notices, winter timetables, night network, stop ridership and
# commute-time planner are human-readable or interactive-only with no
# public bulk feed; each scorer reports the gap with a concrete
# buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_tlt_bus_cut(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """P4-061: NULL — TLT bus-cut tracker needs the machine feed (no map)."""
    return None, ("TLT bussikärbe jälgija on liinimuudatuste hinnang "
                  "(EI OLE masinloetavat voogu): sügis-talviseid "
                  "sõiduplaane ja liinimuudatuste teateid tlt.ee "
                  "teadeteajaloos inimloetavalt on, aga võrreldavat "
                  "masin-vintsi pole — kontrolli Harku/Maardu/Saue suuna "
                  "teateid tlt.ee-st ja küsi Peatus.ee GTFS diffi, ära feigi")


def dim_tlt_school_routes(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-012: NULL — safe-school-routes map is unpublished (no map)."""
    return None, ("Ohutute kooliteede kaart on TLT liikluskorralduse "
                  "hinnang (EI OLE masinloetavat kaarti): kooliteede "
                  "trasse ja reguleeritud ristmikke avalikus voogus pole "
                  "— hinda ristmikku kohapealsel vaatlusel ja kontrolli "
                  "OSM sebra/kiirustõkete kaarti, ära feigi ohutus-skoori")


def dim_tlt_winter_ops(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-018: NULL — winter bus-ops cross-check needs timetables (no map)."""
    return None, ("Talvise bussiliikluse ristkontroll on sõiduplaani "
                  "hinnang (EI OLE võrreldavat masin-vintsi): sügis-"
                  "talvised sõiduplaanid elavad tlt.ee teadetes "
                  "inimloetavalt — kontrolli oma liini talvist tihedust "
                  "teadeteajaloost ja Tallinna talihoolduse tasemeid "
                  "Keskkonna- ja Kommunaalametist, ära feigi")


def dim_tlt_night_network(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-027: NULL — night-transport coverage has no machine map (no map)."""
    return None, ("Öötranspordi katvus on öövõrgu hinnang (EI OLE "
                  "masinloetavat öökaarti): ööbusside trasse avalikus "
                  "voogus pole — kontrolli oma aadressi öist jõudmist "
                  "transport.tallinn.ee reisplaneerijast ja Wolt/Bolti "
                  "öökatvust, ära feigi auto-vaba ööelu skoori")


def dim_tlt_evening_ridership(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-032: NULL — evening ridership per stop is unpublished (no map)."""
    return None, ("Peatuse õhtune täituvus on kasutusaktiivsuse hinnang "
                  "(EI OLE loendusandmeid, kasutus-mitte-turvalisus): "
                  "TLT/Elroni õhtuseid väljumisarve peatuse kohta "
                  "avalikus voogus pole ning PPA/Päästeamet pole allikas "
                  "— hinda õhtust elavust kohapealsel vaatlusel, ära feigi")


def dim_tlt_commute_offset(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-037: NULL — commute-alternative offset needs planner join (no map)."""
    return None, ("Ühistranspordi-alternatiivi leevendus on pendelrände "
                  "hinnang (EI OLE masinarvutust): aadressi TLT-"
                  "alternatiive avalikus voogus pole — arvuta oma "
                  "pendel transport.tallinn.ee reisplaneerijaga ja "
                  "kontrolli EMTA automaksu kalkulaatorist, ära feigi")


def dim_tlt_evening_access(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-045: NULL — evening access per third place is unjoined (no map)."""
    return None, ("Kolmanda koha õhtune juurdepääs on TLT-ühenduse "
                  "hinnang (EI OLE masinliidestust): sauna/publi/"
                  "raamatukogu õhtust TLT-jõudmist avalikus voogus pole "
                  "— kontrolli õhtust ühendust reisplaneerijast ja "
                  "õhtuseid lahtiolekuaegu kohapeal, ära feigi")


def dim_tlt_delight_access(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-048: NULL — <15 min delight access needs timetable join (no map)."""
    return None, ("Rõõmukoha <15 min juurdepääs on TLT-isokrooni hinnang "
                  "(EI OLE sõiduplaani-liidestust): ujula/jäähalli "
                  "15-minuti kättesaadavust masinloetaval sõiduplaanil "
                  "pole — mõõda jalutuskäik kohapeal ja kontrolli "
                  "ühendust reisplaneerijast, ära feigi")


def dim_tlt_guest_arrival(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-049: NULL — guest-arrival time per address is unjoined (no map)."""
    return None, ("Külalise saabumisaeg on TLT-ühenduse hinnang (EI OLE "
                  "masinarvutust): aadressi külalise saabumisaega "
                  "avalikus voogus pole — proovi laupäeva 19:00 ühendust "
                  "transport.tallinn.ee reisplaneerijast ja Bolti "
                  "leitavust, ära feigi")


P4_TLT_DIMS = (
    ("tlt_bus_cut", "P4-061", dim_tlt_bus_cut),
    ("tlt_school_routes", "P4-012", dim_tlt_school_routes),
    ("tlt_winter_ops", "P4-018", dim_tlt_winter_ops),
    ("tlt_night_network", "P4-027", dim_tlt_night_network),
    ("tlt_evening_ridership", "P4-032", dim_tlt_evening_ridership),
    ("tlt_commute_offset", "P4-037", dim_tlt_commute_offset),
    ("tlt_evening_access", "P4-045", dim_tlt_evening_access),
    ("tlt_delight_access", "P4-048", dim_tlt_delight_access),
    ("tlt_guest_arrival", "P4-049", dim_tlt_guest_arrival),
)


def score_p4_tlt(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All nine P4 TLT dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_TLT_DIMS). Every value
    is None by design — unpublished TLT feed, never a faked area
    score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_TLT_DIMS}
