"""P4 Statamet tables (new uses) dims: demo (#292) + coverage (#365).

Demo param (this ingestion's anchor):
* P4-002 Closed-deal micro-comps, Stat-table anchor leg
  -> dim_stat_micro_comp_anchor

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-001 Price history + days-on-market per ad (Stat-median anchor leg)
  -> dim_price_history_dom_stat
* P4-003 Rent reality + Airbnb density (Stat rent-table leg)
  -> dim_rent_reality_stat
* P4-019 KOV fiscal health (Stat KOV-budget leg)
  -> dim_kov_fiscal_stat
* P4-025 Micro-liquidity (Stat migration-table leg)
  -> dim_micro_liquidity_stat
* P4-038 Bargaining margin (Stat quarterly-median calibration leg)
  -> dim_bargaining_margin_stat
* P4-043 Number-13 / name arbitrage (Stat linnaosa-prestige baseline leg)
  -> dim_number13_baseline_stat
* P4-050 Permit glut vs completions (Stat EH-pipeline leg)
  -> dim_permit_glut_stat
* P4-051 Zero-consumption stairwells (Stat empty-dwellings leg)
  -> dim_zero_consumption_stat
* P4-061 Last-shop/pharmacy/ATM + bus-cut tracker (Stat spiral-check leg)
  -> dim_last_shop_spiral_stat

OPENNESS VERDICT (probed 2026-09-13, ~14 single polite GETs, 3 s pacing,
contact UA, cached /tmp/hf-p4-stat/ — full evidence in docs/p4_stat.md):
* PX-Web API root + stat tree: OPEN (HTTP 200 throughout).
* hinnad (IA027/IA028 dwelling-price index, quarterly): OPEN.
* ehitus/ehitus-ja-kasutusload (EH04/EH05/EH06/EH44U/EH46U permits +
  completions): OPEN.
* ranne (RVR02 migration by haldusuksus, annual, Rändesaldo variable): OPEN.
* eluruumid LER series (dwellings): OPEN.
* KOV eelarve (RR300/RR302 local budgets): OPEN.
* HH01/KK11 as literal codes: DATED PARTIAL-NEGATIVE — neither code appears
  in the current PX-Web tree (stat + statsql listings traversed 2026-09-13).
  They are legacy table codes; the honest substitutes wired below are the
  current equivalents (IA028 quarterly index, EH series, RVR migration,
  RR budgets, LER dwellings). Fixture tables are KK11-shaped area medians,
  labelled as such, never as literal KK11 pulls.
* Maa-amet per-address deals: RESTRICTED (dated negative in the sibling
  module) — the building/street fineness stays that module's job.

HONESTY (AGENTS.md section 7.2): the only scored shapes in this module are
exact AREA-TABLE JOINS (linnaosa/asum/KOV/settlement, normalised exact
match) and the SETTLEMENT CHECKLIST — never a distance gradient, never
interpolation across quarters, never cross-area smoothing. Each dim reads
the LATEST period present for its area; a missing area row stays NULL
("EI OLE"). A single published official median IS the statistic (unlike a
micro-median over raw deals, which needs MIN_COMPS in the sibling module).
Every NULL reason says "hinnang" (estimate) and "EI OLE" and names the
concrete check (PX-table row, adapter store, manual checklist) — never a
faked number. Transport errors in fetch_cached are NEVER cached as data,
and HTTP 429 is a stop signal, not a retry dare (AGENTS.md 7.2/7.4).

Style: pure offline scorers (listing, rows, ...) -> (Optional[int 0..100],
Estonian reason), mirroring sibling batches (dims_p4_maa_tehingud.py
#244/#328, dims_p4_rel2021.py #274/#348). Network lives ONLY in
fetch_cached (polite single-GET + file cache + TTL); tests never touch the
network. No livability/WEIGHTS/layers integration here — rebalancing stays
one joint change across batches (existing tests pin WEIGHTS).

Overlap note (no double-score): P4-001/P4-002/P4-025/P4-038/P4-043/P4-050/
P4-061 already have TEHINGUD legs in dims_p4_maa_tehingud.py; P4-003/
P4-025/P4-043/P4-051 have REL2021-grid legs in dims_p4_rel2021.py; P4-019/
P4-025/P4-050/P4-061 have cityplans legs in dims_p4_cityplans.py; P4-051
has arireg/elektrilevi legs; P4-061 has elron/peatus/osm legs. This module
scores ONLY the Stat-table legs and names each sibling leg as EI OLE where
the param needs it (and vice versa) — complementary, never overlapping.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #365's body states it
  extends the #292 demo ingestion ("no new plumbing expected") — splitting
  would leave the demo unreviewable against its coverage contract (same
  precedent as #244/#328, #274/#348, #285/#359).
* P4-002 score = round(100 * area_median / asking), capped at 100: asking
  at or below the Stat quarterly area median is "fair/steal" (100);
  overpaying scales down linearly. Coarser than the sibling's
  building/street median by construction — the reason always names the
  finer check (licensed-valuer extract / broker comps).
* Latest-period-only: quarter rows are never averaged or trended inside a
  dim (except P4-038, whose param IS the quarterly change). A stale table
  is a TTL/re-pull problem, not a smoothing problem.
* P4-038 stat leg scores market-heat from the quarterly index change; the
  area-type gap TABLE itself stays the sibling module's job and is named
  EI OLE when unpublished — the two legs multiply judgement, never numbers.
* P4-043 stat leg is the linnaosa prestige BASELINE (area median vs city
  median); the street residual stays the sibling's job. Taste-match flag,
  never a worth judgement about the street ("maitse-sobivus").
* P4-051 stays at AREA grain (never addresses — privacy-safe by
  construction, per parameters4.md "hex/KOV only, never addresses").
* P4-061 stat leg is the spiral CHECK (shrinking population + thin
  turnover); the shop/pharmacy/ATM + bus-cut checklist stays the sibling's
  job and is named EI OLE when missing.
"""

