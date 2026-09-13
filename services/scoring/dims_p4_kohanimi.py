"""P4 Kohanimeregister guest-name per-listing dim (issue #313 demo, single-param).

Params (this module only — the KOHANIMEREGISTER slice of the param;
sibling slices are owned elsewhere and untouched):
* P4-049 Taxi/guest test: the Kohanimeregister (Maa- ja Ruumiamet
  AKS-Kohanimeregister, KNR) name-pronounceability slice
  (source (2), batch 4, demo in #313). Disjoint from the Ads/DSM
  findability-probe slice, the Tallinna guest-parking-rules slice,
  the TLT/Peatus.ee guest-arrival slice, the listing-photo
  entrance-tidiness slice (P4-022/P4-029 join), and the OSM
  entrance/wheelchair-tags slice (their own demos, not this
  source). This source feeds only P4-049, so there is no
  follow-up coverage issue.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #313): the register is openly SEARCHABLE but has no pollable
bulk feed — and its records are names, not guest-test scores. Polite
evidence, 5 single GETs total (labelled one-off user-agent, headers
+ visible-text scope read only, no scraping, no auth, no form
submissions, no XHR probing, paced >= 4 s, `--max-time 25`), raw
bodies cached at /tmp/hf-kohanimi-probe/ (TTL: one-off check, kept
for the PR record, never committed):
* https://geoportaal.maaamet.ee/ -> HTTP 200, 27567 bytes, title
  "Avaleht | Geoportaal | Maa- ja Ruumiamet" — portal reachable;
  advertises "Kohanimeregistri teenus (AKS) / Kohanimede otsing
  ning kuvamine kaardil" (search + display on map, not a feed).
* https://andmed.eesti.ee/dataset?q=kohanimi -> HTTP 200 JS
  "Teabevärav" shell with 12 visible chars and zero
  kohanimi hits — no trivially pollable national-portal dataset.
* https://geoportaal.maaamet.ee/est/teenused/kohanimeregistri-teenus-aks-p133.html
  ("Kohanimeregistri teenus (AKS)") -> HTTP 200, 33093 bytes:
  since 23.04.2025 the new AKS address/place-name system is live
  and KNR aggregates official + unofficial + former names for
  everyone; the public service "võimaldab otsida ... huvipakkuvaid
  kohanimesid" (search shows matching records), URL access needs a
  known KNR object ID (e.g. .../aks/name/detail/NO003313428), and
  the only machine path named anywhere is "KNR X-tee teenused"
  (authenticated X-Road, not open polling). Zero masinloetav /
  avaandmed / csv / rest / json mentions on the page.
* https://aks.geoportaal.ee/aks/search/placename ("Kohanimede
  otsing (AKS)") -> HTTP 200, 1571 bytes — a JS app shell titled
  "AKS" (5 visible chars, 0 forms, 0 export / csv / api /
  download hits): results load through app-internal requests.
  Driving those internals for per-listing names would mean
  scraping map-app-style endpoints — exactly the scraping this
  repo refuses (AGENTS.md section 5, X-GIS precedent #266).
* https://geoportaal.maaamet.ee/est/teenused/wms-wfs-wcs-teenused-p65.html
  -> HTTP 200, 55694 bytes: zero kohanimi mentions; the single
  KNR hit is the nav link to "KNR X-tee teenused" — no open KNR
  WFS layer advertised.
So the dim returns None for EVERY input including missing origin,
on two independent legs: (a) no pollable bulk feed (interactive
search + authenticated X-Road only), and (b) even pulled names
would not score the question — KNR records ARE names
(official/unofficial/former), while P4-049 asks whether a guest
can SAY and FIND the name (Õismäe vs Kadriorg guest test): grading
"Õismäe = hard" off the register would be a linguistic worth
judgement on a neighbourhood name and fake precision (OTA PR #131
precedent). The reason says "hinnang" (estimate) and "EI OLE" and
points at the concrete buyer-side check (say the address aloud to
a guest / send it to a taxi driver, Sat 19:00 parking + on-site
entrance look) — never a faked usability score.

Style mirrors services/scoring/dims_p4_ttjacons.py (#295, the
closest sibling: same single-param register-only NULL shape) and
dims_group20a.py (#212): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for a
listing's guest-pronounceability, so there is nothing for the
live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param module with no ingestion function: there is no open
  KNR file or feed to fetch, parse, or cache — the only artefact
  of the demo is this dated-negative verdict plus its doc note.
  Fetching nothing is the polite choice, stated not hidden.
* The dim stays NULL even though the buyer CAN hand-search a name
  in AKS: a manual lookup returns name RECORDS (incl. unofficial
  and former variants of the same place), not a pronounceability
  verdict, and picking which variant the guest hears is itself
  the test — a register join cannot run it for the buyer.
* No scored "diacritic-count hinnang" off name strings: counting
  õ-letters in "Õismäe" as difficulty would bless a heuristic as a
  guest verdict (same rejected-steelman precedent as #295's
  complaint-count off HTML rows).
* No worth judgement on names: grading a district's name
  "hard/foreign" from the register would score the AREA's
  identity, not the listing's usability — taste-match, never
  worth judgement (P4-043/P4-044 precedent).

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-049 (Kohanimeregister slice): documented no-feed guest-name NULL
# (OTA PR #131 precedent). The AKS register is interactively
# searchable but has no open bulk feed, and its records are names —
# not guest-pronounceability verdicts; the scorer reports the gap
# with the concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_guest_name_test(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """P4-049: NULL — guest-name test needs a guest, not a register (no map)."""
    return None, ("Külalise-nime (takso-)test on külalise hinnang (EI OLE "
                  "masinloetavat hääldusvoogu): AKS-Kohanimeregister annab "
                  "nimede kirjeid (ametlikud + mitteametlikud + endised), aga "
                  "otsing on interaktiivne (JS-rakendus, masintee ainult "
                  "X-tee kaudu) ning kirje ei ütle, kas külaline nime välja "
                  "hääldab — öelge aadress külalisele ette / saatke taksojuhile, "
                  "kontrollige laupäev 19.00 külalisparkimist ja vaadake sissepääs "
                  "kohapeal üle ning ära feigi olematut kasutatavusskoori")


P4_KOHANIMI_DIMS = (
    ("guest_name_test", "P4-049", dim_guest_name_test),
)


def score_p4_kohanimi(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 Kohanimeregister dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_KOHANIMI_DIMS). The
    value is None by design — searchable register only, and names
    are not guest verdicts, never a faked usability score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_KOHANIMI_DIMS}
