"""Group 2 EHR building-registry dimensions, batch A (issue #136).

Params (this agent only -- sibling batch G2-B owns p79/p154/p196/p495):
* p21 square footage -> NO DIM (verdict below).
* p30 accessibility (stories) -> dim_accessibility (listing floor + lift).
* p33 age of the property -> NO DIM (verdict below).
* p35 energy efficiency -> dim_energy (listing energy class A-G).
* p48 permit history -> dim_permits (listing permit status).

Per-param verdicts (documented in code + PR, issue #136):
* p21/p30/p33/p35/p48 are ALL documented no-map: EHR building
  attributes describe the DEAL (one building), not the PLACE (the
  area). A green wash over panel districts labelled "accessible" or
  "energy efficient" would paint 5th-floor walk-ups green because
  their NEIGHBOURS are tall -- fake precision (AGENTS.md section
  7.2). Neighbour attributes do not transfer to your flat.
* p21 has no dim either: floor area is a buyer FILTER (rooms wanted),
  never monotonic goodness -- scoring 200 m2 above 40 m2 would be
  wrong. The kv.ee adapter already extracts area_m2; it stays a
  filter, not a score.
* p33 has no dim either: age goodness is taste (Vanalinn charm vs new
  build), never monotonic -- and OSM start_date covers 328 buildings
  county-wide (0.13%), far too sparse for even a proxy.
* p30/p35/p48 have listing-attribute dims below. They are
  deliberately NOT (origin, pois) proximity scorers: no OSM
  neighbourhood signal honestly measures YOUR flat's floor, energy
  class, or permits.

HONESTY (load-bearing, AGENTS.md section 7.2): the EHR registry is
NOT in the 2026-09-12 snapshot (MANIFEST gaps: "registries
(EHR/EHIS/PPA/cadastre/...) not yet pulled"; registries/ is empty),
so every dim returns None when its input is missing -- never a
guess. OSM evidence (local PBF probes 2026-09-12, nwr/building
filter, 252146 buildings county-wide): building:levels 13507 (5%),
start_date on buildings 328 (0.13%), no EPC/permit/area tags at any
scale. Reasons name the data source ("kuulutuse/EHR andmed" for
listing facts, never "hinnang" for them -- the inputs are measured,
not estimated).

Style mirrors services/scoring/livability.py: pure functions ->
(Optional[int 0..100], Estonian reason), absolute scales, hermetic
tests. No network calls in this module.

Integration (deliberately NOT done here): these dims consume
per-listing attributes (floor, lift, energy class, permit status)
from the portal adapters / EHR follow-up -- NOT livability
OVERPASS_QUERY/_POI_KIND/WEIGHTS, which score OSM proximity around
an origin. Wiring them into the enrich/score path is a joint change
with the adapter fields; existing tests pin set(WEIGHTS) exactly.
"""

from typing import Callable, Dict, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# p35: energy efficiency -> listing energy class (monotonic: A best).
# Bands are judgment calls (documented for the reviewer): A/B top band,
# C mid (renovation-grant threshold order), G floor above zero (a
# standing flat is never scored 0 on energy alone).
# ---------------------------------------------------------------------------

#: Energy class -> score (case-insensitive, stripped; EU EPC A-G).
ENERGY_BANDS = {
    "A": 100,
    "B": 90,
    "C": 78,
    "D": 62,
    "E": 45,
    "F": 28,
    "G": 12,
}


def dim_energy(energy_class: Optional[str]) -> Score:
    """p35: energy class score (listing/EHR fact, NOT an estimate)."""
    if energy_class is None:
        return None, "Energiaklass puudub"
    key = str(energy_class).strip().upper()
    if not key:
        return None, "Energiaklass puudub"
    if key not in ENERGY_BANDS:
        # Unknown code (e.g. "A+"): never map to a neighbour band.
        return None, "Tundmatu energiaklass (%s)" % str(energy_class).strip()
    return (ENERGY_BANDS[key],
            "Energiaklass %s (kuulutuse/EHR andmed, mitte hinnang)" % key)


