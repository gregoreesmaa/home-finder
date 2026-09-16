"""P4 kitsendus dims (issue #543): kataster KPO restriction zones + tehnovorgud.

Two legs, both documented no-map NULLs until the licence gate clears:

* ``restriction_zone`` -- per-parcel restriction-zone membership
  (piiranguvööndid: ehituskeeld vs conditioned).
* ``utility_corridor`` -- tehnovõrgud (utility-network corridor) membership.

OPENNESS VERDICT (probed 2026-09-16, polite one-off round, custom UA
``home-finder openness-check (one-off, few pages max, no scrape)``,
single GETs with 2 s pacing, ``--max-time 30``; raw bodies kept at
/tmp/hf-probes/, never committed):

* KMA zones WFS ``gsavalik.envir.ee/geoserver/kmakitsendused/wfs`` ->
  GetCapabilities HTTP 200 (127 KB): 18 public zone feature types,
  ``kmakitsendused:kma_avalik_*`` -- asjaoigus, elekter, gaas, geodeesia,
  kaugkyte, kemikaal, looduskaitse, maaparandus, muinsuskaitse,
  planeering, reostusoht, ressurss, riigikaitse, side, sundvaldus,
  transport, veekogu, veevarustus. CRS: EPSG:3301 + EPSG:3857 +
  EPSG:4326. Fees/AccessConstraints ``puudub`` (= no charge -- NOT a
  licence grant).
* DescribeFeatureType ``kma_avalik_looduskaitse`` -> HTTP 200 (2.4 KB):
  the join attributes EXIST and are exactly what a per-parcel join needs
  -- ``voond_liik_id`` + ``voond_liik_id_vaartus`` (zone-type value),
  ``klass``, ``nimi``, ``reegel`` (rule!), ``ulatus``, ``maksusoodustus``,
  ``valise_registri_viide``. The SHAPE is joinable; the VALUES are
  unprobed (no rows pulled -- see the gate).
* GATE (issue hard gate): the catalogue states NO licence, and none was
  found in the capabilities either -- so NO zone row is ingested, NO
  Harjumaa count is pulled, NO per-parcel containment is proven on live
  rows. The join below is proven on FIXTURES only; the >=20-parcel live
  proof (kataster tunnus) is reopen-checklist item 2.

HONESTY (AGENTS.md section 7.2): both scorers return None for EVERY
input. Inside/outside is computed ONLY by the offline join helper over
caller-supplied polygons; outside every polygon stays NULL (teadmata,
never "clean title" -- zones are not title truth, the legend must say
so, and every reason names the kinnistusraamat/notar buyer check).
Transport errors are never cached as data: this module makes NO network
calls at all (pinned by test via source inspection).

ZONE-TYPE -> BAND MAPPING (reviewable; APPLIES ONLY after the gate --
today every call returns None. Calibrated per the issue: building ban
-> 20-35, conditioned -> 50-65; exact Harjumaa tally on reopen):

===========================+==========+=====================================
zone family (voond_liik)   | band     | rationale
===========================+==========+=====================================
ehituskeeld / building ban | 20       | cannot build here -- deal question
                           |          | (kinnistusraamat + notar check)
range 20-35 for ban severity (full ban 20, partial/setback 35)
---------------------------+----------+-------------------------------------
tingimuslik / conditioned  | 50       | buildable with conditions (load,
(load, kooskõlastus)       |          | Keskkonnaamet/Muinsuskaitse
                           |          | coordination -- buyer check names it)
range 50-65 (heavy conditions 50, light notice-duty 65)
---------------------------+----------+-------------------------------------
teadmata / unknown type    | NULL     | unmapped type must not score --
                           |          | EI OLE, never a guess
---------------------------+----------+-------------------------------------
outside every polygon      | NULL     | teadmata -- NEVER "clean title"
                           |          | (zones != title: kinnistusraamat)
===========================+==========+=====================================

Style mirrors services/scoring/dims_p4_maa_subsurface.py (#248/#332):
pure offline join core (rings are [[lon, lat], ...] in EPSG:4326;
projection happens upstream), per-parcel class flags, scorers
(parcel, zones) -> (Optional[int 0..100], Estonian reason). Helpers are
local copies (no livability import -- that would turn the future central
hook into a cycle, same precedent as PRs #100/#106/#115). No shared-file
edits: 3 new files only (this module + tests + docs/p4_kitsendus.md).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Verdict instead of bands (OTA PR #131 precedent): the no-licence hard
  gate forbids ingestion; painting bands from unlicensed polygons would
  be fake precision AND a licence breach.
* Polygons-only, never gradients (issue conformance): the join is
  containment only; no distance-to-zone gradient is computed anywhere.
* G4 title/legal params stay documented no-map NULLs against the PAID
  register -- this open-WFS family was never probed for those verdicts,
  and zones must never be presented as encumbrance truth (reason +
  legend say so).
* Kataster parcels / EELIS zones / flood zones stay untouched cousins
  (distinct keys); #235/#491 parcel-class overlay is the pattern
  precedent (polygons-only, outside stays unknown).

Integration (deliberately NOT done here): WEIGHTS/livability/layers
rebalancing stays one joint change across all batches (existing tests pin
set(WEIGHTS) exactly).
"""

