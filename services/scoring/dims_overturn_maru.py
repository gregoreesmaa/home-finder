"""Overturn [MARU/Stat/ECB]: G16 market aggregates per-KOV choropleth (#241).

Scope: parameters3.md section 5.16 Group 16 params whose honest output is
a per-KOV CHOROPLETH / REGISTRY-TABLE JOIN -- never a walk-gradient
(nomap.md section 3 G16 verdict, which this PR deliberately does NOT
edit; the final index PR owns nomap.md). Five G16 params FLIP to
per-listing context dims off a quarterly KOV table; the rest stay NULL
with dated verdicts owned by dims_group16a.py (#205) / dims_group16b.py
(#206), which are READ here and never edited.

OPENNESS (probed 2026-09-13, 5 polite single GETs, labelled research
UA `home-finder-research/0.1 (... issue 241)`, paced >= 4 s, bodies at
/tmp/hf-maru-241/, never committed -- full log in docs/overturn_maru.md):
* MARU hinnastatistika query env (https://www.maaamet.ee/kinnisvara/
  htraru/): OPEN (HTTP 200, 23 kB, "Real property price statistics").
  The landing HTML carries Maakond + Omavalitsus (KOV) multi-selects
  (DDMaakond/DDOmavalitsus) -- per-KOV aggregation verified. The env
  is FORM-driven (JS postbacks): no anonymous bulk CSV URL is
  verified, so the quarterly KOV table is a caller-supplied
  maintainer export parsed by parse_maru_kov_csv (EHR gated-export
  precedent, dims_overturn_ehr.py #234) -- never scraped.
* MARU annual report "Eesti kinnisvaraturg 2025" (maaruum.ee):
  PUBLIC (HTTP 200 HEAD, application/pdf, 7 878 623 B) -- headers
  only, no bulk download pulled.
* Statistikaamet PxWeb (https://andmed.stat.ee/api/v1/et): OPEN
  (HTTP 200, 67 B, lists stat/statsql -- same as the #292/#365
  probe); hinnad folder OPEN (HTTP 200, 30 tables incl. IA027/IA028
  dwelling-price index). HH01/KK11 as literal codes stay a DATED
  PARTIAL-NEGATIVE (sibling dims_p4_stat.py tree traversal,
  2026-09-13 -- not re-traversed here out of politeness).
* ECB Data Portal SDMX (data-api.ecb.europa.eu): OPEN (HTTP 200,
  csvdata, lastNObservations=3). Latest print 2026-08: 6M Euribor
  2.7133333 % p.a. Series title says it all: "Euro area (changing
  composition)" -- NATIONAL by construction, so Euribor stays
  UNMAPPED (no dim, no choropleth band); ecb_latest_6m is a
  display-only context accessor, never a scorer.

HONESTY (AGENTS.md section 7.2): every scored shape here is an EXACT
KOV-TABLE JOIN (normalised exact match, latest quarter present) --
never a distance gradient, never interpolation across KOVs, never
cross-KOV smoothing. A missing KOV row stays NULL ("EI OLE") with an
Estonian reason naming the concrete check -- never a faked number.
Transport errors in fetch_cached are NEVER cached as data; HTTP 429
is a stop signal, not a retry dare (AGENTS.md 7.2/7.4).

Style: pure offline scorers (listing, rows, ...) -> (Optional[int
0..100], Estonian reason), mirroring dims_p4_stat.py (#292/#365).
Network lives ONLY in fetch_cached (polite single-GET + file cache +
TTL); tests never touch the network. No livability/WEIGHTS/layers
integration here -- rebalancing stays one joint change across
batches (existing tests pin WEIGHTS). Helpers are local copies (no
sibling imports): a future central hook may import this module
alongside them, and importing any of them here would turn that into
a cycle (batch B3 / PR #100 precedent).

Boundary vs siblings (no double-scoring, no overlap -- READ, not edited):
* dims_p4_stat.py (#292/#365) owns the P4 Stat-table legs off
  KK11-shaped area medians (P4-002 micro-comp anchor, P4-038 QoQ
  heat, ...). This module owns the G16 legs off the MARU KOV table:
  same honest join SHAPE, disjoint param sets and disjoint
  questions -- p41 scores YoY APPRECIATION (a year-apart pair),
  never the QoQ heat P4-038 owns; p421 scores the appraisal-GAP
  band, never the fair/steal anchor P4-002 owns. The rebalance
  follow-up must weight only one leg per question.
* dims_overturn_maa.py (#235) owns Maa-amet WFS per-PARCEL joins
  (cadastre/KKIS/soil) -- a different feed (parcels, not market
  aggregates); no median/volume dim exists there.
* dims_group16a/b.py (#205/#206) keep every other G16 verdict:
  national series/rules (p6/p156/p185), per-deal/per-borrower facts,
  US-jurisdiction concepts with no Estonian register, and the
  tax/fiscal tables outside this issue's three feeds.
* p1 purchase price (G1, dims_group01a) stays a LISTING fact: the
  asking-vs-KOV-median comparison lives HERE as G16 context
  (p421), never as a p1 area score.

Judgment calls (reviewable per AGENTS.md section 7.5):
* MARU KOV import schema is OURS (kov;quarter;median_eur_m2;deals,
  semicolon-separated, BOM-tolerant, unknown columns ignored):
  the query env verifies per-KOV aggregation but exposes no
  anonymous bulk contract, so the maintainer pastes the quarterly
  export into this shape (documented in docs/overturn_maru.md).
  The numbers stay MARU's; the column contract is the reviewable
  seam.
* p41 needs the SAME quarter a year apart (never adjacent-quarter
  annualisation -- seasonal new-build spikes would fake a trend).
* p149 deal-count bands are first-cut Harju judgments (Tallinn
  thousands/quarter, Viimsi low hundreds, small KOVs tens):
  challenge with a full quarterly KOV distribution.
* p43 is a composite of the p41 + p149 legs (depth + direction =
  resale): same table, distinct question -- P4-stat precedent
  (one table, many dims). A missing leg NULLs p43 (no half-comp).
* p484 is a WEAK flip (cap 70): MARU deals give velocity only;
  months-of-supply needs the KV-adapter inventory leg, which is
  named EI OLE, never guessed. QoQ pairs only, never trending.
* p481 price ceiling stays NULL (dated): a KOV max (luxury
  new-build) cannot cap ONE street's panel flats -- scoring it
  would invert the param's question. Street ceilings need micro-
  comps (restricted per-address leg, sibling tehingud territory).
* ECB TTL 7 d (parameters3.md section 5.16: weekly Euribor sync);
  MARU/Stat quarterly tables 91 d; refresh rhythm in
  docs/overturn_maru.md.

Integration (deliberately NOT done here): feeding these dims into
livability scoring, rebalancing livability.WEIGHTS, and updating
docs/nomap.md GROUP16 verdicts must be one joint change -- the
final docs-index PR owns nomap.md.
"""

