"""P4 TTJA consumer-complaints per-entity dim (issue #295 demo, single-param).

Params (this module only — the TTJA SLICE of the param; sibling
slices are owned elsewhere and untouched):
* P4-021 Developer + broker track record: the TTJA
  (Tarbijakaitse) kaebused Tallinn developers/brokers slice
  (source (2), batch 2, demo in #295). Disjoint from the EHR
  ehitaja-history slice, the own cross-portal broker-stats slice,
  the e-Äriregister company-facts slice, the Ametlikud
  Teadaanded developer-notice slice
  (dims_p4_ata.dim_developer_track, issues #254/#335), and the
  Maa-amet tehingud resale-performance slice (their own demos,
  not this source). This source feeds only P4-021, so there is
  no follow-up coverage issue.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #295): TTJA publishes no pollable per-entity complaint feed.
Polite evidence, 6 tiny requests total (single GETs with a
labelled one-off user-agent, headers + visible-text keyword scope
read only, no scraping, no auth, no form submissions, no XHR
probing, paced >= 3 s), raw bodies cached at /tmp/hf-ttjacons/
(TTL: one-off check, kept for the PR record, never committed):
* https://ttja.ee/ -> HTTP 200, 177990 bytes, title "Eraklient |
  Tarbijakaitse ja Tehnilise Järelevalve Amet" — agency portal
  reachable; visible-text sweep: must nimekiri 3x, kaebus 1x,
  while avaandmed / open data / masinloetav / X-tee / X-Road /
  andmestik / arendaja / developer / api all score 0 — no
  open-data page, no developer portal, no X-tee service
  advertised.
* https://ttja.ee/komisjoni-otsused ("Komisjoni otsused") ->
  HTTP 200, 187004 bytes — info page pointing decisions at the
  JVIS register below; no machine feed advertised (avaandmed /
  masinloetav / X-tee / andmestik all 0).
* https://jvis.ttja.ee/modules/tarbijavaidluskomisjoni-otsused/avalik
  ("Tarbijavaidluste komisjoni otsuste register | JVIS") ->
  HTTP 200, 18122 bytes — an 18 KB Axios/WeBase JS app shell
  with a search form (1 form, 3 server-rendered rows): decisions
  load through app-internal requests. Driving those internals
  for per-entity complaints would mean scraping map-app-style
  endpoints — exactly the scraping this repo refuses (AGENTS.md
  section 5, X-GIS precedent #266).
* https://jvis.ttja.ee/modules/tarbijavaidluskomisjoni-otsused/mustnimekiri
  ("Mustas nimekirjas olevad ettevõtted | JVIS") -> HTTP 200,
  193078 bytes — a server-rendered HTML table (144 company rows:
  Kaupleja name ONLY, no registry code; Otsuse nr; Nimekirjas
  alates date) with real-estate filters ("Kinnisasi - ostmine",
  "Kinnisasi - remont/ehitus") but NO export link (csv / xlsx /
  json / api / avaandmed all absent). Listed max 12 months until
  the trader complies. Polling it would mean scraping HTML
  tables, and a name-only join without registry codes is fuzzy
  matching — fake precision, not a per-entity join.
* https://andmed.eesti.ee/dataset?q=ttja -> HTTP 200 JS
  "Teabevärav" shell with zero server-rendered
  tarbijakaitse / kaebus / komisjon hits — no trivially
  pollable national-portal dataset.
So the dim returns None for EVERY input including missing
origin: a complaint band painted from a one-off hand-check, a
scraped HTML table, or a fuzzy name match would be fake
precision (OTA PR #131 precedent). Absence from the 12-month
must-nimekiri is not proof of a clean record either, so even a
penalty-only off-list score would bless gaps. The reason says
"hinnang" (estimate) and "EI OLE" and points at the concrete
buyer-side check (manual JVIS must-nimekiri + otsusteregister
lookup by company name) — never a faked entity score.

Style mirrors services/scoring/dims_p4_ttja_net.py (#266, the
closest sibling: same agency, same NULL-with-markers shape) and
dims_group20a.py (#212): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois;
this module adds no network calls, no Overpass fragment, and no
tag mapping: there is no honest snapshot tag to query for a
seller's complaint record, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param module with no ingestion function: unlike the
  Konkurentsiamet sibling (#262, downloadable XLSX to parse),
  there is no open TTJA file or feed to fetch, parse, or cache
  — the only artefact of the demo is this dated-negative
  verdict plus its doc note. Fetching nothing is the polite
  choice, stated not hidden.
* P4-021 (TTJA slice) stays NULL even though the buyer CAN look
  a seller up by hand in JVIS: a manual name lookup is not a
  pollable join, the blacklist carries names without registry
  codes (fuzzy join = fake precision), and absence (12-month
  expiry, only non-complied decisions) is not a clean bill.
  The reason tells the buyer exactly where to click instead.
* No scored "complaint-count hinnang" off the HTML table: a
  count needs a stable per-entity series from an open layer —
  paginated HTML rows relabelled as data would be scraping,
  not ingestion (same rejected-steelman precedent as #266).

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-021 (TTJA slice): documented no-feed complaint-record NULL
# (OTA PR #131 precedent). Seller complaint decisions live in the
# interactive JVIS register and a name-only HTML blacklist with no
# public feed; the scorer reports the gap with the concrete
# buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_seller_complaint_record(origin: Optional[Tuple[float, float]],
                                pois: Optional[List[dict]]) -> Score:
    """P4-021: NULL — TTJA seller complaint record is register-only (no feed)."""
    return None, ("Müüja (arendaja/maakler) kaebustetaust on TTJA "
                  "tarbijavaidluste hinnang (EI OLE masinloetavat kaebustevoogu): "
                  "otsused elavad JVIS interaktiivses otsusteregistris ja must "
                  "nimekiri HTML-tabelina (ainult ärinimi, registrikoodita), avalik "
                  "päringuliides puudub — kontrolli müüja käsitsi JVIS mustast "
                  "nimekirjast ja otsusteregistrist ärinimega ning ära feigi "
                  "olematut tausta")


P4_TTJACONS_DIMS = (
    ("seller_complaint_record", "P4-021", dim_seller_complaint_record),
)


def score_p4_ttjacons(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 TTJA complaints dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_TTJACONS_DIMS). The
    value is None by design — interactive register only, never a
    faked per-entity score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_TTJACONS_DIMS}
