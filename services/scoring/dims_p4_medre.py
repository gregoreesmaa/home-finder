"""P4 TEHIK medre primary-care proximity dims (issue #532).

Params (this module only):
* P4-011 GP half: "is my GP list open near this address / how far is the
  nearest clinic".

LIVE FEED VERDICT (checked 2026-09-16, polite one-off round, custom UA
`home-finder-research/0.1`, single GETs, no retries; aggregates only, raw
bodies never committed):
* `https://medre.tehik.ee/open-data` -> HTTP 200, 1422 B: a React SPA shell
  ("Tervishoiutootaja registrid", `/assets/index-CEBE_YUb.js`), no
  server-rendered data. Per AGENTS.md section 7.7 the shell was opened, not
  filed: static read of the bundle (~4.8 MB, two ranged GETs) names the
  keyless bulk endpoints below — no login/session flow, no paywall, no
  per-record scraping of human publications (all endpoints are the
  register's own declared open-data bulks).
* `.../api-common/public/general-practitioner-lists/open-data`
  -> HTTP 200, application/xml, 3 591 143 B, `hetk="2026-09-16T02:10:02"`
  (today: DAILY feed confirmed). 782 `<nimistu>` rows: `<kood>`, `<perearst>`
  (name), `<teeninduspiirkonnad>`, `<vastuvott><kohad><koht>` with `<adr_id>`
  (ADS address id) + `<adr_kood>` + `<adr_tekst>` (371 Harju, 289 Tallinn).
  Tag set has NO open/closed, capacity, or patient-count column anywhere
  (grep over the full 3.6 MB): the status leg closes as documented NULL
  (per-GP searchability lives in the JS UI; driving it per GP would be
  directory scraping, explicitly out).
* `.../api-common/public/companies/open-data`
  -> HTTP 200, application/xml, 14 536 762 B, `hetk="2026-09-16T02:05:08"`.
  1572 `<asutus>` rows (832 Harju/Tallinn) with `<tegevusload>` /
  `<tegevuskohad><aadress>` (plain text, no adr_id) + `<teenused>`; licence
  kinds: Eriarstiabi 1292 / Oendusabi 739 / Uldarstiabi 500 /
  Fusioteraapia 194 / Ammaemandusabi 162 / others. The Uldarstiabi
  (general-medicine) tegevuskohad are the clinic leg.
* `.../api-common/public/open-data/{companies,data,lists}/description`
  -> HTTP 200, application/pdf data dictionaries (the `lists` one 117 897 B).
  Licence: CC BY-NC-SA 3.0 per the national catalogue for BOTH datasets;
  the rendered licence line lives in the JS open-data tab (server-side
  confirmation needs JS rendering — documented boundary, never faked).
  Direct overturn path for the GP half of `kindergarten_queue_gp`
  (docs/p4_haridus.md): that check guessed a directory path and 404'd;
  this bulk was never probed.

Geocoding path (stated, counted): NEITHER bulk ships coordinates — 0 of
371 Harju GP addresses and 0 of 832 Harju provider addresses place as-is.
GP `<koht>` rows carry `<adr_id>`/`<adr_kood>` (ADS identifiers): the
honest join is adr_id -> AKS address system (same family as the EHR
precedent #136 and the ADS ids EHIS ships in #530). Company `<aadress>`
rows are plain text (AKS text join). Until an adapter owns the join,
proximity POIs are caller-supplied post-join points; unjoined rows stay
out (never invented coordinates). Reasons label the join explicitly.

Dims:
* dim_gp_proximity — nearest nimistu vastuvotukoht bands.
* dim_gp_clinic_proximity — nearest Uldarstiabi-licensed tegevuskoht bands.
* dim_gp_open_status — documented NULL: no bulk open/closed column exists
  (evidence above); the reason points at the Tervisekassa per-GP lookup.

Bands (straight-line haversine on joined points ⇒ reasons say "hinnang
(linnulennult, mitte marsruut)"): <= 500 m -> 80, <= 1 km -> 65,
<= 2 km -> 50, beyond -> NULL (never "no care", only distance; proximity
is not quality — legend must say so). Missing origin or no joined POIs of
that kind -> NULL with an EI OLE reason + buyer check.

Style mirrors services/scoring/livability.py and sibling batch
dims_p4_sportreg.py (#531): scorers are pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
nowhere in this module: the polite harvest (DAILY feed -> monthly harvest
at most) is a future adapter job; parse helpers below take bulk text.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and sibling #152).

Judgment calls (reviewable per AGENTS.md section 7.5):
* No patient data, ever: fixtures use synthetic GP names; the parse helper
  keeps names only as register metadata (the bulk publishes them), and
  reasons never name a doctor.
* Eriarstiabi/Oendusabi/etc. legs are NOT scored: primary-care scope only;
  specialist proximity belongs to a future source issue, named in
  docs/p4_medre.md as an overturn path, not scored here.
* DAILY feed, monthly harvest at most (TTL 30 d in-module): scoring never
  paints open/closed from a stale snapshot — and since no status column
  exists at all, the status dim stays NULL regardless of harvest.
* No Tervisekassa directory scraping; no quality-of-care claims.

Integration (deliberately NOT done here): no livability.OVERPASS_QUERY /
livability._POI_KIND extension, no WEIGHTS change — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling. Rebalancing stays one joint change across all batches.
"""