import datetime as _dt
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #292 acceptance criterion 2).
# ---------------------------------------------------------------------------

SOURCE_URLS = {
    # Open PX-Web API root (probed 2026-09-13: HTTP 200, lists stat/statsql).
    "px_root": "https://andmed.stat.ee/api/v1/et",
    # Open stat tree (probed 2026-09-13: HTTP 200, 7 topic folders).
    "px_stat": "https://andmed.stat.ee/api/v1/et/stat",
    # Dwelling-price index, quarterly (probed 2026-09-13: IA027/IA028 listed
    # under majandus/hinnad — honest substitute for legacy KK11/HH01 codes,
    # which no longer appear in the tree: dated partial-negative).
    "px_hinnad": "https://andmed.stat.ee/api/v1/et/stat/majandus/hinnad",
    # Permits + completions (probed 2026-09-13: EH04/EH05/EH06/EH44U/EH46U
    # listed under ehitus/ehitus-ja-kasutusload).
    "px_permits": ("https://andmed.stat.ee/api/v1/et/stat/majandus/ehitus/"
                   "ehitus-ja-kasutusload"),
    # Migration by haldusuksus, annual (probed 2026-09-13: RVR02..RVR10
    # listed under rahvastik/rahvastikusundmused/ranne; RVR02 metadata
    # confirms annual grain, 201 haldusuksus values, Rändesaldo variable).
    "px_ranne": ("https://andmed.stat.ee/api/v1/et/stat/rahvastik/"
                 "rahvastikusundmused/ranne"),
    "px_RVR02": ("https://andmed.stat.ee/api/v1/et/stat/rahvastik/"
                 "rahvastikusundmused/ranne/RVR02.px"),
    # Dwellings LER series (probed 2026-09-13: 17 tables listed).
    "px_eluruumid": ("https://andmed.stat.ee/api/v1/et/stat/sotsiaalelu/"
                     "leibkonnad/leibkonna-elamistingimused/eluruumid"),
    # KOV budgets (probed 2026-09-13: RR300/RR302 listed).
    "px_kov_eelarve": ("https://andmed.stat.ee/api/v1/et/stat/majandus/"
                       "rahandus/valitsemissektori-rahandus/"
                       "kohalike-omavalitsuste-eelarve"),
}

