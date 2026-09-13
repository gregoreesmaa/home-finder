"""P4 Maa-amet tehingud + market publications dims: demo (#244) + coverage (#328).

Demo param (this ingestion's anchor):
* P4-002 Closed-deal micro-comps (building/street EUR/m2) -> dim_closed_deal_micro_comp

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-001 Price history + days-on-market per ad -> dim_price_history_dom
* P4-021 Developer + broker track record -> dim_developer_broker_track
* P4-025 Micro-liquidity -> dim_micro_liquidity
* P4-028 Listing demand exhaust -> dim_listing_demand_exhaust
* P4-038 Bargaining margin (offer-vs-close gap) -> dim_bargaining_margin
* P4-043 Number-13 / name arbitrage -> dim_number13_arbitrage
* P4-044 Herd of picky people (gentrification front) -> dim_herd_gentrification_front
* P4-050 Permit glut vs completions (price leg) -> dim_permit_glut_price_leg
* P4-052 Turnover wave per building -> dim_turnover_wave
* P4-061 Last-shop/pharmacy/ATM + bus-cut tracker -> dim_last_shop_tracker

OPENNESS VERDICT (probed 2026-09-13, single polite fetches, cached /tmp — full
evidence in docs/p4_maa_tehingud.md):
* Maa-amet tehingute andmebaas (per-address deals): HTTP 200 landing page, but
  "Tehingu andmetele on juurdepääs piiratud" — restricted to licensed valuers /
  statistics producers / R&D bodies / supervised lenders. DATED NEGATIVE for
  per-address bulk: no open building-level feed exists, so in production every
  median join below stays NULL with an Estonian reason. The join LOGIC is still
  implemented and proven hermetically on synthetic fixtures here.
* Maa-amet kinnisvaraturu ülevaated (market publications, PDF): OPEN
  (HTTP 200, last-modified 2026-2, annual + monthly). TTL: publications
  monthly/annual; HTRARU public stats UI aggregates quarterly.
* Statistikaamet PX-Web API (HH01/KK11 Tallinn tables): OPEN (HTTP 200).
  TTL: quarterly.

HONESTY (AGENTS.md section 7.2): the only scored shape in this module is the
per-address MEDIAN JOIN (building exact match, street fallback) — never a
distance gradient, never interpolation, never a heat-coloured guess. Medians
need >= MIN_COMPS (3) closed deals at the joined level; anything thinner stays
NULL ("EI OLE piisavalt võrdlustehinguid"). Every NULL reason says "hinnang"
(estimate) and "EI OLE" and names the concrete check (licensed-valuer extract,
Land Board publication table, adapter store, manual checklist) — never a faked
number. Transport errors in fetch_cached are NEVER cached as data, and HTTP 429
is a stop signal, not a retry dare (AGENTS.md sections 7.2/7.4).

Style: pure offline scorers (listing, deals, ...) -> (Optional[int 0..100],
Estonian reason), mirroring sibling batches (e.g. dims_group16a.py #205).
Network lives ONLY in fetch_cached (polite single-GET + file cache + TTL);
tests never touch the network. No livability/WEIGHTS/layers integration here —
rebalancing stays one joint change across batches (existing tests pin WEIGHTS).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #328's body states it extends
  the #244 demo ingestion ("no new plumbing expected") — splitting would leave
  the demo unreviewable against its coverage contract.
* MIN_COMPS = 3: Land Board publications threshold at >= 5 deals per
  settlement; micro (building/street) uses >= 3 with a street fallback so a
  single deal can never set a "median".
* P4-002 score = round(100 * comp_median / asking), capped at 100: asking at or
  below the closed-deal median is "fair/steal" (100); overpaying scales down
  linearly (25% over -> 80). Simple, explainable, feeds the steal sort.
* P4-044/P4-050 score ONLY their tehingud legs (gentrification price drift /
  falling-price check); the REL2021-grid and EHR-permit legs are named as
  missing (EI OLE) in the reason rather than faked.
* P4-052 wave threshold = 6 deals/building/12mo; a detected wave scores neutral
  50 with BOTH readings (problem vs gentrifying) in the reason, per
  parameters4.md — an ambiguous signal must not push the steal sort.
* P4-061 needs a manual settlement checklist (shop/pharmacy/ATM + bus cuts):
  Peatus GTFS diffs and OSM closure tracking are not in-snapshot, so a passed
  checklist is scored as a labelled hinnang, a missing one stays NULL.
"""

