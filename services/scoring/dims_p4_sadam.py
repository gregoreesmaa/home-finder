"""P4 sadam dims (issues #298 demo + #368 coverage): Tallinna Sadam verdict.

Demo (#298): Tallinna Sadam ingestion + P4-033 Seasonal nuisance calendar
(cruise days, Vanasadam traffic) end-to-end in Tallinn. Coverage (#368):
P4-023 (sadam ship/heli noise leg), P4-053 (harbour-odour sector
cross-check leg), P4-055 (harbour timetable leg: foghorns, icebreakers)
wired to the same demoed ingestion.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#298: the harbour publishes no pollable machine-readable feed for any of
the four legs, so all four dims stay NULL). Polite evidence, 4 tiny
requests total (four single GETs with a labelled one-off user-agent,
2 s pacing, `--max-time 25`, headers + visible-text keyword scope read
only, no scraping, no auth), raw bodies cached at /tmp/hf-p4-sadam/
(one-off PR record, never committed):
* https://www.ts.ee/ -> HTTP 200 (~137 KB, cloudflare). Human
  storefront ("Tallinna Sadam - hoiame Eesti kurssi mereriigina",
  ~11.4k visible chars). Sweep 0 for csv / geojson / wfs / api /
  masinloetav / andmestik / avaandmed. Links schedule pages
  (/laevad-sadamas/, /kruiisid/) and the newsroom (/uudised/).
* https://www.ts.ee/laevad-sadamas/ -> HTTP 200 (~158 KB). Human
  ship-timetable page with a server-rendered filter form ("Saabumise
  kuupäev alates/kuni", "Saabumise sadam", "Laeva nimi") and live rows
  (e.g. SPIRIT OF DISCOVERY, 13.09.2026, kai 27, Stockholm->Helsinki).
  No JSON/CSV/API endpoint in page-source scope (only a Google Maps
  key + theme ajax chrome) - a filter-form HTML table, not a feed.
* https://www.ts.ee/kruiisid/ -> HTTP 200 (~233 KB). Human cruise page
  (26x "kruiisilaev", 105x "saabum", 27x "kai" in visible text), 0 for
  csv / geojson / wfs / api / masinloetav / andmestik.
* https://andmed.eesti.ee/dataset?q=sadam -> HTTP 200 (~75 KB) with 12
  visible characters ("Teabevärav" JS shell) - no server-rendered
  national-portal sadam dataset (same shell as the #264/#277/#284
  checks). The only notice channel is the human newsroom /uudised/.

So all four dims return None for EVERY input including missing origin:
a cruise count hand-read from the filter-form HTML would be fake
precision (OTA PR #131 precedent) and scraping the form is exactly the
human-page harvesting this repo refuses (AGENTS.md section 5; same
stop-at-human-HTML precedent as komun #290, Elron #284, kesk-hunting
#291/#364). Reasons say "hinnang" (estimate) and "EI OLE" and point at
the concrete buyer-side check (ts.ee timetable/cruise pages, newsroom,
on-site listening, sibling slices) - never a faked area score.

Style mirrors services/scoring/dims_p4_komun.py (#290/#363): every
scorer is pure and offline-tested - (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no Overpass
fragment, and no tag mapping: there is no honest snapshot tag to query
for cruise days, harbour noise notices, or foghorn timetables, so there
is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In practice
this verdict module needs no helpers at all - each dim reports its
missing feed directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#368) states it extends the demoed ingestion (#298): with the
  demo verdict dated-negative, there is no ingestion to extend, so the
  three coverage slices land in the same verdict module rather than a
  second file importing a pipeline that does not exist (same precedent
  as komun #290+#363, TLT #277+#351, elektrilevi #264+#344, Elron
  #284+#358, RB #281+#355, kesk #291+#364).
* Pairing rationale (each param names Tallinna Sadam in its
  parameters4.md source list, so no weak link): P4-033 source (1)
  "Tallinna Sadam cruise schedule (Vanasadam traffic days)" is the
  demo leg; P4-023 source (4) "Tallinna Sadam laeva/helikopteri müra
  teated" is the noise leg; P4-053 source (6) "Tallinna Sadam
  harbour-odour teated (sector cross-check)" is the odour leg; P4-055
  source (1) "Tallinna Sadam laevagraafik (foghorns, icebreakers -
  Vanasadam/Pirita)" is the timetable leg.
* Per-source slices, not full params: P4-023 keeps the trans zone band
  (dims_p4_trans), the KAUR rattle leg (dims_p4_kaur) and the EHR NULL
  (dims_p4_ehr); P4-033 keeps the kesk hunting leg (dims_p4_kesk);
  P4-053 keeps the ilm rose (dims_p4_ilm), the KAUR sector days
  (dims_p4_kaur), the EELIS emitters (dims_p4_eelis) and the komun
  complaint legs (dims_p4_komun); P4-055 keeps the Elron night-
  maintenance NULL (dims_p4_elron) and the komun validation leg
  (dims_p4_komun). Distinct dim keys throughout so the central hook
  can weight slices independently. Each reason names its cousins.
* The human timetable EXISTS (live ship rows observed) but is not a
  pollable feed: replaying its filter form would be HTML scraping with
  no stated vintage or schema, so no calendar band is painted from it.
  The reopening checklist in docs/p4_sadam.md says exactly what would
  graduate each dim.

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-033/P4-023/P4-053/P4-055: documented no-map sadam-leg NULLs (OTA PR
# #131 precedent). ts.ee publishes human timetable/cruise/news pages but
# no keyless machine feed (2026-09-13 dated-negative verdict above); each
# scorer reports the gap with a concrete buyer-side check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_sadam_cruise_calendar(origin: Optional[Tuple[float, float]],
                              pois: Optional[List[dict]]) -> Score:
    """P4-033: NULL - cruise calendar needs the machine feed (no map)."""
    return None, ("Kruiisikalendri hinnangut pole (EI OLE masinloetavat "
                  "kruiisigraafiku voogu): ts.ee laevagraafik "
                  "(/laevad-sadamas/) ja kruiisileht (/kruiisid/) on "
                  "inimloetav HTML-filtrivorm (kontrollitud 2026-09-13, "
                  "teated uudisevoos /uudised/), mitte võtmeta CSV/API - "
                  "kontrolli Vanasadama liikluspäevi sealt ning "
                  "Lauluväljaku/Pirita ja Kaitseväe kalendreid, "
                  "jahiteadete-pool dims_p4_kesk'is, ära feigi")


def dim_sadam_noise_notices(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-023: NULL - harbour noise notices are newsroom items (no map)."""
    return None, ("Sadama müra-hinnangut pole (EI OLE laeva/helikopteri "
                  "müra teadete-voogu): teated elavad inimloetavas "
                  "uudisevoos (ts.ee/uudised/, kontrollitud 2026-09-13), "
                  "sadamal pole tsoonikihti ega EANS-liidestust - kuula "
                  "Vanasadama/Pirita serva kohapeal; lennu- ja õppuse-"
                  "tsoonid dims_p4_trans'is ja dims_p4_kaur'is, "
                  "isolatsiooninõuded dims_p4_ehr'is, ära feigi")


