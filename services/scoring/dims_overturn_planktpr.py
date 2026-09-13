"""Overturn dims for issue #236: PLANK/TPR per-parcel joins (p47/p74) + p274 ceiling partial.

Params (this module only — sibling legs untouched, see the scope guard):
* p47  zoning laws (parameters3.md section 5.5, Group 5): per-parcel
  designated-use join off the PLANK/TPR snapshot (kehtestatud decree only).
* p74  rental restrictions (parameters3.md section 5.5, Group 5):
  per-parcel restriction-decree join off the same snapshot.
* p274 air rights (parameters3.md section 5.4, Group 4): PARTIAL ONLY —
  the plan's max-height per parcel as a ceiling proxy for development
  rights above, with soft caps (never above 65, never below 55). The deed
  clause itself (who owns the air) stays NULL by construction: the
  e-Kinnistusraamat extract is Tier 2 PAID with no open bulk, so no
  ceiling number can ever prove or block the right.

OPENNESS VERDICT (re-verified 2026-09-13, 7 tiny polite requests, custom
UA, >= 3 s pacing, headers + SPA-shell scope only, no scrape; raw bodies
at /tmp/hf-236-planktpr/, never committed — full log docs/overturn_planktpr.md):
* HEAD https://planeeringud.ee/ -> HTTP 301 (Apache/ZoneOS) to
  https://livekluster.ehr.ee/ui/ehr/v1/detailsearch/PLANNINGS_SEARCH
* HEAD https://planeeringud.ee/geoserver/wfs -> same HTTP 301: the
  documented OGC WFS 2.0.0 base from parameters3.md Group 5 no longer
  serves WFS — it redirects to the E-ehitus platform SPA.
* GET .../geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities
  (redirects followed) -> HTTP 200 text/html, the E-ehitus SPA shell
  ("e-ehituse platvorm") — NO WFS XML, no GetCapabilities document.
* HEAD https://tpr.tallinn.ee/ -> HTTP 200, Apache, 83 331 B SPA shell
  ("Tpr"); first 16 kB of the shell carry no wfs/bulk/api/download link.
So the live path below is honest plumbing with NO live data: the fetcher
performs NO request while OVERTURN_BULK_URL is None, every scorer returns
None without a snapshot join, and the scored shapes are proven on
fixtures only. Dated negative keeps verdicts per the #236 RULE.

HONESTY (AGENTS.md section 7.2): the scored dims say "hinnang"
(estimate) and print their components (parcel, decree values, snapshot
date); every NULL reason says "EI OLE" and names the missing input.
Transport errors are never cached as data (the fetcher stores a body
only on HTTP 200 with JSON content, else returns None). A measured
join from the snapshot (parcel row present: restriction False scores,
ceiling known scores within the soft caps) is a real signal — while a
missing join (no snapshot, parcel absent, stage not kehtestatud,
unverified use code) stays NULL: absence of data is unknown, never
good. Exact-parcel joins only (katastritunnus key): never a distance
gradient, never interpolation (same discipline as dims_p4_maa_kataster).

FAKE-PRECISION GUARDS (pinned by tests):
* OSM landuse=* stays OUT of p47: it is descriptive (what is built),
  never the prescriptive PLANK/TPR decree (group05a precedent). This
  module takes no OSM tags and stages no Overpass fragment.
* p74 counts decree rows only: tourism=apartment supply stays OUT
  (group05a: 25 objects are supply, not restriction).
* p274 never issues the deed verdict: the ceiling proxy cannot prove
  the right (cap 65) nor block the deal (floor 55); the reason always
  points at the kinnistusraamat extract.

Ingestion (stdlib only, offline-first):
* fetch_overturn_snapshot(cache_dir): polite pull, max 1 download / 14 d
  per cache dir (OVERTURN_TTL_S; parameters3.md section 5.5 cadence:
  bi-weekly scraping of active detailed plans). Cache hit within TTL
  performs NO request. While no open bulk endpoint exists
  (OVERTURN_BULK_URL is None) it performs no request at all and returns
  the fresh-cache path or None. Single GET with an identifying UA once a
  bulk URL is known, no retries (HTTP 429 is a stop signal, 7.4).
* parse_overturn_snapshot / parcels_to_index: pure offline readers over
  the cached JSON snapshot (schema documented below). Network lives ONLY
  in fetch_overturn_snapshot; scorers and tests never touch it.

Snapshot schema (what a future adapter would store; fixtures match it):
  {"parcels": [{"parcel_id": str (katastritunnus-style exact key),
                "kov": str,
                "designated_use": str | None (plan use code),
                "use_stage": str | None ("kehtestatud" joins, else NULL),
                "max_height_m": float | None (allowed ceiling from plan),
                "rental_restriction": bool | None,
                "decree_ref": str | None}]}
Malformed rows are skipped, never faked; non-Tallinn kov rows are
skipped (Tallinn filter — TPR is Tallinn-only and PLANK is national,
same call as the dims_p4_plank sibling); a missing/unparseable file
parses to None (unknown), never to an empty snapshot.

Style mirrors services/scoring/dims_p4_maa_kataster.py (#245/#329, the
per-parcel-join precedent): pure scorers (parcel_id, index) ->
(Optional[int 0..100], Estonian reason), local helpers (no livability
import — importing it here would turn the future central hook into a
cycle, same precedent as PRs #100/#106/#115).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Only use_stage == "kehtestatud" (case-insensitive) joins: a
  menetluses/eelnõu use label is not the decree — non-decree rows stay
  NULL naming the stage, conservative by design.
* designated-use bands are a first-cut judgment on UNVERIFIED code
  spellings (no live codelist exists to check against): residential-only
  -> 80, mixed with housing -> 60, commercial-only -> 35 (parameters3.md
  Illegal-Land-Use edge case: arimaa flags financing restrictions +
  commercial land tax, named in the reason), restricted (industrial /
  agricultural / special) -> 20, anything unrecognised -> NULL (an
  unverified codelist is never assumed). Cap 80: plan conditions beyond
  the use label are unknown from this table alone. The use-stem sets
  MUST be verified against the live PLANK codelist on reopen
  (docs/overturn_planktpr.md checklist).
* p74 restriction present scores 30 (restriction named via decree_ref;
  the parameters3 "Abort deal if missing" abort itself belongs to the
  deal layer, never to a dim). Covered parcel with restriction False
  scores 80 measured-clear, snapshot-dated (cap 80: decree texts beyond
  the snapshot are unknown). rental_restriction None stays NULL.
* p274 soft-cap band (first cut, MUST be recalibrated): ceiling <= 9 m
  -> 55, <= 25 m -> 60, above -> 65. Garbage (bool/NaN/<= 0) stays NULL.
* Tallinn filter matches kov case-insensitively against
  {"tallinn", "tallinna linn"} (PLANK municipal naming varies across
  register exports, same call as the dims_p4_plank sibling). Rows with a
  missing/unparseable kov are skipped: an unknown municipality is never
  assumed to be Tallinn.
* Scope guard (no double-scoring, no overlap): this module scores ONLY
  the parameters3 p47/p74/p274 per-parcel joins with _overturn-suffixed
  dim keys. Untouched: dims_group05*.py (canonical p45/p47/p74 NULLs +
  p42/p44 proxies), dims_group04.py (canonical p274 deed NULL),
  dims_p4_plank.py (P4-006 PLANK pipeline leg), dims_p4_tpr.py (P4-006 /
  P4-005 / P4-050 TPR legs), dims_p4_maa_kataster.py (P4-004 KKIS
  restriction leg — per-parcel restriction DETAIL stays its leg; this
  module reads only the planning decree feed).

Integration (deliberately NOT done here): wiring the snapshot into a
listing pipeline plus rebalancing livability.WEIGHTS must be one joint
change across all batches — existing tests pin set(WEIGHTS) exactly,
so per-batch WEIGHTS edits would break every sibling. No shared files
touched: 3 new files only (this module, its test, docs/overturn_planktpr.md).
"""

