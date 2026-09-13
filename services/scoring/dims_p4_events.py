"""P4 events dims (issues #310 demo + #375 coverage): Tallinna event and
fireworks-calendars verdict.

Demo (#310): Tallinna event & fireworks calendars via P4-033 Seasonal
nuisance calendar (Lauluväljak/Pirita event calendars, church bells,
fireworks permits, festive calendar) end-to-end in Tallinn.
Coverage (#375): P4-047 Small horrors calendar, fireworks-alleys slice
(ilutulestiku load + jaanipäeva/uusaasta calendar), wired to the same
demoed ingestion.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict per
#310: the venues publish no pollable machine-readable feed for either
leg, so both dims stay NULL). Polite evidence, 6 single GETs plus 2
TLS-failed attempts total (labelled one-off user-agent, 2 s pacing,
`--max-time 25`, headers + visible-text keyword scope read only, no
scraping, no auth, no retries - HTTP 429/errors are a stop signal),
raw bodies cached at /tmp/hf-p4-events/ (one-off PR record, never
committed):
* https://www.lauluväljak.ee/ and https://lauluväljak.ee/ -> TLS
  certificate mismatch (curl exit 60 on both): transport error, never
  data. No retry dare per AGENTS.md section 7.4.
* http://lauluväljak.ee/ -> HTTP 400, Veebimajutus.ee parking page
  (~8.8 KB raw, 582 visible chars, 0 for ilutulestik/luba/load/
  lauluväljak/laulupidu/kalender/üritus/sündmus/csv/json/api/
  avaandmed/masinloetav/andmestik). The IDN domain serves hosting
  placeholder HTML, not an event calendar.
* https://kultuurikava.ee/ -> HTTP 200 (1796 bytes): React SPA shell
  (`/static/js/main.07d7e3b5.js`, "Sinu teejuht kultuurimaastikul"),
  no server-rendered event rows. Chasing the app API would exceed a
  polite probe budget (same stop-at-shell precedent as the lumekaart
  and veebikaart shells in #283).
* https://www.rescue.ee/et -> HTTP 200 (~143 KB): Päästeamet homepage
  (~3.8k visible chars), 0 for ilutulestik/luba/load/kalender in
  visible text - no fireworks-permit feed advertised at entry level.
* https://andmed.eesti.ee/dataset?q=ilutulestik -> HTTP 200 (~75 KB
  raw) with 12 visible characters ("Teabevärav" JS shell) - no
  server-rendered national-portal fireworks dataset (same shell as
  the #264/#277/#284/#298 checks).
* https://www.tallinn.ee/et/kultuur -> HTTP 200 (~83 KB): CMS culture
  page (institution links, 2x Lauluväljak, 3x üritus, 2x sündmus),
  0 for kalender/ilutulestik/load/csv/json/api/avaandmed - links to
  institutions, never a pollable calendar feed.

So both dims return None for EVERY input including missing origin:
a date hand-read from a human culture page or a React shell would be
fake precision (OTA PR #131 precedent), and replaying forms or app
APIs is exactly the human-page harvesting this repo refuses
(AGENTS.md section 5; same stop-at-human-HTML precedent as komun
#290, Elron #284, kesk-hunting #291/#364, sadam #298/#368). Reasons
say "hinnang" (estimate) and "EI OLE" and point at the concrete
buyer-side check (venue calendars, permit desk, on-site listening,
sibling slices) - never a faked area score.

Style mirrors services/scoring/dims_p4_sadam.py (#298/#368): every
scorer is pure and offline-tested - (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no Overpass
fragment, and no tag mapping: there is no honest snapshot tag to query
for dated event rows or dated fireworks permits, so there is nothing
for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In practice
this verdict module needs no helpers at all - each dim reports its
missing feed directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#375) states it extends the demoed ingestion (#310) with "no
  new plumbing expected": with the demo verdict dated-negative, there
  is no ingestion to extend, so the P4-047 fireworks slice lands in
  the same verdict module rather than a second file importing a
  pipeline that does not exist (same precedent as komun #290+#363,
  TLT #277+#351, elektrilevi #264+#344, Elron #284+#358, RB #281+#355,
  kesk #291+#364, sadam #298+#368).
* Pairing rationale (each param names this source family in its
  parameters4.md source list, so no weak link): P4-033 source (2)
  "Lauluväljak/Pirita event calendars (Tallinn Culture programme)"
  and source (3) "Tallinna kirikute kellad + ürituste müra load" are
  the demo legs; P4-047 source (3) "Tallinna ilutulestiku load +
  jaanipäeva/uusaasta calendar" is the fireworks-alleys coverage leg.
* Per-source slices, not full params: P4-033 keeps the sadam cruise
  leg (dims_p4_sadam) and the kesk hunting leg (dims_p4_kesk);
  P4-047 keeps the komun mürakaebused + talihooldus legs
  (dims_p4_komun), the KÜ complaint-log slice (dims_p4_kudocs), the
  OSM proxy NULL (dims_p4_osm) and the Päästeamet event-traffic
  calendar (dims_p4_paaste). Distinct dim keys throughout so the
  central hook can weight slices independently. Each reason names
  its cousins.
* The tallinn.ee culture CMS page EXISTS (Lauluväljak mentions
  observed) but is not a pollable feed: institution links are not
  dated event rows, so no calendar band is painted from them. The
  reopening checklist in docs/p4_events.md says exactly what would
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
# P4-033/P4-047: documented no-map events-leg NULLs (OTA PR #131
# precedent). Venues publish human culture pages and a React shell but
# no keyless machine feed (2026-09-13 dated-negative verdict above);
# each scorer reports the gap with a concrete buyer-side check instead
# of a faked number.
# ---------------------------------------------------------------------------

def dim_events_calendar(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-033: NULL - event calendar needs the machine feed (no map)."""
    return None, ("Ürituskalendri hinnangut pole (EI OLE masinloetavat "
                  "Lauluväljak/Pirita/kultuurikalendri voogu): "
                  "lauluväljak.ee on majutuse platsihoidja-leht "
                  "(kontrollitud 2026-09-13, HTTP 400), kultuurikava.ee "
                  "on Reacti kest ilma serveri ürituseridadeta ja "
                  "tallinn.ee/kultuur on asutuste-linkide CMS-leht, mitte "
                  "kuupäevatud kalendrivoog - kontrolli Lauluväljaku ja "
                  "Pirita kalendreid ning kirikukellade/müra lubasid "
                  "sealt, kuula Kesklinna/Pirita serva kohapeal; "
                  "kruiisipäevad dims_p4_sadam'is, jahiteated "
                  "dims_p4_kesk'is, ära feigi")