import math
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Proximity bands: (radius_km, score). Beyond 2 km -> NULL (distance only).
PROX_BANDS = ((0.5, 80), (1.0, 65), (2.0, 50))

#: POI kinds (caller-side contracts for AKS-joined medre points).
GP_KIND = "medre_gp"
GP_CLINIC_KIND = "medre_gp_clinic"

#: The primary-care licence kind in the companies bulk (others stay unscored).
GP_LICENCE = "Üldarstiabi"

#: Feed identity (verified 2026-09-16, all HTTP 200, same-day `hetk`).
MEDRE_OPEN_DATA_URL = "https://medre.tehik.ee/open-data"
MEDRE_GP_LISTS_URL = (
    "https://medre.tehik.ee/api-common/public/general-practitioner-lists/open-data"
)
MEDRE_COMPANIES_URL = (
    "https://medre.tehik.ee/api-common/public/companies/open-data"
)
MEDRE_USER_AGENT = (
    "home-finder-p4-medre/1.0 (Estonia open-data monthly adapter; "
    "polite single-pull, cache-first)"
)
#: DAILY feed, monthly harvest at most: cache wins inside the TTL.
MEDRE_CACHE_TTL_S = 30 * 86400
MEDRE_LICENCE = "CC BY-NC-SA 3.0 (Terviseamet via TEHIK)"


# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points (pure)."""
    r = 6371.0
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dla = math.radians(b[0] - a[0])
    dlo = math.radians(b[1] - a[1])
    h = (math.sin(dla / 2.0) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2.0) ** 2)
    return 2.0 * r * math.asin(min(1.0, math.sqrt(h)))


def _pois_of(pois: Optional[List[dict]], kind: str) -> List[dict]:
    out = []
    for p in pois or []:
        if not isinstance(p, dict) or p.get("kind") != kind:
            continue
        if p.get("lat") is None or p.get("lon") is None:
            continue
        out.append(p)
    return out


def _nearest(origin: Tuple[float, float],
             pois: List[dict]) -> Tuple[Optional[dict], Optional[float]]:
    best = None
    best_km = None
    for p in pois:
        km = haversine_km(origin, (p["lat"], p["lon"]))
        if best_km is None or km < best_km:
            best, best_km = p, km
    return best, best_km


# ---------------------------------------------------------------------------
# Pure offline readers (hermetic; parse harvested bulk text, no network).
# Neither bulk ships coordinates: readers extract the AKS-joinable address
# references (GP adr_id) / text addresses (companies) with counts; the
# adapter joins them via AKS, unjoined rows stay out.
# ---------------------------------------------------------------------------

def _xtext(el: Optional[ET.Element], tag: str) -> str:
    if el is None:
        return ""
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def parse_nimistud_xml(text: str) -> Tuple[List[dict], dict]:
    """Parse the GP-lists bulk into joinable reception points (pure).

    One dict per <koht> (reception address): nimistu + ADS address refs,
    NO coordinates (the feed ships none). Returns (points, stats).
    """
    root = ET.fromstring(text)
    points: List[dict] = []
    stats = {"nimistu": 0, "kohad": 0, "harju_kohad": 0, "with_coords": 0}
    for nim in root.iter("nimistu"):
        stats["nimistu"] += 1
        code = _xtext(nim, "kood")
        piirkonnad = [p.text.strip() for p in
                      nim.findall("./teeninduspiirkonnad/teeninduspiirkond/nimi")
                      if p.text and p.text.strip()]
        for koht in nim.findall("./vastuvott/kohad/koht"):
            addr = _xtext(koht, "adr_tekst")
            points.append({
                "nimistu": code,
                "adr_id": _xtext(koht, "adr_id"),
                "adr_kood": _xtext(koht, "adr_kood"),
                "address": addr,
                "piirkonnad": piirkonnad,
            })
            stats["kohad"] += 1
            if addr.startswith("Harju maakond") or ", Tallinn" in addr:
                stats["harju_kohad"] += 1
    return points, stats


