"""P4 notice-watch scorer dims from Ametlikud Teadaanded open data (issue #550).

Early-warning feed for the pending pipeline: quarry/mining licence
applications, zoning (detailplaneering) hearings, cadastre notices.
Complements the Group-5 activity/stock proxies (adopted state) with the
announcement side (dates + applicants + parcels) and the dims_p4_ata
developer-track slice (different notice types, disjoint dim keys).

OPENNESS VERDICT (polite probes, 2026-09-16, custom UA, /tmp/hf550_*):
* https://andmed.eesti.ee/datasets/ametlike-teadaannete-avaandmed
  -> HTTP 200, 75497 bytes, Angular JS shell (12 chars visible text,
  no server-rendered distribution/API URL). Full bundle dig would cost
  many GETs, so the catalogue leg stops here per the polite budget.
* https://www.ametlikudteadaanded.ee/avalik/uriotsing -> HTTP 200,
  152268 bytes. The machine interface IS this page's documented URI
  scheme (same scheme dims_p4_ata pulls stand-alone notices from):
  /ee/{andmeandja}/{pealiik}/{alaliik}/{aasta}/{kuu}/{paev}/
  {teate_number}/{xml}. Dropping trailing components lists notices;
  appending "xml" returns an XML koondfail (aggregate) of every notice
  under the filled components. 1000-result cap per search. No auth.
  Publisher: Ministry of Justice and Digital Affairs, CC BY-SA 4.0.
* Taxonomy observed in the page (pealiik -> alaliik slugs, buyer
  relevant): keskkonnaluba -> kaevandamisloa-* (grant/amend/procedure/
  auction), keskkonnaloa-* (grant/draft/procedure); planeeringud ->
  detailplaneeringu-algatamine / -kehtestamine /
  -osalise-kehtetuks-tunnistamine; maakatastri-teated ->
  maakatastri-teade. Felling: NO mandatory AT channel exists — the
  only forest hit is metsa-raieoiguse-ja-metsamaterjali-myyk (sale of
  felling rights/timber, a commercial notice, not a felling permit);
  metsateatis goes to the Forest Register, not AT. The felling leg is
  therefore documented no-map (NULL with reason), not scored.
* Location fields: NONE structured. The URI components carry only
  publisher/type/date/number; the notice XML schema (per dims_p4_ata)
  carries teate_number, liik, andmeandja, puudutatud_isik, dates,
  kinnitatud_sisu, sisendid — location, if present at all, is free
  text inside sisendid/kinnitatud_sisu. No parcel number, address id,
  or coordinate field exists. Measured linkage rate over structured
  fields: 0 locatable / total (linkage_rate pins this). Unlocatable
  notices stay out (counted) per the issue contract.

HONESTY (AGENTS.md 7.2): every dim scores ONLY joined parcel-linked
records. No joined pull -> NULL. Joined but parcel_linked False ->
NULL (counted as unlocatable). Expired (archived, or published more
than NOTICE_TTL_MONTHS ago) -> NULL, never scored. An announcement is
not an approval — every scored reason says so. Clean (joined pull,
zero in-scope notices) is weak-good capped at CLEAN_CAP (never 100):
the 1000-result cap means a wide query may truncate, and each clean
reason names the queried window. Applicants are never named in
reasons (notice-type stats + parcel links only, no person scoring).

Style mirrors dims_p4_ata.py: pure (notice/listing) -> Score dicts,
absolute bands, hermetic fixture tests. Network lives only in
fetch_bulk_xml (single polite GET, file cache, weekly TTL — notices
move slowly; issue caps harvest at weekly). Tests never call it.
"""

import os
import time
import urllib.request
from datetime import date
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Weekly harvest at most: notices move slowly (issue constraint).
NOTICE_TTL_DAYS = 7

#: Notices older than this are expired -> NULL, never scored.
NOTICE_TTL_MONTHS = 12

#: Weak-good cap for a clean joined window (never 100: cap + truncation).
CLEAN_CAP = 70