from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)


# ---------------------------------------------------------------------------
# Offline join core (pure; mirrors dims_p4_maa_subsurface join shape).
# Rings are [[lon, lat], ...] in EPSG:4326. Containment only -- no
# distance gradients on zone params.
# ---------------------------------------------------------------------------

def point_in_polygon(lon: float, lat: float,
                     ring: List[List[float]]) -> bool:
    """Ray-casting containment. Degenerate rings (< 3 distinct points) match
    nothing -- a broken polygon must not flag a parcel."""
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


def join_zone_flags(lon: float, lat: float,
                    zones: List[dict]) -> List[dict]:
    """Per-parcel zone membership: attrs of every containing zone.

    Zones are [{"attrs": {...}, "polygons": [rings]}] (WFS polygons cached
    offline after the licence gate clears). A parcel outside every polygon
    maps to [] (the scorers turn that into NULL, never "clean title").
    Non-polygon / broken geometry is skipped, never coerced.
    """
    hits = []
    for zone in zones or []:
        attrs = (zone or {}).get("attrs", {})
        polys = (zone or {}).get("polygons") or []
        if any(point_in_polygon(lon, lat, ring) for ring in polys):
            hits.append(dict(attrs))
    return hits


# ---------------------------------------------------------------------------
# Band table (APPLIES ONLY after the licence gate -- see module docstring).
# Today both scorers below return None for every input.
# ---------------------------------------------------------------------------

#: Building-ban zone families -> low band (20-35: full ban 20, setback 35).
BAN_SCORES = {"ehituskeeld": 20, "ehituskeeluvöönd": 20, "tagasilöök": 35}

#: Conditioned zone families -> mid band (50-65: heavy 50, notice-duty 65).
CONDITIONED_SCORES = {"tingimuslik": 50, "kooskõlastus": 50,
                      "teavitus": 65}


def _band_for_zone(attrs: dict) -> Optional[int]:
    """Zone-type -> band per the table above; unknown type -> None."""
    raw = str((attrs or {}).get("voond_liik_id_vaartus", "")
              or (attrs or {}).get("voond_liik_id", "")).lower()
    for key, score in BAN_SCORES.items():
        if key in raw:
            return score
    for key, score in CONDITIONED_SCORES.items():
        if key in raw:
            return score
    return None


# ---------------------------------------------------------------------------
# P4 scorers: licence-gated NULLs (OTA PR #131 precedent). Each reports the
# gap with the concrete buyer-side check instead of a faked number.
# ---------------------------------------------------------------------------

NO_LICENCE = ("KPO kitsenduste litsentsi EI OLE kinnitatud "
              "(kataloogis puudub, WFS-võimekuses 2026-09-16 litsentsi "
              "EI OLE): ühtegi tsooni EI OLE liidestatud")