import datetime as _dt
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #244 acceptance criterion 2).
# ---------------------------------------------------------------------------

SOURCE_URLS = {
    # Restricted per-address DB (dated negative 2026-09-13 — kept so the
    # verdict stays checkable, NOT fetched in bulk).
    "tehingute_andmebaas": (
        "https://geoportaal.maaamet.ee/est/ruumiandmed/"
        "kinnisvara-tehingute-andmebaas-p81.html"
    ),
    # Open market publications (annual + monthly PDFs).
    "turuylevaade_aasta": (
        "https://maaruum.ee/sites/default/files/documents/2026-02/"
        "Eesti%20kinnisvaraturg%202025.pdf"
    ),
    # Open statistics API (HH01/KK11 Tallinn tables live under /et/stat).
    "stat_api": "https://andmed.stat.ee/api/v1/et",
}

# TTLs in days, per parameters4.md P4-002 ("TTL: quarterly") and the
# publication cadence observed 2026-09-13 (annual yearbook + monthly PDFs).
TTL_DAYS = {
    "tehingud_bulk": 91,      # quarterly bulk (HTRARU aggregates / future feed)
    "market_publication": 30,  # monthly PDFs (yearbook: 365, handled by caller)
    "stat_tables": 91,        # HH01/KK11 quarterly
}

CACHE_SUBDIR = "hf-p4-maa-tehingud"
USER_AGENT = (
    "home-finder-research/0.1 (polite quarterly bulk; "
    "GitHub gregoreesmaa/home-finder issue 244)"
)
MIN_COMPS = 3  # minimum closed deals for an honest median (see docstring)
WAVE_DEALS_12MO = 6  # P4-052 turnover-wave threshold per building


def cache_path(cache_dir: str, name: str) -> str:
    """Cache file location for a named fetch (flat files, no dumps committed)."""
    return os.path.join(cache_dir, CACHE_SUBDIR, name)


def is_fresh(path: str, ttl_days: int,
             now: Optional[_dt.datetime] = None) -> bool:
    """True when a cached file exists and is younger than ttl_days."""
    try:
        mtime = _dt.datetime.fromtimestamp(
            os.path.getmtime(path), tz=_dt.timezone.utc)
    except OSError:
        return False
    at = now or _dt.datetime.now(tz=_dt.timezone.utc)
    return (at - mtime) <= _dt.timedelta(days=ttl_days)


def fetch_cached(url: str, cache_dir: str, name: str, ttl_days: int,
                 timeout_s: int = 25) -> str:
    """Polite single-GET with file cache. Returns the cache path.

    Fresh cache wins (no request). Transport errors are raised and NEVER
    written as data; HTTP 429 raises immediately (stop signal, no retry).
    Pulls urllib only (no new dependency).
    """
    import urllib.request

    dest = cache_path(cache_dir, name)
    if is_fresh(dest, ttl_days):
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            if resp.status == 429:
                raise RuntimeError("HTTP 429 — stop, do not retry: " + url)
            body = resp.read()
    except Exception:
        raise
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with open(tmp, "wb") as fh:
        fh.write(body)
    os.replace(tmp, dest)
    return dest


# ---------------------------------------------------------------------------
# Pure helpers (median join core — hermetically tested).
# ---------------------------------------------------------------------------

