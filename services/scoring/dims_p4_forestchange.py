"""Clear-cut dynamics from metsamuutused yearly SHPs (issue #548).

DOCUMENTED NO-MAP VERDICT with pinned bands: the series exists and
serves, but the catalogue states NO licence, so nothing is ingested.
The day an open licence is confirmed, flip LICENCE_OK and the same
bands go live — tests already pin them.

Source: Maa- ja Ruumiamet metsamuutuste andmed, ANNUAL. Series
2012-2015 + 2017-2024 (2016 absent — stated gap). Content: polygons
where CHM comparison shows vegetation-height drop >5 m on >0.25 ha,
with area + first/second survey dates.

Probe (2026-09-16, UA home-finder-idea-probe/1.0, HEAD only — the
~59 MB zip stays on the server):
HEAD https://geoportaal.maaruum.ee/docs/Avaandmed/Metsamuutused_2024.zip
-> HTTP/2 200, content-type application/zip, content-length 59 179 549,
content-disposition inline; filename=Metsamuutused_2024.zip,
last-modified 16.09.2026. Endpoint serves; nothing downloaded.

Licence gate (LOAD-BEARING, issue constraint): catalogue licence NONE
stated; the description page was not reachable under a polite single
pull. LICENCE_OK = False until a dated re-probe confirms an open
licence. While False every public dim returns None with a gate reason
— no points vendored, no centroids counted, no map.

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
* False-positive sanity (20 Harjumaa spots: new developments vs real
  cuts) belongs to the licence-day bulk job — the SHPs were never
  pulled, so a precision note today would be invented. Stated here so
  the job cannot skip it.
* No WEIGHTS / livability / layers / registry edits (joint precedent).
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Licence hard gate: catalogue states NONE — re-probe before ingesting.
LICENCE_OK = False
LICENCE_NOTE = ("litsents kinnitamata (kataloogis puudub) – "
                "sisse lugemata")
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


#: Honest Estonian web labels for licence-day (never rendered while gated).
LAYER_META = {
    "forest_recent": {
        "param": "p4-forestchange",
        "title": "Tuvastatud võramuutis (litsents ootel)",
        "good": "roheline = muutisaknas muutust pole (mitte 'turvaline mets')",
        "bad": "punane = värske muutus lähedal",
        "source": ("Maa-amet metsamuutused (litsents kinnitamata; %s)"
                    % CAVEAT),
    },
}