def dim_restriction_zone(parcel: Optional[dict],
                         zones: Optional[List[dict]]) -> Score:
    """Restriction-zone membership leg: NULL until the licence gate clears."""
    parcel = parcel or {}
    lon, lat = parcel.get("lon"), parcel.get("lat")
    if not isinstance(lon, (int, float)) \
            or not isinstance(lat, (int, float)):
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "kitsendustsooni-liidetust ei saa arvutada -- "
                      "täienda koordinaat, ära feigi")
    if not zones:
        return None, ("Piiranguvööndite hinnangut pole (%s) -- "
                      "ehituskeeld (20-35) vs tingimuslik (50-65) "
                      "liigitus ootab loa kinnitust; väljaspool kõiki "
                      "polügoone jääks teadmata, mitte puhtaks: tsoonid "
                      "EI OLE omandiõigus -- kontrolli kinnistusraamatust "
                      "ja notarilt, ära feigi" % NO_LICENCE)
    hits = join_zone_flags(lon, lat, zones)
    if not hits:
        return None, ("Krunt pole üheski liidestatud piiranguvööndis, "
                      "aga kiht pole litsentsi tõttu laetud (%s) -- "
                      "teadmata, mitte puhas omand: kontrolli "
                      "kinnistusraamatust ja notarilt, ära feigi"
                      % NO_LICENCE)
    scored = [(h, _band_for_zone(h)) for h in hits]
    known = [(h, s) for h, s in scored if s is not None]
    if not known:
        return None, ("Krunt on piiranguvööndis tundmatu liigiga "
                      "(%s) -- hinnangut EI OLE: liigitus peab tulema "
                      "voond_liik-jalast, ära feigi; kontrolli "
                      "kinnistusraamatust ja notarilt"
                      % ", ".join(str(h.get("nimi", "?")) for h, _ in scored))
    score = min(s for _, s in known)
    names = ", ".join(str(h.get("nimi", h.get("voond_liik_id_vaartus",
                                              "?"))) for h, _ in known)
    return None, ("Krunt vööndis (%s -> skoor %d ootab litsentsi): "
                  "hinnangut EI OLE (%s) -- kontrolli kinnistusraamatust "
                  "ja notarilt, ära feigi" % (names, score, NO_LICENCE))


def dim_utility_corridor(parcel: Optional[dict],
                         corridors: Optional[List[dict]]) -> Score:
    """Tehnovõrgud corridor leg: NULL until the licence gate clears."""
    parcel = parcel or {}
    lon, lat = parcel.get("lon"), parcel.get("lat")
    if not isinstance(lon, (int, float)) \
            or not isinstance(lat, (int, float)):
        return None, ("Krundi koordinaati EI OLE (hinnang puudub): "
                      "tehnovõrgu-koridori ei saa arvutada -- täienda "
                      "koordinaat, ära feigi")
    if not corridors:
        return None, ("Tehnovõrkude (elekter/gaas/side/vesi/kaugküte) "
                      "koridori-hinnangut pole (%s) -- trasside "
                      "kaitsevööndid ootavad loa kinnitust; kontrolli "
                      "võrguettevõtjalt (Elektrilevi/vee-ettevõte) ja "
                      "kinnistusraamatust, ära feigi" % NO_LICENCE)
    hits = join_zone_flags(lon, lat, corridors)
    if not hits:
        return None, ("Krunt pole üheski liidestatud tehnovõrgu-koridoris, "
                      "aga kiht pole litsentsi tõttu laetud (%s) -- "
                      "teadmata, mitte vaba: kontrolli võrguettevõtjalt "
                      "(Elektrilevi/vee-ettevõte) ja kinnistusraamatust, "
                      "ära feigi" % NO_LICENCE)
    names = ", ".join(str(h.get("nimi", "?")) for h in hits)
    return None, ("Krunt tehnovõrgu-koridoris (%s): hinnangut EI OLE "
                  "(%s) -- kaitsevööndi ulatus võrguettevõtjalt, "
                  "koormatis kinnistusraamatust, ära feigi"
                  % (names, NO_LICENCE))


P4_KITSENDUS_DIMS = (
    ("restriction_zone", dim_restriction_zone),
    ("utility_corridor", dim_utility_corridor),
)


def score_p4_kitsendus(parcel: Optional[dict],
                       zones: Optional[List[dict]] = None,
                       corridors: Optional[List[dict]] = None) -> Dict[
                           str, Optional[int]]:
    """Both P4 kitsendus dims for one parcel (entry point for the
    weight-rebalance follow-up). Every value is None by design -- no
    licence, no ingestion, never a faked zone score."""
    return {
        "restriction_zone": dim_restriction_zone(parcel, zones)[0],
        "utility_corridor": dim_utility_corridor(parcel, corridors)[0],
    }