def normalise_address(raw: Optional[str]) -> Optional[str]:
    """Lowercase + collapse whitespace. Exact-match only (no fuzzy join)."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or None


def median_eur_m2(values: List[Optional[float]]) -> Optional[float]:
    """Median of positive EUR/m2 values; None when empty (never a gradient)."""
    clean = sorted(v for v in values
                   if isinstance(v, (int, float)) and v is not None and v > 0)
    if not clean:
        return None
    n = len(clean)
    mid = n // 2
    if n % 2:
        return float(clean[mid])
    return (clean[mid - 1] + clean[mid]) / 2.0


def _quarter_key(q: Optional[str]) -> Optional[Tuple[int, int]]:
    try:
        year, qq = str(q).split("-Q")
        return (int(year), int(qq))
    except (ValueError, AttributeError):
        return None


def micro_comp(address: Optional[str], street: Optional[str],
               deals: List[dict]) -> Tuple[Optional[float], int,
                                           Optional[str]]:
    """(median EUR/m2, n deals, level) for building, else street, else empty.

    Honest shape: exact normalised-address match first, then normalised-street
    match. Each level needs >= MIN_COMPS deals. No distance weighting, no
    interpolation — a thin level is skipped, never smoothed.
    """
    addr = normalise_address(address)
    if addr:
        rows = [d.get("eur_m2") for d in deals
                if normalise_address(d.get("address")) == addr]
        med = median_eur_m2(rows) if len(
            [v for v in rows if isinstance(v, (int, float)) and v and v > 0]
        ) >= MIN_COMPS else None
        if med is not None:
            return med, len([v for v in rows if v]), "building"
        building_n = len(rows)
    else:
        building_n = 0
    st = normalise_address(street)
    if st:
        rows = [d.get("eur_m2") for d in deals
                if normalise_address(d.get("street")) == st]
        valid = [v for v in rows
                 if isinstance(v, (int, float)) and v and v > 0]
        if len(valid) >= MIN_COMPS:
            med = median_eur_m2(rows)
            if med is not None:
                return med, len(valid), "street"
        street_n = len(rows)
    else:
        street_n = 0
    return None, building_n + street_n, None


def _asum_rows(asum: Optional[str], deals: List[dict]) -> List[dict]:
    key = normalise_address(asum)
    if not key:
        return []
    return [d for d in deals if normalise_address(d.get("asum")) == key]


def _median_by_window(rows: List[dict]) -> Dict[Tuple[int, int], float]:
    buckets: Dict[Tuple[int, int], List[float]] = {}
    for d in rows:
        q = _quarter_key(d.get("quarter"))
        v = d.get("eur_m2")
        if q is None or not isinstance(v, (int, float)) or v <= 0:
            continue
        buckets.setdefault(q, []).append(float(v))
    out: Dict[Tuple[int, int], float] = {}
    for q, vals in buckets.items():
        if len(vals) >= MIN_COMPS:
            med = median_eur_m2(vals)
            if med is not None:
                out[q] = med
    return out


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


# ---------------------------------------------------------------------------
# Demo dim: P4-002 closed-deal micro-comps (issue #244).
# ---------------------------------------------------------------------------

def dim_closed_deal_micro_comp(listing: dict, deals: List[dict]) -> Score:
    """P4-002: asking EUR/m2 vs closed-deal building/street median.

    100 = asking at/under the micro-comp median (fair/steal); overpaying
    scales down linearly. NULL when the join is not honest (no address, no
    asking, or < MIN_COMPS deals at both levels).
    """
    asking = listing.get("eur_m2")
    if not isinstance(asking, (int, float)) or asking <= 0:
        return None, ("Küsimishind €/m² puudub kuulutusest (EI OLE hinnangut): "
                      "mikro-võrdlust ei saa arvutada — kontrolli kuulutuse "
                      "hinda, ära feigi")
    med, n, level = micro_comp(listing.get("address"), listing.get("street"),
                               deals)
    if med is None:
        return None, ("Sulgunud tehingute mikro-võrdlust EI OLE (leiti %d "
                      "tehingut, vaja >= %d hoone/tänava tasandil): hoone- "
                      "põhine hulgilaadimine on piiratud (litsentseeritud "
                      "hindaja väljavõte) — küsi maaklerilt compe, ära feigi "
                      "hinnangut" % (n, MIN_COMPS))
    score = _clamp(100.0 * med / asking)
    lvl = "hoone" if level == "building" else "tänava"
    return score, ("Sulgunud tehingute %s mediaan %.0f €/m² (%d tehingut) vs "
                   "küsitav %.0f €/m²: õiglane-hind hinnang %d/100 "
                   "(100 = mediaanis/allpool)" % (lvl, med, n, asking, score))


# ---------------------------------------------------------------------------
# Coverage dims: the 10 remaining params off this source (issue #328).
# ---------------------------------------------------------------------------

def dim_price_history_dom(listing: dict, deals: List[dict],
                          today: Optional[str] = None) -> Score:
    """P4-001: stale/desperate/overpriced vs steal from DOM + price cuts.

    Scores only stale ads (DOM >= 90 d or >= 2 cuts), anchored on the P4-002
    micro-comp median. Fresh ads and missing adapter history stay NULL.
    """
    first = listing.get("first_seen")
    if not first:
        return None, ("Kuulutuse ajalugu (first_seen) adapteri laos EI OLE "
                      "(hinnang puudub): DOM-i ei saa arvutada — vaja "
                      "portaali hetktõmmiste ajalugu, ära feigi")
    try:
        seen = _dt.date.fromisoformat(str(first))
    except ValueError:
        return None, ("Kuulutuse first_seen on vigane (%s) — DOM-hinnangut EI "
                      "OLE: paranda adapteri ajavahemik" % first)
    now = _dt.date.fromisoformat(str(today)) if today else _dt.date.today()
    dom = (now - seen).days
    cuts = listing.get("price_cuts") or 0
    if dom < 0:
        return None, ("first_seen on tulevikus — DOM-hinnangut EI OLE "
                      "(adapteri kella viga)")
    if not (dom >= 90 or cuts >= 2):
        return None, ("Värske kuulutus (DOM %d p, %d hinnalangust): "
                      "staleness-signaali EI OLE — hinnang puudub, jälgi "
                      "edasisi langusi" % (dom, cuts))
    asking = listing.get("eur_m2")
    med, n, level = micro_comp(listing.get("address"), listing.get("street"),
                               deals)
    if (not isinstance(asking, (int, float)) or asking <= 0
            or med is None):
        return None, ("Seisnud kuulutus (DOM %d p, %d langust), aga "
                      "võrdlusankrut EI OLE (leiti %d tehingut): steal-hinnang "
                      "puudub — küsi compe" % (dom, cuts, n))
    if asking <= med:
        return 85, ("Seisnud kuulutus (DOM %d p, %d hinnalangust) hinnaga "
                    "%.0f €/m² sulgunud mediaanis/allpool (%.0f €/m², %d "
                    "tehingut): võimaliku tehingukoha hinnang 85/100"
                    % (dom, cuts, asking, med, n))
    return 40, ("Seisnud kuulutus (DOM %d p, %d langust), aga küsitakse "
                "%.0f €/m² üle sulgunud mediaani (%.0f €/m²): üle hinnatud "
                "seisuja hinnang 40/100" % (dom, cuts, asking, med))


def dim_developer_broker_track(listing: dict, deals: List[dict]) -> Score:
    """P4-021: developer project resale performance from tehingud.

    Same-developer Tallinn resale median vs all-deal median. NULL when the
    listing names no developer or the developer has < MIN_COMPS resales.
    (TTJA complaints / broker cross-portal stats are not in-snapshot and
    stay out — EI OLE — rather than faked.)
    """
    dev = normalise_address(listing.get("developer"))
    if not dev:
        return None, ("Arendaja ei selgu kuulutusest (EI OLE hinnangut): "
                      "track-record vajab arendaja nime + edasimüügitehinguid "
                      "— küsi maaklerilt/arendajalt, ära feigi")
    dev_rows = [d.get("eur_m2") for d in deals
                if normalise_address(d.get("developer")) == dev
                and isinstance(d.get("eur_m2"), (int, float))
                and d.get("eur_m2") > 0]
    if len(dev_rows) < MIN_COMPS:
        return None, ("Arendaja '%s' edasimüüke leiti %d (vaja >= %d) — "
                      "track-recordi hinnangut EI OLE: tehinguajalugu on "
                      "õhuke, küsi arendaja referentse"
                      % (listing.get("developer"), len(dev_rows), MIN_COMPS))
    all_rows = [d.get("eur_m2") for d in deals
                if isinstance(d.get("eur_m2"), (int, float))
                and d.get("eur_m2") > 0]
    dev_med = median_eur_m2(dev_rows) or 0.0
    all_med = median_eur_m2(all_rows) or 0.0
    if all_med <= 0:
        return None, ("Võrdlusbaasi (kõik tehingud) mediaani EI OLE — "
                      "arendaja-hinnang puudub")
    ratio = dev_med / all_med
    if ratio >= 1.0:
        score = 70
        word = "hoiab turgu"
    elif ratio >= 0.95:
        score = 55
        word = "püsib turu lähedal"
    else:
        score = 40
        word = "jääb turule alla"
    return score, ("Arendaja '%s' edasimüügi mediaan %.0f €/m² (%d tehingut) "
                   "%s (kogu baas %.0f €/m²): usalduse hinnang %d/100 "
                   "(TTJA kaebuste/EHR ajaloo jalga EI OLE — ainult "
                   "edasimüügi-jalg)" % (listing.get("developer"), dev_med,
                                          len(dev_rows), word, all_med, score))


def dim_micro_liquidity(listing: dict, deals: List[dict]) -> Score:
    """P4-025: turnover-based micro-liquidity per asum (deals-leg only).

    Counts asum deals in the two latest quarters present in the feed.
    REL2021 age/migration/vacancy + school-plan legs are not in-snapshot
    (EI OLE) and are named, not faked.
    """
    rows = _asum_rows(listing.get("asum"), deals)
    if not rows:
        return None, ("Asumi '%s' tehingukäibe andmeid EI OLE (hinnang "
                      "puudub): likviidsus vajab kvartali tehinguarve — küsi "
                      "maaklerilt/statistikast" % listing.get("asum"))
    quarters = sorted({_quarter_key(d.get("quarter")) for d in rows
                       } - {None})
    if not quarters:
        return None, ("Asumi tehingutel kvartalit EI OLE — käibe-hinnang "
                      "puudub")
    recent = set(quarters[-2:])
    n = sum(1 for d in rows if _quarter_key(d.get("quarter")) in recent)
    if n >= 20:
        score, word = 80, "likviidne"
    elif n >= 8:
        score, word = 60, "mõõdukalt likviidne"
    elif n >= 3:
        score, word = 45, "õhuke"
    else:
        return None, ("Asumi '%s' käive %d tehingut/2 kvartalit — "
                      "likviidsushinnangut EI OLE (liiga õhuke): müügiperiood "
                      "võib venida" % (listing.get("asum"), n))
    return score, ("Asumi '%s' käive %d tehingut/2 kvartalit (%s): "
                   "likviidsuse hinnang %d/100 (ainult tehingute käibe-jalg; "
                   "REL2021 vanus/ränne/vakants + kooliplaanide jalga EI OLE)"
                   % (listing.get("asum"), n, word, score))


def dim_listing_demand_exhaust(listing: dict, deals: List[dict]) -> Score:
    """P4-028: demand-exhaust reading (views/day + DOM + updates).

    Score = buyer-position strength: exhausted demand (few views, long DOM)
    scores HIGH (negotiation room); hot listings score LOW. NULL when no
    exhaust counters exist at all. (deals unused — kept for uniform wiring;
    the Maa-amet ask-vs-close calibration leg lives in P4-038.)
    """
    _ = deals
    views = listing.get("views_per_day")
    dom = listing.get("dom_days")
    updates = listing.get("updates_30d") or 0
    if views is None and dom is None:
        return None, ("Nõudluse kulutusloendureid (vaatamised/päev, DOM) "
                      "adapteri laos EI OLE — hinnang puudub: vaja portaali "
                      "hetktõmmiseid, ära feigi")
    views_f = float(views) if isinstance(views, (int, float)) else None
    dom_i = int(dom) if isinstance(dom, (int, float)) else None
    if views_f is not None and views_f < 1.0 and dom_i is not None \
            and dom_i >= 60:
        return 80, ("Nõudlus raugenud (%.1f vaatamist/päev, DOM %d p): "
                    "läbirääkimisruumi hinnang 80/100 — võimalik "
                    "pakkumisaken" % (views_f, dom_i))
    if views_f is not None and views_f >= 5.0:
        return 30, ("Kuum kuulutus (%.1f vaatamist/päev, %d uuendust/30 p): "
                    "pakkumisruumi hinnang 30/100 — konkurents tihe"
                    % (views_f, updates))
    dom_txt = "%d p" % dom_i if dom_i is not None else "teadmata"
    views_txt = "%.1f/päev" % views_f if views_f is not None else "teadmata"
    return 55, ("Keskmine nõudlus (vaatamised %s, DOM %s): positsiooni "
                "hinnang 55/100" % (views_txt, dom_txt))


def dim_bargaining_margin(listing: dict, deals: List[dict],
                          gap_table: Optional[dict] = None) -> Score:
    """P4-038: opening-bid hint from the area-type offer-vs-close gap.

    gap_table maps area_type -> typical gap fraction (0.03 = 3%), from the
    Land Board publication. No table -> NULL (never a guessed gap).
    """
    _ = deals
    area = listing.get("area_type")
    if not gap_table or area not in gap_table:
        return None, ("Piirkonnatüübi '%s' pakkumis-vs-sulgemis lõhe tabelit "
                      "(Land Board publikatsioon) EI OLE — avamispakkumuse "
                      "hinnang puudub" % area)
    gap = gap_table[area]
    if not isinstance(gap, (int, float)) or gap < 0:
        return None, ("Lõhe väärtus tüübile '%s' on vigane — hinnangut EI OLE"
                      % area)
    if gap >= 0.05:
        score = 80
    elif gap >= 0.03:
        score = 65
    elif gap >= 0.01:
        score = 50
    else:
        score = 35
    return score, ("Piirkonnatüübi '%s' tüüpiline lõhe %.1f%% (Land Board "
                   "publikatsioon, hinnang): avamispakkumuse vihje ~%.1f%% "
                   "küsitavast alla, ruumi-hinnang %d/100"
                   % (area, gap * 100.0, gap * 100.0, score))


def dim_number13_arbitrage(listing: dict, deals: List[dict]) -> Score:
    """P4-043: floor/house-13 + unsexy-street discount vs street median.

    Taste-match steal flag: a 13-marked listing priced under its street
    median scores HIGH (discount for the unbothered). No 13-mark, no floor
    data, or thin street comps stay NULL.
    """
    floor = listing.get("floor")
    house = str(listing.get("house_number") or "")
    has_floor = isinstance(floor, int)
    mark13 = (floor == 13) or house.strip().startswith("13")
    if not has_floor and not house:
        return None, ("Korruse/maja numbrit kuulutuses EI OLE — 13-arbitraaži "
                      "hinnang puudub: kontrolli kuulutuse korrust, ära feigi")
    if not mark13:
        return None, ("13-märki (korrus/maja 13) EI OLE — arbitraaži-signaali "
                      "hinnang puudub")
    asking = listing.get("eur_m2")
    st = normalise_address(listing.get("street"))
    rows = [d.get("eur_m2") for d in deals
            if normalise_address(d.get("street")) == st
            and isinstance(d.get("eur_m2"), (int, float))
            and d.get("eur_m2") > 0] if st else []
    if (not isinstance(asking, (int, float)) or asking <= 0
            or len(rows) < MIN_COMPS):
        return None, ("13-märgiga kuulutus, aga tänava võrdlusbaasi EI OLE "
                      "(leiti %d tehingut, vaja >= %d) — allahindluse "
                      "hinnang puudub" % (len(rows), MIN_COMPS))
    med = median_eur_m2(rows) or 0.0
    if asking < med:
        return 80, ("13-märk (korrus %s, maja %s) + hind %.0f €/m² tänava "
                    "mediaanist %.0f €/m² allpool: ebausu-allahindluse "
                    "hinnang 80/100 (maitse-sobivus, mitte väärtushinnang)"
                    % (floor, house or "?", asking, med))
    return 50, ("13-märgiga, aga hind %.0f €/m² tänava mediaanis/üle (%.0f "
                "€/m²): allahindluse hinnang 50/100 — ebausk hinda ei "
                "alandanud" % (asking, med))


def dim_herd_gentrification_front(listing: dict, deals: List[dict]) -> Score:
    """P4-044: gentrification-front tracking per asum (tehingud-leg only).

    Compares the asum median of the newer half of quarter-windows vs the
    older half (each window needs >= MIN_COMPS). Grid taste-match, never a
    worth judgement; the REL2021 occupation-mix grid is named missing.
    """
    rows = _asum_rows(listing.get("asum"), deals)
    meds = _median_by_window(rows)
    if len(meds) < 2:
        return None, ("Asumi '%s' gentrifikatsiooni-jälgimiseks EI OLE "
                      "piisavalt kvartaliaknaid (leiti %d, vaja >= 2): "
                      "suundumuse hinnang puudub" % (listing.get("asum"),
                                                     len(meds)))
    qs = sorted(meds)
    half = max(1, len(qs) // 2)
    old = sum(meds[q] for q in qs[:half]) / half
    new_qs = qs[-half:]
    new = sum(meds[q] for q in new_qs) / len(new_qs)
    drift = (new - old) / old if old > 0 else 0.0
    if drift > 0.05:
        score, word = 70, "pealetulev (hinnad +%.0f%%)" % (drift * 100.0)
    elif drift < -0.05:
        score, word = 40, "jahtuv (hinnad %.0f%%)" % (drift * 100.0)
    else:
        score, word = 55, "stabiilne (nihe %+.0f%%)" % (drift * 100.0)
    return score, ("Asumi '%s' tehingute hinnanihke-jalg: %s — maitse-sobivuse "
                   "hinnang %d/100 (REL2021 ametisegu-ruudustikku EI OLE; "
                   "kunagi väärtushinnang, ainult maitse-sobivus)"
                   % (listing.get("asum"), word, score))


def dim_permit_glut_price_leg(listing: dict, deals: List[dict]) -> Score:
    """P4-050: falling-price check per asum (tehingud-leg only, quarterly).

    Latest quarter-window median vs the window 4 quarters back. The EHR
    permit/completion counts are not in-snapshot (EI OLE) — this is the
    price-leg cross-check, documented as such.
    """
    rows = _asum_rows(listing.get("asum"), deals)
    meds = _median_by_window(rows)
    if len(meds) < 2:
        return None, ("Asumi '%s' hinnalanguse kontrolliks EI OLE piisavalt "
                      "kvartaliaknaid (leiti %d): hinnang puudub"
                      % (listing.get("asum"), len(meds)))
    qs = sorted(meds)
    latest = meds[qs[-1]]
    base_q = (qs[-1][0] - 1, qs[-1][1])  # same quarter one year back
    base = meds.get(base_q)
    if base is None or base <= 0:
        base = meds[qs[0]]  # honest fallback: oldest available window
    trend = (latest - base) / base if base > 0 else 0.0
    if trend < -0.03:
        score, word = 30, "langev (%.0f%% aastas)" % (trend * 100.0)
    elif trend > 0.03:
        score, word = 70, "tõusev (+%.0f%% aastas)" % (trend * 100.0)
    else:
        score, word = 55, "külgnev (%+.0f%%)" % (trend * 100.0)
    return score, ("Asumi '%s' tehingute hinna-jalg: %s — torujuhtme-riski "
                   "hinnang %d/100 (EHR ehitus-/kasutuslubade arve EI OLE; "
                   "ainult hinna-jalg, kvartaalne)" % (listing.get("asum"),
                                                       word, score))


def dim_turnover_wave(listing: dict, deals: List[dict]) -> Score:
    """P4-052: turnover wave per building from tehingud (12-month window).

    >= WAVE_DEALS_12MO deals at the exact building address scores neutral 50
    with BOTH readings (problem vs gentrifying) in the reason — an ambiguous
    signal must not push the steal sort. Normal turnover stays NULL.
    """
    addr = normalise_address(listing.get("address"))
    if not addr:
        return None, ("Hoone aadressi kuulutuses EI OLE — käibelaine "
                      "hinnang puudub")
    n = sum(1 for d in deals
            if normalise_address(d.get("address")) == addr
            and isinstance(d.get("months_ago"), (int, float))
            and 0 <= d.get("months_ago") <= 12)
    if n < WAVE_DEALS_12MO:
        return None, ("Hoone käibelaine EI OLE (%d tehingut/12 k, vaja >= "
                      "%d laineks): tavaline käive, hinnang puudub"
                      % (n, WAVE_DEALS_12MO))
    return 50, ("Hoone käibelaine: %d tehingut/12 k (hinnang 50/100, "
                "neutraalne): lugemine A — probleem (miks kõik lahkuvad? "
                "küsi KÜ-lt remondifondi ja müügipõhjuseid); lugemine B — "
                "pealetulev piirkond (renoveerimisload/EHR tormi-sisenemise "
                "lugemine). Kumbki ei ole tõestatud — kontrolli kohapeal"
                % n)


def dim_last_shop_tracker(listing: dict, deals: List[dict]) -> Score:
    """P4-061: settlement service checklist + bus-cut tracker (annual).

    checklist = {"shop": bool, "pharmacy": bool, "atm": bool,
    "bus_cuts_12mo": int}. Each missing service -15, each bus cut -10 from
    80. No checklist -> NULL. Peatus GTFS diffs / OSM closure tracking are
    not in-snapshot (EI OLE) — a passed checklist is a labelled hinnang.
    """
    _ = deals
    check = listing.get("settlement_checklist")
    if not isinstance(check, dict) or not check:
        return None, ("Asula teenuste-kontrollnimekirja (pood/apteek/ATM + "
                      "bussikärped) EI OLE — likviidsusspiraali hinnang "
                      "puudub: täida nimekiri kohapeal/Peatus.ee-st")
    score = 80
    missing = [k for k in ("shop", "pharmacy", "atm")
               if not check.get(k)]
    score -= 15 * len(missing)
    cuts = check.get("bus_cuts_12mo") or 0
    cuts_i = int(cuts) if isinstance(cuts, (int, float)) and cuts > 0 else 0
    score -= 10 * cuts_i
    score = _clamp(score)
    if not missing and not cuts_i:
        word = "kõik teenused avatud, kärpeid pole"
    else:
        word = ("puudu: %s; bussikärpeid 12 k: %d"
                % (", ".join(missing) if missing else "—", cuts_i))
    return score, ("Asula teenuste-nimekiri (%s): püsimajäämise hinnang "
                   "%d/100 (Peatus GTFS diffi/OSM sulgemisjälgimist EI OLE "
                   "snapshots — käsitsi hinnang, aastane)" % (word, score))


# ---------------------------------------------------------------------------
# Registry + aggregator (entry point for the weight-rebalance follow-up).
# ---------------------------------------------------------------------------

P4_MAA_TEHINGUD_DIMS = (
    ("micro_comp", "P4-002", dim_closed_deal_micro_comp),
    ("price_history_dom", "P4-001", dim_price_history_dom),
    ("developer_track", "P4-021", dim_developer_broker_track),
    ("micro_liquidity", "P4-025", dim_micro_liquidity),
    ("demand_exhaust", "P4-028", dim_listing_demand_exhaust),
    ("bargaining_margin", "P4-038", dim_bargaining_margin),
    ("number13_arbitrage", "P4-043", dim_number13_arbitrage),
    ("herd_front", "P4-044", dim_herd_gentrification_front),
    ("permit_glut_price", "P4-050", dim_permit_glut_price_leg),
    ("turnover_wave", "P4-052", dim_turnover_wave),
    ("last_shop", "P4-061", dim_last_shop_tracker),
)


def score_p4_maa_tehingud(listing: dict, deals: List[dict],
                          gap_table: Optional[dict] = None,
                          today: Optional[str] = None
                          ) -> Dict[str, Optional[int]]:
    """All 11 P4 Maa-tehingud dims for one listing (keys match registry)."""
    out: Dict[str, Optional[int]] = {}
    for key, _pnum, fn in P4_MAA_TEHINGUD_DIMS:
        if fn in (dim_price_history_dom,):
            out[key] = fn(listing, deals, today)
        elif fn in (dim_bargaining_margin,):
            out[key] = fn(listing, deals, gap_table)
        else:
            out[key] = fn(listing, deals)
    # dim_* return (score, reason); unwrap to score-only for the aggregator.
    return {k: (v[0] if isinstance(v, tuple) else v)
            for k, v in out.items()}