# ---------------------------------------------------------------------------
# p48: permit history -> listing permit status (monotonic: clean best).
# Minimal contract (judgment call, reviewer-adjustable): the EHR
# loamenetlus states collapse to clean / flagged / unpermitted_work.
# Anything else -- including None -- stays None, never a guess.
# ---------------------------------------------------------------------------

#: Permit status -> score.
PERMIT_SCORES = {
    "clean": 100,
    "flagged": 20,
    "unpermitted_work": 0,
}

_PERMIT_REASON = {
    "clean": "Load korras (kuulutuse/EHR andmed, mitte hinnang)",
    "flagged": "Loaloos märge -- kontrolli ehitisregistrist",
    "unpermitted_work": "Loata ehitis/ümberehitus (kuulutuse/EHR andmed)",
}


def dim_permits(status: Optional[str]) -> Score:
    """p48: permit-history score (listing/EHR fact, NOT an estimate)."""
    if status is None:
        return None, "Loaajaloo info puudub"
    key = str(status).strip().lower()
    if key not in PERMIT_SCORES:
        return None, "Tundmatu loastaatus (%s)" % str(status).strip()
    return PERMIT_SCORES[key], _PERMIT_REASON[key]


# ---------------------------------------------------------------------------
# p30: accessibility (stories) -> listing floor + lift (mobility view).
# Ground (1. korrus -- Estonian ground floor) and any lift-served flat
# read 100; walk-up flats decay per floor. Lift UNKNOWN with floor > 1
# stays None: assuming a lift would fake step-free access.
# ---------------------------------------------------------------------------

#: Walk-up floor (2+) without a lift -> score (judgment call).
WALKUP_FLOOR_SCORE = {2: 80, 3: 60, 4: 40}


def dim_accessibility(floor: Optional[int],
                      has_lift: Optional[bool]) -> Score:
    """p30: step-free access from the listing's own floor + lift flag."""
    if has_lift is True:
        return 100, "Lift olemas -- ligipääs tagatud (kuulutuse andmed)"
    if floor is None:
        return None, "Korruse/lifti info puudub"
    try:
        f = int(floor)
    except (TypeError, ValueError):
        return None, "Korruse/lifti info puudub"
    if f < 1:
        # Floor 0/negative: unknown numbering, never guessed as ground.
        return None, "Korruse/lifti info puudub"
    if f == 1:
        return 100, "1. korrus -- trepivaba ligipääs (kuulutuse andmed)"
    if has_lift is None:
        # Floor known above ground, lift unknown: cannot score access.
        return None, "Lifti info puudub"
    if f in WALKUP_FLOOR_SCORE:
        return (WALKUP_FLOOR_SCORE[f],
                "%d. korrus ilma liftita -- ligipääs piiratud" % f)
    return 25, "%d. korrus ilma liftita -- ligipääs piiratud" % f


#: Registry for the per-listing follow-up: (dims key, param id, fn).
#: Signatures differ from the (origin, pois) spatial dims on purpose --
#: EHR params are building attributes (see module docstring).
GROUP02_DIMS: Tuple[Tuple[str, str, Callable], ...] = (
    ("accessibility", "p30", dim_accessibility),
    ("energy", "p35", dim_energy),
    ("permits", "p48", dim_permits),
)

#: Group 2 A params with documented no-dim verdicts (filter/taste,
#: never monotonic goodness): p21 size filter, p33 age taste axis.
GROUP02_NO_DIM = ("p21", "p33")


def score_group02(attrs: Optional[dict]) -> Dict[str, Optional[int]]:
    """All three Group 2 A dims for one listing.

    attrs: {"floor": int|None, "has_lift": bool|None,
    "energy_class": str|None, "permit_status": str|None}.
    Missing attrs dict scores every dim None (never a guess).
    """
    attrs = attrs or {}
    return {
        "accessibility": dim_accessibility(attrs.get("floor"),
                                           attrs.get("has_lift"))[0],
        "energy": dim_energy(attrs.get("energy_class"))[0],
        "permits": dim_permits(attrs.get("permit_status"))[0],
    }
