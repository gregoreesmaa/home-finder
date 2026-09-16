"""P4 riigimaa dims (issue #544): state-land adjacency + auction early-warning.

Two per-parcel adjacency scorer dims (never gradients):

* ``state_land_adjacency`` -- borders state land (KATRI): forest-class
  neighbour -> assurance band 70, other state land -> 60 (capped hinnang --
  ownership can change; the auction leg exists precisely because of that).
* ``auction_warning`` -- borders an ACTIVE auction parcel
  (riigimaaoksjon.ee): flat flag 40, dated, carries auction date + ID +
  URL. Expired auctions never score.

OPENNESS VERDICT (probed 2026-09-16, polite one-off round, custom UA
``home-finder openness-check (one-off, few pages max, no scrape)``,
single GETs with 2 s pacing, ``--max-time 30``; raw bodies kept at
/tmp/hf-probes/, never committed):

* KATRI WFS ``gsavalik.envir.ee/geoserver/katri/wfs`` ->
  GetCapabilities HTTP 200 (162 KB): 30 types incl.
  ``katri:state_property_ownership`` (state parcels),
  ``katri:state_property_unreformed``,
  ``katri:state_property_usage_rights`` (+ maintenance/contract slices).
  CRS EPSG:3301/3857/4326. Licence CC BY 4.0 (issue-stated; attribution
  below).
* DescribeFeatureType (both state types) -> HTTP 200 (3.7 KB): the join
  attributes EXIST -- ``katastritunnus``, ``vara_liik`` (asset class),
  ``riigivara_valitseja`` (manager, e.g. RMK), ``volitatud_asutus``,
  ``nimetus``, ``pindala``. Exact ``vara_liik`` codelist VALUES are
  unprobed (no KATRI rows pulled -- only caps + schema), so the
  forest/other split below matches on documented substrings and is
  labelled provisional (reopen-checklist item 1).
* Auction WFS ``gsavalik.envir.ee/geoserver/maaoksjon/wfs`` ->
  GetCapabilities HTTP 200 (109 KB): exactly one type,
  ``maaoksjon:auction``. Schema (DFT HTTP 200, 2.1 KB): ``id``,
  ``obj_id``, ``purpose`` (Müük/Rent), ``organizer``, ``offer_deadline``
  (``17.09.2026 kell 10:00`` shape), ``starting_price``,
  ``deposit_amount``, ``status`` (``Avaldatud``), ``url``
  (riigimaaoksjon.ee), ``note`` + polygon ``geom``.
* ONE live sample row (count=1, EPSG:4326): id 3244621, Müük,
  Maa- ja Ruumiamet, deadline 17.09.2026 kell 10:00, status Avaldatud,
  ``totalFeatures`` 272 Estonia-wide -- the join is proven on live bytes.
* Harjumaa bbox (24.5,59.3,25.3,59.6) pull, count=300: 15 auction
  features (8 Rent + 7 Müük, ALL status Avaldatud, deadlines
  17.09-21.10.2026) -- the early-warning leg has live discrimination in
  the buyer area, not a flat field.

ATTRIBUTION: Maa- ja Ruumiamet (Land and Spatial Administration),
licence CC BY 4.0. Daily feed -> harvest WEEKLY at most (TTL note, no
harvester built here).

HONESTY (AGENTS.md section 7.2): outside every state/auction polygon
stays NULL (teadmata, never "no state neighbour" / "nothing planned").
Assurance is hinnang, capped at 70 -- state CAN sell (legend says so).
Every scored reason prints its components (neighbour tunnus/class or
auction date + ID + URL); every NULL reason says "EI OLE" and names the
concrete check (KATRI app, riigimaaoksjon.ee, KOV ehitusplaan). Transport
errors are never cached as data: this module makes NO network calls at
all (pinned by test via source inspection).

ADJACENCY RULE (reviewer call, documented): a state/auction parcel whose
polygon CONTAINS the listing, or whose nearest vertex is within
``ADJACENCY_M = 50`` m, counts as adjacent. Shared-boundary-only would
miss true neighbours on digitisation slivers; the 50 m buffer can only
over-flag, and the reason states the buffer ("<= 50 m puhvri-hinnang").

AUCTION-EXPIRY HANDLING: active = ``status == "Avaldatud"`` AND parsed
``offer_deadline`` date >= today. Anything else (expired deadline,
other status, unparseable/missing deadline) is IGNORED -- expired
auctions must not score, and an unknown expiry must not flag either
(unknown -> NULL with EI OLE, never a guess).

Style mirrors services/scoring/dims_p4_maa_subsurface.py (#248/#332):
pure offline scorers over caller-supplied polygons ([[lon, lat], ...] in
EPSG:4326; projection happens upstream), local helpers (no livability
import -- that would turn the future central hook into a cycle, same
precedent as PRs #100/#106/#115). No shared-file edits: 3 new files
only (this module + tests + docs/p4_riigimaa.md).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Assurance capped at 70 (never 100): bordering RMK forest is evidence
  the next-door field stays field, not a guarantee -- the auction leg
  prices the residual sale risk on the SAME parcel family.
* Flat 40 for the auction flag: a neighbouring sale is a warning, not a
  measured noise/view loss -- no timetable, no gradient, dated by design.
* Rent vs Müük both flag (a rental auction still changes the neighbour);
  purpose is named in the reason so the buyer can weight it.
* No auction-bidding advice/valuation (existence + date + buyer check
  only); no RMK management-plan claims (boundaries != logging plans).

Integration (deliberately NOT done here): WEIGHTS/livability/layers
rebalancing stays one joint change across all batches (existing tests pin
set(WEIGHTS) exactly).
"""