import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Hunt verdict date (2026-09-13) — the day the polite probes above ran.
VERDICT_DATE = "2026-09-13"

#: Re-check the PLANK WFS + TPR bulk surfaces no later than this date.
RECHECK_AFTER = "2027-03-13"

# ---------------------------------------------------------------------------
# Ingestion contract: source, politeness, cache.
# ---------------------------------------------------------------------------

#: Documented PLANK WFS base (parameters3.md Group 5; verified 2026-09-13:
#: HTTP 301 to the E-ehitus SPA — the WFS itself is gone, see docstring).
PLANK_WFS_URL = "https://planeeringud.ee/geoserver/wfs"

#: Human TPR register (verified 2026-09-13: HTTP 200 Angular SPA, no bulk).
TPR_INDEX_URL = "https://tpr.tallinn.ee/"

#: Open per-parcel bulk endpoint (designated-use + max-height + decree
#: rows): NONE found 2026-09-13 (dated negative, see module docstring).
#: Stays None until the reopening checklist in docs/overturn_planktpr.md
#: names a verified bulk URL; while None, fetch performs no requests.
OVERTURN_BULK_URL: Optional[str] = None

#: Max one download per 14 d per cache dir (parameters3.md section 5.5:
#: bi-weekly scraping of active detailed plans). Stated TTL.
OVERTURN_TTL_S = 14 * 24 * 3600

