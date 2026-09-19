"""P4 school-quality (Harno exam results) per-listing dim (issue #687).

STATIC-PENDING VERDICT (checked 2026-09-19, dated negative keeps
verdict): no bulk machine-readable per-school exam export exists
(Haridussilm is a PowerBI-backed visual portal, EIS records sit
behind school accounts, yearly averages reach the public as media
graphics — full evidence in docs/p4_harno.md section 6). So the dim
returns None for EVERY input including missing origin: a school-
quality gradient painted without a verified annual snapshot would
be fake precision (OTA PR #131 precedent). The reason says
"hinnang" and "EI OLE" and points at the concrete buyer-side check
— never a faked school score.

Style mirrors services/scoring/dims_gbfs.py (#688, the closest
sibling: same static-pending NULL shape): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). No network, no Overpass fragment, no tag mapping.

When the first verified annual snapshot lands (validated by
scripts/build/batch_harno.py, docs/p4_harno.md updated), graduate
this dim to a per-listing join (nearest school's band within 1 km,
capped 80) and re-open #687 — until then the key stays NULL.

Integration (deliberately NOT done here): no WEIGHTS change —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits
would break every sibling. Rebalancing stays one joint change.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-harno: documented static-pending school-quality NULL (OTA PR
# #131 precedent). No verified annual per-school snapshot exists;
# the scorer reports the gap with the buyer-side check instead of a
# faked school score.
# ---------------------------------------------------------------------------

def dim_harno_quality(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """P4-harno: NULL — verifitseeritud kooli-kvaliteedi snapshot puudub."""
    return None, ("Kooli kvaliteet (riigieksamite keskmised kooli "
                  "kaupa) on korteri-hinnang (EI OLE verifitseeritud "
                  "aastasnapshotti): Haridussilm on visuaalne portaal "
                  "ilma per-kooli masin-ekspordita — vaata kooli "
                  "näitajaid Haridussilma kooli-lehelt ja käi kool "
                  "kohapeal läbi, ära feigi olematut koolihinnet")


HARNO_DIMS = (
    ("harno_quality", "P4-harno", dim_harno_quality),
)


def score_harno(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 Harno dim for one listing (entry point for the
    weight-rebalance follow-up; keys match HARNO_DIMS). The value is
    None by design — no verified annual snapshot, never a faked
    per-listing school score."""
    return {key: fn(origin, pois)[0] for key, _, fn in HARNO_DIMS}