# TTLs in days: quarterly tables 91 d, annual tables 365 d.
TTL_DAYS = {
    "stat_quarterly": 91,  # IA28 index, EH permits, KK11-shaped medians
    "stat_annual": 365,    # RVR migration, RR budgets, RV population, LER
}

CACHE_SUBDIR = "hf-p4-stat"
USER_AGENT = (
    "home-finder-research/0.1 (polite quarterly bulk; "
    "GitHub gregoreesmaa/home-finder issues 292/365)"
)
CITY = "tallinn"  # normalised city baseline key for prestige fallback


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
# Pure helpers (exact area-table join core — hermetically tested).
# ---------------------------------------------------------------------------

def normalise_area(raw: Optional[str]) -> Optional[str]:
    """Lowercase + collapse whitespace. Exact-match only (no fuzzy join)."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or None


def _num(row: dict, key: str) -> Optional[float]:
    v = row.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _quarter_key(q: Optional[str]) -> Optional[Tuple[int, int]]:
    try:
        year, qq = str(q).split("-Q")
        return (int(year), int(qq))
    except (ValueError, AttributeError):
        return None


def latest_rows(rows: List[dict], area: Optional[str],
                period_key: str = "quarter") -> List[dict]:
    """Rows for the exact area at the latest period present (no trending).

    Exact normalised-area match only; neighbouring areas NEVER leak in.
    """
    key = normalise_area(area)
    if not key:
        return []
    mine = [r for r in rows if normalise_area(r.get("area")) == key]
    if not mine:
        return []
    if period_key == "quarter":
        keys = sorted({_quarter_key(r.get("quarter")) for r in mine} - {None})
        if not keys:
            return mine
        latest = keys[-1]
        return [r for r in mine if _quarter_key(r.get("quarter")) == latest]
    years = sorted({r.get("year") for r in mine
                    if isinstance(r.get("year"), int)})
    if not years:
        return mine
    return [r for r in mine if r.get("year") == years[-1]]


def area_median(area: Optional[str], rows: List[dict]) -> Optional[float]:
    """Latest-quarter Stat median EUR/m2 for the exact area (KK11-shaped)."""
    for r in latest_rows(rows, area):
        v = _num(r, "median_eur_m2")
        if v is not None and v > 0:
            return v
    return None


# ---------------------------------------------------------------------------
# Demo dim: P4-002 Stat-table anchor (issue #292).
# ---------------------------------------------------------------------------

def dim_stat_micro_comp_anchor(listing: dict,
                               area_medians: List[dict]) -> Score:
    """P4-002: asking EUR/m2 vs Stat quarterly area median (KK11-shaped).

    100 = asking at/under the area median (fair/steal); overpaying scales
    down linearly. Coarser than the sibling tehingud building/street median
    by construction — the reason always names the finer check. NULL when
    the listing has no asking, no area, or the area has no row in the
    latest quarter present.
    """
    asking = listing.get("eur_m2")
    if not isinstance(asking, (int, float)) or asking <= 0:
        return None, ("Küsimishind €/m² puudub kuulutusest (EI OLE hinnangut): "
                      "Stat-ankrut ei saa arvutada — kontrolli kuulutuse "
                      "hinda, ära feigi")
    med = area_median(listing.get("area"), area_medians)
    if med is None:
        return None, ("Stat kvartali mediaanrea piirkonnale '%s' EI OLE "
                      "(PX-tabelis rida puudub): ankur-hinnang puudub — "
                      "hoone/tänava täpsusega compe küsi maaklerilt "
                      "(litsentseeritud hindaja väljavõte), ära feigi "
                      "hinnangut" % listing.get("area"))
    score = _clamp(100.0 * med / asking)
    return score, ("Stat kvartali mediaan %.0f €/m² piirkonnas '%s' vs "
                   "küsitav %.0f €/m²: õiglane-hind hinnang %d/100 "
                   "(100 = mediaanis/allpool; KK11-laadne tabel, hinnang — "
                   "hoone-täpsuse jalga EI OLE siin, see on "
                   "sõsarmoodulis)" % (med, listing.get("area"), asking,
                                       score))


# ---------------------------------------------------------------------------
# Coverage dims: the 9 remaining params off this source (issue #365).
# ---------------------------------------------------------------------------

def dim_price_history_dom_stat(listing: dict, area_medians: List[dict],
                               today: Optional[str] = None) -> Score:
    """P4-001: stale/desperate/overpriced vs steal from DOM + Stat anchor.

    Scores only stale ads (DOM >= 90 d or >= 2 cuts), anchored on the Stat
    quarterly area median. Fresh ads and missing adapter history stay NULL.
    The tehingud micro-comp anchor stays the sibling module's job.
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
    med = area_median(listing.get("area"), area_medians)
    if (not isinstance(asking, (int, float)) or asking <= 0
            or med is None):
        return None, ("Seisnud kuulutus (DOM %d p, %d langust), aga "
                      "Stat-ankrut EI OLE (piirkonna '%s' mediaanrida "
                      "puudub): steal-hinnang puudub — küsi compe"
                      % (dom, cuts, listing.get("area")))
    if asking <= med:
        return 85, ("Seisnud kuulutus (DOM %d p, %d hinnalangust) hinnaga "
                    "%.0f €/m² Stat mediaanis/allpool (%.0f €/m², '%s'): "
                    "võimaliku tehingukoha hinnang 85/100 (hoone-"
                    "täpsusega tehingute-jalga EI OLE siin)"
                    % (dom, cuts, asking, med, listing.get("area")))
    return 40, ("Seisnud kuulutus (DOM %d p, %d langust), aga küsitakse "
                "%.0f €/m² üle Stat mediaani (%.0f €/m²): üle hinnatud "
                "seisuja hinnang 40/100 (hoone-täpsusega tehingute-jalga "
                "EI OLE siin)" % (dom, cuts, asking, med))