import csv
import datetime as _dt
import io
import os
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Hunt/verdict date (2026-09-13) -- the day the five polite probes ran.
VERDICT_DATE = "2026-09-13"

#: Re-check the dated negatives (HH01/KK11 literal codes, MARU bulk
#: contract, p481 street-ceiling comps) no later than this date.
RECHECK_AFTER = "2027-03-13"

# ---------------------------------------------------------------------------
# Ingestion: polite fetch + cache + TTL (issue #241 acceptance crit. 1).
# ---------------------------------------------------------------------------

SOURCE_URLS = {
    # MARU hinnastatistika query env (probed 2026-09-13: HTTP 200,
    # per-KOV selects verified). FORM-driven: provenance constant,
    # NOT a fetch target -- the quarterly KOV table is a
    # maintainer-supplied export parsed by parse_maru_kov_csv.
    "maru_htraru": "https://www.maaamet.ee/kinnisvara/htraru/",
    # MARU annual report 2025 (probed 2026-09-13 HEAD: HTTP 200,
    # application/pdf, 7 878 623 B). Provenance only.
    "maru_annual_2025": ("https://maaruum.ee/sites/default/files/"
                         "documents/2026-02/Eesti%20kinnisvaraturg%202025.pdf"),
    # Stat PxWeb root + hinnad folder (probed 2026-09-13: HTTP 200;
    # 30 tables incl. IA027/IA028 -- HH01/KK11 substitutes).
    "stat_root": "https://andmed.stat.ee/api/v1/et",
    "stat_hinnad": "https://andmed.stat.ee/api/v1/et/stat/majandus/hinnad",
    # ECB 6M Euribor, monthly csvdata (probed 2026-09-13: HTTP 200;
    # latest print 2026-08 = 2.7133333 % p.a., euro-area national).
    "ecb_6m": ("https://data-api.ecb.europa.eu/service/data/FM/"
               "M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA?format=csvdata"),
}