#: Snapshot filename inside the cache dir.
CACHE_FILENAME = "overturn-planktpr-snapshot.json"

#: Identifying user agent for the polite pull (no scrape, single GET).
OVERTURN_UA = "home-finder overturn-planktpr (max 1 req/14d, no scrape)"

#: Plan stage that counts as the decree (parameters3.md Group 5 wording).
DECREE_STAGE = "kehtestatud"

#: Tallinn kov spellings accepted by the Tallinn filter (lowercased).
TALLINN_KOVS = frozenset({"tallinn", "tallinna linn"})


def fetch_overturn_snapshot(cache_dir: str,
                            ttl_s: int = OVERTURN_TTL_S,
                            bulk_url: Optional[str] = OVERTURN_BULK_URL,
                            ) -> Optional[str]:
    """Polite per-parcel planning snapshot pull with a stated TTL.

    Cache hit (fresh mtime within ttl_s): NO request is made. Otherwise,
    with no known bulk endpoint (bulk_url None) it returns None WITHOUT
    any request — the dated negative stays an explicit code path, not a
    hidden assumption. With a bulk URL: one GET with OVERTURN_UA and a
    30 s timeout; the body is stored only on HTTP 200 with JSON content,
    else None is returned and nothing is cached (transport errors are
    never data). No retries — HTTP 429/errors are a stop signal. The
    scorers never call this; tests cover the cache-hit and no-endpoint
    paths with a stubbed opener, never the network.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, CACHE_FILENAME)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    if bulk_url is None:
        return None
    try:
        req = urllib.request.Request(bulk_url, headers={"User-Agent": OVERTURN_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            ctype = resp.headers.get("Content-Type", "")
            if status != 200 or "json" not in ctype:
                return None
            body = resp.read()
        try:
            json.loads(body)
        except ValueError:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached snapshot (pure; fixtures match schema).
# ---------------------------------------------------------------------------

def parse_overturn_snapshot(path: str) -> Optional[dict]:
    """Read a cached per-parcel planning snapshot file. Offline, stdlib.

    Returns {"parcels": [...]} with malformed rows skipped, or None when
    the file is missing/unparseable (unknown, never an empty snapshot —
    the scorers must not read "no file" as "no restrictions").
    """
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    parcels = raw.get("parcels") if isinstance(raw.get("parcels"), list) else []
    return {"parcels": [r for r in parcels if isinstance(r, dict)]}


def normalise_id(raw) -> Optional[str]:
    """Parcel join key when honest, else None (whitespace-collapsed)."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().split())
    return key or None


def normalise_text(raw) -> Optional[str]:
    """Lowercased whitespace-collapsed text, or None when empty."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or None


def _is_tallinn(row: dict) -> bool:
    """True when the row's kov is a recognised Tallinn spelling."""
    kov = normalise_text(row.get("kov"))
    return kov in TALLINN_KOVS if kov else False