AT_BASE_URL = "https://www.ametlikudteadaanded.ee"

USER_AGENT = ("home-finder notices ingest (polite weekly pulls, single GET, "
              "file cache; contact via GitHub home-finder)")

#: Buyer-relevant pealiik -> scored alaliik slugs (observed 2026-09-16).
#: Felling is deliberately absent: no mandatory AT channel (see docstring).
NOTICE_TAXONOMY: Dict[str, Dict[str, str]] = {
    "keskkonnaluba": {
        "kaevandamisloa-andmine-voi-muutmine": "quarry",
        "kaevandamisloa-eelnou-avalikustamine": "quarry",
        "kaevandamisloa-menetluse-algatamine": "quarry",
        "kaevandamisloa-saamise-enampakkumine": "quarry",
        "keskkonna-andmise-voi-andmisest-keeldumise-teade": "quarry",
        "keskkonnaloa-eelnou-avalikustamise-teade": "quarry",
        "keskkonnaloa-menetluse-algatamise-teade": "quarry",
    },
    "planeeringud": {
        "detailplaneeringu-algatamine": "zoning",
        "detailplaneeringu-kehtestamine": "zoning",
        "detailplaneeringu-osalise-kehtetuks-tunnistamine": "zoning",
    },
    "maakatastri-teated": {
        "maakatastri-teade": "cadastre",
    },
}

#: Distance bands in metres per notice family (issue contract).
DISTANCE_BAND_M = {"quarry": 1000, "zoning": 1000, "cadastre": 500}

#: Score per family for an active, linked, in-band notice.
FAMILY_SCORE = {"quarry": 35, "zoning": 55, "cadastre": 60}

_KIND_ET = {"quarry": "karjääri-/kaevandamisloa teadaanne",
            "zoning": "detailplaneeringu teadaanne",
            "cadastre": "maakatastri teadaanne"}


# ---------------------------------------------------------------------------
# Ingestion: polite, cached, TTL-stated AT bulk-XML pulls.
# ---------------------------------------------------------------------------

def build_bulk_url(publisher: str, pealiik: str,
                   alaliik: Optional[str] = None) -> str:
    """One AT bulk-list URL per the documented URI scheme (+xml koondfail)."""
    parts = [AT_BASE_URL, "ee", publisher, pealiik]
    if alaliik:
        parts.append(alaliik)
    parts.append("xml")
    return "/".join(parts)


def _cache_path(cache_dir: str, url: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in url)
    return os.path.join(cache_dir, "notices-%s.xml" % safe[-120:])


