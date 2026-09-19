"""P4 micromobility (bike-share GBFS) per-listing dim (issue #688).

FEED VERDICT (checked 2026-09-19, dated negative keeps verdict):
no anonymously pollable keyless GBFS feed exists for Tallinn or
Tartu (official registry empty for EE, Tartu Smart Bike is a
session-keyed WeGoShare app with zero GBFS surface, Dott answers
ERR_REGION_NOT_FOUND, no Tallinn municipal system exists at all —
full evidence in docs/p4_gbfs.md section 6). So the dim returns
None for EVERY input including missing origin: a bike-availability
gradient painted without a feed would be fake precision (OTA PR
#131 precedent). The reason says "hinnang" and "EI OLE" and points
at the concrete buyer-side check — never a faked station count.

Style mirrors services/scoring/dims_p4_viirs.py (#325, the closest
sibling: same dated-negative NULL shape): the scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100],
Estonian reason). No network, no Overpass fragment, no tag mapping.

When a keyless feed verifies (FEEDS in scripts/build/batch_gbfs.py
non-empty, docs/p4_gbfs.md updated), graduate this dim to a
per-listing join (stations within 500 m, capped amenity band) and
re-open #688 — until then the key stays NULL.

Integration (deliberately NOT done here): no WEIGHTS change —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits
would break every sibling. Rebalancing stays one joint change.
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-GBFS: documented no-feed micromobility NULL (OTA PR #131
# precedent). No keyless Tallinn/Tartu GBFS feed is verified; the
# scorer reports the gap with the buyer-side check instead of a
# faked station count.
# ---------------------------------------------------------------------------

def dim_gbfs_bikes(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """P4-GBFS: NULL — keyless rattaringluse-voogu pole (EI OLE)."""
    return None, ("Rattaringluse jaamad (Tartu Smart Bike / Tallinna "
                  "operaatorrattad) on korteri-hinnang (EI OLE "
                  "anonüümselt loetavat keyless GBFS-voogu): ametlik "
                  "GBFS-register Eestit ei nimeta, Tartu rakendus on "
                  "sessioonivõtmega äpp ilma GBFS-pinnata, Tallinnas "
                  "munitsipaal-rattaringlust pole — vaata jaamade seisu "
                  "ratas.tartu.ee kaardilt või operaatori äpist ja "
                  "käi lähim jaam kohapeal läbi, ära feigi olematut "
                  "jaamaloendust")


GBFS_DIMS = (
    ("gbfs_bikes", "P4-GBFS", dim_gbfs_bikes),
)


def score_gbfs(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """The P4 GBFS dim for one listing (entry point for the
    weight-rebalance follow-up; keys match GBFS_DIMS). The value is
    None by design — no verified keyless feed, never a faked
    per-listing station count."""
    return {key: fn(origin, pois)[0] for key, _, fn in GBFS_DIMS}