#: TTLs in days: quarterly tables 91 d, ECB monthly series 7 d
#: (parameters3.md section 5.16: weekly Euribor sync).
TTL_DAYS = {
    "maru_quarterly": 91,  # maintainer-placed quarterly KOV export
    "stat_quarterly": 91,  # IA028-shaped index pulls
    "ecb_weekly": 7,       # 6M Euribor monthly prints
}

CACHE_SUBDIR = "hf-overturn-maru"
USER_AGENT = (
    "home-finder-research/0.1 (polite MARU/Stat/ECB overturn harvest; "
    "GitHub gregoreesmaa/home-finder issue 241)"
)


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
                raise RuntimeError("HTTP 429 -- stop, do not retry: " + url)
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
# Pure helpers (exact KOV-table join core -- hermetically tested).
# Local copies, no sibling imports (batch B3 / PR #100 precedent).
# ---------------------------------------------------------------------------

def normalise_kov(raw: Optional[str]) -> Optional[str]:
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


def latest_rows(rows: List[dict], kov: Optional[str]) -> List[dict]:
    """Rows for the exact KOV at the latest quarter present (no trending).

    Exact normalised-KOV match only; neighbouring KOVs NEVER leak in.
    """
    key = normalise_kov(kov)
    if not key:
        return []
    mine = [r for r in rows if normalise_kov(r.get("kov")) == key]
    if not mine:
        return []
    keys = sorted({_quarter_key(r.get("quarter")) for r in mine} - {None})
    if not keys:
        return mine
    latest = keys[-1]
    return [r for r in mine if _quarter_key(r.get("quarter")) == latest]


def kov_median(kov: Optional[str], rows: List[dict],
               quarter: Optional[str] = None) -> Optional[float]:
    """Latest-quarter (or pinned-quarter) MARU median EUR/m2, exact KOV."""
    if quarter is not None:
        key = normalise_kov(kov)
        cand = [r for r in rows
                if normalise_kov(r.get("kov")) == key
                and _quarter_key(r.get("quarter")) == _quarter_key(quarter)]
    else:
        cand = latest_rows(rows, kov)
    for r in cand:
        v = _num(r, "median_eur_m2")
        if v is not None and v > 0:
            return v
    return None


def kov_deals(kov: Optional[str], rows: List[dict],
              quarter: Optional[str] = None) -> Optional[int]:
    """Latest-quarter (or pinned-quarter) MARU deal count, exact KOV."""
    if quarter is not None:
        key = normalise_kov(kov)
        cand = [r for r in rows
                if normalise_kov(r.get("kov")) == key
                and _quarter_key(r.get("quarter")) == _quarter_key(quarter)]
    else:
        cand = latest_rows(rows, kov)
    for r in cand:
        v = _num(r, "deals")
        if v is not None and v >= 0:
            return int(v)
    return None


def kov_quarters(kov: Optional[str], rows: List[dict]) -> List[str]:
    """Sorted quarter labels present for the exact KOV (choropleth audit)."""
    key = normalise_kov(kov)
    out = sorted({_quarter_key(r.get("quarter")) for r in rows
                  if normalise_kov(r.get("kov")) == key} - {None})
    return ["%d-Q%d" % (y, q) for y, q in out]


def kov_latest_map(rows: List[dict], value_key: str) -> Dict[str, float]:
    """Per-KOV choropleth paint input: {normalised kov: latest value}.

    The registry-table half of the honest output shape: one value per
    KOV at the latest quarter present for THAT KOV (KOVs update
    independently -- never forward-filled, never smoothed).
    """
    kovs = {normalise_kov(r.get("kov")) for r in rows} - {None}
    out: Dict[str, float] = {}
    for kov in sorted(kovs):
        for r in latest_rows(rows, kov):
            v = _num(r, value_key)
            if v is not None:
                out[kov] = v
                break
    return out


# ---------------------------------------------------------------------------
# Parsers (pure; fixture-tested). The MARU KOV import schema is OURS
# (see docstring): the query env verifies per-KOV aggregation but
# exposes no anonymous bulk contract. The ECB csvdata column contract
# (TIME_PERIOD/OBS_VALUE) is live-verified 2026-09-13.
# ---------------------------------------------------------------------------

#: Canonical MARU KOV import columns (semicolon-separated, BOM-tolerant;
#: unknown columns ignored, missing numeric cells read as None).
MARU_KOV_COLUMNS = ("kov", "quarter", "median_eur_m2", "deals")