def dim_rent_reality_stat(listing: dict, rents: List[dict]) -> Score:
    """P4-003: gross-yield context from the Stat rent table (Tallinn).

    Yield = 12 * area monthly-median rent / asking price. Airbnb density,
    KV-medians and the REL2021 rental-share/vacancy grid legs are not
    scored here (EI OLE) — KV-medians stay the adapter store's job, density
    the Inside-Airbnb-style check's, the grid the sibling module's.
    """
    price = listing.get("price_eur")
    if not isinstance(price, (int, float)) or price <= 0:
        return None, ("Kuulutuse koguhind puudub (EI OLE hinnangut): "
                      "tootluse ei saa arvutada — kontrolli kuulutuse "
                      "hinda, ära feigi")
    med_rent = None
    for r in latest_rows(rents, listing.get("area"), period_key="year"):
        v = _num(r, "median_rent_eur")
        if v is not None and v > 0:
            med_rent = v
            break
    if med_rent is None:
        return None, ("Stat üüri mediaanrea piirkonnale '%s' EI OLE "
                      "(üüri-tabelis rida puudub): tootluse hinnang puudub "
                      "— KV üüri-mediaanide jalga EI OLE siin, küsi "
                      "maaklerilt" % listing.get("area"))
    yld = 12.0 * med_rent / price
    if yld >= 0.05:
        score, word = 80, "tugev üüri-tootlus"
    elif yld >= 0.035:
        score, word = 65, "mõistlik tootlus"
    elif yld >= 0.025:
        score, word = 50, "nõrk tootlus"
    else:
        score, word = 35, "tootlus katab vaevalt kulusid"
    return score, ("Piirkonna '%s' üüri-mediaan %.0f €/kuu vs hind %.0f €: "
                   "bruto-tootluse hinnang %.1f%% (%s) %d/100 (Airbnb-"
                   "tiheduse + üürikorterite-osakaalu ruudustiku jalga EI "
                   "OLE)" % (listing.get("area"), med_rent, price,
                             yld * 100.0, word, score))


