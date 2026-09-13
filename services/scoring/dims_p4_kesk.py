"""P4 kesk dims (issues #291 demo + #364 coverage).

Params (this module only — demo + its coverage follow-up share one source):
* P4-017 Drinking-water quality + sewer reality, Keskkonnaamet leg:
  vee-erikasutusload Tallinn (batch 2, demo in #291)
* P4-033 Seasonal nuisance calendar, Keskkonnaamet leg: jahiteated
  Tallinn fringe (batch 3, coverage in #364)
* P4-054 Quarry blast + truck season, Keskkonnaamet leg:
  kaevandamisload + lohkamiste ajagraafik (batch 5, coverage in #364)
* P4-059 Wood-burning restriction zones, Keskkonnaamet leg:
  tahkekutte piirangualad notices (batch 5, coverage in #364)

OPENNESS VERDICT (checked 2026-09-13, dated partial keeps verdict per
#291: the national feed EXISTS and is pollable, but its schema serves
none of the four legs, so all four dims stay NULL). Polite evidence, 8
requests total with a labelled one-off user-agent, `--max-time 20/30`,
single attempts, 1-2 s pacing, raw bodies cached at /tmp/kesk-open/
(one-off PR record, never committed):
* https://keskkonnaamet.ee/ -> HTTP 200, 182 674 B, ~9 960 visible
  chars. Sweep 0 for avaandmed / open data / API / masinloetav /
  andmestik. Permits live behind named e-service registers (KOTKAS
  application submission, VEKA borehole search, Metsaregister, FOKA,
  SPIM — the last needs a prior access application), never a bulk
  feed on the storefront itself.
* https://andmed.eesti.ee/dataset?q=keskkonnaamet -> HTTP 200,
  75 497 B, 10 visible characters ("Teabevärav" JS shell) — no
  server-rendered national-portal dataset (same shell as the
  #264/#277/#284 checks).
* https://kotkas.envir.ee/ (KOTKAS permit register) -> HTTP 200,
  28 452 B. JS-required app (AVE v2.13.64), "Sisene" login for
  self-service, but the public /opendata page IS linked and keyless.
* https://kotkas.envir.ee/opendata?represented_id= -> HTTP 200,
  26 570 B. Bulk downloads: Taotlused (.json 10.2 MB), Keskkonnaload
  (.json 6.1 MB), Registreeringud (.json 2.6 MB), Dokumendid (.json
  30.7 MB), Seirearuanded (.json 22.6 MB), plus 4 .xlsx registers.
  No licence stated on the page (not claimed here).
* permits.json (HEAD 200, application/json, 6 385 555 B; full body
  pulled once — the server ignores Range): a list of 13 120 records
  with keys permit_number/object_name/object_location/owners_name/
  permit_type/permit_status/valid_from_date/valid_to_date/version_*.
  permit_type is only KL (12 338) / KKL (782) — NO water-abstraction,
  mining, or air subtype. Geography is linnaosa free text
  ("Lasnamäe linnaosa, Tallinn, Harju maakond"; 503 Kehtiv Tallinn
  rows), no coordinates, no parcel link. Status Kehtiv 4 227 /
  Arhiveeritud 8 892.
* registrations.json (200, 2 734 673 B): 5 320 records, same keys;
  permit_type is only RE.JA (3 769) / RE.VT (981) / PHRR (550) /
  OLRR (20) — waste/dredging-type registrations, no vee-erikasutus,
  hunting, mining, or solid-fuel subtype.
* object_name free-text scan (observed, NOT used): "vee" hits 77
  Kehtiv rows (e.g. offshore-wind meretuulepargi vee erikasutus,
  mine-dewatering liigvee umberjuhtimine), "puurkaev" 13,
  "kaevand" 9, "paekivi" 1 (Vao quarry remediation). Keyword NLP
  over these names would be fake precision: "vee erikasutus"
  covers sea use, dredging and dewatering — never drinking-water
  quality or sewer reality — and names carry no dates or
  coordinates for a blast timetable.
* https://keskkonnaamet.ee/elusloodus-looduskaitse/jahipidamine/
  kuttimisandmed -> HTTP 200, 192 575 B human HTML. Hunting figures
  live as human pages; no hunting-notice dataset appears in the
  KOTKAS avaandmed list, and no blast-schedule or solid-fuel-zone
  dataset appears there either.
So all four dims return None for EVERY input including missing
origin: a linnaosa permit-count band would score "paperwork near
you", not water/sewer reality, hunting season, blast Tuesdays, or
stove law (OTA PR #131 precedent). Reasons say "hinnang"
(estimate) and "EI OLE" and point at the concrete buyer-side check
(Tallinna Vesi UVK kaart, Terviseamet seire, jahiteated, Maa-amet
maardlad, Tallinna Keskkonnaameti teated, EHR kutte liik) — never
a faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_p4_elron.py (#284/#358): every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100], Estonian
reason). Network lives only in livability.fetch_pois; this module
adds no network calls, no Overpass fragment, and no tag mapping:
there is no honest snapshot tag to query for a permit subtype the
feed does not publish, so there is nothing for the live path to
fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#364) states it extends the demoed ingestion (#291): the
  ingestion exists (KOTKAS avaandmed) but serves no leg, so the
  three coverage slices land in the same verdict module rather
  than a second file importing a pipeline none of the four dims
  can consume (same precedent as Elron #284+#358, TLT #277+#351,
  RB #281+#355).
* NO fetch/parse helpers are staged even though the feed is open:
  unused ingestion would be fake progress (AGENTS.md 7.2). The
  exact download URLs, schema, and counts above plus
  docs/p4_kesk.md give the overturn PR everything needed to build
  the polite cached pull when a leg becomes servable.
* Sibling legs stay scored where they live (future source issues):
  the P4-017 Terviseamet/Tallinna Vesi/EHR legs, the P4-033
  Sadam/event/Kaitsevae legs, the P4-054 Maa-amet maardlate leg,
  and the P4-059 Tallinna Keskkonnaamet/EHR legs are different
  sources' readings, not this verdict's kesk legs — re-scoring
  those cousins here would claim the full param on a partial
  signal (same split-slice precedent as P4-020: ATA notices in
  dims_p4_ata, bureau scores NULL in dims_p4_creditinfo).
* The openness check stopped at page + schema level on purpose —
  no subscription-flow driving, no JS-app scraping, no KOTKAS
  self-service login. Parsing human hunting pages would be
  scraping publications, not polling a feed — exactly the
  scraping this repo refuses (AGENTS.md section 5).
* TTL: one-off check 2026-09-13 (no ingestion cached, nothing
  consumed). Re-check annually or on a KOTKAS schema change
  (new subtype, coordinates, or a hunting/blast/solid-fuel
  dataset); the page carries no refresh date (app internal
  version 2026-09-02 observed at check time).

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-017/P4-033/P4-054/P4-059: documented no-map kesk-leg NULLs (OTA PR
# #131 precedent). KOTKAS avaandmed publishes keyless bulk JSON, but the
# schema carries no water-abstraction / hunting-notice / mining-permit /
# blast-schedule / solid-fuel subtype and no parcel geography; each
# scorer reports the gap with a concrete buyer-side check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_water_permit_reality(origin: Optional[Tuple[float, float]],
                             pois: Optional[List[dict]]) -> Score:
    """P4-017: NULL — vee-erikasutusluba leg needs the subtype (no map)."""
    return None, ("Keskkonnaameti vee-erikasutuslubade joogivee-hinnang "
                  "(EI OLE eristatav andmestik): KOTKAS avaandmete load "
                  "on alamtüüpideta KL/KKL-kirjed linnaosa vabatekstiga, "
                  "nime-märksõnad (meretuulepark, liigvesi) ei mõõda "
                  "joogivett ega kanalisatsiooni — kontrolli Tallinna "
                  "Vee ÜVK kaarti (tsentraalne vs puurkaev/omapuhasti), "
                  "Terviseameti joogivee seiret ja EHR veevarustuse "
                  "liiki, ära feigi")


def dim_hunting_notices(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-033: NULL — jahiteated calendar needs the dataset (no map)."""
    return None, ("Keskkonnaameti jahiteadete hooajakalender on "
                  "mürahinnang (EI OLE masinloetavat teadete-voogu): "
                  "küttimisandmete leht on inimloetav HTML ja KOTKAS "
                  "avaandmetes jahiteadete andmestikku pole — kontrolli "
                  "jahipidamise teateid keskkonnaamet.ee-st ja Kaitseväe "
                  "õppuste teateid, ära feigi")