def parse_maru_kov_csv(csv_text: str) -> List[dict]:
    """Parse a maintainer-placed quarterly MARU KOV export.

    One row per (KOV, quarter); rows without a KOV or a parseable
    quarter are skipped (no join key -- keeping them would fake
    join coverage). Duplicate (KOV, quarter) rows: first wins.
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")),
                            delimiter=";")
    rows: List[dict] = []
    seen = set()
    for raw in reader:
        kov = (raw.get("kov") or "").strip()
        quarter = (raw.get("quarter") or "").strip()
        if not kov or _quarter_key(quarter) is None:
            continue
        dup = (normalise_kov(kov), _quarter_key(quarter))
        if dup in seen:
            continue
        seen.add(dup)
        row: dict = {"kov": kov, "quarter": quarter}
        for col in ("median_eur_m2", "deals"):
            cell = (raw.get(col) or "").strip().replace(" ", "")
            cell = cell.replace(",", ".")
            try:
                row[col] = float(cell) if cell else None
            except ValueError:
                row[col] = None
        rows.append(row)
    return rows


def parse_ecb_csv(csv_text: str) -> List[dict]:
    """Parse an ECB csvdata pull into [{month, euribor_6m_pct}].

    Keeps TIME_PERIOD + OBS_VALUE only (national monthly prints);
    non-numeric observations are skipped, never zero-filled.
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    rows: List[dict] = []
    for raw in reader:
        month = (raw.get("TIME_PERIOD") or "").strip()
        val = (raw.get("OBS_VALUE") or "").strip()
        if not month:
            continue
        try:
            rows.append({"month": month, "euribor_6m_pct": float(val)})
        except ValueError:
            continue
    return rows


def ecb_latest_6m(rows: List[dict]) -> Tuple[Optional[float], Optional[str]]:
    """Latest ECB 6M print (value, YYYY-MM) for DISPLAY context only.

    Deliberately NOT a scorer and NOT in OVERTURN_MARU_DIMS: a euro-area
    constant has no per-KOV join and must never be painted as a map.
    """
    dated = [(r.get("month"), r.get("euribor_6m_pct")) for r in rows
             if isinstance(r.get("month"), str)
             and isinstance(r.get("euribor_6m_pct"), (int, float))]
    if not dated:
        return None, None
    month, val = sorted(dated)[-1]
    return float(val), month


# ---------------------------------------------------------------------------
# p41: historical appreciation -- MARU KOV median YoY% (same quarter a
# year apart; never adjacent-quarter annualisation).
# ---------------------------------------------------------------------------

def _yoy_pct(kov: Optional[str], rows: List[dict]) -> Optional[float]:
    mine = latest_rows(rows, kov)
    if not mine:
        return None
    now_q = _quarter_key(mine[0].get("quarter"))
    if now_q is None:
        return None
    then = "%d-Q%d" % (now_q[0] - 1, now_q[1])
    med_now = kov_median(kov, rows)
    med_then = kov_median(kov, rows, quarter=then)
    if med_now is None or med_then is None or med_then <= 0:
        return None
    return (med_now - med_then) / med_then * 100.0


def dim_appreciation_p41(listing: dict, maru_kov: List[dict]) -> Score:
    """p41: KOV price momentum from the MARU quarterly median pair.

    Cooling/falling KOVs read buyer-friendly (room to bid); hot KOVs
    read overpay-risk. The QoQ HEAT question stays the P4-038 sibling
    leg's job -- this dim scores the year-apart APPRECIATION only.
    """
    kov = listing.get("kov")
    yoy = _yoy_pct(kov, maru_kov)
    if yoy is None:
        return None, ("KOV '%s' MARU mediaanide aastapaari (sama kvartal "
                      "aasta tagasi) EI OLE — kallinemise hinnang puudub: "
                      "vaja kvartali KOV-väljavõtet, ära feigi "
                      "hinnangut" % kov)
    if yoy <= -5.0:
        score, word = 75, "langus (ostjal ruumi)"
    elif yoy < 0.0:
        score, word = 65, "jahtumine"
    elif yoy <= 5.0:
        score, word = 50, "mõõdukas kasv"
    elif yoy <= 10.0:
        score, word = 40, "kiire kasv"
    else:
        score, word = 30, "ülekuumenenud (ülemaksmise risk)"
    latest = latest_rows(maru_kov, kov)[0].get("quarter")
    return score, ("KOV '%s' mediaan %s vs aasta tagasi %+.1f%% (MARU "
                   "kvartali KOV-tabel, hinnang): kallinemise hinnang "
                   "%d/100 — %s (kvartali-kuumuse jalga EI OLE siin, "
                   "see on P4-038 sõsarmoodulis)" % (kov, latest, yoy,
                                                     score, word))