def dim_kov_fiscal_stat(listing: dict, kov_finance: List[dict]) -> Score:
    """P4-019: tax-hike/service-cut risk from the Stat KOV-budget table.

    Annual RR300/RR302-shaped rows (debt burden + operating result). The
    arengukava investment-table leg stays the sibling cityplans module's
    job; EMTA maamaks/audit legs are named EI OLE, not faked.
    """
    kov = listing.get("kov") or "Tallinn"
    rows = latest_rows(
        [{**r, "area": r.get("kov")} for r in kov_finance], kov,
        period_key="year")
    debt = res = None
    for r in rows:
        debt, res = _num(r, "debt_burden_pct"), \
            _num(r, "operating_result_per_capita")
        if debt is not None and res is not None:
            break
    if debt is None or res is None:
        return None, ("KOV '%s' eelarve-rea (võlakoormus/tulem) Stat tabelis "
                      "EI OLE — fiskaal-hinnang puudub: vaja RR300/RR302 "
                      "rida, ära feigi" % kov)
    if res >= 0 and debt <= 40:
        score, word = 75, "terve (madal võlg, ülejääk)"
    elif res >= 0 and debt <= 60:
        score, word = 60, "mõõdukas (jälgi võlga)"
    elif res >= 0:
        score, word = 45, "pinges (kõrge võlakoormus)"
    else:
        score, word = 35, "nõrk (tegevustulem miinuses)"
    return score, ("KOV '%s' võlakoormus %.0f%%, tegevustulem %+.0f €/elanik "
                   "(Stat eelarve-tabel, hinnang): fiskaal-tervise hinnang "
                   "%d/100 — %s (arengukava investeeringute + maamaksu-ajaloo "
                   "jalga EI OLE siin)" % (kov, debt, res, score, word))


def dim_micro_liquidity_stat(listing: dict, migration: List[dict]) -> Score:
    """P4-025: sellable in 10 yrs? from the Stat migration table (RVR02).

    Annual haldusuksus-grain net migration per 1000 residents. REL2021
    age/vacancy grid, school open/close plans and the tehingud turnover leg
    are not scored here (EI OLE) — the grid stays the rel2021 sibling's
    job, turnover the tehingud sibling's, plans Haridusamet's table.
    """
    rows = latest_rows(
        [{**r, "area": r.get("area") or r.get("kov")} for r in migration],
        listing.get("area") or listing.get("kov"), period_key="year")
    net = pop = None
    for r in rows:
        inm, out = _num(r, "in_migrants"), _num(r, "out_migrants")
        pop = _num(r, "population")
        if inm is not None and out is not None and pop:
            net = inm - out
            break
    if net is None or not pop:
        return None, ("Piirkonna '%s' rände-rea (sisse/välja + rahvaarv) "
                      "Stat tabelis EI OLE — likviidsuse rände-hinnang "
                      "puudub: vaja RVR02 rida, ära feigi"
                      % (listing.get("area") or listing.get("kov")))
    net_k = net / pop * 1000.0
    if net_k >= 10:
        score, word = 75, "pealetung (sissevool)"
    elif net_k >= -5:
        score, word = 60, "tasakaalus"
    elif net_k >= -20:
        score, word = 45, "väljavool (müügiperiood võib venida)"
    else:
        score, word = 30, "tugev väljavool (likviidsus-risk)"
    return score, ("Piirkonna '%s' rändesaldo %+.0f/1000 elaniku kohta "
                   "(Stat RVR02, hinnang): likviidsuse rände-hinnang %d/100 "
                   "— %s (vanuse/vakantsi-ruudustiku + kooliplaanide + "
                   "tehingute käibe jalga EI OLE siin)"
                   % (listing.get("area") or listing.get("kov"), net_k,
                      score, word))


