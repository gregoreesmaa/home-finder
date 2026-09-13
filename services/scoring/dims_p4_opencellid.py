"""P4 OpenCellID mast-density dims (issue #269, single-param demo, no coverage issue).

Demo (#269): OpenCellID ingestion for P4-009 end-to-end in Tallinn —
polite, cached, TTL-stated pulls of the Tallinn mast-density slice
plus the per-address join. Single param: P4-009 Power/internet
reliability at address, OpenCellID slice (source (6), batch 1).
Honest shape when a feed lands: coarse raster hinnang, never
per-mast precision.

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #269): OpenCellID's Tallinn mast-density bulk pull needs an API
key, so there is no anonymous feed to poll. Polite evidence, 4
served requests total (single GETs with a labelled one-off
user-agent, headers + visible-text keyword scope read only, no
scraping, no auth, no token used — the checkout-root token was
never read, printed, or sent), raw bodies cached at
/tmp/hf-opencellid-probe/ (TTL: one-off check, kept for the PR
record, never committed):
* https://opencellid.org/ -> HTTP 200, 13932 bytes, title
  "OpenCelliD - Largest Open Database of Cell Towers &
  Geolocation - by Unwired Labs". Community-built cell-tower
  database (55M+ cells, GSM/CDMA/UMTS/LTE/5G NR); the landing
  funnels to "Query the API" and "Download the dataset", both
  gated (see below).
* https://docs.opencellid.org/docs/api/overview -> HTTP 200, 67656
  bytes, title "API overview | OpenCellID". Verbatim: "Most
  operations require an API key, supplied as key". Read
  operations: Get a cell position (/cell/get), List cells in an
  area (/cell/getInArea), Count cells in an area
  (/cell/getInAreaSize). Data under CC BY-SA 4.0 with attribution.
* https://opencellid.org/downloads.php -> HTTP 200, 7319 bytes,
  title "Data Downloads - OpenCelliD ...". Verbatim: "Enter your
  API access token to see download links." Country/worldwide CSV
  exports (last-18-months window) need the token-gated account.
* https://opencellid.org/cell/getInAreaSize?BBOX=59.35,24.55,59.50,24.95&format=json
  (one anonymous Tallinn-bbox count, no key) -> HTTP 401, 40
  bytes: {"error":"API Key not known: ","code":2}. The exact bulk
  call this demo would poll politely refuses anonymously.
So the single dim returns None for EVERY input including missing
origin: a mast-density raster painted without the keyed bulk (or
from one anonymous cell) would be fake precision (OTA PR #131
precedent). Reasons say "hinnang" (estimate) and "EI OLE" and
point at the concrete buyer-side checks (TTJA netikaart +
Telia/Elisa/Tele2 levikaardid + Ookla avaandmed) — never a faked
per-address score.

SIBLING OVERLAP (read first, not edited): the other P4-009 slices
stay where they live and are named here, never re-scored — the
Elektrilevi feeder-SAIDI slice (dims_p4_elektrilevi
dim_power_reliability, NULL: unpublished DSO feed), the Elering
national-system slice (dims_p4_elering dim_system_adequacy, NULL:
national series, no feeder signal), and the G10 OSM
confirmed-telecom-mast proximity proxy (dims_group10c
dim_internet, SCORED proxy). The TTJA/Ookla broadband slices are
their own demos. This module owns ONLY the OpenCellID
mast-density leg (Tallinn BBOX count/area bulk), which is
key-gated — hence NULL. Consequence for #230: the B10C mobile
cover-kind discs have no open OpenCellID raster to consume, so G10
mobile stays on the OSM proxy until the key story changes.

Style mirrors services/scoring/dims_p4_rik.py (#252): the scorer
is pure and offline-tested — (origin, pois) ->
(Optional[int 0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for key-gated mast density, so there is
nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: #269 states the remaining
  0 params using this source are covered by a follow-up that is
  only created after this demo — with a dated-negative demo there
  is no ingestion to extend, so there is nothing to split out.
  One dim, one module, three new files, no shared-file edits.
* No ingestion to cache and no TTL to state beyond this one-off
  check (rik #252 precedent): re-probe yearly, or sooner if the
  API overview drops the key requirement or an anonymous bulk
  appears. A newly opened anonymous bulk flips the verdict
  without re-probing deeper than the overview + downloads pages
  plus one anonymous area-count.
* The key was deliberately never used: the checkout-root token
  was never read, and no keyed request was sent. Spending a live
  key from CI/ingestion would bake a secret into the polite-pull
  path this repo refuses (AGENTS.md section 5: public repo, no
  secrets), and one anonymous cell says nothing about Tallinn
  density — the honest bulk shape (BBOX count/area over Tallinn)
  is exactly the call that 401s.
* Honest future shape (stated, not scored): coarse Tallinn
  raster hinnang off BBOX counts (mast-density bands, weak-good
  capped like the scored cousins — density hints at redundancy,
  never a guarantee; never 100 on this leg alone, never 0 on
  this leg alone). OpenCellID markers are estimated cell
  locations, not confirmed tower sites, so per-mast precision
  stays unscored even then. Today every reason says EI OLE and
  names the netikaart + levikaardid + Ookla checks.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-009: documented no-map OpenCellID key-gated NULL (OTA PR #131
# precedent). Tallinn mast density (BBOX count/area bulk) needs an API
# key — the anonymous area-count 401s and CSV downloads need an
# access token — so the scorer reports the gap with the concrete
# buyer-side checks instead of a faked number.
# ---------------------------------------------------------------------------

def dim_mast_density(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-009: NULL — OpenCellID Tallinna masti-tihedus on võtmega voog."""
    return None, ("Mobiilimasti tihedus OpenCellID-st (Tallinna jäme "
                  "raster-hinnang, nõrk-hea laega tulevikukuju) on ilma "
                  "võtmeta kättesaamatu hinnang (EI OLE avatud "
                  "hulgiliidest): Tallinna BBOX-loendus ilma võtmeta "
                  "vastab HTTP 401 'API Key not known' ja "
                  "CSV-allalaadimised nõuavad ligipääsu-tokenit — "
                  "puhverdatavat avatud voogu pole, kontrolli aadressi "
                  "internetti TTJA netikaardilt ja Telia/Elisa/Tele2 "
                  "levikaartidelt ning kiirust Ookla avaandmetest, vaata "
                  "kinnitatud-sidemasti legi dims_group10c-st "
                  "(dim_internet), fiidri-legi dims_p4_elektrilevi-st "
                  "(dim_power_reliability) ja süsteemi-legi "
                  "dims_p4_elering-ist (dim_system_adequacy), ära feigi")


P4_OPENCELLID_DIMS = (
    ("mast_density", "P4-009", dim_mast_density),
)


def score_p4_opencellid(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 OpenCellID dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_OPENCELLID_DIMS). The
    value is None by design — key-gated mast-density bulk, never a
    faked per-address score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_OPENCELLID_DIMS}