# ---------------------------------------------------------------------------
# p149: market liquidity -- MARU KOV quarterly deal counts.
# ---------------------------------------------------------------------------

def dim_market_liquidity_p149(listing: dict, maru_kov: List[dict]) -> Score:
    """p149: how fast does this KOV turn? (deals in the latest quarter).

    First-cut Harju bands (challengeable): Tallinn thousands/quarter,
    Viimsi low hundreds, small KOVs tens. Thin KOVs read resale-risk,
    never a verdict -- the buyer still checks broker comps.
    """
    kov = listing.get("kov")
    deals = kov_deals(kov, maru_kov)
    if deals is None:
        return None, ("KOV '%s' tehingute-arvu rida MARU kvartali tabelis "
                      "EI OLE — likviidsuse hinnang puudub: vaja kvartali "
                      "KOV-väljavõtet, ära feigi hinnangut" % kov)
    if deals >= 300:
        score, word = 80, "sügav turg"
    elif deals >= 100:
        score, word = 65, "mõistlik käive"
    elif deals >= 30:
        score, word = 50, "hõre käive"
    else:
        score, word = 35, "õhuke turg (edasimüügi-risk)"
    latest = latest_rows(maru_kov, kov)[0].get("quarter")
    return score, ("KOV '%s' tehinguid %d (%s, MARU kvartali KOV-tabel, "
                   "hinnang): likviidsuse hinnang %d/100 — %s "
                   "(tehingu-KIIRUSE jalga EI OLE siin, see on "
                   "sõsarmoodulite käive)" % (kov, deals, latest, score,
                                              word))


# ---------------------------------------------------------------------------
# p421: appraisal gap risk -- asking EUR/m2 vs the MARU KOV median.
# THIS is where area-median-vs-listing-price lives (issue #241), NOT
# in p1: p1 stays a listing fact, this dim is its KOV context (a bank
# appraises near the median, so asking far above it risks a gap).
# ---------------------------------------------------------------------------

def dim_appraisal_gap_p421(listing: dict, maru_kov: List[dict]) -> Score:
    """p421: gap risk between the asking price and the KOV median."""
    asking = listing.get("eur_m2")
    kov = listing.get("kov")
    if not isinstance(asking, (int, float)) or asking <= 0:
        return None, ("Küsimishind €/m² puudub kuulutusest (EI OLE "
                      "hinnangut): lõhe-hinnangut ei saa arvutada — "
                      "kontrolli kuulutuse hinda, ära feigi")
    med = kov_median(kov, maru_kov)
    if med is None:
        return None, ("KOV '%s' MARU mediaanrida kvartali tabelis EI OLE "
                      "— lõhe-hinnang puudub: vaja KOV-väljavõtet, ära "
                      "feigi hinnangut" % kov)
    ratio = asking / med
    if ratio <= 1.0:
        score, word = 80, "mediaanis/allpool (lõhe ebatõenäoline)"
    elif ratio <= 1.10:
        score, word = 60, "kuni 10% üle mediaani"
    elif ratio <= 1.25:
        score, word = 45, "kuni 25% üle mediaani (lõhe võimalik)"
    else:
        score, word = 30, "üle 25% mediaanist (lõhe-risk)"
    return score, ("Küsitav %.0f €/m² vs KOV '%s' MARU mediaan %.0f €/m² "
                   "(suhe %.2f, hinnang): hindamisakti-lõhe hinnang "
                   "%d/100 — %s (panga hindamisakti jalga EI OLE siin; "
                   "p1 ostuhind jääb kuulutuse-faktiks, see on KOV-"
                   "kontekst)" % (asking, kov, med, ratio, score, word))


# ---------------------------------------------------------------------------
# p43: resale appeal -- composite of the p149 + p41 legs (depth +
# direction). Same table, distinct question (P4-stat precedent: one
# table, many dims). A missing leg NULLs p43 -- no half-comps.
# ---------------------------------------------------------------------------