def dim_bargaining_margin_stat(listing: dict,
                               price_index: List[dict]) -> Score:
    """P4-038: market-heat calibration from the Stat quarterly index.

    Quarter-over-quarter change of the dwelling-price index (IA028-shaped):
    a falling market widens the opening-bid room, a hot one narrows it.
    The area-type gap TABLE itself stays the tehingud sibling's job and is
    named EI OLE when unpublished.
    """
    rows = latest_rows(price_index, listing.get("area"))
    if not rows:
        rows = latest_rows(price_index, CITY)
        city_fallback = True
    else:
        city_fallback = False
    qoq = None
    for r in rows:
        qoq = _num(r, "index_qoq_pct")
        if qoq is not None:
            break
    if qoq is None:
        return None, ("Kvartali hinnaindeksi muutuse (IA028-laadne) "
                      "piirkonnale '%s' EI OLE — turu-kuumuse kalibratsiooni "
                      "hinnang puudub" % listing.get("area"))
    if qoq <= -2.0:
        score, word = 80, "langev turg (avamispakkumuses ruumi)"
    elif qoq <= 0.0:
        score, word = 65, "jahtuv turg"
    elif qoq <= 2.0:
        score, word = 50, "soojenev turg"
    else:
        score, word = 35, "kuum turg (ruumi vähe)"
    scope = " (linna-koondrida, hinnang)" if city_fallback else ""
    return score, ("Kvartali muutus %+.1f%% piirkonnas '%s'%s: turu-kuumuse "
                   "hinnang %d/100 — %s (piirkonnatüübi lõhe-TABELI jalga EI "
                   "OLE siin, see on sõsarmoodulis)"
                   % (qoq, listing.get("area"), scope, score, word))


def dim_number13_baseline_stat(listing: dict,
                               area_medians: List[dict]) -> Score:
    """P4-043: discount-for-the-unbothered flag on the Stat prestige baseline.

    The Stat leg is the LINNAOSA baseline (area median vs Tallinn median);
    the street residual stays the tehingud sibling's job, the education
    control the rel2021 sibling's. Taste-match flag, never a worth
    judgement about the street ("maitse-sobivus").
    """
    floor = listing.get("floor")
    house = str(listing.get("house_number") or "")
    mark13 = (floor == 13) or house.strip().startswith("13")
    if not isinstance(floor, int) and not house:
        return None, ("Korruse/maja numbrit kuulutuses EI OLE — 13-arbitraaži "
                      "hinnang puudub: kontrolli kuulutuse korrust, ära feigi")
    if not mark13:
        return None, ("13-märki (korrus/maja 13) EI OLE — arbitraaži-signaali "
                      "hinnang puudub")
    med = area_median(listing.get("area"), area_medians)
    city = area_median(CITY, area_medians)
    if med is None or city is None or city <= 0:
        return None, ("Stat baasjoone (piirkond + Tallinn) mediaanrea EI OLE "
                      "— 13-arbitraaži hinnang puudub: vaja PX-mediaaniridu")
    asking = listing.get("eur_m2")
    if not isinstance(asking, (int, float)) or asking <= 0:
        return None, ("Küsimishind €/m² puudub — 13-allahindluse hinnangut EI "
                      "OLE")
    prestige = "prestiižne" if med >= city else "tavahinnaga"
    if asking < med:
        score, word = 80, "allahindlus ebausu eest"
    elif asking == med:
        score, word = 60, "mediaanihind 13-märgiga"
    else:
        score, word = 45, "ebausk hinda ei alandanud"
    return score, ("13-märk (korrus %s, maja %s), piirkond '%s' %s (%.0f vs "
                   "Tallinn %.0f €/m²), küsitav %.0f €/m²: ebausu-"
                   "allahindluse hinnang %d/100 — %s (maitse-sobivus, mitte "
                   "väärtushinnang; tänava-jäägi jalga EI OLE siin)"
                   % (floor, house or "?", listing.get("area"), prestige,
                      med, city, asking, score, word))