def dim_sadam_odour_sector(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-053: NULL - harbour-odour sector needs feed + inventory (no map)."""
    return None, ("Sadama lõhnasektori hinnangut pole (EI OLE sadama "
                  "lõhnateadete-voogu ega heitja-inventuuri): teated on "
                  "inimloetavad uudised (ts.ee/uudised/), sektor + "
                  "kalender eeldaks Ilmateenistuse Harku tuuleroosi ja "
                  "Paljassaare/kalasuitsu allikaid - tuulesuuna-pool "
                  "dims_p4_ilm'is, sektoripäevad dims_p4_kaur'is, heitjad "
                  "dims_p4_eelis'is, kaebused dims_p4_komun'is; tee "
                  "allatuule jalutuskäik kohapeal, ära feigi")


def dim_sadam_timetable(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-055: NULL - foghorn/icebreaker calendar needs the feed (no map)."""
    return None, ("Sadama sõiduplaani-müra hinnangut pole (EI OLE "
                  "udusireenide/jäämurdjate masinkalendrit): laevagraafik "
                  "on inimloetav HTML-tabel (ts.ee/laevad-sadamas/, "
                  "kontrollitud 2026-09-13), jäämurdeteated samuti "
                  "uudised - kuula udu- ja jäähooajal kohapeal; "
                  "raudtee-ööaknad dims_p4_elron'is, mürakaebuste-"
                  "validatsioon dims_p4_komun'is, ära feigi")


P4_SADAM_DIMS = (
    ("sadam_cruise_calendar", "P4-033", dim_sadam_cruise_calendar),
    ("sadam_noise_notices", "P4-023", dim_sadam_noise_notices),
    ("sadam_odour_sector", "P4-053", dim_sadam_odour_sector),
    ("sadam_timetable", "P4-055", dim_sadam_timetable),
)


def score_p4_sadam(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All four P4 sadam dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_SADAM_DIMS). Every value
    is None by design - human harbour pages, no pollable feed, never a
    faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_SADAM_DIMS}
