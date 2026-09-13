"""Group 17 HOA-C per-listing dimension (issue #207).

Params (this agent only — sibling batches own disjoint sets):
* p3 HOA fees, monthly (ALWAYS None — per-KÜ EUR fact, do not fake)

HONESTY (AGENTS.md section 7.2): the e-Äriregister KÜ annual
reports (majandusaasta aruanne) and board fee decisions (juhatuse
tasumäär) are NOT in the 2026-09-12 snapshot, so the monthly fee
stays NULL with a KÜ-document reason. The reason names what is
missing — never another building's fee, a neighbours' average, or
an EKÜL baseline quoted as this flat's fee.

Style mirrors sibling batch dims_group17rest.py (#196): the scorer
is pure and offline-tested — (origin, pois) -> (Optional[int
0..100], Estonian reason). Network lives only in
livability.fetch_pois; this module adds no network calls. With no
honest map signal there is no Overpass fragment and no tag mapping
by design (a fee has no OSM tags); a future central hook only needs
GROUP17C_DIMS below.

Judgment calls (reviewable per AGENTS.md section 7.5):
* dim_hoa_fees returns None for EVERY input including missing
  origin: inventing a gradient from zero signal (neighbours'
  average, EKÜL baseline as a per-flat figure) would be fake
  precision (OTA PR #131 precedent). The reason points at the
  e-Äriregister check the buyer must do instead.
* The monthly fee (p3) is deliberately distinct from the one-off
  initiation fee (p427, G17-rest): the reasons name "igakuine"
  vs "sisseastumismaks" so the two NULLs cannot be confused.

Integration (deliberately NOT done here): rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


def dim_hoa_fees(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p3: NULL — the monthly HOA fee is a per-KÜ EUR fact (no map)."""
    return None, ("Igakuine haldustasu (KÜ hooldustasu) teadmata "
                  "(KÜ eelarve/juhatuse tasumäär; hetktõmmises pole "
                  "tasuandmeid — kontrolli Äriregistrist)")


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP17C_DIMS: Dict[str, Tuple[str, object]] = {
    "hoa_fees": ("Haldustasu (kontroll)", dim_hoa_fees),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP17C_PARAM_IDS = {
    "hoa_fees": 3,
}


def score_group17c(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 17-C dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP17C_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