def dim_permit_glut_stat(listing: dict, permits: List[dict]) -> Score:
    """P4-050: buying into falling prices? from the Stat EH-pipeline table.

    Latest-quarter permits/completions ratio per micro-area (EH04/EH05/
    EH06-shaped). A glut pipeline (permits far above completions) reads as
    falling-price risk. EHR per-building load/kasutusluba counts and the
    tehingud falling-price check stay out — EI OLE here (EHR counts are the
    EHR module's job, the price check the tehingud sibling's).
    """
    ratio = None
    for r in latest_rows(permits, listing.get("area")):
        pmt, cmp_ = _num(r, "permits"), _num(r, "completions")
        if pmt is not None and cmp_ is not None and cmp_ > 0 and pmt >= 0:
            ratio = pmt / cmp_
            break
    if ratio is None:
        return None, ("Piirkonna '%s' loa/kasutusloa-rea (EH-laadne) Stat "
                      "tabelis EI OLE — torustiku-hinnang puudub: vaja "
                      "ehitus- ja kasutuslubade rida, ära feigi"
                      % listing.get("area"))
    if ratio >= 2.0:
        score, word = 35, "loa-uputus (hinnalanguse risk)"
    elif ratio >= 1.2:
        score, word = 50, "torustik kasvab"
    elif ratio >= 0.8:
        score, word = 65, "tasakaalus torustik"
    else:
        score, word = 75, "hõre torustik (pakkumine ei suru)"
    return score, ("Piirkonna '%s' lubade/valmimiste suhe %.1f (Stat EH-"
                   "tabel, hinnang): torustiku-hinnang %d/100 — %s (EHR "
                   "hoone-põhiste lubade + tehingute hinna-jalga EI OLE "
                   "siin)" % (listing.get("area"), ratio, score, word))


def dim_zero_consumption_stat(listing: dict, empty: List[dict]) -> Score:
    """P4-051: dead-stairwell governance-risk flag from empty dwellings.

    Area grain ONLY (never addresses — privacy-safe by construction, per
    parameters4.md). Share of empty dwellings from the population-register
    shaped table. Elektrilevi/Vesi aggregated zero-consumption meters and
    KU aruannete remondifond legs are named EI OLE, not faked; the REL2021
    vacancy grid and arireg arrears legs stay the siblings' job.
    """
    share = None
    for r in latest_rows(empty, listing.get("area"), period_key="year"):
        shp = _num(r, "empty_dwellings")
        tot = _num(r, "dwellings")
        if shp is not None and tot and tot > 0 and shp >= 0:
            share = shp / tot
            break
    if share is None:
        return None, ("Piirkonna '%s' tühjade eluruumide rea "
                      "rahvastikuregistri-laadses tabelis EI OLE — tühjade-"
                      "korterite hinnang puudub: ruut/aadress TÄPSUST EI "
                      "FEIGITA" % listing.get("area"))
    if share >= 0.08:
        score, word = 35, "kõrge tühjus (surnud trepikoja risk)"
    elif share >= 0.04:
        score, word = 55, "mõõdukas tühjus"
    else:
        score, word = 70, "elatud piirkond"
    return score, ("Piirkonna '%s' tühje eluruume %.1f%% (rahvastikuregistri-"
                   "laadne tabel, hinnang — piirkonna-tase, mitte aadress): "
                   "tühjuse-hinnang %d/100 — %s (Elektrilevi/Vesi "
                   "nullkulu + KÜ remondifondi jalga EI OLE)"
                   % (listing.get("area"), share * 100.0, score, word))


