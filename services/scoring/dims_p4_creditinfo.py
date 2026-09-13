"""P4 Creditinfo/Krediidiinfo per-entity dimensions (issues #259 demo + #340 coverage).

Params (this agent only — demo + its coverage follow-up share one source):
* P4-007 KÜ loan + remondifond + kütte €/m², Creditinfo slice: KÜ
  maksehäired cross-check (batch 1, demo in #259)
* P4-020 Enforcement, Creditinfo slice: Tallinn developer scores
  (batch 2, coverage in #340)

HONESTY (AGENTS.md section 7.2): the Creditinfo/Krediidiinfo source
is a closed commercial feed — KÜ maksehäired and developer
credit scores live behind the account-gated "Minu Creditinfo"
self-service and contract-gated B2B products (sales department,
lender KYC/debt-management solutions). The openness check of
2026-09-13 (see docs/p4_creditinfo.md) found no public feed, no
open-data page, no developer portal, and no X-tee/X-Road service
for either slice: krediidiinfo.ee 301-redirects to creditinfo.ee,
whose landing page sells reports and self-service access. Pulling
the data anyway would mean creating accounts and driving
session-gated flows — exactly the scraping this repo refuses
(AGENTS.md section 5). So both dims return None for EVERY input
including missing origin: a district band painted from a one-off
hand-check would be fake precision (OTA PR #131 precedent).
Reasons say "hinnang" (estimate) and "EI OLE" and point at the
concrete buyer-side check (KÜ majandusaasta aruanne from
e-Äriregister + direct KÜ enquiry, Ametlikud Teadaanded +
notarikontroll) — never a faked area score.

Style mirrors services/scoring/livability.py and sibling batch
dims_group20a.py (#212): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, no Overpass fragment, and no tag mapping: there is no honest
snapshot tag to query for a closed bureau feed's per-entity
scores, so there is nothing for the live path to fetch.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage share ONE PR and ONE module because the coverage
  body (#340) states it extends the demo ingestion (#259): with the
  demo verdict dated-negative, there is no ingestion to extend, so
  the coverage param lands in the same verdict module rather than a
  second file importing a pipeline that does not exist (same
  precedent as the comapps #302+#371 PR).
* P4-007 stays NULL even though an open cousin exists for the MAIN
  slice: e-Äriregister KÜ majandusaasta aruanded (XBRL bulk) carry
  the loan/remondifond/küte fields themselves (parameters4.md
  source 1). Creditinfo maksehäired were only ever the cross-check
  slice (source 3) — and absence of maksehäired is not evidence of
  a healthy remondifond. Scoring the cousin here would claim the
  full param on a partial signal; the Äriregister bulk wiring
  belongs to a future ingestion of its own, recorded in
  docs/p4_creditinfo.md as the overturn path.
* P4-020 appears twice on purpose with disjoint slices:
  dims_p4_ata scores the open Ametlikud Teadaanded notice slice
  (cap 75); this module scores the closed Creditinfo
  developer-score slice (NULL). Neither claims the full param;
  kohtutäitur register and Maa-amet kitsendused stay unjoined in
  both.
* The openness check stopped at landing-page level on purpose —
  two HEADs (both 301 to creditinfo.ee) plus one GET with a
  labelled one-off user-agent, headers plus a keyword scope read.
  No endpoint enumeration, no account creation, no session flows:
  deeper probing is exactly the scraping this repo refuses
  (AGENTS.md section 5).

Integration (deliberately NOT done here): these dims need no
livability.OVERPASS_QUERY / livability._POI_KIND extension (no
snapshot tags consumed) and no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-007/P4-020: documented no-map commercial-feed NULLs (OTA PR #131
# precedent). The bureau feeds are account/contract-gated with no public
# API; the scorer reports the gap with a concrete buyer-side check
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_ku_loan_fund(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-007: NULL — KÜ loan/remondifond/küte needs the KÜ aruanne (no map)."""
    return None, ("KÜ laen, remondifond ja kütte €/m² on ühistu aruande "
                  "hinnang (EI OLE avaandmeid): Creditinfo/Krediidiinfo "
                  "KÜ maksehäired on lepinguväravaga kommertsteenus, "
                  "avalikku voogu pole — küsi KÜ-lt majandusaasta aruanne "
                  "ja remondifondi otsused ning kontrolli aruanne "
                  "e-Äriregistrist, ära feigi ala skoori")


def dim_enforcement_ci(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-020: NULL — developer credit scores are a gated bureau feed."""
    return None, ("Arendaja krediidiskoor on suletud kommertstee- "
                  "nuse hinnang (EI OLE avaandmeid): Creditinfo/"
                  "Krediidiinfo skoorid on konto- või lepinguväravaga, "
                  "avalikku voogu pole — kontrolli arendajat Ametlike "
                  "Teadaannete pankroti-/täiteteadetest ja notarikontrollist "
                  "(notar.ee), kaardikiht puudub")


P4_CREDITINFO_DIMS = (
    ("ku_loan_fund", "P4-007", dim_ku_loan_fund),
    ("enforcement_ci", "P4-020", dim_enforcement_ci),
)


def score_p4_creditinfo(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both P4 creditinfo dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_CREDITINFO_DIMS). Every value
    is None by design — closed commercial feed, never a faked score."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_CREDITINFO_DIMS}