def dim_fireworks_calendar(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-047: NULL - fireworks calendar needs dated permits (no map)."""
    return None, ("Ilutulestiku-kalendri hinnangut pole (EI OLE "
                  "kuupäevatud ilutulestiku-lubade voogu): Päästeameti "
                  "avalehel pole lubade-kalendrit ja riigiportaalis pole "
                  "ilutulestiku andmestikku (mõlemad kontrollitud "
                  "2026-09-13, Teabevärava kest), jaanipäeva/uusaasta "
                  "kuupäevad üksi pole allee-kaart - küsi korraldaja "
                  "lubasid linnavalitsusest/Päästeametist ning kuula "
                  "jaanipäeva ja aastavahetuse paiku kohapeal; "
                  "mürakaebused ja sahavedu dims_p4_komun'is, KÜ logid "
                  "dims_p4_kudocs'is, üritusliikluse kalender "
                  "dims_p4_paaste'is, ära feigi")


P4_EVENTS_DIMS = (
    ("events_calendar", "P4-033", dim_events_calendar),
    ("fireworks_calendar", "P4-047", dim_fireworks_calendar),
)


def score_p4_events(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 events dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_EVENTS_DIMS). Every value
    is None by design - human culture pages and shells, no pollable
    feed, never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_EVENTS_DIMS}
