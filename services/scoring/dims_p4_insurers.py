"""P4 insurer-tariff-zone dim (issue #286 demo only): PZU/ERGO/If verdict.

Demo (#286): the Insurer tariff zones source via P4-015 Insurability
(flood/theft tariff zones) end-to-end in Tallinn - the insurer-tariff
leg (per-address flood/theft tariff band from the insurers' own zone
tables). Single-param demo: P4-015 is the only param naming this
source, so there is no coverage follow-up issue; P4-015's sibling
legs are already scored where they live (see SIBLING OVERLAP).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #286: insurer tariff zones are proprietary underwriting data with
no pollable bulk feed, so the dim stays NULL). Polite evidence, 2
served requests total (labelled one-off user-agent `home-finder
insurers openness-check #286 (one-off, single GETs, no retry; contact
via GitHub home-finder)`, `--max-time 25`, headers + visible-text/link
scope read only, no scraping, no auth, no quote-flow driving, no
service enumeration), raw bodies cached at /tmp/hf-insurers-probe/
(one-off PR record, never committed):
* GET https://www.if.ee/ -> HTTP 301 (0 bytes) to /eraklient
  (locale-split gate; transport note, not data).
* GET https://www.if.ee/eraklient (redirect target) -> HTTP 200
  (189542 bytes, ~5.5k visible chars, 15 script tags, title "If
  Kindlustus"). 181 links; sweep 0 for avaandmed / open data /
  andmestik / masinloetav / api / csv / geojson / wfs / download /
  arendaja / developer in visible text, and 0 machine-looking hrefs
  (no api/download/csv/json/geojson/wfs/andmestik/opendata/developer
  in any link target). Visible text 0 for tariif / kindlustustsoon /
  flood / uleujutus / varguse - the storefront advertises no zone
  table at all. The only insurance-transaction links are the
  per-customer quote/self-service flows (ekindlustus.if.ee policies,
  invoices, claims; /eraklient/kindlustused/* product pages) -
  authenticated individual quote flows, never a bulk zone feed.

So the dim returns None for EVERY input including missing origin:
tariff zones are the insurers' internal pricing input, and painting
a per-listing insurability score from a one-off hand-read of a
marketing storefront - or by driving the quote calculator with fake
customer profiles - would be fake precision (OTA PR #131 precedent)
and, for the calculator path, exactly the form-driving this repo
refuses (AGENTS.md section 5). The reason says "hinnang" (estimate)
and "EI OLE" and points at the concrete buyer-side checks (kodukindlustuse
pakkumine PZU/ERGO/If kalkulaatorist oma andmetega, omavastutuse ja
üleujutus-/varguse-välistuste võrdlus, KAUR/EELIS/PPA/paaste scored
cousins below) - never a faked tariff score.

SIBLING OVERLAP (read first, not edited): four P4-015 legs are
already scored where they live - this module owns ONLY the
insurer-tariff leg and never re-scores them:
* KAUR flood-zone slice - dims_p4_kaur dim_kindlustatavus_kaur
  (key kindlustatavus_kaur, 300 m zone join).
* EELIS flood/restriction slice - dims_p4_eelis
  dim_kindlustus_eelis (key kindlustus_eelis).
* PPA theft-count tertile slice - dims_p4_ppa
  dim_theft_tariff_proxy (key theft_tariff).
* Paasteamet fire-density slice - dims_p4_paaste dim_insurability
  (key insurability, linnaosa join + illiquidity flag on korge).

Style mirrors services/scoring/dims_p4_opmaps.py (#267): the scorer
is pure and offline-tested - (origin, pois) -> (Optional[int
0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls, no
Overpass fragment, and no tag mapping: there is no honest snapshot
tag to query for an insurer's internal tariff table, so there is
nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing insurer leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: P4-015 is the only param
  naming this source (parameters4.md P4-015 source (3) "insurer
  tariff zones Tallinn - PZU/ERGO/If (verify openness first, else
  illiquidity flag only)"), so one module, one test file, one
  verdict note - no second file importing a pipeline that does not
  exist. The "else illiquidity flag only" branch is already carried
  by the scored cousins (flood/restriction hits flag in KAUR/EELIS,
  korge flags in paaste/PPA) - there is no unflagged residual for
  this leg to own.
* Per-source slice, not the full param: the dim owns ONLY the
  insurer-tariff leg. The scored cousins above keep their owners,
  untouched; the reason names each cousin so the NULL stays
  actionable.
* The check stopped at storefront level on purpose: one insurer's
  storefront (If, the redirect-resolved market leader page) carries
  the verdict for the source family - tariff tables are proprietary
  everywhere by construction, and PZU/ERGO quote flows are the same
  per-customer calculators, not bulk feeds. Chasing PZU/ERGO shells
  or driving quote calculators would add bytes, not information,
  and calculator-driving is form-driving (AGENTS.md section 5).
* (origin, pois) signature instead of a join signature: with the
  dated-negative verdict there is no ingestion and hence no join
  input - the dim reports the tariff-table gap for any listing, the
  same shape as the opmaps/notar dated-negative NULLs.

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-015: documented no-map insurer-tariff-leg NULL (OTA PR #131
# precedent). PZU/ERGO/If tariff zones are internal underwriting data
# with no public bulk feed (2026-09-13 dated-negative verdict above);
# the scorer reports the gap with concrete buyer-side checks instead
# of a faked number.
# ---------------------------------------------------------------------------

def dim_insurer_tariff(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-015: NULL - insurer tariff zones are proprietary (no map)."""
    return None, ("Kindlustusseltsi tariifitsoon on hinnastamise-hinnang (EI OLE "
                  "masinloetavat tariifitabelit): PZU/ERGO/If tsoonid on "
                  "sisemine kindlustusmatemaatika, hulgi-allalaadimist ega "
                  "API-d pole (kontrollitud 2026-09-13, If esindusleht on "
                  "andmevoota pood koos individuaalse kalkulaatoriga) - küsi "
                  "kodukindlustuse pakkumine oma andmetega PZU/ERGO/If "
                  "kalkulaatorist ning võrdle omavastutust ja üleujutus- ja "
                  "varguse-välistusi; numbrilised P4-015-legid on juba "
                  "liidestatud (KAUR-üleujutus dims_p4_kaur-is "
                  "dim_kindlustatavus_kaur, EELIS-piirang dims_p4_eelis-is "
                  "dim_kindlustus_eelis, PPA-vargus dims_p4_ppa-s "
                  "dim_theft_tariff_proxy, pääste-tule-tihedus "
                  "dims_p4_paaste-s dim_insurability) - ära feigi")


P4_INSURERS_DIMS = (
    ("insurer_tariff", "P4-015", dim_insurer_tariff),
)


def score_p4_insurers(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 insurers dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_INSURERS_DIMS). The value
    is None by design - proprietary tariff table with no pollable feed,
    never a faked area score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_INSURERS_DIMS}