def dim_quarry_blast(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-054: NULL — blast timetable needs subtype + dates (no map)."""
    return None, ("Keskkonnaameti kaevandamisloa lõhkamisgraafik on "
                  "mürahinnang (EI OLE alamtüüpi, kuupäevi ega "
                  "koordinaate): load on KL/KKL-kirjed linnaosa "
                  "vabatekstiga, lõhkamiste ajagraafikut voog ei sisalda "
                  "— kontrolli Maa-ameti maardlate registrit "
                  "(Maardu/Harku paekivi), Tark Tee raskeveo infot ja "
                  "küsi teisipäeva-hommikust kohapeal, ära feigi")


def dim_woodburning_zones(origin: Optional[Tuple[float, float]],
                          pois: Optional[List[dict]]) -> Score:
    """P4-059: NULL — tahkekütte zones need the dataset (no map)."""
    return None, ("Tahkekütte piiranguala reegli-hinnang (EI OLE "
                  "masinloetavat tsoonikihti): KOTKAS avaandmetes "
                  "õhu/tahkekütte andmestikku pole — kontrolli Tallinna "
                  "Keskkonnaameti tahkekütte teateid, EHR kütte liiki "
                  "ja Päästeameti korstnateateid, ära feigi")


P4_KESK_DIMS = (
    ("kesk_water_permit", "P4-017", dim_water_permit_reality),
    ("kesk_hunting_notices", "P4-033", dim_hunting_notices),
    ("kesk_quarry_blast", "P4-054", dim_quarry_blast),
    ("kesk_woodburning_zones", "P4-059", dim_woodburning_zones),
)


def score_p4_kesk(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All four P4 kesk dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_KESK_DIMS). Every value
    is None by design — open feed, unservable legs, never a faked
    area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_KESK_DIMS}