def parcels_to_index(parcels: List[dict]) -> Dict[str, dict]:
    """Parcel rows -> {parcel_id: row} exact-join index. Pure.

    Non-Tallinn kov rows and rows without an honest parcel id stay out
    (unknown municipality is never assumed local; an unkeyed row can
    never join). Later rows win on duplicate ids; duplicates are a
    feed bug the adapter must fix, never a scorer crash.
    """
    index: Dict[str, dict] = {}
    for row in parcels:
        if not isinstance(row, dict) or not _is_tallinn(row):
            continue
        kid = normalise_id(row.get("parcel_id"))
        if kid is None:
            continue
        index[kid] = row
    return index


def snapshot_to_index(snapshot: Optional[dict]) -> Dict[str, dict]:
    """Parsed snapshot (or None) -> exact-join index for all three dims."""
    if not isinstance(snapshot, dict):
        return {}
    parcels = snapshot.get("parcels")
    if isinstance(parcels, list):
        return parcels_to_index(parcels)
    return {}


# ---------------------------------------------------------------------------
# Shared join guard (exact parcel key; missing join is unknown, never good).
# ---------------------------------------------------------------------------

def _join(parcel_id: Optional[str],
          index: Optional[Dict[str, dict]],
          ) -> Tuple[Optional[str], Optional[dict], Optional[Score]]:
    """Return (kid, row, null_score): null_score is set when no join."""
    kid = normalise_id(parcel_id)
    if kid is None:
        return None, None, (None, ("Krundi tunnust EI OLE (hinnang puudub): "
                                   "planeeringu-liide vajab katastritunnust "
                                   "— tee Maainfo/KKIS päring aadressi järgi, "
                                   "ära feigi"))
    if index is None:
        return kid, None, (None, ("Planeeringute hetktõmmist krundi %s kohta "
                                  "EI OLE (hinnang puudub): PLANK-WFS-liidest "
                                  "pole, TPR on veebivaade — kontrolli "
                                  "planeeringute registrist, ära feigi") % kid)
    row = index.get(kid)
    if not isinstance(row, dict):
        return kid, None, (None, ("Krundi %s planeeringuridu hetktõmmis EI "
                                  "OLE (hinnang puudub): liidese puudumine ei "
                                  "ole puhas otsus — kontrolli planeeringute "
                                  "registrist, ära feigi") % kid)
    return kid, row, None


# ---------------------------------------------------------------------------
# p47: designated-use join (kehtestatud decree only).
# ---------------------------------------------------------------------------

#: Use-code stems for the FIRST-CUT bands below. UNVERIFIED against any
#: live codelist (none is openly served) — MUST be checked against the
#: live PLANK codelist on reopen. Anything unrecognised stays NULL.
_RESIDENTIAL_STEMS = ("elamu", "eluhoon", "elamupiirkond")
_MIXED_STEMS = ("sega", "segafunktsioon")
_COMMERCIAL_STEMS = ("ari", "buroo", "kaubandus", "teenindus")
_RESTRICTED_STEMS = ("toostus", "tootmis", "maatulundus", "pollu",
                     "transpordi", "eriotstarb", "kaitsev", "jaatme",
                     "ladu", "logistika")


def classify_use(use: Optional[str]) -> Optional[str]:
    """Designated-use code -> residential|mixed|commercial|restricted|None.

    Pure, stem-ordered, conservative: commercial-only before residential
    would misread housing-mixed codes, so mixed patterns (incl. commercial
    + housing stems together) win over pure commercial; restricted stems
    win over everything (a tootmis- prefix is never housing); unknown
    codes return None (never assumed). Estonian diacritics are folded
    to ASCII before matching (see _fold()), so "ärimaa" and "arimaa"
    classify identically.
    """
    code = _fold(use)
    if not code:
        return None
    if any(s in code for s in _RESTRICTED_STEMS):
        return "restricted"
    has_housing = any(s in code for s in _RESIDENTIAL_STEMS)
    has_commerce = any(s in code for s in _COMMERCIAL_STEMS)
    if has_housing and has_commerce:
        return "mixed"
    if any(s in code for s in _MIXED_STEMS):
        return "mixed"
    if has_commerce:
        return "commercial"
    if has_housing:
        return "residential"
    return None


def _fold(raw) -> Optional[str]:
    """Lowercase ASCII-folded code for stem matching (estonian dia out)."""
    code = normalise_text(raw)
    if not code:
        return None
    return (code.replace("ä", "a").replace("ö", "o")
                .replace("ü", "u").replace("õ", "o").replace("ž", "z")
                .replace("š", "s"))