def cache_is_fresh(path: str, ttl_days: int = NOTICE_TTL_DAYS,
                   now: Optional[float] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        age_days = ((now if now is not None else time.time())
                    - os.path.getmtime(path)) / 86400.0
    except OSError:
        return False
    return age_days < ttl_days


def fetch_bulk_xml(url: str, cache_dir: str = "/tmp/hf-cache",
                   ttl_days: int = NOTICE_TTL_DAYS) -> str:
    """Fetch one AT bulk XML politely (single GET, cached, TTL-stated).

    Returns cached text when fresh; otherwise one GET with a polite
    User-Agent and a 30 s timeout. Transport errors RAISE (never cached
    as data); HTTP 429 propagates (stop signal, AGENTS.md 7.4).
    """
    os.makedirs(cache_dir, exist_ok=True)
    path = _cache_path(cache_dir, url)
    if cache_is_fresh(path, ttl_days):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


# ---------------------------------------------------------------------------
# Pure scoring on joined records.
# ---------------------------------------------------------------------------

def classify_notice(pealiik: str, alaliik: str) -> Optional[str]:
    """Notice family (quarry/zoning/cadastre) or None when out of scope."""
    return NOTICE_TAXONOMY.get(pealiik, {}).get(alaliik)


def is_expired(published: date, archived: Optional[date],
               today: Optional[date] = None) -> bool:
    """Expired when archived, or published more than 12 months ago."""
    today = today or date.today()
    if archived is not None:
        return True
    age_days = (today - published).days
    return age_days > NOTICE_TTL_MONTHS * 30 + 5


def linkage_rate(notices: List[dict]) -> Tuple[int, int]:
    """(locatable, total): structured parcel linkage is never present.

    Kept as a function (not a constant) so the harvest PR can re-point
    it at real pulls; the zero today is measured, not assumed.
    """
    total = len(notices)
    locatable = sum(1 for n in notices if n.get("parcel_linked"))
    return locatable, total


def dim_notice_watch(origin: Optional[Tuple[float, float]],
                     pull: Optional[dict],
                     today: Optional[date] = None) -> Score:
    """Early-warning flag from joined parcel-linked AT notices.

    pull: None (no joined pull), or {"notices": [notice, ...]} where a
    notice is {"pealiik", "alaliik", "published" (date),
    "archived" (date|None), "distance_m" (float|None),
    "parcel_linked" (bool), "teate_number" (str)}.
    Worst active in-band linked notice wins; expired/unlinked stay out.
    """
    today = today or date.today()
    if pull is None:
        return (None, "Teadaannete seos puudub (hinnang EI OLE): "
                "Ametlike Teadaannete väljavõtet ei ole liidetud.")
    notices = pull.get("notices", []) if isinstance(pull, dict) else []
    if not notices:
        return (CLEAN_CAP, "Lähikonna teadaandeaknas teateid ei ole "
                "(nõrk hea, ei ole tõend puhtast tiitlist: teadaanne "
                "ei ole heakskiit; päringut piirab 1000 tulemust).")
    scored: List[Tuple[int, str, str]] = []
    unlocatable = 0
    for n in notices:
        kind = classify_notice(n.get("pealiik", ""), n.get("alaliik", ""))
        if kind is None:
            continue
        if not n.get("parcel_linked"):
            unlocatable += 1
            continue
        pub = n.get("published")
        if pub is None or is_expired(pub, n.get("archived"), today):
            continue
        dist = n.get("distance_m")
        band = DISTANCE_BAND_M[kind]
        if dist is None or dist > band:
            continue
        scored.append((FAMILY_SCORE[kind], kind, str(n.get("teate_number", "?"))))
    if not scored:
        extra = ("; %d teadet ilma asukohaseoseta (loendamata jäetud)"
                 % unlocatable) if unlocatable else ""
        return (None, "Hinnatavaid sidusaid teadaandeid ei ole "
                "(hinnang EI OLE): aegunud/väljaspool teadaanded "
                "ei lähe arvesse%s." % extra)
    scored.sort()
    score, kind, num = scored[0]
    return (score, "%s %dm raadiuses (teadaanne nr %s): varajane "
            "hoiatus, teadaanne ei ole heakskiit."
            % (_KIND_ET[kind], DISTANCE_BAND_M[kind], num))


def dim_felling_watch(origin: Optional[Tuple[float, float]],
                      pull: Optional[dict]) -> Score:
    """Felling-notice leg: documented no-map NULL (no mandatory AT channel)."""
    return (None, "Raieteateid Ametlikes Teadaannetes ei ole (hinnang "
            "EI OLE): metsateatis läheb metsaregistrisse, kontrolli "
            "metsaportaali / küsi KOV-ist.")


P4_NOTICES_DIMS = {
    "notice_watch": ("Teadaandevalve (AT)", dim_notice_watch),
    "felling_watch": ("Raieteadete kontroll (NULL)", dim_felling_watch),
}

P4_NOTICES_PARAM_IDS = {"notice_watch": 550, "felling_watch": 550}


def score_p4_notices(origin: Optional[Tuple[float, float]],
                     pull: Optional[dict],
                     today: Optional[date] = None) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """Roll up the notice-watch dims; NULL dims contribute no reasons."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    watched, watch_reason = dim_notice_watch(origin, pull, today)
    dims["notice_watch"] = watched
    if watched is not None:
        reasons.append(watch_reason)
    dims["felling_watch"] = None
    return dims, reasons