import datetime as _dt
import math
import re
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# Contract constants.
# ---------------------------------------------------------------------------

#: Adjacency buffer in metres (shared boundary OR within this vertex
#: distance counts as adjacent -- documented reviewer call above).
ADJACENCY_M = 50.0

#: State-forest assurance band (capped hinnang) vs other state land.
FOREST_ASSURANCE = 70
OTHER_ASSURANCE = 60

#: Active-auction flag (flat, dated warning -- never a measured loss).
AUCTION_FLAG = 40

#: Auction status value meaning "published / open for bids" (live bytes).
AUCTION_ACTIVE_STATUS = "Avaldatud"

#: ``offer_deadline`` shape on live bytes: "17.09.2026 kell 10:00".
_DEADLINE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; local to avoid import cycles).
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lon1: float, lat2: float,
                 lon2: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def point_in_polygon(lon: float, lat: float,
                     ring: List[List[float]]) -> bool:
    """Ray-casting containment. Degenerate rings match nothing."""
    pts = [(p[0], p[1]) for p in ring
           if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 3:
        return False
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            xinters = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < xinters:
                inside = not inside
    return inside


def _nearest_vertex_m(lon: float, lat: float,
                      polygons: List[List[List[float]]]) -> Optional[float]:
    """Haversine to the nearest polygon vertex; None when no vertices."""
    best: Optional[float] = None
    for ring in polygons or []:
        for p in ring or []:
            if not (isinstance(p, (list, tuple)) and len(p) >= 2):
                continue
            try:
                d = _haversine_m(lat, lon, float(p[1]), float(p[0]))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(d):
                continue
            if best is None or d < best:
                best = d
    return best


def _contains(lon: float, lat: float,
              polygons: List[List[List[float]]]) -> bool:
    """True when the point falls inside any ring."""
    return any(point_in_polygon(lon, lat, ring) for ring in polygons or [])


def parse_offer_deadline(raw: object) -> Optional[_dt.date]:
    """Parse ``offer_deadline`` (``17.09.2026 kell 10:00``) to a date.

    Unparseable / missing input -> None (callers treat that as unknown
    expiry, which must NOT flag -- expired auctions never score).
    """
    if not isinstance(raw, str):
        return None
    m = _DEADLINE_RE.search(raw)
    if not m:
        return None
    try:
        return _dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _is_forest(attrs: dict) -> bool:
    """Forest-class heuristic (PROVISIONAL -- vara_liik codelist values
    unprobed; only caps + schema were pulled, no KATRI rows).

    Matches ``mets`` (forest) in vara_liik/nimetus or RMK
    (Riigimetsa Majandamise Keskus) in the manager fields.
    """
    blob = " ".join(str((attrs or {}).get(k, "")) for k in (
        "vara_liik", "nimetus", "riigivara_valitseja",
        "volitatud_asutus")).lower()
    return ("mets" in blob) or ("rmk" in blob)


# ---------------------------------------------------------------------------
# Dim 1: state-land adjacency (assurance leg, capped hinnang).
#
# state_parcels: [{"polygons": [rings], "katastritunnus": str,
#   "vara_liik": str, "riigivara_valitseja": str, "nimetus": str}]
# ---------------------------------------------------------------------------

def dim_state_land_adjacency(origin: Optional[Tuple[float, float]],
                             state_parcels: Optional[List[dict]]) -> Score:
    """Borders-state-land assurance (high = likelier-stable neighbour).

    Nearest KATRI state parcel containing the listing or within 50 m:
    forest class -> 70, other -> 60. Outside stays NULL (teadmata).
    """
    if not origin or state_parcels is None:
        return None, ("Riigimaa-naabruse info puudub (EI OLE KATRI "
                      "riigimaa-liidestust hetktõmmes: kiht pole laetud)")
    lat, lon = origin
    if not all(isinstance(v, (int, float)) and math.isfinite(v)
               for v in (lat, lon)):
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "riigimaa-puhvrit ei saa arvutada, ära feigi")
    if not state_parcels:
        return None, ("KATRI riigimaa-kihti EI OLE laetud (hinnang "
                      "puudub): naabrus vajab state_property_ownership "
                      "liidestust -- kontrolli KATRI rakendusest, ära feigi")
    best = None  # (dist_m, parcel, inside)
    for parcel in state_parcels:
        polys = (parcel or {}).get("polygons") or []
        inside = _contains(lon, lat, polys)
        dist = 0.0 if inside else _nearest_vertex_m(lon, lat, polys)
        if dist is None or dist > ADJACENCY_M:
            continue
        if best is None or dist < best[0]:
            best = (dist, parcel)
    if best is None:
        return None, ("Läheduses (<= 50 m) riigimaad EI OLE teada "
                      "(hinnang puudub): kaugus ei tõesta arendusohu "
                      "puudumist -- naaberkinnistute plaanid KOV-ist, "
                      "ära feigi")
    dist_m, parcel = best
    attrs = parcel if isinstance(parcel, dict) else {}
    tunnus = attrs.get("katastritunnus", "?")
    if _is_forest(attrs):
        score, word = FOREST_ASSURANCE, "riigimets (RMK/metsamaa)"
    else:
        score, word = OTHER_ASSURANCE, "muu riigimaa"
    pos = "krundil" if dist_m == 0.0 else "<= 50 m puhvri-hinnangus"
    return score, ("Riigimaa-naabruse hinnang %d/100 (%s %s, tunnus %s, "
                   "jäme hinnang, lagi 70): mets/põld kõrval jääb "
                   "tõenäoliselt põlluks/metsaks, AGA omand võib muutuda "
                   "-- riik müüb oksjonil (oksjonipool samas moodulis); "
                   "allikas Maa- ja Ruumiamet CC BY 4.0"
                   % (score, word, pos, tunnus))


