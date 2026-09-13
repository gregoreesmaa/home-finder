"""P4 REL2021 1 km grid dims: demo (#274) + coverage (#348).

Demo param (this ingestion's anchor):
* P4-025 Micro-liquidity (age/migration/vacancy + schools) -> dim_micro_liquidity_rel

Coverage params (extend the demoed ingestion, no new plumbing):
* P4-003 Rent reality + Airbnb density (rental-share/vacancy leg) -> dim_rent_reality_rel
* P4-011 Kindergarten queue + GP list (0-6 demand-pressure leg) -> dim_kindergarten_pressure_rel
* P4-043 Number-13 / name arbitrage (prestige-control leg) -> dim_number13_prestige_rel
* P4-044 Herd of picky people (occupation-mix leg) -> dim_herd_occupation_rel
* P4-045 Third places + keeper effect (evening-population leg) -> dim_third_place_demand_rel
* P4-051 Zero-consumption stairwells (vacancy leg) -> dim_zero_consumption_vacancy_rel
* P4-052 Turnover wave per building (migration leg) -> dim_turnover_migration_rel

OPENNESS VERDICT (probed 2026-09-13, 7 single polite GETs, 3 s pacing,
contact UA, cached /tmp/hf-p4-rel2021/ — full evidence in docs/p4_rel2021.md):
* Statistikaamet PX-Web API root + stat DB + rahvaloendus/rel2021 tree: OPEN
  (HTTP 200 throughout; 9 topic folders under rel2021).
* REL2021 PX tables (e.g. RL21003 age by residence): OPEN, but finest open
  geography is ASULA (settlement, 4868 values) / haldusuksus — confirmed in
  RL21003 variable metadata. NO 1 km-grid level exists in the traversed open
  tree.
* 1 km-grid bulk: DATED NEGATIVE for an open grid bulk — no grid-level table
  or download endpoint was found in the open PX-Web tree, so in production
  every grid-cell join below stays NULL with an Estonian reason. The join
  LOGIC (exact cell-ID match, privacy floor, no interpolation) is implemented
  and proven hermetically on synthetic fixtures here.
* Complementary open leg: the asula-level REL2021 tables ARE openly
  ingestible (cached + TTL below), so P4-025 carries an honest asula-choropleth
  fallback (labelled "ainult asula-jalg"), a legit shape per parameters4.md.

HONESTY (AGENTS.md section 7.2): the only scored shapes in this module are
the exact 1 km-CELL JOIN (opaque official cell ID, exact string match) and
the ASULA CHOROPLETH fallback — never a distance gradient, never
nearest-neighbour smoothing, never interpolation. A neighbouring cell's values
never leak into the listing's cell (pinned by test). Thin cells
(population < MIN_CELL_POP) and privacy-suppressed cells stay NULL ("EI OLE
piisavalt elanikke / allasurutud ruut"). Every NULL reason says "hinnang"
(estimate) and "EI OLE" and names the concrete check (open grid bulk,
lasteaia jarjekord, perearsti nimistu, kohapealne vaatlus) — never a faked
number. Transport errors in fetch_cached are NEVER cached as data, and
HTTP 429 is a stop signal, not a retry dare (AGENTS.md sections 7.2/7.4).

Style: pure offline scorers (listing, cells, ...) -> (Optional[int 0..100],
Estonian reason), mirroring sibling batch dims_p4_maa_tehingud.py (#244/#328).
Network lives ONLY in fetch_cached (polite single-GET + file cache + TTL);
tests never touch the network. No livability/WEIGHTS/layers integration here —
rebalancing stays one joint change across batches (existing tests pin WEIGHTS).

Overlap note (no double-score): P4-025/P4-043/P4-044/P4-052 already have
TEHINGUD legs in dims_p4_maa_tehingud.py. This module scores ONLY the
REL2021-grid legs and names the tehingud legs as the sibling module's job
(and vice versa) — complementary, never overlapping.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Demo + coverage paired in ONE PR because issue #348's body states it extends
  the #274 demo ingestion ("no new plumbing expected") — splitting would leave
  the demo unreviewable against its coverage contract (same precedent as
  #244/#328, #263/#343).
* MIN_CELL_POP = 100: 1 km cells below 100 residents are privacy-thin
  (Statamet suppresses small cells); scoring them would be fake precision.
* Cell IDs are opaque strings (fixture: "TLL-1km-NNNN"). No coordinate
  flooring helper is offered: inventing our own grid != the official REL2021
  grid, and a wrong-cell join is worse than NULL. Production IDs come from the
  open grid bulk when it appears — no code change needed (exact-match join).
* P4-044 scores taste-match ONLY (pealetulev maitseklaster vs hajus), never a
  worth judgement — "mitte vaartushinnang" is pinned in every reason.
* P4-052 migration wave scores neutral 50 with BOTH readings (problem vs
  gentrifying) in the reason, per parameters4.md — an ambiguous signal must
  not push the steal sort (same precedent as the tehingud turnover wave).
* Census tables are frozen (31.12.2021): TTL 365 d is a re-probe for a newly
  published open grid bulk, not a data refresh.
"""

