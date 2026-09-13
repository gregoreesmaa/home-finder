"""P4 kohtud dim (issue #317 demo only): Kohtute infosüsteem verdict.

Demo (#317): the Kohtute infosüsteem source via P4-020 Enforcement
source (5) "kohtute infosüsteem (published decisions,
property/developer filter)" end-to-end in Tallinn - the published-
decisions leg (per-entity property/developer filter over court
decisions). Single-param demo: P4-020 is the only param naming this
source (parameters4.md mentions "kohtute infosüsteem" exactly once),
so there is no coverage follow-up issue; P4-020's sibling legs are
already scored where they live (see SIBLING OVERLAP).

OPENNESS VERDICT (checked 2026-09-13, dated negative keeps verdict
per #317: no open per-entity machine feed, so the dim stays NULL).
Polite evidence, exactly 1 request with a labelled one-off
user-agent `home-finder kohtud openness-check #317 (one-off, single
GET, no retry; contact via GitHub home-finder)`, `--max-time 25`,
headers + visible-text scope read only (no decision download, no
auth, no account creation), raw body at /tmp/hf-kohtud-body.html
(one-off PR record, never committed):
* GET https://www.kohus.ee/ -> HTTP 200 (46633 bytes, Cloudflare-
  fronted RIK/Drupal portal, content-language et). Visible text
  (~5.4k chars) links published decisions to the browser search UI:
  "Kohtulahendid" (6 hits), "Otsi"/"otsing" (2 hits) - href targets
  are https://www.riigiteataja.ee/et/otsing/kohtulahendid (Riigi
  Teataja decision search) and https://etoimik.rik.ee/ (authenticated
  e-toimik case-file system).
* Keyword sweep of the same visible text: avaandmed / API / X-tee /
  X-Road / allalaad / REST / masinloetav - all absent. No open-data
  page, no developer portal, no X-tee service, no bulk download, and
  no per-property/per-developer filter feed advertised.

So the dim returns None for EVERY input including missing origin:
a per-entity property/developer filter needs a machine-readable
decisions feed that does not exist openly, and painting an
enforcement tint from a one-off hand-read of the portal landing page
- which carries no case data at all - would be fake precision (OTA
PR #131 precedent). Driving the Riigi Teataja search UI or e-toimik
session flows, or reading decisions to join parties to listings,
would mean handling case-level personal data (parties to
proceedings) - exactly what this repo refuses (AGENTS.md section 5:
no personal data; per #317: no scraping or storing of personal
data). The reason says "hinnang" (estimate) and "EI OLE" and points
at the concrete buyer-side checks (Ametlikud Teadaanded
pankroti-/taiteteated, notarikontroll, KÜ/omaniku päring) - never a
faked enforcement flag.

SIBLING OVERLAP (read first, not edited): the P4-020 scored legs
already live where they belong - this module owns ONLY the Kohtute
infosüsteem published-decisions leg and never re-scores them:
* AT pankrot/taitemenetlus slice - dims_p4_ata dim_enforcement
  (key enforcement, cap 75).
* Kohtutaiturite register slice - dims_p4_taitur dim_enforcement
  (key enforcement, 15/40/70 bands).
* e-Ariregister maksehaired/aruandevolad slice - dims_p4_arireg
  dim_enforcement_arireg (key enforcement_arireg).
* Maa-amet kitsendused (arest/keelumärge) slice -
  dims_p4_maa_kataster dim_enforcement (key enforcement).
* Creditinfo/Krediidiinfo developer-score slice -
  dims_p4_creditinfo dim_enforcement_ci (key enforcement_ci, NULL).

Style mirrors services/scoring/dims_p4_s2.py (#305): the scorer is
pure and offline-tested - (origin, pois) -> (Optional[int 0..100],
Estonian reason). Network lives only in livability.fetch_pois; this
module adds no network calls, no Overpass fragment, and no tag
mapping: there is no honest snapshot tag to query for a closed
court-decisions per-entity feed, so there is nothing for the live
path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152). In
practice this verdict module needs no helpers at all - the single
dim reports its missing decisions leg directly.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Single-param demo, no coverage issue: "kohtute infosüsteem"
  appears exactly once in parameters4.md (P4-020 source (5)), so one
  module, one test file, one verdict note - no second file importing
  a pipeline that does not exist.
* The check stopped at portal-landing level on purpose: one GET
  showing the decisions path is the browser search UI plus the
  authenticated e-toimik carries the verdict for the source family -
  per-entity joins all need the same non-existent machine feed by
  construction, and enumerating search endpoints or driving session
  flows would be the personal-data scraping this repo refuses
  (AGENTS.md section 5).
* (origin, pois) signature instead of a join signature: with the
  dated-negative verdict there is no ingestion and hence no join
  input - the dim reports the decisions-feed gap for any listing,
  the same shape as the Sentinel-2 dated-negative NULL (#305).

Integration (deliberately NOT done here): this dim needs no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change - existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-020: documented no-map kohtute-infosüsteemi-leg NULL (OTA PR #131
# precedent). Published court decisions have no open per-entity
# (property/developer-filtered) machine feed (2026-09-13
# dated-negative verdict above); the scorer reports the gap with
# concrete buyer-side checks instead of a faked enforcement flag.
# ---------------------------------------------------------------------------

def dim_enforcement_kohtud(origin: Optional[Tuple[float, float]],
                           pois: Optional[List[dict]]) -> Score:
    """P4-020: NULL - court decisions have no open per-entity feed (no map)."""
    return None, ("Kohtulahendite hinnang eeldaks Kohtute infosüsteemi "
                  "avaldatud lahendite masinloetavat päringut kinnistu või "
                  "arendaja filtriga (EI OLE avaandmeid: kohus.ee-portaal "
                  "viitab vaid Riigi Teataja brauseriotsingule ja autentitud "
                  "e-toimikule, kontrollitud 2026-09-13 - avalikku API-t, "
                  "X-tee-teenust ega hulgi-allalaadimist pole ning lahendite "
                  "koosseis on isikuandmetega menetlusteave, mida ei kraapita "
                  "ega salvestata) - kontrolli arendajat ja kinnistut "
                  "Ametlike Teadaannete pankroti- ja täiteteadetest ning "
                  "notarikontrollist (notar.ee), kohtuvaidluse kahtluse "
                  "korral küsi KÜ-lt või omanikult; kaardikiht puudub - "
                  "ära feigi")


P4_KOHTUD_DIMS = (
    ("enforcement_kohtud", "P4-020", dim_enforcement_kohtud),
)


def score_p4_kohtud(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 kohtud dim for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_KOHTUD_DIMS). The value
    is None by design - no open per-entity decisions feed, never a
    faked enforcement flag."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_KOHTUD_DIMS}