# ---------------------------------------------------------------------------
# Dim 2: auction early-warning (flag leg, flat + dated).
#
# auctions: [{"polygons": [rings], "offer_deadline": str, "status": str,
#   "purpose": str, "obj_id": int, "url": str}]
# ---------------------------------------------------------------------------

def dim_auction_warning(origin: Optional[Tuple[float, float]],
                        auctions: Optional[List[dict]],
                        today: Optional[_dt.date] = None) -> Score:
    """Borders-active-auction flag (low flat = construction may come).

    Only ``Avaldatud`` auctions with a deadline >= today count; expired /
    unknown-expiry auctions are ignored (they must not score). Outside
    stays NULL (teadmata).
    """
    now = today or _dt.date.today()
    if not origin or auctions is None:
        return None, ("Oksjoni-early-warning info puudub (EI OLE "
                      "riigimaaoksjonite liidestust hetktõmmes: kiht pole "
                      "laetud)")
    lat, lon = origin
    if not all(isinstance(v, (int, float)) and math.isfinite(v)
               for v in (lat, lon)):
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "oksjoni-puhvrit ei saa arvutada, ära feigi")
    if not auctions:
        return None, ("Riigimaaoksjonite kihti EI OLE laetud (hinnang "
                      "puudub): naabrus vajab maaoksjon:auction liidestust "
                      "-- kontrolli riigimaaoksjon.ee-st, ära feigi")
    best = None  # (dist_m, auction, deadline)
    skipped_expired = 0
    for auc in auctions:
        auc = auc or {}
        if auc.get("status") != AUCTION_ACTIVE_STATUS:
            skipped_expired += 1
            continue
        deadline = parse_offer_deadline(auc.get("offer_deadline"))
        if deadline is None or deadline < now:
            skipped_expired += 1
            continue
        polys = auc.get("polygons") or []
        inside = _contains(lon, lat, polys)
        dist = 0.0 if inside else _nearest_vertex_m(lon, lat, polys)
        if dist is None or dist > ADJACENCY_M:
            continue
        if best is None or dist < best[0]:
            best = (dist, auc, deadline)
    if best is None:
        extra = ("; %d aegunud/tundmatu oksjonit eiratud (EI OLE "
                 "skoorivat kirjet)" % skipped_expired) if skipped_expired \
            else ""
        return None, ("Aktiivset riigimaaoksjonit läheduses (<= 50 m) "
                      "EI OLE teada (hinnang puudub%s): kaugus ei tõesta, "
                      "et kõrvale ei ehitata -- naaberkinnistute plaanid "
                      "KOV-ist ja riigimaaoksjon.ee-st, ära feigi" % extra)
    dist_m, auc, deadline = best
    pos = "krundil" if dist_m == 0.0 else "<= 50 m puhvri-hinnangus"
    return AUCTION_FLAG, ("Oksjoni-early-warning %d/100: %s-oksjon "
                          "(objekt %s, pakkumiste tähtaeg %s, staatus "
                          "%s) %s -- kõrvale VÕIB tulla ehitus "
                          "(hind + vaade + müra); kontrolli KOV "
                          "ehitusplaane ja %s, ära feigi"
                          % (AUCTION_FLAG, auc.get("purpose", "?"),
                             auc.get("obj_id", "?"), deadline.isoformat(),
                             AUCTION_ACTIVE_STATUS, pos,
                             auc.get("url", "riigimaaoksjon.ee")))


P4_RIIGIMAA_DIMS = (
    ("state_land_adjacency", dim_state_land_adjacency),
    ("auction_warning", dim_auction_warning),
)


def score_p4_riigimaa(origin: Optional[Tuple[float, float]],
                      state_parcels: Optional[List[dict]] = None,
                      auctions: Optional[List[dict]] = None,
                      today: Optional[_dt.date] = None) -> Dict[
                          str, Optional[int]]:
    """Both P4 riigimaa dims for one listing (entry point for the
    weight-rebalance follow-up)."""
    return {
        "state_land_adjacency": dim_state_land_adjacency(
            origin, state_parcels)[0],
        "auction_warning": dim_auction_warning(origin, auctions, today)[0],
    }