#: First-cut fit bands for a kehtestatud residential purchase. Cap 80:
#: plan conditions beyond the use label are unknown from this table
#: alone. MUST be recalibrated from a real snapshot on reopen.
USE_BANDS = {"residential": 80, "mixed": 60, "commercial": 35,
             "restricted": 20}


def dim_zoning_use(parcel_id: Optional[str],
                   index: Optional[Dict[str, dict]],
                   snapshot_date: Optional[str] = VERDICT_DATE) -> Score:
    """p47: designated-use fit for a residential purchase (high = fits).

    Exact-parcel join: only a kehtestatud row with a recognised use code
    scores. Non-decree stages, unknown codes, and missing joins stay NULL
    (unknown, never good). OSM landuse is never consulted.
    """
    kid, row, null = _join(parcel_id, index)
    if null is not None or row is None or kid is None:
        assert null is not None
        return null
    stage = normalise_text(row.get("use_stage"))
    if stage != DECREE_STAGE:
        return None, ("Sihtotstarbe määrust krundi %s kohta EI OLE "
                      "(hinnang puudub): rea plaani etapp on '%s', mitte "
                      "'%s' — menetluses silt ei ole määrus, kontrolli "
                      "planeeringute registrist"
                      % (kid, stage or "teadmata", DECREE_STAGE))
    cls = classify_use(row.get("designated_use"))
    if cls is None:
        return None, ("Sihtotstarbe kood '%s' (krunt %s) EI OLE "
                      "tunnustatud koodiloendis (hinnang puudub): "
                      "tundmatut koodi ei eelda elamuks — kontrolli "
                      "planeeringute registrist"
                      % (row.get("designated_use"), kid))
    s = USE_BANDS[cls]
    dated = "hetktõmmis %s" % snapshot_date if snapshot_date else "hetktõmmis"
    if cls == "commercial":
        return s, ("Sihtotstarve (hinnang, %s): krunt %s on '%s' "
                   "(kehtestatud) — ärimaa tõstatab finantseerimispiiranguid "
                   "ja kõrgemat ärimaa maksu → skoor %d: nõua pangalt ja "
                   "notarilt kinnitust enne pakkumist"
                   % (dated, kid, row.get("designated_use"), s))
    if cls == "restricted":
        return s, ("Sihtotstarve (hinnang, %s): krunt %s on '%s' "
                   "(kehtestatud) — elamiseks sobimatu tsoon → "
                   "skoor %d: kontrolli kasutusotstarvet planeeringute "
                   "registrist ja KOV-ist"
                   % (dated, kid, row.get("designated_use"), s))
    return s, ("Sihtotstarve (hinnang, %s): krunt %s on '%s' "
               "(kehtestatud, %s) → skoor %d"
               % (dated, kid, row.get("designated_use"), cls, s))


# ---------------------------------------------------------------------------
# p74: restriction-decree join.
# ---------------------------------------------------------------------------

#: Restriction present: low score naming the decree (the deal-layer abort
#: itself is never a dim's job). First cut, MUST be recalibrated.
RESTRICTION_PRESENT_SCORE = 30

#: Covered parcel with restriction False: measured clear, snapshot-dated.
#: Cap 80: decree texts beyond the snapshot are unknown.
NO_RESTRICTION_SCORE = 80