def parse_companies_xml(text: str) -> Tuple[List[dict], dict]:
    """Parse the providers bulk into Üldarstiabi activity sites (pure).

    One dict per <tegevuskoht> under an Üldarstiabi <tegevusluba>: plain
    text address + service names, NO coordinates, NO adr_id. Other licence
    kinds are counted, never scored. Returns (points, stats).
    """
    root = ET.fromstring(text)
    points: List[dict] = []
    stats = {"asutus": 0, "harju_asutus": 0, "uldarstiabi_kohad": 0,
             "other_licences": 0, "with_coords": 0}
    for asutus in root.iter("asutus"):
        stats["asutus"] += 1
        name = _xtext(asutus, "nimi")
        reg = _xtext(asutus, "registrikood")
        if "Harju maakond" in (_xtext(asutus, "aadress")) or "Tallinn" in (
                _xtext(asutus, "aadress")):
            stats["harju_asutus"] += 1
        for luba in asutus.findall("./tegevusload/tegevusluba"):
            if _xtext(luba, "loaliik_nimi") != GP_LICENCE:
                stats["other_licences"] += 1
                continue
            for koht in luba.findall("./tegevuskohad/tegevuskoht"):
                addr = _xtext(koht, "aadress")
                points.append({
                    "asutus": name, "registrikood": reg,
                    "licence": _xtext(luba, "tegevusloa_number"),
                    "address": addr,
                    "teenused": [_xtext(t, "nimi") for t in
                                 koht.findall("./teenused/teenus")],
                })
                stats["uldarstiabi_kohad"] += 1
    return points, stats


# ---------------------------------------------------------------------------
# Scorers: AKS-joined register proximity bands, NULL beyond 2 km; the
# open/closed leg is a documented NULL (no bulk column exists).
# ---------------------------------------------------------------------------

def _band_score(km: float) -> Optional[int]:
    for radius, pts in PROX_BANDS:
        if km <= radius:
            return pts
    return None


def _slice_dim(kind: str, label: str, check: str,
               origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    mine = _pois_of(pois, kind)
    if not origin:
        return None, ("%s teadmata (EI OLE hinnangut): aadress puudub — "
                      "medre registri vastuvotukohtade kaugus selgub aadressi "
                      "puhvrist, mitte tühjalt" % label)
    if not mine:
        return None, ("%s teadmata (EI OLE hinnangut): hetktõmmises pole "
                      "uhtki AKS-liidetud %s vastuvotukohta (register ise "
                      "koordinaate ei kanna — liitmine AKS-ist; liitmata read "
                      "valjas) — %s; kaugemal kui 2 km pole samuti hinnet, "
                      "ainult kaugus (lähedus ei ole kvaliteet, ära feigi)"
                      % (label, label.lower(), check))
    nearest, km = _nearest(origin, mine)
    assert nearest is not None and km is not None
    score = _band_score(km)
    if score is None:
        return None, ("%s kaugemal kui 2 km (EI OLE hinnet, ainult kaugus): "
                      "lähim AKS-liidetud registri vastuvotukoht on %.1f km "
                      "linnulennult (hinnang, mitte marsruut) — %s"
                      % (label, km, check))
    return score, ("%s: lähim AKS-liidetud registri vastuvotukoht %s on "
                   "%.1f km linnulennult (hinnang, mitte marsruut-aeg) — "
                   "kauguse, mitte kvaliteedi hinne; %s"
                   % (label, nearest.get("address") or "teadmata", km, check))


def dim_gp_proximity(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Score:
    """P4-011 GP slice: nearest nimistu vastuvotukoht (AKS-joined) bands."""
    return _slice_dim(GP_KIND, "Lähim perearsti vastuvott",
                      "kontrolli nimistu avatust Tervisekassa otsingust",
                      origin, pois)


def dim_gp_clinic_proximity(origin: Optional[Tuple[float, float]],
                            pois: Optional[List[dict]]) -> Score:
    """P4-011 clinic slice: nearest Uldarstiabi tegevuskoht bands."""
    return _slice_dim(GP_CLINIC_KIND, "Lähim üldarstiabi tegevuskoht",
                      "kontrolli vastuvotuaegu asutuse kodulehelt",
                      origin, pois)


def dim_gp_open_status(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """P4-011 open/closed leg: documented NULL — no bulk column exists."""
    return None, ("Nimistu avatus teadmata (EI OLE hinnangut): medre avaandmete "
                  "koondfailis (nimistud + asutused, 2026-09-16 hetk) pole "
                  "avatud/suletud, vabade kohtade ega patsientide veergu — "
                  "kontrolli oma nimistu avatust Tervisekassa "
                  "perearsti-otsingust; registri UI pohine uksikparingu "
                  "ajamine oleks kataloogi kraapimine, mitte voo lugemine "
                  "(valjas), ara feigi")


P4_MEDRE_DIMS = (
    ("gp_proximity", "P4-011", dim_gp_proximity),
    ("gp_clinic_proximity", "P4-011", dim_gp_clinic_proximity),
    ("gp_open_status", "P4-011", dim_gp_open_status),
)


def score_p4_medre(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All three P4 medre dims for one listing (entry point for the
    weight-rebalance follow-up; keys match P4_MEDRE_DIMS). The open-status
    value is None by design — no bulk column exists, never a faked flag."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_MEDRE_DIMS}