def dim_last_shop_spiral_stat(listing: dict, fringe: List[dict]) -> Score:
    """P4-061: liquidity-spiral check for fringe settlements (Stat leg).

    Settlement-grain population change + deal turnover (Stat rahvastik +
    tehingute-arv shaped rows). The shop/pharmacy/ATM + bus-cut CHECKLIST
    stays the sibling modules' job (manual checklist / Peatus GTFS diffs /
    OSM closures / Elron timetable / aarealade-kava) and is named EI OLE
    when missing — a shrinking settlement without a checklist stays a
    named gap, never a guessed flag.
    """
    key = normalise_area(listing.get("settlement"))
    row = None
    for r in fringe:
        if normalise_area(r.get("settlement")) == key and key:
            row = r
            break
    if row is None:
        return None, ("Asula '%s' rahvastiku/tehingute-rea Stat tabelis EI "
                      "OLE — spiraali-hinnang puudub: vaja ääreasula rida, "
                      "ära feigi" % listing.get("settlement"))
    pop_ch = _num(row, "pop_change_pct")
    deals = _num(row, "deals_12mo")
    if pop_ch is None or deals is None:
        return None, ("Asula '%s' rida on poolik (rahvaarvu muutus/"
                      "tehingute arv) — spiraali-hinnangut EI OLE"
                      % listing.get("settlement"))
    if pop_ch >= 0 and deals >= 30:
        score, word = 70, "stabiilne ääreasula"
    elif pop_ch >= 0:
        score, word = 60, "kasvav, aga õhuke käive"
    elif deals >= 30:
        score, word = 50, "kahanev, aga käive püsib"
    else:
        score, word = 35, "likviidsus-spiraali risk (kahaneb + õhuke käive)"
    return score, ("Asula '%s' rahvaarv %+.1f%%, tehinguid %d/12 k (Stat, "
                   "hinnang): spiraali-hinnang %d/100 — %s (poe/apteegi/"
                   "sularaha + bussikärbete kontrollnimekirja jalga EI OLE "
                   "siin)" % (listing.get("settlement"), pop_ch, deals,
                              score, word))


P4_STAT_DIMS = (
    ("micro_comp_anchor", "P4-002", dim_stat_micro_comp_anchor),
    ("price_history_dom_stat", "P4-001", dim_price_history_dom_stat),
    ("rent_reality_stat", "P4-003", dim_rent_reality_stat),
    ("kov_fiscal_stat", "P4-019", dim_kov_fiscal_stat),
    ("micro_liquidity_stat", "P4-025", dim_micro_liquidity_stat),
    ("bargaining_margin_stat", "P4-038", dim_bargaining_margin_stat),
    ("number13_baseline_stat", "P4-043", dim_number13_baseline_stat),
    ("permit_glut_stat", "P4-050", dim_permit_glut_stat),
    ("zero_consumption_stat", "P4-051", dim_zero_consumption_stat),
    ("last_shop_spiral_stat", "P4-061", dim_last_shop_spiral_stat),
)


def score_p4_stat(listing: dict, tables: dict,
                  today: Optional[str] = None) -> Dict[str, Optional[int]]:
    """All 10 P4 Stat dims for one listing (keys match registry).

    tables keys: area_medians, rents, kov_finance, migration, price_index,
    permits, empty, fringe. Missing tables score their dims NULL (never a
    guessed join). dim_* return (score, reason); unwrapped to score-only.
    """
    tables = tables or {}
    out: Dict[str, Optional[int]] = {}
    for key, _pnum, fn in P4_STAT_DIMS:
        if fn is dim_price_history_dom_stat:
            out[key] = fn(listing, tables.get("area_medians") or [],
                          today)[0]
        elif fn is dim_stat_micro_comp_anchor:
            out[key] = fn(listing, tables.get("area_medians") or [])[0]
        elif fn is dim_rent_reality_stat:
            out[key] = fn(listing, tables.get("rents") or [])[0]
        elif fn is dim_kov_fiscal_stat:
            out[key] = fn(listing, tables.get("kov_finance") or [])[0]
        elif fn is dim_micro_liquidity_stat:
            out[key] = fn(listing, tables.get("migration") or [])[0]
        elif fn is dim_bargaining_margin_stat:
            out[key] = fn(listing, tables.get("price_index") or [])[0]
        elif fn is dim_number13_baseline_stat:
            out[key] = fn(listing, tables.get("area_medians") or [])[0]
        elif fn is dim_permit_glut_stat:
            out[key] = fn(listing, tables.get("permits") or [])[0]
        elif fn is dim_zero_consumption_stat:
            out[key] = fn(listing, tables.get("empty") or [])[0]
        else:
            out[key] = fn(listing, tables.get("fringe") or [])[0]
    return out
