"""Group 2 (Ehitisregister/EHR) batch-B scorer dims: issue #137.

Params (this agent only — sibling batch A, issue #136, owns p21/p30/p33/p35/p48):
* p79  building permit history (ehitusloa ajalugu)
* p154 builder warranties (ehitaja garantiid)
* p196 residential elevators (liftid)
* p495 unpermitted sunroom addition (loata klaasveranda/päikesetuba)

HONESTY (load-bearing, AGENTS.md §7.2): the EHR registry is NOT in the
2026-09-12 snapshot (~/hf-data/2026-09-12/registries/ is EMPTY) and this
module performs no live EHR fetch, so every dim returns None while the
pipeline has no EHR record for the listing — never a faked number. Every
non-None reason says "EHR", so a score is always traceable to a registry
record, never to a guess. p79/p154/p495 are dims-ONLY (documented no-map
verdicts, OTA PR #131 precedent — per-building/per-developer records
have no honest area proxy); p196 additionally ships the liftproxy map
layer (apps/web/lib/layers_group02b.ts), which scores AREA high-rise
density while these dims score the LISTING's own EHR record.

Input shape (one listing's EHR record; the whole record may be None):
  {"permits_finalized": int | None,   # finalized EHR permits on the building
   "warranty_valid": bool | None,     # builder warranty currently in force
   "elevator_count": int | None,      # lifts recorded for the building
   "unpermitted_works": bool | None}  # unpermitted works on record
Missing record (None) or missing field (None) stays None — "Flag NULL;
do not fake" per parameters3.md §5.2.

Style mirrors services/scoring/livability.py: pure (value) ->
(Optional[int 0..100], Estonian reason), absolute bands, hermetic
tests. Bands are judgment calls, documented per dim for the reviewer.

Integration (deliberately NOT done here): feeding dim_* with the
listing's EHR record inside livability scoring and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling (group09 precedent).
"""

from typing import Callable, Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# p79: building permit history (finalized-permit count = transparent history).
# A zero is a WEAK history, not a violation — unpermitted works are p495.
# ---------------------------------------------------------------------------

def dim_permit_history(permits_finalized: Optional[int]) -> Score:
    """p79: transparency of the building's EHR permit history."""
    if permits_finalized is None:
        return None, "Ehitusloa ajaloo info puudub (EHR andmed hetktõmmises puuduvad)"
    if permits_finalized >= 2:
        return 85, "EHR: lõpetatud ehituslubasid vähemalt 2 (läbipaistev ehituslugu)"
    if permits_finalized == 1:
        return 70, "EHR: 1 lõpetatud ehitusluba"
    return 45, "EHR: lõpetatud ehituslubasid pole kirjas (nõrk ehituslugu, mitte rikkumine)"


# ---------------------------------------------------------------------------
# p154: builder warranties (warranty in force = post-handover cover).
# ---------------------------------------------------------------------------

def dim_warranties(warranty_valid: Optional[bool]) -> Score:
    """p154: whether a builder warranty currently covers the flat."""
    if warranty_valid is None:
        return None, "Ehitaja garantii info puudub (EHR andmed hetktõmmises puuduvad)"
    if warranty_valid:
        return 90, "EHR: ehitusgarantii kehtib"
    return 50, "EHR: ehitusgarantii on lõppenud"


# ---------------------------------------------------------------------------
# p196: residential elevators (registry lift count for the building).
# Zero here is MEASURED-from-registry (record present, no lift), the one
# honest zero in this module — it still says EHR, never a guess. Unknown
# stays None. Area lift-likelihood lives on the liftproxy map layer.
# ---------------------------------------------------------------------------

def dim_elevators(elevator_count: Optional[int]) -> Score:
    """p196: lifts recorded for the building in EHR."""
    if elevator_count is None:
        return None, "Lifti info puudub (EHR andmed hetktõmmises puuduvad)"
    if elevator_count >= 1:
        return 95, "EHR: hoones on lift (%d)" % elevator_count
    return 30, "EHR: hoones lifti pole kirjas"


# ---------------------------------------------------------------------------
# p495: unpermitted sunroom addition (violation on record = red).
# ---------------------------------------------------------------------------

def dim_sunroom(unpermitted_works: Optional[bool]) -> Score:
    """p495: unpermitted works (sunroom/glazing or similar) on EHR record."""
    if unpermitted_works is None:
        return None, "Loata ehitiste info puudub (EHR andmed hetktõmmises puuduvad)"
    if unpermitted_works:
        return 20, "EHR: kirjas loata ehitis (päikesevarjund/klaasveranda vms)"
    return 85, "EHR: loata ehitisi pole kirjas"


#: Registry for UI/API wiring on integration: field -> (Estonian title, fn).
GROUP02B_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "permit_history": ("Ehitusloa ajalugu (EHR)", dim_permit_history),
    "warranties": ("Ehitaja garantii (EHR)", dim_warranties),
    "elevators": ("Lift (EHR)", dim_elevators),
    "sunroom": ("Loata ehitis (EHR)", dim_sunroom),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP02B_PARAM_IDS = {
    "permit_history": 79,
    "warranties": 154,
    "elevators": 196,
    "sunroom": 495,
}

#: EHR record keys consumed by score_group02b, in dim order.
EHR_RECORD_KEYS = ("permits_finalized", "warranty_valid", "elevator_count",
                   "unpermitted_works")


def score_group02b(ehr: Optional[dict]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 2 batch-B dims at once: ({field: score}, [reasons]).

    ehr is one listing's EHR record (or None while the pipeline has no
    EHR data — every dim then stays None, never faked).
    """
    record = ehr if isinstance(ehr, dict) else {}
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    values = (
        record.get("permits_finalized"),
        record.get("warranty_valid"),
        record.get("elevator_count"),
        record.get("unpermitted_works"),
    )
    for (field, (_, fn)), value in zip(GROUP02B_DIMS.items(), values):
        v, reason = fn(value)
        dims[field] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