def dim_rentrestr_decree(parcel_id: Optional[str],
                         index: Optional[Dict[str, dict]],
                         snapshot_date: Optional[str] = VERDICT_DATE,
                         ) -> Score:
    """p74: rental-restriction decree per parcel (high = unrestricted).

    Exact-parcel join over decree rows only: restriction True scores low
    with the decree_ref printed; False scores measured-clear dated to the
    snapshot; None/missing stays NULL. Supply counts (tourism apartments)
    are never consulted.
    """
    kid, row, null = _join(parcel_id, index)
    if null is not None or row is None or kid is None:
        assert null is not None
        return null
    dated = "hetktõmmis %s" % snapshot_date if snapshot_date else "hetktõmmis"
    flag = row.get("rental_restriction")
    if flag is True:
        ref = row.get("decree_ref") or "viide teadmata"
        return RESTRICTION_PRESENT_SCORE, (
            "Üüripiirangu määrus (hinnang, %s): krundil %s kehtib piirang "
            "(%s) → skoor %d: loe määruse tekst Riigi Teatajast ja nõua "
            "notari kinnitust — tehingu peatamine kuulub tehingukihile, "
            "mitte skoorile" % (dated, kid, ref, RESTRICTION_PRESENT_SCORE))
    if flag is False:
        return NO_RESTRICTION_SCORE, (
            "Üüripiirangu määrust (hinnang, %s): krundil %s piirangut EI OLE "
            "snapshot'is → skoor %d (mõõdetud puhtus ainult tõmmise "
            "ulatuses, mitte garantii)"
            % (dated, kid, NO_RESTRICTION_SCORE))
    return None, ("Krundi %s üüripiirangu-kirjet hetktõmmis EI OLE "
                  "(hinnang puudub): teadmatus ei ole puhas otsus — "
                  "kontrolli KOV määrust/Riigi Teatajat" % kid)


# ---------------------------------------------------------------------------
# p274: max-height ceiling proxy (PARTIAL — never the deed clause).
# ---------------------------------------------------------------------------

#: Soft-cap band for the KNOWN ceiling (first cut, MUST be recalibrated):
#: the proxy can neither prove the right (cap 65) nor block the deal
#: (floor 55). The deed question always points at the kinnistusraamat.
CEILING_BANDS = [(9.0, 55), (25.0, 60), (float("inf"), 65)]


def _sane_height(raw) -> Optional[float]:
    """Allowed ceiling in metres when honest, else None (never faked)."""
    if isinstance(raw, bool):
        return None
    try:
        h = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(h) or h <= 0:
        return None
    return h


def dim_airrights_ceiling(parcel_id: Optional[str],
                          index: Optional[Dict[str, dict]],
                          snapshot_date: Optional[str] = VERDICT_DATE,
                          ) -> Score:
    """p274 partial: plan ceiling as development-right proxy (soft caps).

    A known max_height_m scores INSIDE [55, 65] with the deed disclaimer;
    anything else (missing join, unknown/garbage ceiling) stays NULL. The
    reason always says lagi-proksi and points at the kinnistusraamat
    extract for the right itself.
    """
    kid, row, null = _join(parcel_id, index)
    if null is not None or row is None or kid is None:
        assert null is not None
        return null
    h = _sane_height(row.get("max_height_m"))
    if h is None:
        return None, ("Krundi %s lubatud kõrgust (lagi) hetktõmmis EI OLE "
                      "(hinnang puudub): õigust selle kohal ei saa tuletada "
                      "— kontrolli detailplaneeringut ja kinnistusraamatu "
                      "väljavõtet" % kid)
    s = next(pts for limit, pts in CEILING_BANDS if h <= limit)
    dated = "hetktõmmis %s" % snapshot_date if snapshot_date else "hetktõmmis"
    return s, ("Õhuõiguse lagi-proksi (hinnang, pehme lagi, %s): krundil %s "
               "lubatud kõrgus %.1f m → skoor %d (lagi ≠ õigus: omandit "
               "tõmmise kohal EI OLE tõestatud — õigus teadmata, kontrolli "
               "kinnistusraamatu väljavõtet)"
               % (dated, kid, h, s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
OVERTURN_PLANKTPR_DIMS = (
    ("zoning_use_overturn", "p47", dim_zoning_use),
    ("rentrestr_decree_overturn", "p74", dim_rentrestr_decree),
    ("airrights_ceiling_overturn", "p274", dim_airrights_ceiling),
)


def score_overturn_planktpr(parcel_id: Optional[str],
                            index: Optional[Dict[str, dict]],
                            snapshot_date: Optional[str] = VERDICT_DATE,
                            ) -> Dict[str, Optional[int]]:
    """All three overturn dims for one parcel (entry point for the
    weight-rebalance follow-up; keys match OVERTURN_PLANKTPR_DIMS)."""
    return {key: fn(parcel_id, index, snapshot_date)[0]
            for key, _, fn in OVERTURN_PLANKTPR_DIMS}
