"""P4 Elron dims (issues #284 demo + #358 coverage).

Params (this module only — demo + its coverage follow-up share one source):
* P4-014 Rail Baltica / tram construction phase, Elron slice: ajutised
  sõiduplaanid (batch 1, demo in #284)
* P4-032 Activity heat, Elron slice: evening ridership per Tallinn stop,
  usage proxy only (batch 3, coverage in #358)
* P4-055 Harbour/air timetable nuisances, Elron slice: raudteemüra
  ööaknad / maintenance windows (batch 5, coverage in #358)
* P4-061 Last-shop/pharmacy/ATM + bus-cut tracker, Elron slice:
  sõiduplaanimuudatused at Tallinn fringe stations (batch 5, coverage
  in #358)

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#284): Elron publishes no pollable machine-readable feed for any of the
four slices above. Polite evidence, 5 tiny requests total (four single
GETs with a labelled one-off user-agent, headers + visible-text
keyword scope read only, no scraping, no auth), raw bodies cached at
/tmp/elron-open/ (TTL: one-off check, kept for the PR record, never
committed):
* https://elron.ee/ -> HTTP 200, ~93 KB. Visible text (~2.5k chars)
  sweeps 0 for avaandmed / open data / GTFS / arendaja / developer /
  API / X-tee / andmestik / masinloetav. Timetables are linked as
  passenger pages (/soiduinfo/soiduplaanid), notices as
  /soiduinfo/teated — never a bulk feed.
* https://elron.ee/soiduinfo/soiduplaanid -> HTTP 200, ~82 KB.
  Timetables are per-direction PDF files
  (/sites/default/files/2026-08/...pdf: lääne-, edela-, ida-/
  lõuna-, Tallinn-Riia/Vilnius). Visible text (~2.1k chars) sweeps 0
  for GTFS / avaandmed / API / masinloetav / rss. "Telli teated" is a
  human subscription, not a feed; /raudteeremondid is a human repair
  page. Parsing direction PDFs would be scraping human publications,
  not polling a feed — exactly the scraping this repo refuses
  (AGENTS.md section 5).
* https://elron.ee/soiduinfo/teated -> HTTP 200, ~100 KB.
  "Rongiliikluse teated" are dated human-readable news entries (e.g.
  "13.09.2026 10:27 Reis..."); visible text (~3.8k chars) sweeps 0
  for GTFS / avaandmed / masinloetav / rss / API. Schedule changes
  exist as news HTML, never a comparable machine vintage — so neither
  the P4-014 construction calendar nor the P4-061 fringe-station cut
  fraction can be measured.
* https://andmed.eesti.ee/dataset?q=elron -> HTTP 200, ~75 KB JS
  "Teabevärav" shell with 12 visible characters and no
  server-rendered results — no trivially pollable national-portal
  Elron dataset (same shell as the #264 and #277 checks).
* Peatus.ee GTFS (the national GTFS door Elron departures would ride)
  stays closed per the #314 check (2026-09-13, "Rakendus on suletud")
  — not re-probed here.
So all four dims return None for EVERY input including missing
origin: a per-station band painted from a one-off hand-check would be
fake precision (OTA PR #131 precedent). Reasons say "hinnang"
(estimate) and "EI OLE" and point at the concrete buyer-side check
(elron.ee sõiduplaanid/teated/raudteeremondid, Peatus.ee GTFS diff,
kohapealne vaatlus) — never a faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_p4_tlt.py (#277/#351): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a rail operator's unpublished timetable
deltas, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#358) states it extends the demoed ingestion (#284): with
  the demo verdict dated-negative, there is no ingestion to extend,
  so the three coverage slices land in the same verdict module
  rather than a second file importing a pipeline that does not
  exist (same precedent as TLT #277+#351, elektrilevi #264+#344,
  comapps #302+#371, RB #281+#355).
* Sibling legs stay scored where they live: the P4-014 Rail Baltica
  slices (dims_p4_rb dim_ehitusfaas_rb / dim_koridor_reserv_rb, #410)
  and the P4-061 Peatus-GTFS bus-cut leg (dims_p4_peatus
  dim_bus_cut) are different sources' readings, not this verdict's
  Elron slices — re-scoring those cousins here would claim the full
  param on a partial signal (same split-slice precedent as P4-020:
  ATA notices scored in dims_p4_ata, bureau scores NULL in
  dims_p4_creditinfo). The P4-032 TLT evening-ridership leg is
  likewise NULL in dims_p4_tlt, and the OSM leisure-density proxy
  touching P4-032/P4-061 lives in dims_p4_osm.
* P4-032 names the usage-not-safety label explicitly (PPA/
  Päästeamet explicitly NOT a source): an evening-departure count
  is a lived-in-street proxy, never a safety verdict.
* P4-055 covers ONLY the Elron raudteemüra-ööaknad leg: the
  harbour/air slices (Sadam laevagraafik, EANS lennuinfo, Männiku
  laskmisteated) belong to future source issues and are named in
  docs/p4_elron.md as overturn paths, not scored here.
* The openness check stopped at storefront/page level on purpose —
  no PDF parsing, no subscription-flow driving, no timetable
  internals scraping.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-014/P4-032/P4-055/P4-061: documented no-map Elron-feed NULLs (OTA PR
# #131 precedent). Elron's temporary timetables, evening ridership,
# night maintenance windows and fringe-station schedule changes are
# direction PDFs or human-readable news with no public bulk feed; each
# scorer reports the gap with a concrete buyer-side check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_elron_construction_calendar(origin: Optional[Tuple[float, float]],
                                    pois: Optional[List[dict]]) -> Score:
    """P4-014: NULL — ajutised sõiduplaanid calendar needs the feed (no map)."""
    return None, ("Elroni ajutiste sõiduplaanide kalender on ehitusfaasi "
                  "hinnang (EI OLE masinloetavat kalendrit): suunapõhised "
                  "PDF-sõiduplaanid ja rongiliikluse teated elron.ee-s on "
                  "inimloetavad, võrreldavat masin-vintsi pole — kontrolli "
                  "oma suuna PDF-i ja teateid elron.ee/soiduinfo/ "
                  "sõiduplaanid-lehelt ning RB-slice'i dims_p4_rb-st, "
                  "ära feigi")


def dim_elron_evening_ridership(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """P4-032: NULL — evening ridership per stop is unpublished (no map)."""
    return None, ("Elroni peatuse õhtune täituvus on kasutusaktiivsuse "
                  "hinnang (EI OLE loendusandmeid, kasutus-mitte-"
                  "turvalisus): õhtuseid väljumisarve Tallinna peatuse "
                  "kohta avalikus voogus pole ning PPA/Päästeamet pole "
                  "allikas — hinda õhtust elavust kohapealsel vaatlusel, "
                  "ära feigi")


def dim_elron_night_maintenance(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """P4-055: NULL — raudteemüra ööaknad have no machine calendar (no map)."""
    return None, ("Elroni raudteemüra ööaknad on hooldusgraafiku hinnang "
                  "(EI OLE masinloetavat akna-kalendrit): raudteeremondid "
                  "ja rongiliikluse teated elavad elron.ee-s inimloetavalt "
                  "— kontrolli öise müra aknaid elron.ee/raudteeremondid- "
                  "lehelt ja teadetest, sadama/lennu-slice'id eraldi "
                  "allikatest, ära feigi")


def dim_elron_schedule_changes(origin: Optional[Tuple[float, float]],
                               pois: Optional[List[dict]]) -> Score:
    """P4-061: NULL — fringe-station schedule changes need the feed (no map)."""
    return None, ("Elroni sõiduplaanimuudatused äärejaamades on "
                  "bussikärbe-jälgija Elroni-hinnang (EI OLE võrreldavat "
                  "masin-vintsi): Lilleküla/Kitseküla/Ülemiste muudatused "
                  "elavad elron.ee teadetes inimloetavalt — kontrolli "
                  "teateid elron.ee/soiduinfo/teated-lehelt ja küsi "
                  "Peatus.ee GTFS diffi, ära feigi")


P4_ELRON_DIMS = (
    ("elron_construction_calendar", "P4-014", dim_elron_construction_calendar),
    ("elron_evening_ridership", "P4-032", dim_elron_evening_ridership),
    ("elron_night_maintenance", "P4-055", dim_elron_night_maintenance),
    ("elron_schedule_changes", "P4-061", dim_elron_schedule_changes),
)


def score_p4_elron(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All four P4 Elron dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_ELRON_DIMS). Every value
    is None by design — unpublished Elron feed, never a faked area
    score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_ELRON_DIMS}
