"""P4 Veeteede Amet icebreaking dim (issue #311, single-param demo, no coverage issue).

Demo (#311): Veeteede Amet jäämurde teated (icebreaking notices,
Tallinn Bay) for P4-055 end-to-end in Tallinn — openness verification
plus the honest-shape icebreaking-season leg. Single param: P4-055
Harbour/air timetable nuisances, Veeteede slice (source (4), batch 5:
Tallinn Bay icebreakers). Honest shape when a feed lands: calendar
dim, never a gradient.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #311): the icebreaking notices live as dated human PDF directives
(käskkirjad) on a Transpordiamet topic page — no keyless machine
calendar feed — so there is no polite pull to cache and no honest
calendar to score. Polite evidence, 6 served requests total (single
GETs with a labelled one-off user-agent, headers + visible-text
keyword scope read only, no scraping, no auth, no PDF parsing, no
form driving, redirects not spidered beyond the single canonical
documented link), raw bodies cached at /tmp/hf-p4-veeteede/ (one-off
PR record, never committed):
* https://www.veeteedeamet.ee/ -> HTTP 301 (0 B) to
  https://www.transpordiamet.ee/ (single documented-link redirect;
  the old Veeteede Amet host is a forwarder, not a feed — the
  successor since the 2021 merger is Transpordiamet).
* https://transpordiamet.ee/ -> HTTP 200, 227 004 B, title
  "Transpordiamet | Muretult kohale!". Portal front; visible-text
  sweep (~12.5k chars): jäämur x2, 0 for avaandmed / open data / API
  / andmestik / masinloetav / csv / geojson / wfs / wms. Links the
  /jaamurre-ja-talvine-navigatsioon and /jaateed topic pages.
* https://transpordiamet.ee/jaamurre-ja-talvine-navigatsioon ->
  HTTP 200, 226 301 B, main content ~6.1k visible chars. Rich HUMAN
  icebreaking guide: jäämur x37 (fleet Tarmo / EVA-316 / Botnica,
  Gulf of Finland work area, served ports incl. Tallinna/Kopli/Muuga
  bays), 0 for avaandmed / API / andmestik / masinloetav / csv /
  json / geojson / wfs / rss / kalender / graafik. The dated
  notices are PDF käskkirjad (e.g. "Nõuete kehtestamine jäämurdja
  poolt teenindatavatele laevadele Kopli, Tallinna ja Muuga lahe
  sadamates (2026 veeb)", "Jäämurdetööde alustamine/lõpetamine ..."),
  each a month-year-parenthetical human publication — never a
  comparable machine vintage. The only machine pointer in main is
  the site-wide rss-feeds/rss.xml (generic news, never a dated
  icebreaking calendar).
* https://transpordiamet.ee/jaateed -> HTTP 200, 205 446 B
  (~11.1k visible chars). Ice-road page (jääte x26), not the
  Tallinn Bay icebreaking leg; same 0 for every machine format.
* https://andmed.eesti.ee/dataset?q=jäämurre -> HTTP 200,
  75 497 B, title "Teabevärav". JS app shell, 12 visible
  characters, no server-rendered results (same shell as the
  #264/#277/#284 checks) — no trivially pollable national-portal
  icebreaking dataset.
* https://baltice.org/ (the page's "Seotud viited" related link)
  -> HTTP 301 (232 B, polite stop at the redirect, not followed).
So the single dim returns None for EVERY input including missing
origin: an icebreaking calendar painted from month-parenthetical
PDF filenames — or from one generic RSS headline — would be fake
precision (OTA PR #131 precedent), and parsing/driving those human
publications is exactly the scraping this repo refuses (AGENTS.md
section 5; same stop-at-human-HTML precedent as komun #290, Elron
#284, sadam #298). Reasons say "hinnang" (estimate) and "EI OLE"
and point at the concrete buyer-side checks (Transpordiamet
jäämurre page + sadamagraafik, jäähooaja kohapealne kuuletuvus
Tallinna lahe ääres) — never a faked calendar score.

SIBLING OVERLAP (read first, not edited): the other P4-055 legs
stay where they live and are named here, never re-scored — the
Sadam foghorn/icebreaker timetable slice (dims_p4_sadam
dim_sadam_timetable, NULL: human filter-form HTML, no feed), the
EANS harbour/air notice slice (dims_p4_eans
dim_harbour_air_calendar, SCORED calendar on fixtures), the
Männiku weekend-pops slice (dims_p4_kvagi
dim_manniku_weekend_calendar, SCORED calendar on fixtures), the
Elron raudteemüra-ööaknad slice (dims_p4_elron
dim_elron_night_maintenance, NULL: direction PDFs / human news)
and the kommunaalamet mürakaebuste-validation slice
(dims_p4_komun dim_schedulable_noise_calendar, NULL: no complaint
register). This module owns ONLY the Veeteede Amet Tallinn Bay
icebreaking leg (parameters4.md source (4)), which has no
verified keyless feed — hence NULL.

Style mirrors services/scoring/dims_p4_pria.py (#299, the
dated-negative single-param precedent): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for
icebreaking-season exposure, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #311 states the remaining
  0 params using this source are covered by a follow-up created
  after this demo — with a dated-negative demo there is no
  ingestion to extend, so there is nothing to split out. One dim,
  one module, three new files, no shared-file edits.
* No ingestion to cache and no TTL to state beyond this one-off
  check (pria #299 / opencellid #269 precedent): re-probe yearly
  each autumn before the ice season, or sooner if Transpordiamet
  (or andmed.eesti.ee / baltice.org) publishes a pollable dated
  icebreaking feed. The PDF parentheticals ("2026 veeb") are
  month grain for humans, not joinable ISO dates — recorded as
  the reason parsing stops, not as a vintage to transcribe by
  hand (hand-transcribing a season of PDFs would be harvesting
  human publications, not polling a feed).
* The check stopped at storefront/page level on purpose: no PDF
  parsing, no RSS driving, no Teabevärav JS-app driving, no
  baltice.org redirect chasing. Driving a news feed or a PDF set
  notice-by-notice would be scraping human publications, not
  polling a feed — exactly what this repo refuses (AGENTS.md
  section 5; tervise #289 precedent).
* Honest future shape (stated, not scored): calendar dim over
  joined dated Tallinn Bay icebreaking notices (flat exposure
  while a dated notice is in effect, e.g. the sibling 45 band;
  2 km Tallinn Bay propagation gate, membership never gradient;
  never 0/100 on this leg alone — an active season hints at
  winter-night rumble on the bay edge, never a guarantee).
  Today every reason says EI OLE and names the topic-page +
  Teabevärav gap plus the jäähooaja-kuulatlus checks.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-055: documented no-map Veeteede icebreaking-calendar NULL (OTA PR
# #131 precedent). Tallinn Bay icebreaking-season exposure needs a
# dated keyless notice feed — the topic page publishes month-
# parenthetical PDF käskkirjad for humans and the Teabevärav
# catalogue is a JS shell with no server-rendered dataset — so the
# scorer reports the gap with the concrete buyer-side checks
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_jaamurde_calendar(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-055: NULL — Veeteede jäämurdekalender on sulgemata voog."""
    return None, ("Tallinna lahe jäämurdehooaja müra-hinnangut pole (EI OLE "
                  "Veeteede jäämurdeteadete masinkalendrit): veeteedeamet.ee "
                  "suunab Transpordiametisse (kontrollitud 2026-09-13) ja "
                  "transpordiamet.ee/jaamurre-ja-talvine-navigatsioon on "
                  "inimloetav teemaleht, mille dated teated on kuu-"
                  "täpsusega PDF-käskkirjad (nt Kopli, Tallinna ja Muuga "
                  "lahe sadamate 2026 veeb-nõuded), mitte võtmeta CSV/API; "
                  "Teabevärava kataloog on JS-kest ilma serveris renditud "
                  "jäämurde-andmestikuta ja baltice.org on uudiseviide, "
                  "mitte liidestus — kuula jäähooajal kohapeal Tallinna "
                  "lahe ääres ning kontrolli sadamagraafikut ts.ee-st; "
                  "Sadam-leg dims_p4_sadam'is (dim_sadam_timetable), "
                  "EANS-leg dims_p4_eans'is (dim_harbour_air_calendar), "
                  "Männiku-leg dims_p4_kvagi's "
                  "(dim_manniku_weekend_calendar), raudtee-ööaknad "
                  "dims_p4_elron'is (dim_elron_night_maintenance) ja "
                  "mürakaebuste-validatsioon dims_p4_komun'is "
                  "(dim_schedulable_noise_calendar), ära feigi")


P4_VEETEEDE_DIMS = (
    ("jaamurde_calendar", "P4-055", dim_jaamurde_calendar),
)


def score_p4_veeteede(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 Veeteede dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_VEETEEDE_DIMS). The value
    is None by design — unverified icebreaking-notice feed, never a
    faked calendar score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_VEETEEDE_DIMS}
