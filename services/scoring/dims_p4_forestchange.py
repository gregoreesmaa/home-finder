"""Clear-cut dynamics from metsamuutused yearly SHPs (issues #548, #624).

LICENCE VERDICT, FLIPPED 2026-09-17 (issue #624): the distribution
bundles its licence — ETAK-open-data-licence.pdf + Estonian twin
(verified in the 2024 zip central directory; English PDF
range-fetched, decompresses to its stated size) — the Land Board
open-data licence 01.01.2025, grant-by-use for ETAK spatial data,
catalogue access PUBLIC. Attribution stamped in every sidecar +
source line. Residual gray (reviewable): the glyph-encoded PDFs
defeated verbatim clause extraction, and the catalogue still shows no
licence field — so the verdict cites the bundled file + indexed grant
text, and the reviewer judges. LICENCE_OK = True; the pinned bands go
live with the #624 overlay.

Source: Maa- ja Ruumiamet metsamuutuste andmed, ANNUAL. Series
2012-2015 + 2017-2024 (2016 absent — stated gap). Content: polygons
where CHM comparison shows vegetation-height drop >5 m on >0.25 ha,
with area + first/second survey dates.

Harvest (2026-09-17, UA home-finder-dev/0.1, polite single pull — the
licence-day bulk job): Metsamuutused_2024.zip (59 179 549 bytes),
kevad 9212 + suvi 989 polygons national; Harju+2 km keep 4951 + 337;
all second_dates 2024-04/05/08 (age ~2.3 y — RECENT bracket).

Publisher caveat (LOAD-BEARING, restated in every reason): detected
change is NOT official logging statistics — automatic CHM-difference
processing, errors expected (classification/filtering artefacts from
differing LiDAR conditions). Reasons always say "tuvastatud muutus"
(detected change), never "lageraiet" (logging).

Shape (for licence-day): recent change (<=3 yrs) <=500 m -> low band;
older/far -> neutral; NO change in the window -> NULL (never "safe
forest" — absence of detected change is not protection, #517 zones
answer the legal half). Per-listing overlay only; no raster master
here (county stamp run belongs to the bulk job).

Style: pure functions, (origin, changes, today) -> (Optional[int],
Estonian reason). No network, no cache — transport errors cannot
become data because there is no transport here.

Judgment calls (reviewable):
* Bands: <=3 yrs & <=500 m -> 30 (fresh cut next door dominates);
  <=3 yrs & <=1500 m -> 55; 4-10 yrs & <=500 m -> 60 (regrowth
  trajectory); anything older/farther with a change on record -> 70;
  empty window -> None. 0.25 ha / 5 m thresholds are the publisher's,
  not ours — we only band age x distance.
* False-positive sanity: 20-spot Harjumaa note run 2026-09-17 on the
  real vintage (see docs/p4_forestchange.md §2) — 20/20 clean forest
  context, zero buildings inside any sampled polygon. OSM buildings
  can miss the newest construction, so the detected-change caveat
  still rides in every reason.
* No WEIGHTS / livability / layers / registry edits (joint precedent).
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Licence gate, FLIPPED 2026-09-17 (issue #624): bundled
#: ETAK-open-data-licence.pdf + PUBLIC catalogue access (see module
#: docstring for the evidence + residual gray).
LICENCE_OK = True
LICENCE_NOTE = ("ETAK avaandmete litsents 01.01.2025 "
                "(jaotuses kaasas, kataloogis PUBLIC)")
#: Publisher's load-bearing caveat, restated in every reason.
CAVEAT = ("tuvastatud muutus, mitte ametlik raiestatistika "
          "(automaattöötlus, vead võimalikud)")
#: Recent-change window (years) and near radius (m).
RECENT_YEARS = 3
NEAR_M = 500


def _age_years(first: object, second: object,
               today: date) -> Optional[float]:
    """Years since the change window midpoint (pure, tolerant parser)."""
    def _parse(v: object) -> Optional[date]:
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                y, m, d = v.strip().split("-")[:3]
                return date(int(y), int(m), int(d))
            except (ValueError, TypeError):
                return None
        return None
    d1, d2 = _parse(first), _parse(second)
    ref = d2 or d1
    if ref is None:
        return None
    return (today - ref).days / 365.25


def _score_change(age_yrs: Optional[float],
                  dist_m: Optional[float]) -> Optional[int]:
    """Pure age x distance band (pinned now, live on licence-day)."""
    if age_yrs is None or dist_m is None:
        return None
    if age_yrs <= RECENT_YEARS and dist_m <= NEAR_M:
        return 30
    if age_yrs <= RECENT_YEARS and dist_m <= 1500:
        return 55
    if age_yrs <= 10 and dist_m <= NEAR_M:
        return 60
    return 70


def dim_forest_recent(origin: Optional[Tuple[float, float]],
                      changes: Optional[List[dict]],
                      today: Optional[date] = None) -> Score:
    """Detected-change overlay leg (gated: NULL until licence clears)."""
    if LICENCE_OK and origin and changes is not None:
        day = today or date.today()
        scored = []
        for c in changes:
            d = c.get("dist_m")
            d = float(d) if isinstance(d, (int, float)) and d >= 0 else None
            age = _age_years(c.get("first_date"), c.get("second_date"), day)
            s = _score_change(age, d)
            if s is not None and d is not None and age is not None:
                scored.append((s, d, age))
        if scored:
            scored.sort()
            s, d, age = scored[0]
            return s, ("Lähim tuvastatud võramuutis %.0f m, ~%.0f a tagasi "
                       "(%s)" % (d, age, CAVEAT))
        return None, ("Muutisaknas tuvastatud muutust pole – "
                      "turvalist metsa see ei tõenda (%s)" % CAVEAT)
    if not origin or changes is None:
        return None, "Metsamuutuse info puudub"
    return None, ("Metsamuutuste kiht %s (%s)" % (LICENCE_NOTE, CAVEAT))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
FORESTCHANGE_DIMS = (
    ("forest_recent", "p4-forestchange", dim_forest_recent),
)


def score_forestchange(origin: Optional[Tuple[float, float]],
                       changes: Optional[List[dict]],
                       today: Optional[date] = None
                       ) -> Dict[str, Optional[int]]:
    """Forest-change dim for one listing (rebalance entry point)."""
    return {key: fn(origin, changes, today)[0]
            for key, _, fn in FORESTCHANGE_DIMS}


#: Honest Estonian web labels (live since the #624 licence verdict).
LAYER_META = {
    "forest_recent": {
        "param": "p4-forestchange",
        "title": "Tuvastatud võramuutis (2024 lend)",
        "good": "roheline = muutisaknas muutust pole (mitte 'turvaline mets')",
        "bad": "pruun = 2024 tuvastatud muutus lähedal",
        "source": ("Maa- ja Ruumiamet metsamuutused 2024 "
                    "(ETAK avaandmete litsents; %s)" % CAVEAT),
    },
}
