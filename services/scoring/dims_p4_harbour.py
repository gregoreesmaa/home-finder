"""P4 harbour dims (issues #542, #627): measured sadamaregister + AIS legs.

GATES CLEARED 2026-09-17 (issue #627 probe round, owner decision
"usable without a licence" per #625): sadamaregister ApiBaseUrl
resolved (same-host /api, ``/ports/public-active`` serves 245 rows),
portFunction enum mapped from the app's own UI (1 = full-service,
2 = small paid <24 m, 3 = small free), INSPIRE PortNode geometry
joined on publicId (``EE-PIR_168`` ↔ 168, N,E axis despite the CRS84
label), AIS 2024 SHP pulled (CC BY-SA 3.0; Pirita near-cell
Pleasure=53 proven). Season data is NOT public (detail endpoints
401) -- no calendar leg is built, stated in every reason.

Two live legs (both NULL outside their data, never calm/quiet):

* ``harbour_function_zone`` -- port-function proximity leg (the
  measured replacement for the P4-023 ``sadam`` fixture zone in
  ``dims_p4_trans``: fixture sadam-within-1km -> fn1-within-1km band).
* ``ais_pleasure_density`` -- AIS pleasure-craft 500 m-grid leg, grid
  used as-is, never re-interpolated.

OPENNESS VERDICT (probed 2026-09-16, polite one-off round, custom UA
``home-finder openness-check (one-off, few pages max, no scrape)``,
single GETs with 2 s pacing, ``--max-time 30``; raw bodies kept at
/tmp/hf-probes/, never committed):

UPDATE 2026-09-17 (issue #627): every gate above cleared except
season. Same-host ``/api`` tried on the bundle's paths:
``/api/ports/public-active`` -> HTTP 200, 245 port rows WITH
``portFunction`` (the function source the WFS lacked); the 1/2/3 enum
maps to the app's own UI strings (full-service / small paid <24 m /
small free). Per-port detail paths 401 (auth) -- no per-record
scraping, list only. INSPIRE PortNode Harju pull (38 nodes) joins on
publicId (``EE-PIR_168`` <-> 168); the WFS labels CRS84 but serves
3301 N,E (verified at Pirita). AIS: Teabevärav search API resolves
the ``laevaliikluse-tihedus`` record (PUBLIC, CC BY-SA 3.0 on the SHP
distribution, Transpordiamet); both S3 HEADs 302 to presigned URLs;
``ais_density_shp.zip`` (47 MB, 2018-2024 vintages, L-EST97 500 m
grid, All/Cargo/Fishing/Passenger/Pleasure/Tanker/Under24m/Over24m)
pulled once; Pirita near-cell (494 m offshore) reads
All=63/Pleasure=53 -- the marina-side signal, proven not faked.
Season dates stay non-public: no calendar leg, stated everywhere.

HONESTY (AGENTS.md section 7.2): outside port/cell influence stays
NULL (never "quiet/calm"). Reasons carry the no-season caveat and
point at the buyer-side check (sadamaregister port pages, on-site
listening at the Vanasadam/Pirita edge) -- never a faked area score.
Transport errors are never cached as data: this module makes NO network
calls at all (pinned by test via source inspection).

FIXTURE-REPLACEMENT AUDIT (P4-023 sadam leg, row-for-row): the live
``dims_p4_trans.dim_noise_zone_trans`` join reads fixture labels
``NOISE_ZONE_SCORES = {"lennumüra": 35, "õppus": 50, "sadam": 60}`` --
any ``noisezone_p4`` POI labelled ``sadam`` within 1 km scores a flat 60.
The measured replacement (SHIPPED in #627 once the licence gate
opened) maps row-for-row: fixture ``sadam``-within-1km -> function bands
by distance from joined port rows (fn1 working ports read industrial,
fn2/fn3 marinas read amenity -- worst/lowest wins, buyer-conservative).
Rows without a joined function keep the fixture 60, honestly. The live
hook is ``dims_p4_trans.dim_noise_zone_trans``. Full table in
docs/p4_harbour.md.

Style mirrors services/scoring/dims_p4_sadam.py (#298/#368): pure
offline scorers (origin, pois) -> (Optional[int 0..100], Estonian
reason); helpers are local (no livability import -- that would turn the
future central hook into a cycle, same precedent as PRs #100/#106/#115).
Shared-file change: the P4-023 hook in ``dims_p4_trans`` (plus this
module + tests + docs/p4_harbour.md).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Bands instead of verdict (gate opened #627): the sadamaregister
  ``public-active`` leg + INSPIRE names + pulled AIS grid graduate both
  legs to bands from joined records only -- bands from either BEFORE
  the join would have been fake precision (OTA PR #131 precedent).
* P4-047 event-traffic + P4-055 icebreaking dims stay cousins (distinct
  keys); P4-023 keeps the trans fixture band plus the KAUR/EHR slices --
  each reason names its cousins.
* AIS gaps note: the publisher (per issue) ships annual 2018-2024 grids;
  brief AIS coverage gaps are a stated reopen-check, not a silent caveat.

Integration (deliberately NOT done here): WEIGHTS/livability/layers
rebalancing stays one joint change across all batches (existing tests pin
set(WEIGHTS) exactly).
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# P4-023/P4-033-adjacent: measured harbour legs (live since #627).
# sadamaregister.ee public-active app API (function taxonomy) + INSPIRE
# PortNode (names) + pulled AIS 2024 grid. Each scorer still reports its
# gap with a concrete buyer-side check (no-season caveat, NULL outside).
# ---------------------------------------------------------------------------

#: Function proximity bands: (within_m, score). Worst (lowest) wins
#: across joined ports (buyer-conservative, like the noise min-wins).
#: fn1 working ports read industrial; fn2/fn3 marinas read amenity.
FUNCTION_BANDS = {
    1: ((500, 45), (1500, 65)),
    2: ((500, 70), (1500, 80)),
    3: ((500, 75), (1500, 85)),
}

#: Pleasure-cell bands by annual count in the nearest cell (mild leg,
#: never dominates): busy sailing water = recreation amenity.
PLEASURE_BANDS = ((50, 70), (10, 80), (1, 85))

#: AIS influence window (mirror of the 1500 m function gate): cells past
#: this are outside influence -> NULL, never a far-away busy score.
AIS_WINDOW_M = 1500.0

#: Season data is not public (detail endpoints 401) -- restated in
#: every reason: no sailing-calendar claims, annual totals only.
NO_SEASON = "hooajajaotust pole (aastakokku)"


def _dist(row: dict) -> Optional[float]:
    d = row.get("dist_m")
    if isinstance(d, bool) or not isinstance(d, (int, float)) or d < 0:
        return None
    return float(d)


def _pleasure(c: dict) -> Optional[float]:
    pl = c.get("pleasure")
    if isinstance(pl, bool) or not isinstance(pl, (int, float)):
        return None
    return float(pl)


def dim_harbour_function_zone(origin: Optional[Tuple[float, float]],
                              ports: Optional[List[dict]]) -> Score:
    """Measured port-function proximity leg (live since #627)."""
    if not origin or ports is None:
        return None, "Sadama info puudub"
    scored = []
    for p in ports:
        fn = p.get("function")
        bands = FUNCTION_BANDS.get(fn) if type(fn) is int else None
        d = _dist(p)
        if not bands or d is None:
            continue
        for within, score in bands:
            if d <= within:
                scored.append((score, d, p))
                break
    if not scored:
        return None, ("Sadama mõjualas sadamat pole (lähim teadaolev "
                      "sadam kaugemal kui 1500 m) -- NULL, MITTE rahulik "
                      "(%s)" % NO_SEASON)
    scored.sort(key=lambda t: (t[0], t[1]))
    s, d, p = scored[0]
    return s, ("Lähim sadam %s (%s) %.0f m -- %s"
               % (p.get("name", "?"), p.get("function_label", "?"),
                  d, NO_SEASON))


def dim_ais_pleasure_density(origin: Optional[Tuple[float, float]],
                             cells: Optional[List[dict]]) -> Score:
    """AIS pleasure-craft grid leg (live since #627, grid as-is)."""
    if not origin or cells is None:
        return None, "AIS-tiheduse info puudub"
    scored = []
    for c in cells:
        d = _dist(c)
        pl = _pleasure(c)
        if d is None or pl is None or d > AIS_WINDOW_M:
            continue
        for at_least, score in PLEASURE_BANDS:
            if pl >= at_least:
                scored.append((score, d, pl))
                break
    if not scored:
        return None, ("Läheduses väikelaevaliiklust pole (500 m ruudustik, "
                      "mõjuaken 1500 m) -- NULL, MITTE vaikne (%s)"
                      % NO_SEASON)
    scored.sort(key=lambda t: (t[0], t[1]))
    s, d, pl = scored[0]
    return s, ("Lähim väikelaevaruudustik %.0f m (aasta ~%d) -- %s"
               % (d, pl, NO_SEASON))


P4_HARBOUR_DIMS = (
    ("harbour_function_zone", "P4-023", dim_harbour_function_zone),
    ("ais_pleasure_density", "P4-033", dim_ais_pleasure_density),
)


def score_p4_harbour(origin: Optional[Tuple[float, float]],
                     ports: Optional[List[dict]] = None,
                     cells: Optional[List[dict]] = None
                     ) -> Dict[str, Optional[int]]:
    """Both P4 harbour dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_HARBOUR_DIMS). Missing
    joins stay None (unknown, never calm) -- never a faked score."""
    return {
        "harbour_function_zone": dim_harbour_function_zone(origin, ports)[0],
        "ais_pleasure_density": dim_ais_pleasure_density(origin, cells)[0],
    }