def dim_resale_appeal_p43(listing: dict, maru_kov: List[dict]) -> Score:
    """p43: can I resell here? (KOV deal depth + median direction)."""
    kov = listing.get("kov")
    deals = kov_deals(kov, maru_kov)
    yoy = _yoy_pct(kov, maru_kov)
    if deals is None:
        return None, ("KOV '%s' tehingute-arvu rida MARU kvartali tabelis "
                      "EI OLE — edasimüügi hinnang puudub (sügavuse-jalga "
                      "pole): vaja kvartali KOV-väljavõtet, ära feigi "
                      "hinnangut" % kov)
    if yoy is None:
        return None, ("KOV '%s' MARU mediaanide aastapaari EI OLE — "
                      "edasimüügi hinnang puudub (suuna-jalga pole): vaja "
                      "sama kvartali rida aasta tagasi, ära feigi "
                      "hinnangut" % kov)
    if deals >= 100 and yoy >= 0.0:
        score, word = 70, "sügav + kasvav/stabiilne"
    elif deals >= 100:
        score, word = 55, "sügav, aga jahtuv"
    elif yoy >= 0.0:
        score, word = 50, "õhuke, aga stabiilne"
    else:
        score, word = 35, "õhuke + langev (edasimüügi-risk)"
    return score, ("KOV '%s' tehinguid %d/kv + mediaan %+.1f%% aastas "
                   "(MARU kvartali KOV-tabel, hinnang): edasimüügi "
                   "hinnang %d/100 — %s (maakleri võrdlustehingute "
                   "jalga EI OLE siin)" % (kov, deals, yoy, score, word))


# ---------------------------------------------------------------------------
# p484: absorption rate -- WEAK flip (cap 70). MARU deals give VELOCITY
# only (QoQ pair); months-of-supply needs the KV-adapter inventory leg,
# which is named EI OLE, never guessed.
# ---------------------------------------------------------------------------

def dim_absorption_p484(listing: dict, maru_kov: List[dict]) -> Score:
    """p484: deal-velocity context (weak absorption hinnang, lagi 70)."""
    kov = listing.get("kov")
    quarters = kov_quarters(kov, maru_kov)
    if len(quarters) < 2:
        return None, ("KOV '%s' MARU kvartalipaari (jooksev + eelmine) EI "
                      "OLE — käibe-hinnang puudub: vaja kahte järjestikust "
                      "KOV-rida, ära feigi hinnangut" % kov)
    now_d = kov_deals(kov, maru_kov, quarter=quarters[-1])
    prev_d = kov_deals(kov, maru_kov, quarter=quarters[-2])
    if now_d is None or prev_d is None or prev_d <= 0:
        return None, ("KOV '%s' tehingute-arvude paari (%s vs %s) MARU "
                      "tabelis EI OLE — käibe-hinnang puudub" % (
                          kov, quarters[-2], quarters[-1]))
    chg = (now_d - prev_d) / prev_d * 100.0
    if chg >= 10.0:
        score, word = 70, "käive kasvab"
    elif chg >= -10.0:
        score, word = 55, "käive stabiilne"
    else:
        score, word = 40, "käive langeb"
    return score, ("KOV '%s' tehinguid %d vs %d eelmises kvartalis (%+.1f%%, "
                   "MARU KOV-tabel, hinnang — NÕRK, lagi 70): imemise "
                   "hinnang %d/100 — %s (pakkumiste laoseisu KV-adapteri "
                   "jalga EI OLE siin)" % (kov, now_d, prev_d, chg, score,
                                           word))


OVERTURN_MARU_DIMS = (
    ("appreciation_maru", "p41", dim_appreciation_p41),
    ("market_liquidity_maru", "p149", dim_market_liquidity_p149),
    ("appraisal_gap_maru", "p421", dim_appraisal_gap_p421),
    ("resale_appeal_maru", "p43", dim_resale_appeal_p43),
    ("absorption_maru", "p484", dim_absorption_p484),
)

#: Registry key -> G16 param number (ecb_latest_6m is display-only and
#: deliberately absent: the euro-area constant has no per-KOV join).
OVERTURN_MARU_PARAM_IDS = {
    "appreciation_maru": 41,
    "market_liquidity_maru": 149,
    "appraisal_gap_maru": 421,
    "resale_appeal_maru": 43,
    "absorption_maru": 484,
}


def score_overturn_maru(listing: dict, tables: dict) -> Dict[str, Optional[int]]:
    """All 5 G16 MARU overturn dims for one listing (entry point for the
    weight-rebalance follow-up; keys match OVERTURN_MARU_DIMS).

    tables keys: maru_kov (quarterly KOV rows). Missing tables score
    their dims NULL (never a guessed join).
    """
    maru_kov = (tables or {}).get("maru_kov") or []
    return {key: fn(listing, maru_kov)[0]
            for key, _, fn in OVERTURN_MARU_DIMS}