import datetime as _dt
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (demo #274 acceptance criterion 2).
# ---------------------------------------------------------------------------

SOURCE_URLS = {
    # Open PX-Web API root (probed 2026-09-13: HTTP 200, lists stat/statsql).
    "px_root": "https://andmed.stat.ee/api/v1/et",
    # Open REL2021 topic tree (probed 2026-09-13: HTTP 200, 9 topic folders).
    "px_rel2021": (
        "https://andmed.stat.ee/api/v1/et/stat/rahvaloendus/rel2021"
    ),
    # Open asula-level age table metadata (probed 2026-09-13: HTTP 200;
    # finest open geography = asula, 4868 values — NO grid level).
    "px_RL21003": (
        "https://andmed.stat.ee/api/v1/et/stat/rahvaloendus/rel2021/"
        "rahvastiku_paiknemine/elukoht-ja-soo-vanusjaotus/RL21003.px"
    ),
    # 1 km-grid bulk: NO open endpoint found in the traversed tree
    # (dated negative 2026-09-13) — deliberately no URL here so nothing
    # unverified is ever fetched. Re-probe annually; an opened bulk plugs
    # into fetch_cached + TTL below with no scorer changes.
}

# TTLs in days. Census data are frozen at 31.12.2021, so rel_tables TTL is a
# re-probe for a newly published open grid bulk, not a refresh.
TTL_DAYS = {
    "rel_tables": 365,  # frozen census tables + annual grid-bulk re-probe
    "grid_bulk": 91,    # standby: quarterly once an open grid bulk appears
}

CACHE_SUBDIR = "hf-p4-rel2021"
USER_AGENT = (
    "home-finder-research/0.1 (polite annual bulk; "
    "GitHub gregoreesmaa/home-finder issues 274/348)"
)
MIN_CELL_POP = 100  # privacy floor: thinner/suppressed cells stay NULL
CHURN_WAVE_PER_1000 = 150.0  # P4-052 migration-wave threshold (12 mo)


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
# Pure helpers (exact cell-join core — hermetically tested).
# ---------------------------------------------------------------------------

def normalise_cell_id(raw: Optional[str]) -> Optional[str]:
    """Fold case + trim whitespace. Exact-match only (no fuzzy join)."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or None


def get_cell(cells: List[dict], cell_id: Optional[str]) -> Optional[dict]:
    """Exact cell-ID match. Neighbouring cells NEVER leak in (no gradient)."""
    want = normalise_cell_id(cell_id)
    if not want:
        return None
    for cell in cells:
        if normalise_cell_id(cell.get("cell_id")) == want:
            return cell
    return None


def cell_blocked_reason(cell: dict) -> Optional[str]:
    """Privacy/honesty gate: suppressed or thin cells are unusable (not zero)."""
    if cell.get("suppressed"):
        return "allasurutud"
    pop = cell.get("population")
    if not isinstance(pop, (int, float)) or pop < MIN_CELL_POP:
        return "liiga vähe elanikke"
    return None


def _num(cell: dict, key: str) -> Optional[float]:
    v = cell.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def _share(part: Optional[float], whole: Optional[float]) -> Optional[float]:
    if part is None or whole is None or whole <= 0 or part < 0:
        return None
    return part / whole


def _clamp(score: float) -> int:
    return max(0, min(100, int(round(score))))


def normalise_asula(raw: Optional[str]) -> Optional[str]:
    """Lowercase + collapse whitespace. Exact-match only (no fuzzy join)."""
    if raw is None:
        return None
    key = " ".join(str(raw).strip().lower().split())
    return key or None


def asula_youth_share(asum: Optional[str],
                      rows: List[dict]) -> Optional[float]:
    """Share aged 0-17 in an asula from RL21003-shaped rows.

    rows = [{"asum": str, "age_group": "0-6"|"7-17"|"18-64"|"65+", ...,
    "value": n}]. Returns None when the asula has no usable rows.
    """
    key = normalise_asula(asum)
    if not key:
        return None
    young = total = 0.0
    for r in rows:
        if normalise_asula(r.get("asum")) != key:
            continue
        v = r.get("value")
        if not isinstance(v, (int, float)) or v < 0:
            continue
        total += v
        if r.get("age_group") in ("0-6", "7-17"):
            young += v
    if total <= 0:
        return None
    return young / total


# ---------------------------------------------------------------------------
# Demo dim: P4-025 micro-liquidity (issue #274).
# ---------------------------------------------------------------------------

def dim_micro_liquidity_rel(listing: dict, cells: List[dict],
                            asula_rows: Optional[List[dict]] = None) -> Score:
    """P4-025: sellable in 10 yrs? from the REL2021 1 km cell (demo param).

    Prefers the exact grid-cell join (vacancy + net migration + age balance).
    Falls back to the honest asula choropleth (open PX-table shape, labelled
    "ainult asula-jalg"). School open/close plans are not in-snapshot
    (EI OLE) and are named, not faked; the tehingud turnover leg lives in
    the sibling module dims_p4_maa_tehingud.py.
    """
    cell = get_cell(cells, listing.get("cell_id"))
    if cell is not None:
        blocked = cell_blocked_reason(cell)
        if blocked is not None:
            return None, ("REL2021 1 km ruut %s on %s (privaatsus-põrand %d) "
                          "— likviidsuse hinnangut EI OLE: ruut on statistiliselt "
                          "liiga õhuke, ära feigi" % (cell.get("cell_id"),
                                                     blocked, MIN_CELL_POP))
        pop = _num(cell, "population")
        vac = _share(_num(cell, "vacant_dwellings"), _num(cell, "dwellings"))
        net = _num(cell, "in_migrants_12mo") - _num(cell, "out_migrants_12mo") \
            if _num(cell, "in_migrants_12mo") is not None \
            and _num(cell, "out_migrants_12mo") is not None else None
        net_k = (net / pop * 1000.0) if net is not None and pop else None
        a06, a717 = _num(cell, "age_0_6"), _num(cell, "age_7_17")
        young = _share(a06 + a717, pop) \
            if pop and a06 is not None and a717 is not None else None
        senior = _share(_num(cell, "age_65_plus"), pop)
        if vac is None or net_k is None or young is None or senior is None:
            return None, ("REL2021 ruudu %s kirjed on puudulikud (vakants/ "
                          "ränne/vanus) — likviidsuse hinnangut EI OLE: "
                          "poolik ruut, ära feigi" % cell.get("cell_id"))
        score = 60.0
        score += 10 if vac <= 0.08 else (0 if vac <= 0.15 else -15)
        score += 10 if net_k >= 20 else (0 if net_k >= -10 else -10)
        score += 10 if 0.15 <= young <= 0.30 else 0
        score -= 5 if senior > 0.30 else 0
        score = _clamp(score)
        return score, ("REL2021 1 km ruudu %s likviidsus-hinnang %d/100: "
                       "vakants %.0f%%, rändesaldo %+.0f/1000, noori %.0f%%, "
                       "65+ %.0f%% (kooli avamis/sulgemisplaanide jalga EI OLE; "
                       "tehingute käibe-jalg on sõsarmoodulis)"
                       % (cell.get("cell_id"), score, vac * 100.0, net_k,
                          young * 100.0, senior * 100.0))
    rows = asula_rows or []
    youth = asula_youth_share(listing.get("asum"), rows)
    if youth is None:
        return None, ("REL2021 1 km ruutu '%s' EI OLE (avatud ruudu-hulgilaadimist "
                      "pole) ja asumi '%s' vanuse ridu EI OLE — likviidsuse "
                      "hinnang puudub: vaja avatud ruudustikku või PX-tabelit, "
                      "ära feigi" % (listing.get("cell_id"), listing.get("asum")))
    score = 60 if 0.15 <= youth <= 0.30 else 50
    return score, ("Asumi '%s' noorte osakaal %.0f%% (avatud PX-vanusetabel, "
                   "hinnang): likviidsuse asula-hinnang %d/100 (AINULT "
                   "asula-jalg; 1 km ruudustiku-jalga + kooliplaanide jalga "
                   "EI OLE)" % (listing.get("asum"), youth * 100.0, score))


# ---------------------------------------------------------------------------
# Coverage dims: the 7 remaining params off this source (issue #348).
# ---------------------------------------------------------------------------

def _require_cell(listing: dict, cells: List[dict],
                  what: str) -> Tuple[Optional[dict], Optional[Score]]:
    """Exact cell join + privacy gate shared by the coverage dims.

    Returns (cell, None) when usable, else (None, NULL-score with reason).
    """
    cell = get_cell(cells, listing.get("cell_id"))
    if cell is None:
        return None, (None, ("REL2021 1 km ruutu '%s' EI OLE (avatud "
                             "ruudu-hulgilaadimist pole) — %s hinnang puudub: "
                             "vaja avatud ruudustikku, ära feigi"
                             % (listing.get("cell_id"), what)))
    blocked = cell_blocked_reason(cell)
    if blocked is not None:
        return None, (None, ("REL2021 1 km ruut %s on %s (privaatsus-põrand "
                             "%d) — %s hinnangut EI OLE: ruut on statistiliselt "
                             "liiga õhuke" % (cell.get("cell_id"), blocked,
                                              MIN_CELL_POP, what)))
    return cell, None


def dim_rent_reality_rel(listing: dict, cells: List[dict]) -> Score:
    """P4-003: yield/nuisance context from cell rental-share + vacancy.

    High rental share with high vacancy reads as nuisance-risk (low score);
    settled owner-majority cells read calm (high score). Airbnb density and
    KV-medians legs are not in-snapshot (EI OLE) and are named, not faked.
    """
    cell, null = _require_cell(listing, cells, "üüri/naabruskonna")
    if cell is None:
        return null  # type: ignore[return-value]
    rent = _num(cell, "rental_share")
    vac = _share(_num(cell, "vacant_dwellings"), _num(cell, "dwellings"))
    if rent is None or vac is None:
        return None, ("REL2021 ruudu %s üüri/vakantsi kirjed on puudulikud — "
                      "üürireaalsuse hinnangut EI OLE: poolik ruut, ära feigi"
                      % cell.get("cell_id"))
    if rent >= 0.40 and vac > 0.12:
        score, word = 35, "kõrge üüri-osakaal + vakants (nuisance-risk)"
    elif rent >= 0.25 or vac > 0.12:
        score, word = 55, "keskmine üüri/vakantsi-surve"
    else:
        score, word = 75, "rahulik omanike-enamusega ruut"
    return score, ("REL2021 ruudu %s üüri-osakaal %.0f%%, vakants %.0f%% (%s): "
                   "üürireaalsuse hinnang %d/100 (Airbnb-tiheduse + "
                   "KV-mediaanide jalga EI OLE)"
                   % (cell.get("cell_id"), rent * 100.0, vac * 100.0,
                      word, score))


def dim_kindergarten_pressure_rel(listing: dict, cells: List[dict]) -> Score:
    """P4-011: service-demand pressure from cell 0-6 cohort size.

    More small children per 1 km cell = longer queues (lower "can family use
    services" score). The Haridusamet queue table + Tervisekassa GP lists are
    not in-snapshot (EI OLE) — this is the demand-pressure leg only.
    """
    cell, null = _require_cell(listing, cells, "lasteaia/perearsti")
    if cell is None:
        return null  # type: ignore[return-value]
    kids = _num(cell, "age_0_6")
    if kids is None:
        return None, ("REL2021 ruudu %s 0-6 kirje puudub — "
                      "teenuskoormuse hinnangut EI OLE" % cell.get("cell_id"))
    if kids >= 300:
        score, word = 35, "kõrge koormus (lasteaia-järjekorra risk)"
    elif kids >= 150:
        score, word = 55, "keskmine koormus"
    else:
        score, word = 70, "madal koormus"
    return score, ("REL2021 ruudu %s 0-6-aastasi %.0f (%s): pereteenuste "
                   "hinnang %d/100 (Haridusameti järjekorra + perearsti "
                   "nimistute jalga EI OLE — ainult nõudlus-jalg)"
                   % (cell.get("cell_id"), kids, word, score))


def dim_number13_prestige_rel(listing: dict, cells: List[dict]) -> Score:
    """P4-043: discount-for-the-unbothered flag (13-mark x street residual).

    The REL2021 leg is the prestige CONTROL (cell higher-education share, so
    the residual is not mistaken for area worth). Taste-match flag, never a
    worth judgement; the tehingud-residual leg lives in the sibling module.
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
    cell, null = _require_cell(listing, cells, "13-arbitraaži")
    if cell is None:
        return null  # type: ignore[return-value]
    resid = listing.get("street_residual_vs_median")
    if not isinstance(resid, (int, float)):
        return None, ("13-märk on, aga tänava hinna-jääki (tehingute mediaan "
                      "vs küsitav) EI OLE — allahindluse hinnang puudub: vaja "
                      "sõsarmooduli tehingute-jalga")
    edu = _num(cell, "higher_education_share")
    edu_txt = ("prestiiži-kontroll kõrgharidus %.0f%%" % (edu * 100.0)) \
        if edu is not None else "prestiiži-kontrolli EI OLE (haridus-kirje puudub)"
    if resid <= -0.05:
        score, word = 80, "allahindlus ebausu eest"
    elif resid <= 0:
        score, word = 60, "väike allahindlus"
    else:
        score, word = 45, "ebausk hinda ei alandanud"
    return score, ("13-märk (korrus %s, maja %s), tänava-jääk %+.1f%%, %s: "
                   "ebausu-allahindluse hinnang %d/100 — %s (maitse-sobivus, "
                   "mitte väärtushinnang; hinna-ajaloo jalga EI OLE — ainult "
                   "hetke-jääk)"
                   % (floor, house or "?", resid * 100.0, edu_txt,
                      score, word))


def dim_herd_occupation_rel(listing: dict, cells: List[dict]) -> Score:
    """P4-044: leading-gentrification taste-match from occupation mix.

    Aggregated creative-occupation share (architects/chefs/lens jobs) at
    1 km. Grid taste-match ONLY — never a worth judgement about the people
    living there ("mitte vaartushinnang" pinned). The tehingud price-drift
    leg lives in the sibling module dims_p4_maa_tehingud.py.
    """
    cell, null = _require_cell(listing, cells, "loomeklastri")
    if cell is None:
        return null  # type: ignore[return-value]
    share = _share(_num(cell, "creative_occupations"), _num(cell, "employed"))
    if share is None:
        return None, ("REL2021 ruudu %s ametisegu kirjed on puudulikud — "
                      "klastri-hinnangut EI OLE: poolik ruut, ära feigi"
                      % cell.get("cell_id"))
    if share >= 0.12:
        score, word = 70, "pealetulev maitseklaster"
    elif share >= 0.06:
        score, word = 60, "tarkav loome-jalajälg"
    else:
        score, word = 50, "hajus (klastri-signaali pole)"
    return score, ("REL2021 ruudu %s loome-ametite osakaal %.1f%% (%s): "
                   "maitse-sobivuse hinnang %d/100 — mitte vaartushinnang, "
                   "ainult maitse-sobivus (hinna-triivi jalga EI OLE siin, "
                   "see on sõsarmoodulis)" % (cell.get("cell_id"),
                                              share * 100.0, word, score))


def dim_third_place_demand_rel(listing: dict, cells: List[dict]) -> Score:
    """P4-045: belonging-demand context from the evening-population grid.

    A cell that stays populated in the evening reads as lived-in (third
    places have customers); a dormitory-emptying cell reads quiet. OSM
    evening hours + long-tenure keeper independents are not in-snapshot
    (EI OLE) — this is the demand leg only.
    """
    cell, null = _require_cell(listing, cells, "õhtuse-kvartali")
    if cell is None:
        return null  # type: ignore[return-value]
    pop = _num(cell, "population")
    eve = _num(cell, "evening_population")
    ratio = _share(eve, pop)
    if ratio is None:
        return None, ("REL2021 ruudu %s õhtuse rahvastiku kirje puudub — "
                      "kuuluvuse hinnangut EI OLE" % cell.get("cell_id"))
    if ratio >= 0.95:
        score, word = 70, "elatud õhtune kvartal"
    elif ratio >= 0.80:
        score, word = 60, "mõõdukalt elatud õhtud"
    else:
        score, word = 45, "õhtuti tühjenev magalarajoon"
    return score, ("REL2021 ruudu %s õhtune rahvastik %.0f%% päevasest (%s): "
                   "kuuluvuse hinnang %d/100 (OSM õhtuste tundide + "
                   "püsikohvikute (keeper) jalga EI OLE — ainult nõudlus-jalg)"
                   % (cell.get("cell_id"), ratio * 100.0, word, score))


def dim_zero_consumption_vacancy_rel(listing: dict, cells: List[dict]) -> Score:
    """P4-051: dead-stairwell governance-risk flag from the vacancy leg.

    Cell-level ONLY (never addresses — privacy-safe by construction).
    Elektrilevi/Vesi aggregated zero-consumption + KU aruannete legs are not
    in-snapshot (EI OLE) and are named, not faked.
    """
    cell, null = _require_cell(listing, cells, "tühjade-korterite")
    if cell is None:
        return null  # type: ignore[return-value]
    vac = _share(_num(cell, "vacant_dwellings"), _num(cell, "dwellings"))
    if vac is None:
        return None, ("REL2021 ruudu %s vakantsi kirjed on puudulikud — "
                      "trepikoja-riski hinnangut EI OLE" % cell.get("cell_id"))
    if vac >= 0.20:
        score, word = 30, "tühjade korterite risk (surnud trepikoda?)"
    elif vac >= 0.10:
        score, word = 50, "mõõdukas vakants"
    else:
        score, word = 70, "elatud trepikojad"
    return score, ("REL2021 ruudu %s vakants %.0f%% (%s, ruudu-tasandil, mitte "
                   "aadressil): valitsemisriski hinnang %d/100 "
                   "(Elektrilevi/Vesi null-tarbimise + KÜ fondi jalga EI OLE)"
                   % (cell.get("cell_id"), vac * 100.0, word, score))


def dim_turnover_migration_rel(listing: dict, cells: List[dict]) -> Score:
    """P4-052: turnover reading from cell in/out migration (12-month window).

    Churn >= CHURN_WAVE_PER_1000 scores neutral 50 with BOTH readings
    (problem vs gentrifying) in the reason, per parameters4.md — an ambiguous
    signal must not push the steal sort. Normal churn stays NULL. The
    tehingud per-building wave lives in the sibling module.
    """
    cell, null = _require_cell(listing, cells, "rände-käibe")
    if cell is None:
        return null  # type: ignore[return-value]
    inm, outm = _num(cell, "in_migrants_12mo"), _num(cell, "out_migrants_12mo")
    pop = _num(cell, "population")
    if inm is None or outm is None or not pop:
        return None, ("REL2021 ruudu %s rände kirjed on puudulikud — "
                      "käibe-hinnangut EI OLE" % cell.get("cell_id"))
    churn = (inm + outm) / pop * 1000.0
    net = (inm - outm) / pop * 1000.0
    if churn < CHURN_WAVE_PER_1000:
        return None, ("REL2021 ruudu %s rändekäive %.0f/1000 (alla laine "
                      "%.0f/1000): tavaline käive, laine-hinnangut EI OLE"
                      % (cell.get("cell_id"), churn, CHURN_WAVE_PER_1000))
    return 50, ("REL2021 ruudu %s rändelaine: käive %.0f/1000, saldo "
                "%+.0f/1000 (hinnang 50/100, neutraalne): lugemine A — "
                "probleem (miks kõik lahkuvad? küsi KÜ-lt ja vaata kohapeal); "
                "lugemine B — pealetulev piirkond (sissevool). Kumbki lugemine "
                "EI OLE tõestatud" % (cell.get("cell_id"), churn, net))


# ---------------------------------------------------------------------------
# Registry + aggregator (entry point for the weight-rebalance follow-up).
# ---------------------------------------------------------------------------

P4_REL2021_DIMS = (
    ("micro_liquidity_rel", "P4-025", dim_micro_liquidity_rel),
    ("rent_reality_rel", "P4-003", dim_rent_reality_rel),
    ("kindergarten_pressure_rel", "P4-011", dim_kindergarten_pressure_rel),
    ("number13_prestige_rel", "P4-043", dim_number13_prestige_rel),
    ("herd_occupation_rel", "P4-044", dim_herd_occupation_rel),
    ("third_place_demand_rel", "P4-045", dim_third_place_demand_rel),
    ("zero_consumption_vacancy_rel", "P4-051", dim_zero_consumption_vacancy_rel),
    ("turnover_migration_rel", "P4-052", dim_turnover_migration_rel),
)


def score_p4_rel2021(listing: dict, cells: List[dict],
                     asula_rows: Optional[List[dict]] = None
                     ) -> Dict[str, Optional[int]]:
    """All 8 P4 REL2021 dims for one listing (keys match registry)."""
    out: Dict[str, Optional[int]] = {}
    for key, _pnum, fn in P4_REL2021_DIMS:
        if fn is dim_micro_liquidity_rel:
            out[key] = fn(listing, cells, asula_rows)
        else:
            out[key] = fn(listing, cells)
    # dim_* return (score, reason); unwrap to score-only for the aggregator.
    return {k: (v[0] if isinstance(v, tuple) else v)
            for k, v in out.items()}
